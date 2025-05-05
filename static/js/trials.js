/**
 * MedMatchINT - Trials JavaScript
 * Handles functionality for displaying active clinical trials at INT
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const searchInput = document.getElementById('search-input');
    const phaseFilter = document.getElementById('phase-filter');
    const cancerTypeFilter = document.getElementById('cancer-type-filter');
    const trialsContainer = document.getElementById('trials-container');
    
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
        const phaseValue = phaseFilter ? phaseFilter.value : '';
        const cancerTypeValue = cancerTypeFilter ? cancerTypeFilter.value : '';
        
        const filteredTrials = trials.filter(trial => {
            // Search term filter
            const matchesSearch = searchTerm === '' || 
                trial.title.toLowerCase().includes(searchTerm) || 
                trial.description.toLowerCase().includes(searchTerm);
            
            // Phase filter
            const matchesPhase = phaseValue === '' || trial.phase === phaseValue;
            
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
            
            // Add inclusion criteria
            const inclusionContainer = trialCard.querySelector('.inclusion-criteria-container');
            trial.inclusion_criteria.forEach(criterion => {
                const criterionEl = document.createElement('div');
                criterionEl.className = 'match-criterion criterion-matched mb-2 p-2';
                criterionEl.innerHTML = `<p class="criterion-text mb-0">${criterion.text}</p>`;
                inclusionContainer.appendChild(criterionEl);
            });
            
            // Add exclusion criteria
            const exclusionContainer = trialCard.querySelector('.exclusion-criteria-container');
            trial.exclusion_criteria.forEach(criterion => {
                const criterionEl = document.createElement('div');
                criterionEl.className = 'match-criterion criterion-not-matched mb-2 p-2';
                criterionEl.innerHTML = `<p class="criterion-text mb-0">${criterion.text}</p>`;
                exclusionContainer.appendChild(criterionEl);
            });
            
            trialsContainer.appendChild(trialCard);
        });
        
        // Initialize feather icons
        feather.replace();
    }
});