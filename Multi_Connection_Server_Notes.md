# Python Multi-Connection Server Explained

> A step-by-step guide to sockets, `selectors`, buffers, and concurrency.

## 1. The operating system is involved

Your Python program does not directly control the network cable.

There are several layers:

1. Your Python code
2. Python’s socket object
3. Operating system
4. Network card, Wi-Fi, or loopback network
5. Another computer or process

When Python creates a socket, Python asks the operating system:

> “Please create a network communication endpoint for me.”

The operating system creates the real networking object and gives Python a reference to it. On Unix-like systems, this reference is commonly called a file descriptor. On Windows, it is usually called a socket handle.

Python wraps that operating-system object in a Python socket object.

So this:

```python
listening_socket = socket.socket(...)
```

creates:

The **Python socket object** communicates with the **OS-level socket**.

The Python object is how your code talks to the OS-level socket.

## 2. Creating the listening socket

This part creates the server’s first socket:

```python
listening_socket = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM,
)
```

There are two important arguments.

### `socket.AF_INET`

This says:

> “Use IPv4 addresses.”

An IPv4 address looks like:

```text
127.0.0.1
192.168.1.20
```

IPv6 would use `socket.AF_INET6`.

### `socket.SOCK_STREAM`

This says:

> “Use a stream-oriented connection.”

That means TCP.

TCP gives you:

- A connection between two endpoints
- Reliable delivery
- Bytes delivered in order
- Automatic retransmission when appropriate
- A continuous stream of bytes

TCP does not give you individual messages. It only knows about bytes.

If a client sends:

```text
Hello
World
```

TCP might deliver it to the server as:

```text
HelloWorld
```

or:

```text
Hel
loWorld
```

or:

```text
Hello
World
```

Your application must decide where one message ends and another begins.

## 3. Giving the socket an address

```python
listening_socket.bind(("127.0.0.1", 65432))
```

This gives the socket an address.

The address has two parts:

| Address part | Example | Analogy |
| --- | --- | --- |
| IP address | `127.0.0.1` | The building’s street address |
| Port | `65432` | A particular door in that building |

You can think of them like this:

- IP address: the building’s street address
- Port: a particular door in that building

127.0.0.1 means:

> “This computer itself.”

It is also called the loopback address. A client connecting to it must be running on the same computer as the server.

A real server might bind to another local IP address so other computers can connect.

## 4. Telling the OS to listen

```python
listening_socket.listen()
```

This tells the operating system:

> “Start accepting incoming TCP connection requests for this address and port.”

The operating system now watches port 65432.

When a client tries to connect, the operating system handles the initial TCP connection process. This includes the TCP handshake.

There is a queue inside the operating system for connections that are waiting for the Python program to accept them.

At this point, the server has one special socket:

```text
listening_socket
```

This socket is like the server’s front door.

It is used to accept visitors. It is not normally used to exchange application data with clients.

## 5. Why make the socket non-blocking?

```python
listening_socket.setblocking(False)
```

Normally, a socket can be blocking.

A blocking operation means:

> “Wait here until this operation finishes.”

For example, a blocking `accept()` might wait until a client connects:

A blocking `accept()` waits until a client connects before the program continues.
That is dangerous in a multi-connection server if the server waits on one socket while other clients need attention.

A non-blocking socket says:

> “Do not make the whole program wait here. Return control to the program if the operation is not ready.”

But non-blocking sockets create a new question:

> “How do we know when a socket is ready?”

That is what the selector solves.

## 6. The selector is the server’s watchman

```python
selector = selectors.DefaultSelector()
```

A selector is like a watchman watching many doors.

You register sockets with it:

```python
selector.register(
    listening_socket,
    selectors.EVENT_READ,
    data=None,
)
```

This says:

> “Watch this socket. Tell me when it is ready to be read.”

For the listening socket, “ready to be read” means:

> “There is a new client waiting to be accepted.”

The selector uses the operating system’s readiness facilities underneath. Depending on the operating system, this may involve mechanisms such as select, poll, epoll, or kqueue.

You do not normally call those mechanisms directly. Python’s `selectors` module gives you one common interface.

## 7. The event loop

The heart of the server is:

```python
while True:
    ready_events = selector.select(timeout=None)

    for key, event_mask in ready_events:
        if key.data is None:
            accept_connection(key.fileobj)
        else:
            service_connection(key, event_mask)
```

This is an event loop.

It repeatedly asks:

> “Which sockets need attention right now?”

### What does `select()` do?

```python
ready_events = selector.select(timeout=None)
```

This line does block, but in a useful way.

It does not wait for one particular client. It waits for any registered socket to become ready.

If nothing is happening, the operating system can let the process sleep:

When no socket is ready, the Python process sleeps efficiently. The operating system wakes it when something happens.
If three sockets become ready, `select()` might return three events.

Each event contains:

```text
key
event_mask
```

The key identifies the socket and its associated information.

The event_mask says what the socket is ready to do.

## 8. What is a key?

The selector returns a `SelectorKey` object.

It contains information such as:

- `key.fileobj`
- `key.data`

### `key.fileobj`

This is the actual socket object:

```python
connection = key.fileobj
```

### `key.data`

This is extra information that you attached when registering the socket.

For the listening socket, we registered:

```python
data=None
```

For a client socket, we register a data object:

```python
selector.register(
    connection,
    events,
    data=client_data,
)
```

That gives us a simple way to tell the sockets apart:

```python
if key.data is None:
    # This is the listening socket.
else:
    # This is a connected client socket.
```

None is being used as a special marker.

## 9. A client connects

When a client connects, the selector reports that the listening socket is ready.

The event loop calls:

```python
accept_connection(key.fileobj)
```

Inside that function:

```python
connection, address = listening_socket.accept()
```

This does two things:

- Removes one waiting connection from the operating system’s connection queue.
- Creates a new connected socket for that client.

Now the server has:

```text
listening_socket
connection_for_client_1
```

If another client connects:

```text
listening_socket
connection_for_client_1
connection_for_client_2
```

The listening socket stays open. It continues accepting new clients.

The new connection socket is different from the listening socket. It is the socket used to communicate with this particular client.

## 10. The client socket has an address

The `accept()` call returns:

```text
connection, address
```

For example:

```text
connection = a socket object
address = ("127.0.0.1", 61354)
```

The client’s port might be 61354.

The server is listening on port 65432, but the client uses a temporary port.

A TCP connection can be identified by four values:

| Endpoint | IP address | Port |
| --- | --- | --- |
| Server | `127.0.0.1` | `65432` |
| Client | `127.0.0.1` | `61354` |

Another client can connect to the same server port using a different client port. That is how the operating system knows the connections are different.

## 11. Making the client socket non-blocking

```python
connection.setblocking(False)
```

The new client socket must also be non-blocking.

The listening socket is non-blocking, but that setting does not automatically mean every accepted socket behaves the way you want. The code explicitly configures the connected socket too.

The goal is:

One slow or broken client must not freeze communication with all the other clients.

## 12. Creating per-client data

```python
client_data = types.SimpleNamespace(
    address=address,
    input_buffer=b"",
    output_buffer=b"",
)
```

`SimpleNamespace` is a small object that lets you store attributes.

It is roughly like a tiny custom record:

```python
client_data.address
client_data.input_buffer
client_data.output_buffer
```

Each client gets a separate object.

For example:

| Client | Separate state object |
| --- | --- |
| Client 1 | `client_data_1` |
| Client 2 | `client_data_2` |
| Client 3 | `client_data_3` |

Each object stores state for only one client.

### `address`

This remembers where the client is located.

### `input_buffer`

This is space for bytes being received.

In this simple example from the tutorial, `input_buffer` is created but not really used. A more complete server would use it to save incoming bytes until a complete application message has arrived.

### `output_buffer`

This stores bytes waiting to be sent to the client.

If the server receives:

```python
b"Hello"
```

it adds those bytes to the client’s output buffer.

## 13. Registering the connected socket

```python
events = selectors.EVENT_READ | selectors.EVENT_WRITE
selector.register(
    connection,
    events,
    data=client_data,
)
```

The server asks the selector to watch this client socket for two types of events:

- `EVENT_READ`: data can be read
- `EVENT_WRITE`: data can be written

The `|` operator is bitwise OR. Here it combines two flags into one event mask.

You can think of it as checking two boxes:

- Watch for reading: **yes**
- Watch for writing: **yes**

Now the selector is watching:

- the listening socket
- client 1's socket
- client 2's socket
- client 3's socket
- ...

## 14. The selector reports a client is readable

Suppose client 1 sends:

```text
Hello
```

The operating system receives those bytes and places them in its receive buffer for client 1’s socket.

The selector notices that data is available and returns an event.

The event loop sees that:

```python
key.data is not None
```

So it calls:

```python
service_connection(key, event_mask)
```

Inside that function:

```python
connection = key.fileobj
client_data = key.data
```

Now the function has:

- The socket for this particular client
- The state object for this particular client
- The event flags describing what is ready

## 15. Reading the bytes

The server checks:

```python
if event_mask & selectors.EVENT_READ:
```

The `&` operator checks whether the read flag is present in the mask.

Then it reads:

```python
received = connection.recv(1024)
```

This means:

> “Copy up to 1,024 bytes from the operating system’s receive buffer into Python.”

The result is a Python bytes object:

```python
received == b"Hello"
```

The path is approximately:

1. Bytes arrive from the network.
2. The server’s operating system stores them in its TCP receive buffer.

3. `recv()` copies bytes into a Python `bytes` object.

## 16. Adding data to the output buffer

This server is an echo server, so it sends received data back to the same client:

```python
client_data.output_buffer += received
```

Now:

```python
client_data.output_buffer == b"Hello"
```

The server does not necessarily send the bytes immediately. It saves them first.

Why?

Because sending may be partial. The operating system might accept only some of the bytes right now.

The output buffer is like a basket of mail waiting to be delivered.

## 17. The socket becomes writable

Most healthy TCP sockets are usually writable, but “writable” means:

> “The operating system currently has room to accept some outgoing bytes.”

The event loop eventually receives a write-ready event.

It checks:

```python
if event_mask & selectors.EVENT_WRITE:
```

Then:

```python
if client_data.output_buffer:
```

This second check is important. The socket may be writable even when there is nothing to send.

The server calls:

```python
sent_count = connection.send(
    client_data.output_buffer
)
```

Suppose `send()` sends all five bytes:

```python
sent_count == 5
```

The bytes move approximately like this:

1. Bytes wait in Python’s `output_buffer`.
2. `send()` passes bytes to the server operating system’s TCP send buffer.
3. TCP transfers them over the network.
4. The client operating system stores them in its receive buffer.
5. The client application reads them with `recv()`.

## 18. Why does the server slice the buffer?

The server removes the bytes that were successfully sent:

```python
client_data.output_buffer = (
    client_data.output_buffer[sent_count:]
)
```

If the buffer contained:

```python
b"Hello"
```

and `send()` sent two bytes, then:

```python
sent_count == 2
output_buffer == b"llo"
```

The unsent bytes remain for the next write-ready event.

This is called handling a partial send.

The important rule is:

> **Important:** Never assume that one call to `send()` sends everything.

## 19. What does an empty result from `recv()` mean?

This part is very important:

```python
if received:
    client_data.output_buffer += received
else:
    selector.unregister(connection)
    connection.close()
```

If `recv()` returns non-empty bytes, data arrived.

If `recv()` returns:

```python
b""
```

that means the client closed its side of the connection normally.

It does not mean:

> “No data is available right now.”

Because the socket was reported as readable, an empty result means:

> “The other side reached the end of the stream.”

The server then:

- Removes the socket from the selector.
- Closes the socket.
- Stops tracking that client.

If the server forgot to unregister the socket, the selector could keep reporting it even though the server no longer wants to use it.

## 20. How multiple clients are handled

Imagine three clients:

- Client 1 sends "A"
- Client 2 sends "B"
- Client 3 sends nothing

The server does not do this:

- Wait for client 1 to finish.
- Then handle client 2.
- Then handle client 3.

Instead, it does this:

- Ask the operating system which sockets are ready.
- Handle client 1 briefly.
- Handle client 2 briefly.
- Ignore client 3 for now.
- Ask again.

The event loop might behave like this:

| Event reported by `select()` | Server action |
| --- | --- |
| Client 1 is readable | Service client 1 |
| Client 2 is readable | Service client 2 |
| Listening socket is readable | Accept client 4 |
| Client 1 is writable | Send client 1’s response |
| Client 2 is writable | Send client 2’s response |

This is called I/O multiplexing.

I/O means input and output.
Multiplexing means handling many things through one control mechanism.

## 21. Is this parallelism?

Usually, this example uses one Python thread and one event loop.

The server is not literally executing several client operations at the exact same instant.

Instead, it works on each ready socket for a short time:

1. Handle client 1 briefly.
2. Handle client 2 briefly.
3. Handle client 3 briefly.
4. Return to client 1 when it is ready again.

This is a form of concurrency.

**Concurrency** means managing multiple tasks during the same period.

**Parallelism** means actually executing tasks at the same time, usually with multiple CPU cores or threads/processes.

The multi-connection server is concurrent, even if it is not doing all client work in parallel.

## 22. What happens when the program stops?

The loop normally runs forever:

```python
while True:
```

If you press Ctrl+C, Python raises `KeyboardInterrupt`.

The code catches it:

```python
except KeyboardInterrupt:
    print("Server stopping")
```

Then the finally block runs:

```python
finally:
    selector.close()
```

A production server would also carefully close all remaining client sockets and handle errors such as:

- A client disappearing unexpectedly
- A network timeout
- A failed `send()`
- A failed `recv()`
- A connection reset
- A client that connects but never sends anything

The tutorial example keeps error handling small so the main idea is easier to see.

## 23. The most important abstract idea

The server is a state machine.

For each socket, the server keeps track of a state such as:

- listening for a new connection
- connected and waiting for data
- received data and waiting to send it
- client disconnected

The selector tells the program when a state transition might be possible:

- new connection available
- data available
- space available for writing
- connection closed

The event loop performs a small piece of work and then returns to watching all sockets.

That is the central pattern:

- watch many sockets
- find the ones ready
- do a small amount of work
- save unfinished work in buffers
- watch again

## 24. One final picture

| Server component | Associated state |
| --- | --- |
| `listening_socket` | Accepts new clients |
| Selector / event loop | Watches and services registered sockets |
| Client socket 1 | `client_data_1` and its `output_buffer` |
| Client socket 2 | `client_data_2` and its `output_buffer` |
| Client socket 3 | `client_data_3` and its `output_buffer` |

The listening socket is the front door.

Each accepted socket is a separate conversation line.

The selector is the watchman.

The event loop is the worker.

The per-client data object is the worker’s notebook.

The buffers are temporary baskets of bytes.

The operating system is the layer that manages the actual network connections, queues, and communication with the network hardware.

And TCP is the reliable but message-unaware stream of bytes underneath everything.
