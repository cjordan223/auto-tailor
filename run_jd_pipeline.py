#!/usr/bin/env python3
"""
JD Pipeline Automation Script

Runs both jd-parser.py and skills-updater.py in sequence to automate the complete
JD analysis and resume skills update workflow.

Usage:
    python3 run_jd_pipeline.py [--artifacts-only] [--dry-run] [--jd jd.txt]
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print()

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd, check=True, capture_output=False, text=True)
        elapsed = time.time() - start_time
        print(f"\n✅ {description} completed successfully ({elapsed:.1f}s)")
        return True
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        print(f"\n❌ {description} failed after {elapsed:.1f}s")
        print(f"Exit code: {e.returncode}")
        return False


def main():
    ap = argparse.ArgumentParser(
        description="Run complete JD analysis and resume skills update pipeline")
    ap.add_argument("--jd", default="jd.txt",
                    help="Path to job description file (default: jd.txt)")
    ap.add_argument("--artifacts-only", action="store_true",
                    help="Only write to artifacts directory, don't update resume files")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show changes without writing any files")
    ap.add_argument("--base-url", default="http://127.0.0.1:1234/v1",
                    help="LM Studio base URL")
    ap.add_argument("--api-key", default="lm-studio",
                    help="API key for LM Studio")
    ap.add_argument("--model", default="qwen2.5-32b-instruct",
                    help="Model name for both scripts")
    args = ap.parse_args()

    # Start timing
    pipeline_start_time = time.time()

    # Validate inputs
    jd_path = Path(args.jd)
    if not jd_path.exists():
        sys.exit(f"❌ ERROR: Job description file not found: {jd_path}")

    print("🚀 JD Pipeline Automation")
    print("=" * 60)
    print(f"Job Description: {jd_path}")
    print(
        f"Mode: {'Artifacts Only' if args.artifacts_only else 'Dry Run' if args.dry_run else 'Full Update'}")
    print(f"Model: {args.model}")
    print(f"Base URL: {args.base_url}")
    print()

    # Step 1: Run JD Parser
    jd_cmd = [
        "python3", "jd-parser.py",
        "--jd", str(jd_path),
        "--base-url", args.base_url,
        "--api-key", args.api_key,
        "--model", args.model
    ]

    if not run_command(jd_cmd, "JD Skills Extraction"):
        sys.exit("❌ Pipeline failed at JD parsing step")

    # Step 2: Run Skills Updater
    skills_cmd = [
        "python3", "skills-updater.py",
        "--base-url", args.base_url,
        "--api-key", args.api_key,
        "--model", args.model
    ]

    if args.artifacts_only:
        skills_cmd.append("--artifacts-only")
    elif args.dry_run:
        skills_cmd.append("--dry-run")

    if not run_command(skills_cmd, "Skills Section Update"):
        sys.exit("❌ Pipeline failed at skills update step")

    # Step 3: Run Summary Updater
    summary_cmd = [
        "python3", "summary-updater.py",
        "--base-url", args.base_url,
        "--api-key", args.api_key,
        "--model", args.model
    ]

    if args.artifacts_only:
        summary_cmd.append("--artifacts-only")
    elif args.dry_run:
        summary_cmd.append("--dry-run")

    if not run_command(summary_cmd, "Summary Section Update"):
        sys.exit("❌ Pipeline failed at summary update step")

    # Summary
    print(f"\n{'='*60}")
    print("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
    print(f"{'='*60}")

    if args.artifacts_only:
        print("📁 Generated artifacts:")
        print("   • artifacts/jd_skills.json")
        print("   • artifacts/skills_editor_output.json")
        print("   • artifacts/skills_updated_block.tex")
        print("\n🔍 Review artifacts before running without --artifacts-only")
    elif args.dry_run:
        print("🔍 Dry run completed - no files were modified")
        print("   Review output above before running without --dry-run")
    else:
        print("✅ Resume files have been updated!")
        print("   • skills.tex")
        print("   • Resume/Conner_Jordan_Software_Engineer.tex")
        print("   • artifacts/ (backup copies)")
        print("\n🎯 Skills have been automatically inserted into the main resume!")

    total_time = time.time() - pipeline_start_time
    print(f"\n⏱️  Total pipeline time: {total_time:.1f}s")


if __name__ == "__main__":
    main()
