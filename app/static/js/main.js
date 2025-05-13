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

        // Create progress banner if it doesn't exist
        let progressBanner = document.getElementById('progress-banner');
        if (!progressBanner) {
            progressBanner = document.createElement('div');
            progressBanner.id = 'progress-banner';
            progressBanner.className = 'progress-banner';
            progressBanner.innerHTML = `
                <div class="progress">
                    <div class="progress-bar" role="progressbar" style="width: 0%"></div>
                </div>
                <div class="progress-message"></div>
            `;
            document.body.appendChild(progressBanner);
        }
        
        // Show progress banner
        progressBanner.style.display = 'block';
        const progressBar = progressBanner.querySelector('.progress-bar');
        const progressMessage = progressBanner.querySelector('.progress-message');
        
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
        
        // Send request using EventSource for progress updates
        const params = new URLSearchParams();
        if (selectedFile) {
            params.append('file', selectedFile);
        } else {
            params.append('text', textInput.value.trim());
        }

        const evtSource = new EventSource('/process?' + params.toString());
        
        evtSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            if (data.percentage !== undefined) {
                // Update progress
                progressBar.style.width = data.percentage + '%';
                progressMessage.textContent = data.message;
                
                if (data.complete) {
                    // Complete - hide progress and show results
                    progressBanner.style.display = 'none';
                    evtSource.close();
                    displayResults(data);
                    if (resultsSection) resultsSection.classList.remove('d-none');
                }
            }
        };
        
        evtSource.onerror = function(err) {
            evtSource.close();
            progressBanner.style.display = 'none';
            showAlert('An error occurred while processing the document.', 'danger');
        };
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
        
        // Display original text and PDF viewer button if available
        displayOriginalText(data.text || data.features.original_text, data.pdf_filename);
        
        // Scroll to results
        if (resultsSection) {
            resultsSection.scrollIntoView({ behavior: 'smooth' });
        }
    }
    
    // Display original text/PDF content and add PDF viewer button if available
    function displayOriginalText(text, pdfFilename) {
        const pdfContainer = document.getElementById('pdf-container');
        const pdfTextContainer = document.getElementById('pdf-text');
        
        if (pdfTextContainer && text) {
            pdfTextContainer.textContent = text;
        }
        
        // Se il nome del file PDF è disponibile, mostriamo il pulsante
        if (pdfFilename && pdfContainer) {
            // Rimuovi eventuali pulsanti precedenti
            const oldButton = document.getElementById('view-pdf-button');
            if (oldButton) {
                oldButton.remove();
            }
            
            // Crea un nuovo pulsante per visualizzare il PDF
            const viewButton = document.createElement('div');
            viewButton.className = 'text-center p-3';
            viewButton.innerHTML = `
                <a id="view-pdf-button" href="/view-pdf/${pdfFilename}" target="_blank" 
                   class="btn btn-primary">
                    <i data-feather="file-text"></i> Visualizza PDF Originale
                </a>
            `;
            
            // Inserisci il pulsante prima del contenitore di testo
            pdfContainer.insertBefore(viewButton, pdfTextContainer);
            
            // Inizializza le icone Feather
            feather.replace();
        }
    }
    
    // Display extracted features
    function displayFeatures(features) {
        if (!featuresContainer) return;
        
        featuresContainer.innerHTML = '';
        
        // Create feature items (simple values)
        const simpleFeatures = {
            'Age': features.age && features.age.value ? `${features.age.value} anni` : 'Non rilevato',
            'Gender': features.gender && features.gender.value ? features.gender.value : 'Non rilevato',
            'Diagnosis': features.diagnosis && features.diagnosis.value ? features.diagnosis.value : 'Non rilevato',
            'Stage': features.stage && features.stage.value ? features.stage.value : 'Non rilevato',
            'ECOG Status': features.ecog && features.ecog.value !== null ? features.ecog.value : 'Non rilevato'
        };
        
        // Aggiungi le feature semplici
        for (const [label, value] of Object.entries(simpleFeatures)) {
            const featureDiv = document.createElement('div');
            featureDiv.className = 'feature-item';
            
            const featureLabel = document.createElement('div');
            featureLabel.className = 'feature-label';
            featureLabel.textContent = label;
            
            const featureValue = document.createElement('div');
            featureValue.className = 'feature-value';
            featureValue.textContent = value;
            
            featureDiv.appendChild(featureLabel);
            featureDiv.appendChild(featureValue);
            featuresContainer.appendChild(featureDiv);
        }
        
        // Add mutations - formato conciso
        if (features.mutations && features.mutations.length > 0) {
            const mutationsDiv = document.createElement('div');
            mutationsDiv.className = 'feature-item';
            
            const mutationsLabel = document.createElement('div');
            mutationsLabel.className = 'feature-label';
            mutationsLabel.textContent = 'Mutations';
            
            const mutationsValue = document.createElement('div');
            mutationsValue.className = 'feature-value';
            
            features.mutations.forEach(mutation => {
                // Creiamo un testo più conciso per la mutazione
                let conciseValue = mutation.value;
                
                // Estrai informazioni più specifiche sul tipo di mutazione
                if (mutation.source && mutation.source.toLowerCase().includes(mutation.value.toLowerCase())) {
                    // Cerca pattern specifici
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
                
                const mutationText = document.createElement('div');
                mutationText.textContent = conciseValue;
                mutationsValue.appendChild(mutationText);
            });
            
            mutationsDiv.appendChild(mutationsLabel);
            mutationsDiv.appendChild(mutationsValue);
            featuresContainer.appendChild(mutationsDiv);
        }
        
        // Add metastases - formato conciso
        if (features.metastases && features.metastases.length > 0) {
            const metastasesDiv = document.createElement('div');
            metastasesDiv.className = 'feature-item';
            
            const metastasesLabel = document.createElement('div');
            metastasesLabel.className = 'feature-label';
            metastasesLabel.textContent = 'Metastases';
            
            const metastasesValue = document.createElement('div');
            metastasesValue.className = 'feature-value';
            
            features.metastases.forEach(metastasis => {
                // Creiamo un testo più conciso per la metastasi
                let conciseValue = metastasis.value;
                
                // Estrai informazioni significative come numero e dimensioni
                if (metastasis.source) {
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
                
                const metastasisText = document.createElement('div');
                metastasisText.textContent = conciseValue;
                metastasesValue.appendChild(metastasisText);
            });
            
            metastasesDiv.appendChild(metastasesLabel);
            metastasesDiv.appendChild(metastasesValue);
            featuresContainer.appendChild(metastasesDiv);
        }
        
        // Add previous treatments - formato conciso
        if (features.previous_treatments && features.previous_treatments.length > 0) {
            const treatmentsDiv = document.createElement('div');
            treatmentsDiv.className = 'feature-item';
            
            const treatmentsLabel = document.createElement('div');
            treatmentsLabel.className = 'feature-label';
            treatmentsLabel.textContent = 'Treatments';
            
            const treatmentsValue = document.createElement('div');
            treatmentsValue.className = 'feature-value';
            
            features.previous_treatments.forEach(treatment => {
                // Creiamo un testo più conciso per il trattamento
                let conciseValue = treatment.value;
                
                // Estrai informazioni sui cicli, dosaggio o date
                if (treatment.source) {
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
                
                const treatmentText = document.createElement('div');
                treatmentText.textContent = conciseValue;
                treatmentsValue.appendChild(treatmentText);
            });
            
            treatmentsDiv.appendChild(treatmentsLabel);
            treatmentsDiv.appendChild(treatmentsValue);
            featuresContainer.appendChild(treatmentsDiv);
        }
        
        // Add lab values - formato conciso
        if (features.lab_values && Object.keys(features.lab_values).length > 0) {
            const labValuesDiv = document.createElement('div');
            labValuesDiv.className = 'feature-item';
            
            const labValuesLabel = document.createElement('div');
            labValuesLabel.className = 'feature-label';
            labValuesLabel.textContent = 'Lab Values';
            
            const labValuesValue = document.createElement('div');
            labValuesValue.className = 'feature-value';
            
            for (const [key, value] of Object.entries(features.lab_values)) {
                const labValueText = document.createElement('div');
                labValueText.textContent = `${key}: ${value.value}`;
                labValuesValue.appendChild(labValueText);
            }
            
            labValuesDiv.appendChild(labValuesLabel);
            labValuesDiv.appendChild(labValuesValue);
            featuresContainer.appendChild(labValuesDiv);
        }
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
