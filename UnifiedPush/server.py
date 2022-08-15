# Copyright © 2022 Mayeul Cantan
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the “Software”), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
#     The above copyright notice and this permission notice shall be included
#     in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from socketserver import ThreadingMixIn
import http.server
import time
import random
import string
import json
import codecs


# TODO:
# * Unregister
# * Garbage collection after a certain time

class PushItem():
    """ Store a message to be pushed to a client device """
    def __init__(self, content: bytes):
        self.created = time.time()
        self.content = content

class ClientRecord():
    """ Store user data and pending messages for that user """
    def __init__(self):
        self.id = "".join(random.choices(string.ascii_uppercase, k=9))
        self.msgList = []
        self.last_listened = None
        self.created = time.time()


class DataBase():
    """ Store all user data and pending messages """
    def __init__(self):
        self.records = {}
    def add_ClientRecord(self, record: ClientRecord):
        self.records |= {record.id: record}
    def del_record(self, key):
        if key in self.records:
            del self.records[key]
    def get_record(self, key):
        return self.records.get(key)


db = DataBase()  # Global database of messages

class PyUPushHTTPHandler(http.server.BaseHTTPRequestHandler):

    # API paths:
    clientPath = "/client/id/"
    clientPathMultiple = "/client/multi_id/"
    registerPath = "/client/register"
    pusherPath = "/push/id/"

    def __init__(self, *args):
        http.server.BaseHTTPRequestHandler.__init__(self, *args)

    def err404(self, message="404 Not Found"):
        self.send_error(404, explain=message)

    def __sendJson(self, payload):
        self.send_response(200)
        self.send_header('Content-type', 'text/json')
        self.end_headers()
        self.wfile.write(payload.encode())

    def __up_discovery(self, path):
        key = path.split(self.pusherPath)[1]
        if db.get_record(key) is None:
            self.err404("sorry, nobody has registered that endpoint")
            return
        self.__sendJson('{"unifiedpush":{"version":1}}')

    def __clientapi_incremental(self, message: PushItem):
        self.wfile.write(message.content)
        self.wfile.write(b'\n\n')  # Seems to allow pushing the message out
    
    def __clientapi_multiple(self, path):
        keys_str = path.split(self.clientPathMultiple)[1]
        keys = keys_str.split("&")
        keyError = []
        clients = []
        for key in keys:
            client = db.get_record(key)
            if client is None:
                keyError.append(key)
            else:
                clients.append(client)
        if len(keyError) > 0:  # Some keys are invalid
            self.errInvalidKeys(keyError)
            return
        # TODO: mutex, timeout, TCP keepalive
        self.send_response(200)
        self.send_header('Content-type', 'text/json')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()
        while True:
            # The idea is to regularly check if there is anything to send.
            # If there is, construct a dictionary that can be json-serialized
            # Format is something similar to:
            # {id1: [message1_base64, msg2_b64,...], id2: [msg1_b64,...]}
            sendList = {}
            for client in clients:
                client.last_listened = time.time()
                if len(client.msgList) > 0:
                    # TODO: support multiple push items for same client
                    sendList[client.id] = []
                    for msg in client.msgList:
                        sendList[client.id].append(
                                codecs.encode(
                                    msg.content, 'base64').decode('ascii'))
                        # JSON encoder needs strings
                    del client.msgList[:]  # TODO: race condition if no mutex
            if len(sendList) > 0:
                js = json.dumps(sendList).encode()
                self.wfile.write(js)
                self.wfile.write(b'\r\n')
            time.sleep(1)  # Use less CPU while waiting for new events

    def __clientapi(self, path):
        key = path.split(self.clientPath)[1]
        client = db.get_record(key)
        if client is None:
            self.err404("sorry, nobody has registered that endpoint")
            return
        # TODO: mutex, timeout, TCP keepalive
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()
        while True:
            if len(client.msgList) > 0:
                self.__clientapi_incremental(client.msgList[0])
                del client.msgList[0]
            else:
                time.sleep(1)
                client.last_listened = time.time()

    def __postserverapi(self, path, data):
        key = path.split(self.pusherPath)[1]
        client_record = db.get_record(key)
        if client_record is None:
            self.err404("No client with that id")
            return
        item = PushItem(data)
        client_record.msgList.append(item)
        self.send_response(204)  # specification says it SHOULD be 201
        self.send_header('Content-Length', 0)
        self.send_header('Connection', 'close')
        self.end_headers()

    def __clientRegister(self):
        while True:
            client = ClientRecord()
            if db.get_record(client.id) is not None:
                continue  # Bad luck, id already exists
            db.add_ClientRecord(client)
            break
        self.__sendJson('{"id":"'+client.id+'"}')


    def do_GET(self):
        if self.path.startswith(self.pusherPath):
            self.__up_discovery(self.path)
        elif self.path.startswith(self.clientPath):
            self.__clientapi(self.path)
        elif self.path.startswith(self.clientPathMultiple):
            self.__clientapi_multiple(self.path)
        elif self.path == self.registerPath:
            self.__clientRegister()
        else:
            self.err404("No such endpoint")

    def do_POST(self):
        if self.path.startswith(self.pusherPath):
            data_length = int(self.headers['Content-Length'])
            if data_length > 4096 or data_length < 1:
                self.send_error(413, 'Payload too large',
                                "According to the UnifiedPush specification, \
                                Payload must be between 1 and 4096 bytes")
                return
            data = self.rfile.read(data_length)
            self.__postserverapi(self.path, data)
        else:
            self.err404("No such endpoint")


class ThreadedHTTPServer(ThreadingMixIn, http.server.HTTPServer):
    """ Make the server multithreaded to handle concurrent connections """


if __name__ == "__main__":
    server_address = ("localhost", 8976)
    print("Server started http://%s:%s" % server_address)

    try:
        server = ThreadedHTTPServer(server_address, PyUPushHTTPHandler)
    except KeyboardInterrupt:
        pass

    server.serve_forever()
    print("Server stopped.")
