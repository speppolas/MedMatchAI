import os
import json
import re
import logging
import uuid
import time
import shutil
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import render_template, request, jsonify, current_app, send_from_directory, session, abort
from app import bp
from app.utils import extract_text_from_pdf, extract_features, clean_expired_files, format_features_concise
from models import ClinicalTrial, db
from app.llm_processor import get_llm_processor
from app.hybrid_query import get_hybrid_query

@bp.route('/')
def index():
    """Render the main application page."""
    return render_template('index.html')

@bp.route('/trials')
def trials():
    """Render the trials listing page."""
    return render_template('trials.html')

@bp.route('/view-pdf/<filename>')
def view_pdf(filename):
    """
    Visualizza un PDF dal filesystem in modo sicuro.
    
    Questa route consente di visualizzare un PDF caricato in precedenza,
    ma solo se il nome del file è autorizzato (presente nella sessione) e
    il file esiste ancora. Ciò garantisce che solo l'utente che ha caricato
    il file possa visualizzarlo.
    
    Args:
        filename: Il nome del file PDF da visualizzare
        
    Returns:
        Il file PDF o un errore 404/403 se non trovato o non autorizzato.
    """
    try:
        # Verifica se il file è autorizzato (presente nella sessione)
        session_filename = session.get('pdf_filename')
        
        # Se non c'è nessun filename nella sessione o non corrisponde
        if not session_filename or session_filename != filename:
            # Controllo di sicurezza fallito
            logging.warning(f"Tentativo di accesso a PDF non autorizzato: {filename}")
            abort(403)  # Forbidden
        
        # Pulisci i file scaduti prima di servire il PDF richiesto
        clean_expired_files()
        
        # Costruisci il percorso completo del file
        pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        # Verifica se il file esiste
        if not os.path.exists(pdf_path):
            logging.warning(f"PDF richiesto non trovato: {filename}")
            abort(404)  # Not Found
        
        # Restituisci il file PDF
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'],
            filename,
            mimetype='application/pdf',
            as_attachment=False
        )
    except Exception as e:
        logging.error(f"Errore durante l'accesso al PDF {filename}: {str(e)}")
        return jsonify({'error': f'Si è verificato un errore: {str(e)}'}), 500

@bp.route('/api/trials')
def api_trials():
    """API endpoint to get all available trials."""
    try:
        # Ottieni il parametro di aggiornamento dalla query string
        update_param = request.args.get('update', 'false').lower()
        
        # Se è richiesto un aggiornamento
        if update_param == 'true':
            try:
                from update_trials import update_trials
                success = update_trials()
                if success:
                    logging.info("Aggiornamento dei trial clinici completato con successo")
                else:
                    logging.error("Aggiornamento dei trial clinici non riuscito")
            except Exception as update_err:
                logging.error(f"Errore durante l'aggiornamento dei trial: {str(update_err)}")
        
        # Verifica se è richiesto un ID specifico
        trial_id = request.args.get('id')
        
        if trial_id:
            # Ricerca per ID del protocollo (sia per NCT che per ID interno come D5087C00001)
            matching_trials = []
            
            # Cerca nel modello ClinicalTrial con ricerca flessibile
            # Utilizziamo un approccio più flessibile per trovare corrispondenze negli ID
            try:
                # 1. Cerca corrispondenza esatta nell'ID
                trials_db_exact = ClinicalTrial.query.filter(
                    ClinicalTrial.id == trial_id
                ).all()
                
                # Se il trial non esiste nel database locale con corrispondenza esatta,
                # prova a cercarlo direttamente su ClinicalTrials.gov
                if not trials_db_exact:
                    # Importa il modulo per il recupero diretto da ClinicalTrials.gov
                    from fetch_trial_by_id import fetch_and_save_trial_by_id
                    
                    logging.info(f"Cercando il trial con ID '{trial_id}' su ClinicalTrials.gov")
                    
                    # Recupera il trial da ClinicalTrials.gov
                    fetched_trial = fetch_and_save_trial_by_id(trial_id, current_app._get_current_object())
                    
                    if fetched_trial:
                        logging.info(f"Trial trovato su ClinicalTrials.gov e salvato localmente: {fetched_trial['id']}")
                        return jsonify([fetched_trial])
                    
                    # Se non è possibile recuperare il trial da ClinicalTrials.gov,
                    # continua con la ricerca locale standard
                    logging.info(f"Impossibile trovare il trial su ClinicalTrials.gov, continuando con la ricerca locale")
                
                # Se abbiamo trovato un risultato esatto, restituiscilo subito
                if trials_db_exact:
                    return jsonify([trial.to_dict() for trial in trials_db_exact])
                    
                # 2. Cerca corrispondenza in tutti gli ID possibili (ID principale, ID organizzazione e ID secondari)
                from sqlalchemy.sql import or_, cast
                from sqlalchemy import String, JSON, func
                from sqlalchemy.sql.expression import literal
                
                # Normalizza l'ID di ricerca rimuovendo trattini e spazi
                normalized_trial_id = trial_id.lower().replace('-', '').replace(' ', '')
                
                # Prima cerca usando i campi diretti del database
                trials_db = ClinicalTrial.query.filter(
                    or_(
                        ClinicalTrial.id.ilike(f"%{trial_id}%"),
                        ClinicalTrial.title.ilike(f"%{trial_id}%"),
                        ClinicalTrial.org_study_id.ilike(f"%{trial_id}%"),
                        # Ricerca per formati speciali come EudraCT e D5087C00001
                        func.lower(ClinicalTrial.org_study_id).contains(trial_id.lower()),
                        # Ricerca specifica per D5087C00001
                        ClinicalTrial.org_study_id == "D5087C00001" if trial_id.upper() == "D5087C00001" else False
                    )
                ).all()
                
                # Se non abbiamo trovato corrispondenze o per sicurezza (per gli ID secondari)
                # Consulta tutti i trial e filtra manualmente
                all_trials_db = ClinicalTrial.query.all()
                
                # Se la ricerca precedente non ha trovato risultati, inizializza una lista vuota
                # altrimenti mantieni i risultati già trovati
                if not trials_db:
                    trials_db = []
                    
                # Converti in un set per evitare duplicati
                trials_db_set = set(trials_db)
                
                for trial in all_trials_db:
                    # Salta i trial già trovati
                    if trial in trials_db_set:
                        continue
                        
                    # ID dell'organizzazione, prova con formati normalizzati
                    if trial.org_study_id:
                        normalized_org_id = trial.org_study_id.lower().replace('-', '').replace(' ', '')
                        if normalized_trial_id in normalized_org_id:
                            trials_db.append(trial)
                            trials_db_set.add(trial)
                            continue
                    
                    # Verifica negli ID secondari
                    if trial.secondary_ids:
                        # Confronto semplice in stringa JSON
                        secondary_ids_str = json.dumps(trial.secondary_ids).lower()
                        if trial_id.lower() in secondary_ids_str:
                            trials_db.append(trial)
                            trials_db_set.add(trial)
                            continue
                            
                        # Confronto specifico e normalizzato con ogni ID secondario
                        found_in_secondary = False
                        for sec_id in trial.secondary_ids:
                            if 'id' in sec_id:
                                sec_id_value = sec_id['id'].lower()
                                # Confronto esatto
                                if trial_id.lower() == sec_id_value:
                                    found_in_secondary = True
                                    break
                                # Confronto parziale
                                if trial_id.lower() in sec_id_value:
                                    found_in_secondary = True
                                    break
                                # Confronto normalizzato (senza trattini/spazi)
                                norm_sec_id = sec_id_value.replace('-', '').replace(' ', '')
                                if normalized_trial_id in norm_sec_id:
                                    found_in_secondary = True
                                    break
                                    
                        if found_in_secondary:
                            trials_db.append(trial)
                            trials_db_set.add(trial)
                            continue
                
                if trials_db:
                    return jsonify([trial.to_dict() for trial in trials_db])
                
                # 3. Cerca corrispondenza nei dettagli del trial (descrizione e criteri)
                # Questa è una soluzione temporanea per supportare ID di protocollo interni
                # che potrebbero essere menzionati nella descrizione o nei criteri
                all_trials = get_all_trials_db()
                
                for trial in all_trials:
                    # Cerca nell'ID e nel titolo
                    if (trial['id'] and trial_id.lower() in trial['id'].lower()) or \
                       (trial['title'] and trial_id.lower() in trial['title'].lower()):
                        matching_trials.append(trial)
                        continue
                        
                    # Cerca nella descrizione
                    if trial['description'] and trial_id.lower() in trial['description'].lower():
                        matching_trials.append(trial)
                        continue
                    
                    # Cerca nei criteri di inclusione ed esclusione
                    criteria_texts = []
                    for criterion in trial.get('inclusion_criteria', []) + trial.get('exclusion_criteria', []):
                        if 'text' in criterion:
                            criteria_texts.append(criterion['text'].lower())
                    
                    if any(trial_id.lower() in text for text in criteria_texts):
                        matching_trials.append(trial)
                
                if matching_trials:
                    # Rimuovi duplicati se ci sono
                    unique_ids = set()
                    unique_trials = []
                    for trial in matching_trials:
                        if trial['id'] not in unique_ids:
                            unique_ids.add(trial['id'])
                            unique_trials.append(trial)
                    
                    return jsonify(unique_trials)
                
                # 4. Fallback: cerca nel file JSON se il database non ha risultati
                trials_json = get_all_trials_json()
                matching_trials_json = []
                
                for t in trials_json:
                    # Cerca corrispondenza in tutti i campi rilevanti
                    if ((t.get('id') and trial_id.lower() in t['id'].lower()) or 
                        (t.get('title') and trial_id.lower() in t['title'].lower()) or
                        (t.get('description') and trial_id.lower() in t['description'].lower())):
                        matching_trials_json.append(t)
                        continue
                        
                    # Cerca nell'ID dell'organizzazione
                    if t.get('org_study_id') and trial_id.lower() in t['org_study_id'].lower():
                        matching_trials_json.append(t)
                        continue
                    
                    # Cerca specificatamente D5087C00001
                    if trial_id.upper() == "D5087C00001" and t.get('org_study_id') == "D5087C00001":
                        matching_trials_json.append(t)
                        continue
                    
                    # Cerca negli ID secondari
                    if t.get('secondary_ids'):
                        # Converte in stringa per cercare dentro
                        secondary_ids_str = json.dumps(t['secondary_ids'])
                        if trial_id.lower() in secondary_ids_str.lower():
                            matching_trials_json.append(t)
                            continue
                    
                    # Cerca nei criteri
                    criteria_matched = False
                    for criterion in t.get('inclusion_criteria', []) + t.get('exclusion_criteria', []):
                        if 'text' in criterion and trial_id.lower() in criterion['text'].lower():
                            criteria_matched = True
                            break
                    
                    if criteria_matched:
                        matching_trials_json.append(t)
                
                if matching_trials_json:
                    return jsonify(matching_trials_json)
                
            except Exception as e:
                logging.error(f"Errore nella ricerca per ID del protocollo: {str(e)}")
                pass
            
            # Fai un ultimo tentativo di cercare su ClinicalTrials.gov prima di usare i metodi di ricerca locali
            try:
                # Importa il modulo per il recupero diretto da ClinicalTrials.gov
                from fetch_trial_by_id import fetch_and_save_trial_by_id
                
                logging.info(f"Ultimo tentativo di cercare il trial con ID '{trial_id}' su ClinicalTrials.gov")
                
                # Recupera il trial da ClinicalTrials.gov
                fetched_trial = fetch_and_save_trial_by_id(trial_id, current_app._get_current_object())
                
                if fetched_trial:
                    logging.info(f"Trial trovato su ClinicalTrials.gov e salvato localmente: {fetched_trial['id']}")
                    return jsonify([fetched_trial])
            except Exception as e:
                logging.error(f"Errore nel tentativo finale di cercare il trial su ClinicalTrials.gov: {str(e)}")
            
            # Cerca di nuovo tra tutti i trial disponibili, specificamente per i pattern di ID del protocollo
            # Riconosce vari formati di ID (NCT, D5087C00001, EudraCT, Registry)
            has_pattern = any([
                trial_id.upper().startswith('NCT'),
                trial_id.startswith('D') and any(c.isdigit() for c in trial_id), 
                bool(re.match(r'^\d{4}-\d{6}-\d{2}', trial_id)),  # EudraCT pattern
                len(trial_id.replace('-', '').replace(' ', '')) > 8 and any(c.isdigit() for c in trial_id)
            ])
            
            if has_pattern:
                # Cerca in tutti i trial, sia nel database che nel file JSON
                all_trials = []
                
                # Cerca prima nel database
                trials_db = get_all_trials_db()
                if trials_db:
                    all_trials.extend(trials_db)
                
                # Cerca nel file JSON se necessario
                if not all_trials:
                    trials_json = get_all_trials_json()
                    if trials_json:
                        all_trials.extend(trials_json)
                
                # Filtra manualmente cercando in tutti i campi
                protocol_matches = []
                # Normalizza l'ID ricercato rimuovendo trattini e spazi
                normalized_trial_id = trial_id.lower().replace('-', '').replace(' ', '')
                
                for t in all_trials:
                    # ID NCT principale
                    if t.get('id') and trial_id.lower() in t['id'].lower():
                        protocol_matches.append(t)
                        continue
                        
                    # ID dell'organizzazione (es. D5087C00001)
                    if t.get('org_study_id'):
                        org_id = t['org_study_id'].lower()
                        # Confronto semplice
                        if trial_id.lower() in org_id:
                            protocol_matches.append(t)
                            continue
                        # Confronto normalizzato (senza trattini/spazi)
                        if normalized_trial_id in org_id.replace('-', '').replace(' ', ''):
                            protocol_matches.append(t)
                            continue
                    
                    # ID secondari (es. EudraCT Number, Registry Identifier)
                    if t.get('secondary_ids'):
                        secondary_ids_str = json.dumps(t['secondary_ids']).lower()
                        # Confronto semplice nelle stringhe JSON
                        if trial_id.lower() in secondary_ids_str:
                            protocol_matches.append(t)
                            continue
                        
                        # Confronto specifico con ogni ID secondario
                        for sec_id in t['secondary_ids']:
                            if 'id' in sec_id:
                                sec_id_value = sec_id['id'].lower()
                                # Confronto esatto
                                if trial_id.lower() == sec_id_value:
                                    protocol_matches.append(t)
                                    break
                                # Confronto parziale
                                if trial_id.lower() in sec_id_value:
                                    protocol_matches.append(t)
                                    break
                                # Confronto normalizzato (senza trattini/spazi)
                                if normalized_trial_id in sec_id_value.replace('-', '').replace(' ', ''):
                                    protocol_matches.append(t)
                                    break
                        
                        # Se l'ID è già stato trovato, continua con il prossimo trial
                        if t in protocol_matches:
                            continue
                    
                    # Cerca nella descrizione
                    if t.get('description') and trial_id.lower() in t['description'].lower():
                        protocol_matches.append(t)
                
                if protocol_matches:
                    return jsonify(protocol_matches)
                
            # Se ancora non trovato, restituisci array vuoto
            return jsonify([])
        
        # Altrimenti recupera tutti i trial dal database
        trials = get_all_trials_db()
        return jsonify(trials)
    except Exception as e:
        logging.error(f"Error fetching trials: {str(e)}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@bp.route('/process', methods=['POST'])
def process():
    """Process uploaded PDF or text input and find matching trials."""
    try:
        # Check if we have a file upload or text input
        text = ""
        pdf_filename = None
        
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            if file.filename.endswith('.pdf'):
                # Generate a unique filename to avoid collisions
                unique_filename = f"{str(uuid.uuid4())}.pdf"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                
                # Save the file to disk
                file.save(file_path)
                
                # Store the filename in session for later retrieval
                session['pdf_filename'] = unique_filename
                pdf_filename = unique_filename
                
                # Extract text from PDF
                text = extract_text_from_pdf(file_path)
            else:
                return jsonify({'error': 'Only PDF files are supported'}), 400
        elif 'text' in request.form and request.form['text'].strip():
            text = request.form['text']
        else:
            return jsonify({'error': 'No input provided. Please upload a PDF or enter text.'}), 400
        
        # Extract features using local LLM
        features = extract_features(text)
        
        # Format features in a concise way for display
        concise_features = format_features_concise(features)
        
        # Match with clinical trials
        trial_matches = match_trials_db(features)
        
        # Return extracted features and matching trials
        return jsonify({
            'features': concise_features,
            'matches': trial_matches,
            'text': text,
            'pdf_filename': pdf_filename
        })
        
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

# Database functions

def get_all_trials_db():
    """
    Get all available clinical trials from the database.
    
    Returns:
        list: All clinical trials as dictionaries
    """
    try:
        trials = ClinicalTrial.query.all()
        return [trial.to_dict() for trial in trials]
    except Exception as e:
        logging.error(f"Error retrieving trials from DB: {str(e)}")
        # Se il database non è disponibile, usa il vecchio metodo
        return get_all_trials_json()

def get_all_trials_json():
    """
    Get all available clinical trials from the JSON file (fallback).
    
    Returns:
        list: All clinical trials
    """
    try:
        with open('trials_int.json', 'r') as f:
            trials = json.load(f)
        return trials
    except Exception as e:
        logging.error(f"Error loading trials from JSON: {str(e)}")
        return []

def match_trials_db(patient_features):
    """
    Match patient features with available clinical trials using the hybrid approach.
    
    Questo metodo utilizza un approccio ibrido che combina:
    1. Filtro veloce con PostgreSQL per criteri oggettivi (età, genere, stato trial)
    2. Valutazione semantica con LLM per criteri complessi
    
    Args:
        patient_features: Caratteristiche estratte del paziente
        
    Returns:
        list: Trial clinici corrispondenti con spiegazioni e punteggi
    """
    try:
        logging.info("Avvio ricerca trial con approccio ibrido PostgreSQL + LLM")
        
        # Istanzia il processore di query ibrido
        try:
            hybrid_searcher = get_hybrid_query()
            use_hybrid = True
            logging.info("Utilizzando approccio ibrido con LLM")
        except Exception as hybrid_error:
            logging.warning(f"Errore nell'inizializzazione dell'approccio ibrido: {str(hybrid_error)}")
            logging.info("Fallback all'approccio tradizionale senza LLM")
            use_hybrid = False
        
        # APPROCCIO IBRIDO
        if use_hybrid:
            try:
                # Filtra i trial utilizzando l'approccio ibrido
                hybrid_results = hybrid_searcher.filter_trials_by_criteria(patient_features)
                
                if hybrid_results:
                    matched_trials = []
                    
                    for trial_data in hybrid_results:
                        # Estrai valutazione semantica
                        semantic_match = trial_data.get('semantic_match')
                        match_explanation = trial_data.get('match_explanation', '')
                        semantic_score = trial_data.get('match_score')
                        
                        # Inizializza match e non-match
                        matches = []
                        non_matches = []
                        
                        # Elabora i risultati del matching
                        if 'matching_criteria' in trial_data:
                            for criterion in trial_data.get('matching_criteria', []):
                                matches.append({
                                    'criterion': criterion,
                                    'matches': True,
                                    'explanation': "Criterio soddisfatto (analisi semantica)"
                                })
                        
                        if 'conflicting_criteria' in trial_data:
                            for criterion in trial_data.get('conflicting_criteria', []):
                                non_matches.append({
                                    'criterion': criterion,
                                    'matches': False, 
                                    'explanation': "Criterio non soddisfatto (analisi semantica)"
                                })
                        
                        # Calcola punteggio e percentuale
                        match_score = len(matches)
                        total_criteria = match_score + len(non_matches)
                        match_percentage = (match_score / total_criteria * 100) if total_criteria > 0 else 0
                        
                        # Se non ci sono criteri valutati ma c'è un punteggio semantico, usalo
                        if total_criteria == 0 and semantic_score is not None:
                            match_percentage = semantic_score
                        
                        # Aggiungi il trial se supera la soglia (o se ha una valutazione semantica positiva)
                        if match_percentage >= 50 or (semantic_match is not None and semantic_match in [True, 'true', 'True']):
                            matched_trial = {
                                'trial_id': trial_data.get('id'),
                                'title': trial_data.get('title'),
                                'phase': trial_data.get('phase'),
                                'match_percentage': round(match_percentage, 1),
                                'matches': matches,
                                'non_matches': non_matches,
                                'description': trial_data.get('description', ''),
                                'semantic_evaluation': {
                                    'match': semantic_match,
                                    'explanation': match_explanation,
                                    'score': semantic_score
                                }
                            }
                            matched_trials.append(matched_trial)
                    
                    # Ordina per percentuale di match (decrescente)
                    matched_trials.sort(key=lambda x: x['match_percentage'], reverse=True)
                    
                    logging.info(f"Trovati {len(matched_trials)} trial compatibili con approccio ibrido")
                    return matched_trials
            except Exception as hybrid_process_error:
                logging.error(f"Errore nell'elaborazione ibrida: {str(hybrid_process_error)}")
                logging.info("Fallback all'approccio tradizionale")
        
        # APPROCCIO TRADIZIONALE (FALLBACK)
        logging.info("Utilizzando approccio tradizionale per match_trials_db")
        # Get trials from database
        trials = get_all_trials_db()
        
        matched_trials = []
        
        for trial in trials:
            # Initialize match score and explanations
            match_score = 0
            total_criteria = 0
            matches = []
            non_matches = []
            
            # Check inclusion criteria
            for criterion in trial.get('inclusion_criteria', []):
                total_criteria += 1
                match_result = check_criterion_match(criterion, patient_features)
                
                if match_result['matches']:
                    match_score += 1
                    matches.append(match_result)
                else:
                    non_matches.append(match_result)
            
            # Check exclusion criteria
            for criterion in trial.get('exclusion_criteria', []):
                total_criteria += 1
                match_result = check_criterion_match(criterion, patient_features)
                
                # For exclusion criteria, we want it NOT to match
                if not match_result['matches']:
                    match_score += 1
                    matches.append({
                        'criterion': criterion,
                        'matches': True,
                        'explanation': "Patient does not meet exclusion criterion"
                    })
                else:
                    non_matches.append({
                        'criterion': criterion,
                        'matches': False,
                        'explanation': "Patient meets exclusion criterion: " + match_result['explanation']
                    })
            
            # Calculate match percentage
            match_percentage = (match_score / total_criteria * 100) if total_criteria > 0 else 0
            
            # Add to matched trials if score is above threshold
            if match_percentage >= 50:  # Minimum 50% match
                matched_trial = {
                    'trial_id': trial.get('id'),
                    'title': trial.get('title'),
                    'phase': trial.get('phase'),
                    'match_percentage': round(match_percentage, 1),
                    'matches': matches,
                    'non_matches': non_matches,
                    'description': trial.get('description', ''),
                    # Aggiungiamo un campo per informare che non è stata usata l'analisi semantica
                    'semantic_evaluation': {
                        'match': None,
                        'explanation': "Valutazione semantica non disponibile. Configura un modello LLM locale per risultati più accurati.",
                        'score': None
                    }
                }
                matched_trials.append(matched_trial)
        
        # Sort by match percentage (descending)
        matched_trials.sort(key=lambda x: x['match_percentage'], reverse=True)
        
        logging.info(f"Trovati {len(matched_trials)} trial compatibili con approccio tradizionale")
        return matched_trials
    
    except Exception as e:
        logging.error(f"Error matching trials: {str(e)}")
        # Return empty list in case of error
        return []

def check_criterion_match(criterion, patient_features):
    """
    Check if a patient matches a specific clinical trial criterion.
    
    Args:
        criterion: The criterion to check
        patient_features: The patient's extracted features
        
    Returns:
        dict: Match result with explanation
    """
    criterion_text = criterion.get('text', '').lower()
    criterion_type = criterion.get('type', '').lower()
    
    result = {
        'criterion': criterion,
        'matches': False,
        'explanation': ""
    }
    
    # Age criteria
    if 'age' in criterion_type or re.search(r'\bage\b', criterion_text):
        if patient_features['age']['value'] is not None:
            age = patient_features['age']['value']
            
            # Check for minimum age
            min_age_match = re.search(r'(?:age|patients?)\s*(?:>=|≥|>=|greater than or equal to|at least|minimum|>|greater than)\s*(\d+)', criterion_text)
            if min_age_match and age < int(min_age_match.group(1)):
                result['explanation'] = f"Patient age {age} is below minimum required age {min_age_match.group(1)}"
                return result
            
            # Check for maximum age
            max_age_match = re.search(r'(?:age|patients?)\s*(?:<=|≤|<=|less than or equal to|maximum|<|less than)\s*(\d+)', criterion_text)
            if max_age_match and age > int(max_age_match.group(1)):
                result['explanation'] = f"Patient age {age} is above maximum allowed age {max_age_match.group(1)}"
                return result
            
            result['matches'] = True
            result['explanation'] = f"Patient age {age} meets criterion"
        else:
            result['explanation'] = "Patient age unknown"
    
    # Gender criteria
    elif 'gender' in criterion_type or re.search(r'\b(?:male|female|gender|sex)\b', criterion_text):
        if patient_features['gender']['value'] is not None:
            gender = patient_features['gender']['value'].lower()
            
            if 'male' in criterion_text and gender == 'male':
                result['matches'] = True
                result['explanation'] = "Patient is male as required"
            elif 'female' in criterion_text and gender == 'female':
                result['matches'] = True
                result['explanation'] = "Patient is female as required"
            else:
                result['explanation'] = f"Patient gender {gender} does not match criterion"
        else:
            result['explanation'] = "Patient gender unknown"
    
    # Diagnosis criteria
    elif 'diagnosis' in criterion_type or re.search(r'\b(?:cancer|tumor|carcinoma|sarcoma|leukemia|lymphoma|melanoma|glioma|blastoma)\b', criterion_text):
        if patient_features['diagnosis']['value'] is not None:
            diagnosis = patient_features['diagnosis']['value'].lower()
            
            # Check for cancer type match
            cancer_types = ['lung', 'breast', 'colorectal', 'ovarian', 'prostate', 'pancreatic']
            patient_cancer_types = [ct for ct in cancer_types if ct in diagnosis]
            
            if patient_cancer_types:
                # Check if any of the patient's cancer types are mentioned in the criterion
                if any(ct in criterion_text for ct in patient_cancer_types):
                    result['matches'] = True
                    result['explanation'] = f"Patient has {diagnosis} which matches criterion"
                else:
                    result['explanation'] = f"Patient has {diagnosis} which does not match required cancer type"
            else:
                # More generic check if specific cancer types not found
                common_terms = ['non-small cell', 'small cell', 'metastatic', 'advanced', 'recurrent', 'invasive']
                matches_general = any(term in diagnosis and term in criterion_text for term in common_terms)
                
                if matches_general:
                    result['matches'] = True
                    result['explanation'] = f"Patient's diagnosis {diagnosis} generally matches criterion"
                else:
                    result['explanation'] = f"Patient's diagnosis {diagnosis} does not match criterion"
        else:
            result['explanation'] = "Patient diagnosis unknown"
    
    # Stage criteria
    elif 'stage' in criterion_type or re.search(r'\bstage\b', criterion_text):
        if patient_features['stage']['value'] is not None:
            stage = patient_features['stage']['value'].upper()
            
            # Extract stage from criterion
            stage_in_criterion = re.search(r'stage\s+(I{1,3}V?|IV|III|II|I)([A-C])?', criterion_text, re.IGNORECASE)
            if stage_in_criterion:
                criterion_stage = stage_in_criterion.group(1).upper() + (stage_in_criterion.group(2) or "").upper()
                
                # Check for exact match
                if stage == criterion_stage:
                    result['matches'] = True
                    result['explanation'] = f"Patient stage {stage} matches criterion exactly"
                # Check for stage ranges (e.g. "stage II-IV")
                elif re.search(r'stage\s+([I]{1,3}V?|IV|III|II|I)\s*[-–—]\s*([I]{1,3}V?|IV|III|II|I)', criterion_text, re.IGNORECASE):
                    range_match = re.search(r'stage\s+([I]{1,3}V?|IV|III|II|I)\s*[-–—]\s*([I]{1,3}V?|IV|III|II|I)', criterion_text, re.IGNORECASE)
                    start_stage = range_match.group(1).upper()
                    end_stage = range_match.group(2).upper()
                    
                    # Convert Roman numerals to integers for comparison
                    roman_to_int = {'I': 1, 'II': 2, 'III': 3, 'IV': 4}
                    patient_stage_num = roman_to_int.get(re.sub(r'[A-C]', '', stage), 0)
                    start_stage_num = roman_to_int.get(start_stage, 0)
                    end_stage_num = roman_to_int.get(end_stage, 0)
                    
                    if start_stage_num <= patient_stage_num <= end_stage_num:
                        result['matches'] = True
                        result['explanation'] = f"Patient stage {stage} is within the range {start_stage}-{end_stage}"
                    else:
                        result['explanation'] = f"Patient stage {stage} is outside the range {start_stage}-{end_stage}"
                else:
                    result['explanation'] = f"Patient stage {stage} does not match criterion stage {criterion_stage}"
            else:
                # If no specific stage in criterion, check for general mentions
                if "early stage" in criterion_text and stage in ["I", "II", "IA", "IB", "IIA", "IIB"]:
                    result['matches'] = True
                    result['explanation'] = f"Patient has early stage disease ({stage})"
                elif "advanced stage" in criterion_text and stage in ["III", "IV", "IIIA", "IIIB", "IIIC", "IV"]:
                    result['matches'] = True
                    result['explanation'] = f"Patient has advanced stage disease ({stage})"
                else:
                    result['explanation'] = f"Cannot determine if patient stage {stage} matches criterion"
        else:
            result['explanation'] = "Patient disease stage unknown"
    
    # ECOG/Performance status criteria
    elif 'performance' in criterion_type or 'ecog' in criterion_type or re.search(r'\b(?:ECOG|performance status|PS)\b', criterion_text):
        if patient_features['ecog']['value'] is not None:
            ecog = patient_features['ecog']['value']
            
            # Check for specific ECOG value
            ecog_in_criterion = re.search(r'ECOG\s*(?:PS|performance status)?\s*(?:of|:|=)?\s*(\d)', criterion_text, re.IGNORECASE)
            if ecog_in_criterion:
                criterion_ecog = int(ecog_in_criterion.group(1))
                if ecog == criterion_ecog:
                    result['matches'] = True
                    result['explanation'] = f"Patient ECOG {ecog} matches criterion exactly"
                else:
                    result['explanation'] = f"Patient ECOG {ecog} does not match criterion ECOG {criterion_ecog}"
            
            # Check for ECOG range (e.g. "ECOG 0-2")
            elif re.search(r'ECOG\s*(?:PS|performance status)?\s*(?:of|:|=)?\s*(\d)\s*[-–—]\s*(\d)', criterion_text, re.IGNORECASE):
                range_match = re.search(r'ECOG\s*(?:PS|performance status)?\s*(?:of|:|=)?\s*(\d)\s*[-–—]\s*(\d)', criterion_text, re.IGNORECASE)
                min_ecog = int(range_match.group(1))
                max_ecog = int(range_match.group(2))
                
                if min_ecog <= ecog <= max_ecog:
                    result['matches'] = True
                    result['explanation'] = f"Patient ECOG {ecog} is within the range {min_ecog}-{max_ecog}"
                else:
                    result['explanation'] = f"Patient ECOG {ecog} is outside the range {min_ecog}-{max_ecog}"
            
            # Check for ECOG using words like "less than or equal to"
            elif re.search(r'ECOG\s*(?:PS|performance status)?\s*(?:<=|≤|less than or equal to)\s*(\d)', criterion_text, re.IGNORECASE):
                match = re.search(r'ECOG\s*(?:PS|performance status)?\s*(?:<=|≤|less than or equal to)\s*(\d)', criterion_text, re.IGNORECASE)
                max_ecog = int(match.group(1))
                
                if ecog <= max_ecog:
                    result['matches'] = True
                    result['explanation'] = f"Patient ECOG {ecog} is less than or equal to {max_ecog}"
                else:
                    result['explanation'] = f"Patient ECOG {ecog} is greater than {max_ecog}"
            else:
                result['explanation'] = f"Cannot determine if patient ECOG {ecog} matches criterion"
        else:
            result['explanation'] = "Patient ECOG status unknown"
    
    # Mutation criteria
    elif 'mutation' in criterion_type:
        # Get patient mutations as a list of values
        patient_mutations = [mutation['value'].lower() for mutation in patient_features['mutations']]
        
        # Check for common mutation types
        common_mutations = {
            'egfr': ['egfr', 'epidermal growth factor receptor'],
            'alk': ['alk', 'anaplastic lymphoma kinase'],
            'ros1': ['ros1'],
            'braf': ['braf', 'braf v600e', 'braf v600'],
            'kras': ['kras', 'kras g12c'],
            'her2': ['her2', 'erbb2'],
            'brca': ['brca1', 'brca2'],
            'pd-l1': ['pd-l1', 'pdl1'],
            'msi': ['msi-h', 'microsatellite instability-high'],
            'tmb': ['tmb-high', 'tumor mutational burden-high']
        }
        
        # Check if patient has/doesn't have mutations mentioned in criterion
        for mutation_type, aliases in common_mutations.items():
            if any(alias in criterion_text for alias in aliases):
                has_mutation = any(any(alias in mutation for alias in aliases) for mutation in patient_mutations)
                
                # If criterion requires mutation presence
                if 'positive' in criterion_text or 'with mutation' in criterion_text:
                    if has_mutation:
                        result['matches'] = True
                        result['explanation'] = f"Patient is positive for {mutation_type} mutation"
                    else:
                        result['explanation'] = f"Patient is not positive for {mutation_type} mutation"
                    return result
                
                # If criterion requires mutation absence
                if 'negative' in criterion_text or 'without mutation' in criterion_text or 'wild-type' in criterion_text:
                    if not has_mutation:
                        result['matches'] = True
                        result['explanation'] = f"Patient is negative for {mutation_type} mutation"
                    else:
                        result['explanation'] = f"Patient is not negative for {mutation_type} mutation"
                    return result
        
        # Generic mutation check if specific types not found
        has_any_mutation = len(patient_mutations) > 0
        requires_any_mutation = 'mutation' in criterion_text and ('positive' in criterion_text or 'with mutation' in criterion_text)
        requires_no_mutation = 'mutation' in criterion_text and ('negative' in criterion_text or 'without mutation' in criterion_text)
        
        if requires_any_mutation:
            if has_any_mutation:
                result['matches'] = True
                result['explanation'] = "Patient has mutations as required"
            else:
                result['explanation'] = "Patient does not have any mutations"
        elif requires_no_mutation:
            if not has_any_mutation:
                result['matches'] = True
                result['explanation'] = "Patient has no mutations as required"
            else:
                result['explanation'] = "Patient has mutations which are not allowed"
        else:
            result['explanation'] = "Cannot determine if patient's mutation status matches criterion"
    
    # Metastasis criteria
    elif 'metastasis' in criterion_type or re.search(r'\b(?:metastases|metastasis|metastatic)\b', criterion_text):
        # Get patient metastases as a list of values
        patient_metastases = [metastasis['value'].lower() for metastasis in patient_features['metastases']]
        
        # Check for brain metastases specifically (common exclusion criterion)
        if 'brain' in criterion_text and 'metastases' in criterion_text:
            has_brain_mets = any('brain' in mets for mets in patient_metastases)
            
            # If criterion requires absence of brain metastases
            if 'no ' in criterion_text or 'without ' in criterion_text or 'absence of ' in criterion_text:
                if not has_brain_mets:
                    result['matches'] = True
                    result['explanation'] = "Patient does not have brain metastases as required"
                else:
                    result['explanation'] = "Patient has brain metastases which are not allowed"
            # If criterion requires presence of brain metastases
            else:
                if has_brain_mets:
                    result['matches'] = True
                    result['explanation'] = "Patient has brain metastases as required"
                else:
                    result['explanation'] = "Patient does not have brain metastases"
            return result
        
        # Generic metastasis check
        has_any_metastases = len(patient_metastases) > 0
        requires_metastatic = 'metastatic' in criterion_text and not ('no ' in criterion_text or 'not ' in criterion_text)
        requires_non_metastatic = 'non-metastatic' in criterion_text or ('metastatic' in criterion_text and ('no ' in criterion_text or 'not ' in criterion_text))
        
        if requires_metastatic:
            if has_any_metastases:
                result['matches'] = True
                result['explanation'] = "Patient has metastatic disease as required"
            else:
                result['explanation'] = "Patient does not have metastatic disease"
        elif requires_non_metastatic:
            if not has_any_metastases:
                result['matches'] = True
                result['explanation'] = "Patient has non-metastatic disease as required"
            else:
                result['explanation'] = "Patient has metastatic disease which does not match criterion"
        else:
            result['explanation'] = "Cannot determine if patient's metastatic status matches criterion"
    
    # Prior treatment criteria
    elif 'treatment' in criterion_type or re.search(r'\b(?:prior|previous|therapy|treatment)\b', criterion_text):
        # Get patient prior treatments as a list of values
        prior_treatments = [treatment['value'].lower() for treatment in patient_features['previous_treatments']]
        
        # Check for common treatment types
        common_treatments = {
            'chemotherapy': ['chemotherapy', 'cytotoxic'],
            'radiation': ['radiation', 'radiotherapy'],
            'immunotherapy': ['immunotherapy', 'checkpoint inhibitor', 'anti-pd-1', 'anti-pd-l1', 'anti-ctla-4'],
            'targeted therapy': ['targeted therapy', 'tyrosine kinase inhibitor', 'tki', 'egfr-tki'],
            'surgery': ['surgery', 'resection', 'surgical']
        }
        
        for treatment_type, aliases in common_treatments.items():
            if any(alias in criterion_text for alias in aliases):
                has_prior_treatment = any(any(alias in treatment for alias in aliases) for treatment in prior_treatments)
                
                # If criterion requires no prior treatment
                if 'no prior' in criterion_text or 'without prior' in criterion_text:
                    if not has_prior_treatment:
                        result['matches'] = True
                        result['explanation'] = f"Patient has not received prior {treatment_type} as required"
                    else:
                        result['explanation'] = f"Patient has received prior {treatment_type} which is not allowed"
                    return result
                
                # If criterion requires prior treatment
                if 'prior' in criterion_text or 'previous' in criterion_text:
                    if has_prior_treatment:
                        result['matches'] = True
                        result['explanation'] = f"Patient has received prior {treatment_type} as required"
                    else:
                        result['explanation'] = f"Patient has not received prior {treatment_type}"
                    return result
        
        # Check for treatment-naive (no prior treatment)
        if 'treatment-naive' in criterion_text or 'treatment naive' in criterion_text:
            if len(prior_treatments) == 0:
                result['matches'] = True
                result['explanation'] = "Patient is treatment-naive as required"
            else:
                result['explanation'] = "Patient has received prior treatment"
            return result
        
        # Generic treatment check if specific types not found
        has_any_treatment = len(prior_treatments) > 0
        requires_any_treatment = 'prior treatment' in criterion_text and not ('no prior' in criterion_text or 'without prior' in criterion_text)
        requires_no_treatment = 'no prior treatment' in criterion_text or 'without prior treatment' in criterion_text
        
        if requires_any_treatment:
            if has_any_treatment:
                result['matches'] = True
                result['explanation'] = "Patient has received prior treatment as required"
            else:
                result['explanation'] = "Patient has not received prior treatment"
        elif requires_no_treatment:
            if not has_any_treatment:
                result['matches'] = True
                result['explanation'] = "Patient has not received prior treatment as required"
            else:
                result['explanation'] = "Patient has received prior treatment which is not allowed"
        else:
            result['explanation'] = "Cannot determine if patient's treatment history matches criterion"
    
    # General and other criteria types - more lenient matching
    else:
        # For general criteria, we'll assume they match if not clearly in the categories above
        # This is a simplification that can be improved with more sophisticated matching
        result['matches'] = True
        result['explanation'] = "Criterion assumed to match (general criterion)"
    
    return result
