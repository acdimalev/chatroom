from dataclasses import dataclass
from socket import create_server
from time import sleep

CONNECTIONS_MAX = 1024
IN_BUFFER_MAX = 4096
IN_MESSAGE_MAX = 4


@dataclass
class Message:
    prefix: bytes
    command: bytes
    params: list[bytes]


@dataclass
class Connection:
    socket: int
    in_buffer: bytes
    in_messages: list[Message]


class PoolExhaustedException(BaseException):
    pass


class Pool:

    def __init__(self, size):
        self._items = {}
        self._next_reference = 0
        self._size = size

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, reference):
        return self._items[reference]

    def __delitem__(self, reference):
        del self._items[reference]

    def append(self, item):
        if self._size < 1 + len(self._items):
            raise PoolExhaustedException
        reference = self._next_reference
        self._items[reference] = item
        self._next_reference = 1 + reference
        return reference

    def items(self):
        return iter(self._items.items())


connections = Pool(CONNECTIONS_MAX)
drop_connections = []


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
    return Message(prefix, command, params)

server = create_server(("localhost", 6667))
server.setblocking(False)

# FIXME: server should gracefully handle interrupts for termination
while True:

    # handle new connections
    # one per iteration

    try:
        (socket, _) = server.accept()
        socket.setblocking(False)
        connection_reference = connections.append(Connection(
            socket=socket,
            in_buffer=b'',
            in_messages=[],
        ))
        print(f"received connection {connection_reference}")
    except BlockingIOError:
        pass
    except PoolExhaustedException:
        socket.close()


    # process connection input

    for (connection_reference, connection) in connections.items():

        # read from connections
        try:
            connection.in_buffer += fancyrecv(
                connection.socket, IN_BUFFER_MAX - len(connection.in_buffer),
            )
        except EOFError:
            drop_connections.append(connection_reference)

        # strip carriage returns out of the in-buffer
        connection.in_buffer = connection.in_buffer.translate(None, delete=b'\r')

        # split buffers into lines
        (*in_lines, connection.in_buffer) = connection.in_buffer.split(
            b'\n', IN_MESSAGE_MAX - len(connection.in_messages),
        )

        # disconnect connections with full buffers that do not parse into lines
        if (IN_BUFFER_MAX == len(connection.in_buffer) and 0 == len(in_lines)):
            drop_connections.append(connection_reference)

        # parse lines into messages
        connection.in_messages += map(parse, in_lines)


    # pump messages to stdout for development

    for (connection_reference, connection) in connections.items():
        for message in connection.in_messages:
            print(f"{connection_reference} > {message}")

        connection.in_messages = []


    # process dropped connections

    for connection_reference in drop_connections:
        if connection_reference in connections:
            connections[connection_reference].socket.close()
            del connections[connection_reference]
            print(f"closed connection {connection_reference}")

    drop_connections = []


    sleep(1/30.0)
