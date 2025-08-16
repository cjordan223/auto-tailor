#!/usr/bin/env python3
"""
Quick server startup script for the JD Parser Web UI
"""

import subprocess
import sys
from pathlib import Path


def main():
    # Check if we're in the right directory
    if not Path('app.py').exists():
        print("❌ Error: app.py not found. Please run this from the project directory.")
        sys.exit(1)

    # Check if LM Studio might be running
    print("🔧 Pre-flight checks:")
    print("   ✅ app.py found")

    # Install dependencies if needed
    try:
        import flask
        print("   ✅ Flask is installed")
    except ImportError:
        print("   📦 Installing Flask...")
        subprocess.run([sys.executable, '-m', 'pip',
                       'install', 'flask'], check=True)
        print("   ✅ Flask installed")

    print("\n🚀 Starting JD Parser Web UI...")
    print("💡 Make sure LM Studio is running with qwen2.5-32b-instruct model")
    print("🌐 Server will be available at: http://localhost:8080")
    print("⏹️  Press Ctrl+C to stop\n")

    # Start the Flask app
    subprocess.run([sys.executable, 'app.py'])


if __name__ == '__main__':
    main()
