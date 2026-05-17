"""
End-to-End Pipeline Test — Go-Live Readiness
─────────────────────────────────────────────
Runs the full pipeline: PARSE → SCRAPE → FILTER → SCORE → APPLY
with configurable threshold and dry_run mode.

Usage:
    python test_e2e_live.py                   # dry run (default)
    python test_e2e_live.py --live            # REAL applications
    python test_e2e_live.py --threshold 50    # custom threshold
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure the backend directory is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from pipeline import JobApplicationPipeline, UserPreferences
from cookie_manager import list_saved_cookies
from shared.logger import logger


# ─── Configuration ────────────────────────────────────────────────────────────

RESUME_PATH = "Dhruv_Resume.pdf"

DEFAULT_ROLES = [
    "software engineer",
    "python developer",
    "backend developer",
]

DEFAULT_LOCATIONS = ["Bangalore", "Mumbai"]

DEFAULT_THRESHOLD = 45
DEFAULT_MAX_APPS = 10


# ─── Main ─────────────────────────────────────────────────────────────────────

async def run_e2e_test(
    *,
    threshold: int = DEFAULT_THRESHOLD,
    dry_run: bool = True,
    roles: list[str] | None = None,
    locations: list[str] | None = None,
    max_apps: int = DEFAULT_MAX_APPS,
) -> dict:
    """Run the full pipeline and return results."""

    roles = roles or DEFAULT_ROLES
    locations = locations or DEFAULT_LOCATIONS

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       🚀  CelerixAi E2E Pipeline Test                   ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(f"  Mode:       {'🔒 DRY RUN (no real applications)' if dry_run else '🔴 LIVE (real applications!)'}")
    print(f"  Threshold:  {threshold}%")
    print(f"  Roles:      {', '.join(roles)}")
    print(f"  Locations:  {', '.join(locations)}")
    print(f"  Max apps:   {max_apps}")
    print(f"  Resume:     {RESUME_PATH}")
    print(f"  Browser:    WebKit (Safari engine)")
    print()

    # ── Check cookie status ────────────────────────────────────
    print("  📂 Cookie Status:")
    saved = list_saved_cookies()
    if saved:
        for plat, info in saved.items():
            status = "⚠ expired" if info["all_expired"] else "✅ valid"
            print(f"      {plat:<15}  {info['cookie_count']:>3} cookies  {status}")
    else:
        print("      ⚠  No cookies saved! Run: python cookie_manager.py linkedin naukri")
    print()

    # ── Check resume ───────────────────────────────────────────
    resume = Path(RESUME_PATH)
    if not resume.exists():
        print(f"  ❌ Resume not found: {RESUME_PATH}")
        return {"error": "Resume not found"}
    print(f"  ✅ Resume found: {resume.stat().st_size / 1024:.0f} KB")
    print()

    # ── Run pipeline ───────────────────────────────────────────
    print("━" * 60)
    print("  Starting pipeline...")
    print("━" * 60)
    print()

    start = time.monotonic()

    preferences = UserPreferences(
        target_roles=roles,
        locations=locations,
        auto_apply_threshold=threshold,
    )

    pipeline = JobApplicationPipeline(
        apply_threshold=threshold,
        max_applications=max_apps,
        user_id="e2e-test",
        dry_run=dry_run,
    )

    results = await pipeline.run(RESUME_PATH, preferences)

    elapsed = time.monotonic() - start

    # ── Print report ───────────────────────────────────────────
    print()
    print("━" * 60)
    print("  📊  PIPELINE RESULTS")
    print("━" * 60)
    print()
    print(f"  ⏱  Duration:         {elapsed:.1f}s")
    print(f"  📄 Resume parsed:    {'✅' if results.get('resume_parsed') else '❌'}")
    print(f"  🔍 Jobs scraped:     {results.get('jobs_scraped', 0)}")
    print(f"  🔬 After pre-filter: {results.get('jobs_after_filter', 0)}")
    print(f"  🏆 Jobs scored:      {results.get('jobs_scored', 0)}")
    print(f"  🎯 Auto-apply:       {results.get('auto_apply_count', 0)}")
    print(f"  👁  Manual review:    {results.get('manual_review_count', 0)}")
    print(f"  ✅ Applied:          {results.get('applied_count', 0)}")
    print(f"  ❌ Failed:           {results.get('failed_count', 0)}")
    print()

    # Print scored jobs detail
    scored = results.get("scored", [])
    if scored:
        print("  📋 Scored Jobs:")
        print(f"  {'Score':>5}  {'Apply':>5}  {'Title':<35}  {'Company':<20}  {'Source'}")
        print(f"  {'─'*5}  {'─'*5}  {'─'*35}  {'─'*20}  {'─'*10}")
        for job, score in scored:
            apply_icon = "✅" if score.should_apply else "—"
            print(f"  {score.score:>4}%  {apply_icon:>5}  {job.title[:35]:<35}  {job.company[:20]:<20}  {job.source}")
        print()

    # Print apply results
    apply_results = results.get("apply_results", [])
    if apply_results:
        print("  🚀 Apply Results:")
        for r in apply_results:
            icon = "✅" if r["applied"] else "❌"
            print(f"    {icon}  {r['job_title'][:40]:<40}  {r['company']:<20}  score={r['score']}%")
        print()

    # Print errors
    errors = results.get("errors", [])
    if errors:
        print("  ⚠  Errors:")
        for err in errors:
            print(f"    • {err}")
        print()

    # ── Save results to file ──────────────────────────────────
    report_path = Path(__file__).parent / "logs" / f"e2e_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(exist_ok=True)

    serializable = {
        "timestamp": datetime.now().isoformat(),
        "mode": "dry_run" if dry_run else "live",
        "threshold": threshold,
        "duration_seconds": round(elapsed, 1),
        "resume_parsed": results.get("resume_parsed", False),
        "jobs_scraped": results.get("jobs_scraped", 0),
        "jobs_after_filter": results.get("jobs_after_filter", 0),
        "jobs_scored": results.get("jobs_scored", 0),
        "auto_apply_count": results.get("auto_apply_count", 0),
        "applied_count": results.get("applied_count", 0),
        "failed_count": results.get("failed_count", 0),
        "errors": errors,
        "apply_results": apply_results,
    }
    report_path.write_text(json.dumps(serializable, indent=2, default=str))
    print(f"  💾 Report saved: {report_path}")
    print()

    return results


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CelerixAi E2E Pipeline Test")
    parser.add_argument("--live", action="store_true", help="Run in LIVE mode (real applications)")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD, help=f"Auto-apply threshold (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("--max-apps", type=int, default=DEFAULT_MAX_APPS, help=f"Max applications (default: {DEFAULT_MAX_APPS})")
    parser.add_argument("--locations", nargs="+", default=DEFAULT_LOCATIONS, help="Target locations")
    parser.add_argument("--roles", nargs="+", default=DEFAULT_ROLES, help="Target roles")

    args = parser.parse_args()

    if args.live:
        print("\n  ⚠️  LIVE MODE — Real applications will be submitted!")
        confirm = input("  Type 'YES' to confirm: ")
        if confirm.strip() != "YES":
            print("  Aborted.")
            return

    asyncio.run(run_e2e_test(
        threshold=args.threshold,
        dry_run=not args.live,
        roles=args.roles,
        locations=args.locations,
        max_apps=args.max_apps,
    ))


if __name__ == "__main__":
    main()
