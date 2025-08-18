#!/usr/bin/env python3
"""
Web UI for JD Parser & Resume Tailoring Pipeline

A Flask web application that provides a simple interface for uploading job descriptions
and generating tailored resume files through the existing pipeline.
"""

import sys
import asyncio
import json
import os
import tempfile
import zipfile
import base64
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from flask import Flask, request, render_template, jsonify, send_file

# Import PDF utilities
from pdf_utils import compile_latex_to_pdf, backup_resume_files, generate_comparison_pdfs, pdf_to_base64

# Import performance monitoring
from performance_monitor import get_performance_dashboard_data, create_performance_report
from cache_manager import cleanup_cache, get_cache_stats
from task_queue import cleanup_old_tasks, get_queue_stats

app = Flask(__name__)

# Import existing pipeline modules
sys.path.append('.')

# Store processing results temporarily
processing_results = {}


@app.route('/')
def index():
    """Serve the main web interface"""
    return render_template('index.html')


@app.route('/process-jd', methods=['POST'])
def process_job_description():
    """Process a job description through the existing pipeline (synchronous)"""
    try:
        data = request.get_json()
        if not data or 'job_description' not in data:
            return jsonify({'success': False, 'error': 'No job description provided'}), 400

        job_description = data['job_description'].strip()
        if not job_description:
            return jsonify({'success': False, 'error': 'Job description cannot be empty'}), 400

        # Create temporary directory for this processing session
        temp_dir = tempfile.mkdtemp(prefix='jd_processing_')
        temp_jd_file = Path(temp_dir) / 'jd.txt'

        # Write JD to temporary file
        temp_jd_file.write_text(job_description, encoding='utf-8')

        # Create or use permanent baseline backup for "before" comparison
        baseline_backup_successful = ensure_baseline_backup()

        # Run the JD parsing pipeline
        result = run_jd_parsing(str(temp_jd_file), temp_dir)

        if result['success']:
            # Generate unique download ID for this session
            download_id = f"jd_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"

            # Store result for this session
            processing_results[download_id] = {
                'temp_dir': temp_dir,
                'skills_count': result['skills_count'],
                'skills_data': result['skills_data'],
                'jd_file': str(temp_jd_file)
            }

            response_data = {
                'success': True,
                'download_id': download_id,
                'skills_count': result['skills_count'],
                'skills': result['skills_data']
            }

            return jsonify(response_data)
        else:
            return jsonify({'success': False, 'error': result['error']}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/process-jd-async', methods=['POST'])
def process_job_description_async():
    """Process a job description asynchronously for better performance"""
    try:
        from task_queue import submit_skills_extraction_task, get_task_queue

        data = request.get_json()
        if not data or 'job_description' not in data:
            return jsonify({'success': False, 'error': 'No job description provided'}), 400

        job_description = data['job_description'].strip()
        if not job_description:
            return jsonify({'success': False, 'error': 'Job description cannot be empty'}), 400

        # Create or use permanent baseline backup for "before" comparison
        ensure_baseline_backup()

        # Submit to background task queue
        task_id = submit_skills_extraction_task(job_description)

        # Store session info
        session_id = f"async_jd_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{task_id[:8]}"
        processing_results[session_id] = {
            'task_id': task_id,
            'job_description': job_description,
            'created_at': datetime.now().isoformat(),
            'async': True
        }

        return jsonify({
            'success': True,
            'task_id': task_id,
            'session_id': session_id,
            'status': 'processing',
            'message': 'Job description submitted for processing. Use task_id to check status.'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/task-status/<task_id>')
def get_task_status(task_id):
    """Get the status of an async task"""
    try:
        from task_queue import get_task_queue

        queue = get_task_queue()
        task = queue.get_task_status(task_id)

        if not task:
            return jsonify({'success': False, 'error': 'Task not found'}), 404

        response = {
            'success': True,
            'task_id': task_id,
            'status': task.status.value,
            'progress': task.progress,
            'created_at': task.created_at.isoformat(),
            'task_type': task.task_type
        }

        if task.started_at:
            response['started_at'] = task.started_at.isoformat()
        if task.completed_at:
            response['completed_at'] = task.completed_at.isoformat()
        if task.error:
            response['error'] = task.error
        if task.result:
            response['result'] = task.result
            # For completed skills extraction, format as expected by frontend
            if task.task_type == 'skills_extraction' and task.status.value == 'completed':
                response['skills_count'] = len(
                    task.result.get('skills_flat', []))
                response['skills'] = task.result

        return jsonify(response)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/generate-summary', methods=['POST'])
def generate_summary():
    """Generate professional summary without modifying files"""
    try:
        # Run summary-updater.py with --generate-only flag
        result = subprocess.run([
            sys.executable, 'summary-updater.py', '--generate-only'
        ], capture_output=True, text=True, timeout=1800)  # 30 minutes timeout

        if result.returncode != 0:
            return jsonify({
                'success': False,
                'error': f'Summary generation failed: {result.stderr}'
            }), 500

        # Extract the summary from stdout (skip the log messages)
        output_lines = result.stdout.strip().split('\n')
        # Find the actual summary text (usually the last non-empty line after log messages)
        summary_text = ""
        for line in reversed(output_lines):
            if line.strip() and not line.startswith('🧠') and not line.startswith('✅'):
                summary_text = line.strip()
                break

        if not summary_text:
            # If we can't find clean summary, return the full stdout
            summary_text = result.stdout.strip()

        return jsonify({
            'success': True,
            'summary': summary_text
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Summary generation timed out after 30 minutes'
        }), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/update-resume', methods=['POST'])
def update_resume():
    """Update the resume with selected skills and custom summary"""
    try:
        # Get request data
        data = request.get_json() or {}
        selected_skills = data.get('selected_skills', [])
        professional_summary = data.get('professional_summary', '')

        # Find the most recent JD session (handle both sync and async sessions)
        jd_sessions = [k for k in processing_results.keys()
                       if k.startswith('jd_session_') or k.startswith('async_jd_session_')]
        if not jd_sessions:
            return jsonify({'success': False, 'error': 'No job description session found. Please process a job description first.'}), 400

        # Get the most recent session
        latest_session = max(
            jd_sessions, key=lambda x: processing_results[x].get('created_at', ''))
        session_data = processing_results[latest_session]

        # Handle different session types
        is_async_session = latest_session.startswith('async_jd_session_')

        # For async sessions, we need to create a temp_dir and get skills_count from artifacts
        if is_async_session:
            # Create temp directory for async session
            temp_dir = tempfile.mkdtemp(prefix='async_jd_processing_')
            session_data['temp_dir'] = temp_dir

            # Get skills count from artifacts if available
            artifacts_path = Path('artifacts/jd_skills.json')
            if artifacts_path.exists():
                with open(artifacts_path, 'r') as f:
                    skills_data = json.load(f)
                session_data['skills_count'] = len(
                    skills_data.get('skills_flat', []))
            else:
                session_data['skills_count'] = 0

        # Create a filtered skills file if specific skills were selected
        if selected_skills:
            # Load the original skills data
            artifacts_path = Path('artifacts/jd_skills.json')
            if artifacts_path.exists():
                with open(artifacts_path, 'r') as f:
                    original_skills = json.load(f)

                # Filter the skills to only include selected ones
                filtered_skills = {
                    'skills_flat': selected_skills,
                    'by_section_top3': {},
                    'categorized': {},
                    'job_skills_ranked': []
                }

                # Preserve structure for selected skills
                if 'by_section_top3' in original_skills:
                    for section, skills in original_skills['by_section_top3'].items():
                        filtered_section_skills = [
                            s for s in skills if s in selected_skills]
                        if filtered_section_skills:
                            filtered_skills['by_section_top3'][section] = filtered_section_skills

                if 'job_skills_ranked' in original_skills:
                    filtered_skills['job_skills_ranked'] = [
                        skill_obj for skill_obj in original_skills['job_skills_ranked']
                        if skill_obj.get('canonical') in selected_skills
                    ]

                # Write filtered skills back to artifacts
                with open(artifacts_path, 'w') as f:
                    json.dump(filtered_skills, f, indent=2)

                print(
                    f"✅ Filtered skills to {len(selected_skills)} selected items")

        # Run the resume update pipeline
        result = run_resume_update(
            session_data['temp_dir'], professional_summary)

        if result['success']:
            # Generate PDFs for comparison
            before_pdf_b64 = None
            after_pdf_b64 = None

            # Get before PDF (from permanent baseline backup)
            before_pdf_path = Path(
                'baseline_backup/Conner_Jordan_Software_Engineer.pdf')
            if before_pdf_path.exists():
                before_pdf_b64 = pdf_to_base64(str(before_pdf_path))

            # Generate after PDF (compile updated resume)
            resume_tex = Path('Resume/Conner_Jordan_Software_Engineer.tex')
            if resume_tex.exists():
                pdf_result = compile_latex_to_pdf(
                    str(resume_tex), str(Path(session_data['temp_dir']) / 'after'))
                if pdf_result and pdf_result.get('success'):
                    after_pdf_b64 = pdf_to_base64(pdf_result['pdf_path'])
                else:
                    print(
                        f"PDF compilation failed: {pdf_result.get('error', 'Unknown error')}")
                    after_pdf_b64 = None

            # Generate unique download ID for the final result
            download_id = f"final_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"

            # Store final result for download
            processing_results[download_id] = {
                'temp_dir': session_data['temp_dir'],
                'skills_count': len(selected_skills) if selected_skills else session_data['skills_count'],
                'files': result['files'],
                'before_pdf': before_pdf_b64,
                'after_pdf': after_pdf_b64
            }

            response_data = {
                'success': True,
                'download_id': download_id,
                'skills_count': len(selected_skills) if selected_skills else session_data['skills_count']
            }

            # Include PDF data if both are available
            if before_pdf_b64 and after_pdf_b64:
                response_data['before_pdf'] = before_pdf_b64
                response_data['after_pdf'] = after_pdf_b64

            # Include changes summary if available
            if 'changes' in result:
                response_data['changes'] = result['changes']

            return jsonify(response_data)
        else:
            return jsonify({'success': False, 'error': result['error']}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/download/<download_id>')
def download_result(download_id):
    """Download the processed resume files as a ZIP"""
    if download_id not in processing_results:
        return "Download not found or expired", 404

    try:
        result = processing_results[download_id]
        temp_dir = result['temp_dir']

        # Create ZIP file with results
        zip_path = Path(temp_dir) / 'tailored_resume.zip'

        with zipfile.ZipFile(zip_path, 'w') as zipf:
            # Add artifacts
            artifacts_dir = Path('artifacts')
            if artifacts_dir.exists():
                for file_path in artifacts_dir.glob('*'):
                    if file_path.is_file():
                        zipf.write(file_path, f'artifacts/{file_path.name}')

            # Add updated resume files if they exist
            skills_file = Path('skills.tex')
            if skills_file.exists():
                zipf.write(skills_file, 'skills.tex')

            resume_file = Path('Resume/Conner_Jordan_Software_Engineer.tex')
            if resume_file.exists():
                zipf.write(
                    resume_file, 'Resume/Conner_Jordan_Software_Engineer.tex')

        # Clean up after sending
        def remove_files():
            try:
                import shutil
                shutil.rmtree(temp_dir)
                del processing_results[download_id]
            except:
                pass

        return send_file(
            zip_path,
            as_attachment=True,
            download_name=f'tailored_resume_{download_id}.zip',
            mimetype='application/zip'
        )

    except Exception as e:
        return f"Error creating download: {str(e)}", 500


def run_jd_parsing(jd_file_path: str, temp_dir: str) -> Dict[str, Any]:
    """Run only the JD parsing part of the pipeline"""
    try:
        print("🔧 Running jd-parser.py...")

        # Use subprocess to run jd-parser properly
        result = subprocess.run([
            sys.executable, 'jd-parser.py', '--jd', jd_file_path
        ], capture_output=True, text=True, timeout=1800)  # 30 minutes timeout

        print(f"JD-parser exit code: {result.returncode}")
        if result.stdout:
            print(f"JD-parser stdout: {result.stdout}")
        if result.stderr:
            print(f"JD-parser stderr: {result.stderr}")

        if result.returncode != 0:
            return {
                'success': False,
                'error': f'JD parser failed with exit code {result.returncode}: {result.stderr}'
            }

        # Load and validate results
        artifacts_path = Path('artifacts/jd_skills.json')
        if artifacts_path.exists():
            with open(artifacts_path, 'r') as f:
                skills_data = json.load(f)

            skills_count = len(skills_data.get('skills_flat', []))
            print(f"✅ JD parsing completed - extracted {skills_count} skills")

            return {
                'success': True,
                'skills_count': skills_count,
                'skills_data': skills_data
            }
        else:
            return {'success': False, 'error': 'Failed to extract skills from job description'}

    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'JD parser timed out after 30 minutes'}
    except Exception as e:
        return {'success': False, 'error': f'JD parsing failed: {str(e)}'}


def ensure_baseline_backup() -> bool:
    """
    Ensure we have a permanent baseline backup of the original resume.
    This backup will never be updated and serves as the 'before' state for all comparisons.
    """
    try:
        baseline_dir = Path('baseline_backup')
        baseline_tex = baseline_dir / 'Conner_Jordan_Software_Engineer.tex'
        baseline_pdf = baseline_dir / 'Conner_Jordan_Software_Engineer.pdf'

        # If baseline backup already exists, don't overwrite it
        if baseline_dir.exists() and baseline_tex.exists() and baseline_pdf.exists():
            print("✅ Using existing baseline backup")
            return True

        print("📁 Creating baseline backup (first time setup)...")
        baseline_dir.mkdir(exist_ok=True)

        # Copy current resume files to baseline backup
        current_tex = Path('Resume/Conner_Jordan_Software_Engineer.tex')
        current_pdf = Path('Resume/Conner_Jordan_Software_Engineer.pdf')

        if current_tex.exists():
            shutil.copy2(current_tex, baseline_tex)
            print(f"✅ Backed up baseline TEX: {current_tex} -> {baseline_tex}")
        else:
            print(
                f"⚠️  Warning: Could not find current resume TEX file: {current_tex}")

        if current_pdf.exists():
            shutil.copy2(current_pdf, baseline_pdf)
            print(f"✅ Backed up baseline PDF: {current_pdf} -> {baseline_pdf}")
        else:
            # Generate PDF from TEX if PDF doesn't exist
            if current_tex.exists():
                print("📄 Generating baseline PDF from TEX...")
                pdf_result = compile_latex_to_pdf(
                    str(current_tex), str(baseline_dir))
                if pdf_result and pdf_result.get('success'):
                    print(
                        f"✅ Generated baseline PDF: {pdf_result['pdf_path']}")
                else:
                    print(
                        f"❌ Failed to generate baseline PDF: {pdf_result.get('error', 'Unknown error')}")
                    return False
            else:
                print("❌ Cannot create baseline backup - no TEX or PDF file found")
                return False

        print("✅ Baseline backup created successfully")
        return True

    except Exception as e:
        print(f"❌ Failed to create baseline backup: {e}")
        return False


def parse_all_changes(temp_dir: str) -> Optional[Dict[str, Any]]:
    """Parse changes from both skills and summary editor outputs"""
    try:
        # Get skills changes
        skills_changes = parse_skills_changes(temp_dir)

        # Get summary changes
        summary_changes = parse_summary_changes(temp_dir)

        # Combine changes
        all_changes = {
            'added': [],
            'removed': [],
            'skipped': [],
            'summary_updated': False,
            'summary_changes': None
        }

        if skills_changes:
            all_changes['added'].extend(skills_changes.get('added', []))
            all_changes['removed'].extend(skills_changes.get('removed', []))
            all_changes['skipped'].extend(skills_changes.get('skipped', []))

        if summary_changes:
            all_changes['summary_updated'] = True
            all_changes['summary_changes'] = summary_changes

        return all_changes if (all_changes['added'] or all_changes['removed'] or all_changes['skipped'] or all_changes['summary_updated']) else None

    except Exception as e:
        print(f"Warning: Could not parse changes: {e}")
        return None


def parse_summary_changes(temp_dir: str) -> Optional[Dict[str, Any]]:
    """Parse changes from the summary editor output"""
    try:
        summary_output_path = Path('artifacts/summary_editor_output.json')

        if not summary_output_path.exists():
            return None

        with open(summary_output_path, 'r') as f:
            summary_output = json.load(f)

        original_summary = summary_output.get('original_summary', '')
        revised_summary = summary_output.get('revised_summary', '')

        if original_summary and revised_summary and original_summary.strip() != revised_summary.strip():
            return {
                'original': original_summary.strip(),
                'revised': revised_summary.strip(),
                'change_type': 'Professional Summary Updated',
                'reason': 'Tailored to align with job requirements and company values'
            }

        return None

    except Exception as e:
        print(f"Warning: Could not parse summary changes: {e}")
        return None


def parse_skills_changes(temp_dir: str) -> Optional[Dict[str, Any]]:
    """Parse changes from the skills editor output and extract added/removed/skipped skills"""
    try:
        # Read the skills editor output
        editor_output_path = Path('artifacts/skills_editor_output.json')
        jd_skills_path = Path('artifacts/jd_skills.json')

        if not editor_output_path.exists() or not jd_skills_path.exists():
            return None

        with open(editor_output_path, 'r') as f:
            editor_output = json.load(f)

        with open(jd_skills_path, 'r') as f:
            jd_skills = json.load(f)

        changes = {
            'added': [],
            'removed': [],
            'skipped': []
        }

        # Parse change notes from editor output
        change_notes = editor_output.get('change_notes', [])

        for note in change_notes:
            section = note.get('section', 'Unknown')
            added_skills = note.get('added', note.get('adds', []))
            removed_skills = note.get('removed', note.get('removes', []))
            reason = note.get('reason', '')

            # Add skills that were added
            for skill in added_skills:
                changes['added'].append({
                    'skill': skill,
                    'section': section,
                    'reason': reason or 'Added from job requirements'
                })

            # Add skills that were removed
            for skill in removed_skills:
                changes['removed'].append({
                    'skill': skill,
                    'section': section,
                    'reason': reason or 'Removed to make room for job-relevant skills'
                })

        # Identify skills that were extracted but not added (skipped)
        jd_skills_flat = jd_skills.get('skills_flat', [])
        added_skills_list = [change['skill'] for change in changes['added']]

        # Read the current skills to see what was actually added
        skills_updated_path = Path('artifacts/skills_updated_block.tex')
        if skills_updated_path.exists():
            updated_skills_content = skills_updated_path.read_text()

            for skill in jd_skills_flat:
                if skill not in added_skills_list and skill not in updated_skills_content:
                    # This skill was extracted but not added
                    # Try to determine which section it would belong to
                    skill_section = 'Unknown'
                    for ranked_skill in jd_skills.get('job_skills_ranked', []):
                        if ranked_skill.get('canonical') == skill:
                            skill_section = ranked_skill.get(
                                'section', 'Unknown')
                            break

                    changes['skipped'].append({
                        'skill': skill,
                        'section': skill_section,
                        'reason': 'Not added - may be irrelevant to section or already present'
                    })

        return changes if (changes['added'] or changes['removed'] or changes['skipped']) else None

    except Exception as e:
        print(f"Warning: Could not parse skills changes: {e}")
        return None


def update_summary_in_tex_file(summary_text: str) -> bool:
    """Update the professional summary directly in the resume .tex file"""
    try:
        import re
        from pathlib import Path

        resume_file = Path('Resume/Conner_Jordan_Software_Engineer.tex')
        if not resume_file.exists():
            return False

        # Read current resume content
        resume_content = resume_file.read_text()

        # Pattern to find the summary section
        SUMMARY_PATTERN = re.compile(
            r"(% SUMMARY_BLOCK_START\s*\n)(.*?)(\n\s*% SUMMARY_BLOCK_END)",
            re.DOTALL
        )

        if SUMMARY_PATTERN.search(resume_content):
            # Replace the content of the summary block
            updated_content = SUMMARY_PATTERN.sub(
                f"\\1{summary_text.strip()}\\3",
                resume_content,
                count=1
            )
            resume_file.write_text(updated_content)
            return True
        else:
            print("Warning: Could not find summary block markers in resume file")
            return False

    except Exception as e:
        print(f"Error updating summary in tex file: {e}")
        return False


def run_resume_update(temp_dir: str, custom_summary: str = None) -> Dict[str, Any]:
    """Run only the resume update part of the pipeline"""
    try:
        print("🔧 Running skills-updater.py...")

        # Step 1: Use subprocess to run skills-updater
        skills_result = subprocess.run([
            sys.executable, 'skills-updater.py'
        ], capture_output=True, text=True, timeout=300)

        print(f"Skills-updater exit code: {skills_result.returncode}")
        if skills_result.stdout:
            print(f"Skills-updater stdout: {skills_result.stdout}")
        if skills_result.stderr:
            print(f"Skills-updater stderr: {skills_result.stderr}")

        if skills_result.returncode != 0:
            return {
                'success': False,
                'error': f'Skills updater failed with exit code {skills_result.returncode}: {skills_result.stderr}'
            }

        print("✅ Skills updater completed successfully")

        # Step 2: Handle summary update
        if custom_summary:
            # Use the provided custom summary directly
            print("📝 Using custom professional summary...")
            success = update_summary_in_tex_file(custom_summary)
            if not success:
                return {
                    'success': False,
                    'error': 'Failed to update custom summary in resume file'
                }
            print("✅ Custom summary updated successfully")
        else:
            # Use subprocess to run summary-updater
            print("🔧 Running summary-updater.py...")
            summary_result = subprocess.run([
                sys.executable, 'summary-updater.py'
            ], capture_output=True, text=True, timeout=300)

            print(f"Summary-updater exit code: {summary_result.returncode}")
            if summary_result.stdout:
                print(f"Summary-updater stdout: {summary_result.stdout}")
            if summary_result.stderr:
                print(f"Summary-updater stderr: {summary_result.stderr}")

            if summary_result.returncode != 0:
                return {
                    'success': False,
                    'error': f'Summary updater failed with exit code {summary_result.returncode}: {summary_result.stderr}'
                }

            print("✅ Summary updater completed successfully")

        # Check if the required artifacts were created
        artifacts_dir = Path('artifacts')
        skills_updated_block = artifacts_dir / 'skills_updated_block.tex'
        skills_editor_output = artifacts_dir / 'skills_editor_output.json'
        summary_updated_block = artifacts_dir / 'summary_updated_block.tex'
        summary_editor_output = artifacts_dir / 'summary_editor_output.json'

        if not skills_updated_block.exists():
            return {
                'success': False,
                'error': 'Skills updater did not generate required artifacts'
            }

        # Only check for summary artifacts if we didn't use a custom summary
        if not custom_summary and not summary_updated_block.exists():
            return {
                'success': False,
                'error': 'Summary updater did not generate required artifacts'
            }

        # Parse changes from skills and summary editor outputs
        changes = parse_all_changes(temp_dir)

        files_list = [
            'artifacts/jd_skills.json',
            'artifacts/skills_updated_block.tex',
            'artifacts/skills_editor_output.json',
            'skills.tex',
            'Resume/Conner_Jordan_Software_Engineer.tex'
        ]

        # Only include summary artifacts if we used the automatic summary updater
        if not custom_summary:
            files_list.extend([
                'artifacts/summary_updated_block.tex',
                'artifacts/summary_editor_output.json'
            ])

        result_data = {
            'success': True,
            'files': files_list
        }

        if changes:
            result_data['changes'] = changes

        return result_data

    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'Resume updater timed out after 5 minutes'}
    except Exception as e:
        return {'success': False, 'error': f'Resume update failed: {str(e)}'}


def run_pipeline(jd_file_path: str, temp_dir: str) -> Dict[str, Any]:
    """Run the complete pipeline (for backward compatibility)"""
    # First run JD parsing
    jd_result = run_jd_parsing(jd_file_path, temp_dir)
    if not jd_result['success']:
        return jd_result

    # Then run resume update
    update_result = run_resume_update(temp_dir)
    if not update_result['success']:
        return update_result

    # Combine results
    return {
        'success': True,
        'skills_count': jd_result['skills_count'],
        'files': update_result['files']
    }


@app.route('/reset-baseline', methods=['POST'])
def reset_baseline():
    """Reset the baseline backup to current resume state"""
    try:
        # Remove existing baseline backup
        baseline_dir = Path('baseline_backup')
        if baseline_dir.exists():
            shutil.rmtree(baseline_dir)
            print("🗑️ Removed existing baseline backup")

        # Create new baseline backup
        success = ensure_baseline_backup()

        if success:
            return jsonify({'success': True, 'message': 'Baseline backup reset successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to create new baseline backup'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/performance')
def performance_dashboard():
    """Serve the performance dashboard"""
    return render_template('performance.html')


@app.route('/api/performance')
def api_performance():
    """API endpoint for performance data"""
    try:
        data = get_performance_dashboard_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/performance/report')
def api_performance_report():
    """API endpoint for detailed performance report"""
    try:
        report = create_performance_report()
        return jsonify(report)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/performance/cleanup', methods=['POST'])
def api_performance_cleanup():
    """API endpoint for cleaning up old data"""
    try:
        cache_cleaned = cleanup_cache()
        tasks_cleaned = cleanup_old_tasks()

        return jsonify({
            'success': True,
            'cache_cleaned': cache_cleaned,
            'tasks_cleaned': tasks_cleaned
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/performance/stats')
def api_performance_stats():
    """API endpoint for performance statistics"""
    try:
        cache_stats = get_cache_stats()
        queue_stats = get_queue_stats()

        return jsonify({
            'cache': cache_stats,
            'tasks': queue_stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("🚀 Starting JD Parser Web UI...")
    print("📝 Open http://localhost:8081 in your browser")
    print("💡 Make sure LM Studio is running with qwen2.5-32b-instruct model")

    # Ensure baseline backup exists on startup
    print("\n🔧 Checking baseline backup...")
    ensure_baseline_backup()

    app.run(debug=False, host='127.0.0.1', port=8081, use_reloader=False)
