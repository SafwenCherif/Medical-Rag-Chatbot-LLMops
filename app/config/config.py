import os

from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.environ.get("HF_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL",
    "meta-llama/llama-3.1-8b-instruct",
)

# Kept for compatibility with course materials (not used by current Groq path)
HUGGINGFACE_REPO_ID = "mistralai/Mistral-7B-Instruct-v0.3"

DB_FAISS_PATH = "vectorstore/db_faiss"
DATA_PATH = "data/"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
