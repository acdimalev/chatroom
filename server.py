from socket import create_server
from time import sleep

MAX_SOCKETS = 1024
BUFFER_SIZE = 4096

sockets = [(0, None)] * MAX_SOCKETS
buffers = [b''] * MAX_SOCKETS
lines = [[]] * MAX_SOCKETS
messages = [[]] * MAX_SOCKETS

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

def pad(xs, length, value=None):
    return xs + [value] * (length - len(xs))

def parse(line):
    # prefix (optional)
    if b':' == line[:1]:
        (prefix, line) = pad(line.split(b' ', 1), 2, b'')
        prefix = prefix[1:]
    else:
        prefix = None
    # command
    (command, line) = pad(line.split(b' ', 1), 2)
    # params (+trailing)
    if line:
        line = b' ' + line
        (params, line) = pad(line.split(b' :', 1), 2)
        params = params.split(b' ')[1:]
    else:
        params = []
    if line:
        params += [line]
    return (prefix, command, params)

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
        lines[i] = []
        messages[i] = []
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
            # if recvbuf:
            #     print(f"{i} > {recvbuf}")
            buffers[i] += recvbuf
        except EOFError:
            sockets[i][1].close()
            sockets[i] = (sockets[i][0], None)
            connections[n] = None
            print(f"closed connection {i}")

    connections = [x for x in connections if x is not None]


    # split buffers into lines
    # TODO: disconnect connections with full buffers that do not parse into lines

    for i in connections:
        (*lines[i], buffers[i]) = buffers[i].translate(None, delete=b'\r').split(b'\n')
        # for line in lines[i]:
        #     print(f"{i} > {line}")


    # parse lines into messages

    for i in connections:
        messages[i] = [
            parse(line)
            for line in lines[i]
        ]
        for message in messages[i]:
            print(f"{i} > {message}")


    sleep(1/30.0)
