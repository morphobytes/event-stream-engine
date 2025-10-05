// Event Stream Engine - Frontend JavaScript
class EventStreamApp {
    constructor() {
        this.apiBase = '/api/v1';
        this.init();
    }

    init() {
        // Initialize file upload handlers
        this.initFileUpload();
        
        // Initialize auto-refresh for monitoring
        this.initAutoRefresh();
        
        // Initialize form handlers
        this.initFormHandlers();
    }

    // File upload with drag and drop
    initFileUpload() {
        const fileUpload = document.querySelector('.file-upload');
        const fileInput = document.querySelector('#file-input');
        
        if (fileUpload && fileInput) {
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                fileUpload.addEventListener(eventName, this.preventDefaults);
            });

            ['dragenter', 'dragover'].forEach(eventName => {
                fileUpload.addEventListener(eventName, () => fileUpload.classList.add('drag-over'));
            });

            ['dragleave', 'drop'].forEach(eventName => {
                fileUpload.addEventListener(eventName, () => fileUpload.classList.remove('drag-over'));
            });

            fileUpload.addEventListener('drop', (e) => {
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    fileInput.files = files;
                    this.handleFileSelect(files[0]);
                }
            });

            fileUpload.addEventListener('click', () => fileInput.click());
            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    this.handleFileSelect(e.target.files[0]);
                }
            });
        }
    }

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    handleFileSelect(file) {
        const fileInfo = document.querySelector('.file-info');
        if (fileInfo) {
            fileInfo.innerHTML = `
                <p><strong>Selected:</strong> ${file.name}</p>
                <p><strong>Size:</strong> ${this.formatFileSize(file.size)}</p>
                <p><strong>Type:</strong> ${file.type || 'Unknown'}</p>
            `;
        }
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Auto-refresh for monitoring pages
    initAutoRefresh() {
        const autoRefreshElements = document.querySelectorAll('[data-auto-refresh]');
        autoRefreshElements.forEach(element => {
            const interval = parseInt(element.dataset.autoRefresh) * 1000;
            if (interval > 0) {
                setInterval(() => {
                    this.refreshElement(element);
                }, interval);
            }
        });
    }

    async refreshElement(element) {
        const url = element.dataset.refreshUrl;
        if (!url) return;

        try {
            const response = await fetch(url);
            const data = await response.json();
            
            if (element.classList.contains('stats-grid')) {
                this.updateStatsGrid(element, data);
            } else if (element.classList.contains('table')) {
                this.updateTable(element, data);
            }
        } catch (error) {
            console.error('Refresh failed:', error);
        }
    }

    updateStatsGrid(container, data) {
        const stats = container.querySelectorAll('.stat-number');
        stats.forEach(stat => {
            const key = stat.dataset.key;
            if (data[key] !== undefined) {
                this.animateNumber(stat, data[key]);
            }
        });
    }

    animateNumber(element, newValue) {
        const currentValue = parseInt(element.textContent) || 0;
        const increment = (newValue - currentValue) / 20;
        let current = currentValue;
        
        const timer = setInterval(() => {
            current += increment;
            if ((increment > 0 && current >= newValue) || (increment < 0 && current <= newValue)) {
                element.textContent = newValue;
                clearInterval(timer);
            } else {
                element.textContent = Math.floor(current);
            }
        }, 50);
    }

    // Form handlers
    initFormHandlers() {
        // Campaign trigger buttons
        document.querySelectorAll('.btn-trigger-campaign').forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const campaignId = button.dataset.campaignId;
                this.triggerCampaign(campaignId, button);
            });
        });

        // Bulk upload forms
        const bulkUploadForm = document.querySelector('#bulk-upload-form');
        if (bulkUploadForm) {
            bulkUploadForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleBulkUpload(bulkUploadForm);
            });
        }

        // Campaign creation forms
        const campaignForm = document.querySelector('#campaign-form');
        if (campaignForm) {
            campaignForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleCampaignSubmit(campaignForm);
            });
        }
    }

    async triggerCampaign(campaignId, button) {
        const originalText = button.textContent;
        button.textContent = 'Triggering...';
        button.disabled = true;

        try {
            const response = await fetch(`${this.apiBase}/campaigns/${campaignId}/trigger`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showAlert('Campaign triggered successfully!', 'success');
                // Update UI to show task ID
                const taskInfo = document.querySelector(`#task-info-${campaignId}`);
                if (taskInfo) {
                    taskInfo.innerHTML = `
                        <p><strong>Task ID:</strong> ${data.task_id}</p>
                        <p><strong>Status:</strong> ${data.status}</p>
                    `;
                }
            } else {
                this.showAlert(`Error: ${data.message}`, 'error');
            }
        } catch (error) {
            this.showAlert(`Network error: ${error.message}`, 'error');
        } finally {
            button.textContent = originalText;
            button.disabled = false;
        }
    }

    async handleBulkUpload(form) {
        const formData = new FormData(form);
        const submitButton = form.querySelector('button[type="submit"]');
        const progressBar = form.querySelector('.progress-bar-fill');
        
        submitButton.textContent = 'Uploading...';
        submitButton.disabled = true;

        try {
            const response = await fetch(`${this.apiBase}/users/bulk`, {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showAlert(`Upload successful! Processed ${data.total_processed} users`, 'success');
                form.reset();
                document.querySelector('.file-info').innerHTML = '';
            } else {
                this.showAlert(`Upload failed: ${data.message}`, 'error');
            }
        } catch (error) {
            this.showAlert(`Network error: ${error.message}`, 'error');
        } finally {
            submitButton.textContent = 'Upload Users';
            submitButton.disabled = false;
            if (progressBar) {
                progressBar.style.width = '0%';
            }
        }
    }

    async handleCampaignSubmit(form) {
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);
        const submitButton = form.querySelector('button[type="submit"]');
        
        submitButton.textContent = 'Creating...';
        submitButton.disabled = true;

        try {
            const response = await fetch(`${this.apiBase}/campaigns`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.showAlert('Campaign created successfully!', 'success');
                // Redirect to campaigns page or update UI
                window.location.href = '/campaigns';
            } else {
                this.showAlert(`Error: ${result.message}`, 'error');
            }
        } catch (error) {
            this.showAlert(`Network error: ${error.message}`, 'error');
        } finally {
            submitButton.textContent = 'Create Campaign';
            submitButton.disabled = false;
        }
    }

    showAlert(message, type = 'info') {
        const alertsContainer = document.querySelector('.alerts-container') || document.querySelector('.container');
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.textContent = message;
        
        alertsContainer.insertBefore(alert, alertsContainer.firstChild);
        
        setTimeout(() => {
            alert.remove();
        }, 5000);
    }

    // Utility functions
    async apiRequest(endpoint, options = {}) {
        const url = `${this.apiBase}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    formatDateTime(dateString) {
        return new Date(dateString).toLocaleString();
    }

    formatPhoneNumber(phone) {
        // Simple E.164 formatting
        return phone.replace(/(\+\d{1,3})(\d{3})(\d{3})(\d{4})/, '$1 $2-$3-$4');
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new EventStreamApp();
});

// Utility functions available globally
window.utils = {
    formatDateTime: (dateString) => new Date(dateString).toLocaleString(),
    formatPhoneNumber: (phone) => phone.replace(/(\+\d{1,3})(\d{3})(\d{3})(\d{4})/, '$1 $2-$3-$4'),
    copyToClipboard: (text) => {
        navigator.clipboard.writeText(text).then(() => {
            window.app.showAlert('Copied to clipboard!', 'success');
        });
    }
};