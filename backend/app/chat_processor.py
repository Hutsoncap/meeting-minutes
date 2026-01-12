"""
Chat Processor for meeting conversations.
Uses RAG-style context retrieval from meeting transcripts.
"""

import logging
import os
from typing import List, Optional, AsyncGenerator
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider

logger = logging.getLogger(__name__)


class ChatProcessor:
    """Processes chat messages with meeting context."""

    def __init__(self, db):
        self.db = db
        logger.info("ChatProcessor initialized.")

    async def get_relevant_context(self, meeting_id: str, query: str, max_chars: int = 8000) -> str:
        """
        Get relevant transcript context for a query.
        For simplicity, we use the full transcript (truncated if needed).
        A more sophisticated approach would use embeddings and vector search.
        """
        transcript = await self.db.get_meeting_transcript_text(meeting_id)
        if not transcript:
            return ""

        # Truncate if too long
        if len(transcript) > max_chars:
            # Get start and end portions
            half = max_chars // 2
            transcript = transcript[:half] + "\n\n[...transcript truncated...]\n\n" + transcript[-half:]

        return transcript

    async def generate_response(
        self,
        meeting_id: str,
        message: str,
        conversation_history: List[dict],
        model_provider: str = "ollama",
        model_name: str = "llama3.2:latest"
    ) -> str:
        """
        Generate a response to a chat message using meeting context.
        """
        logger.info(f"Generating chat response for meeting {meeting_id} with {model_provider}/{model_name}")

        # Get transcript context
        transcript_context = await self.get_relevant_context(meeting_id, message)

        if not transcript_context:
            return "I don't have any transcript content for this meeting yet. Please record a meeting first."

        # Build conversation context
        history_text = ""
        for msg in conversation_history[-6:]:  # Last 6 messages for context
            role = "User" if msg['role'] == 'user' else "Assistant"
            history_text += f"{role}: {msg['content']}\n"

        # Build the prompt
        system_prompt = """You are a helpful assistant that answers questions about meeting content.
You have access to the meeting transcript below. Answer questions accurately based on what was discussed.
If something wasn't discussed in the meeting, say so. Be concise but informative.

MEETING TRANSCRIPT:
{transcript}

Previous conversation:
{history}
"""

        full_prompt = system_prompt.format(
            transcript=transcript_context,
            history=history_text if history_text else "(No previous messages)"
        )

        # Initialize the LLM based on provider
        llm = None
        try:
            if model_provider == "claude":
                api_key = await self.db.get_api_key("claude")
                if not api_key:
                    raise ValueError("Claude API key not configured")
                llm = AnthropicModel(model_name, provider=AnthropicProvider(api_key=api_key))

            elif model_provider == "openai":
                api_key = await self.db.get_api_key("openai")
                if not api_key:
                    raise ValueError("OpenAI API key not configured")
                llm = OpenAIModel(model_name, provider=OpenAIProvider(api_key=api_key))

            elif model_provider == "groq":
                api_key = await self.db.get_api_key("groq")
                if not api_key:
                    raise ValueError("Groq API key not configured")
                llm = GroqModel(model_name, provider=GroqProvider(api_key=api_key))

            elif model_provider == "openrouter":
                api_key = await self.db.get_api_key("openrouter")
                if not api_key:
                    raise ValueError("OpenRouter API key not configured")
                llm = OpenAIModel(
                    model_name=model_name,
                    provider=OpenAIProvider(
                        base_url="https://openrouter.ai/api/v1",
                        api_key=api_key
                    )
                )

            elif model_provider == "ollama":
                ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
                ollama_base_url = f"{ollama_host}/v1"
                llm = OpenAIModel(
                    model_name=model_name,
                    provider=OpenAIProvider(base_url=ollama_base_url)
                )

            else:
                raise ValueError(f"Unsupported model provider: {model_provider}")

            # Create agent and run
            agent = Agent(llm, result_type=str)

            user_message = f"{full_prompt}\n\nUser question: {message}"
            result = await agent.run(user_message)

            response_text = result.data if hasattr(result, 'data') else str(result)
            logger.info(f"Generated response: {response_text[:100]}...")
            return response_text

        except Exception as e:
            logger.error(f"Error generating chat response: {str(e)}", exc_info=True)
            raise

    async def create_conversation_title(self, first_message: str) -> str:
        """Generate a short title for a conversation based on the first message."""
        # Simple approach: use first few words of the message
        words = first_message.split()[:5]
        title = " ".join(words)
        if len(first_message) > len(title):
            title += "..."
        return title[:50]  # Max 50 chars
