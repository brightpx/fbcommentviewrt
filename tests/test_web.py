"""Tests for the Flask web dashboard (uses the real dev database read-only)."""
import sqlite3
from unittest.mock import AsyncMock, patch

import yaml

from app.web import create_app


def make_client():
    app = create_app("config.yaml")
    app.config["TESTING"] = True
    return app.test_client()


def make_isolated_client(tmp_path):
    """App instance backed by a scratch DB (safe for write-endpoint tests)."""
    db = tmp_path / "t.db"
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE comments (id TEXT PRIMARY KEY, parent_id TEXT, tier INTEGER,"
        " author TEXT, message TEXT, created_time TIMESTAMP, last_seen TIMESTAMP,"
        " display_order INTEGER DEFAULT 0, is_deleted BOOLEAN DEFAULT 0, post_url TEXT)"
    )
    con.execute(
        "CREATE TABLE posts (url TEXT PRIMARY KEY, group_name TEXT, post_id TEXT,"
        " author TEXT, content TEXT, first_seen TIMESTAMP, last_monitored TIMESTAMP)"
    )
    con.execute(
        "INSERT INTO comments VALUES ('c1', NULL, 1, 'Owner', 'hello',"
        " '2026-01-01 10:00:00', '2026-01-01 10:00:00', 0, 0, 'https://x/y')"
    )
    con.commit()
    con.close()
    base = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    base["database"]["path"] = str(db)
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump(base), encoding="utf-8")
    app = create_app(str(cfg))
    app.config["TESTING"] = True
    return app.test_client()


def test_index_renders():
    client = make_client()
    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "FB Comment Viewer" in html
    assert "__INITIAL__" in html
    assert "app.js" in html


def test_api_comments_structure():
    client = make_client()
    res = client.get("/api/comments")
    assert res.status_code == 200
    data = res.get_json()
    assert "comments" in data and "stats" in data
    assert "total" in data["stats"]
    assert data["stats"]["total"] >= 0
    for c in data["comments"]:
        assert {"id", "author", "message", "children"} <= set(c)


def test_api_comments_sort_oldest():
    client = make_client()
    data = client.get("/api/comments?sort=oldest").get_json()
    # Contract: chronological by monotonic FB comment ID (created_time values
    # are first-scan estimates and collide).
    ids = [c["id"] for c in data["comments"] if c["id"].isdigit()]
    assert ids == sorted(ids, key=int)


def test_api_comments_sort_newest():
    client = make_client()
    data = client.get("/api/comments").get_json()
    ids = [c["id"] for c in data["comments"] if c["id"].isdigit()]
    assert ids == sorted(ids, key=int, reverse=True)


def test_api_status():
    client = make_client()
    data = client.get("/api/status").get_json()
    assert data["mode"] == "read-only"
    assert "total_comments" in data


def test_add_post_invalid_url(tmp_path):
    client = make_isolated_client(tmp_path)
    res = client.post("/api/posts", json={"url": "https://google.com/"})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_add_post_valid_url(tmp_path):
    client = make_isolated_client(tmp_path)
    url = "https://www.facebook.com/groups/123/posts/456"
    res = client.post("/api/posts", json={"url": url})
    assert res.status_code == 200
    data = res.get_json()
    assert data["url"] == url
    assert url in data["posts"]


def test_reply_missing_comment(tmp_path):
    client = make_isolated_client(tmp_path)
    res = client.post("/api/reply", json={"comment_id": "nope", "message": "hi"})
    assert res.status_code == 404


def test_reply_queues_job_and_completes(tmp_path):
    client = make_isolated_client(tmp_path)
    fake = AsyncMock()
    fake.initialize.return_value = None
    fake.navigate_to_post.return_value = True
    fake.reply_to_comment.return_value = True
    fake.close.return_value = None
    with patch("app.scraper.facebook.FacebookScraper", return_value=fake):
        res = client.post("/api/reply", json={"comment_id": "c1", "message": "hi"})
        assert res.status_code == 202
        job_id = res.get_json()["job_id"]
        import time
        for _ in range(50):
            st = client.get(f"/api/reply/{job_id}").get_json()
            if st["status"] in ("done", "failed"):
                break
            time.sleep(0.2)
        assert st["status"] == "done", st
        fake.reply_to_comment.assert_called_once_with("c1", "hi")


def test_reply_job_unknown():
    client = make_client()
    assert client.get("/api/reply/doesnotexist").status_code == 404


def test_delete_post_removes_post_and_comments(tmp_path):
    client = make_isolated_client(tmp_path)
    url = "https://www.facebook.com/groups/123/posts/456"
    assert client.post("/api/posts", json={"url": url}).status_code == 200
    res = client.delete("/api/posts", json={"url": url})
    assert res.status_code == 200
    data = res.get_json()
    assert url not in data["posts"]
    # deleting unknown url is still fine (idempotent)
    res2 = client.delete("/api/posts", json={"url": url})
    assert res2.status_code == 200


def test_delete_post_missing_url(tmp_path):
    client = make_isolated_client(tmp_path)
    assert client.delete("/api/posts", json={}).status_code == 400


def test_api_monitor_shape():
    client = make_client()
    data = client.get("/api/monitor").get_json()
    assert {"monitor", "web", "session", "db", "log"} <= set(data)
    assert isinstance(data["monitor"]["running"], bool)
    assert isinstance(data["monitor"]["headless"], bool)
    assert isinstance(data["log"]["tail"], list)
