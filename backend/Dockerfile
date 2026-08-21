FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

# Set working directory
WORKDIR /app

# Install system dependencies with retry logic and --fix-missing
RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libmagic1 \
    netcat-traditional \
    wget \
    curl \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Pre-install CPU-only PyTorch and Torchvision to prevent huge CUDA downloads & speed up builds
RUN pip install --no-cache-dir torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cpu

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install remaining Python dependencies
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Download lightweight spaCy model
RUN python -m spacy download en_core_web_sm

# Copy the rest of the application
COPY . .

# Ensure entrypoint script is executable and directories exist
RUN chmod +x /app/entrypoint.sh && \
    mkdir -p /app/data /app/logs /app/uploads /app/app/ml/table_recognition/weights

# Expose API port
EXPOSE 8000

# Set entrypoint to wait for PostgreSQL & Redis
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command runs FastAPI server with live reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]