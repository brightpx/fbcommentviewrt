"""Flask web dashboard - Facebook-like view of collected comments.

Read path needs no browser. Replying to a comment launches a Playwright
browser job in a background worker (uses the saved FB session).
"""
import asyncio
import json
import os
import queue
import re
import socket
import sqlite3
import threading
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml
from flask import Flask, jsonify, render_template, request

REPO_ROOT = Path(__file__).resolve().parents[2]

FB_POST_RE = re.compile(
    r"^https?://(www\.)?facebook\.com/groups/\d+/(posts|permalink)/\d+/?(\?.*)?$"
)

# --- reply worker (single-flight: one browser job at a time) ---
_reply_queue: "queue.Queue[dict]" = queue.Queue()
_jobs: dict = {}
_jobs_lock = threading.Lock()
_worker_started = False


def _ensure_reply_worker(app_config: dict) -> None:
    global _worker_started
    if _worker_started:
        return
    _worker_started = True
    t = threading.Thread(target=_reply_worker_loop, args=(app_config,), daemon=True)
    t.start()


def _reply_worker_loop(app_config: dict) -> None:
    while True:
        job = _reply_queue.get()
        try:
            _execute_reply(app_config, job)
        except Exception as e:  # never kill the worker
            with _jobs_lock:
                job["status"] = "failed"
                job["detail"] = f"worker error: {e}"
                job["finished_at"] = datetime.now().isoformat(timespec="seconds")
        finally:
            _reply_queue.task_done()


def _execute_reply(app_config: dict, job: dict) -> None:
    from ..scraper.facebook import FacebookScraper

    with _jobs_lock:
        job["status"] = "running"
        job["started_at"] = datetime.now().isoformat(timespec="seconds")

    async def _flow():
        scraper = FacebookScraper(app_config)
        await scraper.initialize()
        try:
            if not await scraper.navigate_to_post(job["post_url"]):
                return False, "navigate to post failed"
            ok = await scraper.reply_to_comment(job["comment_id"], job["message"])
            return ok, ("posted + verified" if ok else "reply not verified in DOM")
        finally:
            try:
                await scraper.close()
            except Exception:
                pass

    try:
        ok, detail = asyncio.run(_flow())
    except Exception as e:
        ok, detail = False, f"exception: {e}"

    if ok:
        # Mark parent as replied (display_order doubles as replied flag)
        try:
            con = sqlite3.connect(str(_db_path(app_config)), timeout=30)
            try:
                con.execute(
                    "UPDATE comments SET display_order = 1 WHERE id = ?",
                    (job["comment_id"],),
                )
                con.commit()
            finally:
                con.close()
        except Exception as mark_err:
            detail = f"{detail} (posted, but DB mark failed: {mark_err})"

    with _jobs_lock:
        job["status"] = "done" if ok else "failed"
        job["detail"] = detail
        job["finished_at"] = datetime.now().isoformat(timespec="seconds")


def load_config(config_path: str = "config.yaml") -> dict:
    path = Path(config_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _db_path(config: dict) -> Path:
    p = Path(config.get("database", {}).get("path", "database/comments.db"))
    return p if p.is_absolute() else REPO_ROOT / p


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con


def list_posts(con: sqlite3.Connection) -> list:
    try:
        rows = con.execute(
            "SELECT url FROM posts ORDER BY last_monitored DESC"
        ).fetchall()
        urls = [r["url"] for r in rows]
    except sqlite3.Error:
        urls = []
    # Always include comment post_urls even if posts table is empty.
    # NOTE: plain DISTINCT avoids aggregate scans; the comments table has a
    # corrupt page on the full-scan path, so never add GROUP BY / MAX here.
    try:
        for r in con.execute("SELECT DISTINCT post_url FROM comments").fetchall():
            if r["post_url"] not in urls:
                urls.append(r["post_url"])
    except sqlite3.Error:
        pass
    return urls


def fetch_comments(con: sqlite3.Connection, post_url: str) -> list:
    rows = con.execute(
        """SELECT id, parent_id, tier, author, message, created_time,
                  last_seen, display_order
           FROM comments WHERE post_url = ? AND is_deleted = 0""",
        (post_url,),
    ).fetchall()
    return [dict(r) for r in rows]


def detect_owner(comments: list) -> str | None:
    t1 = [c["author"] for c in comments if (c["tier"] or 1) == 1 and c["author"]]
    if not t1:
        authors = [c["author"] for c in comments if c["author"]]
        if not authors:
            return None
        return Counter(authors).most_common(1)[0][0]
    return Counter(t1).most_common(1)[0][0]


def _order_key(c: dict):
    """Chronological key: FB comment IDs are monotonic snowflakes, so a
    bigger numeric ID is always newer. created_time values are only
    first-scan estimates (many collide), so ID order matches FB exactly
    while timestamps stay approximate."""
    cid = c.get("id", "")
    if isinstance(cid, str) and cid.isdigit():
        return (0, int(cid))
    return (1, c.get("created_time") or "")


def build_tree(comments: list, sort: str = "newest") -> tuple[list, dict]:
    """Nest replies under parents. Returns (top_level, stats)."""
    nodes = {}
    for c in comments:
        nodes[c["id"]] = {
            "id": c["id"],
            "parent_id": c["parent_id"],
            "tier": c["tier"] or 1,
            "author": c["author"] or "Unknown",
            "message": c["message"] or "",
            "created_time": c["created_time"],
            "last_seen": c["last_seen"],
            "replied": bool(c["display_order"]),
            "children": [],
        }
    roots = []
    for n in nodes.values():
        p = n["parent_id"]
        if p and p in nodes and p != n["id"]:
            nodes[p]["children"].append(n)
        else:
            roots.append(n)

    reverse = sort != "oldest"
    for n in nodes.values():
        n["children"].sort(key=_order_key, reverse=False)
    roots.sort(key=_order_key, reverse=reverse)

    owner = detect_owner(comments)
    for n in nodes.values():
        n["is_owner"] = bool(owner and n["author"] == owner)
    return roots, {"owner": owner}


def summarize(comments: list, tree: list, owner: str | None) -> dict:
    t1 = sum(1 for c in comments if (c["tier"] or 1) == 1)
    replies = len(comments) - t1
    owner_t1 = sum(
        1 for c in comments
        if (c["tier"] or 1) == 1 and owner and c["author"] == owner
    )
    replied = sum(1 for c in comments if c["display_order"])
    last_seen = max((c["last_seen"] or "" for c in comments), default=None)
    return {
        "total": len(comments),
        "top_level": t1,
        "replies": replies,
        "owner_comments": owner_t1,
        "replied": replied,
        "owner": owner,
        "last_seen": last_seen,
    }


def create_app(config_path: str = "config.yaml") -> Flask:
    config = load_config(config_path)
    db_path = _db_path(config)
    default_post = config.get("target", {}).get("post_url", "")
    auto_reply = config.get("auto_reply", {})

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["DASH_CONFIG"] = {
        "db_path": str(db_path),
        "default_post": default_post,
        "auto_reply": {
            "enabled": bool(auto_reply.get("enabled", False)),
            "reply_message": auto_reply.get("reply_message", ""),
        },
    }

    def payload(post_url: str, sort: str) -> dict:
        con = _connect(_db_path_from_app(app))
        try:
            comments = fetch_comments(con, post_url)
            posts = list_posts(con)
        except sqlite3.Error as e:
            con.close()
            return {
                "post_url": post_url,
                "posts": [],
                "comments": [],
                "stats": {"total": 0, "top_level": 0, "replies": 0,
                          "owner_comments": 0, "replied": 0,
                          "owner": None, "last_seen": None},
                "auto_reply": app.config["DASH_CONFIG"]["auto_reply"],
                "sort": sort,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "db_error": f"Database read failed: {e}",
            }
        finally:
            try:
                con.close()
            except Exception:
                pass
        try:
            tree, meta = build_tree(comments, sort=sort)
            stats = summarize(comments, tree, meta["owner"])
        except Exception as e:
            return {
                "post_url": post_url,
                "posts": posts,
                "comments": [],
                "stats": {"total": len(comments), "top_level": 0, "replies": 0,
                          "owner_comments": 0, "replied": 0,
                          "owner": None, "last_seen": None},
                "auto_reply": app.config["DASH_CONFIG"]["auto_reply"],
                "sort": sort,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "db_error": f"Failed to build comment tree: {e}",
            }
        return {
            "post_url": post_url,
            "posts": posts,
            "comments": tree,
            "stats": stats,
            "auto_reply": app.config["DASH_CONFIG"]["auto_reply"],
            "sort": sort,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

    @app.route("/")
    def index():
        post_url = request.args.get("post_url", default_post)
        sort = request.args.get("sort", "newest")
        if sort not in ("newest", "oldest"):
            sort = "newest"
        data = payload(post_url, sort)
        # Embed first paint so the page works without an extra round-trip
        return render_template(
            "index.html",
            initial=json.dumps(data, ensure_ascii=False),
            post_url=post_url,
            sort=sort,
        )

    @app.get("/api/comments")
    def api_comments():
        post_url = request.args.get("post_url", default_post)
        sort = request.args.get("sort", "newest")
        if sort not in ("newest", "oldest"):
            sort = "newest"
        return jsonify(payload(post_url, sort))

    @app.get("/api/status")
    def api_status():
        # NOTE: aggregate SQL (COUNT(*)/MAX) hits a corrupt page in the
        # current database file, so stats are computed in Python from
        # index-served row fetches instead.
        con = _connect(_db_path_from_app(app))
        try:
            posts = list_posts(con)
            total = 0
            last = None
            errors = []
            targets = posts or [default_post]
            for url in targets:
                if not url:
                    continue
                try:
                    rows = fetch_comments(con, url)
                except sqlite3.Error as e:
                    errors.append(f"{url}: {e}")
                    continue
                total += len(rows)
                for r in rows:
                    if r["last_seen"] and (last is None or r["last_seen"] > last):
                        last = r["last_seen"]
        finally:
            con.close()
        out = {
            "mode": "read-only",
            "total_comments": total,
            "last_seen": last,
            "posts": posts,
            "default_post": default_post,
            "auto_reply": app.config["DASH_CONFIG"]["auto_reply"],
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }
        if errors:
            out["db_warning"] = errors
        return jsonify(out)

    @app.post("/api/posts")
    def api_add_post():
        """Register a new Facebook post link for tracking."""
        body = request.get_json(silent=True) or {}
        url = (body.get("url") or "").strip()
        if not url or not FB_POST_RE.match(url):
            return jsonify({"error": "ลิงก์ไม่ถูกต้อง (ต้องเป็น facebook.com/groups/<id>/(posts|permalink)/<id>)"}), 400
        # Normalize: strip trailing slash + query
        url = re.sub(r"/+$", "", url.split("?")[0])
        con = _connect(_db_path_from_app(app))
        try:
            now = datetime.now().isoformat(timespec="seconds")
            con.execute(
                """INSERT INTO posts (url, first_seen, last_monitored)
                   VALUES (?, ?, ?)
                   ON CONFLICT(url) DO UPDATE SET last_monitored = excluded.last_monitored""",
                (url, now, now),
            )
            con.commit()
            posts = list_posts(con)
        except sqlite3.Error as e:
            return jsonify({"error": f"บันทึกไม่ได้: {e}"}), 500
        finally:
            con.close()
        if url not in posts:
            posts.append(url)
        return jsonify({"posts": posts, "url": url})

    @app.delete("/api/posts")
    def api_delete_post():
        """Untrack a post and delete its collected comments."""
        body = request.get_json(silent=True) or {}
        url = (body.get("url") or "").strip()
        if not url:
            return jsonify({"error": "ต้องระบุ url"}), 400
        con = _connect(_db_path_from_app(app))
        try:
            cur = con.execute("DELETE FROM comments WHERE post_url = ?", (url,))
            n_comments = cur.rowcount
            con.execute("DELETE FROM posts WHERE url = ?", (url,))
            con.commit()
            posts = list_posts(con)
        except sqlite3.Error as e:
            return jsonify({"error": f"ลบไม่ได้: {e}"}), 500
        finally:
            con.close()
        return jsonify({"posts": posts, "deleted_comments": n_comments})

    @app.post("/api/reply")
    def api_reply():
        """Queue an auto-reply to one comment (runs a browser job)."""
        _ensure_reply_worker(config)
        body = request.get_json(silent=True) or {}
        comment_id = (body.get("comment_id") or "").strip()
        message = (body.get("message") or "").strip()
        if not comment_id:
            return jsonify({"error": "ต้องระบุ comment_id"}), 400
        if not message:
            message = auto_reply.get("reply_message", "")
        if not message:
            return jsonify({"error": "ต้องระบุ message (หรือตั้ง auto_reply.reply_message ใน config)"}), 400
        con = _connect(_db_path_from_app(app))
        try:
            row = con.execute(
                "SELECT id, author, post_url FROM comments WHERE id = ?",
                (comment_id,),
            ).fetchone()
        except sqlite3.Error as e:
            return jsonify({"error": f"อ่าน DB ไม่ได้: {e}"}), 500
        finally:
            con.close()
        if not row:
            return jsonify({"error": "ไม่พบ comment นี้ในฐานข้อมูล"}), 404
        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "comment_id": comment_id,
            "author": row["author"],
            "post_url": row["post_url"],
            "message": message,
            "status": "queued",
            "detail": f"รอคิว (มี { _reply_queue.qsize()} งานข้างหน้า)",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        with _jobs_lock:
            _jobs[job_id] = job
        _reply_queue.put(job)
        return jsonify({"job_id": job_id, "status": "queued"}), 202

    @app.get("/api/reply/<job_id>")
    def api_reply_status(job_id: str):
        with _jobs_lock:
            job = _jobs.get(job_id)
            job = dict(job) if job else None
        if not job:
            return jsonify({"error": "ไม่พบ job"}), 404
        return jsonify(job)

    @app.get("/api/monitor")
    def api_monitor():
        """Program status: monitor process, web, session, DB, recent log."""
        log_file = config.get("logging", {}).get("file", "output.log")
        log_path = Path(log_file)
        if not log_path.is_absolute():
            log_path = REPO_ROOT / log_path
        session_path = REPO_ROOT / Path(config.get("session", {}).get("file", "session/fb_session.json"))
        db_path = _db_path_from_app(app)
        total = None
        try:
            con = _connect(db_path)
            try:
                total = 0
                for url in list_posts(con) or [default_post]:
                    if url:
                        try:
                            total += len(fetch_comments(con, url))
                        except sqlite3.Error:
                            pass
            finally:
                con.close()
        except sqlite3.Error:
            pass
        return jsonify({
            "monitor": {
                "running": _monitor_running(),
                "headless": bool(config.get("browser", {}).get("headless", False)),
            },
            "web": {"running": True},
            "session": _file_info(session_path),
            "db": {"path": str(db_path), "rows": total, "info": _file_info(db_path)},
            "log": {"path": str(log_path), "info": _file_info(log_path),
                    "tail": _tail_log(log_path)},
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        })

    return app


def _db_path_from_app(app: Flask) -> Path:
    return Path(app.config["DASH_CONFIG"]["db_path"])


def _monitor_running(port: int = 51234) -> bool:
    """True when another process holds the monitor single-instance lock."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        return False
    except OSError:
        return True
    finally:
        s.close()


def _tail_log(path: Path, max_lines: int = 12, max_bytes: int = 65536) -> list:
    """Last meaningful log lines without reading a huge file.

    Drops DEBUG spam and the per-scan timestamp warnings so the card
    shows real events (detections, replies, errors).
    """
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            f.seek(max(0, size - max_bytes))
            text = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    lines = []
    for line in text.splitlines():
        if " - DEBUG - " in line:
            continue
        if "Failed to parse timestamp" in line:
            continue
        line = line.strip()
        if not line:
            continue
        lines.append(line[-220:])
    return lines[-max_lines:]


def _file_info(path: Path) -> dict | None:
    try:
        st = path.stat()
        return {
            "size_kb": round(st.st_size / 1024, 1),
            "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        }
    except OSError:
        return None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="FB comment web dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    create_app().run(host=args.host, port=args.port, debug=args.debug)
