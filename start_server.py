#!/usr/bin/env python3
"""
Startup script for JD Parser & Resume Tailoring Pipeline

This script provides an easy way to start the web interface with proper
error checking and setup validation.
"""

import sys
import subprocess
from pathlib import Path


def check_dependencies():
    """Check if all required dependencies are available."""
    print("🔍 Checking dependencies...")
    
    # Check Python version
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ required")
        return False
    
    # Check required files
    required_files = [
        'app.py',
        'pipeline_handlers.py',
        'jd-parser.py',
        'skills-updater.py',
        'summary-updater.py',
        'pdf_utils.py',
        'requirements.txt'
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing required files: {', '.join(missing_files)}")
        return False
    
    # Check if LaTeX is available
    try:
        result = subprocess.run(['pdflatex', '--version'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("⚠️  LaTeX (pdflatex) not found - PDF generation will fail")
        else:
            print("✅ LaTeX found")
    except FileNotFoundError:
        print("⚠️  LaTeX (pdflatex) not found - PDF generation will fail")
    
    # Check if LM Studio is running
    try:
        import requests
        response = requests.get('http://127.0.0.1:1234/v1/models', timeout=5)
        if response.status_code == 200:
            print("✅ LM Studio API accessible")
        else:
            print("⚠️  LM Studio API not responding correctly")
    except Exception:
        print("⚠️  LM Studio not running - start LM Studio with qwen2.5-32b-instruct model")
    
    print("✅ Dependency check completed")
    return True


def create_directories():
    """Create necessary directories if they don't exist."""
    print("📁 Creating directories...")
    
    directories = ['artifacts', 'baseline_backup']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created directory: {directory}")


def main():
    """Main startup function."""
    print("🚀 Starting JD Parser & Resume Tailoring Pipeline")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        print("\n❌ Dependency check failed. Please fix the issues above.")
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    print("\n🎯 Starting web interface...")
    print("📱 Open http://localhost:8081 in your browser")
    print("🛑 Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        # Import and run the Flask app
        from app import app
        app.run(host='0.0.0.0', port=8081, debug=True)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
