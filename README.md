# MedMatchINT - Sistema di Abbinamento Pazienti e Trial Clinici

MedMatchINT è un'applicazione web privacy-preserving per abbinare i dati dei pazienti oncologici dell'Istituto Nazionale dei Tumori (INT) con i trial clinici attivi. L'applicazione estrae caratteristiche cliniche dai documenti PDF dei pazienti e le confronta con i criteri dei trial clinici, fornendo risultati di corrispondenza spiegabili e dettagliati.

## Caratteristiche Principali

- Elaborazione locale di documenti PDF per estrazione di caratteristiche cliniche
- Sistema ibrido di matching che combina:
  - **Filtro PostgreSQL:** rapido ed efficiente per criteri oggettivi (età, genere, stato)
  - **Analisi semantica con LLM locale:** modelli Mistral/LLaMA via llama.cpp per valutazione avanzata
- Database PostgreSQL per lo storage dei trial clinici
- Aggiornamento automatico dei trial da ClinicalTrials.gov
- Interfaccia web responsive e intuitiva
- Ricerca di trial per diversi tipi di ID (NCT, Protocollo, EudraCT, Registry)
- Gestione sicura dei documenti dei pazienti con auto-eliminazione
- Struttura modulare per facilitare manutenzione ed estensioni
- Approccio privacy-preserving con elaborazione completamente locale

## Requisiti di Sistema

- Python 3.10 o superiore
- PostgreSQL 12 o superiore
- Sistema operativo Linux, MacOS o Windows
- 2GB di RAM minimo (consigliati 4GB per prestazioni ottimali)
- 1GB di spazio su disco per l'applicazione e le dipendenze

### Requisiti Opzionali per l'Approccio Ibrido

Per l'utilizzo completo dell'approccio ibrido PostgreSQL + LLM:

- llama.cpp (compilato per il tuo sistema)
- Modello LLM Mistral 7B o LLaMA 2 in formato GGUF
- 8GB di RAM minimo per modelli quantizzati a 4-bit
- GPU con 6GB+ VRAM per accelerazione hardware (consigliata ma opzionale)

> **Nota**: L'applicazione funziona anche senza LLM, utilizzando un approccio fallback basato su PostgreSQL e analisi con espressioni regolari.

## Installazione

### 1. Preparazione dell'Ambiente

Clonare il repository e creare un ambiente virtuale:

```bash
# Clonare il repository
git clone https://github.com/tuorepositorio/medmatchint.git
cd medmatchint

# Creare e attivare un ambiente virtuale
python -m venv venv

# Su Linux/MacOS
source venv/bin/activate

# Su Windows
venv\Scripts\activate
```

### 2. Installazione delle Dipendenze

```bash
# Aggiornare pip
pip install --upgrade pip

# Installare le dipendenze
pip install -r requirements.txt
```

Se il file `requirements.txt` non è presente, puoi generarlo con:

```bash
pip install email-validator flask flask-sqlalchemy gunicorn pdfplumber psycopg2-binary requests trafilatura
pip freeze > requirements.txt
```

### 3. Configurazione del Database PostgreSQL

Assicurati che PostgreSQL sia installato e in esecuzione sul tuo sistema.

```bash
# Su Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Su MacOS con Homebrew
brew install postgresql
brew services start postgresql

# Su Windows
# Scarica e installa da https://www.postgresql.org/download/windows/
```

Crea un database e un utente per l'applicazione:

```bash
# Accedi a PostgreSQL
sudo -u postgres psql

# All'interno dell'interfaccia psql:
CREATE DATABASE medmatchint;
CREATE USER medmatchuser WITH PASSWORD 'password_sicura';
GRANT ALL PRIVILEGES ON DATABASE medmatchint TO medmatchuser;
\q
```

### 4. Configurazione delle Variabili d'Ambiente

Crea un file `.env` nella directory principale del progetto:

```bash
# Linux/MacOS
cp .env.example .env
nano .env

# Windows
copy .env.example .env
notepad .env
```

Modifica il file `.env` inserendo le tue configurazioni:

```
# Configurazione database
DATABASE_URL=postgresql://medmatchuser:password_sicura@localhost/medmatchint

# Configurazione Flask
FLASK_SECRET_KEY=una_chiave_segreta_lunga_e_casuale
FLASK_ENV=production

# Configurazione LLM (opzionale, per approccio ibrido)
LLAMA_CPP_PATH=/percorso/completo/a/llama.cpp
LLM_MODEL_PATH=/percorso/completo/a/llama.cpp/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
```

## Inizializzazione del Database

Esegui gli script di inizializzazione per creare le tabelle e popolare il database con dati iniziali:

```bash
# Inizializzazione dello schema del database
python db_init.py

# Aggiornamento dei trial clinici
python update_trials.py
```

## Avvio dell'Applicazione

### Modalità Sviluppo

```bash
# Avvia il server di sviluppo
flask run --host=0.0.0.0 --port=5000
```

### Modalità Produzione con Gunicorn

Per un ambiente di produzione, è consigliabile utilizzare Gunicorn:

```bash
# Avvia l'applicazione con Gunicorn
gunicorn --bind 0.0.0.0:5000 --workers=4 --timeout=120 main:app
```

Se desideri utilizzare un server proxy come Nginx davanti a Gunicorn (consigliato per la produzione), configura Nginx per inoltrare le richieste a Gunicorn.

## Deployment con Virtualenv e Gunicorn

Per un deployment completo in produzione, puoi seguire questi passaggi:

### 1. Configurazione di Systemd (Linux)

Crea un file di servizio systemd per gestire l'avvio automatico dell'applicazione:

```bash
sudo nano /etc/systemd/system/medmatchint.service
```

Inserisci il seguente contenuto (modifica i percorsi in base alla tua installazione):

```ini
[Unit]
Description=MedMatchINT Gunicorn Service
After=network.target postgresql.service

[Service]
User=nome_utente
Group=nome_gruppo
WorkingDirectory=/percorso/completo/a/medmatchint
Environment="PATH=/percorso/completo/a/medmatchint/venv/bin"
EnvironmentFile=/percorso/completo/a/medmatchint/.env
ExecStart=/percorso/completo/a/medmatchint/venv/bin/gunicorn --workers=4 --bind=0.0.0.0:5000 main:app
Restart=always
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=medmatchint

[Install]
WantedBy=multi-user.target
```

Attiva e avvia il servizio:

```bash
sudo systemctl daemon-reload
sudo systemctl enable medmatchint
sudo systemctl start medmatchint
sudo systemctl status medmatchint  # Verifica che il servizio sia attivo
```

### 2. Configurazione di Nginx (opzionale)

Se desideri utilizzare Nginx come proxy:

```bash
sudo apt-get install nginx
sudo nano /etc/nginx/sites-available/medmatchint
```

Inserisci la configurazione:

```nginx
server {
    listen 80;
    server_name tuo_dominio.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Attiva il sito e riavvia Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/medmatchint /etc/nginx/sites-enabled
sudo nginx -t  # Testa la configurazione
sudo systemctl restart nginx
```

## Aggiornamento dei Trial Clinici

L'applicazione include funzionalità per aggiornare automaticamente i trial clinici da ClinicalTrials.gov. Puoi eseguire questo aggiornamento manualmente:

```bash
python update_trials.py
```

Per un aggiornamento automatico, puoi configurare un job cron:

```bash
# Modifica i cron job
crontab -e

# Aggiungi questa riga per aggiornare i trial ogni giorno alle 3:00
0 3 * * * cd /percorso/completo/a/medmatchint && /percorso/completo/a/medmatchint/venv/bin/python update_trials.py >> /var/log/medmatchint_update.log 2>&1
```

## Architettura dell'Approccio Ibrido

MedMatchINT implementa un approccio ibrido innovativo per il matching dei trial clinici, combinando le capacità di PostgreSQL e di un modello LLM locale:

### 1. Filtro Rapido con PostgreSQL

Il sistema inizia con un filtro rapido utilizzando PostgreSQL per verificare criteri oggettivi:
- Età del paziente (min/max)
- Genere
- Stato del trial (attivo/reclutante)
- Parole chiave della diagnosi
- Presenza di mutazioni specifiche

Questa fase è altamente efficiente e riduce significativamente il numero di trial da valutare in dettaglio.

### 2. Valutazione Semantica con LLM Locale

I trial preselezionati vengono poi valutati in profondità utilizzando un LLM locale:
- Analisi dei criteri testuali complessi
- Comprensione del contesto medico e delle relazioni tra termini
- Valutazione di criteri di inclusione/esclusione non strutturati
- Generazione di spiegazioni dettagliate sul perché un paziente corrisponde o meno a un criterio

### 3. Sistema di Fallback Automatico

L'applicazione include un sofisticato sistema di fallback:
- Se l'LLM non è disponibile, l'estrazione utilizza analisi basata su pattern
- Se llama.cpp non è installato, il matching utilizza solo il filtro PostgreSQL
- Tentativi multipli con diversi approcci garantiscono che l'applicazione funzioni sempre

### Diagramma dell'Architettura Ibrida

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

## Struttura del Progetto

```
medmatchint/
├── app/                    # Pacchetto principale dell'applicazione
│   ├── __init__.py         # Inizializzazione dell'app Flask
│   ├── routes.py           # Route e controller dell'app
│   ├── utils.py            # Funzioni di utilità generale
│   ├── hybrid_query.py     # Implementazione dell'approccio ibrido PostgreSQL + LLM
│   └── llm_processor.py    # Gestione dell'interazione con LLM locale
├── static/                 # File statici (CSS, JS, immagini)
├── templates/              # Template HTML
├── uploads/                # Directory temporanea per i PDF caricati
├── .env.example            # Esempio di file di configurazione
├── db_init.py              # Script di inizializzazione del database
├── fetch_trial_by_id.py    # Script per recuperare trial per ID
├── fetch_trials.py         # Script per recuperare trial da ClinicalTrials.gov
├── main.py                 # Punto di ingresso dell'applicazione
├── models.py               # Modelli del database
├── requirements.txt        # Dipendenze Python
├── update_trials.py        # Script di aggiornamento trial
└── llama_cpp_config.md     # Istruzioni dettagliate per configurare llama.cpp
```

## Configurazione dell'Approccio Ibrido con LLM Locale

Per abilitare l'approccio ibrido con valutazione semantica avanzata:

### 1. Installazione di llama.cpp

Per i dettagli completi, consulta il file `llama_cpp_config.md`. In sintesi:

```bash
# Clona repository llama.cpp
git clone https://github.com/ggerganov/llama.cpp.git ~/llama.cpp
cd ~/llama.cpp

# Compila (versione base CPU)
mkdir build && cd build
cmake ..
cmake --build . --config Release

# Alternativa: compila con supporto CUDA (GPU NVIDIA)
# mkdir build-cuda && cd build-cuda
# cmake .. -DLLAMA_CUDA=ON
# cmake --build . --config Release
```

### 2. Download del Modello

Scarica un modello quantizzato adatto (esempio Mistral 7B):

```bash
mkdir -p ~/llama.cpp/models
wget -O ~/llama.cpp/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf
```

### 3. Configurazione dell'Applicazione

Aggiorna il file `.env` con i percorsi:

```
LLAMA_CPP_PATH=/percorso/completo/a/llama.cpp
LLM_MODEL_PATH=/percorso/completo/a/llama.cpp/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
```

L'applicazione rileverà automaticamente il modello LLM e utilizzarà l'approccio ibrido per il matching dei trial clinici, combinando il filtraggio rapido di PostgreSQL con l'analisi semantica approfondita del LLM.

> **Nota**: Se il modello LLM non è disponibile, l'applicazione utilizzerà automaticamente la modalità fallback basata su PostgreSQL e analisi con espressioni regolari.

## Risoluzione dei Problemi

### Errori di Connessione al Database

1. Verifica che PostgreSQL sia in esecuzione:
   ```bash
   # Su Linux
   sudo systemctl status postgresql
   
   # Su MacOS
   brew services list
   ```

2. Controlla che le credenziali nel file `.env` siano corrette.

3. Verifica che l'utente abbia i permessi necessari:
   ```bash
   sudo -u postgres psql
   \c medmatchint
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO medmatchuser;
   ```

### Problemi con l'Aggiornamento dei Trial

1. Controlla la connessione a Internet.

2. Verifica i log dell'applicazione per errori specifici dell'API di ClinicalTrials.gov.

3. In caso di errori persistenti, puoi utilizzare la modalità di fallback implementata nell'applicazione che utilizza query più semplici.

### Errori di Avvio dell'Applicazione

1. Controlla che tutte le dipendenze siano installate correttamente:
   ```bash
   pip install -r requirements.txt
   ```

2. Verifica che Gunicorn sia installato e accessibile nel tuo ambiente virtuale:
   ```bash
   venv/bin/gunicorn --version
   ```

3. Controlla i log di sistema per errori specifici:
   ```bash
   # Se usi systemd
   sudo journalctl -u medmatchint.service
   ```

## Contribuire al Progetto

Siamo aperti a contributi! Se desideri contribuire al progetto, segui questi passaggi:

1. Fork del repository
2. Crea un branch per la tua feature (`git checkout -b feature/amazing-feature`)
3. Effettua le modifiche e commit (`git commit -m 'Aggiunta una feature fantastica'`)
4. Push al branch (`git push origin feature/amazing-feature`)
5. Apri una Pull Request

## Licenza

[Inserire informazioni sulla licenza]

## Contatti

[Inserire informazioni di contatto]