#!/bin/bash

# Script per impostare l'ambiente di MedMatchINT
# Questo script crea un ambiente virtuale e installa tutte le dipendenze

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funzione per stampare messaggi di stato
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verifica Python
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 non trovato. Installalo prima di continuare."
    exit 1
fi

python_version=$(python3 --version | cut -d' ' -f2)
print_status "Versione Python rilevata: $python_version"

# Prepara l'ambiente virtuale
print_status "Creazione dell'ambiente virtuale..."
python3 -m venv venv

if [ ! -d "venv" ]; then
    print_error "Creazione dell'ambiente virtuale fallita. Verifica di avere i pacchetti necessari installati."
    print_status "Su Ubuntu/Debian prova: sudo apt-get install python3-venv"
    exit 1
fi

print_status "Attivazione dell'ambiente virtuale..."
source venv/bin/activate

# Aggiorna pip
print_status "Aggiornamento di pip..."
pip install --upgrade pip

# Installa le dipendenze
print_status "Installazione delle dipendenze..."
pip install email-validator flask flask-sqlalchemy gunicorn pdfplumber psycopg2-binary requests trafilatura

# Crea il file .env se non esiste
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    print_status "Creazione del file .env da .env.example..."
    cp .env.example .env
    print_warning "Modifica il file .env con le tue configurazioni!"
fi

# Verifica la presenza della cartella uploads
if [ ! -d "uploads" ]; then
    print_status "Creazione della directory uploads..."
    mkdir -p uploads
    chmod 755 uploads
fi

print_status "Installazione completata! Per avviare l'applicazione:"
print_status "1. Modifica il file .env con le tue configurazioni"
print_status "2. Inizializza il database: python db_init.py"
print_status "3. Aggiorna i trial clinici: python update_trials.py"
print_status "4. Avvia l'applicazione in sviluppo: ./run_development.sh"
print_status "5. Avvia l'applicazione in produzione: ./run_production.sh"

print_warning "Ricorda di rendere eseguibili gli script: chmod +x *.sh"

# Disattiva l'ambiente virtuale
deactivate