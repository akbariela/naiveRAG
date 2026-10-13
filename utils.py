"""Shared helpers for the Sandogh FAQ chatbot.

This module provides two things:
1. Text embeddings (used by the Flask server that Weaviate calls to vectorize text).
2. A thin wrapper around the Claude API (used by the notebook to generate answers).
"""

import os
import threading
from typing import Dict, List, Optional, Union

import anthropic
from sentence_transformers import SentenceTransformer

# ------------------------------------------------------------
# Embeddings
# ------------------------------------------------------------
# The FAQ data is Persian, so a multilingual model is required for useful
# retrieval (BAAI/bge-base-en-v1.5 is English-only). Override with the
# EMBEDDING_MODEL environment variable if needed.
# NOTE: if you change the model after the Weaviate collection was built, delete
# the ./chatbot folder so the data is re-embedded (vector sizes must match).
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

# Store downloaded model weights next to this file (not in whatever directory
# the notebook happens to be started from), so they are downloaded only once.
_MODEL_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".models")

# Loaded once at import time so the first Weaviate request doesn't time out
# while the model is still loading.
_embedding_model = SentenceTransformer(EMBEDDING_MODEL, cache_folder=_MODEL_CACHE_DIR)

# Flask serves requests on several threads, and Weaviate sends batches
# concurrently. Hugging Face fast tokenizers are not safe to call from several
# threads at once ("Already borrowed" errors), so encoding is serialized.
_embedding_lock = threading.Lock()


def generate_embedding(text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
    """Embed a string (returns one vector) or a list of strings (returns a list of vectors).

    Vectors are L2-normalized, so cosine similarity equals the dot product.
    """
    with _embedding_lock:
        return _embedding_model.encode(text, normalize_embeddings=True).tolist()


# ------------------------------------------------------------
# LLM (Claude)
# ------------------------------------------------------------
CLAUDE_MODEL = "claude-opus-5-5"

# Reads ANTHROPIC_API_KEY (or another configured Anthropic credential, such as an
# `ant auth login` profile) from the environment. The SDK retries rate-limit and
# server errors automatically (2 retries by default).
_client = anthropic.Anthropic()


def generate_with_multiple_input(
    messages: List[Dict],
    system: Optional[str] = None,
    max_tokens: int = 16000,
    effort: str = "medium",
    model: str = CLAUDE_MODEL,
) -> Dict[str, str]:
    """Send a conversation to Claude and return {"role": "assistant", "content": <text>}.

    Args:
        messages: Conversation history, e.g. [{"role": "user", "content": "..."}].
        system: Optional system prompt (instructions for the assistant).
        max_tokens: Upper limit on the length of the reply.
        effort: How much reasoning Claude spends: "low", "medium", "high", "xhigh" or "max".
            Thinking is always on for this model; effort is the control for its depth.
        model: Claude model ID.
    """
    request = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
        "output_config": {"effort": effort},
        # If a safety classifier declines the request, the API retries it on
        # Anthropic's recommended fallback model instead of returning a refusal.
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",
    }
    if system:
        request["system"] = system

    response = _client.beta.messages.create(**request)

    # A refusal means every model in the fallback chain declined.
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined the request: {response.stop_details}")

    # The response can contain several block types (thinking, fallback markers, text);
    # only the text blocks make up the visible answer.
    text = "".join(block.text for block in response.content if block.type == "text")
    return {"role": "assistant", "content": text}


def generate_with_single_input(
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 16000,
    effort: str = "medium",
    model: str = CLAUDE_MODEL,
) -> Dict[str, str]:
    """Send a single user prompt to Claude (convenience wrapper around the function above)."""
    return generate_with_multiple_input(
        [{"role": "user", "content": prompt}],
        system=system,
        max_tokens=max_tokens,
        effort=effort,
        model=model,
    )
