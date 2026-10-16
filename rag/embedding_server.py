"""Local embedding server for Weaviate.

Weaviate's `text2vec-transformers` module does not embed text itself; it sends the
text to an HTTP "inference API" and stores the vector that comes back. This module
is that API: it wraps `utils.generate_embedding` in a tiny Flask app.

Importing this module starts the server in a background thread and waits until it
answers, so the notebook can use it right after `from rag import embedding_server`.
"""

import logging
import socket
import threading
import time

from flask import Flask, jsonify, request

from .utils import generate_embedding

app = Flask(__name__)

HOST = "127.0.0.1"
PORT = 5050


# --- Health & Readiness Check Endpoints ---
# Weaviate calls these to check that the inference API is up before using it.
@app.route('/', methods=['GET'])
@app.route('/.well-known/ready', methods=['GET'])
@app.route('/.well-known/live', methods=['GET'])
@app.route('/meta', methods=['GET'])
def health_check():
  return jsonify({'status': 'ready'}), 200


# --- Vectorization Endpoint (text2vec-transformers inference API) ---
@app.route('/vectors', methods=['POST'])
def vectorize():
  data = request.get_json(force=True, silent=True) or {}

  # Weaviate sends a single string in 'text'
  text_input = data.get('text', '')
  if not isinstance(text_input, str):
    text_input = str(text_input)

  try:
    vector = generate_embedding(text_input)
  except Exception as e:
    print(f'Vectorize Error: {e}')
    return jsonify({'error': str(e)}), 500

  # Response shape expected by Weaviate's text2vec-transformers module.
  return jsonify({'text': text_input, 'vector': vector, 'dim': len(vector)}), 200


# Silence Flask default logs (one line per request would flood the notebook)
app.logger.disabled = True
logging.getLogger('werkzeug').setLevel(logging.ERROR)


def _port_in_use(host: str, port: int) -> bool:
  """Return True if something is already listening on host:port."""
  with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.settimeout(0.5)
    return s.connect_ex((host, port)) == 0


def run_app():
  # threaded=True lets Weaviate send several embedding requests at once.
  app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)


def _start_server(timeout: float = 30.0) -> None:
  """Start the server in a daemon thread and block until it accepts connections."""
  if _port_in_use(HOST, PORT):
    # Already running (e.g. the module was re-imported in the same kernel).
    return

  thread = threading.Thread(target=run_app, daemon=True)
  thread.start()

  # Wait until the server is reachable so Weaviate never calls a server that isn't up yet.
  deadline = time.time() + timeout
  while not _port_in_use(HOST, PORT):
    if not thread.is_alive() or time.time() > deadline:
      raise RuntimeError(f'Embedding server failed to start on {HOST}:{PORT}')
    time.sleep(0.1)


# Start the server once, in the background, when this module is imported.
_start_server()
