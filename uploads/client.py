import socket
import json
import sys
import os
import logging
import time
from utils import verify_checksum

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class FileClient:
    def __init__(self, host='localhost', port=12345):
        self.host = host
        self.port = port
        self.socket = None
        self.max_retries = 3
        self.timeout = 30  # 30 second timeout

    def connect(self):
        """Connect to the server with retries."""
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(self.timeout)
                self.socket.connect((self.host, self.port))
                logger.info(f"Connected to server at {self.host}:{self.port}")
                logger.info(f"Local endpoint: {self.socket.getsockname()}")
                return True
            except (ConnectionRefusedError, socket.timeout):
                retry_count += 1
                wait_time = 2 ** retry_count  # Exponential backoff
                logger.warning(f"Connection attempt {retry_count} failed. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            except Exception as e:
                logger.error(f"Connection error: {e}")
                if self.socket:
                    self.socket.close()
                return False
        
        logger.error(f"Failed to connect after {self.max_retries} attempts")
        return False

    def request_file(self, filename):
        """Request a file from the server."""
        if not filename:
            logger.error("Error: Filename cannot be empty")
            return False

        try:
            # Send file request
            logger.debug(f"Sending file request for: {filename}")
            self.socket.send(filename.encode())

            # Receive initial response with timeout
            try:
                response = self.socket.recv(1024)
                if not response:
                    logger.error("Server closed connection")
                    return False
            except socket.timeout:
                logger.error("Timeout waiting for server response")
                return False

            response_str = response.decode()
            logger.debug(f"Received response: {response_str}")

            # Parse the JSON response
            try:
                response_data = json.loads(response_str)
                if 'segment_count' in response_data:
                    num_segments = response_data['segment_count']
                    logger.debug(f"Expected number of segments: {num_segments}")
                else:
                    logger.error(f"Server error: {response_data.get('message', 'Unknown error')}")
                    return False
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON response from server: {response_str}")
                return False

            if num_segments is None:
                logger.error("Failed to get number of segments from server")
                return False

            self.socket.send(b"OK")  # Acknowledge receipt of segment count

            # Create downloads directory if it doesn't exist
            download_dir = 'downloads'
            os.makedirs(download_dir, exist_ok=True)

            # Prepare to receive segments
            received_segments = {}
            max_retries = 5
            current_retry = 0

            while current_retry < max_retries:
                success = True
                logger.debug(f"Attempt {current_retry + 1} of {max_retries}")

                try:
                    for i in range(num_segments):
                        # Receive packet with timeout
                        try:
                            packet_data = self.socket.recv(1024)
                            if not packet_data:
                                raise socket.error("Connection closed by server")
                        except socket.timeout:
                            logger.error(f"Timeout waiting for segment {i+1}")
                            success = False
                            break

                        try:
                            packet = json.loads(packet_data.decode())
                            seq_num = packet['seq_num']
                            data = bytes(packet['data'])
                            received_checksum = packet['checksum']
                            logger.debug(f"Received segment {seq_num + 1}/{num_segments} (size: {len(data)} bytes)")
                        except (json.JSONDecodeError, KeyError, TypeError) as e:
                            logger.error(f"Invalid packet format for segment {i+1}: {e}")
                            logger.debug(f"Raw packet data: {packet_data[:100]}...")  # Show first 100 bytes
                            success = False
                            break

                        # Verify checksum
                        if verify_checksum(data, received_checksum):
                            received_segments[seq_num] = data
                            ack_msg = f"ACK_{seq_num}".encode()
                            self.socket.send(ack_msg)
                            logger.debug(f"Sent acknowledgment: ACK_{seq_num}")
                        else:
                            logger.error(f"Checksum verification failed for segment {seq_num + 1}")
                            nak_msg = f"NAK_{seq_num}".encode()
                            self.socket.send(nak_msg)
                            logger.debug(f"Sent negative acknowledgment: NAK_{seq_num}")
                            success = False
                            break

                except socket.error as e:
                    logger.error(f"Socket error during transfer: {e}")
                    success = False

                if success and len(received_segments) == num_segments:
                    # All segments received successfully
                    logger.info("All segments received successfully")
                    
                    try:
                        # Reconstruct and save the file
                        reconstructed_data = b''.join(
                            received_segments[i] for i in range(num_segments)
                        )
                        
                        filepath = os.path.join(download_dir, filename)
                        with open(filepath, 'wb') as f:
                            f.write(reconstructed_data)
                        
                        logger.info(f"File saved as {filepath}")
                        return True
                    except Exception as e:
                        logger.error(f"Error saving file: {e}")
                        return False
                else:
                    if success:
                        logger.warning(f"Missing segments. Got {len(received_segments)}/{num_segments}")
                    logger.warning(f"Transfer failed, retrying... ({current_retry + 1}/{max_retries})")
                    current_retry += 1
                    received_segments.clear()
                    # Send retry request to server
                    self.socket.send(b"RETRY")

            logger.error(f"Failed to receive file after {max_retries} attempts")
            return False

        except Exception as e:
            logger.error(f"Error requesting file: {e}")
            return False

    def close(self):
        """Close the connection."""
        if self.socket:
            self.socket.close()

def main():
    if len(sys.argv) != 3:
        logger.error("Usage: python client.py <server_ip> <server_port>")
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
        logger.info("Client shutting down...")
    finally:
        client.close()

if __name__ == "__main__":
    main()