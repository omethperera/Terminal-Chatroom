# Terminal-Chatroom
A terminal chat server that lets many clients connect and talk to each other at the same time. It runs on **a single thread**, uses **non-blocking sockets** and multiplexes I/O with Python's built-in `selectors` module.
