#!/usr/bin/env python3
"""
JD Pipeline Automation Script

Runs both jd-parser.py and skills-updater.py in sequence to automate the complete
JD analysis and resume skills update workflow.

Usage:
    python3 run_jd_pipeline.py [--artifacts-only] [--dry-run] [--no-clean] [--jd jd.txt]
"""

import argparse
import shutil
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
    ap.add_argument("--no-clean", action="store_true",
                    help="Skip cleaning artifacts directory (for debugging)")
    args = ap.parse_args()

    # Start timing
    pipeline_start_time = time.time()

    # Clean artifacts directory unless --no-clean is specified
    artifacts_dir = Path("artifacts")
    if not args.no_clean and artifacts_dir.exists():
        print("🧹 Cleaning artifacts directory to prevent stale data contamination...")
        shutil.rmtree(artifacts_dir)
        print("✅ Artifacts directory cleaned")
    elif args.no_clean:
        print("⚠️  Skipping artifacts cleanup (--no-clean specified)")
    
    # Ensure artifacts directory exists
    artifacts_dir.mkdir(exist_ok=True)

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

    # PHASE 1: JD Analysis
    print(f"\n📋 PHASE 1: JD Analysis")
    print(f"Input:  {jd_path}")
    print(f"Output: artifacts/jd_skills.json")
    jd_cmd = [
        "python3", "jd-parser.py",
        "--jd", str(jd_path),
        "--base-url", args.base_url,
        "--api-key", args.api_key,
        "--model", args.model
    ]

    if not run_command(jd_cmd, "Extract skills from job description"):
        sys.exit("❌ PHASE 1 FAILED: JD Analysis")

    # PHASE 2: Skills Update
    print(f"\n🔧 PHASE 2: Skills Update")
    print(f"Input:  artifacts/jd_skills.json")
    print(f"Output: artifacts/skills_updated_block.tex + Resume/skills.tex")
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

    if not run_command(skills_cmd, "Update technical skills section"):
        sys.exit("❌ PHASE 2 FAILED: Skills Update")

    # PHASE 3: Summary Tailoring  
    print(f"\n✍️  PHASE 3: Summary Tailoring")
    print(f"Input:  artifacts/jd_skills.json + current resume summary")
    print(f"Output: artifacts/summary_updated_block.tex + Resume/*.tex")
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

    if not run_command(summary_cmd, "Tailor professional summary"):
        sys.exit("❌ PHASE 3 FAILED: Summary Tailoring")

    # Pipeline Complete
    print(f"\n{'='*60}")
    print("🎉 ALL 3 PHASES COMPLETED SUCCESSFULLY!")
    print(f"{'='*60}")
    print("✅ Phase 1: JD Analysis - Skills extracted")
    print("✅ Phase 2: Skills Update - Technical skills updated") 
    print("✅ Phase 3: Summary Tailoring - Professional summary tailored")

    if args.artifacts_only:
        print(f"\n📁 Generated Artifacts:")
        print("   • artifacts/jd_skills.json (Phase 1 output)")
        print("   • artifacts/skills_updated_block.tex (Phase 2 output)")
        print("   • artifacts/summary_updated_block.tex (Phase 3 output)")
        print("\n🔍 Review artifacts before running without --artifacts-only")
    elif args.dry_run:
        print(f"\n🔍 Dry run completed - no files were modified")
        print("   Review output above before running without --dry-run")
    else:
        print(f"\n✅ Resume files updated:")
        print("   • Resume/Conner_Jordan_Software_Engineer.tex (both skills & summary)")
        print("   • Resume/skills.tex (skills section)")
        print("   • artifacts/ (phase outputs preserved)")
        print("\n🎯 Resume fully tailored for this job description!")

    total_time = time.time() - pipeline_start_time
    print(f"\n⏱️  Total pipeline time: {total_time:.1f}s")


if __name__ == "__main__":
    main()
