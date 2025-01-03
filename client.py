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

    def receive_packet(self):
        """Receive a framed packet."""
        try:
            # Receive packet length (4 bytes)
            length_bytes = self.socket.recv(4)
            if not length_bytes:
                logger.error("Connection closed by server while receiving packet length")
                return None
                
            # Convert bytes to integer
            packet_length = int.from_bytes(length_bytes, byteorder='big')
            
            # Receive packet data
            received_data = b''
            remaining = packet_length
            
            while remaining > 0:
                chunk = self.socket.recv(min(remaining, 4096))
                if not chunk:
                    logger.error("Connection closed by server while receiving packet data")
                    return None
                received_data += chunk
                remaining -= len(chunk)
            
            # Parse JSON
            try:
                packet = json.loads(received_data.decode())
                return packet
            except json.JSONDecodeError as e:
                logger.error(f"Invalid packet format: {e}")
                logger.debug(f"Raw packet data: {received_data[:100]}...")
                return None
                
        except socket.timeout:
            logger.error("Timeout while receiving packet")
            return None
        except Exception as e:
            logger.error(f"Error receiving packet: {e}")
            return None

    def request_file(self, filename):
        """Request a file from the server."""
        if not filename:
            logger.error("Error: Filename cannot be empty")
            return False

        try:
            # Send file request
            logger.debug(f"Sending file request for: {filename}")
            self.socket.send(filename.encode())

            # Receive initial response
            response = self.receive_packet()
            if not response:
                logger.error("Failed to receive server response")
                return False

            # Check for error response
            if "error" in response:
                logger.error(f"Server error: {response['error']}")
                return False

            # Get number of segments
            num_segments = response.get("segment_count")
            if num_segments is None:
                logger.error("Failed to get number of segments from server")
                return False

            logger.debug(f"Expected number of segments: {num_segments}")
            self.socket.send(b"OK")  # Acknowledge receipt of segment count

            # Create downloads directory if it doesn't exist
            download_dir = 'downloads'
            os.makedirs(download_dir, exist_ok=True)

            # Prepare to receive segments
            received_segments = {}
            max_retries = 5
            current_retry = 0

            while current_retry < max_retries:
                try:
                    logger.debug(f"Attempt {current_retry + 1} of {max_retries}")
                    
                    for i in range(num_segments):
                        # Receive packet
                        packet = self.receive_packet()
                        if not packet:
                            raise Exception(f"Failed to receive segment {i}")
                        
                        # Extract segment data
                        seq_num = packet['seq_num']
                        segment_data = bytes(packet['data'])
                        received_checksum = packet['checksum']
                        
                        # Verify checksum
                        if verify_checksum(segment_data, received_checksum):
                            received_segments[seq_num] = segment_data
                            self.socket.send(b"ACK")
                        else:
                            logger.warning(f"Checksum verification failed for segment {seq_num}")
                            self.socket.send(b"NAK")
                            # Wait for retransmission
                            packet = self.receive_packet()
                            if not packet:
                                raise Exception(f"Failed to receive retransmitted segment {seq_num}")
                            
                            segment_data = bytes(packet['data'])
                            if verify_checksum(segment_data, packet['checksum']):
                                received_segments[seq_num] = segment_data
                                self.socket.send(b"ACK")
                            else:
                                raise Exception(f"Checksum verification failed for retransmitted segment {seq_num}")
                    
                    # All segments received successfully
                    break
                    
                except (socket.error, Exception) as e:
                    logger.error(f"Socket error during transfer: {e}")
                    current_retry += 1
                    if current_retry < max_retries:
                        logger.warning(f"Transfer failed, retrying... ({current_retry}/{max_retries})")
                        continue
                    else:
                        logger.error("Failed to receive file after maximum retries")
                        return False

            # Combine segments and write to file
            if len(received_segments) == num_segments:
                file_data = b''.join(received_segments[i] for i in range(num_segments))
                output_path = os.path.join(download_dir, os.path.basename(filename))
                with open(output_path, 'wb') as f:
                    f.write(file_data)
                logger.info(f"File saved to {output_path}")
                return True
            else:
                logger.error("Missing segments in received data")
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