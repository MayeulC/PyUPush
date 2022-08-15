from typing import NewType
import codecs
import json
import threading
import time
import pydbus
from gi.repository import GLib
from pydbus.generic import signal
import requests

server_url = "http://127.0.0.1:8976"

# Type hints for robustness
ServerID = NewType('ServerID', str)  # server-side ID
Token = NewType('Token', str)  # client-side token
ServiceName = NewType('ServiceName', str)  # d-bus service name


class UPMessage():
    """ This class contains data passed around between the server communication
    part and the D-Bus API.
    It contains an internal ID specific to this implementation, as well as the
    raw data pushed to the service.
    The internal id can be matched to a UnifiedPush-specified
    application-provided token.
    """
    def __init__(self, id: ServerID, data: bytes):
        self.id = id
        self.data = data


class Server():
    """ Implements the distributor-specific client-server API,
    this is not specified by UnifiedPush, and you are free to use whatever
    transport you want (websockets, SMS, server-sent events, etc).
    For now, this uses HTTP long poll.
    """
    clientPath = "/client/id/"
    clientPathMultiple = "/client/multi_id/"
    registerPath = "/client/register"
    pusherPath = "/push/id/"

    def __init__(self, url):
        self.base_url = url
        self.id_set: set[ServerID] = []
        self.reconnect_flag = False  # When the list of IDs has changed, reco
        self.stop_listening_flag = False
        self.response: requests.Response | None = None

    def unregister(self, id: ServerID):
        return True  # TODO

    def register(self):
        try:
            r = requests.get(self.base_url + self.registerPath)
            j = r.json()
            id = j.get("id")
            return id  # TODO register and return endpoint
        except requests.exceptions.RequestException:
            return None

    def id_to_endpoint(self, id: ServerID):
        return self.base_url + self.pusherPath + id

    def id_is_registered(self, id: ServerID):
        try:
            r = requests.get(self.base_url + self.pusherPath)
            j = r.json
            if j.get("unifiedpush") is not None and \
               j.get("unifiedpush").get("version") == 1:
                return True
        except requests.exceptions.RequestException:
            return False  # Not strictly true, but not sure what to return TODO

    def listen(self, id_set: set[ServerID]):
        self.update_listening(id_set)
        self.__listen()

    def __messages_from_line(self, line: bytes):
        j = json.loads(line)
        messages = []
        for key in j:
            if not isinstance(key, str):
                print(f"key {key} is not a str, ignoring")
                continue
            id = ServerID(key)
            for b64message in j[key]:
                data = codecs.decode(b64message, 'base64')
                message = UPMessage(id, data)
                messages.append(message)
        return messages

    def __listen(self):
        self.stop_listening_flag = False
        while self.stop_listening_flag is False:
            if len(self.id_set) == 0:
                time.sleep(1)
                continue
            self.reconnect_flag = False
            r = requests.get(self.make_listen_multiple_URL(), stream=True)
            self.response = r
            # TODO: check that it returns 2xx, if all ids valid
            while self.reconnect_flag is False and \
                    self.stop_listening_flag is False:
                line = r.raw.readline()
                # time.sleep(0.1)
                if line:  # TODO: check that this catches keepalives
                    messages = self.__messages_from_line(line)
                    # decoded = codecs.decode(line, 'base64')
                    # bus.send_message(sn, decoded)
                    bus.send_messages(messages)

    def stop_listening(self):
        self.stop_listening_flag = True
        if self.response is not None:
            self.response.close()

    def update_listening(self, new_set: set[ServerID]):
        if new_set != self.id_set:
            self.id_set = new_set
            self.reconnect()

    def reconnect(self):
        """ Reconnect to the push server, only has an effect if listening """
        self.reconnect_flag = True
        if self.response is not None:
            self.response.close()

    def make_listen_multiple_URL(self):
        url = self.base_url + self.clientPathMultiple
        for item in self.id_set:
            url += item+"&"
        return url[:-1]


class DBus():
    """ This class implements the UnifiedPush D-Bus distributor API.
    The specified interface is mostly in the Distributor subclass,
    and this class implements helper functions to interface with the server
    and database.
    """
    class PyUPush():  # Dummy D-Bus interface
        """
        <!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
        <!--
            SPDX-FileCopyrightText: 2022 Mayeul Cantan <oss+up@mayeul.net>
            SPDX-License-Identifier: CC0-1.0
        -->
        <node>
          <interface name="org.unifiedPush.Distributor.PyUPush.hello">
            <method name="Say_hello">
              <arg name="answer" type="s" direction="out"/>
            </method>
          </interface>
        </node>
        """
        def Say_hello(self):
            return "hello"

    class Distributor():
        """
        <!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
        <!--
            SPDX-FileCopyrightText: 2022 Volker Krause <vkrause@kde.org>
            SPDX-License-Identifier: CC0-1.0
        -->
        <node>
          <interface name="org.unifiedpush.Distributor1">
            <method name="Register">
              <arg name="serviceName" type="s" direction="in"/>
              <arg name="token" type="s" direction="in"/>
              <arg name="description" type="s" direction="in"/>
              <arg name="registrationResult" type="s" direction="out"/>
              <arg name="registrationResultReason" type="s" direction="out"/>
            </method>
            <method name="Unregister">
              <arg name="token" type="s" direction="in"/>
              <annotation name="org.freedesktop.DBus.Method.NoReply" value="true"/>
            </method>
          </interface>
        </node>
        """
        def Register(self, serviceName: str, token: str, description: str):
            """UnifiedPush-specified register D-Bus method.
            Calls into the implementation-specific server registration code,
            and returns a success/failure message.
            If successful, call the application-provided D-Bus serviceName
            to give it the UnifiedPush endpoint
            """
            # Silently drop serviceName and description after printing them
            print(f"New registration from {serviceName} \
                    with token:{token} -- {description}")
            failure = "REGISTRATION_FAILED"
            success = "REGISTRATION_SUCCEEDED"

            tk = Token(token)
            sn = ServiceName(serviceName)
            if registrationDB.token_exists(tk):  # Already registered
                if server.id_is_registered(registrationDB.get_id(tk)):
                    return (success, "already registered")
            new_id = server.register()
            if new_id is None:
                return (failure, "error during registration")
            status = registrationDB.insert(tk, new_id, sn, description)
            if not status:
                return (failure, "failed to save info")
            bus.send_new_endpoint(sn, tk, server.id_to_endpoint(new_id))  # TODO can MAYBE cause deadlocks?
            return (success, "successfully registered")

        def Unregister(self, token: str):
            """ UnifiedPush-specified unregister D-Bus method. Returns nothing,
            but subsequently calls into the application-provided serviceName
            to tell it the result of the operation.
            """
            tk = Token(token)
            unregistered = True
            # If we didn't know the token, assume unregistration successful
            if registrationDB.token_exists(tk):
                unregistered = server.unregister(registrationDB.get_id(tk))
                if unregistered:
                    registrationDB.remove(tk)
            bus.tell_unregistered(registrationDB.get_serviceName(tk),  # TODO SPEC issue: if not registered, how can I know the service name?
                                  tk, unregistered)
            return

    def __init__(self):
        session_bus = pydbus.SessionBus()
        # system_bus = pydbus.SystemBus() # TODO: try to register on system bus
        self.bus = session_bus

        self.loop = GLib.MainLoop()
        self.bus.publish("org.unifiedpush.Distributor.PyUPush", self.PyUPush(),
                         ("/org/unifiedpush/Distributor", self.Distributor()))
        self.loop.run()

    def stop(self):
        self.loop.quit()

    def get_connector(self, sn: ServiceName):
        return self.bus.get(sn, "/org/unifiedpush/Connector")

    def send_messages(self, messages: list[UPMessage]):
        for message in messages:
            self.send_message(message)

    def send_message(self, message: UPMessage):
        tk = registrationDB.get_token(message.id)
        sn = registrationDB.get_serviceName(tk)
        con = self.get_connector(sn)
        con.org.unifiedpush.Connector1.Message(tk, message.data, "")

    def send_new_endpoint(self, sn: ServiceName, token: Token, endpoint: str):
        con = self.get_connector(sn)
        con.org.unifiedpush.Connector1.NewEndpoint(token, endpoint)

    def tell_unregistered(self, sn: ServiceName, token: Token, status: bool):
        con = self.get_connector(sn)
        if status is True:
            token = Token("")
        con.org.unifiedpush.Connector1.Unregistered(token)


class RegistrationDB():
    """ This class is just an abstract layer above the dictionary
    that serves to map D-Bus UnifiedPush tokens to the
    target D-Bus service Name, and the internal Client-Server token
    """
    class UPclient():
        """ Helper structure that stores info about a client that has asked
        us to register a UnifiedPush endpoint """
        def __init__(self, token: Token, id: ServerID,
                     serviceName: ServiceName, description: str):
            self.id = id
            self.serviceName = serviceName
            self.description = description
            self.token = token

    def __init__(self):
        self.db: dict[Token, self.UPclient] = {}

    def insert(self, token: Token, id: ServerID,
               serviceName: ServiceName, description: str):
        if token in self.db:
            return False
        client = self.UPclient(token, id, serviceName, description)
        self.db[token] = client
        return True

    def id_set(self):
        return set(client.id for client in self.db)

    def token_list(self):
        return list(tk for tk in self.db)

    def token_exists(self, tk: Token):
        return tk in self.db

    def get_id(self, tk: Token):
        client = self.db.get(tk)
        if client is not None:
            return client.id
        return None

    def get_token(self, id: ServerID):
        for tk in self.db:
            if self.db[tk].id == id:
                return tk
        return None

    def remove(self, tk: Token):
        if tk not in self.db:
            return
        del self.db[tk]

    def get_serviceName(self, tk: Token):
        if tk not in self.db:
            return None
        return self.db[tk].serviceName


registrationDB = RegistrationDB()
server = Server(server_url)

id_set = registrationDB.id_set()
listen_thread = threading.Thread(target=server.listen, args=(id_set,))
listen_thread.start()
bus = DBus()
listen_thread.join()
