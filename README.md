
# MedMatchINT - Clinical Trial Matching System

## 🚀 Quick Start on Replit

1. Fork this repl to your account
2. Start Ollama server and download the Mistral model:
```bash
ollama serve &
ollama pull mistral
```
3. Run the Flask application:
```bash
FLASK_APP=main.py FLASK_ENV=development flask run --host=0.0.0.0 --port=5000
```

## 📋 Manual Setup Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file with your configuration:
```bash
cp .env.example .env
```

### 3. Privacy Note
This application processes all data in-memory only.
No files or patient data are saved to disk for privacy protection.

### 4. Run the Application

Start Ollama server and pull the model:
```bash
ollama serve &
ollama pull mistral
```

Then run the Flask application:
```bash
FLASK_APP=main.py FLASK_ENV=development flask run --host=0.0.0.0 --port=5000
```

## 📊 Key Features

- PDF Processing and Analysis
- LLM-powered Analysis with Ollama (Mistral model)
- Clinical Trial Matching
- Secure File Handling

## 📝 Logs

Application logs are stored in:
- `logs/medmatchint.log`

## 🔒 Security Notes

- Use HTTPS in production (enabled by default on Replit)
- Keep your `.env` file secure
- Regular security updates
