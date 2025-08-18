# JD Parser & Resume Tailoring Pipeline

Intelligent resume tailoring using local LLMs. Automatically customize your resume for any job application while maintaining ATS optimization.

## 🔄 Pipeline Phases

### **Phase 1: JD Analysis** (`jd-parser.py`)
- **Input**: Job description text file (`jd.txt`)
- **Process**: Extract skills, map to resume categories, validate with evidence
- **Output**: `artifacts/jd_skills.json` (structured skills data)
- **Checkpoint**: ✅ Skills extracted and categorized

### **Phase 2: Skills Update** (`skills-updater.py`)
- **Input**: `artifacts/jd_skills.json`
- **Process**: Update technical skills section, prioritize job-relevant skills
- **Output**: `artifacts/skills_updated_block.tex`, updated `Resume/*.tex`
- **Checkpoint**: ✅ Skills section updated

### **Phase 3: Summary Tailoring** (`summary-updater.py`)
- **Input**: `artifacts/jd_skills.json`, current resume summary
- **Process**: Tailor professional summary to align with job requirements
- **Output**: `artifacts/summary_updated_block.tex`, updated `Resume/*.tex`
- **Checkpoint**: ✅ Summary tailored and resume complete

## 🚀 Quick Start

```bash
# Install dependencies
pip3 install -r requirements.txt

# Start LM Studio with qwen2.5-32b-instruct model
# Ensure running on http://127.0.0.1:1234/v1

# Start web interface
python3 start_server.py  # → http://localhost:8081
```

## 💻 Usage

### Web Interface (Recommended)
1. Open `http://localhost:8081`
2. **Step 1**: Paste job description → Process
3. **Step 2**: Review extracted skills → Edit summary → Approve
4. **Step 3**: Compare PDFs → Download tailored resume

### Command Line
```bash
# Complete pipeline
python3 run_jd_pipeline.py                   # Full update
python3 run_jd_pipeline.py --artifacts-only  # Safe test mode
python3 run_jd_pipeline.py --no-clean        # Debug mode

# Individual phases
python3 jd-parser.py --jd job_description.txt      # Phase 1
python3 skills-updater.py --dry-run                # Phase 2  
python3 summary-updater.py --artifacts-only        # Phase 3
```

## 📁 Project Structure

```
├── start_server.py          # Entry point with validation
├── app.py                   # Modern web interface (3-step wizard)
├── run_jd_pipeline.py       # CLI pipeline runner
│
├── jd-parser.py             # Phase 1: JD Analysis
├── skills-updater.py        # Phase 2: Skills Update
├── summary-updater.py       # Phase 3: Summary Tailoring
│
├── Resume/                  # Resume files
├── artifacts/               # Phase outputs (auto-cleaned)
├── baseline_backup/         # Original resume backup
├── templates/               # Web interface templates
└── static/                  # CSS/JS assets
```

## 🔧 Phase Checkpoints

| Phase | Success Indicator | Troubleshoot |
|-------|------------------|--------------|
| **1** | `jd_skills.json` created with extracted skills | Check LM Studio, validate JD file |
| **2** | Skills section updated, `skills_updated_block.tex` | Verify skills mapping, check LaTeX |
| **3** | Summary updated, `summary_updated_block.tex` | Check summary markers in LaTeX |

## ⚙️ Configuration

**Prerequisites:**
- Python 3.9+
- [LM Studio](https://lmstudio.ai) with `qwen2.5-32b-instruct`
- LaTeX distribution
- Resume with `TECHNICAL SKILLS` section and `% SUMMARY_BLOCK_START/END` markers

**Safety Features:**
- `--artifacts-only`: Test without modifying resume files
- `--dry-run`: Preview changes without writing
- `--no-clean`: Preserve artifacts for debugging
- Automatic backup in `baseline_backup/`

## 🎯 Status

✅ **Production Ready** - All phases working end-to-end  
🔒 **Local Only** - No external API calls  
🧹 **Clean Pipeline** - Auto-cleanup prevents data contamination  
🔧 **Debuggable** - Clear checkpoints and phase separation  

---

*Built for privacy-conscious professionals who want intelligent resume tailoring.*