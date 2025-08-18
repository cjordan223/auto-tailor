// JD Parser & Resume Tailoring - JavaScript functionality

class ResumeWizard {
    constructor() {
        this.currentStep = 1;
        this.extractedSkills = null;
        this.selectedSkills = new Set();
        this.processingResults = null;
        this.downloadId = null;
        
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        // Form submission
        document.getElementById('jdForm').addEventListener('submit', (e) => this.handleJobDescriptionSubmit(e));
        
        // Initialize other event listeners as needed
        this.setupUtilityButtons();
    }

    setupUtilityButtons() {
        // Clear form button
        window.clearForm = () => {
            document.getElementById('jobDescription').value = '';
            this.hideStatus();
            this.goToStep(1);
            this.extractedSkills = null;
            this.selectedSkills.clear();
            this.processingResults = null;
            this.downloadId = null;
        };

        // Reset baseline button  
        window.resetBaseline = () => this.handleResetBaseline();
        
        // Navigation functions
        window.goToStep = (step) => this.goToStep(step);
        window.generateFinalResume = () => this.handleGenerateFinalResume();
        window.startOver = () => {
            window.clearForm();
        };
    }

    async handleJobDescriptionSubmit(e) {
        e.preventDefault();
        
        const jobDescription = document.getElementById('jobDescription').value.trim();
        if (!jobDescription) {
            this.showStatus('Please enter a job description.', 'error');
            return;
        }

        const processBtn = document.getElementById('processBtn');
        processBtn.disabled = true;
        processBtn.innerHTML = '<span class="spinner"></span>Processing...';
        
        // Try async processing first, fall back to sync if needed
        const useAsync = true; // Could be a user preference
        
        if (useAsync) {
            await this.handleAsyncProcessing(jobDescription, processBtn);
        } else {
            await this.handleSyncProcessing(jobDescription, processBtn);
        }
    }

    async handleAsyncProcessing(jobDescription, processBtn) {
        this.showStatus('🚀 Starting background processing...', 'info');

        try {
            // Submit for async processing
            const response = await fetch('/process-jd-async', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ job_description: jobDescription })
            });

            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    this.showStatus('⏳ Processing in background... Please wait', 'info');
                    
                    // Start polling for task completion
                    await this.pollTaskStatus(result.task_id, processBtn);
                } else {
                    this.showStatus(`❌ Error: ${result.error}`, 'error');
                    this.resetProcessButton(processBtn);
                }
            } else {
                // Fall back to sync processing
                this.showStatus('⚠️ Async processing unavailable, using standard processing...', 'warning');
                await this.handleSyncProcessing(jobDescription, processBtn);
            }
        } catch (error) {
            this.showStatus(`❌ Network error: ${error.message}`, 'error');
            this.resetProcessButton(processBtn);
        }
    }

    async handleSyncProcessing(jobDescription, processBtn) {
        this.showStatus('Processing job description and extracting skills...', 'info');

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
                    await this.handleProcessingSuccess(result);
                } else {
                    this.showStatus(`❌ Error: ${result.error}`, 'error');
                }
            } else {
                const error = await response.json();
                this.showStatus(`❌ Error: ${error.error || 'Processing failed'}`, 'error');
            }
        } catch (error) {
            this.showStatus(`❌ Network error: ${error.message}`, 'error');
        } finally {
            this.resetProcessButton(processBtn);
        }
    }

    async pollTaskStatus(taskId, processBtn) {
        const maxAttempts = 120; // 10 minutes with 5-second intervals
        let attempts = 0;
        
        const checkStatus = async () => {
            try {
                const response = await fetch(`/task-status/${taskId}`);
                if (response.ok) {
                    const result = await response.json();
                    
                    if (result.success) {
                        const status = result.status;
                        const progress = result.progress || 0;
                        
                        // Update UI based on status
                        if (status === 'running') {
                            processBtn.innerHTML = `<span class="spinner"></span>Processing... ${Math.round(progress)}%`;
                            this.showStatus(`⚙️ Processing: ${Math.round(progress)}% complete`, 'info');
                        } else if (status === 'completed') {
                            // Task completed successfully
                            const skills = result.skills || result.result;
                            const skillsCount = result.skills_count || (skills ? skills.skills_flat?.length || 0 : 0);
                            
                            await this.handleProcessingSuccess({
                                success: true,
                                skills_count: skillsCount,
                                skills: skills,
                                download_id: `async_${taskId}` // Create a pseudo download ID
                            });
                            this.resetProcessButton(processBtn);
                            return;
                        } else if (status === 'failed') {
                            this.showStatus(`❌ Processing failed: ${result.error || 'Unknown error'}`, 'error');
                            this.resetProcessButton(processBtn);
                            return;
                        } else if (status === 'pending') {
                            processBtn.innerHTML = '<span class="spinner"></span>Queued...';
                            this.showStatus('📋 Task queued for processing...', 'info');
                        }
                        
                        // Continue polling if still processing
                        attempts++;
                        if (attempts < maxAttempts) {
                            setTimeout(checkStatus, 5000); // Check every 5 seconds
                        } else {
                            this.showStatus('❌ Processing timed out. Please try again.', 'error');
                            this.resetProcessButton(processBtn);
                        }
                    } else {
                        this.showStatus(`❌ Error checking status: ${result.error}`, 'error');
                        this.resetProcessButton(processBtn);
                    }
                } else {
                    throw new Error(`HTTP ${response.status}`);
                }
            } catch (error) {
                console.error('Error polling task status:', error);
                attempts++;
                if (attempts < maxAttempts) {
                    setTimeout(checkStatus, 5000);
                } else {
                    this.showStatus('❌ Lost connection to server. Please refresh and try again.', 'error');
                    this.resetProcessButton(processBtn);
                }
            }
        };
        
        // Start polling immediately
        setTimeout(checkStatus, 1000);
    }

    async handleProcessingSuccess(result) {
        this.showStatus(`✅ Success! Extracted ${result.skills_count} relevant skills.`, 'success');
        
        // Store results
        this.processingResults = result;
        this.extractedSkills = result.skills;
        
        // Display extracted skills and move to step 2
        this.displaySkillsForReview(result.skills);
        await this.generateProfessionalSummary();
        this.goToStep(2);
    }

    resetProcessButton(processBtn) {
        processBtn.disabled = false;
        processBtn.innerHTML = '<i class="bi bi-gear"></i> Process Job Description';
    }

    displaySkillsForReview(skills) {
        const container = document.getElementById('skillsContainer');
        let html = '';
        
        // Initialize selected skills set with all skills selected by default
        this.selectedSkills.clear();
        
        if (skills.by_section_top3) {
            for (const [category, skillList] of Object.entries(skills.by_section_top3)) {
                if (skillList && skillList.length > 0) {
                    html += this.createSkillCategoryHTML(category, skillList);
                    skillList.forEach(skill => this.selectedSkills.add(skill));
                }
            }
        } else if (skills.categorized) {
            for (const [category, skillList] of Object.entries(skills.categorized)) {
                if (skillList && skillList.length > 0) {
                    html += this.createSkillCategoryHTML(category, skillList);
                    skillList.forEach(skill => this.selectedSkills.add(skill));
                }
            }
        } else if (skills.skills_flat || skills.flat || Array.isArray(skills)) {
            const skillList = skills.skills_flat || skills.flat || skills;
            html += this.createSkillCategoryHTML('Extracted Skills', skillList);
            skillList.forEach(skill => this.selectedSkills.add(skill));
        }
        
        container.innerHTML = html;
        this.attachSkillEventListeners();
    }

    createSkillCategoryHTML(category, skillList) {
        let html = `
            <div class="col-12 mb-3">
                <div class="skill-category">
                    <h6 class="skill-category-header">
                        <i class="bi bi-folder"></i> ${category}
                    </h6>
                    <div class="skill-category-body">
                        <div class="row">
        `;
        
        skillList.forEach(skill => {
            const skillId = `skill-${this.sanitizeId(skill)}`;
            html += `
                <div class="col-md-6 col-lg-4 mb-2">
                    <div class="skill-card selected" data-skill="${skill}">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" value="${skill}" id="${skillId}" checked>
                            <label class="form-check-label" for="${skillId}">
                                ${skill}
                            </label>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += `
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        return html;
    }

    attachSkillEventListeners() {
        const skillCards = document.querySelectorAll('.skill-card');
        skillCards.forEach(card => {
            const checkbox = card.querySelector('input[type="checkbox"]');
            const skill = card.dataset.skill;
            
            const toggleSkill = () => {
                if (checkbox.checked) {
                    this.selectedSkills.add(skill);
                    card.classList.add('selected');
                } else {
                    this.selectedSkills.delete(skill);
                    card.classList.remove('selected');
                }
            };
            
            card.addEventListener('click', (e) => {
                if (e.target.type !== 'checkbox') {
                    checkbox.checked = !checkbox.checked;
                }
                toggleSkill();
            });
            
            checkbox.addEventListener('change', toggleSkill);
        });
    }

    async generateProfessionalSummary() {
        const summaryTextarea = document.getElementById('professionalSummary');
        
        // Show loading state
        summaryTextarea.value = "Generating professional summary...";
        summaryTextarea.disabled = true;
        
        try {
            const response = await fetch('/generate-summary', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    summaryTextarea.value = result.summary;
                } else {
                    summaryTextarea.value = "Failed to generate summary. You can write your own summary here.";
                    console.error('Summary generation failed:', result.error);
                }
            } else {
                summaryTextarea.value = "Failed to generate summary. You can write your own summary here.";
                console.error('Network error:', response.status);
            }
        } catch (error) {
            summaryTextarea.value = "Failed to generate summary. You can write your own summary here.";
            console.error('Error generating summary:', error);
        } finally {
            summaryTextarea.disabled = false;
        }
    }

    async handleGenerateFinalResume() {
        const generateBtn = document.getElementById('generateResumeBtn');
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<span class="spinner"></span>Generating Resume...';
        
        this.showStatus('Updating resume with selected skills and summary...', 'info');

        try {
            // Prepare data for the resume update
            const selectedSkillsArray = Array.from(this.selectedSkills);
            const professionalSummary = document.getElementById('professionalSummary').value;
            
            const response = await fetch('/update-resume', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    selected_skills: selectedSkillsArray,
                    professional_summary: professionalSummary
                })
            });

            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    this.showStatus(`✅ Resume updated successfully!`, 'success');
                    
                    // Store download ID
                    this.downloadId = result.download_id;
                    
                    // Show changes summary if available
                    if (result.changes) {
                        this.showChangesSummary(result.changes);
                    }
                    
                    // Show PDF comparison if available
                    if (result.before_pdf && result.after_pdf) {
                        this.showPDFComparison(result.before_pdf, result.after_pdf);
                    }
                    
                    // Enable download button
                    const downloadBtn = document.getElementById('downloadBtn');
                    downloadBtn.disabled = false;
                    downloadBtn.onclick = () => window.open(`/download/${this.downloadId}`, '_blank');
                    
                    // Move to step 3
                    this.goToStep(3);
                } else {
                    this.showStatus(`❌ Error: ${result.error}`, 'error');
                }
            } else {
                const error = await response.json();
                this.showStatus(`❌ Error: ${error.error || 'Resume update failed'}`, 'error');
            }
        } catch (error) {
            this.showStatus(`❌ Network error: ${error.message}`, 'error');
        } finally {
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<i class="bi bi-file-earmark-check"></i> Generate Final Resume';
        }
    }

    showChangesSummary(changes) {
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
            html += `
                <div class="card mb-3">
                    <div class="card-header bg-light">
                        <h6 class="card-title mb-0"><i class="bi bi-folder"></i> ${sectionName}</h6>
                    </div>
                    <div class="card-body">
            `;
            
            // Added skills
            sectionChanges.added.forEach(change => {
                html += `
                    <div class="change-item added">
                        <span class="change-icon added">+</span>
                        <span class="skill-name">${change.skill}</span>
                        <span class="skill-reason">${change.reason || 'Added from job requirements'}</span>
                    </div>
                `;
            });
            
            // Removed skills
            sectionChanges.removed.forEach(change => {
                html += `
                    <div class="change-item removed">
                        <span class="change-icon removed">−</span>
                        <span class="skill-name">${change.skill}</span>
                        <span class="skill-reason">${change.reason || 'Removed to make room for job-relevant skills'}</span>
                    </div>
                `;
            });
            
            // Skipped skills
            sectionChanges.skipped.forEach(change => {
                html += `
                    <div class="change-item skipped">
                        <span class="change-icon skipped">⚠</span>
                        <span class="skill-name">${change.skill}</span>
                        <span class="skill-reason">${change.reason || 'Skipped - reason not specified'}</span>
                    </div>
                `;
            });
            
            // Summary changes (special handling)
            if (sectionChanges.summary_change) {
                const summaryChange = sectionChanges.summary_change;
                html += `
                    <div class="change-item added">
                        <span class="change-icon added">✏️</span>
                        <span class="skill-name">Professional Summary</span>
                        <span class="skill-reason">${summaryChange.reason}</span>
                    </div>
                `;
                
                // Add expandable before/after comparison
                html += `
                    <div class="mt-3">
                        <div class="accordion">
                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#summaryChanges">
                                        View Summary Changes
                                    </button>
                                </h2>
                                <div id="summaryChanges" class="accordion-collapse collapse">
                                    <div class="accordion-body">
                                        <div class="mb-3">
                                            <strong>Before:</strong>
                                            <div class="bg-light p-3 rounded mt-2">
                                                ${summaryChange.original}
                                            </div>
                                        </div>
                                        <div>
                                            <strong>After:</strong>
                                            <div class="bg-light p-3 rounded mt-2">
                                                ${summaryChange.revised}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            html += `</div></div>`;
        }
        
        if (!html) {
            html = '<div class="alert alert-info">No specific changes detected. Skills may have been reorganized or optimized.</div>';
        }
        
        contentDiv.innerHTML = html;
        summaryDiv.classList.remove('d-none');
    }

    showPDFComparison(beforePDF, afterPDF) {
        const comparisonDiv = document.getElementById('pdfComparison');
        const beforeEmbed = document.getElementById('beforePDF');
        const afterEmbed = document.getElementById('afterPDF');
        
        beforeEmbed.src = `data:application/pdf;base64,${beforePDF}`;
        afterEmbed.src = `data:application/pdf;base64,${afterPDF}`;
        
        comparisonDiv.classList.remove('d-none');
    }

    async handleResetBaseline() {
        if (!confirm('Are you sure you want to reset the baseline? This will set the current resume as the new "before" state for all future comparisons.')) {
            return;
        }

        try {
            this.showStatus('Resetting baseline backup...', 'info');
            
            const response = await fetch('/reset-baseline', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    this.showStatus('✅ Baseline reset successfully! The current resume is now the new baseline.', 'success');
                } else {
                    this.showStatus(`❌ Error: ${result.error}`, 'error');
                }
            } else {
                const error = await response.json();
                this.showStatus(`❌ Error: ${error.error || 'Failed to reset baseline'}`, 'error');
            }
        } catch (error) {
            this.showStatus(`❌ Network error: ${error.message}`, 'error');
        }
    }

    goToStep(step) {
        // Hide all steps
        for (let i = 1; i <= 3; i++) {
            document.getElementById(`step-${i}`).classList.add('d-none');
            document.getElementById(`step-indicator-${i}`).classList.remove('active', 'completed');
        }
        
        // Show current step
        document.getElementById(`step-${step}`).classList.remove('d-none');
        document.getElementById(`step-indicator-${step}`).classList.add('active');
        
        // Mark previous steps as completed
        for (let i = 1; i < step; i++) {
            document.getElementById(`step-indicator-${i}`).classList.add('completed');
        }
        
        this.currentStep = step;
        
        // Add fade-in animation
        document.getElementById(`step-${step}`).classList.add('fade-in');
        setTimeout(() => {
            document.getElementById(`step-${step}`).classList.remove('fade-in');
        }, 300);
    }

    showStatus(message, type) {
        const statusDiv = document.getElementById('status');
        statusDiv.innerHTML = `
            <div class="alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        statusDiv.classList.remove('d-none');
        
        // Auto-hide success and info messages after 5 seconds
        if (type === 'success' || type === 'info') {
            setTimeout(() => {
                const alert = statusDiv.querySelector('.alert');
                if (alert) {
                    const bsAlert = new bootstrap.Alert(alert);
                    bsAlert.close();
                }
            }, 5000);
        }
    }

    hideStatus() {
        const statusDiv = document.getElementById('status');
        statusDiv.classList.add('d-none');
    }

    sanitizeId(str) {
        return str.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase();
    }
}

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new ResumeWizard();
});