import json
import sys
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
COOKIES_DIR = BASE_DIR / "cookies"
COOKIES_DIR.mkdir(exist_ok=True)

def import_cookies(platform: str, filepath: str):
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
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "cookie_count": len(cookies),
        "user_agent": user_agent_str,
        "cookies": cookies,
    }
    
    out_file = COOKIES_DIR / f"{platform}_cookies.json"
    out_file.write_text(json.dumps(payload, indent=2))
    print(f"✅ Imported {len(cookies)} cookies for {platform} -> {out_file}")

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          🍪  CelerixAi Cookie Import Tool                ║")
    print("║  Import EditThisCookie JSON for deployment environments  ║")
    print("╚══════════════════════════════════════════════════════════╝\n")
    if len(sys.argv) < 3:
        print("Usage: python import_cookies_json.py <platform> <path_to_exported_json>")
        print("Example: python import_cookies_json.py linkedin /tmp/linkedin_cookies.json")
        sys.exit(1)
    import_cookies(sys.argv[1], sys.argv[2])
