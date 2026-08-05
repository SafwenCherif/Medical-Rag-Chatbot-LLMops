## Parent image
FROM python:3.10-slim

## Essential environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

## Work directory inside the docker container
WORKDIR /app

## Installing system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

## Copy project (FAISS index included so the container can answer immediately)
COPY . .

## CPU-only PyTorch first (avoids multi-GB CUDA wheels — embeddings don't need GPU)
RUN pip install --upgrade pip \
    && pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --extra-index-url https://download.pytorch.org/whl/cpu -e .

## Expose only flask port
EXPOSE 5000

## Runtime secrets via env (set in App Runner / docker run): GROQ_API_KEY
CMD ["python", "app/application.py"]
