import socket
import json
import os
from utils import (
    fragment_file, create_segment_packet, MAX_RETRIES,
    inject_error
)

class FileServer:
    def __init__(self, host='0.0.0.0', port=12345):
        self.host = host
        self.port = port
        self.error_probability = 0.3  # Can be changed to 0.5 or 0.8
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def start(self):
        """Start the server and listen for connections."""
        self.socket.bind((self.host, self.port))
        self.socket.listen(1)
        print(f"Server listening on {self.host}:{self.port}")

        while True:
            client_socket, client_address = self.socket.accept()
            print(f"Connection from {client_address}")
            try:
                self.handle_client(client_socket, client_address)
            except Exception as e:
                print(f"Error handling client: {e}")
            finally:
                client_socket.close()

    def handle_client(self, client_socket, client_address):
        """Handle client requests."""
        while True:
            try:
                # Receive filename request
                request = client_socket.recv(1024).decode()
                if not request or request.lower() == 'quit':
                    print(f"Client {client_address} disconnected")
                    break

                print(f"Received request for file: {request}")
                
                # Check if file exists
                if not os.path.exists(request):
                    response = json.dumps({
                        'status': 'error',
                        'message': f"The file {request} you requested does not exist in this folder"
                    })
                    client_socket.send(response.encode())
                    continue

                # Read and fragment file
                with open(request, 'rb') as file:
                    file_data = file.read()

                if len(file_data) < 2000:
                    response = json.dumps({
                        'status': 'error',
                        'message': f"File {request} is too small (must be > 2000 bytes)"
                    })
                    client_socket.send(response.encode())
                    continue

                segments = fragment_file(file_data)
                
                # Send number of segments first
                client_socket.send(str(len(segments)).encode())
                client_socket.recv(1024)  # Wait for acknowledgment

                # Send each segment
                for retry in range(MAX_RETRIES):
                    success = True
                    for seq_num, segment_data in segments:
                        # Inject error based on probability
                        corrupted_data = inject_error(segment_data, self.error_probability)
                        
                        # Create and send packet
                        packet = create_segment_packet(seq_num, corrupted_data)
                        client_socket.send(json.dumps(packet).encode())
                        
                        # Wait for acknowledgment
                        ack = client_socket.recv(1024).decode()
                        if ack != f"ACK_{seq_num}":
                            success = False
                            break
                    
                    if success:
                        print(f"File {request} sent successfully")
                        break
                    elif retry < MAX_RETRIES - 1:
                        print(f"Retrying transmission (attempt {retry + 2})")
                    else:
                        print(f"Failed to send file {request} after {MAX_RETRIES} attempts")
                        response = json.dumps({
                            'status': 'error',
                            'message': f"Failed to send file after {MAX_RETRIES} attempts"
                        })
                        client_socket.send(response.encode())

            except Exception as e:
                print(f"Error: {e}")
                break

if __name__ == "__main__":
    server = FileServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nServer shutting down...")
    finally:
        server.socket.close() 