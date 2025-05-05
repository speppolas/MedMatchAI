# Approccio Ibrido PostgreSQL + LLM in MedMatchINT

Questo documento descrive in dettaglio l'implementazione e il funzionamento dell'approccio ibrido che combina PostgreSQL con un modello LLM locale per il matching di trial clinici in MedMatchINT.

## Panoramica

L'approccio ibrido implementato in MedMatchINT sfrutta i punti di forza di entrambe le tecnologie:

1. **PostgreSQL**: Efficiente per query strutturate su grandi volumi di dati, ottimo per filtrare in base a criteri oggettivi e ben definiti.
2. **LLM Locale**: Potente per l'analisi semantica di testo non strutturato, eccellente per valutare criteri complessi con sfumature linguistiche.

Questo approccio garantisce:
- **Efficienza**: Il filtro preliminare con PostgreSQL riduce il carico di lavoro per l'LLM
- **Precisione**: L'LLM valuta in modo approfondito solo i trial preselezionati
- **Privacy**: Tutti i dati sensibili dei pazienti vengono elaborati localmente
- **Robustezza**: Sistema di fallback automatico se l'LLM non è disponibile

## Architettura

```
Documento PDF del Paziente
        ↓
Estrazione Caratteristiche <-- [LLM locale (se disponibile)]
        ↓                     [Fallback: analisi con pattern]
        ↓
  [Caratteristiche Paziente]
        ↓
        ↓
Filtro PostgreSQL (criteri oggettivi) 
        ↓
  [Trial Preselezionati]
        ↓
        ↓
Valutazione Semantica <-- [LLM locale (se disponibile)]
        ↓                  [Fallback: analisi con pattern]
        ↓
  [Trial Compatibili con Spiegazioni]
        ↓
Presentazione all'Utente
```

## Implementazione Dettagliata

### 1. Estrazione delle Caratteristiche del Paziente

L'estrazione avviene mediante il modulo `scripts/feature_extraction.py` che utilizza un approccio a cascata:

1. **Tentativo con LLM locale (llama.cpp)**: Se configurato, MedMatchINT utilizza un modello locale (Mistral/LLaMA) per estrarre le caratteristiche in modo semanticamente accurato.

2. **Tentativo con Ollama**: Se llama.cpp non è disponibile ma Ollama è configurato sulla macchina, si utilizza quest'ultimo come alternativa.

3. **Fallback con analisi basata su pattern**: Se nessun LLM è disponibile, l'applicazione ricorre a un'analisi con espressioni regolari per estrarre le informazioni chiave.

Ogni metodo produce una struttura dati compatibile, contenente:
- Età
- Genere
- Diagnosi
- Stadio
- Punteggio ECOG
- Mutazioni genetiche
- Metastasi
- Trattamenti precedenti
- Valori di laboratorio

### 2. Filtro Rapido con PostgreSQL

Implementato in `app/hybrid_query.py`, questo filtro:

1. Costruisce una query SQL dinamica in base alle caratteristiche del paziente
2. Filtra i trial per criteri oggettivi come:
   - Intervallo di età ammissibile
   - Genere
   - Stato del trial (attivo/reclutante)
   - Presenza di parole chiave dalla diagnosi

Questo passaggio riduce significativamente il numero di trial da valutare, passando potenzialmente da migliaia a decine.

### 3. Valutazione Semantica Approfondita

Per i trial preselezionati, l'LLM (se disponibile) esegue un'analisi semantica approfondita:

1. **Prompt specifico**: Il sistema genera un prompt che confronta le caratteristiche del paziente con i criteri di inclusione/esclusione del trial.

2. **Valutazione contestuale**: L'LLM considera il contesto medico, la terminologia specializzata e le relazioni implicite.

3. **Output strutturato**: Il risultato include:
   - Valutazione di compatibilità (match/no match/maybe)
   - Punteggio numerico di compatibilità (0-100)
   - Spiegazione dettagliata
   - Lista di criteri soddisfatti e non soddisfatti

### 4. Sistema di Fallback

MedMatchINT implementa un sofisticato sistema di fallback a più livelli:

1. **Stato globale dell'LLM**: La variabile `LLM_AVAILABLE` in `app/llm_processor.py` tiene traccia della disponibilità dell'LLM.

2. **Fallback nell'estrazione**: Se l'LLM non è disponibile durante l'estrazione delle caratteristiche, si utilizzano metodi alternativi.

3. **Fallback nel matching**: Se l'LLM non è disponibile durante la valutazione dei trial, l'applicazione usa un approccio basato su pattern.

4. **Segnalazione all'utente**: Gli utenti sono informati se l'applicazione sta utilizzando la modalità di fallback.

## Ottimizzazioni e Prestazioni

1. **Caching**: I risultati delle valutazioni dell'LLM vengono memorizzati temporaneamente per evitare elaborazioni ripetute.

2. **Parallelizzazione**: L'elaborazione di più trial avviene in parallelo quando possibile.

3. **Prioritizzazione**: I trial con maggiore probabilità di corrispondenza vengono valutati per primi.

4. **Prestazioni tipiche**:
   - Estrazione caratteristiche: 2-5 secondi
   - Filtro PostgreSQL: <1 secondo
   - Valutazione LLM per trial: 3-7 secondi (dipende dal modello)
   - Tempo totale tipico: 10-30 secondi (per 5-10 trial)

## Configurazione

La configurazione dell'approccio ibrido avviene tramite variabili d'ambiente:

```
# Percorso a llama.cpp
LLAMA_CPP_PATH=/percorso/a/llama.cpp

# Percorso al modello
LLM_MODEL_PATH=/percorso/a/llama.cpp/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf

# Parametri opzionali
LLM_CONTEXT_SIZE=4096
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048
```

## Limitazioni e Sviluppi Futuri

1. **Limitazioni attuali**:
   - Dipendenza dalla disponibilità di modelli locali
   - Elaborazione sequenziale che limita la velocità
   - Necessità di hardware adeguato per modelli più grandi

2. **Sviluppi futuri**:
   - Integrazione di modelli LLM più piccoli e ottimizzati
   - Miglioramento delle strategie di prompt
   - Addestramento specializzato per terminologia oncologica
   - Sistema di feedback per migliorare le valutazioni nel tempo

## Considerazioni sulla Privacy

1. **Nessun dato lascia il server**:
   - Tutti i documenti dei pazienti vengono elaborati localmente
   - Non vengono effettuate chiamate API esterne per l'elaborazione dei dati
   - I documenti vengono eliminati automaticamente dopo l'uso

2. **Sicurezza del modello**:
   - I modelli LLM sono ospitati localmente e non condividono dati
   - Il sistema non memorizza dati di apprendimento dai documenti dei pazienti
   - Nessun fine-tuning viene eseguito sui dati sensibili