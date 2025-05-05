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
    const textInputToggle = document.getElementById('text-input-toggle');
    const fileInputToggle = document.getElementById('file-input-toggle');
    const textInputSection = document.getElementById('text-input-section');
    const fileInputSection = document.getElementById('file-input-section');
    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
    const sidebar = document.querySelector('.sidebar');

    // Initialize state
    let selectedFile = null;
    let extractedText = "";
    
    // Initialize dropzone
    if (dropzone) {
        // Prevent default behaviors for drag events
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        // Handle drag enter/over events
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, highlight, false);
        });
        
        // Handle drag leave/drop events
        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, unhighlight, false);
        });
        
        // Handle highlighting
        function highlight() {
            dropzone.classList.add('active');
        }
        
        function unhighlight() {
            dropzone.classList.remove('active');
        }
        
        // Handle file drop
        dropzone.addEventListener('drop', handleDrop, false);
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            if (files.length) {
                handleFiles(files);
            }
        }
        
        // Handle file selection from input
        fileInput.addEventListener('change', function() {
            if (fileInput.files.length) {
                handleFiles(fileInput.files);
            }
        });
        
        // Click on dropzone to trigger file selection
        dropzone.addEventListener('click', function() {
            fileInput.click();
        });
        
        function handleFiles(files) {
            if (files[0].type === 'application/pdf') {
                selectedFile = files[0];
                updateDropzoneUI(selectedFile.name);
            } else {
                showAlert('Please upload a PDF file.', 'danger');
            }
        }
        
        function updateDropzoneUI(filename) {
            const dropzoneMessage = dropzone.querySelector('.dropzone-message');
            dropzoneMessage.innerHTML = `<strong>${filename}</strong>`;
            
            const dropzoneDescription = dropzone.querySelector('.dropzone-description');
            dropzoneDescription.textContent = 'Click to change file or drag and drop a new one';
            
            // Enable process button if file is selected
            processButton.disabled = false;
        }
    }
    
    // Toggle between file upload and text input
    if (textInputToggle && fileInputToggle) {
        textInputToggle.addEventListener('click', function(e) {
            e.preventDefault();
            fileInputSection.classList.add('d-none');
            textInputSection.classList.remove('d-none');
            textInputToggle.classList.add('active');
            fileInputToggle.classList.remove('active');
        });
        
        fileInputToggle.addEventListener('click', function(e) {
            e.preventDefault();
            textInputSection.classList.add('d-none');
            fileInputSection.classList.remove('d-none');
            fileInputToggle.classList.add('active');
            textInputToggle.classList.remove('active');
        });
    }
    
    // Clear button functionality
    if (clearButton) {
        clearButton.addEventListener('click', function() {
            // Clear file selection
            selectedFile = null;
            if (fileInput) fileInput.value = '';
            
            // Reset dropzone UI
            if (dropzone) {
                const dropzoneMessage = dropzone.querySelector('.dropzone-message');
                dropzoneMessage.innerHTML = 'Drag & drop your PDF file here';
                
                const dropzoneDescription = dropzone.querySelector('.dropzone-description');
                dropzoneDescription.textContent = 'or click to browse files';
                
                dropzone.classList.remove('active');
            }
            
            // Clear text input
            if (textInput) textInput.value = '';
            
            // Clear results section
            if (resultsSection) resultsSection.classList.add('d-none');
            if (featuresContainer) featuresContainer.innerHTML = '';
            if (matchesContainer) matchesContainer.innerHTML = '';
            
            // Disable process button
            if (processButton) processButton.disabled = true;
            
            // Clear any alerts
            if (alertContainer) alertContainer.innerHTML = '';
        });
    }
    
    // Process button functionality
    if (processButton) {
        processButton.addEventListener('click', processDocument);
    }
    
    // Mobile menu toggle
    if (mobileMenuToggle && sidebar) {
        mobileMenuToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
        });
    }
    
    // Process document and find matches
    function processDocument() {
        // Check if we have either a file or text input
        if (!selectedFile && (!textInput || !textInput.value.trim())) {
            showAlert('Please upload a PDF file or enter text.', 'danger');
            return;
        }
        
        // Show loading spinner
        if (loadingSpinner) loadingSpinner.classList.remove('d-none');
        
        // Hide results and clear previous content
        if (resultsSection) resultsSection.classList.add('d-none');
        if (featuresContainer) featuresContainer.innerHTML = '';
        if (matchesContainer) matchesContainer.innerHTML = '';
        
        // Create form data
        const formData = new FormData();
        
        if (selectedFile) {
            formData.append('file', selectedFile);
        } else if (textInput && textInput.value.trim()) {
            formData.append('text', textInput.value.trim());
        }
        
        // Send request to backend
        fetch('/process', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'An error occurred while processing the document.');
                });
            }
            return response.json();
        })
        .then(data => {
            // Hide loading spinner
            if (loadingSpinner) loadingSpinner.classList.add('d-none');
            
            // Display extracted features and matches
            displayResults(data);
            
            // Show results section
            if (resultsSection) resultsSection.classList.remove('d-none');
        })
        .catch(error => {
            // Hide loading spinner
            if (loadingSpinner) loadingSpinner.classList.add('d-none');
            
            // Show error message
            showAlert(error.message, 'danger');
        });
    }
    
    // Display results from processing
    function displayResults(data) {
        // Display extracted features
        displayFeatures(data.features);
        
        // Display matching trials
        displayMatches(data.matches);
        
        // Display original text
        displayOriginalText(data.text || data.features.original_text);
        
        // Scroll to results
        if (resultsSection) {
            resultsSection.scrollIntoView({ behavior: 'smooth' });
        }
    }
    
    // Display original text/PDF content
    function displayOriginalText(text) {
        const pdfTextContainer = document.getElementById('pdf-text');
        if (pdfTextContainer && text) {
            pdfTextContainer.textContent = text;
        }
    }
    
    // Display extracted features
    function displayFeatures(features) {
        if (!featuresContainer) return;
        
        featuresContainer.innerHTML = '';
        
        // Create feature items
        addFeatureItem(featuresContainer, 'Age', features.age);
        addFeatureItem(featuresContainer, 'Gender', features.gender);
        addFeatureItem(featuresContainer, 'Diagnosis', features.diagnosis);
        addFeatureItem(featuresContainer, 'Stage', features.stage);
        addFeatureItem(featuresContainer, 'ECOG Status', features.ecog);
        
        // Add mutations
        if (features.mutations && features.mutations.length > 0) {
            const mutationsDiv = document.createElement('div');
            mutationsDiv.className = 'feature-item';
            
            const mutationsLabel = document.createElement('div');
            mutationsLabel.className = 'feature-label';
            mutationsLabel.textContent = 'Mutations';
            
            const mutationsValue = document.createElement('div');
            mutationsValue.className = 'feature-value';
            
            features.mutations.forEach(mutation => {
                const mutationItem = document.createElement('div');
                mutationItem.className = 'mb-2';
                
                // Creiamo un testo più conciso per la mutazione
                const mutationText = document.createElement('div');
                let conciseValue = mutation.value;
                
                // Estrai informazioni più specifiche sul tipo di mutazione, se presenti
                if (mutation.source && mutation.source.toLowerCase().includes(mutation.value.toLowerCase())) {
                    // Cerca pattern comuni di mutazione come "KRAS G12C" o "PD-L1 90%"
                    const pdl1Match = mutation.source.match(new RegExp(mutation.value + '\\s+([0-9]+)\\s*%', 'i'));
                    const mutationMatch = mutation.source.match(new RegExp(mutation.value + '\\s+([A-Z][0-9]+[A-Z])', 'i'));
                    const statusMatch = mutation.source.match(/(positive|negative|mutato|wild.?type)/i);
                    
                    if (pdl1Match) {
                        conciseValue = `${mutation.value} ${pdl1Match[1]}%`;
                    } else if (mutationMatch) {
                        conciseValue = `${mutation.value} ${mutationMatch[1]}`;
                    } else if (statusMatch) {
                        conciseValue = `${mutation.value} ${statusMatch[1]}`;
                    }
                }
                
                mutationText.textContent = conciseValue;
                
                // Manteniamo anche il testo originale come fonte di contesto
                const mutationSource = document.createElement('div');
                mutationSource.className = 'feature-source';
                mutationSource.textContent = mutation.source;
                
                mutationItem.appendChild(mutationText);
                mutationItem.appendChild(mutationSource);
                mutationsValue.appendChild(mutationItem);
            });
            
            mutationsDiv.appendChild(mutationsLabel);
            mutationsDiv.appendChild(mutationsValue);
            featuresContainer.appendChild(mutationsDiv);
        }
        
        // Add metastases
        if (features.metastases && features.metastases.length > 0) {
            const metastasesDiv = document.createElement('div');
            metastasesDiv.className = 'feature-item';
            
            const metastasesLabel = document.createElement('div');
            metastasesLabel.className = 'feature-label';
            metastasesLabel.textContent = 'Metastases';
            
            const metastasesValue = document.createElement('div');
            metastasesValue.className = 'feature-value';
            
            features.metastases.forEach(metastasis => {
                const metastasisItem = document.createElement('div');
                metastasisItem.className = 'mb-2';
                
                // Creiamo un testo più conciso per la metastasi
                const metastasisText = document.createElement('div');
                let conciseValue = metastasis.value;
                
                // Estrai informazioni più specifiche sulle metastasi, se presenti
                if (metastasis.source && metastasis.source.toLowerCase().includes(metastasis.value.toLowerCase())) {
                    // Cerca descrittori comuni come "multiple" o "singular"
                    const countMatch = metastasis.source.match(/(multiple|singular|numerose|singole|solitarie?)\s+/i);
                    const sizeMatch = metastasis.source.match(/(\d+(?:\.\d+)?)\s*(?:mm|cm)/i);
                    
                    let description = "";
                    if (countMatch) description += countMatch[1] + " ";
                    if (sizeMatch) description += sizeMatch[0] + " ";
                    
                    if (description) {
                        conciseValue = description + metastasis.value;
                    } else {
                        conciseValue = metastasis.value + " metastasis";
                    }
                }
                
                metastasisText.textContent = conciseValue;
                
                // Manteniamo anche il testo originale come fonte di contesto
                const metastasisSource = document.createElement('div');
                metastasisSource.className = 'feature-source';
                metastasisSource.textContent = metastasis.source;
                
                metastasisItem.appendChild(metastasisText);
                metastasisItem.appendChild(metastasisSource);
                metastasesValue.appendChild(metastasisItem);
            });
            
            metastasesDiv.appendChild(metastasesLabel);
            metastasesDiv.appendChild(metastasesValue);
            featuresContainer.appendChild(metastasesDiv);
        }
        
        // Add previous treatments
        if (features.previous_treatments && features.previous_treatments.length > 0) {
            const treatmentsDiv = document.createElement('div');
            treatmentsDiv.className = 'feature-item';
            
            const treatmentsLabel = document.createElement('div');
            treatmentsLabel.className = 'feature-label';
            treatmentsLabel.textContent = 'Treatments';
            
            const treatmentsValue = document.createElement('div');
            treatmentsValue.className = 'feature-value';
            
            features.previous_treatments.forEach(treatment => {
                const treatmentItem = document.createElement('div');
                treatmentItem.className = 'mb-2';
                
                // Creiamo un testo più conciso per il trattamento
                const treatmentText = document.createElement('div');
                let conciseValue = treatment.value;
                
                // Estrai informazioni più specifiche sul trattamento, se presenti
                if (treatment.source && treatment.source.toLowerCase().includes(treatment.value.toLowerCase())) {
                    // Cerca informazioni sul numero di cicli o dosaggio
                    const cyclesMatch = treatment.source.match(/(\d+)\s*(?:cicli|ciclo|cycles|cycle)/i);
                    const doseMatch = treatment.source.match(/(\d+(?:\.\d+)?)\s*(?:mg\/m2|mg|g\/m2|g|ml)/i);
                    const dateMatch = treatment.source.match(/((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})/i);
                    
                    let info = [];
                    if (cyclesMatch) info.push(cyclesMatch[0]);
                    if (doseMatch) info.push(doseMatch[0]);
                    if (dateMatch) info.push(dateMatch[0]);
                    
                    if (info.length > 0) {
                        conciseValue = `${treatment.value} (${info.join(", ")})`;
                    }
                }
                
                treatmentText.textContent = conciseValue;
                
                // Manteniamo anche il testo originale come fonte di contesto
                const treatmentSource = document.createElement('div');
                treatmentSource.className = 'feature-source';
                treatmentSource.textContent = treatment.source;
                
                treatmentItem.appendChild(treatmentText);
                treatmentItem.appendChild(treatmentSource);
                treatmentsValue.appendChild(treatmentItem);
            });
            
            treatmentsDiv.appendChild(treatmentsLabel);
            treatmentsDiv.appendChild(treatmentsValue);
            featuresContainer.appendChild(treatmentsDiv);
        }
        
        // Add lab values
        if (features.lab_values && Object.keys(features.lab_values).length > 0) {
            const labValuesDiv = document.createElement('div');
            labValuesDiv.className = 'feature-item';
            
            const labValuesLabel = document.createElement('div');
            labValuesLabel.className = 'feature-label';
            labValuesLabel.textContent = 'Lab Values';
            
            const labValuesValue = document.createElement('div');
            labValuesValue.className = 'feature-value';
            
            for (const [key, value] of Object.entries(features.lab_values)) {
                const labValueItem = document.createElement('div');
                labValueItem.className = 'mb-2';
                
                const labValueText = document.createElement('div');
                labValueText.textContent = `${key}: ${value.value}`;
                
                const labValueSource = document.createElement('div');
                labValueSource.className = 'feature-source';
                labValueSource.textContent = value.source;
                
                labValueItem.appendChild(labValueText);
                labValueItem.appendChild(labValueSource);
                labValuesValue.appendChild(labValueItem);
            }
            
            labValuesDiv.appendChild(labValuesLabel);
            labValuesDiv.appendChild(labValuesValue);
            featuresContainer.appendChild(labValuesDiv);
        }
    }
    
    // Helper function to add a feature item
    function addFeatureItem(container, label, feature) {
        if (!feature || feature.value === null) return;
        
        const featureDiv = document.createElement('div');
        featureDiv.className = 'feature-item';
        
        const featureLabel = document.createElement('div');
        featureLabel.className = 'feature-label';
        featureLabel.textContent = label;
        
        const featureValue = document.createElement('div');
        featureValue.className = 'feature-value';
        
        const valueText = document.createElement('div');
        valueText.textContent = feature.value;
        
        const sourceText = document.createElement('div');
        sourceText.className = 'feature-source';
        sourceText.textContent = feature.source;
        
        featureValue.appendChild(valueText);
        featureValue.appendChild(sourceText);
        featureDiv.appendChild(featureLabel);
        featureDiv.appendChild(featureValue);
        
        container.appendChild(featureDiv);
    }
    
    // Display matching trials
    function displayMatches(matches) {
        if (!matchesContainer) return;
        
        matchesContainer.innerHTML = '';
        
        if (!matches || matches.length === 0) {
            // Show no matches message
            const noMatchesMessage = document.createElement('div');
            noMatchesMessage.className = 'alert alert-info';
            noMatchesMessage.textContent = 'No matching clinical trials found.';
            matchesContainer.appendChild(noMatchesMessage);
            return;
        }
        
        // Create a card for each matching trial
        matches.forEach(match => {
            const matchCard = document.createElement('div');
            matchCard.className = 'match-card';
            
            // Card header
            const cardHeader = document.createElement('div');
            cardHeader.className = 'match-card-header';
            
            const headerLeft = document.createElement('div');
            
            const matchTitle = document.createElement('h5');
            matchTitle.className = 'match-title';
            matchTitle.textContent = match.title;
            
            headerLeft.appendChild(matchTitle);
            
            const headerRight = document.createElement('div');
            headerRight.className = 'd-flex align-items-center';
            
            const phaseSpan = document.createElement('span');
            phaseSpan.className = 'match-phase';
            phaseSpan.textContent = match.phase || 'Unknown Phase';
            
            const percentageClass = match.match_percentage >= 80 ? 'match-percentage-high' :
                                    match.match_percentage >= 60 ? 'match-percentage-medium' :
                                    'match-percentage-low';
            
            const percentageSpan = document.createElement('span');
            percentageSpan.className = `match-percentage ${percentageClass}`;
            percentageSpan.textContent = `${match.match_percentage}% Match`;
            
            headerRight.appendChild(phaseSpan);
            headerRight.appendChild(percentageSpan);
            
            cardHeader.appendChild(headerLeft);
            cardHeader.appendChild(headerRight);
            
            // Card body
            const cardBody = document.createElement('div');
            cardBody.className = 'match-card-body';
            
            // Trial description
            if (match.description) {
                const descriptionPara = document.createElement('p');
                descriptionPara.className = 'match-description';
                descriptionPara.textContent = match.description;
                cardBody.appendChild(descriptionPara);
            }
            
            // Matched criteria
            if (match.matches && match.matches.length > 0) {
                const matchedSection = document.createElement('div');
                matchedSection.className = 'match-criteria-section';
                
                const matchedTitle = document.createElement('h6');
                matchedTitle.className = 'match-criteria-title';
                matchedTitle.textContent = 'Matched Criteria';
                
                matchedSection.appendChild(matchedTitle);
                
                match.matches.forEach(criterion => {
                    const criterionDiv = document.createElement('div');
                    criterionDiv.className = 'match-criterion criterion-matched';
                    
                    const criterionText = document.createElement('div');
                    criterionText.className = 'criterion-text';
                    criterionText.textContent = criterion.criterion.text;
                    
                    const criterionExplanation = document.createElement('div');
                    criterionExplanation.className = 'criterion-explanation';
                    criterionExplanation.textContent = criterion.explanation;
                    
                    criterionDiv.appendChild(criterionText);
                    criterionDiv.appendChild(criterionExplanation);
                    matchedSection.appendChild(criterionDiv);
                });
                
                cardBody.appendChild(matchedSection);
            }
            
            // Non-matched criteria
            if (match.non_matches && match.non_matches.length > 0) {
                const nonMatchedSection = document.createElement('div');
                nonMatchedSection.className = 'match-criteria-section';
                
                const nonMatchedTitle = document.createElement('h6');
                nonMatchedTitle.className = 'match-criteria-title';
                nonMatchedTitle.textContent = 'Unmatched Criteria';
                
                nonMatchedSection.appendChild(nonMatchedTitle);
                
                match.non_matches.forEach(criterion => {
                    const criterionDiv = document.createElement('div');
                    criterionDiv.className = 'match-criterion criterion-not-matched';
                    
                    const criterionText = document.createElement('div');
                    criterionText.className = 'criterion-text';
                    criterionText.textContent = criterion.criterion.text;
                    
                    const criterionExplanation = document.createElement('div');
                    criterionExplanation.className = 'criterion-explanation';
                    criterionExplanation.textContent = criterion.explanation;
                    
                    criterionDiv.appendChild(criterionText);
                    criterionDiv.appendChild(criterionExplanation);
                    nonMatchedSection.appendChild(criterionDiv);
                });
                
                cardBody.appendChild(nonMatchedSection);
            }
            
            matchCard.appendChild(cardHeader);
            matchCard.appendChild(cardBody);
            matchesContainer.appendChild(matchCard);
        });
    }
    
    // Show alert message
    function showAlert(message, type = 'info') {
        if (!alertContainer) return;
        
        // Clear previous alerts
        alertContainer.innerHTML = '';
        
        // Create alert element
        const alertEl = document.createElement('div');
        alertEl.className = `alert alert-${type} alert-dismissible fade show`;
        alertEl.role = 'alert';
        
        alertEl.innerHTML = `
            ${message}
            <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        `;
        
        // Add alert to container
        alertContainer.appendChild(alertEl);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            alertEl.classList.remove('show');
            setTimeout(() => {
                alertContainer.removeChild(alertEl);
            }, 150);
        }, 5000);
    }
});
