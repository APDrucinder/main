import json
import sys
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from cookie_manager import _cookie_path, _safe_user_id


def import_cookies(user_id: str, platform: str, filepath: str):
    try:
        with open(filepath, "r") as f:
            cookies = json.load(f)
    except Exception as e:
        print(f"❌ Failed to read {filepath}: {e}")
        return
    
    # We must use the exact User-Agent that will be used by Playwright
    # to avoid LinkedIn session invalidation.
    user_agent_str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
    
    payload = {
        "platform": platform,
        "user_id": _safe_user_id(user_id),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "cookie_count": len(cookies),
        "user_agent": user_agent_str,
        "cookies": cookies,
    }
    
    out_file = _cookie_path(platform, user_id=user_id, create_parent=True)
    out_file.write_text(json.dumps(payload, indent=2))
    print(f"✅ Imported {len(cookies)} cookies for user {user_id} on {platform} -> {out_file}")

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          🍪  CelerixAi Cookie Import Tool                ║")
    print("║  Import EditThisCookie JSON for deployment environments  ║")
    print("╚══════════════════════════════════════════════════════════╝\n")
    if len(sys.argv) < 4:
        print("Usage: python import_cookies_json.py <user_uuid> <platform> <path_to_exported_json>")
        print("Example: python import_cookies_json.py 858011cd-5a44-4e86-9bc7-0088c22b8efe linkedin /tmp/linkedin_cookies.json")
        sys.exit(1)
    import_cookies(sys.argv[1], sys.argv[2], sys.argv[3])
