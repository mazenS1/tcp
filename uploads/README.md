# **TCP File Transfer Application with Web-Based UI**

This is a TCP client-server application that implements reliable file transfer with fragmentation, checksums, and error simulation. It includes a **web-based user interface** for easier interaction with the system.

---

## **Features**

- **Web-based UI** for managing file uploads, downloads, and monitoring transfer progress.
- TCP-based client-server communication.
- File fragmentation and reassembly for large files.
- 16-bit one's complement checksum for error detection.
- Error simulation with configurable probability.
- Automatic retransmission on error detection.
- Support for large text files (>2000 bytes).

---

## **Requirements**

- **Python 3.6 or higher**
- Required Python libraries (install via `requirements.txt`):
  - `flask`
  - `flask-sock`

---

## **Setup**

1. Clone or download this repository:

   ```bash
   git clone <repository_url>
   cd mazens1-tcp
   ```

2. Install the required Python libraries:

   ```bash
   pip install -r requirements.txt
   ```

3. Ensure the directory structure matches the following:
   ```
   mazens1-tcp/
   ├── README.md
   ├── app.py
   ├── client.py
   ├── requirements.txt
   ├── server.py
   ├── utils.py
   ├── downloads/
   │   └── (empty or contains downloaded files)
   ├── templates/
   │   └── index.html
   └── uploads/
       └── (empty or contains uploaded files)
   ```

---

## **Usage**

### **1. Start the Server**

The server handles file requests and sends file fragments to the client.

1. Open a terminal and navigate to the project directory.
2. Run the server:
   ```bash
   python server.py
   ```
3. The server will start listening on all interfaces (`0.0.0.0`) and port `12345` by default.

   **Example Output**:

   ```
   Server listening on 0.0.0.0:12345
   ```

4. Ensure the files you want to transfer are placed in the same directory as `server.py` or the `uploads/` directory.

---

### **2. Start the Web Application**

The web application provides a user-friendly interface for interacting with the server.

1. Open another terminal and navigate to the project directory.
2. Run the web application:
   ```bash
   python app.py
   ```
3. The web application will start on `http://127.0.0.1:5000` by default.

   **Example Output**:

   ```
   Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
   ```

4. Open a web browser and go to `http://127.0.0.1:5000`.

---

### **3. Using the Web Interface**

The web interface provides the following features:

#### **a. Connect to the Server**

- Enter the server's IP address and port (default: `localhost` and `12345`).
- Click **Connect** to establish a connection with the server.

#### **b. Upload Files**

- Use the **Upload File** section to upload files to the server.
- Files must be larger than 2000 bytes to enable fragmentation.

#### **c. View Available Files**

- The **Available Files** section lists all files available on the server.
- Click the **Request** button next to a file to download it.

#### **d. Request Files**

- Use the **Request File** section to manually request a file by entering its name.
- The file will be downloaded to the `downloads/` directory.

#### **e. Monitor Transfer Progress**

- The **Transfer Status** section displays real-time updates on file transfer progress, including:
  - Overall progress.
  - Number of errors detected.
  - Retransmissions.
  - Transfer rate.

#### **f. Adjust Error Simulation**

- Use the **Error Simulation** slider to adjust the probability of simulated transmission errors (default: 30%).

---

## **Error Simulation**

The server includes an error simulation feature that randomly introduces errors into the transmitted data. The probability can be adjusted using the **Error Simulation** slider in the web interface or by modifying the `error_probability` variable in `server.py`.

---

## **Protocol Details**

1. The client connects to the server.
2. The client sends a filename request.
3. The server checks the file's existence and size.
4. The server fragments the file into segments.
5. Each segment is sent with:
   - Sequence number.
   - Checksum.
   - Data.
6. The client verifies each segment and sends an acknowledgment.
7. On error detection, retransmission is requested.
8. After 5 failed attempts, the transfer is aborted.

---

## **File Requirements**

- Files must be larger than 2000 bytes to enable fragmentation.
- Currently supports text files.
- Files should be placed in the `uploads/` directory or the same directory as `server.py`.

---

## **Error Handling**

- **Server unavailable**: "Server is down, please try again later."
- **File not found**: "The file [filename] you requested does not exist in this folder."
- **Checksum mismatch**: "The received file [filename] is corrupted."
- **Empty filename**: "Error: Filename cannot be empty."

---

## **Directory Structure**

```
mazens1-tcp/
├── README.md               # Project documentation
├── app.py                  # Web application
├── client.py               # TCP client
├── server.py               # TCP server
├── utils.py                # Utility functions (checksum, fragmentation, etc.)
├── requirements.txt        # Required Python libraries
├── downloads/              # Directory for downloaded files
├── uploads/                # Directory for uploaded files
└── templates/
    └── index.html          # Web application UI
```

---

## **Future Improvements**

- Add support for binary files (e.g., images, videos).
- Implement file compression before transfer.
- Enhance the web interface with more detailed statistics.

---

Let me know if you need further modifications!
