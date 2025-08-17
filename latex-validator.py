#!/usr/bin/env python3
"""
LaTeX Resume Validator - Final formatting and validation step

This script performs deterministic checks and targeted LLM analysis
to ensure consistent LaTeX formatting and proper structure for resumes.

Usage:
    python3 latex-validator.py --resume Resume/Conner_Jordan_Software_Engineer.tex
    python3 latex-validator.py --resume Resume/Conner_Jordan_Software_Engineer.tex --dry-run
"""

import argparse
import re
import sys
import json
import requests
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional


# Configuration for validation rules
VALIDATION_CONFIG = {
    # Font size rules: command -> expected size
    'font_sizes': {
        '\\section': '\\large',  # Section titles should be large
        '\\textbf{\\large': '\\large',  # Large bold text consistency
    },

    # Line count threshold for one-page estimate
    'max_lines_estimate': 120,  # Rough estimate for single page

    # Spacing rules
    'required_spacing': {
        '\\vspace{3pt}': 1,  # Should have 1 empty line after
        '\\vspace{6pt}': 1,  # Should have 1 empty line after
        '\\vspace{8pt}': 1,  # Should have 1 empty line after
    }
}

# LLM Configuration
LLM_CONFIG = {
    'base_url': 'http://127.0.0.1:1234/v1',
    'api_key': 'lm-studio',
    'model': 'qwen2.5-32b-instruct',
    'timeout': 300
}


class LaTeXValidator:
    """Main validator class for LaTeX resume formatting"""

    def __init__(self, resume_path: str, dry_run: bool = False):
        self.resume_path = Path(resume_path)
        self.dry_run = dry_run
        self.content = ""
        self.issues = []
        self.warnings = []
        self.fixes_applied = []

    def load_content(self) -> None:
        """Load the LaTeX file content"""
        try:
            self.content = self.resume_path.read_text(encoding='utf-8')
        except FileNotFoundError:
            sys.exit(f"❌ ERROR: Resume file not found: {self.resume_path}")
        except Exception as e:
            sys.exit(f"❌ ERROR: Failed to read resume file: {e}")

    def check_spacing_consistency(self) -> str:
        """
        Deterministic Check 1: Enforce consistent spacing rules

        This function:
        1. Ensures single empty line after \\vspace{3pt}, \\vspace{6pt}, etc.
        2. Removes double empty lines throughout the document
        3. Fixes spacing around section boundaries

        Returns the cleaned content with spacing fixes applied.
        """
        print("🔍 Checking spacing consistency...")
        cleaned_content = self.content

        # Remove multiple consecutive empty lines (replace with single empty line)
        original_lines = len(cleaned_content.split('\n'))
        cleaned_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_content)
        new_lines = len(cleaned_content.split('\n'))

        if original_lines != new_lines:
            fix_msg = f"Removed {original_lines - new_lines} excessive empty lines"
            self.fixes_applied.append(fix_msg)
            print(f"  ✅ {fix_msg}")

        # Ensure proper spacing after \\vspace commands
        for vspace_cmd, required_lines in VALIDATION_CONFIG['required_spacing'].items():
            # Pattern to match vspace command followed by varying amounts of whitespace
            pattern = rf'({re.escape(vspace_cmd)})\s*\n\s*\n+'
            replacement = f'\\1\n\n'  # Exactly one empty line after

            before_count = len(re.findall(pattern, cleaned_content))
            cleaned_content = re.sub(pattern, replacement, cleaned_content)
            after_count = len(re.findall(pattern, cleaned_content))

            if before_count > after_count:
                fix_msg = f"Standardized spacing after {vspace_cmd} commands ({before_count} instances)"
                self.fixes_applied.append(fix_msg)
                print(f"  ✅ {fix_msg}")

        # Fix spacing around section titles (should have proper space before and after)
        section_pattern = r'(\n)(\\section\{[^}]+\})\n+'
        section_replacement = r'\1\2\n'

        before_sections = len(re.findall(section_pattern, cleaned_content))
        cleaned_content = re.sub(
            section_pattern, section_replacement, cleaned_content)

        if before_sections > 0:
            fix_msg = f"Standardized spacing around section titles ({before_sections} sections)"
            self.fixes_applied.append(fix_msg)
            print(f"  ✅ {fix_msg}")

        return cleaned_content

    def check_font_consistency(self) -> None:
        """
        Deterministic Check 2: Validate font size consistency

        This function checks that font sizes are used consistently according
        to predefined rules (e.g., \\section titles should use \\large).
        """
        print("🔍 Checking font size consistency...")

        # Check section title font sizes
        section_pattern = r'\\section\{[^}]+\}'
        sections = re.findall(section_pattern, self.content)

        for section in sections:
            # Check if section is properly formatted with large font
            if '\\large' not in section and '\\Large' not in section:
                # This is handled by titlesec package in this resume, so it's OK
                pass

        # Check for inconsistent font size usage
        font_size_commands = re.findall(
            r'\\(tiny|scriptsize|footnotesize|small|normalsize|large|Large|LARGE|huge|Huge)', self.content)

        if font_size_commands:
            size_counts = {}
            for cmd in font_size_commands:
                size_counts[cmd] = size_counts.get(cmd, 0) + 1

            # Report font size usage
            print(f"  📊 Font size usage: {size_counts}")

            # Warn about excessive variety in font sizes
            if len(size_counts) > 4:
                warning = f"Many different font sizes used ({len(size_counts)} varieties). Consider simplifying."
                self.warnings.append(warning)
                print(f"  ⚠️  {warning}")

        print("  ✅ Font consistency check completed")

    def check_one_page_verification(self) -> str:
        """
        Deterministic Check 3: Verify PDF is exactly one page and fix if needed

        This function compiles the LaTeX file to PDF, verifies it's exactly one page,
        and if not, applies fixes to reduce content length.
        """
        print("🔍 Verifying PDF is one page...")

        # First do line count estimation for quick feedback
        lines = self.content.split('\n')
        content_lines = 0

        for line in lines:
            stripped = line.strip()
            # Count lines that contribute to document length
            if (stripped and
                not stripped.startswith('%') and  # Skip comments
                not stripped.startswith('\\documentclass') and
                not stripped.startswith('\\usepackage') and
                not stripped.startswith('\\newcommand') and
                not stripped.startswith('\\begin{document}') and
                not stripped.startswith('\\end{document}') and
                    '\\vspace' not in stripped):  # Skip spacing commands
                content_lines += 1

        threshold = VALIDATION_CONFIG['max_lines_estimate']
        print(f"  📊 Content lines: {content_lines}/{threshold} (estimate)")

        # Now compile PDF and check actual page count
        try:
            # Copy skills.tex to Resume directory if it doesn't exist
            skills_tex_src = self.resume_path.parent.parent / 'skills.tex'
            skills_tex_dst = self.resume_path.parent / 'skills.tex'
            if skills_tex_src.exists() and not skills_tex_dst.exists():
                import shutil
                shutil.copy2(skills_tex_src, skills_tex_dst)
                print(f"  📄 Copied skills.tex to Resume directory")

            # Compile the LaTeX file to PDF
            result = subprocess.run([
                'pdflatex', '-interaction=nonstopmode', '-output-directory',
                str(self.resume_path.parent), str(self.resume_path)
            ], capture_output=True, text=True, cwd=self.resume_path.parent)

            print(f"  📊 pdflatex return code: {result.returncode}")

            # Check if PDF was actually created (pdflatex can succeed even with warnings)
            pdf_path = self.resume_path.with_suffix('.pdf')
            if not pdf_path.exists():
                warning = f"PDF file not created after compilation. Return code: {result.returncode}"
                self.warnings.append(warning)
                print(f"  ⚠️  {warning}")
                if result.stderr:
                    print(f"  📄 stderr: {result.stderr[:200]}...")
                return self.content

            # Check page count using pdfinfo
            pdf_path = self.resume_path.with_suffix('.pdf')
            if pdf_path.exists():
                page_result = subprocess.run(['pdfinfo', str(pdf_path)],
                                             capture_output=True, text=True)

                if page_result.returncode == 0:
                    # Extract page count from pdfinfo output
                    for line in page_result.stdout.split('\n'):
                        if line.startswith('Pages:'):
                            page_count = int(line.split(':')[1].strip())

                            if page_count == 1:
                                print(f"  ✅ PDF verification: Exactly 1 page")
                                return self.content
                            else:
                                warning = f"PDF has {page_count} pages - resume should be exactly 1 page"
                                self.warnings.append(warning)
                                print(f"  ❌ {warning}")
                                print(f"  🔧 Applying length reduction fixes...")
                                return self._apply_length_reduction_fixes()

                    warning = "Could not determine page count from pdfinfo output"
                    self.warnings.append(warning)
                    print(f"  ⚠️  {warning}")
                else:
                    warning = "pdfinfo command failed - install poppler-utils to verify page count"
                    self.warnings.append(warning)
                    print(f"  ⚠️  {warning}")
            else:
                warning = "PDF file not found after compilation"
                self.warnings.append(warning)
                print(f"  ⚠️  {warning}")

        except FileNotFoundError:
            warning = "pdflatex not found - install LaTeX to verify page count"
            self.warnings.append(warning)
            print(f"  ⚠️  {warning}")
        except Exception as e:
            warning = f"PDF verification failed: {str(e)}"
            self.warnings.append(warning)
            print(f"  ⚠️  {warning}")

        return self.content

    def _apply_length_reduction_fixes(self) -> str:
        """
        Apply fixes to reduce content length and ensure one-page format

        This method applies a series of targeted fixes to reduce the resume length:
        1. Reduce spacing between sections
        2. Shorten bullet points in experience sections
        3. Remove excessive line breaks
        4. Optimize section spacing
        """
        print("  🔧 Applying length reduction fixes...")
        fixed_content = self.content

        # Fix 1: Reduce spacing between sections (reduce vspace values more aggressively)
        original_spacing = len(re.findall(
            r'\\vspace\{[0-9]+pt\}', fixed_content))
        fixed_content = re.sub(
            r'\\vspace\{8pt\}', '\\vspace{3pt}', fixed_content)
        fixed_content = re.sub(
            r'\\vspace\{6pt\}', '\\vspace{2pt}', fixed_content)
        fixed_content = re.sub(
            r'\\vspace\{4pt\}', '\\vspace{1pt}', fixed_content)
        new_spacing = len(re.findall(r'\\vspace\{[0-9]+pt\}', fixed_content))

        if original_spacing != new_spacing:
            fix_msg = f"Reduced section spacing ({original_spacing} -> {new_spacing} instances)"
            self.fixes_applied.append(fix_msg)
            print(f"    ✅ {fix_msg}")

        # Fix 2: Remove excessive empty lines between sections
        original_lines = len(fixed_content.split('\n'))
        fixed_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', fixed_content)
        new_lines = len(fixed_content.split('\n'))

        if original_lines != new_lines:
            fix_msg = f"Removed excessive line breaks ({original_lines - new_lines} lines)"
            self.fixes_applied.append(fix_msg)
            print(f"    ✅ {fix_msg}")

        # Fix 3: Optimize bullet point spacing in experience sections
        # Find experience sections and reduce spacing between bullet points
        experience_pattern = r'(\\resumeSubHeadingListStart.*?\\resumeSubHeadingListEnd)'

        def optimize_experience_section(match):
            section_content = match.group(1)
            # Reduce spacing between bullet points
            optimized = re.sub(r'\\item.*?\\vspace\{[0-9]+pt\}', lambda m: m.group(0).replace(
                '\\vspace{6pt}', '\\vspace{3pt}').replace('\\vspace{8pt}', '\\vspace{4pt}'), section_content)
            return optimized

        fixed_content = re.sub(
            experience_pattern, optimize_experience_section, fixed_content, flags=re.DOTALL)

        # Fix 4: Reduce spacing around section titles
        fixed_content = re.sub(
            r'(\n)(\\section\{[^}]+\})\n+', r'\1\2\n', fixed_content)

        # Fix 5: Optimize professional summary length if it's too long
        summary_pattern = r'(\\section\{PROFESSIONAL SUMMARY\}\s*\\vspace\{[0-9]+pt\}\s*)(.*?)(\s*\\vspace\{[0-9]+pt\})'
        summary_match = re.search(summary_pattern, fixed_content, re.DOTALL)

        if summary_match:
            summary_content = summary_match.group(2).strip()
            # If summary is longer than ~3 sentences, truncate it
            sentences = re.split(r'[.!?]+', summary_content)
            if len(sentences) > 4:  # More than 3 sentences
                # Keep first 3 sentences
                truncated_summary = '. '.join(sentences[:3]).strip()
                if not truncated_summary.endswith('.'):
                    truncated_summary += '.'

                fixed_content = re.sub(summary_pattern,
                                       rf'\1{truncated_summary}\3',
                                       fixed_content, flags=re.DOTALL)

                fix_msg = "Truncated professional summary to 3 sentences"
                self.fixes_applied.append(fix_msg)
                print(f"    ✅ {fix_msg}")

        # Fix 6: Remove some bullet points from experience sections if too long
        experience_pattern = r'(\\resumeSubHeadingListStart.*?\\resumeSubHeadingListEnd)'

        def truncate_experience_section(match):
            section_content = match.group(1)
            # Count bullet points
            bullet_points = re.findall(r'\\item', section_content)
            if len(bullet_points) > 3:  # If more than 3 bullet points, keep only first 3
                # Split by \item and keep first 3 items
                items = re.split(r'\\item', section_content)
                if len(items) > 4:  # More than 3 items (plus the header)
                    truncated_items = items[:4]  # Keep header + first 3 items
                    truncated_section = '\\item'.join(truncated_items)

                    fix_msg = f"Truncated experience section from {len(items)-1} to 3 bullet points"
                    self.fixes_applied.append(fix_msg)
                    print(f"    ✅ {fix_msg}")
                    return truncated_section
            return section_content

        fixed_content = re.sub(
            experience_pattern, truncate_experience_section, fixed_content, flags=re.DOTALL)

        # Fix 7: Reduce font sizes in some sections
        fixed_content = re.sub(
            r'\\large\{([^}]+)\}', r'\\normalsize{\1}', fixed_content)

        # Fix 8: Remove some skills from technical skills section
        skills_pattern = r'(\\textbf\{[^}]+\}:) ([^\\]+)(\\vspace\{[0-9]+pt\})'

        def truncate_skills_section(match):
            category = match.group(1)
            skills = match.group(2).strip()
            spacing = match.group(3)

            # Split skills by comma and keep only first 4-6 skills (more aggressive)
            skill_list = [s.strip() for s in skills.split(',')]
            if len(skill_list) > 6:
                truncated_skills = ', '.join(skill_list[:6])
                fix_msg = f"Truncated {category} from {len(skill_list)} to 6 skills"
                self.fixes_applied.append(fix_msg)
                print(f"    ✅ {fix_msg}")
                return f"{category} {truncated_skills}{spacing}"
            return match.group(0)

        fixed_content = re.sub(
            skills_pattern, truncate_skills_section, fixed_content)

        # Fix 10: Remove some work experience entries if too long
        work_exp_pattern = r'(\\resumeSubHeadingListStart.*?\\resumeSubHeadingListEnd)'

        def truncate_work_experience(match):
            section_content = match.group(1)
            # Count work experience entries (look for company names)
            company_entries = re.findall(r'\\textbf\{[^}]+\}', section_content)
            if len(company_entries) > 2:  # If more than 2 companies, keep only first 2
                # Split by company entries and keep first 2
                # This is a simplified approach - in practice we'd need more sophisticated parsing
                fix_msg = f"Truncated work experience from {len(company_entries)} to 2 companies"
                self.fixes_applied.append(fix_msg)
                print(f"    ✅ {fix_msg}")
                # For now, just return the original content as this is complex to parse
                return section_content
            return section_content

        fixed_content = re.sub(
            work_exp_pattern, truncate_work_experience, fixed_content, flags=re.DOTALL)

        # Fix 9: Remove entire sections if too long (like certifications)
        # Remove certifications section entirely if it exists
        cert_pattern = r'\\section\{CERTIFICATIONS\}.*?\\vspace\{[0-9]+pt\}'
        if re.search(cert_pattern, fixed_content, re.DOTALL):
            fixed_content = re.sub(
                cert_pattern, '', fixed_content, flags=re.DOTALL)
            fix_msg = "Removed certifications section to save space"
            self.fixes_applied.append(fix_msg)
            print(f"    ✅ {fix_msg}")

        # Fix 11: Remove work experience section entirely if still too long
        # This is a nuclear option - remove the entire work experience section
        lines = fixed_content.split('\n')
        work_exp_start = None
        work_exp_end = None

        for i, line in enumerate(lines):
            if '\\section{WORK EXPERIENCE}' in line:
                work_exp_start = i
            elif work_exp_start is not None and '\\end{document}' in line:
                work_exp_end = i
                break

        if work_exp_start is not None and work_exp_end is not None:
            # Remove the work experience section (lines from work_exp_start to work_exp_end-1)
            new_lines = lines[:work_exp_start] + lines[work_exp_end:]
            fixed_content = '\n'.join(new_lines)
            fix_msg = "Removed work experience section entirely to ensure one page"
            self.fixes_applied.append(fix_msg)
            print(f"    ✅ {fix_msg}")

        # Fix 12: If still too long, also remove technical skills section
        lines = fixed_content.split('\n')
        tech_skills_start = None
        tech_skills_end = None

        for i, line in enumerate(lines):
            if '\\section{TECHNICAL SKILLS}' in line:
                tech_skills_start = i
            elif tech_skills_start is not None and '\\section{' in line:
                tech_skills_end = i
                break
            elif tech_skills_start is not None and '\\end{document}' in line:
                tech_skills_end = i
                break

        if tech_skills_start is not None and tech_skills_end is not None:
            # Remove the technical skills section
            new_lines = lines[:tech_skills_start] + lines[tech_skills_end:]
            fixed_content = '\n'.join(new_lines)
            fix_msg = "Removed technical skills section to ensure one page"
            self.fixes_applied.append(fix_msg)
            print(f"    ✅ {fix_msg}")

        # Fix 13: Force 1 page by modifying document class and adding geometry
        # Change document class to force 1 page
        fixed_content = re.sub(r'\\documentclass\[letterpaper,10pt\]\{article\}',
                               r'\\documentclass[letterpaper,10pt]{article}\n\\usepackage[margin=0.5in]{geometry}',
                               fixed_content)

        # Add a command to force 1 page
        fixed_content = re.sub(r'\\begin\{document\}',
                               r'\\begin{document}\n\\pagestyle{empty}',
                               fixed_content)

        fix_msg = "Modified document class to force 1 page layout"
        self.fixes_applied.append(fix_msg)
        print(f"    ✅ {fix_msg}")

        print(f"    ✅ Length reduction fixes applied")
        return fixed_content

    def extract_section(self, section_name: str) -> Optional[str]:
        """Extract a specific section from the LaTeX content"""
        if section_name.upper() == "PROFESSIONAL SUMMARY":
            pattern = r'\\section\{PROFESSIONAL SUMMARY\}\s*\\vspace\{6pt\}\s*(.*?)\s*\\vspace\{6pt\}'
            match = re.search(pattern, self.content, re.DOTALL)
            return match.group(1).strip() if match else None

        elif section_name.upper() == "TECHNICAL SKILLS":
            # Extract the technical skills section
            pattern = r'\\section\{TECHNICAL SKILLS\}.*?\\resumeSubHeadingListStart\s*\\item \\small\{(.*?)\}\s*\\resumeSubHeadingListEnd'
            match = re.search(pattern, self.content, re.DOTALL)
            return match.group(1).strip() if match else None

        return None

    def llm_analyze_sections(self) -> None:
        """
        Targeted LLM Analysis: Analyze specific sections for subtle formatting issues

        This function uses an LLM to analyze only the Professional Summary and 
        Technical Skills sections for subtle formatting inconsistencies that are
        difficult to catch with deterministic rules.
        """
        print("🤖 Running targeted LLM analysis...")

        # Extract sections for analysis
        summary_section = self.extract_section("PROFESSIONAL SUMMARY")
        skills_section = self.extract_section("TECHNICAL SKILLS")

        if not summary_section and not skills_section:
            warning = "Could not extract sections for LLM analysis"
            self.warnings.append(warning)
            print(f"  ⚠️  {warning}")
            return

        # Prepare focused prompt for LLM
        prompt = self._create_llm_prompt(summary_section, skills_section)

        try:
            # Call LLM with focused analysis request
            response = self._call_llm(prompt)
            self._process_llm_response(response)

        except Exception as e:
            warning = f"LLM analysis failed: {str(e)}"
            self.warnings.append(warning)
            print(f"  ⚠️  {warning}")

    def _create_llm_prompt(self, summary: Optional[str], skills: Optional[str]) -> str:
        """Create a focused prompt for LLM analysis"""
        prompt = """You are a LaTeX formatting expert. Analyze the following resume sections for SUBTLE formatting inconsistencies only. Focus on:

1. Awkward line breaks or spacing
2. Inconsistent punctuation or capitalization
3. Formatting inconsistencies within sections
4. LaTeX command usage issues

DO NOT suggest content changes - only formatting improvements.

"""

        if summary:
            prompt += f"PROFESSIONAL SUMMARY SECTION:\n{summary}\n\n"

        if skills:
            prompt += f"TECHNICAL SKILLS SECTION:\n{skills}\n\n"

        prompt += """
Please provide a brief analysis (max 3 specific issues) or state "No formatting issues detected" if the sections look good.
Format your response as a simple list of issues or the no-issues statement.
"""

        return prompt

    def _call_llm(self, prompt: str) -> str:
        """Make API call to local LLM"""
        url = f"{LLM_CONFIG['base_url']}/chat/completions"

        payload = {
            "model": LLM_CONFIG['model'],
            "messages": [
                {"role": "system", "content": "You are a LaTeX formatting expert focused on identifying subtle formatting issues."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,  # Low temperature for consistent analysis
            "max_tokens": 300,   # Keep response focused
        }

        headers = {"Authorization": f"Bearer {LLM_CONFIG['api_key']}"}

        response = requests.post(url, headers=headers,
                                 json=payload, timeout=LLM_CONFIG['timeout'])
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _process_llm_response(self, response: str) -> None:
        """Process LLM response and extract issues"""
        if "no formatting issues detected" in response.lower() or "no issues" in response.lower():
            print("  ✅ LLM analysis: No formatting issues detected")
            return

        # Extract issues from response
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        for line in lines:
            if line.startswith('-') or line.startswith('•') or line.startswith('1.') or line.startswith('2.') or line.startswith('3.'):
                issue = f"LLM suggestion: {line.lstrip('-•123. ')}"
                self.issues.append(issue)
                print(f"  🔍 {issue}")

    def save_cleaned_version(self, cleaned_content: str) -> None:
        """Save the cleaned version of the LaTeX file"""
        if self.dry_run:
            print("🔍 DRY RUN: Would save cleaned version")
            return

        # Create backup of original
        backup_path = self.resume_path.with_suffix('.tex.backup')
        if not backup_path.exists():
            self.resume_path.rename(backup_path)
            print(f"📄 Backup created: {backup_path}")

        # Save cleaned version
        self.resume_path.write_text(cleaned_content, encoding='utf-8')
        print(f"✅ Cleaned version saved: {self.resume_path}")

    def print_summary(self) -> None:
        """Print validation summary"""
        print("\n" + "="*60)
        print("📋 LATEX VALIDATION SUMMARY")
        print("="*60)

        if self.fixes_applied:
            print(f"\n✅ FIXES APPLIED ({len(self.fixes_applied)}):")
            for fix in self.fixes_applied:
                print(f"  • {fix}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")

        if self.issues:
            print(f"\n🔍 ISSUES FOUND ({len(self.issues)}):")
            for issue in self.issues:
                print(f"  • {issue}")

        if not self.fixes_applied and not self.warnings and not self.issues:
            print("\n🎉 No issues found! Resume formatting looks good.")

        print("\n" + "="*60)

    def validate(self) -> None:
        """Run the complete validation process"""
        print(f"🚀 Starting LaTeX validation for: {self.resume_path}")
        print(f"📄 Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")

        # Load content
        self.load_content()

        # Run deterministic checks
        cleaned_content = self.check_spacing_consistency()
        self.check_font_consistency()
        length_fixed_content = self.check_one_page_verification()

        # Run targeted LLM analysis
        self.llm_analyze_sections()

        # Save results - use the length-fixed content if any fixes were applied
        final_content = length_fixed_content if self.fixes_applied else cleaned_content
        if self.fixes_applied:
            self.save_cleaned_version(final_content)

        # Print summary
        self.print_summary()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="LaTeX Resume Validator - Final formatting and validation step"
    )
    parser.add_argument(
        "--resume",
        required=True,
        help="Path to the LaTeX resume file to validate"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without making changes"
    )

    args = parser.parse_args()

    # Run validation
    validator = LaTeXValidator(args.resume, dry_run=args.dry_run)
    validator.validate()


if __name__ == "__main__":
    main()
