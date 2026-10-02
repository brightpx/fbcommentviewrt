"""Test newest-comment selection logic without posting anything (dry run).

Replicates detect_new_owner_comments() filter + sort, then reports which
comment WOULD be selected as the newest owner comment to reply to.
"""
import asyncio
import yaml
import logging
from datetime import datetime, timedelta

from app.scraper.facebook import FacebookScraper
from app.monitor.owner_detector import OwnerCommentDetector

logging.basicConfig(level=logging.INFO)

async def main():
    with open('config.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    s = FacebookScraper(config)
    await s.initialize()
    await s.navigate_to_post(config['target']['post_url'])
    await asyncio.sleep(6)

    # Build a detector instance but DO NOT call initialize() (which reloads page)
    det = OwnerCommentDetector(s, config)
    det.owner_name = await s.get_post_author()
    det.monitoring_start_time = datetime.now() - timedelta(minutes=30)  # look back 30 min
    det.bot_reply_texts.add(config['auto_reply']['reply_message'])

    print(f"\n=== Owner: {det.owner_name} ===")
    print(f"=== Monitoring start (lookback): {det.monitoring_start_time.strftime('%H:%M:%S')} ===\n")

    # Fetch top 20 comments
    raw = await det._get_top_n_comments(n=20)
    print(f"Fetched {len(raw)} T1 comments\n")

    candidates = []
    for c in raw:
        cid = c.get('id')
        author = c.get('author', '')
        ts = c.get('timestamp', '')
        msg = c.get('message', '')

        # timestamp filter
        age = det._parse_facebook_timestamp(ts)
        keep = True
        reason = ''
        if age is None:
            keep = False
            reason = 'unparsed timestamp'
        else:
            posted = datetime.now() - timedelta(minutes=age)
            if posted < det.monitoring_start_time:
                keep = False
                reason = 'older than lookback'
        if det.bot_reply_texts and msg in det.bot_reply_texts:
            keep = False
            reason = 'bot reply text (self)'

        print(f"  id={cid} age={age}m ts=\"{ts}\" keep={keep}{('  [' + reason + ']') if reason else ''}")
        print(f"      author=\"{author[:25]}\" msg=\"{msg[:40]}\"")

        if keep:
            candidates.append({'comment_id': cid, 'comment_age_minutes': age})

    # NEW sort: comment ID descending (monotonic snowflake)
    candidates.sort(key=lambda c: -int(c['comment_id']))

    print("\n=== SORTED (newest first) ===")
    for c in candidates:
        print(f"  {c['comment_id']}  (age {c['comment_age_minutes']}m)")

    if candidates:
        print(f"\n>>> WOULD REPLY TO: {candidates[0]['comment_id']}")
    else:
        print("\n>>> No new owner comment found (none in lookback window)")

    await s.close()

asyncio.run(main())