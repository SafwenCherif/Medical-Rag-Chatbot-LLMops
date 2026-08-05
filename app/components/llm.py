import os

from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from app.config.config import GROQ_API_KEY, OPENROUTER_API_KEY, OPENROUTER_MODEL
from app.common.logger import get_logger
from app.common.custom_exception import CustomException

logger = get_logger(__name__)


def load_llm(
    model_name: str = "llama-3.1-8b-instant",
    groq_api_key: str = GROQ_API_KEY,
):
    """
    Load a chat LLM.

    Priority:
      1) Groq (preferred — fast free-tier friendly API)
      2) OpenRouter — cheap OpenAI-compatible fallback
    """
    try:
        if groq_api_key:
            logger.info("Loading LLM from Groq (%s)...", model_name)
            llm = ChatGroq(
                groq_api_key=groq_api_key,
                model_name=model_name,
                temperature=0.3,
                max_tokens=256,
            )
            logger.info("LLM loaded successfully from Groq.")
            return llm

        if OPENROUTER_API_KEY:
            logger.info("Groq key missing — loading LLM from OpenRouter (%s)...", OPENROUTER_MODEL)
            llm = ChatOpenAI(
                model=OPENROUTER_MODEL,
                api_key=OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.3,
                max_tokens=256,
                default_headers={
                    "HTTP-Referer": "http://localhost:5000",
                    "X-Title": "Medical RAG Chatbot",
                },
            )
            logger.info("LLM loaded successfully from OpenRouter.")
            return llm

        raise CustomException(
            "No LLM API key found. Set GROQ_API_KEY (preferred, free) or OPENROUTER_API_KEY in .env"
        )

    except Exception as e:
        error_message = CustomException("Failed to load an LLM", e)
        logger.error(str(error_message))
        return None
