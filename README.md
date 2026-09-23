# Terminal Chatroom: A Multi-Client Chat Server in Pure Python

A terminal chat server that lets many clients connect and talk to each other at the same time. It runs on **a single thread**, uses **non-blocking sockets** and multiplexes I/O with Python's built-in `selectors` module.

There are no frameworks, threads, `asyncio` or third-party packages. It uses only `socket`, `selectors` and the event loop they make possible.

```
Terminal 1                                  Terminal 2
──────────                                  ──────────
Hello everyone!                             client ('127.0.0.1', 61354): Hello everyone!
                                            >
client ('127.0.0.1', 61360): Hey there!     Hey there!
>
```

---

## Features

- **Multiple clients at once.** Any number of clients can connect and chat at the same time.
- **Broadcast messaging.** Each message is delivered to every connected client except the sender.
- **Single-threaded concurrency.** One event loop serves every client, and a slow client can't block the others.
- **Line-based message framing.** Incoming bytes are buffered until a full line (`\n`) arrives, so split or merged TCP packets are handled correctly.
- **Partial-send handling.** Unsent bytes stay in a per-client output buffer until the socket is writable again.
- **Client state tracking.** The server logs each client's state (`Idle`, `Ready to receive message`, `Ready to send message` and more).
- **Zero dependencies.** It needs only the Python standard library.

---

## Requirements

- Python 3.8 or newer
- A raw TCP client for connecting, such as **Ncat/Netcat** or **Telnet**

---

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
```

### 2. Start the server

```bash
python server_multi.py
```

```
[SERVER] Started. No clients are currently connected.
```

The server listens on **`127.0.0.1:65432`**, so clients must run on the same machine.

### 3. Connect two or more clients

Open a new terminal for each client:

```bash
# Ncat (bundled with Nmap) or Netcat
ncat 127.0.0.1 65432

# Telnet (on Windows, enable it under "Turn Windows features on or off")
telnet 127.0.0.1 65432
```

### 4. Chat

Type a message and press **Enter**. Every other connected client sees:

```
client ('127.0.0.1', 61354): your message here
>
```

Meanwhile, the server terminal logs the activity:

```
Accepted connection from ('127.0.0.1', 61354)
[CLIENT STATE] ('127.0.0.1', 61354) connected. Current state: Idle
[CLIENT STATE] ('127.0.0.1', 61354): Ready to receive message
[RECEIVED] From ('127.0.0.1', 61354): your message here
[CHAT] ('127.0.0.1', 61354) typed a message.
[CLIENT STATE] ('127.0.0.1', 61360): Ready to send message
```

Press **Ctrl+C** in the server terminal to stop it.

---

## How it works

### Architecture

```
                   ┌──────────────────────────────┐
  new client ───►  │  listening_socket :65432     │ ──► accept() → new client socket
                   └──────────────────────────────┘
                                  │
                       selector.select()   ◄── sleeps until ANY socket is ready
                                  │
           ┌──────────────────────┼──────────────────────┐
           ▼                      ▼                      ▼
     client socket 1        client socket 2        client socket 3
     ├ input_buffer         ├ input_buffer         ├ input_buffer
     ├ output_buffer        ├ output_buffer        ├ output_buffer
     └ state                └ state                └ state
```

### The event loop

```python
while True:
    ready_events = selector.select(timeout=None)

    for key, event_mask in ready_events:
        if key.data is None:
            accept_connection(key.fileobj)        # the listening socket: a new client
        else:
            service_connection(key, event_mask)   # an existing client: read or write
```

`selector.select()` asks the operating system which sockets are ready. Depending on the OS it uses `select`, `poll`, `epoll` or `kqueue`. The loop then does a small piece of work for each ready socket and goes back to waiting.

### Life of a message

1. **Accept.** When the listening socket becomes readable, `accept_connection()` accepts the client, makes its socket non-blocking, attaches a `SimpleNamespace` holding its address, buffers and state, and registers it for `EVENT_READ | EVENT_WRITE`.
2. **Receive.** When a client socket becomes readable, `recv(1024)` reads the new bytes and appends them to that client's `input_buffer`.
3. **Frame.** TCP is a byte stream with no concept of separate messages, so the buffer is split on `\n`. Each complete line is broadcast. Any incomplete trailing text stays in `input_buffer` until the rest of the line arrives.
4. **Broadcast.** `broadcast_message()` formats the line as `client (ip, port): message` and appends it to the `output_buffer` of every client except the sender.
5. **Send.** When a client socket becomes writable and its `output_buffer` isn't empty, `send()` transmits as many bytes as the OS will accept. The sent bytes are sliced off and the rest waits for the next write event.
6. **Disconnect.** If `recv()` returns `b""`, the client has closed the connection. The socket is unregistered from the selector and closed.

### Concurrency without threads

The server never runs two clients' work at the same instant. It moves quickly between whichever sockets are ready. That is **concurrency** (managing many tasks over the same period), not **parallelism** (running tasks at the same time). The same pattern underlies Node.js, nginx and Python's `asyncio`.

For a detailed walkthrough of every line, see [**Multi_Connection_Server_Notes.md**](Multi_Connection_Server_Notes.md).

---

## Project structure

```
.
├── server_multi.py                                   # The multi-client terminal chat server
├── Multi_Connection_Server_Notes.md                  # In-depth explanation of sockets, selectors and buffers
├── IO Multi-threding(Terminal Chatroom Project).pdf  # Project reference material
└── server_single.py                                  # Earlier step: a minimal blocking HTTP server
```

---

## Concepts demonstrated

- TCP sockets: `bind`, `listen`, `accept`, `recv`, `send`
- The listening socket vs. per-client connection sockets
- Blocking vs. non-blocking I/O
- I/O multiplexing with `selectors`
- Event-loop and state-machine server design
- Message framing over a TCP byte stream
- Input and output buffering and partial sends
- Detecting and handling client disconnects

---

## Known limitations and roadmap

This is a learning project and is not meant for production use.

- [ ] Remove disconnected clients from `connected_clients`. At the moment they stay in the dictionary after closing.
- [ ] Handle `ConnectionResetError` and other socket errors so an abrupt disconnect can't crash the server.
- [ ] Register `EVENT_WRITE` only when a client has pending output, to avoid busy-looping.
- [ ] Make the host and port configurable with command-line arguments so clients on other machines can join.
- [ ] Add usernames (`/nick`) and commands such as `/list` and `/quit`.
- [ ] Announce when users join and leave.
- [ ] Build a dedicated Python chat client.

---

## Author

**Ometh Perera**
