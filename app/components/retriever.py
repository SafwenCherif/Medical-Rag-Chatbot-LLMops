from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate

from app.components.llm import load_llm
from app.components.vector_store import load_vector_store

from app.common.logger import get_logger
from app.common.custom_exception import CustomException


logger = get_logger(__name__)

CUSTOM_PROMPT_TEMPLATE = """You are a medical assistant. Answer the question in 2-4 lines using ONLY the information in the context below.
If the question has typos, map it to the closest medical term supported by the context and answer that.
If the context truly has no relevant information, reply exactly: "I could not find that in the medical encyclopedia."

Context:
{context}

Question:
{question}

Answer:
"""


def set_custom_prompt():
    return PromptTemplate(
        template=CUSTOM_PROMPT_TEMPLATE,
        input_variables=["context", "question"],
    )


def _correct_medical_query(llm, query: str) -> str:
    """Light typo repair so retrieval matches encyclopedia terms better."""
    try:
        prompt = (
            "Fix spelling typos in this medical question. "
            "If a word is clearly a misspelling of a common medical term "
            "(example: 'epathit' -> 'hepatitis', 'algesic' -> 'analgesic'), "
            "replace it with that term. "
            "Return ONLY the corrected question, nothing else.\n\n"
            f"Question: {query}"
        )
        corrected = llm.invoke(prompt)
        text = getattr(corrected, "content", str(corrected)).strip()
        return text or query
    except Exception as e:
        logger.warning("Query correction failed, using original query: %s", e)
        return query


def create_qa_chain():
    try:
        logger.info("Loading vector store for context")
        db = load_vector_store()

        if db is None:
            raise CustomException("Vector store not present or empty")

        llm = load_llm()

        if llm is None:
            raise CustomException("LLM not loaded")

        # k=3 gives the LLM enough chunks; k=1 was too fragile for typos / phrasing
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=db.as_retriever(search_kwargs={"k": 3}),
            return_source_documents=False,
            chain_type_kwargs={"prompt": set_custom_prompt()},
        )

        logger.info("Successfully created the QA chain")

        class CorrectingQAChain:
            """Wrap RetrievalQA with a cheap typo-correction pass."""

            def invoke(self, inputs):
                query = inputs.get("query") or inputs.get("question") or ""
                fixed = _correct_medical_query(llm, query)
                if fixed != query:
                    logger.info("Corrected query: %r -> %r", query, fixed)
                return qa_chain.invoke({"query": fixed})

        return CorrectingQAChain()

    except Exception as e:
        error_message = CustomException("Failed to make a QA chain", e)
        logger.error(str(error_message))
        return None
