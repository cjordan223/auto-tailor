# JD Parser & Resume Tailoring Pipeline

An intelligent pipeline for extracting job-relevant skills from job descriptions and automatically tailoring resume skills sections for ATS optimization.

## 🎯 **Project Overview**

This project automates the tedious process of customizing resumes for specific job applications by:

1. **Extracting relevant skills** from job descriptions using LLMs
2. **Validating and deduplicating** extracted skills against the original JD
3. **Updating resume skills sections** to align with job requirements
4. **Maintaining resume integrity** while optimizing for ATS systems

## 🏗️ **Architecture**

```
Job Description → Skill Extraction → Validation → Resume Update → Tailored Resume
     ↓                ↓              ↓            ↓              ↓
   jd.txt    →   jd-parser.py  →  Post-process → skills-updater.py → Updated Resume
```

### **Core Components**

- **`jd-parser.py`** - Main JD parser that extracts skills and writes to artifacts
- **`skills-updater.py`** - Resume skills section updater
- **`run_jd_pipeline.py`** - Complete pipeline automation script
- **`test_shuffle.py`** - Test utilities

## 🚀 **Quick Start**

### Prerequisites
- Python 3.9+
- LM Studio running with `qwen2.5-32b-instruct` model
- Job description in `jd.txt`
- Resume skills section in `skills.tex`

### Installation
```bash
# Clone or download the project
cd /path/to/project

# Install dependencies
pip3 install -r requirements.txt

# Start LM Studio with qwen2.5-32b-instruct model
# Make sure it's running on http://127.0.0.1:1234/v1
```

### Basic Usage

#### **Option 1: Run Complete Pipeline (Recommended)**
```bash
# Run the complete pipeline in artifacts-only mode (safe for testing)
python3 run_jd_pipeline.py --artifacts-only

# Run the complete pipeline to update your actual resume files
python3 run_jd_pipeline.py

# Run with custom JD file
python3 run_jd_pipeline.py --jd my_job_description.txt --artifacts-only
```

#### **Option 2: Run Individual Components**
```bash
# Step 1: Extract skills from job description
python3 jd-parser.py --jd jd.txt

# Step 2: Update resume skills (when ready)
python3 skills-updater.py --artifacts-only  # Test mode
python3 skills-updater.py                   # Update actual files
```

#### **Option 3: Custom Configuration**
```bash
# Use different model or API settings
python3 run_jd_pipeline.py \
  --model "qwen2.5-32b-instruct" \
  --base-url "http://127.0.0.1:1234/v1" \
  --api-key "lm-studio" \
  --artifacts-only
```

## 📊 **Current Implementation Status**

### ✅ **Working Features**

#### **Skill Extraction (`jd-parser.py`)**
- **LLM Integration**: Uses LM Studio with qwen2.5-32b-instruct model
- **Robust JSON parsing**: Handles escape sequence issues and malformed JSON
- **Evidence-based validation**: Every skill must appear verbatim in the JD
- **Anti-repetition**: Deduplication and validation
- **Extended timeout**: 30-minute timeout for large models
- **Configurable output**: Adjustable skill count with `--cap` parameter
- **Fallback mechanism**: Uses existing output if LLM call fails
- **Artifacts output**: Writes to `artifacts/jd_skills.json`

#### **Resume Skills Updater (`skills-updater.py`)**
- **LaTeX processing**: Updates resume skills sections while preserving formatting
- **Intelligent integration**: Adds relevant skills without removing important existing ones
- **Safety modes**: `--artifacts-only` and `--dry-run` for testing
- **LaTeX escaping**: Properly handles special characters and formatting
- **Section mapping**: Correctly maps skills to appropriate resume sections

#### **Pipeline Automation (`run_jd_pipeline.py`)**
- **Complete workflow**: Runs both extraction and update in sequence
- **Error handling**: Stops pipeline if any step fails
- **Progress tracking**: Shows timing and status for each step
- **Flexible configuration**: Supports all command-line options

### 🔧 **Configuration**

#### **Model Settings**
- **Temperature**: 0.0 (deterministic)
- **Top_p**: 0.9
- **Seed**: 42 (reproducible)
- **Max tokens**: 4096 (extended for comprehensive responses)
- **Timeout**: 1800s (30 minutes)
- **Streaming**: False (simplified approach to avoid parsing issues)

#### **Skill Categories**
1. Programming Languages
2. Frontend
3. Backend
4. Cloud & DevOps
5. AI & LLM Tools
6. Automation & Productivity
7. Security & Operating Systems
8. Databases

## 📁 **File Structure**
```
Sandbox/
├── jd-parser.py              # Main JD parser
├── skills-updater.py         # Resume skills updater
├── run_jd_pipeline.py        # Complete pipeline automation
├── test_shuffle.py           # Test utilities
├── requirements.txt          # Dependencies
├── jd.txt                    # Job description input
├── skills.tex               # Resume skills section
├── Resume/                   # Resume files
│   └── Conner_Jordan_Software_Engineer.tex
├── artifacts/               # Generated outputs
│   ├── jd_skills.json       # Extracted skills from JD
│   ├── skills_editor_output.json  # LLM editor response
│   └── skills_updated_block.tex   # Updated LaTeX skills block
└── README.md                # This file
```

## 🎯 **Usage Examples**

### **Example 1: Test the Pipeline**
```bash
# Run in safe mode to see what would be generated
python3 run_jd_pipeline.py --artifacts-only

# Check the generated artifacts
ls -la artifacts/
cat artifacts/jd_skills.json
cat artifacts/skills_updated_block.tex
```

### **Example 2: Update Your Resume**
```bash
# Run the complete pipeline to update your actual resume
python3 run_jd_pipeline.py

# This will:
# 1. Extract skills from jd.txt
# 2. Update skills.tex with relevant skills
# 3. Update your main resume file
# 4. Create backup copies in artifacts/
```

### **Example 3: Custom Job Description**
```bash
# Use a different job description file
python3 run_jd_pipeline.py --jd my_custom_jd.txt --artifacts-only

# Use different model settings
python3 run_jd_pipeline.py \
  --model "llama3.1-8b-instruct" \
  --base-url "http://127.0.0.1:1234/v1" \
  --artifacts-only
```

## 🔧 **Recent Fixes & Improvements**

### **Critical Issues Resolved** ✅
1. **Missing File Output**: Fixed `jd-parser.py` to properly write to `artifacts/jd_skills.json`
2. **Section Name Mismatch**: Corrected section names to match actual LaTeX formatting
3. **LaTeX Escaping**: Fixed double backslash issues in generated LaTeX output
4. **Pipeline Flow**: Ensured proper data flow between all components

### **Current Features**
- ✅ Complete pipeline automation
- ✅ Evidence-based skill validation
- ✅ LaTeX formatting preservation
- ✅ Safety modes for testing
- ✅ Comprehensive error handling
- ✅ Configurable skill extraction
- ✅ Proper artifacts generation

## 🧪 **Testing**

### **Quick Test**
```bash
# Test the complete pipeline
python3 run_jd_pipeline.py --artifacts-only

# Verify artifacts were created
ls -la artifacts/
```

### **Individual Component Tests**
```bash
# Test JD parser
python3 jd-parser.py --jd jd.txt

# Test skills updater
python3 skills-updater.py --artifacts-only
```

## 🔧 **Troubleshooting**

### **Common Issues**

#### **LM Studio Not Running**
```bash
# Error: Connection refused
# Solution: Start LM Studio and load qwen2.5-32b-instruct model
```

#### **Model Not Found**
```bash
# Error: Model not found
# Solution: Make sure qwen2.5-32b-instruct is loaded in LM Studio
```

#### **Permission Errors**
```bash
# Error: Permission denied
# Solution: Check file permissions and ensure artifacts/ directory is writable
```

#### **JSON Parsing Errors**
```bash
# Error: Invalid JSON
# Solution: Check llm_output.txt for raw model response
# The parser has fallback mechanisms for malformed JSON
```

### **Performance Tips**
- Use `--artifacts-only` mode for testing before updating actual files
- The pipeline takes 2-3 minutes to complete (mostly LLM processing time)
- Large models may take longer; the 30-minute timeout should be sufficient

## 📈 **Output Examples**

### **Generated Skills JSON**
```json
{
  "job_skills_ranked": [
    {
      "token": "python",
      "canonical": "Python",
      "section": "Programming Languages",
      "confidence": 0.95,
      "evidence": ["Strong experience in either Python or JavaScript"],
      "aliases": []
    }
  ],
  "by_section_top3": {
    "Programming Languages": ["Python", "JavaScript", "C/C++"],
    "Cloud & DevOps": ["Kubernetes", "AWS"]
  },
  "skills_flat": ["Python", "JavaScript", "ReactJS", "C/C++", "Java"]
}
```

### **Updated LaTeX Skills Block**
```latex
\textbf{Programming Languages:} Python, TypeScript, Java, C/C++, SQL, Swift, PowerShell, Bash
\vspace{3pt}
\textbf{Frontend:} React.js, Vue.js, Tailwind CSS, MUI, Vite, Next.js
\vspace{3pt}
\textbf{Cloud \& DevOps:} AWS, Google Cloud Platform, Azure, Docker, Kubernetes, Lambda, Ansible, Terraform, CI/CD (GitHub Actions, Jenkins)
```

## 🤝 **Contributing**

### **Development Setup**
1. Clone repository
2. Install dependencies: `pip3 install -r requirements.txt`
3. Start LM Studio with qwen2.5-32b-instruct model
4. Run tests: `python3 run_jd_pipeline.py --artifacts-only`

### **Code Style**
- Follow PEP 8
- Add type hints
- Include docstrings
- Write tests for new features

## 📄 **License**

This project is for educational and personal use. Please respect the terms of service for any LLM APIs used.

## 🙏 **Acknowledgments**

- **LM Studio** for local LLM hosting
- **Qwen 2.5 32B** for high-quality skill extraction
- **OpenAI-compatible API** for standardization

---

**Status**: ✅ **FULLY FUNCTIONAL** - All critical issues resolved, pipeline working end-to-end

*Last updated: January 2025*
