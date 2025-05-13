# MedMatchINT - Advanced Clinical Trial Matching System

MedMatchINT is a high-performance, privacy-preserving web application designed for matching cancer patient data with active clinical trials. This system leverages a GPU-accelerated Large Language Model (LLM) using llama.cpp, ensuring fast and accurate semantic matching of patient characteristics with trial criteria.

## 🚀 Key Features

* **Local GPU-Accelerated LLM (llama.cpp)** for fast, accurate semantic matching.
* **Modular Architecture:** Easily extensible with a clear directory structure.
* **High-Performance Matching:** Utilizes the LLM (llama.cpp) for feature extraction and matching without PostgreSQL.
* **Secure PDF Processing:** Patient documents are processed locally and deleted after use.
* **Scalable and Customizable:** Easily adaptable to various clinical use cases.

## 📌 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/tuorepositorio/medmatchint.git
cd medmatchint
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements-docker.txt
```

### 4. Configure Environment Variables

* Copy the example environment file and customize it:

```bash
cp .env.example .env
nano .env
```

### 5. Start the Application

#### Development Mode

```bash
flask run --host=0.0.0.0 --port=5000
```

#### Production Mode with Gunicorn

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --timeout 120 --log-level info
```

## ⚡ GPU-Only LLM Configuration

MedMatchINT uses a GPU-accelerated LLM (llama.cpp). Ensure you have CUDA installed.

* Set CUDA environment variables directly in `.env`:

```bash
LLAMA_CPP_PATH=/usr/local/llama.cpp
LLM_MODEL_PATH=/usr/local/llama.cpp/models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
```

## 🚦 System Requirements

* **Python 3.10+**
* **CUDA 12.8+ for GPU Acceleration**
* **8GB RAM minimum (16GB recommended)**
* **NVIDIA GPU with 6GB+ VRAM for optimal performance**

## 📊 Architecture

MedMatchINT is a fully LLM-driven application:

* **GPU-Accelerated LLM (llama.cpp)** for feature extraction and trial matching.
* **No PostgreSQL Required:** Directly utilizes the LLM for all matching logic.

## 🚀 Deployment

### Docker Compose (Recommended for Production)

```bash
docker-compose up --build
```

## 🛡️ Security Best Practices

* Use HTTPS in production.
* Store sensitive credentials securely (e.g., AWS Secrets Manager).
* Restrict access to uploaded patient documents.
* Ensure correct CUDA configuration for GPU-only LLM.

## ❓ Troubleshooting

### Common Issues

* **LLM Errors:** Verify CUDA paths and settings in `.env`.
* **CUDA Errors:** Check CUDA installation and compatibility.

## 📄 License

\[Insert License Information]

## 🌐 Contact

\[Insert Contact Information]

