# Import necessary modules.
# Flask: the web framework.
# render_template: sends HTML files.
# jsonify: converts Python dictionaries to JSON responses.
# os: reads environment variables.
# datetime: provides current UTC time.
from flask import Flask, render_template, jsonify
import os, datetime

# Create the Flask application instance.
app = Flask(__name__)

# Read the APP_NODE environment variable; default to 'developer'.
# This separates configuration from code (12‑factor app principle).
APP_NODE = os.environ.get("APP_NODE", "developer")

# Home page route.
# The 'node' value is passed into the HTML template and replaced by Jinja2.
@app.route("/")
def home():
    return render_template("index.html", node=APP_NODE)

# Health check endpoint – used by orchestrators (Docker HEALTHCHECK, Kubernetes probes).
@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",                   # Simple status string.
        "node": APP_NODE,                      # Identifies the responding instance.
        "time": datetime.datetime.utcnow().isoformat() + "Z"  # UTC timestamp.
    })

# Only start the development server when the script is run directly.
# host='0.0.0.0' makes Flask listen on all network interfaces inside the container.
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)