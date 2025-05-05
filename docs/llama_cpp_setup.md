# Guida all'Installazione e Configurazione di llama.cpp

Questa guida dettagliata spiega come installare e configurare llama.cpp per l'uso con MedMatchINT. llama.cpp è una implementazione efficiente in C/C++ dell'architettura LLaMA, che consente di eseguire modelli LLM localmente, senza necessità di connessione a servizi esterni.

## Panoramica

llama.cpp offre diversi vantaggi per MedMatchINT:
- **Privacy**: Elaborazione completamente locale dei dati sensibili
- **Nessuna connessione internet richiesta**: Funzionamento completo offline
- **Efficienza**: Ottimizzato per CPU e può utilizzare GPU se disponibile
- **Compatibilità**: Supporta diversi modelli in formato GGUF

## Requisiti di Sistema

### Requisiti Minimi
- CPU x86_64 o ARM64 (ARM64 consigliato per efficienza energetica)
- 8 GB di RAM
- 5 GB di spazio su disco per l'applicazione e un modello quantizzato

### Requisiti Consigliati
- CPU moderno con supporto AVX2 o ARM64 con Neon
- 16+ GB di RAM
- GPU NVIDIA con 6+ GB VRAM (opzionale per accelerazione)
- 20+ GB di spazio su disco per più modelli

## 1. Installazione di llama.cpp

### Installazione su Linux

```bash
# Installa le dipendenze di sviluppo
sudo apt-get update
sudo apt-get install -y build-essential cmake git

# Clona il repository llama.cpp
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# Compila (versione base solo CPU)
mkdir build
cd build
cmake ..
cmake --build . --config Release
```

### Installazione su macOS

```bash
# Installa le dipendenze tramite Homebrew
brew install cmake git

# Clona il repository llama.cpp
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# Compila
mkdir build
cd build
cmake ..
cmake --build . --config Release
```

### Installazione con Supporto CUDA (per GPU NVIDIA)

```bash
# Assicurati che CUDA sia già installato

# Clona il repository llama.cpp
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# Compila con supporto CUDA
mkdir build-cuda
cd build-cuda
cmake .. -DLLAMA_CUDA=ON
cmake --build . --config Release
```

## 2. Download e Preparazione dei Modelli

### Modelli Consigliati

MedMatchINT è stato testato con i seguenti modelli, in ordine di preferenza:

1. **Mistral 7B Instruct**
   - Eccellente bilanciamento tra dimensioni e prestazioni
   - Buona comprensione del contesto medico
   - File: `mistral-7b-instruct-v0.2.Q4_K_M.gguf` (4-bit, ~4.1GB)

2. **LLaMA 2 7B**
   - Buona comprensione generale
   - File: `llama-2-7b-chat.Q4_K_M.gguf` (4-bit, ~4.2GB)

### Download dei Modelli

```bash
# Crea la directory per i modelli
mkdir -p ~/llama.cpp/models

# Download Mistral 7B Instruct (4-bit)
wget -O ~/llama.cpp/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf

# OPPURE download LLaMA 2 7B (4-bit)
wget -O ~/llama.cpp/models/llama-2-7b-chat.Q4_K_M.gguf \
  https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_K_M.gguf
```

### Nota sulla Quantizzazione

La quantizzazione riduce le dimensioni del modello e aumenta la velocità a scapito di una leggera riduzione della qualità:

- **Q4_K_M**: Quantizzazione a 4-bit con matrici K, ottimo rapporto performance/dimensioni
- **Q5_K_M**: Quantizzazione a 5-bit, qualità leggermente superiore ma file più grande
- **Q8_0**: Quantizzazione a 8-bit, alta qualità ma file di dimensioni doppie

## 3. Configurazione di MedMatchINT

### Configurazione tramite Variabili d'Ambiente

Modifica il file `.env` nella directory principale di MedMatchINT:

```
# Percorso completo alla directory di llama.cpp
LLAMA_CPP_PATH=/percorso/completo/a/llama.cpp

# Percorso completo al file del modello
LLM_MODEL_PATH=/percorso/completo/a/llama.cpp/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf

# Parametri opzionali del modello
LLM_CONTEXT_SIZE=4096
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2048
```

### Parametri Opzionali

- **LLM_CONTEXT_SIZE**: La dimensione del contesto determina quante informazioni il modello può considerare contemporaneamente. Valori più alti permettono di elaborare più informazioni ma richiedono più memoria.

- **LLM_TEMPERATURE**: Controlla la casualità delle risposte. Valori più bassi (es. 0.1-0.4) generano risposte più deterministiche e precise, mentre valori più alti (0.7-1.0) producono risposte più varie e creative.

- **LLM_MAX_TOKENS**: Il numero massimo di token da generare per risposta.

## 4. Test dell'Installazione

Per verificare che llama.cpp sia installato e configurato correttamente:

```bash
# Nella directory principale di MedMatchINT
python -c "from app.llm_processor import get_llm_processor, LLM_AVAILABLE; llm = get_llm_processor(); print(f'LLM disponibile: {LLM_AVAILABLE}')"
```

Se tutto è configurato correttamente, dovresti vedere:
```
LLM disponibile: True
```

In alternativa puoi testare direttamente llama.cpp:

```bash
cd /percorso/a/llama.cpp
./build/bin/main -m ./models/mistral-7b-instruct-v0.2.Q4_K_M.gguf -p "Ciao, come stai?" -n 128
```

## 5. Risoluzione dei Problemi

### Problema: "LLM non disponibile"

1. **Verifica i percorsi**:
   ```bash
   # Verifica che il percorso a llama.cpp sia corretto
   ls -la $LLAMA_CPP_PATH
   
   # Verifica che l'eseguibile esista
   ls -la $LLAMA_CPP_PATH/build/bin/main
   
   # Verifica che il modello esista
   ls -la $LLM_MODEL_PATH
   ```

2. **Controllo permessi**:
   ```bash
   # Assicurati che i file abbiano i permessi corretti
   chmod +x $LLAMA_CPP_PATH/build/bin/main
   chmod +r $LLM_MODEL_PATH
   ```

3. **Test diretto di llama.cpp**:
   ```bash
   cd $LLAMA_CPP_PATH
   ./build/bin/main -m $LLM_MODEL_PATH -p "Test" -n 10
   ```

### Problema: "Errore di memoria durante l'esecuzione"

1. **Usa un modello più piccolo o con quantizzazione maggiore**:
   - Passa a un modello 4-bit (Q4_K_M) se stai usando modelli con meno quantizzazione
   - Considera modelli più piccoli (7B invece di 13B)

2. **Riduci la dimensione del contesto**:
   ```
   LLM_CONTEXT_SIZE=2048  # Valore più basso rispetto ai 4096 di default
   ```

3. **Limita l'utilizzo della memoria**:
   ```bash
   # Nel file .env
   LLM_EXTRA_PARAMS="--numa -ngl 1"  # Limita l'uso di memoria GPU
   ```

### Problema: "Modello troppo lento"

1. **Abilita l'accelerazione hardware**:
   ```bash
   # Ricompila con supporto specifico del CPU
   cd $LLAMA_CPP_PATH
   make clean
   LLAMA_AVX2=1 make -j  # Per CPU con supporto AVX2
   ```

2. **Utilizza la GPU se disponibile**:
   ```bash
   # Ricompila con supporto CUDA
   cd $LLAMA_CPP_PATH
   mkdir -p build-cuda && cd build-cuda
   cmake .. -DLLAMA_CUDA=ON
   cmake --build . --config Release
   
   # Aggiorna il percorso all'eseguibile nel file .env
   LLAMA_CPP_PATH=/percorso/a/llama.cpp/build-cuda/bin
   ```

## 6. Uso Avanzato

### Modelli Alternativi

MedMatchINT è compatibile con vari modelli GGUF:

- **Modelli OpenOrca**: Buona comprensione di contesti medici
- **Modelli specializzati biomedici**: Perfetti per terminologia medica avanzata
- **Modelli multilingua**: Utili per documentazione in più lingue

### Personalizzazione dei Prompt

Per modificare i prompt utilizzati nelle analisi, è possibile editare:

- `app/llm_processor.py`: Contiene i prompt per l'estrazione delle caratteristiche e la valutazione dei trial

### Ottimizzazione per Hardware Specifico

llama.cpp può essere ottimizzato per diversi tipi di hardware:

```bash
# Per CPU Intel/AMD con AVX2
LLAMA_AVX2=1 make -j

# Per CPU Intel con AVX512
LLAMA_AVX512=1 make -j

# Per Apple Silicon (M1/M2)
LLAMA_METAL=1 make -j

# Per GPU NVIDIA (con CUBLAS)
CMAKE_ARGS="-DLLAMA_CUBLAS=on" make -j
```

## Riferimenti

- [Repository llama.cpp](https://github.com/ggerganov/llama.cpp)
- [Documentazione ufficiale llama.cpp](https://github.com/ggerganov/llama.cpp/blob/master/README.md)
- [Hugging Face - Modelli GGUF](https://huggingface.co/models?sort=trending&search=gguf)
- [Mistral AI](https://mistral.ai/)

## Note sulla Licenza

L'uso di llama.cpp e dei modelli LLM è soggetto alle rispettive licenze. Assicurati di controllare e rispettare le licenze dei modelli che intendi utilizzare in MedMatchINT.