import socket
import json
import sys
from utils import verify_checksum

class FileClient:
    def __init__(self, host='localhost', port=12345):
        self.host = host
        self.port = port
        self.socket = None

    def connect(self):
        """Connect to the server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"Connected to server at {self.host}:{self.port}")
            print(f"Local endpoint: {self.socket.getsockname()}")
            return True
        except ConnectionRefusedError:
            print("Server is down, please try again later.")
            return False
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def request_file(self, filename):
        """Request a file from the server."""
        if not filename:
            print("Error: Filename cannot be empty")
            return

        try:
            # Send file request
            self.socket.send(filename.encode())

            # Receive initial response
            response = self.socket.recv(1024)
            try:
                # Check if it's an error message
                error_response = json.loads(response.decode())
                if error_response.get('status') == 'error':
                    print(error_response['message'])
                    return
            except json.JSONDecodeError:
                # Not an error message, continue with file reception
                pass

            # Get number of segments
            num_segments = int(response.decode())
            self.socket.send(b"OK")  # Acknowledge receipt of segment count

            # Prepare to receive segments
            received_segments = {}
            
            # Receive all segments
            for _ in range(num_segments):
                packet_data = self.socket.recv(1024)
                packet = json.loads(packet_data.decode())
                
                seq_num = packet['seq_num']
                data = bytes(packet['data'])
                received_checksum = packet['checksum']

                # Verify checksum
                if verify_checksum(data, received_checksum):
                    received_segments[seq_num] = data
                    self.socket.send(f"ACK_{seq_num}".encode())
                    print(f"Received segment {seq_num + 1}/{num_segments}")
                else:
                    print(f"Checksum verification failed for segment {seq_num}")
                    self.socket.send(f"NAK_{seq_num}".encode())
                    return

            # Check if we received all segments
            if len(received_segments) == num_segments:
                # Reconstruct file
                reconstructed_data = b''.join(
                    received_segments[i] for i in range(num_segments)
                )
                
                # Save the file with a 'received_' prefix
                output_filename = f"received_{filename}"
                with open(output_filename, 'wb') as f:
                    f.write(reconstructed_data)
                print(f"\nFile saved as {output_filename}")
            else:
                print("Error: Some segments are missing")

        except Exception as e:
            print(f"Error during file transfer: {e}")

    def close(self):
        """Close the connection."""
        if self.socket:
            self.socket.close()

def main():
    if len(sys.argv) != 3:
        print("Usage: python client.py <server_ip> <server_port>")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    
    client = FileClient(host, port)
    
    if not client.connect():
        sys.exit(1)

    try:
        while True:
            filename = input("\nEnter filename to request (or 'quit' to exit): ")
            if filename.lower() == 'quit':
                client.socket.send(b'quit')
                break
            client.request_file(filename)
    except KeyboardInterrupt:
        print("\nClient shutting down...")
    finally:
        client.close()

if __name__ == "__main__":
    main() 