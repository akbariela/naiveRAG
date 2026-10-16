# Changelog

All notable changes to the Sandogh FAQ chatbot are recorded here.
The FAQ data (`faq_qa_pairs.csv`) has not changed in any of these versions.

## [Unreleased]

### Changed: project structure
- Files are organized into folders: `rag/` (code imported by the notebook), `data/` (the FAQ CSV) and `scripts/` (the scraper). The notebook stays at the root.
  - `utils.py` → `rag/utils.py`; `flask_app.py` → `rag/embedding_server.py`; `faq_qa_pairs.csv` → `data/faq_qa_pairs.csv`; `extract_from_site.py` → `scripts/extract_from_site.py`.
  - The notebook imports `from rag import embedding_server` and `from rag.utils import ...`, and reads `data/faq_qa_pairs.csv`.
  - `rag/utils.py` finds `.env` and `.models/` in the project root, so they stay where they were and the model is not downloaded again.
  - The Weaviate database folder is renamed from `chatbot/` to `weaviate_data/` (git-ignored). The database is rebuilt once on the next run.
  - The scraper writes to `data/qa_pairs.csv`, from any working directory. Its scraping logic is unchanged.
- Removed old leftovers: `Untitled.ipynb` (an early scratch notebook) and `chatbot_project/` (the v1.0 database). Both are still in git history.

### Added
- `README.md`: setup guide and a troubleshooting table (kernel restart, missing key, rate limits, busy ports, Windows). It states that macOS or Linux is required (embedded Weaviate does not run on Windows; use WSL), lists Python 3.10 to 3.14 as supported (PyTorch has no Python 3.15 release yet), installs into a virtual environment, and warns against the placeholder `weaviate` package (the real client is `weaviate-client`).
- **Persian normalization:** `normalize_persian()` in `utils.py` unifies Arabic and Persian letters (ي/ى→ی, ك→ک), Persian/Arabic digits (→ Latin), the characters the scraped FAQ uses instead of a half-space (`¬`, soft hyphen, RLM/LRM → ZWNJ), and removes diacritics and tatweel. It is applied to every chunk and to every question.
- `.env.example`: template for the `.env` file that holds `OPENROUTER_API_KEY` (and optionally `LLM_MODEL`). `utils.py` loads `.env` with `python-dotenv`.

### Changed
- **Hybrid search:** `retrieve()` uses `collection.query.hybrid` (vector + BM25 keyword search on `chunk`, `alpha=0.5`) instead of `near_text`.
- The collection is now `sandogh_faq_v2`, so the normalized chunks are built fresh instead of mixing with the old ones in `./chatbot`.
- **LLM switched from Claude to a free OpenRouter model** (`google/gemma-4-31b-it:free` by default, overridable with `LLM_MODEL`), so no paid API key is needed. `utils.py` now calls OpenRouter's OpenAI-compatible endpoint with `requests`. `generate_with_single_input` / `generate_with_multiple_input` return the same `{"role", "content"}` dict as before; the `effort` parameter was removed and the default `max_tokens` is now 2000.
- The API key is read when a request is made, not at import, so the Flask embedding server starts without a key. A missing key or an OpenRouter error (invalid key, unknown model, rate limit) raises a `RuntimeError` with a readable message.
- `requirements.txt`: removed `anthropic`, added `python-dotenv`; `requests` is now listed under the chatbot packages.
- Collection creation uses `vector_config=[Configure.Vectors.text2vec_transformers(...)]` instead of the deprecated `vectorizer_config` / `Configure.NamedVectors`.
- `chatbot/` (the Weaviate database, rebuilt by the notebook) is now in `.gitignore` and no longer tracked by git. Local files are kept.
- `main_project.ipynb`: saved outputs from an old Windows run were cleared (they contained an outdated error and a local file path).
- Rate limits on free models: a 429 response is retried up to 3 times (waiting 5s, 10s, 20s). If it still fails, the error includes the provider's own reason (`metadata.raw`) and a hint to wait or change `LLM_MODEL`.

## [2.1.0] - 2026-10-13

Review pass on top of 2.0.0, plus explanatory comments in every file.

### Fixed
- `utils.py`: embedding calls are now serialized with a lock. Weaviate sends batches concurrently and Hugging Face fast tokenizers can fail with "Already borrowed" when used from several threads at once.
- `flask_app.py`: importing the module now waits until the embedding server accepts connections, so Weaviate never calls a server that isn't up yet.
- `flask_app.py`: the server is not started a second time if port 5050 is already in use (e.g. on re-import).
- `main_project.ipynb`: chunks are inserted whenever the collection holds fewer objects than the CSV, not only when it is empty. An interrupted first load now recovers on the next run (deterministic UUIDs prevent duplicates).

### Changed
- `utils.py`: the embedding model cache (`.models`) is stored next to `utils.py` instead of the current working directory.
- `flask_app.py`: added a `HOST` constant and explicit `threaded=True`.
- `main_project.ipynb`: the server address is defined once (`INFERENCE_URL`), and the notebook prints how many chunks were loaded.

### Documentation
- Module docstrings, function docstrings and inline comments in `utils.py` and `flask_app.py`.
- A markdown explanation before each notebook step (8 sections); the Persian code comment was translated to English.

## [2.0.0] - 2026-10-12

### Changed
- **LLM switched from local Ollama (`qwen3.5:9b`) to Claude (`claude-opus-5-5`)** via the official `anthropic` SDK. `generate_with_single_input` / `generate_with_multiple_input` keep the same `{"role", "content"}` return value.
  - Effort is set explicitly (`medium`, configurable per call).
  - Server-side refusal fallback is enabled: a declined request is retried on Anthropic's recommended fallback model; if every model declines, a `RuntimeError` is raised.
  - The "answer only from the context" instructions moved to a system prompt; context and question are sent in XML-tagged blocks; answers are in the question's language.
- **Embedding model switched from `BAAI/bge-base-en-v1.5` (English-only) to `BAAI/bge-m3` (multilingual)** for Persian retrieval. Vectors are normalized. Override with the `EMBEDDING_MODEL` environment variable.
- `flask_app.py`: binds to `127.0.0.1` instead of `0.0.0.0`; simplified `/vectors`; added a `PORT` constant.
- `main_project.ipynb`: collection renamed from `chunking_example` to `sandogh_faq`; only the `chunk` field is embedded; batch size 32 instead of 1; failed inserts are reported; query code refactored into `retrieve()` and `answer_question()`; outputs cleared.

### Removed
- `utils.py` (~580 → ~75 lines): duplicate imports, unreachable Together/OpenAI code, SSL-bypass HTTP clients, unused ipywidgets UI, duplicate `print_object_properties`, `suppress_subprocess_output`, and `kill_processes_on_ports` (which crashed because `psutil`/`socket` were never imported).
- `flask_app.py`: `flask_cors` (not needed; Weaviate calls the server directly).
- No longer required packages: `openai`, `together`, `httpx`, `ipywidgets`, `psutil`, `flask-cors`.

### Fixed
- `main_project.ipynb`: `created_chuncks` typo.

## [1.0.0]

Original version: scraper + Flask embedding server (`bge-base-en-v1.5`) + embedded Weaviate + local Ollama LLM.
