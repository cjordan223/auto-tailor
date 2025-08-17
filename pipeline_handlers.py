#!/usr/bin/env python3
"""
Pipeline handlers for JD Parser & Resume Tailoring
Contains the core pipeline processing logic separated from the web interface.

This module provides the main pipeline functions that coordinate between:
1. Job Description parsing (jd-parser.py)
2. Skills updating (skills-updater.py) 
3. Summary updating (summary-updater.py)
4. PDF generation and comparison (pdf_utils.py)

The pipeline follows this flow:
Job Description → Parse & Extract Skills → Update Resume Skills → Update Summary → Generate PDFs
"""

import sys
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from pdf_utils import compile_latex_to_pdf, pdf_to_base64


def run_jd_parsing(jd_file_path: str, temp_dir: str) -> Dict[str, Any]:
    """
    Run only the JD parsing part of the pipeline.
    
    This function executes jd-parser.py to extract skills, responsibilities, and values
    from a job description. It returns structured data that can be used by the
    resume updating components.
    
    Args:
        jd_file_path: Path to the job description text file
        temp_dir: Temporary directory for processing artifacts
        
    Returns:
        Dictionary containing:
        - success: Boolean indicating if parsing succeeded
        - skills: Dictionary with skills organized by category
        - skills_count: Total number of skills extracted
        - artifacts: Raw artifacts from the parsing process
        - error: Error message if parsing failed
    """
    try:
        print("🔧 Running jd-parser.py...")
        cmd = [
            sys.executable, 'jd-parser.py',
            '--jd', jd_file_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')

        if result.returncode == 0:
            print("✅ JD parsing completed successfully")

            # Read the generated artifacts
            artifacts = {}
            artifacts_dir = Path('artifacts')

            if artifacts_dir.exists():
                for artifact_file in artifacts_dir.glob('*.json'):
                    try:
                        with open(artifact_file, 'r') as f:
                            artifacts[artifact_file.name] = f.read()
                    except Exception as e:
                        print(
                            f"Warning: Could not read artifact {artifact_file}: {e}")

            # Parse the skills from jd_skills.json
            jd_skills_path = artifacts_dir / 'jd_skills.json'
            skills = {}
            skills_count = 0

            if jd_skills_path.exists():
                try:
                    with open(jd_skills_path, 'r') as f:
                        jd_data = json.load(f)

                        # Send the complete skills data structure for frontend
                        skills = {
                            'by_section_top3': jd_data.get('by_section_top3', {}),
                            'skills_flat': jd_data.get('skills_flat', []),
                            'job_skills_ranked': jd_data.get('job_skills_ranked', [])
                        }

                        # Count total skills from skills_flat for accuracy
                        skills_count = len(jd_data.get('skills_flat', []))

                except Exception as e:
                    print(f"Warning: Could not parse JD skills: {e}")

            return {
                'success': True,
                'skills': skills,
                'skills_count': skills_count,
                'artifacts': artifacts
            }
        else:
            error_msg = result.stderr or result.stdout or 'JD parsing failed'
            print(f"❌ JD parsing failed: {error_msg}")
            return {'success': False, 'error': f'JD parsing failed: {error_msg}'}

    except Exception as e:
        return {'success': False, 'error': f'JD parsing failed: {str(e)}'}


def run_resume_update(temp_dir: str, selected_skills: List[Dict[str, str]] = None, proposed_summary: str = '', skip_summary: bool = False) -> Dict[str, Any]:
    """
    Run the resume update part of the pipeline with selected skills and optional summary.
    
    This function executes skills-updater.py to update the technical skills section
    of the resume based on the extracted job skills. It can also update the summary
    if provided.
    
    Args:
        temp_dir: Temporary directory for processing
        selected_skills: List of skills selected by the user for inclusion
        proposed_summary: New summary text to replace the existing one
        skip_summary: Whether to skip summary updating
        
    Returns:
        Dictionary containing:
        - success: Boolean indicating if update succeeded
        - changes: Dictionary describing what was changed
        - error: Error message if update failed
    """
    try:
        print("🔧 Running skills-updater.py...")

        # Create a temporary file with selected skills if provided
        selected_skills_file = None
        if selected_skills:
            selected_skills_file = Path(temp_dir) / 'selected_skills.json'
            with open(selected_skills_file, 'w') as f:
                json.dump({'selected_skills': selected_skills}, f, indent=2)

        # Run skills updater
        cmd = [sys.executable, 'skills-updater.py']
        if selected_skills_file:
            cmd.extend(['--selected-skills', str(selected_skills_file)])

        result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')

        if result.returncode == 0:
            print("✅ Skills update completed successfully")
            
            # Parse the changes from the output
            changes = parse_skills_changes(result.stdout)
            
            return {
                'success': True,
                'changes': changes
            }
        else:
            error_msg = result.stderr or result.stdout or 'Skills update failed'
            print(f"❌ Skills update failed: {error_msg}")
            return {'success': False, 'error': f'Skills update failed: {error_msg}'}

    except Exception as e:
        return {'success': False, 'error': f'Skills update failed: {str(e)}'}


def run_summary_update(temp_dir: str, proposed_summary: str = '') -> Dict[str, Any]:
    """
    Run the summary update part of the pipeline.
    
    This function executes summary-updater.py to update the professional summary
    section of the resume based on the job description and company values.
    
    Args:
        temp_dir: Temporary directory for processing
        proposed_summary: New summary text to replace the existing one
        
    Returns:
        Dictionary containing:
        - success: Boolean indicating if update succeeded
        - changes: Dictionary describing what was changed
        - error: Error message if update failed
    """
    try:
        print("🔧 Running summary-updater.py...")

        # Create a temporary file with proposed summary if provided
        summary_file = None
        if proposed_summary:
            summary_file = Path(temp_dir) / 'proposed_summary.txt'
            with open(summary_file, 'w') as f:
                f.write(proposed_summary)

        # Run summary updater
        cmd = [sys.executable, 'summary-updater.py']
        if summary_file:
            cmd.extend(['--proposed-summary', str(summary_file)])

        result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')

        if result.returncode == 0:
            print("✅ Summary update completed successfully")
            
            # Parse the changes from the output
            changes = parse_summary_changes(result.stdout)
            
            return {
                'success': True,
                'changes': changes
            }
        else:
            error_msg = result.stderr or result.stdout or 'Summary update failed'
            print(f"❌ Summary update failed: {error_msg}")
            return {'success': False, 'error': f'Summary update failed: {error_msg}'}

    except Exception as e:
        return {'success': False, 'error': f'Summary update failed: {str(e)}'}


def parse_skills_changes(output: str) -> Dict[str, Any]:
    """
    Parse the skills changes from the skills-updater output.
    
    Args:
        output: The stdout from skills-updater.py
        
    Returns:
        Dictionary containing parsed changes information
    """
    changes = {
        'added': [],
        'removed': [],
        'skipped': [],
        'total_added': 0,
        'total_removed': 0,
        'total_skipped': 0
    }
    
    # Simple parsing of the output to extract change information
    lines = output.split('\n')
    for line in lines:
        if 'ADDED:' in line:
            skill = line.split('ADDED:')[-1].strip()
            if skill:
                changes['added'].append(skill)
                changes['total_added'] += 1
        elif 'REMOVED:' in line:
            skill = line.split('REMOVED:')[-1].strip()
            if skill:
                changes['removed'].append(skill)
                changes['total_removed'] += 1
        elif 'SKIPPED:' in line:
            skill = line.split('SKIPPED:')[-1].strip()
            if skill:
                changes['skipped'].append(skill)
                changes['total_skipped'] += 1
    
    return changes


def parse_summary_changes(output: str) -> Dict[str, Any]:
    """
    Parse the summary changes from the summary-updater output.
    
    Args:
        output: The stdout from summary-updater.py
        
    Returns:
        Dictionary containing parsed changes information
    """
    changes = {
        'old_summary': '',
        'new_summary': '',
        'changes_made': False
    }
    
    # Simple parsing of the output to extract summary information
    lines = output.split('\n')
    in_old = False
    in_new = False
    
    for line in lines:
        if 'OLD SUMMARY:' in line:
            in_old = True
            in_new = False
            continue
        elif 'NEW SUMMARY:' in line:
            in_old = False
            in_new = True
            continue
        elif line.strip() == '':
            in_old = False
            in_new = False
            continue
            
        if in_old:
            changes['old_summary'] += line + '\n'
        elif in_new:
            changes['new_summary'] += line + '\n'
    
    changes['old_summary'] = changes['old_summary'].strip()
    changes['new_summary'] = changes['new_summary'].strip()
    changes['changes_made'] = changes['old_summary'] != changes['new_summary']
    
    return changes


def ensure_baseline_backup() -> bool:
    """
    Ensure that a baseline backup of the resume exists for comparison.
    
    This function creates a permanent backup of the original resume files
    in the baseline_backup directory if they don't already exist.
    
    Returns:
        Boolean indicating if baseline backup was successful
    """
    try:
        baseline_dir = Path('baseline_backup')
        baseline_dir.mkdir(exist_ok=True)
        
        resume_dir = Path('Resume')
        if not resume_dir.exists():
            print("Warning: Resume directory not found")
            return False
            
        # Check if baseline already exists
        baseline_tex = baseline_dir / 'Conner_Jordan_Software_Engineer.tex'
        if baseline_tex.exists():
            print("✅ Baseline backup already exists")
            return True
            
        # Create baseline backup
        source_tex = resume_dir / 'Conner_Jordan_Software_Engineer.tex'
        if source_tex.exists():
            import shutil
            shutil.copy2(source_tex, baseline_tex)
            print("✅ Created baseline backup")
            return True
        else:
            print("Warning: Source resume file not found")
            return False
            
    except Exception as e:
        print(f"Error creating baseline backup: {e}")
        return False


def cleanup_temp_files(temp_dir: str):
    """
    Clean up temporary files created during processing.
    
    Args:
        temp_dir: Path to the temporary directory to clean up
    """
    try:
        temp_path = Path(temp_dir)
        if temp_path.exists():
            import shutil
            shutil.rmtree(temp_path)
            print(f"✅ Cleaned up temporary directory: {temp_dir}")
    except Exception as e:
        print(f"Warning: Could not clean up temporary directory {temp_dir}: {e}")


# -------------------
# Main Pipeline Functions
# -------------------

def run_complete_pipeline(jd_file_path: str, selected_skills: List[Dict[str, str]] = None, 
                         proposed_summary: str = '', skip_summary: bool = False) -> Dict[str, Any]:
    """
    Run the complete pipeline from job description to tailored resume.
    
    This is the main orchestration function that runs all pipeline components
    in sequence: JD parsing → Skills updating → Summary updating → PDF generation.
    
    Args:
        jd_file_path: Path to the job description file
        selected_skills: Optional list of skills to include
        proposed_summary: Optional new summary text
        skip_summary: Whether to skip summary updating
        
    Returns:
        Dictionary containing the complete pipeline results
    """
    temp_dir = tempfile.mkdtemp(prefix='pipeline_')
    
    try:
        # Step 1: Parse job description
        jd_result = run_jd_parsing(jd_file_path, temp_dir)
        if not jd_result['success']:
            return jd_result
            
        # Step 2: Update resume skills
        skills_result = run_resume_update(temp_dir, selected_skills, proposed_summary, skip_summary)
        if not skills_result['success']:
            return skills_result
            
        # Step 3: Update summary (if not skipped)
        summary_result = None
        if not skip_summary:
            summary_result = run_summary_update(temp_dir, proposed_summary)
            if not summary_result['success']:
                return summary_result
                
        # Step 4: Generate comparison PDFs
        pdf_result = generate_comparison_pdfs()
        
        return {
            'success': True,
            'jd_parsing': jd_result,
            'skills_update': skills_result,
            'summary_update': summary_result,
            'pdf_generation': pdf_result,
            'temp_dir': temp_dir
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Pipeline failed: {str(e)}'}
    finally:
        # Don't clean up temp_dir here as it might be needed by the web interface
        pass
