import socket
import json
import os
import logging
import random
from utils import (
    fragment_file, create_segment_packet, MAX_RETRIES,
    inject_error, calculate_checksum
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileServer:
    def __init__(self, host='0.0.0.0', port=12345):
        self.host = host
        self.port = port
        self.error_probability = 0.8  # Can be changed to 0.5 or 0.8
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(60)  # 60 second timeout for accept()

    def start(self):
        """Start the server and listen for connections."""
        self.socket.bind((self.host, self.port))
        self.socket.listen(1)
        logger.info(f"Server listening on {self.host}:{self.port}")

        while True:
            try:
                client_socket, client_address = self.socket.accept()
            except socket.timeout:
                logger.error("Timeout waiting for connection")
                continue

            logger.info(f"Connection from {client_address}")
            try:
                self.handle_client(client_socket, client_address)
            except Exception as e:
                logger.error(f"Error handling client: {e}")
            finally:
                client_socket.close()

    def send_packet(self, client_socket, packet):
        """Send a packet with proper framing."""
        try:
            # Convert packet to JSON and encode
            packet_json = json.dumps(packet)
            packet_data = packet_json.encode()
            
            # Send packet length first (4 bytes)
            length = len(packet_data)
            client_socket.send(length.to_bytes(4, byteorder='big'))
            
            # Send packet data
            client_socket.send(packet_data)
            return True
        except Exception as e:
            logger.error(f"Error sending packet: {e}")
            return False

    def handle_client(self, client_socket, client_address):
        """Handle client connection."""
        logger.info(f"Client connected from {client_address}")
        
        # Set timeout for operations
        client_socket.settimeout(30)  # 30 second timeout for operations
        
        try:
            # Receive filename
            filename = client_socket.recv(1024).decode().strip()
            if not filename:
                logger.error("Empty filename received")
                return
                
            logger.info(f"Requested file: {filename}")
            
            try:
                with open(filename, 'rb') as f:
                    file_data = f.read()
            except FileNotFoundError:
                self.send_packet(client_socket, {"error": "File not found"})
                return
            except Exception as e:
                self.send_packet(client_socket, {"error": str(e)})
                return

            if len(file_data) < 2000:
                self.send_packet(client_socket, {
                    "status": "error",
                    "message": "File is too small (must be > 2000 bytes)"
                })
                return

            segments = fragment_file(file_data)
            num_segments = len(segments)
            logger.info(f"File split into {num_segments} segments")

            try:
                # Send number of segments
                if not self.send_packet(client_socket, {"segment_count": num_segments}):
                    return
                
                # Wait for client acknowledgment
                ack = client_socket.recv(1024)
                if ack != b"OK":
                    logger.error(f"Did not receive OK from client, got: {ack}")
                    return

                # Send each segment
                for seq_num in range(num_segments):
                    segment = segments[seq_num]
                    
                    # Apply error simulation if needed
                    error_simulated = False
                    if random.random() < self.error_probability:
                        logger.warning(f"Simulating error for segment {seq_num}")
                        segment = inject_error(segment, 1.0)
                        error_simulated = True
                    
                    # Create and send packet
                    packet = {
                        'seq_num': seq_num,
                        'data': list(segment),
                        'checksum': calculate_checksum(segment),
                        'error_simulated': error_simulated
                    }
                    
                    if not self.send_packet(client_socket, packet):
                        logger.error(f"Failed to send segment {seq_num}")
                        return
                    
                    # Wait for acknowledgment
                    try:
                        ack = client_socket.recv(1024).decode()
                        if ack.startswith('NAK'):
                            logger.warning(f"Received NAK for segment {seq_num}")
                            # Resend the original segment
                            original_packet = {
                                'seq_num': seq_num,
                                'data': list(segments[seq_num]),
                                'checksum': calculate_checksum(segments[seq_num]),
                                'error_simulated': False
                            }
                            if not self.send_packet(client_socket, original_packet):
                                logger.error(f"Failed to resend segment {seq_num}")
                                return
                            
                            # Wait for acknowledgment of resent segment
                            ack = client_socket.recv(1024).decode()
                            if not ack.startswith('ACK'):
                                logger.error(f"Failed to get ACK for resent segment {seq_num}")
                                return
                    except socket.timeout:
                        logger.error(f"Timeout waiting for ACK on segment {seq_num}")
                        return

            except socket.timeout as e:
                logger.error(f"Socket timeout during transfer: {e}")
                return
            except socket.error as e:
                logger.error(f"Socket error during transfer: {e}")
                return
            except Exception as e:
                logger.error(f"Error during transfer: {e}")
                return

        except Exception as e:
            logger.error(f"Error handling client: {e}")
        finally:
            client_socket.close()
            logger.info(f"Connection closed with {client_address}")

if __name__ == "__main__":
    server = FileServer()
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("\nServer shutting down...")
    finally:
        server.socket.close()