# Sandogh FAQ Chatbot

A question-answering chatbot for the **Iran National Innovation Fund** (صندوق نوآوری و شکوفایی).
Ask a question in Persian (or English) and it answers using the fund's official FAQ.

It uses **RAG (retrieval-augmented generation)**: first it finds the FAQ entries most related to the question, then **Claude** writes an answer based only on those entries. If the FAQ doesn't contain the answer, it says so instead of guessing.

## How it works

```
 inif.ir FAQ pages
        │  extract_from_site.py (scraper)
        ▼
 faq_qa_pairs.csv  (134 question/answer pairs)
        │  embedded with BAAI/bge-m3 (flask_app.py + utils.py)
        ▼
 Weaviate vector database
        │  finds the 3 FAQ entries closest to the question
        ▼
 Claude (claude-opus-5-5)
        │  answers using only those entries
        ▼
     Answer
```

1. **Scraping:** `extract_from_site.py` downloads the FAQ pages from [inif.ir](https://www.inif.ir) (9 categories, such as guarantees, investment, leasing and legal) and saves the question/answer pairs to a CSV file.
2. **Embedding:** each FAQ entry is turned into a vector (a list of numbers that captures its meaning) with the multilingual model `BAAI/bge-m3`, which works well for Persian. A small local Flask server provides these vectors to the database.
3. **Storage and search:** the vectors are stored in an embedded [Weaviate](https://weaviate.io) database. For each question, it returns the most similar FAQ entries.
4. **Answering:** the question and the retrieved entries are sent to Claude, which writes the final answer in the language of the question.

## Project files

| File | Purpose |
|---|---|
| `main_project.ipynb` | The main notebook: builds the database and answers questions, step by step |
| `utils.py` | Embedding model and the functions that call Claude |
| `flask_app.py` | Local server that Weaviate uses to turn text into vectors |
| `extract_from_site.py` | Scraper that collects the FAQ from inif.ir |
| `faq_qa_pairs.csv` | The collected FAQ data (category, question, answer) |
| `requirements.txt` | Python packages needed |
| `CHANGELOG.md` | History of changes between versions |

## Getting started

### Requirements
- Python 3.10 to 3.14. Python 3.15 does not work yet: PyTorch (needed by `sentence-transformers`) has no release for it.
- An [Anthropic API key](https://console.anthropic.com/) for Claude
- About 3 GB of free disk space (the embedding model is downloaded on first run)

### 1. Download the project
```bash
git clone https://github.com/akbariela/naiveRAG.git
cd naiveRAG
```

### 2. Install the packages
Create a virtual environment with a supported Python version, then install the packages into it.

Windows (PowerShell):
```powershell
py -3.14 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt jupyter
```
macOS / Linux:
```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt jupyter
```

> Install **`weaviate-client`**, not `weaviate`. The `weaviate` package on PyPI is an empty placeholder. If it is installed, `import weaviate` fails with *"cannot import name 'classes' from partially initialized module 'weaviate'"*. Remove it with `pip uninstall weaviate`.

### 3. Set your API key
Windows (PowerShell):
```powershell
$env:ANTHROPIC_API_KEY = "your-api-key"
```
macOS / Linux:
```bash
export ANTHROPIC_API_KEY="your-api-key"
```

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

The notebook first shows the 3 FAQ entries it found, then Claude's answer based on them.

## Configuration

| Setting | Where | Default |
|---|---|---|
| Claude model | `CLAUDE_MODEL` in `utils.py` | `claude-opus-5-5` |
| Embedding model | `EMBEDDING_MODEL` environment variable | `BAAI/bge-m3` |
| Number of FAQ entries used per answer | `top_k` in `answer_question()` | `3` |

The project uses local ports **5050** (embedding server), **8079** and **50050** (Weaviate). Make sure they are free.

> If you change the embedding model after the database was built, delete the `chatbot/` folder so the data is rebuilt with the new model.

## Updating the FAQ data

The included `faq_qa_pairs.csv` is ready to use. To collect the data again:
```bash
python extract_from_site.py
```
Note: the scraper saves to `qa_pairs.csv`, while the notebook reads `faq_qa_pairs.csv`. Rename the new file (or update the file name in the notebook) before using it.

## Data source

The FAQ content belongs to the Iran National Innovation Fund and was collected from its public FAQ pages at [inif.ir](https://www.inif.ir). This project is not affiliated with the fund.

## Changes

See [CHANGELOG.md](CHANGELOG.md) for the history of changes.
