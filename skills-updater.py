#!/usr/bin/env python3
"""
Skills Updater - Phase 2 of JD Parser Pipeline

Takes extracted skills from jd-parser.py and updates the resume skills section
to align with job requirements while maintaining resume integrity.

SAFETY MODES:
- --dry-run: Show changes without writing any files
- --artifacts-only: Write only to artifacts/ directory, don't update resume files
- Default: Update both artifacts and actual resume files

Use --artifacts-only for testing the flow before updating your actual resume.
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Dict, Any, List
import requests

# -------------------
# Configuration
# -------------------
DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_API_KEY = "lm-studio"
DEFAULT_MODEL = "qwen2.5-32b-instruct"
TIMEOUT_S = 1800  # 30 minutes

EDITOR_OPTIONS = {
    "temperature": 0.0,
    "top_p": 0.9,
    "seed": 42,
    "max_tokens": 1000,
    "stop": ["\nYou:", "\nUser:", "<|im_end|>"],
}

SKILLS_EDITOR_SYSTEM = r"""
You are an expert LaTeX editor. Your task is to edit the TECHNICAL SKILLS section of a resume.

Your goal is to intelligently integrate skills from the provided JOB_SKILLS list into the REFERENCE_LATEX_SECTION. This is to optimize the resume for Applicant Tracking Systems (ATS).

**Instructions:**

1.  **Integrate Skills:** Add relevant skills from the `JOB_SKILLS` list to the appropriate subsections in the `REFERENCE_LATEX_SECTION`.
2.  **Maintain Structure:** Keep the original subsections, their order, and their count:
    `["Programming Languages", "Frontend", "Backend", "Cloud & DevOps", "AI & LLM Tools", "Automation & Productivity", "Security & Operating Systems", "Databases"]`
3.  **Preserve Formatting:**
    - Each subsection must remain on a single line.
    - Keep the `\textbf{}` and `\vspace{3pt}` macros.
    - Escape LaTeX special characters (like `&` as `\&`).
    - CRITICAL: Use single backslash for escaping (`\&`, not `\\&`).
4.  **Be Selective:**
    - Do not add skills that are irrelevant to a section.
    - Do not remove existing skills unless they are clearly less important than the new skills you are adding for a particular job.
    - It is not necessary to add every skill from the `JOB_SKILLS` list. Focus on the most relevant ones.
    - Include compliance frameworks (e.g., SOC2, HIPAA, GDPR) and other relevant keywords if they appear in the `JOB_SKILLS` list.
5.   **Output Format:**
     - You MUST return ONLY a valid JSON object.
     - The JSON object must have a "latex" field containing the complete, updated LaTeX block as a single string with newlines escaped as `\n`.
     - Include a "change_notes" field to explain the changes you made.
     - CRITICAL: All newlines in the LaTeX content must be escaped as `\\n` in the JSON string.
     - Do NOT include any prose, backticks, or markdown formatting outside the JSON.

**Example JSON Output:**

```json
{
  "latex": "\\textbf{Programming Languages:} ...\\n\\n\\vspace{3pt}\\n...",
  "change_notes": [
    {"section": "Security & Operating Systems",
        "added": ["SIEM", "EDR"], "removed": []}
  ]
}
```

If you cannot follow these instructions, return `{"error": "<reason>"}`.
""".strip()

# -------------------
# Helpers
# -------------------


def chat_completions(base_url: str, api_key: str, model: str,
                     messages: List[Dict[str, str]], options: Dict[str, Any]) -> str:
    """Send chat completion request to LM Studio"""
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": options.get("temperature", 0.0),
        "top_p": options.get("top_p", 0.9),
        "seed": options.get("seed", 42),
    }
    if "max_tokens" in options:
        payload["max_tokens"] = options["max_tokens"]
    if "stop" in options:
        payload["stop"] = options["stop"]

    r = requests.post(url, headers={"Authorization": f"Bearer {api_key}"},
                      json=payload, timeout=TIMEOUT_S)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]


def coerce_json(s: str) -> Any:
    """Parse JSON with fallback strategies"""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # Remove markdown code fences if present
        s = re.sub(r'^```json\s*', '', s.strip())
        s = re.sub(r'```\s*$', '', s.strip())
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            # Try to fix common JSON issues with LaTeX content
            # Replace problematic control characters in LaTeX content
            # Escape newlines in string values
            s = re.sub(r'\n(?=\s*")', '\\n', s)
            # Escape carriage returns in string values
            s = re.sub(r'\r(?=\s*")', '\\r', s)
            s = re.sub(r'\t(?=\s*")', '\\t', s)  # Escape tabs in string values
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                # salvage the last JSON object in the string
                m = re.search(r"\{[\s\S]*\}\s*$", s.strip())
                if not m:
                    raise
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    # Last resort: try to manually extract the latex field
                    latex_match = re.search(
                        r'"latex":\s*"([^"]*(?:\\.[^"]*)*)"', s, re.DOTALL)
                    if latex_match:
                        latex_content = latex_match.group(1)
                        # Clean up the LaTeX content
                        latex_content = latex_content.replace(
                            '\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')
                        return {"latex": latex_content, "change_notes": []}
                    # Try a more flexible approach - extract anything that looks like LaTeX
                    latex_pattern = r'\\textbf\{[^}]+\}.*?(?=\\textbf\{|$)'
                    latex_matches = re.findall(latex_pattern, s, re.DOTALL)
                    if latex_matches:
                        latex_content = '\n\n\\vspace{3pt}\n'.join(
                            latex_matches)
                        return {"latex": latex_content, "change_notes": []}
                    raise


def build_job_skills_list(extractor_output: Dict[str, Any]) -> str:
    """Build JOB_SKILLS string from extractor output"""
    # Use the full ranked skills list instead of just top 3 per section
    job_skills_ranked = extractor_output.get("job_skills_ranked", [])
    flat = []

    # Extract canonical skill names from the ranked list
    for skill_item in job_skills_ranked:
        canonical = skill_item.get("canonical", "")
        if canonical:
            flat.append(canonical)

    return "; ".join(flat)


def validate_updated_block(updated: str) -> bool:
    """Validate that the updated block has all required sections"""
    required_sections = [
        "Programming Languages",
        "Frontend",
        "Backend",
        "Cloud & DevOps",
        "AI & LLM Tools",
        "Automation & Productivity",
        "Security & Operating Systems",
        "Databases"
    ]

    for section in required_sections:
        # Escape LaTeX special characters for regex
        escaped_section = re.escape(section.replace("&", "\\&"))
        # Make the pattern flexible to handle both single and double backslashes
        pattern = rf"\\+textbf\{{{escaped_section}:\}}"
        # Also try a more flexible pattern for sections with ampersands
        if "&" in section:
            # For sections like "Cloud & DevOps", also try without escaping
            alt_pattern = rf"\\+textbf\{{{section.replace('&', '\\&')}:\}}"
            if re.search(alt_pattern, updated):
                continue
        if not re.search(pattern, updated):
            print(f"❌ Missing section: {section}")
            return False

    return True


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


def shuffle_skills_in_block(block_text: str) -> str:
    """Shuffle skills in each subsection for a more organic look."""
    lines = block_text.split('\n')
    new_lines = []
    for line in lines:
        # Strip whitespace and match the pattern
        line_stripped = line.strip()
        # Match the pattern with escaped backslashes
        match = re.match(r'(\\+textbf\{.*?\})\s*(.*)', line_stripped)
        if match:
            header = match.group(1)
            skills_str = match.group(2)
            # Split skills by comma, but be careful with parentheses
            skills = re.split(r',\s*(?![^()]*\))', skills_str)
            # Clean up each skill
            skills = [skill.strip() for skill in skills if skill.strip()]
            random.shuffle(skills)
            new_skills_str = ', '.join(skills)
            new_lines.append(f"{header} {new_skills_str}")
        else:
            new_lines.append(line)
    return '\n'.join(new_lines)


def update_resume_tex(resume_path: Path, updated_skills: str) -> str:
    """Update the resume .tex file with new skills section"""
    content = resume_path.read_text(encoding="utf-8")

    # Find the TECHNICAL SKILLS section
    skills_section_start = content.find("\\section{TECHNICAL SKILLS}")
    if skills_section_start == -1:
        raise ValueError("Could not find TECHNICAL SKILLS section in resume")

    # Find the start of the skills content (after \item \small{)
    skills_content_start = content.find(
        "\\item \\small{", skills_section_start)
    if skills_content_start == -1:
        raise ValueError("Could not find skills content start in resume")

    # Find the opening brace after \item \small{
    brace_start = content.find("{", skills_content_start)
    if brace_start == -1:
        raise ValueError("Could not find opening brace for skills content")

    # Find the closing brace for the skills section
    brace_count = 0
    brace_end = -1
    for i, char in enumerate(content[brace_start:], brace_start):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                brace_end = i
                break

    if brace_end == -1:
        raise ValueError("Could not find closing brace for skills section")

    # Simply read the content from the artifacts file and paste it directly
    artifacts_file = Path("artifacts/skills_updated_block.tex")
    if artifacts_file.exists():
        skills_content = artifacts_file.read_text(encoding="utf-8").strip()
    else:
        # Fallback to the passed content if artifacts file doesn't exist
        skills_content = updated_skills

    # Replace the skills content
    before_skills = content[:brace_start + 1]  # Include the opening brace
    after_skills = content[brace_end:]  # Include the closing brace

    # Add the skills content directly
    updated_content = before_skills + "\n" + skills_content + "\n" + after_skills

    return updated_content


def fix_latex_formatting(updated_block: str) -> str:
    """Fix common LaTeX formatting issues"""
    # Convert escaped newlines back to actual newlines
    updated_block = updated_block.replace('\\n', '\n')

    # Fix all variations of malformed LaTeX commands
    # Use regex to fix any number of backslashes followed by textbf or vspace
    updated_block = re.sub(r'\\+\\textbf', '\\textbf', updated_block)
    updated_block = re.sub(r'\\+\\vspace', '\\vspace', updated_block)

    # Fix the null byte issue
    updated_block = updated_block.replace('\x0b', '\\')

    # Also fix the case where we have \\\textbf (3 backslashes)
    updated_block = updated_block.replace('\\\\\\\textbf', '\\textbf')
    updated_block = updated_block.replace('\\\\\\\vspace', '\\vspace')

    # Fix the space command
    updated_block = updated_block.replace('\\space{3pt}', '\\vspace{3pt}')

    # Replace any number of backslashes followed by spaces and then the command
    updated_block = re.sub(r'\\+\s+extbf', '\\textbf', updated_block)
    updated_block = re.sub(r'\\+\s+vspace', '\\vspace', updated_block)

    # Fix the case where backslashes were completely removed
    updated_block = updated_block.replace('        extbf', '\\textbf')
    updated_block = updated_block.replace('    extbf', '\\textbf')

    # Also fix with different spacing - this should catch the remaining cases
    updated_block = re.sub(r'\s+extbf', '\\textbf', updated_block)

    # Final cleanup - replace any remaining malformed patterns
    updated_block = re.sub(r'(\s+)extbf', r'\\textbf', updated_block)

    # Fix LaTeX special characters that need escaping
    # Fix excessive backslashes before ampersands (\\\\& -> \&)
    updated_block = re.sub(r'\\\\+&', r'\\&', updated_block)
    # Fix excessive backslashes before textbf (\\\\textbf -> \textbf)
    updated_block = re.sub(r'\\\\+\\textbf', r'\\textbf', updated_block)
    # Fix excessive backslashes before vspace (\\\\vspace -> \vspace)
    updated_block = re.sub(r'\\\\+\\vspace', r'\\vspace', updated_block)

    # Comprehensive fix for ampersand escaping in section titles
    # First, fix any double backslashes before ampersands in section titles
    updated_block = re.sub(
        r'\\textbf\{([^}]*)\\\\&([^}]*):\}', r'\\textbf{\1\\&\2:}', updated_block)
    # Then fix any unescaped ampersands in section titles
    updated_block = re.sub(
        r'\\textbf\{([^}]*)\&([^}]*):\}', r'\\textbf{\1\\&\2:}', updated_block)
    # Finally, ensure all ampersands in section titles are properly escaped
    updated_block = re.sub(
        r'\\textbf\{([^}]*)\\\\&([^}]*):\}', r'\\textbf{\1\\&\2:}', updated_block)

    return updated_block


def ensure_proper_spacing(updated_block: str) -> str:
    """Ensure proper spacing with empty lines after each \vspace{3pt}"""
    # Split into lines
    lines = updated_block.split('\n')
    new_lines = []

    for i, line in enumerate(lines):
        new_lines.append(line)
        # If this line contains \vspace{3pt}, ensure the next line is empty
        if '\\vspace{3pt}' in line.strip():
            # Check if the next line exists and is not empty
            if i + 1 < len(lines) and lines[i + 1].strip():
                # Insert an empty line after this \vspace{3pt}
                new_lines.append('')

    return '\n'.join(new_lines)


# -------------------
# Main
# -------------------


def main():
    ap = argparse.ArgumentParser(
        description="Update resume skills section based on JD parser output")
    ap.add_argument("--extractor-output", default="artifacts/jd_skills.json",
                    help="Path to jd-parser.py output JSON file")
    ap.add_argument("--skills", default="skills.tex",
                    help="Path to current skills.tex file")
    ap.add_argument("--resume", default="Resume/Conner_Jordan_Software_Engineer.tex",
                    help="Path to main resume .tex file to update")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL,
                    help="LM Studio base URL")
    ap.add_argument("--api-key", default=DEFAULT_API_KEY,
                    help="API key (LM Studio ignores content)")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help="Model name for skills editor")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show changes without writing any files")
    ap.add_argument("--artifacts-only", action="store_true",
                    help="Only write to artifacts directory, don't update actual resume files")
    args = ap.parse_args()

    # Load files
    extractor_path = Path(args.extractor_output)
    skills_path = Path(args.skills)
    resume_path = Path(args.resume)

    if not extractor_path.exists():
        sys.exit(f"ERROR: Extractor output not found: {extractor_path}")
    if not skills_path.exists():
        sys.exit(f"ERROR: Skills file not found: {skills_path}")
    if not resume_path.exists():
        sys.exit(f"ERROR: Resume file not found: {resume_path}")

    print("== Skills Updater - Phase 2 ==")
    if args.artifacts_only:
        print("🔍 RUNNING IN ARTIFACTS-ONLY MODE")
        print("   Resume files will NOT be updated")
        print("   Check artifacts/ directory for generated content")
    elif args.dry_run:
        print("🔍 RUNNING IN DRY-RUN MODE")
        print("   No files will be written")
    else:
        print("🔧 RUNNING IN FULL UPDATE MODE")
        print("   Resume files WILL be updated")

    # Load extractor output
    try:
        with open(extractor_path, 'r', encoding='utf-8') as f:
            extractor_output = json.load(f)
        print(f"✅ Loaded extractor output: {extractor_path}")
    except Exception as e:
        sys.exit(f"ERROR: Failed to load extractor output: {e}")

    # Load current skills
    try:
        current_skills = skills_path.read_text(encoding="utf-8").strip()
        print(f"✅ Loaded current skills: {skills_path}")
    except Exception as e:
        sys.exit(f"ERROR: Failed to load skills file: {e}")

    # Build JOB_SKILLS string
    job_skills = build_job_skills_list(extractor_output)
    print(f"\n🔧 JOB_SKILLS extracted:")
    print(f"   {job_skills}")

    # Prepare editor input
    editor_user_payload = (
        f"REFERENCE_LATEX_SECTION:\n{current_skills}\n\n"
        f"JOB_SKILLS:\n{job_skills}\n"
    )

    print(f"\n== Skills Editor (LaTeX update) ==")
    print(f"Using model: {args.model}")
    print(f"Timeout: {TIMEOUT_S} seconds")

    # Run skills editor
    try:
        editor_resp = chat_completions(
            args.base_url,
            args.api_key,
            args.model,
            [
                {"role": "system", "content": SKILLS_EDITOR_SYSTEM},
                {"role": "user", "content": editor_user_payload},
            ],
            EDITOR_OPTIONS,
        )
    except Exception as e:
        print(f"❌ Skills editor failed: {e}")
        sys.exit(1)

    # Parse editor response
    try:
        editor_json = coerce_json(editor_resp)
    except Exception as e:
        print(f"Editor response length: {len(editor_resp)} characters")
        print("Editor raw output (truncated):\n",
              editor_resp[:1000], file=sys.stderr)
        print(f"Editor raw output (last 500 chars):\n",
              editor_resp[-500:], file=sys.stderr)
        raise SystemExit(f"ERROR: editor did not return valid JSON: {e}")

    if "error" in editor_json:
        raise SystemExit(f"Editor error: {editor_json['error']}")

    updated_block = editor_json["latex"].strip()

    # Fix LaTeX formatting issues
    updated_block = fix_latex_formatting(updated_block)

    # Ensure proper spacing with empty lines after each \vspace{3pt}
    updated_block = ensure_proper_spacing(updated_block)

    # Shuffle skills for a more organic look
    updated_block = shuffle_skills_in_block(updated_block)

    change_notes = editor_json.get("change_notes", [])

    # Validate updated block
    if not validate_updated_block(updated_block):
        print("⚠️  WARNING: Updated skills block is missing required sections")
        print("   Continuing anyway to show what was returned...")
        # Don't exit, just warn

    # Show changes
    print("\n--- Updated TECHNICAL SKILLS (LaTeX) ---\n")
    print(updated_block)

    if change_notes:
        print("\n--- Change Notes ---")
        for note in change_notes:
            section = note.get("section", "Unknown")
            adds = note.get("adds", [])
            removes = note.get("removes", [])
            reason = note.get("reason", "")

            if adds:
                print(f"  + {section}: Added {', '.join(adds)}")
            if removes:
                print(f"  - {section}: Removed {', '.join(removes)}")
            if reason:
                print(f"    Reason: {reason}")

    # Update files
    if not args.dry_run:
        # Always save artifacts first
        artifacts_dir = Path("artifacts")
        artifacts_dir.mkdir(exist_ok=True)

        # Save artifacts (these will overwrite existing files automatically)
        (artifacts_dir / "skills_editor_output.json").write_text(
            json.dumps(editor_json, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (artifacts_dir / "skills_updated_block.tex").write_text(
            clean_unicode_content(updated_block), encoding="utf-8")

        print("\nWrote artifacts:")
        print("  artifacts/skills_editor_output.json")
        print("  artifacts/skills_updated_block.tex")

        # Only update actual resume files if not in artifacts-only mode
        if not args.artifacts_only:
            # Update skills.tex
            skills_path.write_text(clean_unicode_content(
                updated_block), encoding="utf-8")
            print(f"\n✅ Updated: {skills_path}")

            # Update main resume .tex file
            try:
                updated_resume = update_resume_tex(resume_path, updated_block)
                resume_path.write_text(clean_unicode_content(
                    updated_resume), encoding="utf-8")
                print(f"✅ Updated: {resume_path}")
            except Exception as e:
                print(f"⚠️  Could not update main resume: {e}")
                print("   Skills section updated in skills.tex only")
        else:
            print("\n🔍 ARTIFACTS-ONLY MODE - Resume files not updated")
            print("   Review artifacts/ directory for generated content")
    else:
        print("\n🔍 DRY RUN - No files were modified")

    print("\n🎉 Skills updater completed successfully!")


if __name__ == "__main__":
    main()
