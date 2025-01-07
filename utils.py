import struct
import random

# Constants for the TCP implementation
SEGMENT_SIZE = 512  # Fixed size for each data segment in bytes (0.5KB)
MAX_RETRIES = 5    # Maximum number of times the server will attempt to retransmit a failed segment

def calculate_checksum(data):
    """
    Calculate a 16-bit one's complement checksum for error detection.
    
    Args:
        data (bytes): The data to calculate checksum for
    
    Returns:
        int: 16-bit checksum value
    
    Process:
    1. Pad data with zero byte if length is odd
    2. Split data into 16-bit words
    3. Sum all words
    4. Add any carry bits back to sum
    5. Take one's complement of final sum
    """
    # Add padding byte if data length is odd
    if len(data) % 2 == 1:
        data += b'\0'
    
    # Unpack data into 16-bit words and sum them
    words = struct.unpack('!%dH' % (len(data) // 2), data)
    checksum = sum(words)
    
    # Add any carry bits back to sum
    while checksum >> 16:
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    
    # Return one's complement
    return ~checksum & 0xFFFF

def fragment_file(file_data):
    """
    Split a file into fixed-size segments for transmission.
    
    Args:
        file_data (bytes): Complete file data to be split
    
    Returns:
        list: List of byte segments of size SEGMENT_SIZE
        
    Note: The last segment may be smaller than SEGMENT_SIZE
    """
    segments = []
    total_segments = (len(file_data) + SEGMENT_SIZE - 1) // SEGMENT_SIZE
    
    for i in range(total_segments):
        start = i * SEGMENT_SIZE
        end = start + SEGMENT_SIZE
        segment = file_data[start:end]
        segments.append(segment)
    
    return segments

def inject_error(data, error_probability):
    """
    Deliberately corrupt data for testing error detection/correction.
    
    Args:
        data (bytes): Original data segment
        error_probability (float): Probability of injecting an error (0.0 to 1.0)
    
    Returns:
        bytes: Either original or corrupted data
        
    Note: When error is injected, a random byte is modified by adding 1
    """
    if random.random() < error_probability:
        # Randomly modify a byte in the data
        pos = random.randint(0, len(data) - 1)
        modified_data = bytearray(data)
        modified_data[pos] = (modified_data[pos] + 1) % 256
        return bytes(modified_data)
    return data

def create_segment_packet(seq_num, data):
    """
    Create a packet containing segment data and metadata.
    
    Args:
        seq_num (int): Sequence number of the segment
        data (bytes): Segment data
    
    Returns:
        dict: Packet containing sequence number, data, and checksum
    """
    checksum = calculate_checksum(data)
    return {
        'seq_num': seq_num,
        'data': data,
        'checksum': checksum
    }

def verify_checksum(data, received_checksum):
    """
    Verify data integrity by comparing checksums.
    
    Args:
        data (bytes): Received data to verify
        received_checksum (int): Checksum received with the data
    
    Returns:
        bool: True if checksums match, False otherwise
    """
    calculated_checksum = calculate_checksum(data)
    return calculated_checksum == received_checksum