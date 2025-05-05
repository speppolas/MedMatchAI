# Configurazione di llama.cpp per MedMatchINT

Questo documento descrive come configurare e installare llama.cpp per l'utilizzo con MedMatchINT. L'approccio ibrido PostgreSQL + LLM locale offre una soluzione privacy-preserving per l'abbinamento tra pazienti oncologici e trial clinici.

## Prerequisiti

- Sistema operativo Linux, macOS o Windows con WSL
- Compilatore C++ (GCC, Clang, MSVC)
- Git
- CMake (versione 3.12 o superiore)
- Python 3.x con pip (opzionale per i binding Python)
- GPU compatibile con CUDA o Metal per accelerazione (opzionale ma consigliato)

## Installazione di llama.cpp

### 1. Clona il repository

```bash
# Crea una directory per llama.cpp
mkdir -p ~/llama.cpp
cd ~/llama.cpp

# Clona il repository
git clone https://github.com/ggerganov/llama.cpp.git .
```

### 2. Compilazione

#### Compilazione standard (CPU)

```bash
# Configura e compila
mkdir build
cd build
cmake ..
cmake --build . --config Release
```

#### Compilazione con supporto CUDA (per GPU NVIDIA)

```bash
# Installa i prerequisiti CUDA
# Assicurati di avere i driver NVIDIA e CUDA installati

# Configura e compila con supporto CUDA
mkdir build-cuda
cd build-cuda
cmake .. -DLLAMA_CUDA=ON
cmake --build . --config Release
```

#### Compilazione con supporto OpenCL (per GPU AMD)

```bash
# Configura e compila con supporto OpenCL
mkdir build-opencl
cd build-opencl
cmake .. -DLLAMA_OPENCL=ON
cmake --build . --config Release
```

#### Compilazione con supporto Metal (per Mac con Apple Silicon o GPU AMD)

```bash
# Configura e compila con supporto Metal
mkdir build-metal
cd build-metal
cmake .. -DLLAMA_METAL=ON
cmake --build . --config Release
```

### 3. Installazione del modello

MedMatchINT è configurato per utilizzare il modello Mistral 7B Instruct. Puoi scaricare una versione quantizzata dal sito HuggingFace:

```bash
# Crea directory per i modelli
mkdir -p ~/llama.cpp/models

# Scarica il modello Mistral 7B Instruct quantizzato (4-bit)
wget -O ~/llama.cpp/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf
```

## Configurazione dell'applicazione

### 1. Modifica le variabili d'ambiente

Aggiungi queste variabili al file `.env` dell'applicazione:

```
# Configurazione LLM
LLAMA_CPP_PATH=/percorso/completo/a/llama.cpp
LLM_MODEL_PATH=/percorso/completo/a/llama.cpp/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
```

### 2. Verifica l'installazione

Puoi verificare che llama.cpp funzioni correttamente eseguendo:

```bash
cd ~/llama.cpp
./main -m ./models/mistral-7b-instruct-v0.2.Q4_K_M.gguf -p "Ciao, sono un medico. Puoi aiutarmi?" -n 128
```

Dovresti vedere l'output generato dal modello.

## Risoluzione dei problemi

### Errore "GPU Out of Memory"

Se riscontri errori di memoria sulla GPU, puoi:

1. Utilizzare un modello più piccolo o con quantizzazione maggiore (es. Q3_K_S o Q2_K)
2. Ridurre il valore di `context_size` nel file `app/llm_processor.py`
3. Utilizzare la versione CPU anziché quella GPU

### Errore "Model not found"

Assicurati che il percorso al modello sia corretto nelle variabili d'ambiente. Il file del modello deve esistere nel percorso specificato.

### Performance lente

- Su CPU: Prova ad aumentare il numero di thread con `-t N` dove N è il numero di thread
- Su GPU: Verifica che stai realmente utilizzando la versione compilata con supporto GPU

## Modelli alternativi

Se Mistral 7B Instruct non soddisfa le tue esigenze, puoi utilizzare altri modelli come:

- LLaMA 2 7B o 13B
- Gemma 7B
- Phi-2
- Vicuna

Assicurati di scaricare la versione GGUF del modello e di aggiornare la variabile d'ambiente `LLM_MODEL_PATH`.

## Modalità fallback

MedMatchINT è progettato per funzionare anche senza il modello LLM. Se il modello non è disponibile o si verifica un errore, l'applicazione utilizzerà automaticamente la modalità fallback che si basa solo sul filtraggio PostgreSQL e sull'analisi tramite espressioni regolari. Tuttavia, i risultati saranno meno precisi senza l'analisi semantica offerta dal LLM.