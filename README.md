# Sandogh FAQ Chatbot

A question-answering chatbot for the **Iran National Innovation Fund** (صندوق نوآوری و شکوفایی).
Ask a question in Persian (or English) and it answers using the fund's official FAQ.

It uses **RAG (retrieval-augmented generation)**: first it finds the FAQ entries most related to the question, then an **LLM** (a free model via [OpenRouter](https://openrouter.ai)) writes an answer based only on those entries. If the FAQ doesn't contain the answer, it says so instead of guessing.

## How it works

```
 inif.ir FAQ pages
        │  scripts/extract_from_site.py (scraper)
        ▼
 data/faq_qa_pairs.csv  (134 question/answer pairs)
        │  embedded with BAAI/bge-m3 (rag/embedding_server.py + rag/utils.py)
        ▼
 Weaviate vector database
        │  hybrid search (meaning + keywords) finds the 3 best FAQ entries
        ▼
 LLM via OpenRouter (google/gemma-4-31b-it:free)
        │  answers using only those entries
        ▼
     Answer
```

1. **Scraping:** `scripts/extract_from_site.py` downloads the FAQ pages from [inif.ir](https://www.inif.ir) (9 categories, such as guarantees, investment, leasing and legal) and saves the question/answer pairs to a CSV file.
2. **Embedding:** each FAQ entry is turned into a vector (a list of numbers that captures its meaning) with the multilingual model `BAAI/bge-m3`, which works well for Persian. A small local Flask server provides these vectors to the database.
3. **Storage and search:** the vectors are stored in an embedded [Weaviate](https://weaviate.io) database. For each question, it runs a **hybrid search**: vector search finds entries with a similar meaning, and keyword search (BM25) finds entries that use the same words. The best 3 are returned. Before storing and searching, all text goes through `normalize_persian` (in `rag/utils.py`), which unifies Arabic/Persian letters (ي→ی, ك→ک), digits (۱۴۱→141) and half-space characters, so words match however they were typed.
4. **Answering:** the question and the retrieved entries are sent to the LLM, which writes the final answer in the language of the question.

## Project structure

```
naiveRAG/
├── main_project.ipynb        # the main notebook: builds the database and answers questions
├── rag/                      # code imported by the notebook
│   ├── utils.py              # Persian normalization, embedding model, LLM calls
│   └── embedding_server.py   # local Flask server that Weaviate uses to turn text into vectors
├── data/
│   └── faq_qa_pairs.csv      # the FAQ data (category, question, answer)
├── scripts/
│   └── extract_from_site.py  # scraper that collects the FAQ from inif.ir
├── requirements.txt          # Python packages needed
├── .env.example              # template for your .env file (API key, optional model name)
├── README.md
└── CHANGELOG.md              # history of changes
```

Created when you run the project (git-ignored, so they never go to GitHub):

| Path | What it is |
|---|---|
| `.env` | Your API key (you create it from `.env.example`) |
| `.models/` | The downloaded embedding model (about 5 GB, downloaded once) |
| `weaviate_data/` | The vector database the notebook builds |

## Getting started

### Requirements
- **macOS or Linux.** The notebook uses Weaviate's embedded mode, which does not run on Windows. On Windows, use [WSL](https://learn.microsoft.com/windows/wsl/install) and follow the Linux steps.
- Python 3.10 to 3.14. Python 3.15 does not work yet: PyTorch (needed by `sentence-transformers`) has no release for it.
- A free [OpenRouter API key](https://openrouter.ai/keys) (no payment needed for `:free` models)
- About 5 GB of free disk space (the embedding model is downloaded on first run)

### 1. Download the project
```bash
git clone https://github.com/akbariela/naiveRAG.git
cd naiveRAG
```

### 2. Install the packages
Create a virtual environment with a supported Python version, then install the packages into it.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt jupyter
```

> Install **`weaviate-client`**, not `weaviate`. The `weaviate` package on PyPI is an empty placeholder. If it is installed, `import weaviate` fails with *"cannot import name 'classes' from partially initialized module 'weaviate'"*. Remove it with `pip uninstall weaviate`.

### 3. Set your API key
Copy `.env.example` to `.env` and put your key in it:
```
OPENROUTER_API_KEY=your-openrouter-key
```
`rag/utils.py` loads this file automatically. `.env` is listed in `.gitignore`, so your key is never committed. Run `git status` before pushing to make sure `.env` doesn't appear.

> Free models have rate limits and are sometimes renamed or removed. If you get a "model not found" or rate-limit error, pick another model ending in `:free` from [openrouter.ai/models](https://openrouter.ai/models) and set `LLM_MODEL=...` in `.env`.

### 4. Run the notebook
```bash
jupyter notebook main_project.ipynb
```
Start Jupyter from the activated virtual environment so the notebook uses its packages. Run the cells from top to bottom. The first run takes longer: it downloads the embedding model and builds the database. Later runs reuse both.

## Example

```python
answer_question("شرایط دریافت ضمانت‌نامه چیست؟")
# "What are the requirements for getting a guarantee?"
```

The notebook first shows the 3 FAQ entries it found, then the LLM's answer based on them.

## Configuration

| Setting | Where | Default |
|---|---|---|
| LLM model | `LLM_MODEL` in `.env` (or environment) | `google/gemma-4-31b-it:free` |
| Embedding model | `EMBEDDING_MODEL` environment variable | `BAAI/bge-m3` |
| Number of FAQ entries used per answer | `top_k` in `answer_question()` | `3` |
| Balance of vector vs keyword search | `alpha` in `retrieve()` (0 = keywords only, 1 = vectors only) | `0.5` |

The project uses local ports **5050** (embedding server), **8079** and **50050** (Weaviate). Make sure they are free.

> If you change the embedding model after the database was built, delete the `weaviate_data/` folder so the data is rebuilt with the new model.

## Troubleshooting

| Problem | Fix |
|---|---|
| You edited a file in `rag/` or `.env`, but the notebook still behaves the old way | Restart the kernel and run all cells again. Python loads the `rag` code and `.env` once, at import. |
| `OPENROUTER_API_KEY is not set` | Create `.env` from `.env.example` (not by editing `.env.example` itself), add your key, restart the kernel. |
| `OpenRouter request failed (429)` | The free model is rate-limited or busy. The code already retries 3 times; wait a minute, or set another `:free` model with `LLM_MODEL` in `.env`. |
| Weaviate fails to start because ports 8079/50050 are in use | An earlier Weaviate is still running. Restart the kernel, or run `pkill -f weaviate`, then run the cell again. Run the last cell (`client.close()`) when you are done. |
| `Windows is not supported with EmbeddedDB` | Embedded Weaviate needs macOS or Linux. Use WSL on Windows. |

## Updating the FAQ data

The included `data/faq_qa_pairs.csv` is ready to use. To collect the data again:
```bash
python scripts/extract_from_site.py
```
The scraper saves to `data/qa_pairs.csv`, while the notebook reads `data/faq_qa_pairs.csv`. Check the new file, then rename it to `faq_qa_pairs.csv` to use it. After replacing the data, delete `weaviate_data/` so the database is rebuilt.

## Data source

The FAQ content belongs to the Iran National Innovation Fund and was collected from its public FAQ pages at [inif.ir](https://www.inif.ir). This project is not affiliated with the fund.

## Changes

See [CHANGELOG.md](CHANGELOG.md) for the history of changes.
