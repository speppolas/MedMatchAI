/**
 * MedMatchINT - Main JavaScript with Enhanced Real-Time Progress Bar
 * Handles all client-side functionality for the clinical trial matching application
 */

// Initialize Socket.IO
const socket = io();

// Get DOM elements
document.addEventListener('DOMContentLoaded', function() {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const processButton = document.getElementById('process-button');
    const clearButton = document.getElementById('clear-button');
    const resultsSection = document.getElementById('results-section');
    const featuresContainer = document.getElementById('features-container');
    const matchesContainer = document.getElementById('matches-container');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const alertContainer = document.getElementById('alert-container');

    let selectedFile = null;
    let isProcessing = false;

    // Initialize dropzone
    if (dropzone) {
        dropzone.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                selectedFile = e.target.files[0];
                updateDropzoneUI(selectedFile.name);
                processButton.disabled = false;
            }
        });
    }

    // Process button functionality
    if (processButton) {
        processButton.addEventListener('click', processDocument);
    }

    // Clear button functionality
    if (clearButton) {
        clearButton.addEventListener('click', clearAll);
    }

    // Socket.IO progress update
    socket.on('progress_update', function(data) {
        progressContainer.style.display = 'block';
        progressText.textContent = data.message;
        updateProgressBar(data.message);
    });

    // Socket.IO final response
    socket.on('llm_response', function(data) {
        isProcessing = false;
        if (data.error) {
            showAlert('❌ Error extracting features: ' + data.error, 'danger');
            updateProgressBar('❌ Error during feature extraction.');
            setTimeout(() => { progressContainer.style.display = 'none'; }, 4000);
            return;
        }

        // Display results
        displayResults(data);
        updateProgressBar('✅ Feature extraction complete.');
        setTimeout(() => { progressContainer.style.display = 'none'; }, 2000);
    });

    function processDocument() {
        if (!selectedFile) {
            showAlert('Please upload a PDF file.', 'danger');
            return;
        }

        if (isProcessing) {
            showAlert('Feature extraction is already in progress.', 'info');
            return;
        }

        isProcessing = true;
        progressContainer.style.display = 'block';
        progressBar.style.width = '0%';
        progressBar.style.backgroundColor = '#2c7be5';
        progressText.textContent = "Starting feature extraction...";

        const formData = new FormData();
        formData.append('file', selectedFile);

        fetch('/process', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                showAlert(data.message, 'info');
            }
        })
        .catch(error => {
            showAlert('An error occurred while processing.', 'danger');
            updateProgressBar('❌ Error during feature extraction.');
            isProcessing = false;
        });
    }

    function updateProgressBar(message) {
        switch (true) {
            case message.includes('Extracting text'):
                progressBar.style.width = '30%';
                progressBar.style.backgroundColor = '#2c7be5'; // Blue
                break;
            case message.includes('Extracting features'):
                progressBar.style.width = '60%';
                progressBar.style.backgroundColor = '#2c7be5'; // Blue
                break;
            case message.includes('✅ Features extracted successfully'):
                progressBar.style.width = '90%';
                progressBar.style.backgroundColor = '#00d97e'; // Green
                break;
            case message.includes('❌ Failed to extract features'):
                progressBar.style.width = '100%';
                progressBar.style.backgroundColor = '#e63757'; // Red
                break;
            case message.includes('❌ Error'):
                progressBar.style.width = '100%';
                progressBar.style.backgroundColor = '#e63757'; // Red
                break;
            case message.includes('✅ Feature extraction complete.'):
                progressBar.style.width = '100%';
                progressBar.style.backgroundColor = '#00d97e'; // Green
                break;
        }
    }

    function displayResults(data) {
        featuresContainer.innerText = data.features ? JSON.stringify(data.features, null, 2) : "No features extracted.";
        matchesContainer.innerText = data.matches ? JSON.stringify(data.matches, null, 2) : "No matching trials.";
        resultsSection.classList.remove('d-none');
        progressText.textContent = '✅ Feature extraction complete.';
        progressBar.style.width = '100%';
        progressBar.style.backgroundColor = '#00d97e'; // Green
    }

    function clearAll() {
        selectedFile = null;
        fileInput.value = '';
        processButton.disabled = true;
        resultsSection.classList.add('d-none');
        featuresContainer.innerHTML = '';
        matchesContainer.innerHTML = '';
        progressContainer.style.display = 'none';
        progressBar.style.width = '0%';
        progressBar.style.backgroundColor = '#2c7be5';
        progressText.textContent = '';
        showAlert('Cleared all inputs.', 'success');
        isProcessing = false;
    }

    function updateDropzoneUI(filename) {
        const dropzoneMessage = dropzone.querySelector('.dropzone-message');
        dropzoneMessage.innerHTML = `<strong>${filename}</strong>`;
        processButton.disabled = false;
    }

    function showAlert(message, type) {
        alertContainer.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
        setTimeout(() => { alertContainer.innerHTML = ''; }, 4000);
    }
});
