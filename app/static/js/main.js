/**
 * MedMatchINT - Main JavaScript
 * Handles all client-side functionality for the clinical trial matching application
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const textInput = document.getElementById('text-input');
    const clearButton = document.getElementById('clear-button');
    const processButton = document.getElementById('process-button');
    const resultsSection = document.getElementById('results-section');
    const featuresContainer = document.getElementById('features-container');
    const matchesContainer = document.getElementById('matches-container');
    const loadingSpinner = document.getElementById('loading-spinner');
    const alertContainer = document.getElementById('alert-container');

    let selectedFile = null;

    // Handle file selection
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            if (fileInput.files.length) {
                handleFiles(fileInput.files);
            }
        });
    }

    // Dropzone for drag-and-drop file upload
    if (dropzone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, preventDefaults, false);
        });

        dropzone.addEventListener('drop', handleDrop, false);
        dropzone.addEventListener('click', () => fileInput.click());
    }

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length) handleFiles(files);
    }

    function handleFiles(files) {
        if (files[0].type === 'application/pdf') {
            selectedFile = files[0];
            updateDropzoneUI(selectedFile.name);
            if (processButton) processButton.disabled = false;
        } else {
            showAlert('Please upload a PDF file.', 'danger');
        }
    }

    function updateDropzoneUI(filename) {
        const dropzoneMessage = dropzone.querySelector('.dropzone-message');
        dropzoneMessage.innerHTML = `<strong>${filename}</strong>`;
    }

    // Clear button functionality
    if (clearButton) {
        clearButton.addEventListener('click', clearAll);
    }

    function clearAll() {
        selectedFile = null;
        if (fileInput) fileInput.value = '';
        if (textInput) textInput.value = '';
        if (featuresContainer) featuresContainer.innerHTML = '';
        if (matchesContainer) matchesContainer.innerHTML = '';
        if (resultsSection) resultsSection.classList.add('d-none');
        if (processButton) processButton.disabled = true;
        showAlert('All inputs cleared.', 'info');
    }

    // Process document and find matches
    if (processButton) {
        processButton.addEventListener('click', processDocument);
    }

    async function processDocument() {
        if (!selectedFile && (!textInput || !textInput.value.trim())) {
            showAlert('Please upload a PDF file or enter text.', 'danger');
            return;
        }

        // Show loading spinner
        if (loadingSpinner) loadingSpinner.classList.remove('d-none');
        if (resultsSection) resultsSection.classList.add('d-none');
        if (featuresContainer) featuresContainer.innerHTML = '';
        if (matchesContainer) matchesContainer.innerHTML = '';

        const formData = new FormData();
        if (selectedFile) {
            formData.append('file', selectedFile);
        } else if (textInput.value.trim()) {
            formData.append('text', textInput.value.trim());
        }

        try {
            const response = await fetch('/process', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (response.ok) {
                displayResults(data);
                resultsSection.classList.remove('d-none');
            } else {
                showAlert(data.error || 'An error occurred while processing the document.', 'danger');
            }
        } catch (error) {
            showAlert('An error occurred while processing the document.', 'danger');
        } finally {
            if (loadingSpinner) loadingSpinner.classList.add('d-none');
        }
    }

    // Display the extracted features and matched trials
    function displayResults(data) {
        displayFeatures(data.features);
        displayMatches(data.matched_trials);
    }

    // Display extracted features
    function displayFeatures(features) {
        if (!featuresContainer) return;
        featuresContainer.innerHTML = '';

        for (const [key, value] of Object.entries(features)) {
            const featureDiv = document.createElement('div');
            featureDiv.className = 'feature-item';

            const featureLabel = document.createElement('div');
            featureLabel.className = 'feature-label';
            featureLabel.textContent = key.replace(/_/g, ' ').toUpperCase();

            const featureValue = document.createElement('div');
            featureValue.className = 'feature-value';
            featureValue.textContent = JSON.stringify(value, null, 2);

            featureDiv.appendChild(featureLabel);
            featureDiv.appendChild(featureValue);
            featuresContainer.appendChild(featureDiv);
        }
    }

    // Display matched clinical trials
    function displayMatches(matches) {
        if (!matchesContainer) return;
        matchesContainer.innerHTML = '';

        if (!matches || matches.length === 0) {
            matchesContainer.innerHTML = '<p>No matched trials found.</p>';
            return;
        }

        matches.forEach(match => {
            const matchCard = document.createElement('div');
            matchCard.className = 'match-card';

            matchCard.innerHTML = `
                <h4>Trial ID: ${match.trial_id}</h4>
                <p><strong>Confidence:</strong> ${match.confidence}%</p>
                <p><strong>Recommendation:</strong> ${match.recommendation}</p>
                <p><strong>Summary:</strong> ${match.summary}</p>
            `;

            // Criteria Analysis (optional)
            if (match.analysis && Object.keys(match.analysis).length > 0) {
                const analysisDiv = document.createElement('div');
                analysisDiv.className = 'match-analysis';
                analysisDiv.innerHTML = '<h5>Criteria Analysis:</h5>';

                for (const [criterion, details] of Object.entries(match.analysis)) {
                    const criterionDiv = document.createElement('div');
                    criterionDiv.className = 'analysis-item';
                    criterionDiv.innerHTML = `
                        <strong>${criterion}:</strong> ${JSON.stringify(details, null, 2)}
                    `;
                    analysisDiv.appendChild(criterionDiv);
                }

                matchCard.appendChild(analysisDiv);
            }

            matchesContainer.appendChild(matchCard);
        });
    }

    // Show alert message
    function showAlert(message, type = 'info') {
        if (!alertContainer) return;
        alertContainer.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
        setTimeout(() => alertContainer.innerHTML = '', 5000);
    }
});
