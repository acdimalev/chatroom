from socket import create_server

MAX_SOCKETS = 1024
BUFFER_SIZE = 4096

sockets = [(0, None)] * MAX_SOCKETS
buffers = [b''] * MAX_SOCKETS

connections = []

# invert EOF behavior
def fancyrecv(socket, buffersize):
    if 0 == buffersize:
        return b''
    try:
        buffer = socket.recv(buffersize)
    except BlockingIOError:
        return b''
    if 0 == len(buffer):
        raise EOFError
    else:
        return buffer

server = create_server(("localhost", 6667))
server.setblocking(False)

# FIXME: server should gracefully handle interrupts for termination
while True:

    # handle connections
    # one per iteration

    try:
        (socket, _) = server.accept()
        socket.setblocking(False)
        i = [x[1] for x in sockets].index(None)
        sockets[i] = (1 + sockets[i][0], socket)
        buffers[i] = b''
        connections.append(i)
        print(f"received connection {i}")
    except BlockingIOError:
        pass
    except ValueError:
        socket.close()


    # read from connections

    for (n, i) in enumerate(connections):
        try:
            recvbuf = fancyrecv(sockets[i][1], BUFFER_SIZE - len(buffers[i]))
            if recvbuf:
                print(f"{i} > {recvbuf}")
            buffers[i] += recvbuf
        except EOFError:
            sockets[i][1].close()
            sockets[i] = (sockets[i][0], None)
            connections[n] = None
            print(f"closed connection {i}")

    connections = [x for x in connections if x is not None]
