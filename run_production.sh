#!/bin/bash

# Script per avviare l'applicazione MedMatchINT in modalità produzione
# Questo script attiva l'ambiente virtuale e avvia Gunicorn

# Verifica se gunicorn è installato
if ! command -v venv/bin/gunicorn &> /dev/null; then
    echo "Errore: Gunicorn non trovato nell'ambiente virtuale."
    echo "Assicurati di aver installato tutte le dipendenze con 'pip install -r requirements.txt'."
    exit 1
fi

# Carica le variabili d'ambiente
if [ -f .env ]; then
    echo "Caricamento variabili d'ambiente da .env..."
    export $(grep -v '^#' .env | xargs)
else
    echo "File .env non trovato. Assicurati di crearlo copiando .env.example."
    exit 1
fi

# Attiva l'ambiente virtuale e avvia Gunicorn
echo "Avvio MedMatchINT in modalità produzione..."
source venv/bin/activate
gunicorn --bind 0.0.0.0:5000 --workers=4 --timeout=120 main:app