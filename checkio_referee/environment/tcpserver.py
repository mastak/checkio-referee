import logging

from tornado import gen
from tornado.escape import json_encode, json_decode
from tornado.iostream import StreamClosedError
from tornado.tcpserver import TCPServer

logger = logging.getLogger(__name__)


class EnvironmentsTCPServer(TCPServer):

    PORT = 8383

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stream_handler = None
        self.connection_message_callback = None

    def handle_stream(self, stream, address):
        self.stream_handler = StreamHandler(stream, address, self)

    def set_connection_message_callback(self, callback):
        self.connection_message_callback = callback


class StreamHandler(object):

    terminator = b'\0'

    def __init__(self, stream, address, server):
        self.stream = stream
        self.address = address
        self.server = server
        self._is_connection_closed = False
        self.stream.set_close_callback(self._on_client_connection_close)
        self._read_connection_message()

    def _data_decode(self, data):
        if self.terminator in data:
            data = data.split(self.terminator)[0]
        return json_decode(data.decode())

    def _data_encode(self, data):
        data = json_encode(data)
        return data.encode('utf-8')

    def _on_client_connection_close(self):
        self._is_connection_closed = True
        logger.debug("[EXECUTOR-SERVER] :: Client at address {} has closed the connection".format(
            self.address
        ))

    @gen.coroutine
    def read_message(self):
        try:
            data = yield self.stream.read_until(self.terminator)
        except StreamClosedError:
            return
        return self._data_decode(data)

    def _read_connection_message(self):
        self.stream.read_until(self.terminator, self._on_connection_message)

    def _on_connection_message(self, data):
        data = self._data_decode(data)
        self.server.connection_message_callback(data, self)

    @gen.coroutine
    def write(self, message):
        if self._is_connection_closed:
            return
        message = self._data_encode(message)
        logger.debug("[EXECUTOR-SERVER] :: Message to executor {}".format(message))
        try:
            yield self.stream.write(message + self.terminator)
        except Exception as e:
            logger.error(e)
