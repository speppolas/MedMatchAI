#!/bin/bash

# Script per avviare l'applicazione MedMatchINT in modalità sviluppo
# Questo script attiva l'ambiente virtuale e avvia Flask in modalità debug

# Carica le variabili d'ambiente
if [ -f .env ]; then
    echo "Caricamento variabili d'ambiente da .env..."
    export $(grep -v '^#' .env | xargs)
else
    echo "File .env non trovato. Assicurati di crearlo copiando .env.example."
    exit 1
fi

# Imposta l'ambiente di sviluppo
export FLASK_ENV=development
export FLASK_DEBUG=1

# Attiva l'ambiente virtuale e avvia Flask
echo "Avvio MedMatchINT in modalità sviluppo..."
source venv/bin/activate
python -m flask run --host=0.0.0.0 --port=5000