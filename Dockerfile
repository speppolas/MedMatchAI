FROM python:3.11-slim

# Imposta la directory di lavoro nel container
WORKDIR /app

# Copia i file di requisiti e installa le dipendenze
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copia il resto del codice dell'applicazione
COPY . .

# Espone la porta su cui l'app sarà in ascolto
EXPOSE 5000

# Avvia l'applicazione con Gunicorn (server WSGI produzione)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "main:app"]