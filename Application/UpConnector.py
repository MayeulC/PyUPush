from typing import NewType
from typing import Callable
import pydbus
from gi.repository import GLib
import threading
import time
import random
import string

class DBus():
    DBusServiceName = NewType('DBusServiceName', str)  # d-bus service name

    class Connector():
        """
        <!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
        <!--
            SPDX-FileCopyrightText: 2022 Volker Krause <vkrause@kde.org>
            SPDX-License-Identifier: CC0-1.0
        -->
        <node>
          <interface name="org.unifiedpush.Connector1">
            <method name="Message">
              <arg name="token" type="s" direction="in"/>
              <arg name="message" type="ay" direction="in"/>
              <arg name="messageIdentifier" type="s" direction="in"/>
              <annotation name="org.freedesktop.DBus.Method.NoReply" value="true"/>
            </method>
            <method name="NewEndpoint">
              <arg name="token" type="s" direction="in"/>
              <arg name="endpoint" type="s" direction="in"/>
              <annotation name="org.freedesktop.DBus.Method.NoReply" value="true"/>
            </method>
            <method name="Unregistered">
              <arg name="token" type="s" direction="in"/>
              <annotation name="org.freedesktop.DBus.Method.NoReply" value="true"/>
            </method>
          </interface>
        </node>
        """

        UPToken = NewType('UPToken', str)  # UnifiedPush token
        message_callback_type = Callable[[UPToken, bytes, str], None]
        newEndpoint_callback_type = Callable[[UPToken, str], None]
        unregistered_callback_type = Callable[[UPToken], str]

        def __init__(self, message_callback: message_callback_type,
                     newEndpoint_callback: newEndpoint_callback_type,
                     unregistered_callback: unregistered_callback_type):
            self.message_callback = message_callback
            self.newEndpoint_callback = newEndpoint_callback
            self.unregistered_callback = unregistered_callback

        def Message(self, token: str, message: bytes,
                    messageIdentifier: str) -> None:
            self.message_callback(self.UPToken(token),
                                  message, messageIdentifier)

        def NewEndpoint(self, token: str, endpoint: str) -> None:
            self.newEndpoint_callback(self.UPToken(token), endpoint)

        def Unregistered(self, token: str) -> None:
            self.unregistered_callback(self.UPToken(token))

    def __init__(self, bus_name, connector: Connector, nodeInfo=None):
        session_bus = pydbus.SessionBus()
        self.bus = session_bus
        path = "/org/unifiedpush/Connector"
        self.bus_name = bus_name

        self.owned_bus = self.bus.request_name(bus_name)
        self.bus.register_object(path, connector, nodeInfo)

    def run_loop(self):
        self.loop = GLib.MainLoop()
        self.loop.run()

    def stop_loop(self):
        self.loop.quit()

    def find_distributor_services(self):
        prefix = "org.unifiedpush.Distributor."
        dbus = self.bus.get("org.freedesktop.DBus")
        names = dbus.ListNames()
        candidates = [c for c in names if c.startswith(prefix)]
        return candidates

    def register_distributor(self, dist: 'UnifiedPush.Distributor',
                             description=""):
        dbus_dist = self.bus.get(dist.service_name,
                                 "/org/unifiedpush/Distributor")
        token = self.id = "".join(random.choices(string.ascii_uppercase, k=9))
        dbus_dist.Register(self.bus_name, token, description)

class UnifiedPush():
    class Distributor():
        def __init__(self, service_name: DBus.DBusServiceName,
                     pretty_name: str, bus: DBus):
            self.pretty_name = pretty_name
            self.service_name = service_name
            self.bus = bus

        def register(self, description=""):
            self.bus.register_distributor(self, description)


    def __init__(self, bus: DBus):
        self.bus = bus
        self.token = None
        self.endpoint = None
        self.distributor = None
        self.message_queue = []

    def getDistributors(self) -> list[Distributor]:
        names = self.bus.find_distributor_services()
        prefix_len = len("org.unifiedpush.Distributor.")
        services = [
             self.Distributor(DBus.DBusServiceName(sn),
                              sn[prefix_len:], self.bus) for sn in names]
        return services

    ##def register(self, distributor: Distributor):
    ##    """ Register if not already registered.
    ##    Safe to be called multiple times"""
    ##    # TODO self.token = rand(etc)
    ##    # TODO double check if I need this, maybe not if already reg, but check return value anyway self.endpoint = None
    ##    self.bus.register(self.token, distributor.path)

    def is_registered(self):
        return self.token is not None and \
               self.distributor is not None and \
               self.endpoint is not None

    def unregister(self):
        if not self.is_registered:
            return
        self.bus.unregister(self.token, self.distributor.path)

    def newEndPointCallback(self, token, endpoint):
        if self.token != token:
            print("Token invalid, rejecting new endpoint")
            return
        self.endpoint = endpoint

    def newMessageCallback(self, token, message, identifier):
        if self.token != token:
            print("Token invalid, rejecting message")
            return
        self.message_queue.append(message)

    def unregisteredCallback(self, token, endpoint):
        if self.token != token:
            print("Token invalid, not unregistering")
        if self.endpoint is None:
            print("Wasn't supposed to happen, unregistered but not previously registered")
        self.endpoint = None
        self.token = None


def message(token, message, identifier):
    print(f"tk: {token}, message: {message}, identifier: {identifier}")
def new_endpoint(token, endpoint):
    print(f"tk: {token}, endpoint: {endpoint}")
def unregistered(token):
    print(f"unregistered {token}")


identifier = 0
listener_started = False

while not listener_started:
    try:
        bus_name = f'org.UnifiedPush.UPyExample{identifier}'
        connector = DBus.Connector(message, new_endpoint, unregistered)
        dbus = DBus(bus_name, connector)
        dbus_thread = threading.Thread(target=dbus.run_loop)
        dbus_thread.start()
        print("Started D-Bus listener")
        listener_started = True
    except RuntimeError:
        identifier += 1

def die():
    dbus.stop_loop()
    dbus_thread.join()
    exit()


up = UnifiedPush(dbus)

distributors = up.getDistributors()
distributor_names = [d.pretty_name for d in distributors]
n = len(distributors)

print(f"{n} distributors found: {distributor_names}")

if len(distributors) < 1:
    die()

print(f"choosing the first one: {distributor_names[0]}")
# NOTE: here, one should ask the user for a choice
dist = distributors[0]

dist.register("Example application")

try:
    time.sleep(200)
    print("Closing after 200 seconds")
except KeyboardInterrupt:
    pass

die()
