"""Shared helpers for the Sandogh FAQ chatbot.

This module provides three things:
1. Persian text normalization (applied to the FAQ chunks and to user questions).
2. Text embeddings (used by the Flask server that Weaviate calls to vectorize text).
3. A thin wrapper around an LLM served by OpenRouter (used by the notebook to generate answers).
"""

import os
import re
import threading
import time
from typing import Dict, List, Optional, Union

import requests
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# The project root is the folder above this package (rag/). .env and the model
# cache live there, so they are found no matter where the notebook is started.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Read settings such as OPENROUTER_API_KEY from the .env file in the project root
# (the file is git-ignored, so the key never ends up on GitHub).
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# ------------------------------------------------------------
# Persian normalization
# ------------------------------------------------------------
# The same Persian word can be typed in several ways (Arabic vs Persian letters,
# Persian vs Latin digits, different "half-space" characters). Keyword search only
# matches identical words, so the FAQ chunks and the user's question are both
# normalized the same way before they are stored or searched.
_ZWNJ = "‌"  # zero-width non-joiner, the Persian half-space (as in می‌شود)

_CHAR_MAP = str.maketrans({
    # Arabic letters -> Persian letters
    "ي": "ی", "ى": "ی", "ك": "ک",
    # Persian and Arabic-Indic digits -> Latin digits, so "۱۴۱" matches "141"
    **{d: str(i) for i, d in enumerate("۰۱۲۳۴۵۶۷۸۹")},
    **{d: str(i) for i, d in enumerate("٠١٢٣٤٥٦٧٨٩")},
    # Characters the scraped FAQ uses in place of a half-space
    # (e.g. "صندوق¬های", "شرکت\xadها", "صندوق‏های")
    "¬": _ZWNJ, "­": _ZWNJ, "‏": _ZWNJ, "‎": _ZWNJ,
    # Tatweel (letter-stretching character), e.g. "صنـدوق"
    "ـ": None,
})

# Arabic diacritics (harakat) such as fatḥatān in "قطعاً"
_DIACRITICS = re.compile("[ً-ٰٟ]")


def normalize_persian(text: str) -> str:
    """Return the text with unified letters, digits and half-spaces."""
    text = _DIACRITICS.sub("", text.translate(_CHAR_MAP))
    text = re.sub(f"{_ZWNJ}+", _ZWNJ, text)           # repeated half-spaces -> one
    text = re.sub(f"{_ZWNJ}*(\\s+){_ZWNJ}*", r"\1", text)  # a half-space next to a space is meaningless
    return re.sub(r"\s+", " ", text).strip(" " + _ZWNJ)


# ------------------------------------------------------------
# Embeddings
# ------------------------------------------------------------
# The FAQ data is Persian, so a multilingual model is required for useful
# retrieval (BAAI/bge-base-en-v1.5 is English-only). Override with the
# EMBEDDING_MODEL environment variable if needed.
# NOTE: if you change the model after the Weaviate collection was built, delete
# the weaviate_data/ folder so the data is re-embedded (vector sizes must match).
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

# Store downloaded model weights in the project root (not in whatever directory
# the notebook happens to be started from), so they are downloaded only once.
_MODEL_CACHE_DIR = os.path.join(PROJECT_ROOT, ".models")

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
# LLM (via OpenRouter)
# ------------------------------------------------------------
# OpenRouter gives access to many models (including free ones, marked ":free")
# through one OpenAI-compatible API. Free models are renamed or retired from time
# to time; if this one stops working, pick another ":free" model from
# https://openrouter.ai/models and set it in the LLM_MODEL environment variable.
LLM_MODEL = os.getenv("LLM_MODEL", "google/gemma-4-31b-it:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_RETRIES = 3  # extra attempts after a rate-limit (429) response


def generate_with_multiple_input(
    messages: List[Dict],
    system: Optional[str] = None,
    max_tokens: int = 2000,
    model: str = LLM_MODEL,
) -> Dict[str, str]:
    """Send a conversation to the LLM and return {"role": "assistant", "content": <text>}.

    Args:
        messages: Conversation history, e.g. [{"role": "user", "content": "..."}].
        system: Optional system prompt (instructions for the assistant).
        max_tokens: Upper limit on the length of the reply.
        model: OpenRouter model ID.
    """
    # The key is read here (not at import time) so that importing this module for
    # embeddings only, e.g. by the Flask server, works without a key.
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Create a free key at https://openrouter.ai/keys "
            "and put it in the .env file (see .env.example), then restart the kernel."
        )

    # In the OpenAI message format the system prompt is the first message.
    if system:
        messages = [{"role": "system", "content": system}] + messages

    # Free models are shared and rate-limited, so a 429 ("too many requests") is
    # common. Wait and try again a few times before giving up (5s, 10s, 20s).
    for attempt in range(MAX_RETRIES + 1):
        response = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
            timeout=60,
        )
        if response.status_code != 429 or attempt == MAX_RETRIES:
            break
        wait = 5 * 2 ** attempt
        print(f"Rate limited by the free model, retrying in {wait}s ...")
        time.sleep(wait)

    data = response.json()
    # Errors (invalid key, unknown model, rate limit on free models, ...) come back
    # as {"error": {"message": ...}}, sometimes even with status 200.
    if not response.ok or "error" in data:
        error = data.get("error", {})
        message = error.get("message", response.text)
        # "Provider returned error" is generic; the provider's own reason is in metadata.raw.
        raw = (error.get("metadata") or {}).get("raw")
        if raw:
            message += f" - {raw}"
        if response.status_code == 429:
            message += (
                "\nThe free model is busy or you reached its rate limit. Wait a minute and try "
                "again, or set another ':free' model with LLM_MODEL in .env."
            )
        raise RuntimeError(f"OpenRouter request failed ({response.status_code}): {message}")

    return {"role": "assistant", "content": data["choices"][0]["message"]["content"]}


def generate_with_single_input(
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 2000,
    model: str = LLM_MODEL,
) -> Dict[str, str]:
    """Send a single user prompt to the LLM (convenience wrapper around the function above)."""
    return generate_with_multiple_input(
        [{"role": "user", "content": prompt}],
        system=system,
        max_tokens=max_tokens,
        model=model,
    )
