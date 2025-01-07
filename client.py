"""
TCP File Transfer Client

This module implements a TCP client that requests and receives files from the server.
It handles error detection and requests retransmission of corrupted segments.
"""

import socket
import json
import sys
import os
import logging
import time
from utils import verify_checksum

# Configure logging to show debug messages
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class FileClient:
    """
    A TCP client that requests and receives files with error detection.
    
    Features:
    - Reliable connection establishment with retry mechanism
    - Packet framing and reassembly
    - Checksum verification
    - Automatic retransmission requests
    """
    
    def __init__(self, host='localhost', port=12345):
        """
        Initialize client with connection settings.
        
        Args:
            host (str): Server hostname or IP address
            port (int): Server port number
        """
        self.host = host
        self.port = port
        self.socket = None
        self.max_retries = 3  # Maximum connection retry attempts
        self.timeout = 30     # Socket timeout in seconds

    def connect(self):
        """
        Establish connection to server with retry mechanism.
        
        Returns:
            bool: True if connection successful, False otherwise
            
        Note: Uses exponential backoff for retries
        """
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
        """
        Receive a framed packet from the server.
        
        Returns:
            dict: Decoded packet data or None if error
            
        Process:
        1. Read 4-byte length prefix
        2. Read exact number of bytes for packet
        3. Decode JSON packet data
        """
        try:
            # Get packet length from prefix
            length_bytes = self.socket.recv(4)
            if not length_bytes:
                logger.error("Connection closed by server while receiving packet length")
                return None
                
            # Convert length bytes to integer
            packet_length = int.from_bytes(length_bytes, byteorder='big')
            
            # Receive complete packet data
            received_data = b''
            remaining = packet_length
            
            while remaining > 0:
                chunk = self.socket.recv(min(remaining, 4096))
                if not chunk:
                    logger.error("Connection closed by server while receiving packet data")
                    return None
                received_data += chunk
                remaining -= len(chunk)
            
            # Parse JSON packet
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

    def request_file(self, filename, callback=None):
        """
        Request and receive a file from the server.
        
        Args:
            filename (str): Name of file to request
            callback (function): Optional callback for progress updates
            
        Returns:
            bool: True if file received successfully, False otherwise
            
        Process:
        1. Send filename request
        2. Receive file segments
        3. Verify each segment's checksum
        4. Request retransmission if needed
        5. Save complete file
        """
        if not filename:
            logger.error("Error: Filename cannot be empty")
            return False

        try:
            # Send initial file request
            logger.debug(f"Sending file request for: {filename}")
            self.socket.send(filename.encode())

            # Get server's initial response
            response = self.receive_packet()
            if not response:
                logger.error("Failed to receive server response")
                return False

            # Check for server errors
            if "error" in response:
                logger.error(f"Server error: {response['error']}")
                return False

            # Get total number of segments
            num_segments = response.get("segment_count")
            if num_segments is None:
                logger.error("Failed to get number of segments from server")
                return False

            logger.debug(f"Expected number of segments: {num_segments}")
            self.socket.send(b"OK")  # Acknowledge segment count

            # Notify callback about transfer start
            if callback:
                callback('transfer_start', 
                        segment_count=num_segments,
                        file_size=num_segments * 512)  # Approximate size

            # Prepare download directory
            download_dir = 'downloads'
            os.makedirs(download_dir, exist_ok=True)

            # Initialize segment storage
            received_segments = {}
            max_retries = 5
            current_retry = 0

            while current_retry < max_retries:
                try:
                    logger.debug(f"Attempt {current_retry + 1} of {max_retries}")
                    
                    # Receive all segments
                    for i in range(num_segments):
                        # Get next packet
                        packet = self.receive_packet()
                        if not packet:
                            if callback:
                                callback('segment_status',
                                       segment_num=i,
                                       status='error',
                                       message='Failed to receive segment',
                                       error_simulated=False)
                            raise Exception(f"Failed to receive segment {i}")
                        
                        # Extract packet data
                        seq_num = packet['seq_num']
                        segment_data = bytes(packet['data'])
                        received_checksum = packet['checksum']
                        error_simulated = packet.get('error_simulated', False)
                        
                        # Verify segment integrity
                        if verify_checksum(segment_data, received_checksum):
                            received_segments[seq_num] = segment_data
                            self.socket.send(b"ACK")
                            if callback:
                                callback('segment_status',
                                       segment_num=seq_num,
                                       status='success',
                                       message='Segment received successfully',
                                       error_simulated=error_simulated)
                        else:
                            logger.warning(f"Checksum verification failed for segment {seq_num}")
                            self.socket.send(b"NAK")
                            if callback:
                                callback('segment_status',
                                       segment_num=seq_num,
                                       status='error',
                                       message='Checksum verification failed',
                                       error_simulated=error_simulated)
                            
                            # Handle retransmission
                            packet = self.receive_packet()
                            if not packet:
                                if callback:
                                    callback('segment_status',
                                           segment_num=seq_num,
                                           status='error',
                                           message='Failed to receive retransmitted segment',
                                           error_simulated=False)
                                raise Exception(f"Failed to receive retransmitted segment {seq_num}")
                            
                            # Verify retransmitted segment
                            segment_data = bytes(packet['data'])
                            if verify_checksum(segment_data, packet['checksum']):
                                received_segments[seq_num] = segment_data
                                self.socket.send(b"ACK")
                                if callback:
                                    callback('segment_status',
                                           segment_num=seq_num,
                                           status='retry',
                                           message='Retransmission successful',
                                           error_simulated=packet.get('error_simulated', False))
                            else:
                                if callback:
                                    callback('segment_status',
                                           segment_num=seq_num,
                                           status='error',
                                           message='Retransmission checksum failed',
                                           error_simulated=packet.get('error_simulated', False))
                                continue

                    # Check if all segments received
                    if len(received_segments) == num_segments:
                        # Reassemble and save file
                        output_path = os.path.join(download_dir, os.path.basename(filename))
                        with open(output_path, 'wb') as f:
                            for i in range(num_segments):
                                f.write(received_segments[i])
                        
                        if callback:
                            callback('transfer_complete',
                                   filename=output_path,
                                   total_segments=num_segments)
                        
                        logger.info(f"File saved successfully: {output_path}")
                        return True
                    
                    current_retry += 1
                    
                except Exception as e:
                    logger.error(f"Error during transfer: {e}")
                    current_retry += 1
                    if current_retry >= max_retries:
                        if callback:
                            callback('transfer_failed',
                                   error=str(e))
                        return False
                    continue

            logger.error("Failed to receive complete file after all retries")
            return False
            
        except Exception as e:
            logger.error(f"Error requesting file: {e}")
            if callback:
                callback('transfer_failed',
                       error=str(e))
            return False

    def close(self):
        """
        Close the connection.
        """
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

    def callback(event, **kwargs):
        if event == 'transfer_start':
            print(f"Transfer started. Expected {kwargs['segment_count']} segments.")
        elif event == 'segment_status':
            print(f"Segment {kwargs['segment_num']}: {kwargs['status']} - {kwargs['message']} (Error simulated: {kwargs.get('error_simulated', False)})")
        elif event == 'transfer_complete':
            print(f"Transfer complete. Saved file: {kwargs['filename']}")
        elif event == 'transfer_failed':
            print(f"Transfer failed: {kwargs['error']}")

    try:
        while True:
            filename = input("\nEnter filename to request (or 'quit' to exit): ")
            if filename.lower() == 'quit':
                client.socket.send(b'quit')
                break
            client.request_file(filename, callback)
    except KeyboardInterrupt:
        logger.info("Client shutting down...")
    finally:
        client.close()

if __name__ == "__main__":
    main()