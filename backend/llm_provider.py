import os
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Interface the rest of the app uses to talk to a language model.

    Each call to complete() is a standalone request with no memory of earlier
    calls, so one scan can never see another scan's resume text.
    """

    name: str = "base"
    model: str = "unknown"  # used to price usage

    @abstractmethod
    async def complete(self, prompt: str, system_message: str, request_id: Optional[str] = None) -> str:
        """Send one prompt and return the model's text reply"""


class LLMReply(str):
    """A model reply that can carry the token counts the provider reported.

    It behaves exactly like the reply text. Adapters whose library reports usage should
    return LLMReply(text, input_tokens=..., output_tokens=...); otherwise usage is estimated.
    """

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    def __new__(cls, text: str, input_tokens: Optional[int] = None, output_tokens: Optional[int] = None):
        reply = super().__new__(cls, text)
        reply.input_tokens = input_tokens
        reply.output_tokens = output_tokens
        return reply


class EmergentProvider(LLMProvider):
    """Adapter for the emergentintegrations library"""

    name = "emergent"
    # emergentintegrations does not expose token counts, so usage is estimated

    def __init__(self, api_key: str, provider: str = "openai", model: str = "gpt-4o"):
        if not api_key:
            raise ValueError("EMERGENT_LLM_KEY not found in environment variables")
        # Imported here so the rest of the app loads without this package
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        self._LlmChat = LlmChat
        self._UserMessage = UserMessage
        self._api_key = api_key
        self._provider = provider
        self._model = model
        self.model = model

    async def complete(self, prompt: str, system_message: str, request_id: Optional[str] = None) -> str:
        # A new chat object and session id per call keeps history from leaking between scans
        session_id = f"resume-scan-{request_id or uuid.uuid4().hex}"
        chat = self._LlmChat(
            api_key=self._api_key,
            session_id=session_id,
            system_message=system_message,
        ).with_model(self._provider, self._model)
        return await chat.send_message(self._UserMessage(text=prompt))


def get_llm_provider() -> LLMProvider:
    """Build the provider chosen by LLM_PROVIDER (default: emergent)"""
    choice = os.getenv("LLM_PROVIDER", "emergent").lower()
    if choice == "emergent":
        return EmergentProvider(
            api_key=os.getenv("EMERGENT_LLM_KEY", ""),
            provider=os.getenv("LLM_VENDOR", "openai"),
            model=os.getenv("LLM_MODEL", "gpt-4o"),
        )
    raise ValueError(f"Unknown LLM_PROVIDER '{choice}'. Add an adapter in llm_provider.py.")
