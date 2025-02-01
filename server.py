"""
TCP File Transfer Server

This module implements a TCP server that handles file transfer requests from clients.
It includes error simulation and retransmission mechanisms for educational purposes.
"""

import socket
import json
import os
import logging
import random
import time  # Add this import
from utils import (
    fragment_file, create_segment_packet, MAX_RETRIES,
    inject_error, calculate_checksum
)

# Configure logging to show informational messages
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileServer:
    """
    A TCP server that handles file transfer requests with error simulation.
    
    The server implements:
    - File fragmentation and transmission
    - Error simulation for testing reliability
    - Checksum verification
    - Retransmission of corrupted segments
    """
    
    def __init__(self, host='0.0.0.0', port=12345):
        """
        Initialize the server with network settings.
        
        Args:
            host (str): IP address to bind to (0.0.0.0 means all available interfaces)
            port (int): Port number to listen on
        """
        self.host = host
        self.port = port
        self.error_probability = 0.8  # Probability of simulating transmission errors
        # Create TCP socket with address reuse
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(60)  # 60 second timeout for client connections
        self.socket.setblocking(False)  # Make socket non-blocking

    def start(self):
        """
        Start the server and enter the main connection acceptance loop.
        Handles incoming client connections and processes their requests.
        """
        self.socket.bind((self.host, self.port))
        self.socket.listen(1)  # Queue up to 1 connection request
        logger.info(f"Server listening on {self.host}:{self.port}")

        while True:
            try:
                try:
                    client_socket, client_address = self.socket.accept()
                except BlockingIOError:
                    time.sleep(0.1)  # Sleep briefly to prevent CPU hogging
                    continue
                except socket.error as e:
                    if e.errno == socket.errno.EAGAIN or e.errno == socket.errno.EWOULDBLOCK:
                        time.sleep(0.1)
                        continue
                    else:
                        raise

                if client_socket:
                    client_socket.setblocking(True)  # Make client socket blocking
                    logger.info(f"Connection from {client_address}")
                    try:
                        self.handle_client(client_socket, client_address)
                    except Exception as e:
                        logger.error(f"Error handling client: {e}")
                    finally:
                        client_socket.close()

            except KeyboardInterrupt:
                logger.info("\nReceived keyboard interrupt, shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                continue

    def send_packet(self, client_socket, packet):
        """
        Send a packet to the client with proper framing.
        
        Args:
            client_socket (socket): Client's socket connection
            packet (dict): Data packet to send
            
        Returns:
            bool: True if sent successfully, False otherwise
            
        Note: Uses length-prefixed framing to ensure complete packet transmission
        """
        try:
            # Convert packet to JSON and encode
            packet_json = json.dumps(packet)
            packet_data = packet_json.encode()
            
            # Send 4-byte length prefix
            length = len(packet_data)
            client_socket.send(length.to_bytes(4, byteorder='big'))
            
            # Send actual packet data
            client_socket.send(packet_data)
            return True
        except Exception as e:
            logger.error(f"Error sending packet: {e}")
            return False

    def handle_client(self, client_socket, client_address):
        """
        Handle a client's file transfer request.
        
        Args:
            client_socket (socket): Connected client socket
            client_address (tuple): Client's address information
            
        Process:
        1. Receive filename request
        2. Read and fragment file
        3. Send each segment with error simulation
        4. Handle retransmission requests
        """
        logger.info(f"Client connected from {client_address}")
        
        # Set operation timeout
        client_socket.settimeout(30)
        
        try:
            # Get requested filename
            filename = client_socket.recv(1024).decode().strip()
            if not filename:
                logger.error("Empty filename received")
                return
                
            logger.info(f"Requested file: {filename}")
            
            # Try to open and read the file
            try:
                with open(filename, 'rb') as f:
                    file_data = f.read()
            except FileNotFoundError:
                self.send_packet(client_socket, {"error": "File not found"})
                return
            except Exception as e:
                self.send_packet(client_socket, {"error": str(e)})
                return

            # Verify minimum file size requirement
            if len(file_data) < 2000:
                self.send_packet(client_socket, {
                    "status": "error",
                    "message": "File is too small (must be > 2000 bytes)"
                })
                return

            # Split file into segments for transmission
            segments = fragment_file(file_data)
            num_segments = len(segments)
            logger.info(f"File split into {num_segments} segments")

            try:
                # Inform client about number of segments
                if not self.send_packet(client_socket, {"segment_count": num_segments}):
                    return
                
                # Wait for client to acknowledge
                ack = client_socket.recv(1024)
                if ack != b"OK":
                    logger.error(f"Did not receive OK from client, got: {ack}")
                    return

                # Transmit each segment
                for seq_num in range(num_segments):
                    segment = segments[seq_num]
                    
                    # Simulate transmission errors if probability threshold met
                    error_simulated = False
                    if random.random() < self.error_probability:
                        logger.warning(f"Simulating error for segment {seq_num}")
                        segment = inject_error(segment, 1.0)
                        error_simulated = True
                    
                    # Prepare and send packet
                    packet = {
                        'seq_num': seq_num,
                        'data': list(segment),
                        'checksum': calculate_checksum(segment),
                        'error_simulated': error_simulated
                    }
                    
                    if not self.send_packet(client_socket, packet):
                        logger.error(f"Failed to send segment {seq_num}")
                        return
                    
                    # Handle acknowledgment/negative acknowledgment
                    try:
                        ack = client_socket.recv(1024).decode()
                        if ack.startswith('NAK'):
                            logger.warning(f"Received NAK for segment {seq_num}")
                            # Resend original uncorrupted segment
                            original_packet = {
                                'seq_num': seq_num,
                                'data': list(segments[seq_num]),
                                'checksum': calculate_checksum(segments[seq_num]),
                                'error_simulated': False
                            }
                            if not self.send_packet(client_socket, original_packet):
                                logger.error(f"Failed to resend segment {seq_num}")
                                return
                            
                            # Verify retransmission was accepted
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