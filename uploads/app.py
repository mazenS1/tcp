from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_sock import Sock
from client import FileClient
import os
import logging
import json
import threading
from queue import Queue

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
sock = Sock(app)
client = None
UPLOAD_FOLDER = 'uploads'
DOWNLOAD_FOLDER = 'downloads'

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# WebSocket connections
ws_connections = set()

def broadcast_transfer_status(data):
    """Broadcast transfer status to all connected WebSocket clients."""
    message = json.dumps(data)
    dead_connections = set()
    
    for ws in ws_connections:
        try:
            ws.send(message)
        except Exception:
            dead_connections.add(ws)
    
    # Remove dead connections
    ws_connections.difference_update(dead_connections)

@sock.route('/ws')
def handle_websocket(ws):
    """Handle WebSocket connections."""
    ws_connections.add(ws)
    try:
        while True:
            # Keep the connection alive
            message = ws.receive()
            if message is None:
                break
    except Exception:
        pass
    finally:
        ws_connections.remove(ws)

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
    error_rate = float(request.form.get('error_rate', 0.3))
    
    if not filename:
        return jsonify({'status': 'error', 'message': 'Filename is required'})
    
    try:
        logger.debug(f"Requesting file: {filename}")
        
        # Set error simulation rate
        client.error_probability = error_rate
        
        # Create a queue for transfer status updates
        status_queue = Queue()
        
        def transfer_callback(status_type, **kwargs):
            """Callback function for transfer status updates."""
            status_queue.put({
                'type': status_type,
                **kwargs
            })
        
        # Start file transfer in a separate thread
        def transfer_thread():
            success = client.request_file(filename, callback=transfer_callback)
            status_queue.put({'type': 'transfer_complete', 'success': success})
        
        thread = threading.Thread(target=transfer_thread)
        thread.start()
        
        # Process status updates
        while True:
            status = status_queue.get()
            if status['type'] == 'transfer_complete':
                return jsonify({
                    'status': 'success' if status['success'] else 'error',
                    'message': 'File transfer completed successfully' if status['success'] else 'File transfer failed'
                })
            else:
                broadcast_transfer_status(status)
        
    except Exception as e:
        logger.error(f"Error requesting file: {e}")
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
