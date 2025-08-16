#!/usr/bin/env python3
"""
PDF utilities for LaTeX resume compilation and management
"""

import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import os

def compile_latex_to_pdf(tex_file_path: str, output_dir: Optional[str] = None) -> Optional[str]:
    """
    Compile a LaTeX file to PDF using pdflatex
    
    Args:
        tex_file_path: Path to the .tex file
        output_dir: Directory to save the PDF (defaults to same dir as tex file)
    
    Returns:
        Path to generated PDF file, or None if compilation failed
    """
    tex_path = Path(tex_file_path)
    if not tex_path.exists():
        print(f"Error: LaTeX file not found: {tex_path}")
        return None
    
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
            return str(pdf_path)
        else:
            print(f"❌ LaTeX compilation failed:")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Error running pdflatex: {e}")
        return None

def backup_resume_files(backup_dir: str) -> bool:
    """
    Create backup of current resume files before modification
    
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
        
        for file_path in files_to_backup:
            source = Path(file_path)
            if source.exists():
                dest = backup_path / source.name
                shutil.copy2(source, dest)
                print(f"✅ Backed up: {source} -> {dest}")
            else:
                print(f"⚠️  File not found for backup: {source}")
        
        return True
        
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False

def generate_comparison_pdfs(temp_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Generate before and after PDFs for comparison
    
    Args:
        temp_dir: Temporary directory for processing
    
    Returns:
        Tuple of (before_pdf_path, after_pdf_path)
    """
    temp_path = Path(temp_dir)
    
    # Paths for before/after PDFs
    before_pdf = None
    after_pdf = None
    
    # Check if we have a backup (before) PDF
    backup_pdf = temp_path / 'Conner_Jordan_Software_Engineer.pdf'
    if backup_pdf.exists():
        before_pdf = str(backup_pdf)
        print(f"✅ Found before PDF: {before_pdf}")
    
    # Generate after PDF from current resume
    resume_tex = Path('Resume/Conner_Jordan_Software_Engineer.tex')
    if resume_tex.exists():
        after_pdf = compile_latex_to_pdf(str(resume_tex), str(temp_path / 'after'))
        if after_pdf:
            print(f"✅ Generated after PDF: {after_pdf}")
    
    return before_pdf, after_pdf

def pdf_to_base64(pdf_path: str) -> Optional[str]:
    """
    Convert PDF to base64 string for web display
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Base64 encoded PDF data, or None if failed
    """
    try:
        import base64
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
            b64_data = base64.b64encode(pdf_data).decode('utf-8')
            return b64_data
    except Exception as e:
        print(f"❌ Failed to encode PDF to base64: {e}")
        return None

if __name__ == "__main__":
    # Test PDF compilation
    test_tex = "Resume/Conner_Jordan_Software_Engineer.tex"
    if Path(test_tex).exists():
        print("Testing PDF compilation...")
        pdf_path = compile_latex_to_pdf(test_tex)
        if pdf_path:
            print(f"✅ Test successful: {pdf_path}")
        else:
            print("❌ Test failed")
    else:
        print(f"❌ Test file not found: {test_tex}")