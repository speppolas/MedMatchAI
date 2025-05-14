/**
 * MedMatchINT - Trials JavaScript
 * Handles functionality for displaying active clinical trials at INT
 */

// Function to display alert messages
function showAlert(message, type) {
    // Create alert element
    const alertEl = document.createElement('div');
    alertEl.className = `alert alert-${type} alert-dismissible fade show`;
    alertEl.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    // Find or create alerts container
    let alertsContainer = document.getElementById('alerts-container');
    if (!alertsContainer) {
        alertsContainer = document.createElement('div');
        alertsContainer.id = 'alerts-container';
        alertsContainer.className = 'position-fixed top-0 end-0 p-3';
        alertsContainer.style.zIndex = '9999';
        document.body.appendChild(alertsContainer);
    }

    // Add alert to container
    alertsContainer.appendChild(alertEl);

    // Auto dismiss alert after 5 seconds
    setTimeout(() => {
        alertEl.classList.remove('show');
        setTimeout(() => {
            alertEl.remove();
        }, 150);
    }, 5000);
}

// Add CSS for rotating icon animation
// Add CSS for rotating icon animation
document.head.insertAdjacentHTML('beforeend', `
<style>
    @keyframes rotate {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    .rotate {
        animation: rotate 1.5s linear infinite;
    }
</style>
`);

document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const searchInput = document.getElementById('search-input');
    const phaseFilter = document.getElementById('phase-filter');
    const cancerTypeFilter = document.getElementById('cancer-type-filter');
    const trialsContainer = document.getElementById('trials-container');
    const filtersContainer = document.getElementById('filters-container');

    // Aggiungi un bottone di aggiornamento per i trial
    const updateButton = document.createElement('button');
    updateButton.className = 'btn btn-outline-primary mb-3 me-3';
    updateButton.innerHTML = '<i data-feather="refresh-cw"></i> Aggiorna trial da ClinicalTrials.gov';
    updateButton.onclick = function() {
        // Cambia lo stato del pulsante durante l'aggiornamento
        updateButton.disabled = true;
        updateButton.innerHTML = '<i data-feather="refresh-cw" class="rotate"></i> Aggiornamento in corso...';
        feather.replace();

        // Mostra un messaggio di attesa
        showAlert('Aggiornamento dei trial clinici in corso. Questa operazione potrebbe richiedere alcuni minuti...', 'info');

        // Chiama l'API con il parametro di aggiornamento
        fetch('/api/trials?update=true')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to update trials data');
                }
                return response.json();
            })
            .then(data => {
                trials = data;
                displayTrials(trials);

                // Ripristina lo stato del pulsante
                updateButton.disabled = false;
                updateButton.innerHTML = '<i data-feather="refresh-cw"></i> Aggiorna trial da ClinicalTrials.gov';
                feather.replace();

                // Mostra un messaggio di successo
                showAlert('Trial clinici aggiornati con successo!', 'success');
            })
            .catch(error => {
                console.error('Error updating trials:', error);

                // Ripristina lo stato del pulsante
                updateButton.disabled = false;
                updateButton.innerHTML = '<i data-feather="refresh-cw"></i> Aggiorna trial da ClinicalTrials.gov';
                feather.replace();

                // Mostra un messaggio di errore
                showAlert('Errore durante l\'aggiornamento dei trial clinici: ' + error.message, 'danger');
            });
    };

    // Inserisci il pulsante prima dei filtri
    const cardHeader = document.querySelector('.card-header');
    if (cardHeader) {
        cardHeader.appendChild(updateButton);
        feather.replace();
    }

    // Initialize trials data
    let trials = [];

    // Fetch trials data from the server
    fetch('/api/trials')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load trials data');
            }
            return response.json();
        })
        .then(data => {
            trials = data;
            displayTrials(trials);

            // Initialize event listeners for filters
            initializeFilters();
        })
        .catch(error => {
            console.error('Error loading trials:', error);
            trialsContainer.innerHTML = `
                <div class="alert alert-danger">
                    <h5>Error Loading Trials</h5>
                    <p>${error.message}</p>
                </div>
            `;
        });

    // Initialize filter event listeners
    function initializeFilters() {
        if (searchInput) {
            searchInput.addEventListener('input', filterTrials);
        }

        if (phaseFilter) {
            phaseFilter.addEventListener('change', filterTrials);
        }

        if (cancerTypeFilter) {
            cancerTypeFilter.addEventListener('change', filterTrials);
        }
    }

    // Filter trials based on current filter values
    function filterTrials() {
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        const phaseValue = phaseFilter ? phaseFilter.value.toLowerCase() : '';
        const cancerTypeValue = cancerTypeFilter ? cancerTypeFilter.value.toLowerCase() : '';

        // Se stiamo cercando un ID di protocollo specifico, usa l'API del server per la ricerca più accurata
        // Riconosce vari formati di ID utilizzati in ambito clinico

        // Funzione helper per verificare se un termine ha un pattern che assomiglia a un ID di protocollo o registro
        function isLikelyProtocolId(term) {
            term = term.trim().toLowerCase();

            // Controlli speciali per casi noti
            if (term === "d5087c00001" || term === "d5087c" || term.startsWith("d5087")) {
                return true;
            }

            // Pattern per i vari tipi di ID
            const patterns = [
                /^nct\d{6,}/,                         // NCT ID: NCT seguito da numeri (ClinicalTrials.gov)
                /^d\d+c\d+/,                          // Formato D5087C00001
                /^[a-z][0-9]{4}[a-z][0-9]{5}/,        // Altri ID alfanumerici di protocollo
                /^\d{4}-\d{6}-\d{2}/,                 // EudraCT Number: YYYY-NNNNNN-CC
                /^\d{4}-\d{6}-\d{2}-\d{2}/,           // Registry Identifier: YYYY-NNNNNN-CC-DD
                /^[a-z]\d{4,}[a-z0-9]/i,              // ID generici alfanumerici di studi
                /^\d{4,}-\d{4,}/                      // Numeri con trattini (vari formati di ID)
            ];

            // Verifica se uno qualsiasi dei pattern corrisponde
            return patterns.some(pattern => term.match(pattern));
        }

        if (isLikelyProtocolId(searchTerm)) {
            // Mostra un indicatore di caricamento
            trialsContainer.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="sr-only">Loading...</span>
                    </div>
                    <p class="mt-2">Ricerca protocollo ${searchTerm} in corso...</p>
                </div>
            `;

            // Chiama l'API per la ricerca avanzata
            fetch(`/api/trials?id=${encodeURIComponent(searchTerm)}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Failed to search trial by ID');
                    }
                    return response.json();
                })
                .then(data => {
                    // Aggiorna temporaneamente i trial mostrati
                    if (data && data.length > 0) {
                        displayTrials(data);
                    } else {
                        trialsContainer.innerHTML = `
                            <div class="alert alert-info text-center">
                                <i data-feather="info" class="mb-2" width="24" height="24"></i>
                                <p class="mb-0">Nessun trial corrisponde al protocollo "${searchTerm}". Prova un altro ID.</p>
                            </div>
                        `;
                        feather.replace();
                    }
                })
                .catch(error => {
                    console.error('Error searching trial by ID:', error);
                    trialsContainer.innerHTML = `
                        <div class="alert alert-danger">
                            <h5>Error searching trial</h5>
                            <p>${error.message}</p>
                        </div>
                    `;
                });

            return; // Interrompi l'esecuzione qui
        }

        // Per ricerche standard, filtra sul client
        const filteredTrials = trials.filter(trial => {
            // Search term filter (ora include anche l'ID del protocollo)
            const matchesSearch = searchTerm === '' || 
                trial.title.toLowerCase().includes(searchTerm) || 
                trial.description.toLowerCase().includes(searchTerm) ||
                (trial.id && trial.id.toLowerCase().includes(searchTerm));

            // Phase filter
            const matchesPhase = phaseValue === '' || trial.phase.toLowerCase() === phaseValue;

            // Cancer type filter
            let matchesCancerType = cancerTypeValue === '';

            if (!matchesCancerType) {
                const diagnosisCriteria = [...trial.inclusion_criteria, ...trial.exclusion_criteria]
                    .filter(criterion => criterion.type === 'diagnosis')
                    .map(criterion => criterion.text.toLowerCase());

                matchesCancerType = diagnosisCriteria.some(text => text.includes(cancerTypeValue));
            }

            return matchesSearch && matchesPhase && matchesCancerType;
        });

        displayTrials(filteredTrials);
    }

    // Display trials in the container
    function displayTrials(trialsToShow) {
        if (!trialsContainer) return;

        // Clear container
        trialsContainer.innerHTML = '';

        if (trialsToShow.length === 0) {
            trialsContainer.innerHTML = `
                <div class="alert alert-info text-center">
                    <i data-feather="info" class="mb-2" width="24" height="24"></i>
                    <p class="mb-0">No trials match your criteria. Try adjusting your filters.</p>
                </div>
            `;
            feather.replace();
            return;
        }

        // Get the template
        const template = document.getElementById('trial-card-template');

        // Create a card for each trial
        trialsToShow.forEach(trial => {
            const trialCard = document.importNode(template.content, true);

            // Fill in the trial data
            trialCard.querySelector('.trial-title').textContent = trial.title;
            trialCard.querySelector('.match-phase').textContent = trial.phase;
            trialCard.querySelector('.trial-id').textContent = trial.id;
            trialCard.querySelector('.trial-description').textContent = trial.description;

            // Color code the phase badge
            const phaseEl = trialCard.querySelector('.match-phase');
            phaseEl.classList.add('d-inline-block', 'px-2', 'py-1', 'rounded', 'text-white');

            if (trial.phase.includes('I/II')) {
                phaseEl.classList.add('bg-info');
            } else if (trial.phase.includes('I')) {
                phaseEl.classList.add('bg-warning');
            } else if (trial.phase.includes('II')) {
                phaseEl.classList.add('bg-primary');
            } else if (trial.phase.includes('III')) {
                phaseEl.classList.add('bg-success');
            }

            // Nascondi i criteri all'inizio
            const criteriaContainer = trialCard.querySelector('.match-criteria-container');
            if (criteriaContainer) {
                criteriaContainer.style.display = 'none';
            }

            // Aggiungi un pulsante "Mostra dettagli"
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'text-center mt-3';
            const toggleButton = document.createElement('button');
            toggleButton.className = 'btn btn-outline-primary btn-sm';
            toggleButton.innerHTML = '<i data-feather="chevron-down"></i> Mostra criteri';
            toggleButton.dataset.expanded = 'false';
            buttonContainer.appendChild(toggleButton);

            // Inserisci il pulsante prima del container dei criteri
            if (criteriaContainer) {
                criteriaContainer.parentNode.insertBefore(buttonContainer, criteriaContainer);
            }

            // Aggiungi evento click al pulsante
            toggleButton.addEventListener('click', function() {
                const isExpanded = this.dataset.expanded === 'true';

                if (isExpanded) {
                    // Nascondi i criteri
                    criteriaContainer.style.display = 'none';
                    this.innerHTML = '<i data-feather="chevron-down"></i> Mostra criteri';
                    this.dataset.expanded = 'false';
                } else {
                    // Mostra i criteri e caricali se non sono ancora stati caricati
                    criteriaContainer.style.display = 'block';
                    this.innerHTML = '<i data-feather="chevron-up"></i> Nascondi criteri';
                    this.dataset.expanded = 'true';
                    criteriaContainer.style.display = 'block';

                    // Clear and reload criteria every time they are shown
                    const inclusionContainer = trialCard.querySelector('.inclusion-criteria-container');
                    const exclusionContainer = trialCard.querySelector('.exclusion-criteria-container');

                    // Clear existing criteria
                    if (inclusionContainer) inclusionContainer.innerHTML = '';
                    if (exclusionContainer) exclusionContainer.innerHTML = '';

                    // Add inclusion criteria
                    if (inclusionContainer && trial.inclusion_criteria && Array.isArray(trial.inclusion_criteria)) {
                        trial.inclusion_criteria.forEach(criterion => {
                            const criterionEl = document.createElement('div');
                            criterionEl.className = 'match-criterion criterion-matched mb-2 p-2';
                            criterionEl.innerHTML = `<p class="criterion-text mb-0">${typeof criterion === 'string' ? criterion : criterion.text}</p>`;
                            inclusionContainer.appendChild(criterionEl);
                        });
                    }

                    // Add exclusion criteria
                    if (exclusionContainer && trial.exclusion_criteria && Array.isArray(trial.exclusion_criteria)) {
                        trial.exclusion_criteria.forEach(criterion => {
                            const criterionEl = document.createElement('div');
                            criterionEl.className = 'match-criterion criterion-not-matched mb-2 p-2';
                            criterionEl.innerHTML = `<p class="criterion-text mb-0">${typeof criterion === 'string' ? criterion : criterion.text}</p>`;
                            exclusionContainer.appendChild(criterionEl);
                        });
                    }

                    // Initialize feather icons for any new elements
                    feather.replace();
                }

                // Reinizializza le icone feather
                feather.replace();
            });

            trialsContainer.appendChild(trialCard);
        });

        // Initialize feather icons
        feather.replace();
    }
});