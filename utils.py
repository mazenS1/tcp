import struct
import random

SEGMENT_SIZE = 512  # Size of each segment in bytes
MAX_RETRIES = 5    # Maximum number of retransmission attempts

def calculate_checksum(data):
    """Calculate 16-bit one's complement checksum."""
    if len(data) % 2 == 1:
        data += b'\0'
    
    words = struct.unpack('!%dH' % (len(data) // 2), data)
    checksum = sum(words)
    
    while checksum >> 16:
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    
    return ~checksum & 0xFFFF

def fragment_file(file_data):
    """Split file into segments."""
    segments = []
    total_segments = (len(file_data) + SEGMENT_SIZE - 1) // SEGMENT_SIZE
    
    for i in range(total_segments):
        start = i * SEGMENT_SIZE
        end = start + SEGMENT_SIZE
        segment = file_data[start:end]
        segments.append(segment)
    
    return segments

def inject_error(data, error_probability):
    """Randomly inject errors into data based on probability."""
    if random.random() < error_probability:
        # Randomly modify a byte in the data
        pos = random.randint(0, len(data) - 1)
        modified_data = bytearray(data)
        modified_data[pos] = (modified_data[pos] + 1) % 256
        return bytes(modified_data)
    return data

def create_segment_packet(seq_num, data):
    """Create a packet with sequence number and checksum."""
    checksum = calculate_checksum(data)
    return {
        'seq_num': seq_num,
        'data': data,
        'checksum': checksum
    }

def verify_checksum(data, received_checksum):
    """Verify the integrity of received data using checksum."""
    calculated_checksum = calculate_checksum(data)
    return calculated_checksum == received_checksum