#!/usr/bin/env python3
"""
PDF utilities for LaTeX resume compilation and management

This module provides utilities for:
1. Compiling LaTeX files to PDF using pdflatex
2. Creating backups of resume files before modifications
3. Generating comparison PDFs (before/after)
4. Converting PDFs to base64 for web display
5. Managing LaTeX compilation artifacts

The module handles common LaTeX compilation issues and provides
error handling for the resume tailoring pipeline.
"""

import subprocess
import shutil
import tempfile
import base64
import sys
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import os


def compile_latex_to_pdf(tex_file_path: str, output_dir: Optional[str] = None, use_cache: bool = True) -> Dict[str, Any]:
    """
    Compile a LaTeX file to PDF using pdflatex with intelligent caching.
    
    This function handles LaTeX compilation with proper error handling,
    temporary directory management, and caching to avoid redundant compilations.
    
    Args:
        tex_file_path: Path to the .tex file to compile
        output_dir: Directory to save the PDF (defaults to same dir as tex file)
        use_cache: Whether to use caching for faster compilation (default: True)
    
    Returns:
        Dictionary containing:
        - success: Boolean indicating if compilation succeeded
        - pdf_path: Path to generated PDF file (if successful)
        - error: Error message (if failed)
        - cached: Boolean indicating if result came from cache
    """
    tex_path = Path(tex_file_path)
    if not tex_path.exists():
        return {
            'success': False,
            'error': f'LaTeX file not found: {tex_path}',
            'cached': False
        }
    
    # Read tex content for caching
    tex_content = tex_path.read_text(encoding='utf-8')
    
    # Check cache first if enabled
    if use_cache:
        try:
            from cache_manager import get_cached_pdf_compilation, cache_pdf_compilation
            cached_pdf_path = get_cached_pdf_compilation(tex_content)
            if cached_pdf_path and Path(cached_pdf_path).exists():
                print("🚀 Using cached PDF compilation", file=sys.stderr)
                return {
                    'success': True,
                    'pdf_path': cached_pdf_path,
                    'cached': True
                }
        except ImportError:
            print("Cache manager not available for PDF compilation", file=sys.stderr)
    
    print("⚙️ Compiling LaTeX to PDF (no cache hit)", file=sys.stderr)
    
    if output_dir is None:
        output_dir = tex_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # If output_dir is same as tex file directory, use temp dir to avoid conflicts
    if output_dir.resolve() == tex_path.parent.resolve():
        output_dir = Path(tempfile.mkdtemp())
    
    # Expected PDF output path
    pdf_name = tex_path.stem + '.pdf'
    pdf_path = output_dir / pdf_name
    
    try:
        # Create a temporary copy in output directory to avoid permission issues
        temp_tex_path = output_dir / tex_path.name
        shutil.copy2(tex_path, temp_tex_path)
        
        # Run pdflatex with minimal output
        result = subprocess.run([
            'pdflatex',
            '-interaction=nonstopmode',
            str(temp_tex_path.name)
        ], 
        capture_output=True, 
        text=True,
        cwd=str(output_dir)
        )
        
        if result.returncode == 0 and pdf_path.exists():
            print(f"✅ PDF compiled successfully: {pdf_path}")
            
            # Cache the successful compilation if enabled
            if use_cache:
                try:
                    cache_pdf_compilation(tex_content, str(pdf_path))
                    print("💾 Cached PDF compilation result", file=sys.stderr)
                except:
                    print("Failed to cache PDF compilation", file=sys.stderr)
            
            return {
                'success': True,
                'pdf_path': str(pdf_path),
                'cached': False
            }
        else:
            error_msg = f"LaTeX compilation failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            print(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'cached': False
            }
            
    except Exception as e:
        error_msg = f"Error running pdflatex: {e}"
        print(f"❌ {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'cached': False
        }


def backup_resume_files(backup_dir: str) -> bool:
    """
    Create backup of current resume files before modification.
    
    This function creates a permanent backup of the resume files in the
    specified directory. This is important for maintaining the original
    version for comparison purposes.
    
    Args:
        backup_dir: Directory to store backups
    
    Returns:
        True if backup successful, False otherwise
    """
    try:
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Files to backup
        files_to_backup = [
            'Resume/Conner_Jordan_Software_Engineer.tex',
            'Resume/Conner_Jordan_Software_Engineer.pdf',
            'skills.tex'
        ]
        
        backup_success = True
        for file_path in files_to_backup:
            source = Path(file_path)
            if source.exists():
                dest = backup_path / source.name
                shutil.copy2(source, dest)
                print(f"✅ Backed up: {source} -> {dest}")
            else:
                print(f"⚠️  File not found for backup: {source}")
                backup_success = False
        
        return backup_success
        
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False


def generate_comparison_pdfs() -> Dict[str, Any]:
    """
    Generate before/after comparison PDFs for the resume.
    
    This function compiles both the baseline (original) and current resume
    to create comparison PDFs that can be displayed in the web interface.
    
    Returns:
        Dictionary containing:
        - success: Boolean indicating if generation succeeded
        - before_pdf: Path to baseline PDF (if successful)
        - after_pdf: Path to current PDF (if successful)
        - error: Error message (if failed)
    """
    try:
        # Ensure baseline backup exists
        baseline_dir = Path('baseline_backup')
        if not baseline_dir.exists():
            return {
                'success': False,
                'error': 'Baseline backup directory not found'
            }
        
        # Compile baseline PDF
        baseline_tex = baseline_dir / 'Conner_Jordan_Software_Engineer.tex'
        if not baseline_tex.exists():
            return {
                'success': False,
                'error': 'Baseline LaTeX file not found'
            }
        
        baseline_result = compile_latex_to_pdf(str(baseline_tex))
        if not baseline_result['success']:
            return baseline_result
        
        # Compile current PDF
        current_tex = Path('Resume/Conner_Jordan_Software_Engineer.tex')
        if not current_tex.exists():
            return {
                'success': False,
                'error': 'Current LaTeX file not found'
            }
        
        current_result = compile_latex_to_pdf(str(current_tex))
        if not current_result['success']:
            return current_result
        
        return {
            'success': True,
            'before_pdf': baseline_result['pdf_path'],
            'after_pdf': current_result['pdf_path']
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Comparison PDF generation failed: {e}'
        }


def pdf_to_base64(pdf_path: str) -> Optional[str]:
    """
    Convert a PDF file to base64 string for web display.
    
    This function reads a PDF file and converts it to a base64-encoded string
    that can be embedded in HTML for display in the web interface.
    
    Args:
        pdf_path: Path to the PDF file to convert
    
    Returns:
        Base64-encoded string of the PDF, or None if conversion failed
    """
    try:
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            print(f"Error: PDF file not found: {pdf_path}")
            return None
        
        with open(pdf_file, 'rb') as f:
            pdf_data = f.read()
        
        # Convert to base64
        pdf_b64 = base64.b64encode(pdf_data).decode('utf-8')
        return pdf_b64
        
    except Exception as e:
        print(f"Error converting PDF to base64: {e}")
        return None


def cleanup_latex_artifacts(tex_file_path: str):
    """
    Clean up LaTeX compilation artifacts.
    
    This function removes temporary files created during LaTeX compilation
    such as .aux, .log, .out files to keep the directory clean.
    
    Args:
        tex_file_path: Path to the original .tex file
    """
    try:
        tex_path = Path(tex_file_path)
        tex_dir = tex_path.parent
        stem = tex_path.stem
        
        # Common LaTeX artifact extensions
        extensions = ['.aux', '.log', '.out', '.toc', '.lof', '.lot', '.fls', '.fdb_latexmk']
        
        for ext in extensions:
            artifact_file = tex_dir / f"{stem}{ext}"
            if artifact_file.exists():
                artifact_file.unlink()
                print(f"✅ Cleaned up: {artifact_file}")
                
    except Exception as e:
        print(f"Warning: Could not clean up LaTeX artifacts: {e}")


def validate_latex_file(tex_file_path: str) -> Dict[str, Any]:
    """
    Validate a LaTeX file for common issues.
    
    This function performs basic validation on a LaTeX file to check for
    common issues that might cause compilation problems.
    
    Args:
        tex_file_path: Path to the .tex file to validate
    
    Returns:
        Dictionary containing:
        - valid: Boolean indicating if file is valid
        - issues: List of validation issues found
        - warnings: List of warnings
    """
    try:
        tex_path = Path(tex_file_path)
        if not tex_path.exists():
            return {
                'valid': False,
                'issues': [f'File not found: {tex_file_path}'],
                'warnings': []
            }
        
        content = tex_path.read_text(encoding='utf-8')
        issues = []
        warnings = []
        
        # Check for common issues
        if not content.strip():
            issues.append('File is empty')
        
        if '\\documentclass' not in content:
            issues.append('Missing \\documentclass declaration')
        
        if '\\begin{document}' not in content:
            issues.append('Missing \\begin{document}')
        
        if '\\end{document}' not in content:
            issues.append('Missing \\end{document}')
        
        # Check for potential issues
        if content.count('\\begin{document}') != content.count('\\end{document}'):
            warnings.append('Mismatched document environment')
        
        if '\\usepackage' not in content:
            warnings.append('No packages imported')
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }
        
    except Exception as e:
        return {
            'valid': False,
            'issues': [f'Validation error: {e}'],
            'warnings': []
        }