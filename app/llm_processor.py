"""
Modulo per l'elaborazione dei dati tramite LLM locale utilizzando llama.cpp.
Questo modulo fornisce funzionalità per valutare la compatibilità semantica
tra i dati del paziente e i trial clinici preselezionati dal database PostgreSQL.

Gestisce l'interazione con il modello LLM locale (Mistral/LLaMA) per garantire
che tutti i dati sensibili rimangano in locale, preservando la privacy.
"""

import os
import json
import logging
import subprocess
from typing import Dict, List, Any, Optional, Tuple, Union

# Configurazione del logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Percorsi del modello e dell'eseguibile llama.cpp
LLAMA_CPP_PATH = os.environ.get("LLAMA_CPP_PATH", "./llama.cpp")
MODEL_PATH = os.environ.get("LLM_MODEL_PATH", "./models/mistral-7b-instruct-v0.2.Q4_K_M.gguf")
DEFAULT_CONTEXT_SIZE = 4096
DEFAULT_TEMP = 0.7
MAX_TOKENS = 2048

class LLMProcessor:
    """
    Classe per l'elaborazione di dati tramite LLM locale utilizzando llama.cpp.
    Fornisce funzionalità per analizzare semanticamente il testo e valutare
    la compatibilità tra i dati del paziente e i trial clinici.
    """
    
    def __init__(self, 
                 model_path: Optional[str] = None, 
                 llama_cpp_path: Optional[str] = None,
                 context_size: int = DEFAULT_CONTEXT_SIZE,
                 temperature: float = DEFAULT_TEMP):
        """
        Inizializza il processore LLM.
        
        Args:
            model_path: Percorso al file del modello GGUF
            llama_cpp_path: Percorso alla directory di llama.cpp
            context_size: Dimensione del contesto per il modello
            temperature: Temperatura per la generazione (0.0-1.0)
        """
        self.model_path = model_path or MODEL_PATH
        self.llama_cpp_path = llama_cpp_path or LLAMA_CPP_PATH
        self.context_size = context_size
        self.temperature = temperature
        self.main_exe = os.path.join(self.llama_cpp_path, "main")
        
        # Verifica che il modello esista
        if not os.path.exists(self.model_path):
            logger.warning(f"Modello LLM non trovato in: {self.model_path}")
            logger.info("L'applicazione funzionerà in modalità fallback senza LLM")
        
        # Verifica che l'eseguibile llama.cpp esista
        if not os.path.exists(self.main_exe):
            logger.warning(f"Eseguibile llama.cpp non trovato in: {self.main_exe}")
            logger.info("L'applicazione funzionerà in modalità fallback senza LLM")

    def _is_llm_available(self) -> bool:
        """
        Verifica se il LLM è disponibile per l'uso.
        
        Returns:
            bool: True se il LLM è disponibile, False altrimenti
        """
        return os.path.exists(self.model_path) and os.path.exists(self.main_exe)

    def _run_llama_cpp(self, prompt: str, max_tokens: int = MAX_TOKENS) -> str:
        """
        Esegue llama.cpp con il prompt specificato.
        
        Args:
            prompt: Il prompt da inviare al modello
            max_tokens: Numero massimo di token da generare
            
        Returns:
            str: Il testo generato dal modello
        """
        if not self._is_llm_available():
            return self._fallback_response(prompt)
        
        try:
            # Prepara il comando per eseguire llama.cpp
            cmd = [
                self.main_exe,
                "-m", self.model_path,
                "-c", str(self.context_size),
                "--temp", str(self.temperature),
                "-n", str(max_tokens),
                "-p", prompt,
                "--log-disable"
            ]
            
            # Esegui il comando e cattura l'output
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True
            )
            
            # Estrai e restituisci la risposta
            return result.stdout.strip()
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Errore nell'esecuzione di llama.cpp: {e}")
            logger.error(f"Stderr: {e.stderr}")
            return self._fallback_response(prompt)
        except Exception as e:
            logger.error(f"Errore generico nell'esecuzione di llama.cpp: {e}")
            return self._fallback_response(prompt)

    def _fallback_response(self, prompt: str) -> str:
        """
        Genera una risposta di fallback quando il LLM non è disponibile.
        
        Args:
            prompt: Il prompt originale
            
        Returns:
            str: Una risposta di fallback
        """
        logger.warning("Utilizzo modalità fallback: il LLM non è disponibile")
        return ("MODALITÀ FALLBACK: Modello LLM non disponibile. "
                "I risultati sono basati solo sulla ricerca nel database. "
                "Per risultati più precisi, configura correttamente il modello LLM locale.")

    def extract_patient_features(self, pdf_text: str) -> Dict[str, Any]:
        """
        Estrae caratteristiche cliniche del paziente dal testo del PDF.
        
        Args:
            pdf_text: Testo estratto dal PDF del paziente
            
        Returns:
            Dict[str, Any]: Caratteristiche estratte del paziente
        """
        if not self._is_llm_available():
            # Fallback a un'estrazione di base quando il LLM non è disponibile
            return self._basic_feature_extraction(pdf_text)
        
        # Prompt per l'estrazione delle caratteristiche
        prompt = f"""
Analizza il seguente testo medico di un paziente oncologico ed estrai le informazioni cliniche rilevanti in formato strutturato.
Restituisci solo un oggetto JSON con le seguenti chiavi (se presenti nel testo):
- diagnosis: diagnosi principale
- age: età del paziente
- gender: genere del paziente
- ecog: stato performance ECOG
- mutations: mutazioni genetiche rilevanti
- lab_values: valori di laboratorio significativi
- treatments: trattamenti precedenti o in corso
- metastasis: presenza e localizzazione di metastasi
- stage: stadio del tumore

Testo del paziente:
{pdf_text}

Restituisci solo l'oggetto JSON, senza testo aggiuntivo. Se un'informazione non è presente nel testo, ometti la chiave corrispondente.
JSON: 
"""
        # Esegui il modello e ottieni la risposta
        response = self._run_llama_cpp(prompt)
        
        # Cerca di estrarre il JSON dalla risposta
        try:
            # Cerca di individuare il JSON nella risposta
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
            else:
                logger.warning("Impossibile trovare un oggetto JSON valido nella risposta del LLM")
                return self._basic_feature_extraction(pdf_text)
                
        except json.JSONDecodeError:
            logger.warning("Errore nel parsing del JSON dalla risposta del LLM")
            return self._basic_feature_extraction(pdf_text)
        except Exception as e:
            logger.error(f"Errore nell'elaborazione della risposta del LLM: {e}")
            return self._basic_feature_extraction(pdf_text)

    def _basic_feature_extraction(self, text: str) -> Dict[str, Any]:
        """
        Implementazione base di estrazione caratteristiche per fallback.
        
        Args:
            text: Testo da analizzare
            
        Returns:
            Dict[str, Any]: Caratteristiche estratte dal testo
        """
        # Implementazione semplificata basata su regole/keyword per il fallback
        features = {}
        
        # Cerca l'età (pattern semplice)
        import re
        age_patterns = [
            r'(\d{1,2})\s*(?:anni|year[s]?)',
            r'age[\s:]+(\d{1,2})',
            r'(?:patient|paziente)[\s:]*(\d{1,2})[\s-]*(?:anni|year[s]?)'
        ]
        
        for pattern in age_patterns:
            age_match = re.search(pattern, text, re.IGNORECASE)
            if age_match:
                features['age'] = int(age_match.group(1))
                break
        
        # Estrai genere (cerca keywords)
        if re.search(r'\b(?:male|uomo|maschio)\b', text, re.IGNORECASE):
            features['gender'] = 'male'
        elif re.search(r'\b(?:female|donna|femmina)\b', text, re.IGNORECASE):
            features['gender'] = 'female'
        
        # Cerca stato ECOG (0-5)
        ecog_match = re.search(r'ECOG[\s:]*([0-5])', text, re.IGNORECASE)
        if ecog_match:
            features['ecog'] = int(ecog_match.group(1))
        
        # Cerca diagnosi (pattern generico per tumori comuni)
        cancer_patterns = [
            r'(?:carcinoma|tumore|cancro|cancer|adenocarcinoma)[\s\w]*(?:del|della|dello|dell\'|of the)[\s\w]*(polmon|colon|mammell|prostat|pancrea|gastric|stomc|ret|ovaio|uter|cervice|testicol|linfoma|leucemia|melanoma|tiroide)',
            r'(NSCLC|CRC|HCC|AML|CLL|ALL|DLBCL|SCLC)'
        ]
        
        for pattern in cancer_patterns:
            cancer_match = re.search(pattern, text, re.IGNORECASE)
            if cancer_match:
                features['diagnosis'] = cancer_match.group(0)
                break
        
        # Cerca mutazioni comuni (pattern generico)
        mutation_patterns = [
            r'(EGFR|ALK|ROS1|BRAF|KRAS|NRAS|HER2|MET|NTRK|RET|PIK3CA|BRCA[12]|TP53|PD-L1)[\s:]*(?:mutation|mutazione|positivo|positive|\+)',
            r'mutation[\s:]*(?:in)?[\s:]*(EGFR|ALK|ROS1|BRAF|KRAS|NRAS|HER2|MET|NTRK|RET|PIK3CA|BRCA[12]|TP53|PD-L1)'
        ]
        
        mutations = []
        for pattern in mutation_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                mutations.append(match.group(1))
        
        if mutations:
            features['mutations'] = list(set(mutations))  # Rimuove duplicati
        
        return features

    def evaluate_trial_match(self, 
                           patient_features: Dict[str, Any], 
                           trial: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valuta la compatibilità tra il paziente e un trial clinico.
        
        Args:
            patient_features: Caratteristiche del paziente
            trial: Dati del trial clinico
            
        Returns:
            Dict[str, Any]: Risultato della valutazione con spiegazione
        """
        if not self._is_llm_available():
            # Ritorna una valutazione di base senza LLM
            return {
                "match": None,  # None indica che non c'è una valutazione semantica
                "explanation": "La valutazione semantica dettagliata richiede il modello LLM configurato localmente.",
                "score": None
            }
        
        # Formatta le caratteristiche del paziente come testo
        patient_text = self._format_patient_features(patient_features)
        
        # Formatta i criteri del trial come testo
        trial_text = self._format_trial_criteria(trial)
        
        # Crea il prompt per il LLM
        prompt = f"""
Sei un sistema esperto di oncologia che deve valutare la compatibilità di un paziente con un trial clinico.

PAZIENTE:
{patient_text}

TRIAL CLINICO ID {trial['id']}:
Titolo: {trial['title']}
{trial_text}

Valuta con attenzione se il paziente soddisfa i criteri di inclusione e non rientra nei criteri di esclusione.
Analizza ogni criterio rilevante e fornisci una spiegazione dettagliata.

Restituisci la tua valutazione in formato JSON con la seguente struttura:
{{
  "match": true/false/maybe,
  "score": [punteggio da 0 a 100, dove 0 è incompatibile e 100 è perfettamente compatibile],
  "explanation": [spiegazione dettagliata della valutazione con riferimenti specifici a criteri soddisfatti e non soddisfatti],
  "matching_criteria": [lista di criteri soddisfatti],
  "conflicting_criteria": [lista di criteri non soddisfatti]
}}

Basati solo sulle informazioni fornite. Se mancano dati essenziali per valutare criteri specifici, indica "maybe" nel campo match e spiega quali informazioni sarebbero necessarie.
"""
        
        # Esegui il modello e ottieni la risposta
        response = self._run_llama_cpp(prompt)
        
        # Cerca di estrarre il JSON dalla risposta
        try:
            # Cerca di individuare il JSON nella risposta
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                
                # Assicurati che i campi richiesti siano presenti
                if "match" not in result or "explanation" not in result:
                    raise ValueError("Risposta del LLM mancante di campi obbligatori")
                    
                return result
            else:
                logger.warning("Impossibile trovare un oggetto JSON valido nella risposta del LLM")
                return {
                    "match": None,
                    "explanation": "Errore nell'analisi semantica. Verificare la configurazione del modello LLM.",
                    "score": None
                }
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Errore nel parsing del JSON dalla risposta del LLM: {e}")
            return {
                "match": None,
                "explanation": "Errore nell'analisi della compatibilità. Verificare manualmente i criteri.",
                "score": None
            }

    def _format_patient_features(self, features: Dict[str, Any]) -> str:
        """
        Formatta le caratteristiche del paziente come testo strutturato.
        
        Args:
            features: Dizionario con le caratteristiche del paziente
            
        Returns:
            str: Testo formattato delle caratteristiche
        """
        text = []
        
        # Aggiungi ogni caratteristica al testo
        if 'diagnosis' in features:
            text.append(f"Diagnosi: {features['diagnosis']}")
            
        if 'age' in features:
            text.append(f"Età: {features['age']} anni")
            
        if 'gender' in features:
            gender_map = {'male': 'Maschio', 'female': 'Femmina'}
            text.append(f"Genere: {gender_map.get(features['gender'].lower(), features['gender'])}")
            
        if 'ecog' in features:
            text.append(f"Stato ECOG: {features['ecog']}")
            
        if 'mutations' in features:
            if isinstance(features['mutations'], list):
                text.append(f"Mutazioni: {', '.join(features['mutations'])}")
            else:
                text.append(f"Mutazioni: {features['mutations']}")
                
        if 'treatments' in features:
            if isinstance(features['treatments'], list):
                text.append(f"Trattamenti: {', '.join(features['treatments'])}")
            else:
                text.append(f"Trattamenti: {features['treatments']}")
                
        if 'metastasis' in features:
            if isinstance(features['metastasis'], list):
                text.append(f"Metastasi: {', '.join(features['metastasis'])}")
            else:
                text.append(f"Metastasi: {features['metastasis']}")
                
        if 'stage' in features:
            text.append(f"Stadio: {features['stage']}")
            
        if 'lab_values' in features:
            if isinstance(features['lab_values'], dict):
                labs = [f"{k}: {v}" for k, v in features['lab_values'].items()]
                text.append(f"Valori di laboratorio: {', '.join(labs)}")
            else:
                text.append(f"Valori di laboratorio: {features['lab_values']}")
        
        return "\n".join(text)

    def _format_trial_criteria(self, trial: Dict[str, Any]) -> str:
        """
        Formatta i criteri del trial come testo strutturato.
        
        Args:
            trial: Dizionario con i dati del trial
            
        Returns:
            str: Testo formattato dei criteri
        """
        text = []
        
        # Aggiungi la descrizione del trial
        if 'description' in trial and trial['description']:
            text.append(f"Descrizione: {trial['description']}")
        
        # Aggiungi i criteri di inclusione
        if 'inclusion_criteria' in trial and trial['inclusion_criteria']:
            text.append("\nCRITERI DI INCLUSIONE:")
            for i, criterion in enumerate(trial['inclusion_criteria'], 1):
                if isinstance(criterion, dict) and 'text' in criterion:
                    text.append(f"{i}. {criterion['text']}")
                else:
                    text.append(f"{i}. {criterion}")
        
        # Aggiungi i criteri di esclusione
        if 'exclusion_criteria' in trial and trial['exclusion_criteria']:
            text.append("\nCRITERI DI ESCLUSIONE:")
            for i, criterion in enumerate(trial['exclusion_criteria'], 1):
                if isinstance(criterion, dict) and 'text' in criterion:
                    text.append(f"{i}. {criterion['text']}")
                else:
                    text.append(f"{i}. {criterion}")
        
        # Aggiungi altre informazioni rilevanti
        if 'phase' in trial and trial['phase']:
            text.append(f"\nFase: {trial['phase']}")
            
        if 'status' in trial and trial['status']:
            text.append(f"Stato: {trial['status']}")
            
        if 'min_age' in trial and trial['min_age']:
            text.append(f"Età minima: {trial['min_age']}")
            
        if 'max_age' in trial and trial['max_age']:
            text.append(f"Età massima: {trial['max_age']}")
            
        if 'gender' in trial and trial['gender']:
            text.append(f"Genere: {trial['gender']}")
        
        return "\n".join(text)

# Funzione di comodo per creare un'istanza del processore
def get_llm_processor() -> LLMProcessor:
    """
    Crea e restituisce un'istanza di LLMProcessor con la configurazione di default.
    
    Returns:
        LLMProcessor: Un'istanza del processore LLM
    """
    return LLMProcessor()

# Esempio di utilizzo
if __name__ == "__main__":
    # Test dell'estrazione di caratteristiche da un testo di esempio
    test_text = """
    Paziente: Mario Rossi
    Età: 65 anni
    Genere: Maschio
    Diagnosi: Adenocarcinoma polmonare
    Stadio: IV
    ECOG: 1
    Mutazioni: EGFR T790M positivo
    Metastasi: Cerebrali e ossee
    Trattamenti precedenti: Osimertinib (fallimento), radioterapia cerebrale
    """
    
    processor = get_llm_processor()
    features = processor.extract_patient_features(test_text)
    print("Caratteristiche estratte:")
    print(json.dumps(features, indent=2, ensure_ascii=False))