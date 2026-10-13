# Changelog

All notable changes to the Sandogh FAQ chatbot are recorded here.
`extract_from_site.py` and `faq_qa_pairs.csv` were not changed in any of these versions.

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
