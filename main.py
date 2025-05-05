import os
import logging
from app import create_app
from config import LOG_LEVEL, LOG_FORMAT, HOST, PORT

# Configurazione del logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)

# Creazione dell'applicazione
app = create_app()

if __name__ == '__main__':
    # Avvio dell'applicazione in modalità sviluppo
    app.run(host=HOST, port=PORT)