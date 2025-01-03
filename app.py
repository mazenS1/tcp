from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from client import FileClient
import os
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
client = None
UPLOAD_FOLDER = 'uploads'
DOWNLOAD_FOLDER = 'downloads'

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

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
        return jsonify({
            'status': 'success', 
            'message': f'Connected to server at {host}:{port}\nLocal endpoint: {client.socket.getsockname()}'
        })
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
        logger.debug(f"Requesting file: {filename}")
        success = client.request_file(filename)
        
        if success:
            filepath = os.path.join('downloads', filename)
            if os.path.exists(filepath):
                logger.debug(f"File downloaded successfully to {filepath}")
                return send_file(
                    filepath,
                    as_attachment=True,
                    download_name=filename
                )
            else:
                return jsonify({'status': 'error', 'message': 'File transfer failed'})
        else:
            return jsonify({'status': 'error', 'message': 'File transfer failed'})
    except Exception as e:
        logger.error(f"Error in request_file: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'})
    
    try:
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        file_size = os.path.getsize(filepath)
        
        if file_size < 2000:
            os.remove(filepath)
            return jsonify({
                'status': 'error', 
                'message': 'File is too small. Must be larger than 2000 bytes.'
            })
            
        return jsonify({
            'status': 'success',
            'message': f'File {file.filename} ({file_size} bytes) uploaded successfully'
        })
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/files')
def list_files():
    files = []
    try:
        for filename in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(filepath):
                size = os.path.getsize(filepath)
                if size >= 2000:
                    files.append({
                        'name': filename,
                        'size': size
                    })
    except Exception as e:
        logger.error(f"Error listing files: {e}")
    return jsonify(files)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
