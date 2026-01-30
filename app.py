import os
from flask import Flask, request, jsonify
from config import API_KEY
from strategy import decide_action

app = Flask(__name__)

def authorized(req):
    return req.headers.get("X-API-Key") == API_KEY

@app.route("/health", methods=["GET"])
def health():
    if not authorized(request):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"status": "ok"})

@app.route("/reset", methods=["POST"])
def reset():
    if not authorized(request):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"status": "reset_complete"})

@app.route("/start", methods=["POST"])
def start():
    if not authorized(request):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"status": "ready"})

@app.route("/tick", methods=["POST"])
def tick():
    if not authorized(request):
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    action = decide_action(data)
    return jsonify(action)


@app.route("/end", methods=["POST"])
def end():
    if not authorized(request):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"status": "done"})



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

