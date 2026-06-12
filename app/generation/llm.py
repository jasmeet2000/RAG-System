"""
LLM Client Wrapper — Handles communication with the local Ollama instance.

=== WHY THIS FILE EXISTS ===
We need to send our final prompt (System Prompt + Context + User Query) to the
LLM and stream the response back.

While we could use the raw `httpx` library, using the official `ollama` Python
client provides native async support, proper error handling, and a cleaner API.

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  app/pipeline/rag_pipeline.py
  Uses:    ollama (AsyncClient), app.core.config
"""

from typing import AsyncGenerator, Optional

from ollama import AsyncClient
from ollama import ResponseError

from app.core.config import settings
from app.core.exceptions import GenerationError
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMService:
    """
    Service for generating text using a local Ollama LLM.
    """

    def __init__(self):
        # Initialize the async client.
        # It defaults to http://localhost:11434, which can be overridden via config.
        self.host = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        self.model_name = settings.OLLAMA_MODEL
        self.client = AsyncClient(host=self.host)

    async def verify_model_exists(self) -> bool:
        """
        Check if the requested model is actually pulled in the local Ollama instance.
        If not, we can fail fast rather than returning a confusing error to the user.
        """
        try:
            models_response = await self.client.list()
            
            # The ollama library may return a dict (older versions) or a
            # Pydantic-like object (newer versions). Handle both gracefully.
            if isinstance(models_response, dict):
                models_list = models_response.get("models", [])
            else:
                models_list = getattr(models_response, "models", [])
            
            for model_info in models_list:
                # Get the model name — works for both dict and object
                if isinstance(model_info, dict):
                    name = model_info.get("name", "")
                else:
                    name = getattr(model_info, "model", "") or getattr(model_info, "name", "")
                
                if self.model_name in name:
                    return True
            return False
        except Exception as e:
            logger.warning(f"Failed to check Ollama models at {self.host}: {e}")
            return False

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Generate a complete response (blocking until finished).
        Useful for testing or offline batch processing.
        """
        logger.info(f"Generating LLM response using model '{self.model_name}'...")
        
        try:
            response = await self.client.chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                # Options: reduce temperature for more factual (less creative) answers
                options={"temperature": 0.1}
            )
            return response["message"]["content"]
            
        except ResponseError as e:
            raise GenerationError(f"Ollama API returned an error: {e.error}") from e
        except Exception as e:
            raise GenerationError(f"Failed to generate LLM response: {str(e)}") from e

    async def generate_stream(self, system_prompt: str, user_prompt: str) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response.
        CRITICAL FOR UX: LLMs generate text at ~30-50 tokens/second.
        If we wait for the whole answer, the user stares at a spinner for 10 seconds.
        Streaming sends words to the frontend immediately as they are generated.
        """
        logger.info(f"Starting LLM stream using model '{self.model_name}'...")
        
        try:
            async for chunk in await self.client.chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options={"temperature": 0.1},
                stream=True,  # Enable streaming
            ):
                # Yield the raw text token
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]
                    
        except ResponseError as e:
            logger.error(f"Ollama API stream error: {e.error}")
            yield f"\n\n[Error generating response: {e.error}]"
        except Exception as e:
            logger.error(f"Ollama stream failed: {e}")
            yield f"\n\n[System Error during generation]"


# Singleton instance
_llm_service: Optional[LLMService] = None

def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
