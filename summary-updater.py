
#!/usr/bin/env python3
"""
Resume Summary Updater

Takes the output from jd-parser.py and subtly tailors the professional summary
to align with job requirements and company values while maintaining the 
original tone and professionalism.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
import requests


def get_api_key(api_key):
    if api_key == "lm-studio":
        return "lm-studio"
    return os.getenv(api_key) if os.getenv(api_key) else api_key


def read_file_content(path):
    try:
        return path.read_text()
    except FileNotFoundError:
        sys.exit(f"❌ ERROR: File not found: {path}")


def clean_unicode_content(content):
    """Remove problematic Unicode control characters from content"""
    import unicodedata

    # Remove control characters (U+0000 to U+001F, except tab, newline, carriage return)
    cleaned = ''
    for char in content:
        if unicodedata.category(char) == 'Cc' and char not in '\t\n\r':
            continue
        cleaned += char

    return cleaned


def write_file_content(path, content):
    # Clean the content before writing
    cleaned_content = clean_unicode_content(content)
    path.write_text(cleaned_content)


def get_llm_response(base_url, api_key, model, prompt):
    """Send chat completion request to LM Studio"""
    try:
        url = f"{base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "top_p": 0.9,
            "seed": 42,
            "max_tokens": 2000,
            "stop": []
        }

        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=1800  # 30 minutes
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        sys.exit(f"❌ ERROR: Failed to get response from LLM: {e}")


def update_tex_file(tex_content, new_block_content):
    # Remove the \n at the start of the block
    new_block_content = new_block_content.strip()

    pattern = re.compile(
        r"(% SUMMARY_BLOCK_START\n)(.*?)(\n% SUMMARY_BLOCK_END)", re.DOTALL
    )
    if not pattern.search(tex_content):
        sys.exit("❌ ERROR: Could not find SUMMARY_BLOCK_START/END in tex file")

    return pattern.sub(f"\1{new_block_content}\3", tex_content)


def main():
    ap = argparse.ArgumentParser(
        description="Update summary in a tex file based on JD"
    )
    ap.add_argument(
        "--jd-skills",
        default="artifacts/jd_skills.json",
        help="Path to job description skills file",
    )
    ap.add_argument(
        "--resume-file",
        default="Resume/Conner_Jordan_Software_Engineer.tex",
        help="Path to the resume tex file",
    )
    ap.add_argument(
        "--base-url", default="http://127.0.0.1:1234/v1", help="LM Studio base URL"
    )
    ap.add_argument("--api-key", default="lm-studio",
                    help="API key for LM Studio")
    ap.add_argument(
        "--model", default="qwen2.5-32b-instruct", help="Model name for the LLM"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Show changes without writing any files"
    )
    ap.add_argument(
        "--artifacts-only",
        action="store_true",
        help="Only write to artifacts directory",
    )
    args = ap.parse_args()

    # Setup
    jd_skills_path = Path(args.jd_skills)
    resume_file_path = Path(args.resume_file)
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)

    # Read files
    jd_skills_content = read_file_content(jd_skills_path)
    resume_content = read_file_content(resume_file_path)

    # Extract original summary
    original_summary_match = re.search(
        r"% SUMMARY_BLOCK_START\n(.*)\n% SUMMARY_BLOCK_END", resume_content, re.DOTALL
    )
    if not original_summary_match:
        sys.exit("❌ ERROR: Could not find summary block in resume file")
    original_summary = original_summary_match.group(1).strip()

    # Create prompt
    prompt = f"""
    Original Professional Summary:
    ---
    {original_summary}
    ---

    Job Description Details:
    ---
    {jd_skills_content}
    ---

    Instructions:
    Revise the 'Original Professional Summary' to subtly align with the 'Job Description Details'.
    - Do NOT simply list the skills from the job description.
    - Integrate the essence of the responsibilities and company values.
    - Maintain a professional and confident tone.
    - The revised summary should be a natural evolution of the original, not a complete rewrite.
    - Make the changes subtle, so it's not obvious it was tailored.
    - Output ONLY the revised summary text, without any preamble or explanation.
    """

    # Get LLM response
    print("🧠 Calling LLM to revise professional summary...")
    revised_summary = get_llm_response(
        args.base_url, get_api_key(args.api_key), args.model, prompt)
    print("✅ LLM response received.")

    # Save artifacts
    write_file_content(
        artifacts_dir / "summary_editor_output.json",
        json.dumps(
            {
                "original_summary": original_summary,
                "revised_summary": revised_summary,
                "prompt": prompt,
            },
            indent=2,
        ),
    )
    write_file_content(
        artifacts_dir / "summary_updated_block.tex", revised_summary
    )

    if args.dry_run:
        print("DRY RUN: Changes are not being saved.")
        print("--- ORIGINAL SUMMARY ---")
        print(original_summary)
        print("--- REVISED SUMMARY ---")
        print(revised_summary)
    elif args.artifacts_only:
        print("ARTIFACTS ONLY: Resume file not modified.")
        print(f"✅ Revised summary saved to {artifacts_dir}")
    else:
        # Update resume file
        updated_resume_content = update_tex_file(
            resume_content, revised_summary)
        write_file_content(resume_file_path, updated_resume_content)
        print(f"✅ Resume file updated: {resume_file_path}")


if __name__ == "__main__":
    main()
