"""
Modulo per l'integrazione con modelli LLM locali tramite llama.cpp.
Questo modulo fornisce funzionalità per l'utilizzo di modelli LLM locali (come Mistral, LLaMA)
per l'elaborazione di testo e l'analisi semantica in MedMatchINT.
"""

import os
import logging
import subprocess
import json
import tempfile
import threading
from typing import Dict, Any, List, Optional, Tuple, Union

from config import (
    LLAMA_CPP_PATH, LLM_MODEL_PATH, LLM_CONTEXT_SIZE,
    LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_TIMEOUT,
    LLM_EXTRA_PARAMS
)

logger = logging.getLogger(__name__)

# Variabile globale per tracciare la disponibilità dell'LLM
LLM_AVAILABLE = False
_llm_availability_checked = False
_llm_availability_lock = threading.Lock()

# Messaggio di errore standard per quando l'LLM non è disponibile
LLM_ERROR_MESSAGE = "Il modello LLM non è disponibile. Utilizzando metodi alternativi per l'analisi."


class LLMProcessor:
    """
    Classe per l'elaborazione di testo utilizzando un LLM locale tramite llama.cpp.
    Fornisce metodi per generare risposte, analizzare testo e estrarre dati strutturati
    utilizzando un modello LLM installato localmente.
    """
    
    def __init__(self):
        """Inizializza il processore LLM."""
        self.llama_cpp_path = LLAMA_CPP_PATH
        self.model_path = LLM_MODEL_PATH
        self.context_size = LLM_CONTEXT_SIZE
        self.temperature = LLM_TEMPERATURE
        self.max_tokens = LLM_MAX_TOKENS
        self.timeout = LLM_TIMEOUT
        self.extra_params = LLM_EXTRA_PARAMS
        
        # Verifica la disponibilità dell'LLM
        self._check_llm_availability()
        
    def _check_llm_availability(self) -> bool:
        """
        Verifica se l'LLM è disponibile per l'uso.
        
        Returns:
            bool: True se l'LLM è disponibile, False altrimenti
        """
        global LLM_AVAILABLE, _llm_availability_checked
        
        # Se abbiamo già verificato, usa il valore memorizzato
        if _llm_availability_checked:
            return LLM_AVAILABLE
            
        with _llm_availability_lock:
            # Controllo doppio per evitare verifiche multiple in parallelo
            if _llm_availability_checked:
                return LLM_AVAILABLE
                
            # Verifica se i percorsi necessari sono configurati
            if not self.llama_cpp_path or not self.model_path:
                logger.warning("LLM non configurato: percorsi mancanti")
                LLM_AVAILABLE = False
                _llm_availability_checked = True
                return False
                
            # Verifica se il modello esiste
            if not os.path.exists(self.model_path):
                logger.warning(f"Modello LLM non trovato: {self.model_path}")
                LLM_AVAILABLE = False
                _llm_availability_checked = True
                return False
                
            # Verifica se l'eseguibile esiste
            llama_exec = os.path.join(self.llama_cpp_path, "build/bin/main")
            if not os.path.exists(llama_exec):
                # Prova percorso alternativo
                llama_exec = os.path.join(self.llama_cpp_path, "main")
                if not os.path.exists(llama_exec):
                    logger.warning(f"Eseguibile llama.cpp non trovato in: {self.llama_cpp_path}")
                    LLM_AVAILABLE = False
                    _llm_availability_checked = True
                    return False
                    
            # Test rapido dell'LLM
            try:
                logger.info("Verifico disponibilità LLM con test rapido...")
                cmd = [
                    llama_exec,
                    "-m", self.model_path,
                    "-p", "test",
                    "-n", "1",
                    "--temp", "0",
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    logger.info("LLM disponibile e funzionante")
                    LLM_AVAILABLE = True
                    _llm_availability_checked = True
                    return True
                else:
                    logger.warning(f"Test LLM fallito con codice: {result.returncode}")
                    logger.debug(f"Stderr: {result.stderr}")
                    LLM_AVAILABLE = False
                    _llm_availability_checked = True
                    return False
                    
            except (subprocess.SubprocessError, OSError, Exception) as e:
                logger.warning(f"Errore durante il test dell'LLM: {str(e)}")
                LLM_AVAILABLE = False
                _llm_availability_checked = True
                return False
    
    def generate_response(self, prompt: str, 
                         temperature: Optional[float] = None,
                         max_tokens: Optional[int] = None) -> str:
        """
        Genera una risposta testuale utilizzando l'LLM locale.
        
        Args:
            prompt: Il prompt da inviare all'LLM
            temperature: Temperatura per la generazione (opzionale)
            max_tokens: Numero massimo di token da generare (opzionale)
            
        Returns:
            str: La risposta generata dall'LLM
        """
        if not self._check_llm_availability():
            logger.warning("LLM non disponibile per generate_response")
            return "[LLM non disponibile]"
            
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        # Prepara il comando
        llama_exec = os.path.join(self.llama_cpp_path, "build/bin/main")
        if not os.path.exists(llama_exec):
            llama_exec = os.path.join(self.llama_cpp_path, "main")
            
        cmd = [
            llama_exec,
            "-m", self.model_path,
            "-c", str(self.context_size),
            "-n", str(tokens),
            "--temp", str(temp),
            "--repeat_penalty", "1.1",
        ]
        
        # Aggiungi parametri extra se specificati
        if self.extra_params:
            cmd.extend(self.extra_params.split())
            
        try:
            # Usa un file temporaneo per il prompt per gestire prompt lunghi
            with tempfile.NamedTemporaryFile(mode='w+', encoding='utf-8', delete=False) as f:
                prompt_file = f.name
                f.write(prompt)
                
            cmd.extend(["-f", prompt_file])
            
            # Esegui llama.cpp
            logger.debug(f"Esecuzione comando LLM: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            # Pulisci il file temporaneo
            try:
                os.unlink(prompt_file)
            except:
                pass
                
            if result.returncode != 0:
                logger.error(f"Errore nell'esecuzione dell'LLM (codice {result.returncode})")
                logger.debug(f"Stderr: {result.stderr}")
                return "[Errore LLM]"
                
            # Estrai la risposta (rimuovendo il prompt iniziale)
            output = result.stdout
            prompt_end_index = output.find(prompt)
            if prompt_end_index != -1:
                prompt_end_index += len(prompt)
                response = output[prompt_end_index:].strip()
            else:
                response = output.strip()
                
            return response
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout durante l'esecuzione dell'LLM ({self.timeout}s)")
            return "[Timeout LLM]"
            
        except Exception as e:
            logger.error(f"Errore durante l'uso dell'LLM: {str(e)}")
            return "[Errore LLM]"
    
    def extract_structured_data(self, text: str, 
                              schema: Dict[str, Any],
                              system_instruction: str = "") -> Dict[str, Any]:
        """
        Estrae dati strutturati da un testo utilizzando l'LLM.
        
        Args:
            text: Il testo da analizzare
            schema: Lo schema dei dati da estrarre
            system_instruction: Istruzioni di sistema per l'LLM
            
        Returns:
            Dict[str, Any]: I dati strutturati estratti
        """
        if not self._check_llm_availability():
            logger.warning("LLM non disponibile per extract_structured_data")
            return {"error": "LLM non disponibile"}
            
        # Crea un prompt specifico per l'estrazione di dati strutturati
        schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
        
        prompt = f"""
{system_instruction}

Analizza il seguente testo e estrai le informazioni richieste secondo lo schema JSON specificato.
Rispondi SOLO con un oggetto JSON valido, senza testo aggiuntivo prima o dopo.

SCHEMA JSON:
{schema_str}

TESTO DA ANALIZZARE:
{text}

JSON ESTRATTO:
"""

        # Genera la risposta
        response = self.generate_response(prompt, temperature=0.1)
        
        # Estrai il JSON dalla risposta
        try:
            # Cerca di identificare il blocco JSON
            json_start = response.find('{')
            json_end = response.rfind('}')
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_str = response[json_start:json_end+1]
                return json.loads(json_str)
            else:
                logger.warning("Impossibile trovare JSON valido nella risposta dell'LLM")
                return {"error": "Formato risposta non valido", "raw_response": response}
                
        except json.JSONDecodeError as e:
            logger.warning(f"Errore nel parsing JSON dalla risposta LLM: {str(e)}")
            return {"error": "JSON non valido", "raw_response": response}
    
    def extract_patient_features(self, document_text: str) -> Dict[str, Any]:
        """
        Estrae le caratteristiche del paziente da un documento di testo utilizzando l'LLM.
        
        Args:
            document_text: Testo del documento paziente
            
        Returns:
            Dict[str, Any]: Caratteristiche estratte del paziente
        """
        if not self._check_llm_availability():
            logger.warning("LLM non disponibile per extract_patient_features")
            return {"error": "LLM non disponibile"}
            
        # Crea uno schema per i dati da estrarre
        schema = {
            "age": "integer or null",
            "gender": "string (male/female/unknown)",
            "diagnosis": "string (primary tumor diagnosis)",
            "stage": "string (cancer stage if applicable)",
            "ecog": "integer or null (ECOG performance status 0-5)",
            "mutations": ["string (list of genetic mutations)"],
            "metastases": ["string (list of metastasis sites)"],
            "previous_treatments": ["string (list of previous treatments)"],
            "lab_values": {"key": "value pairs of relevant lab tests"}
        }
        
        # Istruzioni specifiche per il contesto oncologico
        system_instruction = """
        Sei un assistente oncologico specializzato nell'estrazione di informazioni cliniche.
        Analizza il documento di seguito per estrarre caratteristiche rilevanti del paziente
        per il matching con trial clinici oncologici. Concentrati sui seguenti aspetti:
        
        1. Dati demografici: età, genere
        2. Diagnosi oncologica: tipo di tumore, stadio, grado
        3. Stato di performance: ECOG, Karnofsky
        4. Profilo genetico: mutazioni, marcatori
        5. Metastasi: siti e caratteristiche
        6. Trattamenti precedenti: chirurgia, radioterapia, chemioterapia
        7. Valori di laboratorio: conta ematica, funzionalità renale/epatica
        
        Estrai solo informazioni presenti esplicitamente nel documento. Non inventare o inferire.
        Se un'informazione non è presente, indica null o lista vuota dove appropriato.
        """
        
        # Estrai i dati utilizzando l'LLM
        extracted_data = self.extract_structured_data(
            document_text,
            schema,
            system_instruction
        )
        
        # Normalizza i dati estratti
        normalized_data = {}
        
        # Gestisci il caso in cui l'estrazione fallisca
        if "error" in extracted_data:
            logger.warning(f"Errore nell'estrazione dei dati: {extracted_data['error']}")
            return {"error": extracted_data["error"]}
            
        # Normalizza età
        if "age" in extracted_data:
            try:
                normalized_data["age"] = int(extracted_data["age"]) if extracted_data["age"] else None
            except (ValueError, TypeError):
                normalized_data["age"] = None
                
        # Normalizza genere
        if "gender" in extracted_data:
            gender = str(extracted_data["gender"]).lower() if extracted_data["gender"] else "unknown"
            if gender in ["m", "male", "uomo", "maschio"]:
                normalized_data["gender"] = "male"
            elif gender in ["f", "female", "donna", "femmina"]:
                normalized_data["gender"] = "female"
            else:
                normalized_data["gender"] = "unknown"
                
        # Normalizza diagnosi
        if "diagnosis" in extracted_data:
            normalized_data["diagnosis"] = str(extracted_data["diagnosis"]) if extracted_data["diagnosis"] else ""
            
        # Normalizza stadio
        if "stage" in extracted_data:
            normalized_data["stage"] = str(extracted_data["stage"]) if extracted_data["stage"] else ""
            
        # Normalizza ECOG
        if "ecog" in extracted_data:
            try:
                ecog_value = int(extracted_data["ecog"]) if extracted_data["ecog"] is not None else None
                if ecog_value is not None and 0 <= ecog_value <= 5:
                    normalized_data["ecog"] = ecog_value
                else:
                    normalized_data["ecog"] = None
            except (ValueError, TypeError):
                normalized_data["ecog"] = None
                
        # Normalizza mutazioni
        if "mutations" in extracted_data:
            if isinstance(extracted_data["mutations"], list):
                normalized_data["mutations"] = [str(m) for m in extracted_data["mutations"] if m]
            else:
                normalized_data["mutations"] = []
                
        # Normalizza metastasi
        if "metastases" in extracted_data:
            if isinstance(extracted_data["metastases"], list):
                normalized_data["metastases"] = [str(m) for m in extracted_data["metastases"] if m]
            else:
                normalized_data["metastases"] = []
                
        # Normalizza trattamenti precedenti
        if "previous_treatments" in extracted_data:
            if isinstance(extracted_data["previous_treatments"], list):
                normalized_data["previous_treatments"] = [str(t) for t in extracted_data["previous_treatments"] if t]
            else:
                normalized_data["previous_treatments"] = []
                
        # Normalizza valori di laboratorio
        if "lab_values" in extracted_data and isinstance(extracted_data["lab_values"], dict):
            normalized_data["lab_values"] = {
                str(k): str(v) for k, v in extracted_data["lab_values"].items() if k and v
            }
        else:
            normalized_data["lab_values"] = {}
            
        return normalized_data
        
    def evaluate_patient_trial_match(self, 
                                   patient_features: Dict[str, Any],
                                   trial: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valuta la compatibilità tra un paziente e un trial clinico usando l'LLM.
        
        Args:
            patient_features: Caratteristiche del paziente
            trial: Dati del trial clinico
            
        Returns:
            Dict[str, Any]: Risultato della valutazione
        """
        if not self._check_llm_availability():
            logger.warning("LLM non disponibile per evaluate_patient_trial_match")
            return {
                "match": "unknown",
                "score": 0,
                "explanation": "LLM non disponibile per la valutazione semantica.",
                "criteria_met": [],
                "criteria_not_met": []
            }
            
        # Prepara il prompt con i dati del paziente e del trial
        patient_json = json.dumps(patient_features, ensure_ascii=False, indent=2)
        
        # Semplifica il trial per il prompt (includi solo le informazioni rilevanti)
        simplified_trial = {
            "id": trial.get("id", ""),
            "title": trial.get("title", ""),
            "phase": trial.get("phase", ""),
            "inclusion_criteria": trial.get("inclusion_criteria", []),
            "exclusion_criteria": trial.get("exclusion_criteria", [])
        }
        
        trial_json = json.dumps(simplified_trial, ensure_ascii=False, indent=2)
        
        prompt = f"""
Sei un assistente specializzato in oncologia che valuta la compatibilità tra pazienti e trial clinici.
Esamina attentamente le caratteristiche del paziente e i criteri del trial clinico forniti.

CARATTERISTICHE DEL PAZIENTE:
{patient_json}

DATI DEL TRIAL CLINICO:
{trial_json}

ISTRUZIONI:
1. Valuta se il paziente soddisfa i criteri di inclusione del trial
2. Verifica se il paziente presenta criteri di esclusione
3. Considera tutti gli aspetti: età, genere, diagnosi, stadio, ECOG, mutazioni, ecc.
4. Valuta i casi "borderline" dove mancano informazioni con cautela

Fornisci una valutazione nel seguente formato JSON:
{{
  "match": "match/no_match/maybe",
  "score": punteggio da 0 a 100,
  "explanation": "Spiegazione dettagliata della valutazione",
  "criteria_met": ["Criterio 1 soddisfatto", "Criterio 2 soddisfatto", ...],
  "criteria_not_met": ["Criterio 1 non soddisfatto", "Criterio 2 non soddisfatto", ...]
}}

Rispondi SOLO con il JSON, senza testo aggiuntivo prima o dopo.
"""

        # Genera la valutazione
        response = self.generate_response(prompt, temperature=0.2)
        
        # Estrai il JSON dalla risposta
        try:
            # Cerca di identificare il blocco JSON
            json_start = response.find('{')
            json_end = response.rfind('}')
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_str = response[json_start:json_end+1]
                evaluation = json.loads(json_str)
                
                # Assicurati che i campi richiesti siano presenti
                required_fields = ["match", "score", "explanation"]
                for field in required_fields:
                    if field not in evaluation:
                        evaluation[field] = "" if field == "explanation" else 0 if field == "score" else "unknown"
                
                # Normalizza i campi di lista se mancanti
                if "criteria_met" not in evaluation:
                    evaluation["criteria_met"] = []
                if "criteria_not_met" not in evaluation:
                    evaluation["criteria_not_met"] = []
                    
                return evaluation
            else:
                logger.warning("Impossibile trovare JSON valido nella risposta dell'LLM")
                return {
                    "match": "unknown",
                    "score": 0,
                    "explanation": "Errore nell'analisi della risposta dell'LLM.",
                    "criteria_met": [],
                    "criteria_not_met": []
                }
                
        except json.JSONDecodeError as e:
            logger.warning(f"Errore nel parsing JSON dalla risposta LLM: {str(e)}")
            return {
                "match": "unknown",
                "score": 0,
                "explanation": f"Errore nel formato della risposta dell'LLM: {str(e)}",
                "criteria_met": [],
                "criteria_not_met": []
            }


def get_llm_processor() -> LLMProcessor:
    """
    Restituisce un'istanza del processore LLM.
    
    Returns:
        LLMProcessor: Una nuova istanza del processore LLM
    """
    return LLMProcessor()