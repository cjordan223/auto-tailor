# JD Parser & Resume Tailoring Pipeline

Intelligent resume tailoring using local LLMs. Automatically customize your resume for any job application while maintaining ATS optimization.

## 🎯 What It Does

Transforms your generic resume into a job-specific version by:
1. **Extracting** relevant skills, responsibilities, and values from job descriptions
2. **Updating** technical skills sections with job-relevant technologies  
3. **Tailoring** professional summary to align with company values
4. **Generating** before/after comparisons with detailed change tracking

## 🏗️ Pipeline Flow

```
Job Description → Parse & Extract → Update Skills → Update Summary → Tailored Resume
     ↓                ↓                ↓              ↓               ↓
   Web UI    →   jd-parser.py  → skills-updater.py → summary-updater.py → Updated Files
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- [LM Studio](https://lmstudio.ai) with `qwen2.5-32b-instruct` model
- LaTeX resume with `TECHNICAL SKILLS` and `SUMMARY_BLOCK_START/END` sections

### Installation
```bash
# Install dependencies
pip3 install -r requirements.txt

# Start LM Studio with qwen2.5-32b-instruct model
# Ensure it's running on http://127.0.0.1:1234/v1

# Start web interface
python3 app.py
```

### Usage

#### **Web Interface (Recommended)**
1. Open `http://localhost:8081` in your browser
2. Paste job description into the text area
3. Click "Process Job Description" to extract skills
4. Click "Update Resume with Skills" to apply changes
5. View detailed changes summary and PDF comparison
6. Download tailored resume files

#### **Command Line**
```bash
# Run complete pipeline
python3 run_jd_pipeline.py --artifacts-only  # Safe test mode
python3 run_jd_pipeline.py                   # Update actual files

# Individual components
python3 jd-parser.py --jd job_description.txt
python3 skills-updater.py
python3 summary-updater.py
```

## 📁 File Structure

```
├── app.py                 # Web interface
├── jd-parser.py          # Extract skills/values from JD  
├── skills-updater.py     # Update technical skills section
├── summary-updater.py    # Tailor professional summary
├── run_jd_pipeline.py    # Command-line pipeline
├── pdf_utils.py          # LaTeX PDF compilation
├── Resume/               # Your resume files
│   └── Conner_Jordan_Software_Engineer.tex
├── artifacts/            # Generated outputs
│   ├── jd_skills.json           # Extracted data
│   ├── skills_updated_block.tex # Updated skills
│   └── summary_updated_block.tex # Updated summary
└── baseline_backup/      # Original resume backup
```

## 🎨 Web Interface Features

- **📝 Skills Extraction**: Visual display of extracted skills by category
- **📊 Change Summary**: Detailed breakdown of what was added/removed/skipped
- **📄 PDF Comparison**: Side-by-side before/after resume comparison
- **✏️ Summary Changes**: Expandable before/after summary comparison
- **📦 File Download**: ZIP with all updated files and artifacts
- **🔄 Baseline Management**: Reset comparison baseline when needed

## ⚙️ Configuration

### **LLM Settings**
- **Model**: `qwen2.5-32b-instruct` (recommended)
- **Temperature**: 0.0 (skills) / 0.7 (summary)
- **Timeout**: 30 minutes
- **API**: Local LM Studio only

### **Skill Categories**
- Programming Languages
- Frontend
- Backend  
- Cloud & DevOps
- AI & LLM Tools
- Automation & Productivity
- Security & Operating Systems
- Databases

## 🔧 Safety Features

- **Artifacts-only mode**: Test changes without modifying files
- **Baseline backup**: Permanent copy of original resume
- **Evidence validation**: Every skill must appear in job description
- **Change tracking**: Detailed logs of all modifications
- **LaTeX preservation**: Maintains formatting and structure

## 🧪 Testing

```bash
# Web interface
python3 app.py  # Open http://localhost:8081

# Command line pipeline
python3 run_jd_pipeline.py --artifacts-only --dry-run

# Individual components
python3 jd-parser.py --jd test_jd.txt
python3 skills-updater.py --dry-run
python3 summary-updater.py --dry-run
```

## 🔍 Troubleshooting

**LM Studio Issues**
- Ensure qwen2.5-32b-instruct model is loaded
- Check http://127.0.0.1:1234/v1 is accessible
- Verify model is running (not just loaded)

**LaTeX Compilation**
- Install LaTeX distribution (e.g., TexLive, MiKTeX)
- Check `pdflatex` command is available
- Ensure resume has required section markers

**Permission Errors**  
- Check file/directory write permissions
- Ensure `artifacts/` directory is writable
- Run from project root directory

## 📊 Example Output

**Skills Added**: Python, Kubernetes, API Security  
**Skills Removed**: Outdated technologies to make room  
**Skills Skipped**: Already present or irrelevant to section  
**Summary Updated**: Tailored to emphasize cloud security experience

## 🎯 Status

✅ **Fully Functional** - Complete 3-phase pipeline with web interface  
🔒 **Local Only** - No external API calls or data sharing  
📱 **Production Ready** - Comprehensive error handling and validation

---

*Built for privacy-conscious professionals who want intelligent resume tailoring without compromising their data.*