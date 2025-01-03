# TCP File Transfer Application

This is a TCP client-server application that implements reliable file transfer with fragmentation, checksums, and error simulation.

## Features

- TCP-based client-server communication
- File fragmentation and reassembly
- 16-bit one's complement checksum for error detection
- Error simulation with configurable probability
- Automatic retransmission on error detection
- Support for large text files (>2000 bytes)

## Requirements

- Python 3.6 or higher
- No external dependencies required

## Setup

1. Clone or download this repository
2. Ensure Python 3.6+ is installed on both client and server machines

## Usage

### Starting the Server

```bash
python server.py
a``

The server will start listening on all interfaces (0.0.0.0) on port 12345 by default.

### Starting the Client

```bash
python client.py <server_ip> <server_port>
```

Example:

```bash
python client.py 192.168.1.100 12345
```

### Using the Application

1. Start the server on one machine
2. Start the client on another machine, providing the server's IP address and port
3. On the client, enter the name of the file you want to request
4. The file will be transferred with error checking and automatic retransmission
5. Retrieved files will be saved with a 'received\_' prefix
6. Type 'quit' to exit the application

## Error Simulation

The server includes an error simulation feature that randomly introduces errors into the transmitted data. The probability can be adjusted by modifying the `error_probability` variable in the server code (default is 0.3).

## Protocol Details

1. Client connects to server
2. Client sends filename request
3. Server checks file existence and size
4. Server fragments file into segments
5. Each segment is sent with:
   - Sequence number
   - Checksum
   - Data
6. Client verifies each segment and sends acknowledgment
7. On error detection, retransmission is requested
8. After 5 failed attempts, transfer is aborted

## File Requirements

- Files must be larger than 2000 bytes to enable fragmentation
- Currently supports text files
- Files should be placed in the same directory as the server script

## Error Handling

- Server unavailable: "Server is down, please try again later"
- File not found: "The file [filename] you requested does not exist in this folder"
- Checksum mismatch: "The received file [filename] is corrupted"
- Empty filename: "Error: Filename cannot be empty"
