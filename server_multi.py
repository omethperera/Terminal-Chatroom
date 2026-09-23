import selectors
import socket
import types

selector = selectors.DefaultSelector()
has_clients = False  # Track if any client has ever connected
connected_clients = {} # Global dictionary to track all active clients: { socket_object: data_namespace }

# Define the possible states for readability
class ClientState:
    IDLE = "Idle"
    READY_TO_RCV = "Ready to receive message"
    RCVD_MSG = "Received message"
    READY_TO_SND = "Ready to send message"
    SENT_MSG = "Sent message"

print("[SERVER] Started. No clients are currently connected.")
# function to listen to listening socket and acept new connections
def accept_connection(listening_socket):
    global has_clients
    connection, address = listening_socket.accept()
    print(f"Accepted connection from {address}")
    has_clients = True

    connection.setblocking(False)

    client_data = types.SimpleNamespace(
        address=address,
        input_buffer=b"",
        state=ClientState.IDLE,
        output_buffer=b"",
    )

    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    selector.register(connection, events, data=client_data) # registers the client 
    connected_clients[connection] = client_data # Add this new client to our global dictionary
    print(f"[CLIENT STATE] {address} connected. Current state: {client_data.state}")

def broadcast_message(sender_socket,message_bytes):
    """Loops through all clients and queues the message for everyone EXCEPT the sender."""
    sender_addr = connected_clients[sender_socket].address
    formatted_msg = f"client {sender_addr}: ".encode()+message_bytes+b"\n> "
    print(formatted_msg)

    for client_sock, client_data in connected_clients.items():
        if client_sock != sender_socket:
            client_data.output_buffer += formatted_msg

# function to check if client_socket is ready to send data or recieve.
def service_connection(key, event_mask):
    connection = key.fileobj
    client_data = key.data

    if event_mask & selectors.EVENT_READ:
        client_data.state = ClientState.READY_TO_RCV
        print(f"[CLIENT STATE] {client_data.address}: {client_data.state}")
        received = connection.recv(1024)

        if received:
            client_data.input_buffer += received  # Add incoming chunks to the input buffer
            print(f"[RECEIVED] From {client_data.address}: {received.decode().strip()}")

            if b"\n" in client_data.input_buffer:
                lines = client_data.input_buffer.split(b"\n") # Split lines by newline
                client_data.input_buffer = lines.pop() # The last element is whatever incomplete text comes after the last '\n'
                    
                for line in lines:
                    clean_line = line.strip()
                    if clean_line:
                        print(f"[CHAT] {client_data.address} typed a message.")
                        broadcast_message(connection, clean_line)
        else:
            print(f"Closing connection to {client_data.address}")
            selector.unregister(connection)
            connection.close()
            return

    if event_mask & selectors.EVENT_WRITE:

        if client_data.output_buffer:
            client_data.state = ClientState.READY_TO_SND
            print(f"[CLIENT STATE] {client_data.address}: {client_data.state}")

            sent_count = connection.send(
                client_data.output_buffer
            )

            client_data.output_buffer = (
                client_data.output_buffer[sent_count:]
            )


# initialize listening socket
listening_socket = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM,
)

listening_socket.bind(("127.0.0.1", 65432))
listening_socket.listen()
listening_socket.setblocking(False)

# registers the listening socket
selector.register(
    listening_socket,
    selectors.EVENT_READ, #
    data=None, # An optional parameter where you can attach custom data (like a callback function or a session ID)
)

try:
    while True:
        ready_events = selector.select(timeout=None)

        for key, event_mask in ready_events:
            if key.data is None:
                accept_connection(key.fileobj)
            else:
                service_connection(key, event_mask)

except KeyboardInterrupt:
    print("Server stopping")

finally:
    selector.close()