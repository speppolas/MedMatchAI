# MedMatchINT - Clinical Trial Matching System

## 🚀 Quick Start on Replit

1. Fork this repl to your account
2. Install dependencies automatically by clicking Run
3. The application will start at port 5000

## 📋 Manual Deployment Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file with your configuration:
```bash
cp .env.example .env
```

### 3. Initialize Database and Upload Directory
```bash
mkdir -p uploads logs
touch logs/medmatchint.log
```

### 4. Run the Application

#### Development Mode
```bash
FLASK_APP=main.py FLASK_ENV=development flask run --host=0.0.0.0 --port=5000
```

#### Production Mode
```bash
gunicorn --bind 0.0.0.0:5000 main:app
```

## 🔧 Environment Variables

Required environment variables in `.env`:
- `FLASK_SECRET_KEY`: Generate a secure random key
- `UPLOAD_FOLDER`: Directory for uploaded files (default: uploads)
- `PDF_AUTO_DELETE_TIMEOUT`: Timeout for PDF deletion in minutes (default: 30)

## 🛠️ CUDA Configuration

The application is configured for CUDA acceleration with these settings:
```bash
GGML_CUDA=yes
GGML_CUDA_FORCE_MMQ=yes
GGML_CUDA_FORCE_CUBLAS=yes
```

## 📊 Key Features

- PDF Processing and Analysis
- GPU-Accelerated LLM Integration
- Clinical Trial Matching
- Secure File Handling

## 📝 Logs

Application logs are stored in:
- `logs/medmatchint.log`

## 🔒 Security Notes

- Use HTTPS in production (enabled by default on Replit)
- Keep your `.env` file secure
- Regular security updates