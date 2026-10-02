"""Owner Comment Detector - Optimized for T1 Owner Detection → T2 Reply Only
 
This module replaces the full comment monitor with a focused, high-performance
detector that ONLY tracks owner comments and replies instantly.

Key Optimizations:
- No BeautifulSoup parsing
- No tree building
- Incremental detection with known_ids
- Top-N comments only (not full scan)
- MutationObserver for real-time detection
- Direct DOM manipulation for instant replies
"""

import asyncio
import logging
import time
from typing import List, Optional, Set, Dict, Any, Callable
from datetime import datetime, timedelta
from playwright.async_api import Page

from ..models.comment import Comment
from ..scraper.facebook import FacebookScraper


logger = logging.getLogger(__name__)


class OwnerCommentDetector:
    """Ultra-fast owner comment detector focused on T1→T2 workflow only."""
    
    def __init__(self, scraper: FacebookScraper, config: dict):
        self.scraper = scraper
        self.config = config
        self.page: Page = scraper.page
        
        # Incremental detection state
        self.owner_name: Optional[str] = None
        self.post_url: str = ""
        self.monitoring_start_time: Optional[datetime] = None  # Track when monitoring started
        self.replied_comment_ids: Set[str] = set()  # Track comments we've already replied to
        self.bot_reply_texts: Set[str] = set()  # Track bot reply texts to prevent self-reply loop
        # SPEED: ID-based incremental detection. All comment IDs seen in past
        # sessions (loaded from DB at initialize) plus every scanned ID go
        # here. A comment is NEW only on first sight - independent of the
        # coarse relative timestamps, so brand-new comments with
        # seconds-level/unparseable timestamps are never skipped.
        self.known_ids: Set[str] = set()
        # Set by detect_new_owner_comments: True when the top ID changed or
        # the MutationObserver flagged activity. monitor_loop uses it to
        # re-scan after 50ms instead of waiting out the full interval.
        self.scan_saw_change: bool = False
        # SPEED (2026-08-23): while a reply is in flight, Facebook's submit
        # pipeline needs the page main thread. Our 200ms DOM scans + MutationObserver
        # callbacks compete with it and stretch the "กำลังโพสต์..." state (~4s).
        # The monitor loop checks this counter and pauses scanning until it hits 0.
        self.in_flight_replies: int = 0
        
        # Performance settings
        self.use_mutation_observer = True
        self.scan_count = 0  # Track scan count for periodic page reload
        self.last_reload_time = 0  # Track last reload timestamp
        self._last_logged_top_id = None  # SPEED: log scan details only when top ID changes
        # New Facebook UI: True once we know the post dialog exposes no comment
        # sort control, so the "no sort UI" notice is logged once, not on
        # every safety-net reload.
        self._sort_ui_unavailable_logged = False
        # Owner comments that existed before this monitor attached and were
        # never replied to. They bypass the "posted after monitoring started"
        # timestamp gate so a newly added post still gets answered.
        self._reply_backlog_ids: Set[str] = set()
        # MEASURED (2026-08-22): passive push delivers new comments ~2.4s after
        # posting, so periodic reload is only a safety-net now. Default 120s
        # (was 10s hard reload - the source of V5's ~10s detection latency).
        # TUNED DOWN to 45s (2026-08-23, production log): FB only pushes live
        # comments for roughly the first minute after a page load — after that
        # new comments NEVER enter the DOM until a reload (top comment ID was
        # frozen for 74s at 12:57-12:58). A 120s safety-net therefore meant
        # up to ~2 minutes of blindness; 45s caps worst-case latency while
        # keeping reload churn low.
        self.reload_interval_s = int(
            self.config.get('monitor', {}).get('reload_interval_s', 45)
        )
        # Full-feed sweep (display backfill): harvests the whole dialog
        # incl. replies every sweep_interval_s so the dashboard matches FB
        # even when the fast top-30 window misses comments (wrong sort).
        self.sweep_interval_s = int(
            self.config.get('monitor', {}).get('sweep_interval_s', 45)
        )
        self.last_sweep_time = 0.0
        # The sweep is awaited inline in the monitor loop, so it must not be
        # allowed to monopolise the page. Budget is in seconds.
        self.sweep_max_seconds = float(
            self.config.get('monitor', {}).get('sweep_max_seconds', 20)
        )
        
        # Callbacks
        self.on_owner_comment = None

        # Optional persistence for web visibility. When set (main_optimized
        # wires the real CommentDatabase here), every DOM scan upserts all
        # visible T1 comments so the dashboard shows the full feed - not
        # just comments the bot replied to.
        self.db = None
        
        # Stats
        self.stats = {
            'total_scans': 0,
            'owner_comments_detected': 0,
            'replies_posted': 0,
            'avg_detection_latency': 0.0,
            'avg_reply_latency': 0.0
        }
    
    async def initialize(self, post_url: str) -> bool:
        """Initialize detector for a specific post.
        
        Args:
            post_url: Facebook post URL to monitor
            
        Returns:
            True if initialization succeeded
        """
        try:
            self.post_url = post_url
            
            # Navigate to post
            logger.info(f"Initializing owner detector for: {post_url}")
            if not await self.scraper.navigate_to_post(post_url):
                logger.error("Failed to navigate to post")
                return False
            
            # Extract owner name (once, cached)
            self.owner_name = await self.scraper.get_post_author()
            if not self.owner_name:
                logger.error("Failed to detect post owner name")
                return False
            
            logger.info(f"OK Post owner detected: {self.owner_name}")
            
            # Switch to most recent view (if configured)
            sorting_mode = self.config.get('monitor', {}).get('sorting_mode', 'most_recent')
            if sorting_mode and sorting_mode != 'none':
                await self.scraper.switch_to_most_recent()
            
            # Install MutationObserver for real-time detection
            if self.use_mutation_observer:
                await self._install_mutation_observer()
                logger.info("OK MutationObserver installed for real-time detection")
            
            # Initialize last reload time
            self.last_reload_time = time.time()
            
            # Seed bot_reply_texts with the configured reply message so the bot
            # never treats its OWN past replies (which appear as owner comments
            # with the NEWEST IDs) as new comments to reply to — this prevents
            # the self-reply loop when the monitor restarts.
            reply_message = self.config.get('auto_reply', {}).get('reply_message', '')
            if reply_message:
                self.add_bot_reply_text(reply_message)
            
            # Record monitoring start time (BEFORE initial scan)
            self.monitoring_start_time = datetime.now()
            logger.info(f"Monitoring start time: {self.monitoring_start_time.strftime('%Y-%m-%d %H:%M:%S')}")

            # Load IDs seen in past sessions so timestamp-unparseable history
            # is never mistaken for new (restart-safe incremental detection).
            if self.db is not None:
                try:
                    self.known_ids = await self.db.get_comment_ids(post_url)
                    logger.info(f"Loaded {len(self.known_ids)} known comment IDs from DB")
                except Exception as e:
                    logger.warning(f"Could not load known IDs: {e}")

                # NEW POST: a post whose owner comments were captured but never
                # answered (display_order = 0) leaves the bot silent forever,
                # because those IDs are already "known" from a previous run.
                # With auto_reply.reply_to_existing enabled, un-claim them so
                # the first scan after attaching treats them as new work.
                reply_existing = self.config.get('auto_reply', {}).get(
                    'reply_to_existing', False)
                max_backlog = int(self.config.get('auto_reply', {}).get(
                    'max_backlog_replies', 3))
                if reply_existing and self.owner_name:
                    try:
                        owed = await self.db.get_unreplied_owner_comment_ids(
                            post_url, self.owner_name)
                        # Keep only the NEWEST few. Without this cap a post with
                        # 30 unanswered old owner comments makes the bot fire 30
                        # back-dated replies and spam the group.
                        if len(owed) > max_backlog:
                            owed = set(sorted(owed, key=int)[-max_backlog:])
                        if owed:
                            self.known_ids -= owed
                            self._reply_backlog_ids = owed
                            logger.info(
                                f"Auto-reply backlog: re-queued {len(owed)} "
                                f"unanswered '{self.owner_name}' comment(s) on this post"
                            )
                    except Exception as e:
                        logger.warning(f"Could not load auto-reply backlog: {e}")
            
            # Initial scan (no ID tracking needed)
            await self._initial_scan()
            
            logger.info(f"OK Initialization complete. Using timestamp filtering (start: {self.monitoring_start_time.strftime('%H:%M:%S')})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize owner detector: {e}")
            return False
    
    async def _initial_scan(self) -> None:
        """Initial scan - just wait a moment for page to stabilize.
        
        No need to track comment IDs - timestamp filtering handles everything.
        Called once during initialization.
        """
        try:
            logger.info("Initial scan: Using timestamp-based detection (no ID tracking needed)")
            
            # FORCE HARD RELOAD after initial scan to clear Facebook cache
            # This ensures we see fresh DOM with any new comments
            logger.info("Forcing hard reload to clear cache...")
            await self.page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(0.5)
            self.last_reload_time = time.time()
            
            # CRITICAL (2026-08-22): Facebook resets comment sorting back to
            # its default ("ความคิดเห็นทั้งหมด") on EVERY reload, undoing the
            # switch_to_most_recent() done earlier in initialize(). Re-apply
            # it BEFORE reinstalling the observer (the switch churns the DOM
            # and would otherwise flood the fresh observer with noise).
            await self._reapply_sort_mode_after_reload()
            
            # CRITICAL: Reload wipes the JS context, so the MutationObserver
            # installed in initialize() is gone. Reinstall it now.
            if self.use_mutation_observer:
                await self._install_mutation_observer()
                logger.info("MutationObserver reinstalled after initial reload")
            
            logger.info("Hard reload complete - ready for fresh comments")
            
        except Exception as e:
            logger.warning(f"Initial scan failed: {e}")
    
    async def _reapply_sort_mode_after_reload(self) -> None:
        """Re-apply the configured comment sorting mode after a page reload.

        MEASURED (2026-08-22, production log): Facebook resets comment sorting
        to its default ("ความคิดเห็นทั้งหมด" / All comments) on EVERY reload.
        Without this call the page silently falls back to "All comments" after
        the initial hard reload and after every periodic safety-net reload,
        hiding the newest comments from BOTH the user's visible screen AND the
        DOM scan (newest-first ordering is required for top-N detection).

        EXCEPTION - new Facebook UI: the 2026 post dialog exposes no sort
        control at all (no text trigger, no gear menu). ``switch_sorting_mode``
        probes both UIs and caches the verdict in ``scraper.sort_ui_available``;
        when it is False we stop paying for the probe and lean on the full
        sweep + ID ordering, which recovers the same rows without sorting.
        """
        sorting_mode = self.config.get('monitor', {}).get('sorting_mode', 'most_recent')
        if not sorting_mode or sorting_mode == 'none':
            return
        try:
            switched = await self.scraper.switch_sorting_mode(sorting_mode)
            if switched:
                logger.info(f"OK Re-applied '{sorting_mode}' sorting after reload")
                return

            if getattr(self.scraper, 'sort_ui_available', None) is False:
                # New UI: report once, then stay quiet - this repeats after
                # every safety-net reload and the answer cannot change while
                # Facebook keeps serving the same layout.
                if not self._sort_ui_unavailable_logged:
                    self._sort_ui_unavailable_logged = True
                    logger.warning(
                        f"New Facebook UI: no comment sort control on this post, so "
                        f"'{sorting_mode}' cannot be selected. Continuing with full "
                        f"sweep + numeric comment-ID ordering (same rows, newest last)."
                    )
                return

            # Non-fatal: switch_sorting_mode already retried ~6x; the next
            # safety-net reload will try again.
            logger.warning(
                f"Could not re-apply '{sorting_mode}' sorting after reload "
                f"(will retry at next safety-net reload)"
            )
        except Exception as e:
            logger.warning(f"Error re-applying sort mode after reload: {e}")
    
    async def _install_mutation_observer(self) -> None:
        """Install MutationObserver to detect new comments in real-time.
        
        MEASURED FACT (2026-08-22, measure_refresh.py, n=4): Facebook delivers
        remote comments passively ~2.4s after posting, but inserts them as a
        PLAIN DIV wrapper + characterData fill - it does NOT append
        div[role=article] or comment_id links as new nodes. The old observer
        (article/comment_id-only) therefore NEVER fired and the bot fell back
        to its 10s reload policy. This observer watches ALL node additions +
        text changes near the comment feed instead.
        """
        try:
            await self.page.evaluate("""
                () => {
                    if (window.__ownerDetectorObserver) {
                        window.__ownerDetectorObserver.disconnect();
                    }
                    
                    window.__newCommentIds = window.__newCommentIds || [];
                    window.__feedActivity = 0;
                    
                    const observer = new MutationObserver((mutations) => {
                        for (const mutation of mutations) {
                            // Track text changes anywhere (FB fills the new
                            // comment's content via characterData updates).
                            if (mutation.type === 'characterData') {
                                window.__feedActivity++;
                                continue;
                            }
                            
                            for (const node of mutation.addedNodes) {
                                if (node.nodeType !== 1) continue;
                                window.__feedActivity++;
                                
                                // Path A: a real article node appeared (some FB
                                // surfaces still do this) - extract its ID.
                                let articles = [];
                                if (node.getAttribute && node.getAttribute('role') === 'article') {
                                    articles.push(node);
                                }
                                if (node.querySelectorAll) {
                                    articles = articles.concat(Array.from(node.querySelectorAll('[role="article"]')));
                                }
                                for (const article of articles) {
                                    const link = article.querySelector('a[href*="comment_id="]');
                                    if (!link) continue;
                                    // FIX (2026-08-23): accept NON-NUMERIC ids too
                                    // (profile pfbid posts) - digit-only regex
                                    // dropped every comment on such pages.
                                    const match = link.href.match(/comment_id=([^&#]+)/);
                                    if (match && !window.__newCommentIds.includes(match[1])) {
                                        window.__newCommentIds.push(match[1]);
                                        console.log('[OwnerDetector] New article detected:', match[1]);
                                    }
                                }
                            }
                        }
                    });
                    
                    const target = document.querySelector('body');
                    if (target) {
                        observer.observe(target, { 
                            childList: true, 
                            subtree: true,
                            characterData: true 
                        });
                        window.__ownerDetectorObserver = observer;
                        console.log('[OwnerDetector] Broad MutationObserver installed');
                    }
                }
            """)
            
        except Exception as e:
            logger.warning(f"Failed to install MutationObserver: {e}")
    
    async def detect_new_owner_comments(self) -> List[Comment]:
        """Detect new owner comments (T1 only) using incremental approach.
        
        This is the core detection method - called in the monitoring loop.
        Only returns NEW comments from the OWNER.
        
        Returns:
            List of new owner Comment objects (empty if none found)
        """
        detect_start = datetime.now()
        new_owner_comments = []
        
        try:
            self.stats['total_scans'] += 1
            
            # Step 1: Check MutationObserver for instant detection
            mutation_ids = await self._get_mutation_observer_comments()
            if mutation_ids:
                logger.info(f"MutationObserver detected {len(mutation_ids)} new comment(s)")
            
            # Step 2: Get TOP 30 newest comments to check for new ones.
            # MEASURED (2026-08-22): FB passively delivers new comments into the
            # open page ~2.4s after posting (plain DIV + text fill), so a plain
            # DOM scan is enough - NO reload, NO sort-mode toggle needed.
            # The reload below is only a periodic safety-net for missed events.
            # 30 (was 20, 2026-08-23): headroom so an owner comment is not
            # pushed out of the scan window when many OTHER people's comments
            # interleave between scans (non-owner comments are filtered later
            # by the author check, but they still occupy window slots).
            raw_comments = await self._get_top_n_comments(n=30)

            # SPEED: flag scans that saw change so monitor_loop re-scans in
            # 50ms instead of waiting out the full interval.
            self.scan_saw_change = bool(mutation_ids)
            if raw_comments:
                top_id = raw_comments[0].get('id')
                if top_id != self._last_logged_top_id:
                    self.scan_saw_change = True
            
            # Step 2b: Persist the whole visible scan so the web dashboard
            # mirrors Facebook, not just bot-replied comments. Throttled:
            # on top-ID change (new arrival) or every ~5s of scanning.
            top_id_now = raw_comments[0].get('id') if raw_comments else None
            if self.db is not None and raw_comments and (
                top_id_now != self._last_logged_top_id
                or self.stats['total_scans'] % 25 == 0
            ):
                await self._persist_scan(raw_comments)

            # [DEBUG] Log what we see with timestamp info.
            # SPEED (2026-08-23): log only when the top ID CHANGES (new comment
            # arrived) - logging every ~300ms scan produced 46k lines/hour and
            # measurable file I/O overhead on the monitor loop.
            if raw_comments:
                top_id = raw_comments[0].get('id')
                if top_id != self._last_logged_top_id:
                    self._last_logged_top_id = top_id
                    logger.debug(f"Found {len(raw_comments)} comments in scan (top={top_id})")
                    for i, comment in enumerate(raw_comments[:5], 1):
                        logger.debug(f"  [{i}] ID={comment.get('id')}, Author={comment.get('author')[:20]}..., Timestamp={comment.get('timestamp')}")
            
            # Step 3: Filter for NEW owner comments using timestamp + author matching
            skipped_old = 0
            candidate_comments = []  # Collect all matching comments, then pick the NEWEST
            
            for raw in raw_comments:
                comment_id = raw.get('id')
                author = raw.get('author', '')
                timestamp_str = raw.get('timestamp', '')

                # SPEED: ID-based incremental filter. IDs from past sessions
                # were loaded from DB at initialize; every scanned ID is
                # recorded. First sight = new, regardless of timestamp
                # coarseness - this is what catches seconds-old comments.
                if not comment_id:
                    continue
                if comment_id in self.known_ids or comment_id in self.replied_comment_ids:
                    skipped_old += 1
                    continue
                self.known_ids.add(comment_id)

                # Parse timestamp to check if comment is NEW (after monitoring started)
                # ID-based filtering above already removed anything seen
                # before, so an unparseable/missing timestamp here means a
                # first-sight comment (typically seconds old, still rendering)
                # -> treat as age 0 instead of skipping it.
                comment_age_minutes = 0
                in_backlog = comment_id in self._reply_backlog_ids
                if self.monitoring_start_time and timestamp_str and not in_backlog:
                    parsed = self._parse_facebook_timestamp(timestamp_str)
                    if parsed is not None:
                        # Calculate when comment was posted
                        comment_posted_time = datetime.now() - timedelta(minutes=parsed)
                        
                        # Skip if comment is OLDER than monitoring start time
                        if comment_posted_time < self.monitoring_start_time:
                            skipped_old += 1
                            continue
                        comment_age_minutes = parsed
                
                # Check if from owner (compare first 10 characters - Facebook may truncate names)
                if not self.owner_name or len(self.owner_name) < 10:
                    continue
                if len(author) < 10:
                    continue
                
                owner_prefix = self.owner_name[:10].lower()
                author_prefix = author[:10].lower()
                if owner_prefix != author_prefix:
                    continue
                
                # Skip if we've already replied to this comment
                if comment_id in self.replied_comment_ids:
                    continue
                
                # Skip if comment text matches bot's own reply message (prevent self-reply loop)
                comment_message = raw.get('message', '')
                if comment_message in self.bot_reply_texts:
                    logger.debug(f"Skipping bot reply comment {comment_id}: '{comment_message[:40]}...'")
                    continue
                    
                # This is a NEW owner comment! Add as candidate
                candidate_comments.append({
                    'comment_id': comment_id,
                    'author': author,
                    'message': raw.get('message', ''),
                    'timestamp_str': timestamp_str,
                    'comment_age_minutes': comment_age_minutes
                })
            
            # Sort candidates by newest first.
            # Facebook timestamps are coarse ("X hours ago"), so age alone can't
            # order comments within the same hour. Facebook comment IDs are assigned
            # chronologically (monotonic snowflake IDs), so a HIGHER id is ALWAYS a
            # NEWER comment. Use comment ID (descending) as the primary sort key —
            # this is far more precise than the coarse relative timestamp.
            # FIX (2026-08-23): profile (pfbid) posts have NON-NUMERIC comment ids,
            # which crashed int(). Non-numeric ids get a constant key so the
            # STABLE sort keeps their DOM order (= newest first as scanned).
            def _newest_first_key(cid: str):
                if cid.isdigit():
                    return (0, -int(cid))
                return (1, 0)

            candidate_comments.sort(key=lambda c: _newest_first_key(c['comment_id']))
            
            for cand in candidate_comments:
                comment_id = cand['comment_id']
                comment = Comment(
                    id=comment_id,
                    parent_id=None,
                    tier=1,
                    author=cand['author'],
                    message=cand['message'],
                    created_time=datetime.now(),
                    last_seen=datetime.now(),
                    display_order=0,
                    is_new=True,
                    children=[]
                )
                
                new_owner_comments.append(comment)
                self.stats['owner_comments_detected'] += 1
                
                logger.info(f"✅ NEW OWNER COMMENT DETECTED: {comment_id}")
                logger.info(f"  Author: {cand['author']}")
                logger.info(f"  Timestamp: {cand['timestamp_str']}")
                logger.info(f"  Message: {comment.message[:50]}...")
                
                # Trigger callback if registered
                if self.on_owner_comment:
                    await self.on_owner_comment({
                        'comment_id': comment_id,
                        'author': cand['author'],
                        'text': comment.message
                    })
                
                # IMPORTANT: Reply to ONLY the newest comment, then stop
                break
            
            # Update detection latency stats
            detection_time = (datetime.now() - detect_start).total_seconds()
            self._update_avg_latency('detection', detection_time)
            
            if new_owner_comments:
                logger.info(f"⚡ Detection latency: {detection_time*1000:.1f}ms")
            
            return new_owner_comments
            
        except Exception as e:
            logger.error(f"Error in detect_new_owner_comments: {e}")
            # Do not spin forever on a dead browser - monitor_loop exits
            # on this so cleanup() runs instead of error-spamming.
            if 'has been closed' in str(e) or 'Target closed' in str(e):
                raise
            return []

    async def _persist_scan(self, raw_comments: List[Dict[str, Any]]) -> None:
        """Upsert visible scan rows for web-dashboard visibility.

        Handles T1 and T2 (replies carry parent_id). Best-effort: never let
        a DB hiccup break the detection loop. Skips rows without a comment
        ID or author (unparseable DOM).

        MUST NOT touch ``known_ids``. Persistence is display-only; ownership
        of the "seen it" bookkeeping belongs to detect_new_owner_comments,
        which decides what still needs a reply. Adding IDs here made the
        periodic full sweep (which persists the whole feed) claim every new
        comment BEFORE the fast path could answer it - so the bot never
        replied to anything the sweep happened to see first.
        """
        try:
            if self.db is None:
                return
            now = datetime.now()
            batch = []
            for raw in raw_comments:
                cid = raw.get('id')
                author = (raw.get('author') or '').strip()
                if not cid or not author:
                    continue
                age = self._parse_facebook_timestamp(raw.get('timestamp', ''))
                created = now - timedelta(minutes=age) if age is not None else now
                batch.append(Comment(
                    id=cid,
                    parent_id=raw.get('parent_id'),
                    tier=raw.get('tier', 1) or 1,
                    author=author,
                    message=raw.get('message', '') or '',
                    created_time=created,
                    last_seen=now,
                    display_order=0,
                    is_new=False,
                    children=[]
                ))
            if batch:
                await self.db.upsert_scanned(batch, self.post_url)
        except Exception as e:
            logger.warning(f"Scan persist skipped: {e}")

    async def _expand_reply_threads(self, rounds: int = 3, batch: int = 4,
                                       click_timeout: int = 1200) -> int:
        """Click 'view replies' buttons so nested T2 articles render.

        Best-effort, bounded: ``rounds`` passes x ``batch`` buttons with short
        timeouts. Returns number of buttons clicked.
        """
        clicked = 0
        try:
            for _ in range(rounds):
                buttons = await self.page.query_selector_all(
                    'div[role="button"]:has-text("ดูการตอบกลับ"), '
                    'span:has-text("ดูการตอบกลับ"), '
                    'div[role="button"]:has-text("View"), '
                    '[role="button"]:has-text("repl")'
                )
                fresh = 0
                for btn in buttons[:batch]:
                    try:
                        if not await btn.is_visible():
                            continue
                        await btn.scroll_into_view_if_needed(timeout=800)
                        await btn.click(timeout=click_timeout)
                        fresh += 1
                    except Exception:
                        continue
                clicked += fresh
                if not fresh:
                    break
                await asyncio.sleep(0.4)
        except Exception as e:
            logger.debug(f"Reply expansion skipped: {e}")
        if clicked:
            logger.info(f"Sweep expand: clicked {clicked} 'view replies' button(s)")
        return clicked

    async def _scroll_comments_step(self, amount: int = 800) -> None:
        """Advance the comment list by one screen.

        The post dialog scrolls inside its OWN container, so ``window.scrollBy``
        alone moves the page behind the dialog and the comment list never
        advances - that is why a window-only sweep kept re-reading the same
        first handful of comments. Scroll every scrollable ancestor of the
        comment articles as well as the window.
        """
        await self.page.evaluate(
            """() => {
                window.scrollBy(0, {amount});
                let anchor = document.querySelector('div[role="article"]');
                let node = anchor;
                let guard = 0;
                while (node && guard++ < 12) {
                    if (node.scrollHeight > node.clientHeight + 200) {
                        node.scrollTop += {amount};
                    }
                    node = node.parentElement;
                }
                for (const d of document.querySelectorAll('div[role="dialog"]')) {
                    if (d.scrollHeight > d.clientHeight + 200) {
                        d.scrollTop += {amount};
                    }
                }
            }""".replace('{amount}', str(amount))
        )

    async def _reset_scroll_to_top(self) -> None:
        """Rewind the window AND every scrollable comment container to the top.

        The comment list is virtualized: once a sweep has walked it to the
        bottom, the top comments are unmounted from the DOM. Without this
        rewind the NEXT sweep starts on an empty region and reports 0 rows
        forever (observed live: 5 rows, then 0 rows on every later sweep).
        """
        await self.page.evaluate(
            """() => {
                window.scrollTo(0, 0);
                for (const d of document.querySelectorAll('div[role="dialog"]')) {
                    d.scrollTop = 0;
                }
                let node = document.querySelector('div[role="article"]');
                let guard = 0;
                while (node && guard++ < 12) {
                    if (node.scrollHeight > node.clientHeight + 200) {
                        node.scrollTop = 0;
                    }
                    node = node.parentElement;
                }
            }"""
        )

    async def _full_sweep(self, max_seconds: float = 8.0) -> None:
        """Periodic whole-feed harvest for display completeness.

        Scrolls the whole comment list, expands reply threads, and persists
        every T1+T2 found. Catches comments that never enter the fast top-30
        window (relevance ordering, virtualized feed). Persist only - never
        triggers replies (the fast path owns that, guarded by known_ids).

        HARD TIME BUDGET. The sweep is awaited inline by the monitor loop, so
        every second it spends is a second the 200ms detection path is blind.
        On a post with many reply threads the unbounded version spent ~60s
        clicking "view replies", during which no new comment could be seen.
        ``max_seconds`` caps that; a partial sweep is still useful because the
        next one starts from the same accumulated rows in the DB.
        """
        deadline = time.time() + max_seconds
        try:
            logger.info("Full sweep: harvesting whole feed...")
            await self._reset_scroll_to_top()
            await asyncio.sleep(0.4)
            seen: Dict[str, Dict[str, Any]] = {}
            stalemate = 0
            for rnd in range(25):
                # Reply threads only render after their "view replies" click,
                # and scrolling in more comments adds new collapsed threads.
                # Clicking is the expensive step, so do it every 3rd round
                # instead of every round.
                if rnd % 3 == 0:
                    await self._expand_reply_threads(rounds=1, batch=4,
                                                     click_timeout=1200)
                rows = await self._parse_articles(top_n=0, include_replies=True)
                new = 0
                for r in rows:
                    key = f"{r.get('tier', 1)}:{r.get('id')}"
                    if key not in seen:
                        seen[key] = r
                        new += 1
                if new == 0:
                    stalemate += 1
                    # Facebook fetches the next page asynchronously; two idle
                    # rounds in a row is not enough evidence that the list
                    # ended, so require four before giving up.
                    if stalemate >= 4:
                        break
                else:
                    stalemate = 0
                if time.time() >= deadline:
                    logger.debug("Full sweep hit its time budget, stopping early")
                    break
                await self._scroll_comments_step()
                await asyncio.sleep(0.5)
            await self._reset_scroll_to_top()
            all_rows = list(seen.values())
            t2 = sum(1 for r in all_rows if r.get('tier') == 2)
            logger.info(f"Full sweep: {len(all_rows)} rows ({t2} replies) - persisting")
            await self._persist_scan(all_rows)
            self.last_sweep_time = time.time()
        except Exception as e:
            if 'has been closed' in str(e) or 'Target closed' in str(e):
                raise
            logger.warning(f"Full sweep skipped: {e}")
    
    async def _get_mutation_observer_comments(self) -> List[str]:
        """Get comment IDs detected by MutationObserver."""
        try:
            comment_ids = await self.page.evaluate("""
                () => {
                    const ids = window.__newCommentIds || [];
                    window.__newCommentIds = [];  // Clear after reading
                    return ids;
                }
            """)
            return comment_ids if comment_ids else []
        except:
            return []
    
    async def _get_feed_activity(self) -> int:
        """Read and reset the broad DOM-activity counter from the observer.
        
        Any node addition or text change in the page bumps this counter.
        A non-zero delta means Facebook changed the feed since we last looked,
        so a fresh scan is worthwhile WITHOUT reloading the page.
        """
        try:
            return await self.page.evaluate(
                "() => { const n = window.__feedActivity || 0; "
                "window.__feedActivity = 0; return n; }"
            )
        except:
            return 0
    
    async def _get_top_n_comments(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get top N comments using direct DOM query (NO BeautifulSoup).
        
        This is 10-20x faster than BeautifulSoup parsing.
        
        Args:
            n: Number of recent comments to retrieve
            
        Returns:
            List of raw comment dictionaries
        """
        try:
            # MEASURED (2026-08-22): Facebook passively delivers new comments
            # into the open page ~2.4s after posting, so reloading on a fixed
            # timer is unnecessary and only adds ~7-10s of render downtime.
            # New policy:
            #   - Reload ONLY as a periodic safety-net (default 120s) in case
            #     the observer missed an event or the feed went stale.
            #   - Between safety-nets: cheap scroll-to-top + DOM scan; the
            #     broad observer flags activity so scans stay meaningful.
            current_time = time.time()
            
            if current_time - self.last_reload_time > self.reload_interval_s:
                logger.info(
                    f"Safety-net reload triggered "
                    f"({self.reload_interval_s}s since last reload)"
                )
                await self.page.reload(wait_until="domcontentloaded")
                self.last_reload_time = current_time
                await asyncio.sleep(0.3)  # Reduced wait time
                
                # CRITICAL: Facebook resets comment sorting to its default
                # ("ความคิดเห็นทั้งหมด") on every reload - re-apply the
                # configured mode BEFORE scanning, otherwise the feed shows
                # "All comments" and newest comments fall out of top-N.
                await self._reapply_sort_mode_after_reload()
                
                # Reload wipes the JS context - reinstall MutationObserver
                if self.use_mutation_observer:
                    await self._install_mutation_observer()
                
                # Aggressive scroll after reload to force Facebook to load new comments
                await self.page.evaluate(
                    """() => {
                        window.scrollTo(0, 0);
                        setTimeout(() => window.scrollTo(0, 500), 100);
                        setTimeout(() => window.scrollTo(0, 0), 200);
                    }"""
                )
                await asyncio.sleep(0.2)  # Reduced wait time
            else:
                # Normal scroll to top
                await self.page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(0.1)
            
            comments = await self._parse_articles(top_n=n, include_replies=False)
            
            return comments if comments else []
            
        except Exception as e:
            logger.error(f"Error getting top N comments: {e}")
            # Do not swallow closed-browser errors: monitor_loop must see them
            # so it can exit and trigger cleanup instead of spinning forever.
            if 'has been closed' in str(e) or 'Target closed' in str(e):
                raise
            return []

    async def _parse_articles(self, top_n: int = 30, include_replies: bool = False) -> List[Dict[str, Any]]:
        """Parse comment articles from the live DOM.

        Args:
            top_n: max T1 comments to return in DOM order (0 = no limit).
            include_replies: also harvest T2 replies (identified SOLELY by
                reply_comment_id in the permalink href; the parent id comes
                from the same href's comment_id param).

        Returns:
            Flat list of raw dicts with id/author/message/href/timestamp
            plus tier (1/2) and parent_id (None for T1).
        """
        raw = await self.page.evaluate(
            # RAW string: the JS below contains regex/split escapes such as
            # /\s+/ and '\n'. In a normal Python string those are interpreted
            # by Python first - '\n' becomes a REAL newline and lands inside
            # the JS single-quoted literal, which makes Chromium reject the
            # whole script with "SyntaxError: Invalid or unexpected token".
            # Raw string passes every backslash through to the browser intact.
            r"""(opts) => {
                const topN = opts.topN || 0;
                const includeReplies = !!opts.includeReplies;
                // SCOPE: read only the post dialog. On a group permalink the
                // group FEED keeps rendering behind the dialog, and every feed
                // post is also a div[role="article"] carrying its own
                // comment_id permalink link. An unscoped query therefore
                // harvested unrelated posts ("7-Eleven Thailand", "POPMART
                // Thailand Market", ...) as if they were comments.
                const dialogs = Array.from(document.querySelectorAll('div[role="dialog"]'))
                    .filter(d => d.getBoundingClientRect().width > 0);
                const dialog = dialogs.find(d => d.querySelector('div[role="article"]'));
                const scope = dialog || document;
                const allArticles = scope.querySelectorAll('div[role="article"]');

                // Filter for COMMENT articles: T1 have aria-label with
                // "ความคิดเห็นจาก"/"Comment by". T2 reply articles often
                // have NO usable label, so also accept any article that
                // contains a reply_comment_id link.
                const commentArticles = Array.from(allArticles).filter(article => {
                    const label = article.getAttribute('aria-label');
                    if (label && (label.includes('ความคิดเห็นจาก') || label.includes('Comment by'))) return true;
                    return !!article.querySelector('a[href*="reply_comment_id="]');
                });

                // MEASURED (2026-08-22): Facebook renders every T1 comment TWICE -
                // once NESTED inside the post's own article and once STANDALONE.
                // A passively-pushed new comment exists ONLY as the nested copy
                // until the next full render, so nesting must NOT be used to
                // decide T1 vs T2 (the old nesting filter silently dropped every
                // freshly-delivered comment until a reload re-rendered it).
                // T2 replies are identified SOLELY by reply_comment_id in the
                // permalink href; duplicate renders are removed by comment ID.
                const seenIds = new Set();

                const parseOne = (article) => {
                    // Extract author from aria-label.
                    // FIX (2026-08-23): FB sometimes embeds newline chars
                    // inside the aria-label between the author/timestamp
                    // parts. The old single-line regexes then failed ->
                    // author empty -> the freshly-pushed comment was
                    // SILENTLY DROPPED from the scan until the next
                    // reload. Collapse all whitespace before matching.
                    const ariaLabel = (article.getAttribute('aria-label') || '').replace(/\s+/g, ' ');
                    let author = '';

                    // Extract author and timestamp from aria-label.
                    // Two formats exist:
                    //  T1 Thai: "ความคิดเห็นจาก [Author] เมื่อ [Timestamp]"
                    //  T1 English: "Comment by [Author] from [Timestamp]"
                    //  T2 reply: "ความคิดเห็นจาก [Author] ตอบกลับความคิดเห็นของ
                    //            [Parent] เมื่อ [Timestamp]"
                    let match = ariaLabel.match(/ความคิดเห็นจาก\s+(.+?)\s+ตอบกลับ/);
                    let timestamp = null;
                    let isReplyLabel = false;
                    if (match) {
                        author = match[1];
                        isReplyLabel = true;
                        const tm = ariaLabel.match(/เมื่อ\s+(.+?)\s*$/);
                        timestamp = tm ? tm[1] : null;
                    } else {
                        match = ariaLabel.match(/ความคิดเห็นจาก\s+(.+?)\s+เมื่อ\s+(.+)/);
                        if (match) {
                            author = match[1];
                            timestamp = match[2]; // e.g., "5 นาที", "2 ชั่วโมง", "1 วัน"
                        } else {
                            // Try English format
                            match = ariaLabel.match(/Comment by\s+(.+?)\s+from\s+(.+)/);
                            if (match) {
                                author = match[1];
                                timestamp = match[2]; // e.g., "5 minutes ago", "2 hours ago"
                            }
                        }
                    }

                    if (!author) {
                        // Fallback for unlabeled reply articles: first
                        // profile link text that is not an action word.
                        const skips = ['reply', 'ตอบกลับ', 'like', 'ถูกใจ', 'share', 'แชร์'];
                        for (const a of article.querySelectorAll('a[role="link"], a[href*="/user/"], strong')) {
                            const t = (a.innerText || '').trim();
                            if (t && t.length > 2 && !skips.some(s => t.toLowerCase() === s.toLowerCase())) {
                                author = t.split('\n')[0].slice(0, 80);
                                break;
                            }
                        }
                    }

                    if (!author) {
                        return null;
                    }

                    // Extract comment ID from links.
                    // A T1 article NESTS its T2 reply articles, so it contains
                    // reply links too - only consider links whose closest
                    // article IS this article, and prefer a reply link among
                    // them (a reply article's own link).
                    const ownLinks = Array.from(article.querySelectorAll('a[href*="comment_id="]'))
                        .filter(l => l.closest('div[role="article"]') === article);
                    if (!ownLinks.length) {
                        return null;
                    }
                    let href = ownLinks[0].href;
                    for (const l of ownLinks) {
                        if (l.href.includes('reply_comment_id=')) { href = l.href; break; }
                    }

                    // Check for reply first.
                    // FIX (2026-08-23): profile (pfbid) posts use NON-NUMERIC
                    // comment ids, so the old digit-only regex silently
                    // dropped EVERY comment on such pages (the scan stayed
                    // empty forever). Capture any chars up to & or #.
                    // NOTE: reply check MUST stay first because the string
                    // reply_comment_id= contains comment_id= as substring.
                    let commentId = null;
                    let parentId = null;
                    let tier = 1;
                    const replyMatch = href.match(/reply_comment_id=([^&#]+)/);
                    if (replyMatch) {
                        if (!includeReplies) {
                            return null;
                        }
                        commentId = replyMatch[1];
                        const pm = href.match(/[?&]comment_id=([^&#]+)/);
                        parentId = pm ? pm[1] : null;
                        tier = 2;
                    } else if (isReplyLabel) {
                        // Reply-format label but plain comment_id link
                        // (encoded href variant): this article IS a reply.
                        if (!includeReplies) {
                            return null;
                        }
                        const commentMatch = href.match(/comment_id=([^&#]+)/);
                        if (commentMatch) {
                            commentId = commentMatch[1];
                        }
                        tier = 2;
                    } else {
                        const commentMatch = href.match(/comment_id=([^&#]+)/);
                        if (commentMatch) {
                            commentId = commentMatch[1];
                        }
                    }

                    if (tier === 2 && !parentId) {
                        // Ancestor fallback: nearest enclosing T1 article's id.
                        let p = article.parentElement;
                        let guard = 0;
                        while (p && guard++ < 8) {
                            if (p.getAttribute && p.getAttribute('role') === 'article') {
                                const pl = Array.from(p.querySelectorAll('a[href*="comment_id="]'))
                                    .find(l => l.closest('div[role="article"]') === p
                                        && !l.href.includes('reply_comment_id='));
                                if (pl) {
                                    const pm2 = pl.href.match(/comment_id=([^&#]+)/);
                                    if (pm2 && pm2[1] !== commentId) { parentId = pm2[1]; break; }
                                }
                            }
                            p = p.parentElement;
                        }
                    }

                    if (!commentId) {
                        return null;
                    }

                    // OPTIMISTIC / PLACEHOLDER IDs - skip them.
                        // A just-posted comment is first rendered optimistically with
                        // comment_id=client%3A<uuid> (or pfbid on some layouts). Once
                        // Facebook confirms it, the SAME comment comes back with its
                        // real id, so persisting the placeholder stores the comment
                        // twice and the dashboard shows a duplicate.
                        const decodedId = decodeURIComponent(commentId);
                        if (!/^[0-9a-z]+$/i.test(decodedId)) {
                            return null;
                        }
                        if (decodedId.startsWith('client:') || decodedId.startsWith('client%3A')) {
                            return null;
                        }

                    // Dedupe: same comment rendered twice (nested + standalone)
                    const dkey = tier + ':' + commentId;
                    if (seenIds.has(dkey)) {
                        return null;
                    }
                    seenIds.add(dkey);

                    // Extract message (first dir=auto div with content).
                    // Strip a leading author-name echo ("Name f" -> "f").
                    let message = '';
                    const messageDivs = article.querySelectorAll('div[dir="auto"]');
                    for (const div of messageDivs) {
                        const text = div.innerText.trim();
                        if (text && text !== author && text.length > 2) {
                            message = text;
                            break;
                        }
                    }
                    if (message.startsWith(author + ' ')) {
                        message = message.slice(author.length).trim();
                    }

                    return {
                        id: commentId,
                        parent_id: parentId,
                        tier: tier,
                        author: author,
                        message: message,
                        href: href,
                        timestamp: timestamp
                    };
                };

                const results = [];
                const t1count = () => results.filter(r => r.tier === 1).length;
                for (let i = 0; i < commentArticles.length; i++) {
                    if (topN > 0 && t1count() >= topN && !includeReplies) {
                        break;
                    }
                    const row = parseOne(commentArticles[i]);
                    if (!row) continue;
                    if (row.tier === 1 && topN > 0 && t1count() >= topN) continue;
                    results.push(row);
                }

                return results;
            }
            """, {"topN": top_n, "includeReplies": include_replies})

        return raw if isinstance(raw, list) else []
    
    async def reply_instantly(self, comment_id: str, message: str) -> bool:
        """Reply to owner comment instantly using direct DOM manipulation + real keyboard events.
        
        This is 5-10x faster than Playwright's type() method.
        CRITICAL: Must use page.keyboard.press() for Enter, not JavaScript dispatchEvent()
        because Facebook requires trusted keyboard events.
        
        Args:
            comment_id: Comment ID to reply to
            message: Reply message text
            
        Returns:
            True if reply posted successfully
        """
        reply_start = datetime.now()
        
        try:
            logger.debug(f"Replying to comment {comment_id}")
            
            # Step 1: Click reply button using Playwright
            try:
                link = self.page.locator(f'a[href*="comment_id={comment_id}"]').first()
                article = link.locator('xpath=ancestor::div[@role="article"]').first()
                reply_button = article.locator('role=button').filter(has_text='ตอบกลับ').or_(
                    article.locator('role=button').filter(has_text='Reply')
                ).first()
                
                await reply_button.click()
                logger.debug("Reply button clicked")
                
            except Exception as e:
                logger.error(f"Failed to click reply button: {e}")
                return False
            
            # Wait for reply box to appear
            await self.page.wait_for_timeout(400)
            
            # Step 2: Use Playwright's .fill() method instead of innerText
            # .fill() properly triggers input events that enable the submit button
            try:
                # Wait a bit for reply box to be fully rendered
                await self.page.wait_for_timeout(300)
                
                # Find reply textbox specifically (aria-label contains "ตอบกลับ" or "Reply")
                # This is more reliable than using all textboxes
                reply_textbox = self.page.locator(
                    '[contenteditable="true"][role="textbox"][aria-label*="ตอบกลับ"]'
                ).or_(
                    self.page.locator('[contenteditable="true"][role="textbox"][aria-label*="Reply"]')
                ).last()
                
                # Check if reply textbox exists
                textbox_count = await reply_textbox.count()
                if textbox_count == 0:
                    logger.error("No reply textbox found (aria-label filter)")
                    return False
                
                logger.debug("Reply textbox found")
                
                # CRITICAL: Use .fill() instead of innerText
                # This properly triggers input events that enable Facebook's submit button
                await reply_textbox.fill(message)
                logger.debug("Message filled in reply box")
                
                # Wait for input to settle and submit button to enable
                await self.page.wait_for_timeout(200)
                
                # Press Enter on the textbox itself (not page.keyboard)
                await reply_textbox.press('Enter')
                
                logger.debug("Enter pressed on textbox")
                
            except Exception as e:
                logger.error(f"Failed to fill/press Enter: {e}")
                return False
            
            # Step 3: Wait for Facebook to process submission
            await self.page.wait_for_timeout(1500)
            
            # Step 4: CRITICAL VERIFICATION - Check if reply actually exists in DOM
            verification = await self.page.evaluate("""
                ([commentId, replyMessage]) => {
                    try {
                        // Find the original comment
                        const link = document.querySelector(`a[href*="comment_id=${commentId}"]`);
                        if (!link) return { success: false, error: 'comment_not_found', nestedCount: 0 };
                        
                        const article = link.closest('[role="article"]');
                        if (!article) return { success: false, error: 'article_not_found', nestedCount: 0 };
                        
                        // Count nested articles (replies are nested articles)
                        const nestedArticles = article.querySelectorAll('[role="article"]');
                        const nestedCount = nestedArticles.length;
                        
                        // Check if our reply message exists in the DOM
                        const articleText = article.innerText;
                        const hasReplyText = articleText.includes(replyMessage.substring(0, 20));
                        
                        // Check for our specific reply message in nested articles
                        let foundReply = false;
                        for (const nested of nestedArticles) {
                            if (nested.innerText.includes(replyMessage.substring(0, 20))) {
                                foundReply = true;
                                break;
                            }
                        }
                        
                        return {
                            success: nestedCount > 0 && foundReply,
                            nestedCount: nestedCount,
                            hasReplyText: hasReplyText,
                            foundReply: foundReply,
                            error: null
                        };
                    } catch (e) {
                        return { success: false, error: e.toString(), nestedCount: 0 };
                    }
                }
            """, [comment_id, message])
            
            # Check verification result
            if not verification.get('success'):
                logger.error(f"REPLY VERIFICATION FAILED!")
                logger.error(f"   Nested articles: {verification.get('nestedCount', 0)}")
                logger.error(f"   Found reply text: {verification.get('foundReply', False)}")
                logger.error(f"   Error: {verification.get('error', 'unknown')}")
                logger.error(f"   -> Reply did NOT post to Facebook!")
                return False
            
            # Success - reply verified in DOM!
            reply_time = (datetime.now() - reply_start).total_seconds()
            self.stats['replies_posted'] += 1
            self._update_avg_latency('reply', reply_time)
            
            logger.info(f"OK REPLY VERIFIED IN DOM!")
            logger.info(f"   Nested articles: {verification.get('nestedCount', 0)}")
            logger.info(f"   Found reply: {verification.get('foundReply', False)}")
            logger.info(f"Total latency: {reply_time*1000:.1f}ms")
            
            return True
                
        except Exception as e:
            logger.error(f"Error in reply_instantly: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def monitor_loop(self) -> None:
        """Main monitoring loop - lightweight and fast.
        
        This replaces the heavy detector.refresh_comments() loop.
        """
        refresh_interval_ms = self.config.get('monitor', {}).get('refresh_interval', 200)
        refresh_interval = refresh_interval_ms / 1000.0
        
        logger.info("MONITORING STARTED")
        auto_reply_enabled = self.config.get('auto_reply', {}).get('enabled', False)
        logger.info(f"   Scan interval: {refresh_interval_ms}ms | Owner: {self.owner_name} | Auto-reply: {'ON' if auto_reply_enabled else 'OFF'}")
        
        scan_count = 0
        while True:
            try:
                # Detect new owner comments — but NOT while a reply is in
                # flight. Scanning during "กำลังโพสต์..." steals the main
                # thread from FB's submit pipeline and slows the post down.
                if self.in_flight_replies > 0:
                    await asyncio.sleep(1.0)
                    continue
                new_owner_comments = await self.detect_new_owner_comments()

                # Periodic whole-feed sweep for display completeness
                # (skipped while a reply is in flight - same reason as scans).
                # Inline because both paths drive the same Playwright page;
                # _full_sweep therefore carries a hard time budget so this
                # await cannot blind detection for long.
                if time.time() - self.last_sweep_time > self.sweep_interval_s:
                    await self._full_sweep(max_seconds=self.sweep_max_seconds)
                
                # Show periodic status every 300 scans (~60 seconds at 200ms intervals)
                scan_count += 1
                if scan_count % 300 == 0:
                    logger.debug(f"Monitoring active... (scans: {scan_count})")
                
                # SPEED: scans that saw DOM change re-fire after 50ms instead
                # of waiting out the full interval - follow-up comments get
                # picked up on the next tick rather than up to a full
                # `refresh_interval` later.
                await asyncio.sleep(0.05 if self.scan_saw_change else refresh_interval)
                
            except KeyboardInterrupt:
                logger.info("Monitor loop stopped by user")
                raise  # Re-raise to allow proper cleanup
            except Exception as e:
                # If the browser/page is gone, the loop can never recover —
                # exit so cleanup() runs instead of spinning error forever.
                if 'has been closed' in str(e) or 'Target closed' in str(e):
                    logger.error("Browser/page closed - stopping monitor loop")
                    raise
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(1.0)
    
    def _update_avg_latency(self, metric: str, value: float) -> None:
        """Update rolling average latency."""
        key = f'avg_{metric}_latency'
        count_key = f'{metric}_count'
        
        if count_key not in self.stats:
            self.stats[count_key] = 0
        
        count = self.stats[count_key]
        current_avg = self.stats[key]
        
        # Rolling average
        new_avg = (current_avg * count + value) / (count + 1)
        self.stats[key] = new_avg
        self.stats[count_key] = count + 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            **self.stats,
            'owner_name': self.owner_name,
            'monitoring_start': self.monitoring_start_time.strftime('%H:%M:%S') if self.monitoring_start_time else None,
            'avg_detection_ms': self.stats['avg_detection_latency'] * 1000,
            'avg_reply_ms': self.stats['avg_reply_latency'] * 1000
        }
    
    def add_bot_reply_text(self, text: str) -> None:
        """Register bot reply text to prevent self-reply loop.
        
        When the bot posts a reply, Facebook may show it as a new comment
        from the owner. By registering the reply text here, the detector
        will skip comments that match known bot reply messages.
        
        Args:
            text: The reply message text that the bot posted
        """
        self.bot_reply_texts.add(text)
        logger.debug(f"Registered bot reply text: '{text[:40]}...' (total: {len(self.bot_reply_texts)})")
    
    def _parse_facebook_timestamp(self, timestamp_str: str) -> Optional[int]:
        """Parse Facebook timestamp string to minutes ago.
        
        Supports both Thai and English formats:
        - Thai: "5 นาที", "2 ชั่วโมง", "1 วัน", "15 ชั่วโมงที่แล้ว", "สักครู่"
        - English: "5 minutes ago", "2 hours ago", "1 day ago", "just now"
        
        Args:
            timestamp_str: Timestamp string from aria-label
            
        Returns:
            Number of minutes ago, or None if parsing failed
        """
        if not timestamp_str:
            return None
        
        timestamp_str = timestamp_str.strip().lower()
        
        # Handle "just now" / seconds-level timestamps as age 0.
        # SPEED: FB shows seconds ("30 วินาทีที่แล้ว", "เมื่อสักครู่") for the
        # newest comments - these MUST map to 0, otherwise the detector
        # skips brand-new comments until the timestamp rolls to minutes.
        if timestamp_str in ['just now', 'สักครู่', 'เมื่อสักครู่', 'เมื่อกี้',
                             'a moment ago', 'ไม่กี่วินาทีที่แล้ว',
                             'a few seconds ago']:
            return 0
        
        import re

        # Seconds: "30 วินาทีที่แล้ว", "30 seconds ago", "30s", "45วิ"
        match = re.match(r'(?:ประมาณ\s*)?(\d+)\s*(วินาที|วิ)(?:ที่แล้ว)?', timestamp_str)
        if match:
            return 0
        match = re.match(r'(\d+)\s*(seconds?|secs?|s)\s*ago', timestamp_str)
        if match:
            return 0
        
        # Weeks / months / years are always OLD - map to large ages so they
        # are skipped as history instead of falling through to "unparseable".
        # Thai: "5 สัปดาห์ที่แล้ว", "สัปดาห์ที่แล้ว", "2 เดือนที่แล้ว", "1 ปีที่แล้ว"
        match = re.match(r'(?:ประมาณ\s*)?(\d+)\s*สัปดาห์(?:ที่แล้ว)?', timestamp_str)
        if match:
            return int(match.group(1)) * 60 * 24 * 7
        if timestamp_str in ['สัปดาห์ที่แล้ว', 'last week', 'a week ago']:
            return 60 * 24 * 7
        match = re.match(r'(?:ประมาณ\s*)?(\d+)\s*เดือน(?:ที่แล้ว)?', timestamp_str)
        if match:
            return int(match.group(1)) * 60 * 24 * 30
        if timestamp_str in ['เดือนที่แล้ว', 'last month', 'a month ago']:
            return 60 * 24 * 30
        match = re.match(r'(?:ประมาณ\s*)?(\d+)\s*ปี(?:ที่แล้ว)?', timestamp_str)
        if match:
            return int(match.group(1)) * 60 * 24 * 365
        if timestamp_str in ['ปีที่แล้ว', 'last year', 'a year ago']:
            return 60 * 24 * 365
        # English: "3 weeks ago", "2 months ago", "1 year ago"
        match = re.match(r'(\d+)\s*weeks?\s*ago', timestamp_str)
        if match:
            return int(match.group(1)) * 60 * 24 * 7
        match = re.match(r'(\d+)\s*months?\s*ago', timestamp_str)
        if match:
            return int(match.group(1)) * 60 * 24 * 30
        match = re.match(r'(\d+)\s*years?\s*ago', timestamp_str)
        if match:
            return int(match.group(1)) * 60 * 24 * 365
        
        # Try Thai format: "5 นาที", "2 ชั่วโมง", "1 วัน", "15 ชั่วโมงที่แล้ว"
        # Also handles "ประมาณ 5 นาทีที่แล้ว" (approximate format)
        # Also handles "หนึ่งวันที่แล้ว" (Thai word for 1)
        # Match patterns with optional "ประมาณ" prefix and optional "ที่แล้ว" suffix
        
        # Map Thai number words to digits
        thai_num_map = {
            'หนึ่ง': '1', 'สอง': '2', 'สาม': '3', 'สี่': '4', 'ห้า': '5',
            'หก': '6', 'เจ็ด': '7', 'แปด': '8', 'เก้า': '9', 'สิบ': '10'
        }
        
        # Try with Thai number words first
        match = re.match(r'(?:ประมาณ\s*)?(หนึ่ง|สอง|สาม|สี่|ห้า|หก|เจ็ด|แปด|เก้า|สิบ)\s*(นาที|ชั่วโมง|วัน)(?:ที่แล้ว)?', timestamp_str)
        if match:
            value = int(thai_num_map[match.group(1)])
            unit = match.group(2)
            
            if unit == 'นาที':
                return value
            elif unit == 'ชั่วโมง':
                return value * 60
            elif unit == 'วัน':
                return value * 60 * 24
        
        # Try with numeric digits
        match = re.match(r'(?:ประมาณ\s*)?(\d+)\s*(นาที|ชั่วโมง|วัน)(?:ที่แล้ว)?', timestamp_str)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            
            if unit == 'นาที':
                return value
            elif unit == 'ชั่วโมง':
                return value * 60
            elif unit == 'วัน':
                return value * 60 * 24
        
        # Try English format: "5 minutes ago", "2 hours ago", "1 day ago"
        match = re.match(r'(\d+)\s*(minute|hour|day)s?\s*ago', timestamp_str)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            
            if unit == 'minute':
                return value
            elif unit == 'hour':
                return value * 60
            elif unit == 'day':
                return value * 60 * 24
        
        # Rate-limited: this runs per comment per scan (~5Hz); an unparsable
        # format (e.g. "5 สัปดาห์ที่แล้ว") would otherwise spam the log
        # (~300MB/day observed). Warn at most once a minute with a count.
        global _ts_warn_state
        try:
            _ts_warn_state
        except NameError:
            _ts_warn_state = {"at": 0.0, "n": 0}
        _ts_warn_state["n"] += 1
        now = time.time()
        if now - _ts_warn_state["at"] >= 60:
            logger.warning(
                f"Failed to parse timestamp: {timestamp_str} "
                f"({_ts_warn_state['n']}x in the last minute)"
            )
            _ts_warn_state = {"at": now, "n": 0}
        return None
