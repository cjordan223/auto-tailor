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

from flask import Flask, request, render_template_string, jsonify, send_file

# Import PDF utilities
from pdf_utils import compile_latex_to_pdf, backup_resume_files, generate_comparison_pdfs, pdf_to_base64

app = Flask(__name__)

# Import existing pipeline modules
sys.path.append('.')

# HTML Template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JD Parser & Resume Tailoring</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #555;
        }
        textarea {
            width: 100%;
            height: 300px;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-family: monospace;
            font-size: 14px;
            resize: vertical;
            box-sizing: border-box;
        }
        textarea:focus {
            outline: none;
            border-color: #007acc;
        }
        .button-group {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-top: 25px;
        }
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .btn-primary {
            background-color: #007acc;
            color: white;
        }
        .btn-primary:hover {
            background-color: #005a99;
        }
        .btn-secondary {
            background-color: #6c757d;
            color: white;
        }
        .btn-secondary:hover {
            background-color: #545b62;
        }
        .btn-primary:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        .status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 6px;
            display: none;
        }
        .status.success {
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }
        .status.error {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }
        .status.info {
            background-color: #d1ecf1;
            border: 1px solid #bee5eb;
            color: #0c5460;
        }
        .progress {
            margin-top: 15px;
            text-align: center;
        }
        .spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #007acc;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .example {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 20px;
        }
        .example h3 {
            margin-top: 0;
            color: #495057;
        }
        .example p {
            margin-bottom: 0;
            color: #6c757d;
            font-size: 14px;
        }
        .skills-section {
            display: none;
            margin-top: 30px;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            background: #f8f9fa;
        }
        .skills-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
            margin-top: 15px;
        }
        .skill-item {
            background: white;
            padding: 8px 12px;
            border-radius: 6px;
            border: 1px solid #e9ecef;
            font-size: 14px;
            color: #495057;
            text-align: center;
        }
        .skill-category {
            margin-bottom: 20px;
        }
        .skill-category h4 {
            margin-bottom: 10px;
            color: #495057;
            border-bottom: 2px solid #007acc;
            padding-bottom: 5px;
        }
        .btn-success {
            background-color: #28a745;
            color: white;
        }
        .btn-success:hover {
            background-color: #218838;
        }
        .btn-success:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        .pdf-comparison {
            display: none;
            margin-top: 30px;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            background: #f8f9fa;
        }
        .pdf-viewer {
            display: flex;
            gap: 20px;
            margin-top: 15px;
        }
        .pdf-container {
            flex: 1;
            text-align: center;
        }
        .pdf-container h4 {
            margin-bottom: 10px;
            color: #495057;
        }
        .pdf-embed {
            width: 100%;
            height: 600px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        .changes-summary {
            display: none;
            margin-top: 30px;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            background: #f8f9fa;
        }
        .change-section {
            margin-bottom: 20px;
            border: 1px solid #e9ecef;
            border-radius: 6px;
            overflow: hidden;
        }
        .change-header {
            background: #007acc;
            color: white;
            padding: 10px 15px;
            font-weight: 600;
            margin: 0;
        }
        .change-content {
            padding: 15px;
        }
        .skill-change {
            display: flex;
            align-items: center;
            margin-bottom: 8px;
            padding: 8px;
            border-radius: 4px;
            background: white;
        }
        .skill-change.added {
            border-left: 4px solid #28a745;
            background: #f8fff9;
        }
        .skill-change.removed {
            border-left: 4px solid #dc3545;
            background: #fff8f8;
        }
        .skill-change.skipped {
            border-left: 4px solid #ffc107;
            background: #fffbf0;
        }
        .change-icon {
            margin-right: 8px;
            font-weight: bold;
        }
        .added .change-icon {
            color: #28a745;
        }
        .removed .change-icon {
            color: #dc3545;
        }
        .skipped .change-icon {
            color: #ffc107;
        }
        .skill-name {
            font-weight: 600;
            margin-right: 10px;
        }
        .skill-reason {
            font-size: 0.9em;
            color: #6c757d;
            font-style: italic;
        }
        @media (max-width: 768px) {
            .pdf-viewer {
                flex-direction: column;
            }
            .pdf-embed {
                height: 400px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 JD Parser & Resume Tailoring Pipeline</h1>
        
        <div class="example">
            <h3>How it works:</h3>
            <p>1. Paste your job description below<br>
               2. Click "Process Job Description" to extract relevant skills<br>
               3. Download your tailored resume files</p>
        </div>

        <form id="jdForm">
            <div class="form-group">
                <label for="jobDescription">Job Description:</label>
                <textarea 
                    id="jobDescription" 
                    name="jobDescription" 
                    placeholder="Paste the job description here..."
                    required
                ></textarea>
            </div>
            
            <div class="button-group">
                <button type="submit" class="btn-primary" id="processBtn">
                    Process Job Description
                </button>
                <button type="button" class="btn-secondary" onclick="clearForm()">
                    Clear
                </button>
                <button type="button" class="btn-secondary" onclick="resetBaseline()" title="Reset the baseline 'before' resume to current state">
                    Reset Baseline
                </button>
            </div>
        </form>

        <div id="status" class="status"></div>
        
        <div id="skillsSection" class="skills-section">
            <h3>🎯 Extracted Skills</h3>
            <div id="skillsContent"></div>
            <div class="button-group" style="margin-top: 20px;">
                <button type="button" class="btn-success" id="updateResumeBtn" onclick="updateResume()">
                    Update Resume with Skills
                </button>
            </div>
        </div>
        
        <div id="changesSummary" class="changes-summary">
            <h3>📝 Resume Changes Summary</h3>
            <div id="changesContent"></div>
        </div>
        
        <div id="pdfComparison" class="pdf-comparison">
            <h3>📄 Resume Comparison</h3>
            <div class="pdf-viewer">
                <div class="pdf-container">
                    <h4>Before (Original)</h4>
                    <embed id="beforePDF" class="pdf-embed" type="application/pdf">
                </div>
                <div class="pdf-container">
                    <h4>After (Tailored)</h4>
                    <embed id="afterPDF" class="pdf-embed" type="application/pdf">
                </div>
            </div>
        </div>
    </div>

    <script>
        const form = document.getElementById('jdForm');
        const status = document.getElementById('status');
        const processBtn = document.getElementById('processBtn');
        const skillsSection = document.getElementById('skillsSection');
        const skillsContent = document.getElementById('skillsContent');
        const updateResumeBtn = document.getElementById('updateResumeBtn');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const jobDescription = document.getElementById('jobDescription').value.trim();
            if (!jobDescription) {
                showStatus('Please enter a job description.', 'error');
                return;
            }

            // Show processing status
            processBtn.disabled = true;
            processBtn.innerHTML = '<span class="spinner"></span>Processing...';
            showStatus('Processing job description and extracting skills...', 'info');

            try {
                const response = await fetch('/process-jd', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ job_description: jobDescription })
                });

                if (response.ok) {
                    const result = await response.json();
                    if (result.success) {
                        showStatus(`✅ Success! Extracted ${result.skills_count} relevant skills.`, 'success');
                        
                        // Display extracted skills
                        if (result.skills) {
                            displaySkills(result.skills);
                        }
                        
                        // Show PDF comparison if available
                        if (result.before_pdf && result.after_pdf) {
                            showPDFComparison(result.before_pdf, result.after_pdf);
                        }
                    } else {
                        showStatus(`❌ Error: ${result.error}`, 'error');
                    }
                } else {
                    const error = await response.json();
                    showStatus(`❌ Error: ${error.error || 'Processing failed'}`, 'error');
                }
            } catch (error) {
                showStatus(`❌ Network error: ${error.message}`, 'error');
            } finally {
                // Reset button
                processBtn.disabled = false;
                processBtn.innerHTML = 'Process Job Description';
            }
        });

        function showStatus(message, type) {
            status.innerHTML = message;
            status.className = `status ${type}`;
            status.style.display = 'block';
        }

        function clearForm() {
            document.getElementById('jobDescription').value = '';
            status.style.display = 'none';
            skillsSection.style.display = 'none';
            document.getElementById('pdfComparison').style.display = 'none';
            document.getElementById('changesSummary').style.display = 'none';
        }

        function displaySkills(skills) {
            let html = '';
            
            // Group skills by category if available
            if (skills.by_section_top3) {
                for (const [category, skillList] of Object.entries(skills.by_section_top3)) {
                    if (skillList && skillList.length > 0) {
                        html += `<div class="skill-category">
                            <h4>${category}</h4>
                            <div class="skills-grid">`;
                        skillList.forEach(skill => {
                            html += `<div class="skill-item">${skill}</div>`;
                        });
                        html += `</div></div>`;
                    }
                }
            } else if (skills.categorized) {
                for (const [category, skillList] of Object.entries(skills.categorized)) {
                    if (skillList && skillList.length > 0) {
                        html += `<div class="skill-category">
                            <h4>${category}</h4>
                            <div class="skills-grid">`;
                        skillList.forEach(skill => {
                            html += `<div class="skill-item">${skill}</div>`;
                        });
                        html += `</div></div>`;
                    }
                }
            } else if (skills.skills_flat) {
                // Display as flat list
                html += `<div class="skills-grid">`;
                skills.skills_flat.forEach(skill => {
                    html += `<div class="skill-item">${skill}</div>`;
                });
                html += `</div>`;
            } else if (skills.flat) {
                // Display as flat list
                html += `<div class="skills-grid">`;
                skills.flat.forEach(skill => {
                    html += `<div class="skill-item">${skill}</div>`;
                });
                html += `</div>`;
            } else if (Array.isArray(skills)) {
                // Direct array
                html += `<div class="skills-grid">`;
                skills.forEach(skill => {
                    html += `<div class="skill-item">${skill}</div>`;
                });
                html += `</div>`;
            }
            
            skillsContent.innerHTML = html;
            skillsSection.style.display = 'block';
        }

        async function updateResume() {
            updateResumeBtn.disabled = true;
            updateResumeBtn.innerHTML = '<span class="spinner"></span>Updating Resume...';
            showStatus('Updating resume with extracted skills...', 'info');

            try {
                const response = await fetch('/update-resume', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                });

                if (response.ok) {
                    const result = await response.json();
                    if (result.success) {
                        showStatus(`✅ Resume updated successfully! <a href="/download/${result.download_id}" style="color: #007acc; text-decoration: none; font-weight: 600;">Download updated resume files</a>`, 'success');
                        
                        // Show changes summary if available
                        if (result.changes) {
                            showChangesSummary(result.changes);
                        }
                        
                        // Show PDF comparison if available
                        if (result.before_pdf && result.after_pdf) {
                            showPDFComparison(result.before_pdf, result.after_pdf);
                        }
                    } else {
                        showStatus(`❌ Error: ${result.error}`, 'error');
                    }
                } else {
                    const error = await response.json();
                    showStatus(`❌ Error: ${error.error || 'Resume update failed'}`, 'error');
                }
            } catch (error) {
                showStatus(`❌ Network error: ${error.message}`, 'error');
            } finally {
                updateResumeBtn.disabled = false;
                updateResumeBtn.innerHTML = 'Update Resume with Skills';
            }
        }

        function showChangesSummary(changes) {
            const summaryDiv = document.getElementById('changesSummary');
            const contentDiv = document.getElementById('changesContent');
            
            let html = '';
            
            // Group changes by section
            const sections = {};
            
            // Process added skills
            if (changes.added && changes.added.length > 0) {
                changes.added.forEach(change => {
                    if (!sections[change.section]) {
                        sections[change.section] = { added: [], removed: [], skipped: [] };
                    }
                    sections[change.section].added.push(change);
                });
            }
            
            // Process removed skills
            if (changes.removed && changes.removed.length > 0) {
                changes.removed.forEach(change => {
                    if (!sections[change.section]) {
                        sections[change.section] = { added: [], removed: [], skipped: [] };
                    }
                    sections[change.section].removed.push(change);
                });
            }
            
            // Process skipped skills
            if (changes.skipped && changes.skipped.length > 0) {
                changes.skipped.forEach(change => {
                    if (!sections[change.section]) {
                        sections[change.section] = { added: [], removed: [], skipped: [] };
                    }
                    sections[change.section].skipped.push(change);
                });
            }
            
            // Add summary changes as a special section
            if (changes.summary_updated && changes.summary_changes) {
                sections['Professional Summary'] = { 
                    added: [], 
                    removed: [], 
                    skipped: [],
                    summary_change: changes.summary_changes
                };
            }
            
            // Generate HTML for each section
            for (const [sectionName, sectionChanges] of Object.entries(sections)) {
                html += `<div class="change-section">
                    <h4 class="change-header">${sectionName}</h4>
                    <div class="change-content">`;
                
                // Added skills
                sectionChanges.added.forEach(change => {
                    html += `<div class="skill-change added">
                        <span class="change-icon">+</span>
                        <span class="skill-name">${change.skill}</span>
                        <span class="skill-reason">${change.reason || 'Added from job requirements'}</span>
                    </div>`;
                });
                
                // Removed skills
                sectionChanges.removed.forEach(change => {
                    html += `<div class="skill-change removed">
                        <span class="change-icon">−</span>
                        <span class="skill-name">${change.skill}</span>
                        <span class="skill-reason">${change.reason || 'Removed to make room for job-relevant skills'}</span>
                    </div>`;
                });
                
                // Skipped skills
                sectionChanges.skipped.forEach(change => {
                    html += `<div class="skill-change skipped">
                        <span class="change-icon">⚠</span>
                        <span class="skill-name">${change.skill}</span>
                        <span class="skill-reason">${change.reason || 'Skipped - reason not specified'}</span>
                    </div>`;
                });
                
                // Summary changes (special handling)
                if (sectionChanges.summary_change) {
                    const summaryChange = sectionChanges.summary_change;
                    html += `<div class="skill-change added">
                        <span class="change-icon">✏️</span>
                        <span class="skill-name">Professional Summary</span>
                        <span class="skill-reason">${summaryChange.reason}</span>
                    </div>`;
                    
                    // Add expandable before/after comparison
                    html += `<div style="margin-top: 10px;">
                        <details style="background: #f8f9fa; padding: 10px; border-radius: 4px;">
                            <summary style="cursor: pointer; font-weight: 600;">View Summary Changes</summary>
                            <div style="margin-top: 10px;">
                                <div style="margin-bottom: 10px;">
                                    <strong>Before:</strong>
                                    <div style="background: #fff; padding: 8px; border-radius: 4px; font-style: italic; margin-top: 4px;">
                                        ${summaryChange.original}
                                    </div>
                                </div>
                                <div>
                                    <strong>After:</strong>
                                    <div style="background: #fff; padding: 8px; border-radius: 4px; font-style: italic; margin-top: 4px;">
                                        ${summaryChange.revised}
                                    </div>
                                </div>
                            </div>
                        </details>
                    </div>`;
                }
                
                html += `</div></div>`;
            }
            
            if (!html) {
                html = '<p>No specific changes detected. Skills may have been reorganized or optimized.</p>';
            }
            
            contentDiv.innerHTML = html;
            summaryDiv.style.display = 'block';
        }

        function showPDFComparison(beforePDF, afterPDF) {
            const comparison = document.getElementById('pdfComparison');
            const beforeEmbed = document.getElementById('beforePDF');
            const afterEmbed = document.getElementById('afterPDF');
            
            beforeEmbed.src = `data:application/pdf;base64,${beforePDF}`;
            afterEmbed.src = `data:application/pdf;base64,${afterPDF}`;
            
            comparison.style.display = 'block';
        }

        async function resetBaseline() {
            if (!confirm('Are you sure you want to reset the baseline? This will set the current resume as the new "before" state for all future comparisons.')) {
                return;
            }

            try {
                showStatus('Resetting baseline backup...', 'info');
                
                const response = await fetch('/reset-baseline', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                });

                if (response.ok) {
                    const result = await response.json();
                    if (result.success) {
                        showStatus('✅ Baseline reset successfully! The current resume is now the new baseline.', 'success');
                    } else {
                        showStatus(`❌ Error: ${result.error}`, 'error');
                    }
                } else {
                    const error = await response.json();
                    showStatus(`❌ Error: ${error.error || 'Failed to reset baseline'}`, 'error');
                }
            } catch (error) {
                showStatus(`❌ Network error: ${error.message}`, 'error');
            }
        }
    </script>
</body>
</html>
"""

# Store processing results temporarily
processing_results = {}


@app.route('/')
def index():
    """Serve the main web interface"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/process-jd', methods=['POST'])
def process_job_description():
    """Process a job description through the existing pipeline"""
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


@app.route('/update-resume', methods=['POST'])
def update_resume():
    """Update the resume with extracted skills"""
    try:
        # Find the most recent JD session
        jd_sessions = [k for k in processing_results.keys()
                       if k.startswith('jd_session_')]
        if not jd_sessions:
            return jsonify({'success': False, 'error': 'No job description session found. Please process a job description first.'}), 400

        # Get the most recent session
        latest_session = max(
            jd_sessions, key=lambda x: processing_results[x].get('temp_dir', ''))
        session_data = processing_results[latest_session]

        # Run the resume update pipeline
        result = run_resume_update(session_data['temp_dir'])

        if result['success']:
            # Generate PDFs for comparison
            before_pdf_b64 = None
            after_pdf_b64 = None

            # Get before PDF (from permanent baseline backup)
            before_pdf_path = Path('baseline_backup/Conner_Jordan_Software_Engineer.pdf')
            if before_pdf_path.exists():
                before_pdf_b64 = pdf_to_base64(str(before_pdf_path))

            # Generate after PDF (compile updated resume)
            resume_tex = Path('Resume/Conner_Jordan_Software_Engineer.tex')
            if resume_tex.exists():
                after_pdf_path = compile_latex_to_pdf(
                    str(resume_tex), str(Path(session_data['temp_dir']) / 'after'))
                if after_pdf_path:
                    after_pdf_b64 = pdf_to_base64(after_pdf_path)

            # Generate unique download ID for the final result
            download_id = f"final_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"

            # Store final result for download
            processing_results[download_id] = {
                'temp_dir': session_data['temp_dir'],
                'skills_count': session_data['skills_count'],
                'files': result['files'],
                'before_pdf': before_pdf_b64,
                'after_pdf': after_pdf_b64
            }

            response_data = {
                'success': True,
                'download_id': download_id,
                'skills_count': session_data['skills_count']
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
            print(f"⚠️  Warning: Could not find current resume TEX file: {current_tex}")
            
        if current_pdf.exists():
            shutil.copy2(current_pdf, baseline_pdf)
            print(f"✅ Backed up baseline PDF: {current_pdf} -> {baseline_pdf}")
        else:
            # Generate PDF from TEX if PDF doesn't exist
            if current_tex.exists():
                print("📄 Generating baseline PDF from TEX...")
                pdf_path = compile_latex_to_pdf(str(current_tex), str(baseline_dir))
                if pdf_path:
                    print(f"✅ Generated baseline PDF: {pdf_path}")
                else:
                    print("❌ Failed to generate baseline PDF")
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
                            skill_section = ranked_skill.get('section', 'Unknown')
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

def run_resume_update(temp_dir: str) -> Dict[str, Any]:
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
        
        # Step 2: Use subprocess to run summary-updater
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
            
        if not summary_updated_block.exists():
            return {
                'success': False,
                'error': 'Summary updater did not generate required artifacts'
            }
        
        # Parse changes from skills and summary editor outputs
        changes = parse_all_changes(temp_dir)
        
        result_data = {
            'success': True,
            'files': [
                'artifacts/jd_skills.json', 
                'artifacts/skills_updated_block.tex', 
                'artifacts/skills_editor_output.json',
                'artifacts/summary_updated_block.tex',
                'artifacts/summary_editor_output.json', 
                'skills.tex', 
                'Resume/Conner_Jordan_Software_Engineer.tex'
            ]
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

if __name__ == '__main__':
    print("🚀 Starting JD Parser Web UI...")
    print("📝 Open http://localhost:8081 in your browser")
    print("💡 Make sure LM Studio is running with qwen2.5-32b-instruct model")
    
    # Ensure baseline backup exists on startup
    print("\n🔧 Checking baseline backup...")
    ensure_baseline_backup()
    
    app.run(debug=False, host='127.0.0.1', port=8081, use_reloader=False)
