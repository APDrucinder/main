import json
import time
from uuid import uuid4

import cookie_manager


class FakeContext:
    def __init__(self):
        self.added_cookies = []

    def add_cookies(self, cookies):
        self.added_cookies.extend(cookies)


def _payload(value: str, *, user_id: str | None = None) -> dict:
    return {
        "platform": "linkedin",
        "user_id": user_id,
        "captured_at": "2026-05-24T00:00:00+00:00",
        "cookie_count": 1,
        "user_agent": f"agent-{value}",
        "cookies": [
            {
                "name": "li_at",
                "value": value,
                "domain": ".linkedin.com",
                "path": "/",
                "expires": time.time() + 3600,
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            }
        ],
    }


def _isolate_cookie_dir(monkeypatch, tmp_path):
    cookies_dir = tmp_path / "cookies"
    users_dir = cookies_dir / "users"
    cookies_dir.mkdir()
    users_dir.mkdir()
    monkeypatch.setattr(cookie_manager, "COOKIES_DIR", cookies_dir)
    monkeypatch.setattr(cookie_manager, "USER_COOKIES_DIR", users_dir)
    monkeypatch.setattr(cookie_manager, "ALLOW_GLOBAL_PLATFORM_COOKIES", False)


def test_user_cookie_loading_is_isolated(monkeypatch, tmp_path):
    _isolate_cookie_dir(monkeypatch, tmp_path)
    user_a = str(uuid4())
    user_b = str(uuid4())

    cookie_manager._cookie_path(
        "linkedin", user_id=user_a, create_parent=True
    ).write_text(json.dumps(_payload("user-a", user_id=user_a)))
    cookie_manager._cookie_path(
        "linkedin", user_id=user_b, create_parent=True
    ).write_text(json.dumps(_payload("user-b", user_id=user_b)))

    context = FakeContext()
    status = cookie_manager.load_cookies("linkedin", context, user_id=user_b)

    assert status.loaded is True
    assert status.cookie_count == 1
    assert context.added_cookies[0]["value"] == "user-b"
    assert cookie_manager.get_cookie_user_agent("linkedin", user_id=user_b) == "agent-user-b"


def test_user_cookie_loading_never_falls_back_to_global(monkeypatch, tmp_path):
    _isolate_cookie_dir(monkeypatch, tmp_path)
    user_id = str(uuid4())
    cookie_manager._cookie_path("linkedin").write_text(json.dumps(_payload("global")))

    context = FakeContext()
    status = cookie_manager.load_cookies("linkedin", context, user_id=user_id)

    assert status.loaded is False
    assert context.added_cookies == []
    assert "No user" in status.message


def test_global_cookie_loading_is_blocked_by_default(monkeypatch, tmp_path):
    _isolate_cookie_dir(monkeypatch, tmp_path)
    cookie_manager._cookie_path("linkedin").write_text(json.dumps(_payload("global")))

    context = FakeContext()
    status = cookie_manager.load_cookies("linkedin", context)

    assert status.loaded is False
    assert context.added_cookies == []
    assert "Refusing to load legacy global cookies" in status.message


def test_list_saved_cookies_is_user_scoped(monkeypatch, tmp_path):
    _isolate_cookie_dir(monkeypatch, tmp_path)
    user_a = str(uuid4())
    user_b = str(uuid4())

    cookie_manager._cookie_path(
        "linkedin", user_id=user_a, create_parent=True
    ).write_text(json.dumps(_payload("user-a", user_id=user_a)))
    cookie_manager._cookie_path(
        "linkedin", user_id=user_b, create_parent=True
    ).write_text(json.dumps(_payload("user-b", user_id=user_b)))

    saved = cookie_manager.list_saved_cookies(user_id=user_a)

    assert list(saved) == ["linkedin"]
    assert saved["linkedin"]["user_id"] == user_a
    assert saved["linkedin"]["cookie_count"] == 1
