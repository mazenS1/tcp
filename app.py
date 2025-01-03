from flask import Flask, render_template, request, jsonify, send_file
from client import FileClient
import os

app = Flask(__name__)
client = None
UPLOAD_FOLDER = 'uploads'

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/connect', methods=['POST'])
def connect():
    global client
    host = request.form.get('host', 'localhost')
    port = int(request.form.get('port', 12345))
    
    client = FileClient(host, port)
    if client.connect():
        return jsonify({'status': 'success', 'message': f'Connected to server at {host}:{port}'})
    return jsonify({'status': 'error', 'message': 'Failed to connect to server'})

@app.route('/request-file', methods=['POST'])
def request_file():
    global client
    if not client:
        return jsonify({'status': 'error', 'message': 'Not connected to server'})
    
    filename = request.form.get('filename')
    if not filename:
        return jsonify({'status': 'error', 'message': 'Filename is required'})
    
    try:
        client.request_file(filename)
        return jsonify({'status': 'success', 'message': f'File {filename} requested successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'})
    
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)
    return jsonify({'status': 'success', 'message': f'File {file.filename} uploaded successfully'})

@app.route('/files')
def list_files():
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(filepath):
            files.append({
                'name': filename,
                'size': os.path.getsize(filepath)
            })
    return jsonify(files)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
