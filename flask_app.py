import json
import logging
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
from utils import generate_embedding

app = Flask(__name__)
CORS(app)


# --- Health & Readiness Check Endpoints ---
@app.route('/', methods=['GET'])
@app.route('/.well-known/ready', methods=['GET'])
@app.route('/.well-known/live', methods=['GET'])
@app.route('/meta', methods=['GET'])
def health_check():
  return jsonify({'status': 'ready'}), 200


# --- Vectorization Endpoint ---
@app.route('/vectors', methods=['POST'])
def vectorize():
  try:
    data = request.get_json(force=True, silent=True) or {}

    # Weaviate usually sends 'text' in the request payload
    text_input = data.get('text', '')

    if isinstance(text_input, str):
      text_list = [text_input]
    elif isinstance(text_input, list):
      text_list = text_input
    else:
      text_list = [str(text_input)]

    embeddings = generate_embedding(text_list)

    if hasattr(embeddings, 'tolist'):
      embeddings = embeddings.tolist()

    if (
        isinstance(embeddings, list)
        and len(embeddings) > 0
        and isinstance(embeddings[0], list)
    ):
      vector_data = embeddings[0]
    else:
      vector_data = embeddings

    return (
        jsonify({
            'text': text_input,
            'vector': vector_data,
            'dim': len(vector_data) if isinstance(vector_data, list) else 0,
        }),
        200,
    )

  except Exception as e:
    print(f'Vectorize Error: {e}')
    return jsonify({'error': str(e)}), 500


# Silence Flask default logs
app.logger.disabled = True
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


def run_app():
  app.run(host='0.0.0.0', port=5050, debug=False, use_reloader=False)


flask_thread = threading.Thread(target=run_app, daemon=True)
flask_thread.start()