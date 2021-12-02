import asyncio
import threading
import time
import typing
from enum import IntEnum

from dbus_next import BusType
from dbus_next.aio import MessageBus as DbusMessageBus
from dbus_next.message import Message as DbusMessage, MessageType as DbusMessageType
from mycroft_bus_client import Message
from ovos_utils.log import LOG

from ovos_PHAL import PHALPlugin


class ConnectivityState(IntEnum):
    """ State of network/internet connectivity.

    See also:
    https://developer-old.gnome.org/NetworkManager/stable/nm-dbus-types.html
    """

    UNKNOWN = 0
    """Network connectivity is unknown."""

    NONE = 1
    """The host is not connected to any network."""

    PORTAL = 2
    """The Internet connection is hijacked by a captive portal gateway."""

    LIMITED = 3
    """The host is connected to a network, does not appear to be able to reach
    the full Internet, but a captive portal has not been detected."""

    FULL = 4
    """The host is connected to a network, and appears to be able to reach the
    full Internet."""


class NetworkManager:
    """Connects to org.freedesktop.NetworkManager over DBus to
    determine network/internet connectivity.

    This differs from the connected() utility method by relying on the reported
    state from org.freedesktop.NetworkManager rather than attempting to reach a
    specific IP address or URL.
    """

    DEFAULT_TIMEOUT = 1.0
    """Seconds to wait for a DBus reply"""

    def __init__(
            self,
            dbus_address: typing.Optional[str] = None,
            bus: typing.Optional[DbusMessageBus] = None
    ):
        self._bus = bus
        self._dbus_address = dbus_address
        self._state: ConnectivityState = ConnectivityState.UNKNOWN

        # Events used to communicate with DBus thread
        self._state_requested = threading.Event()
        self._state_ready = threading.Event()

        # Run DBus message in a separate thread with its own asyncio loop.
        # Thread is started automatically when state is requested.
        self._dbus_thread: typing.Optional[threading.Thread] = None

    def is_network_connected(self, timeout=DEFAULT_TIMEOUT) -> bool:
        """True if the network is connected, but internet may not be
        reachable."""
        return self.get_state(timeout=timeout) in {
            ConnectivityState.PORTAL,
            ConnectivityState.LIMITED,
            ConnectivityState.FULL,
        }

    def is_internet_connected(self, timeout=DEFAULT_TIMEOUT) -> bool:
        """True if the internet is reachable."""
        return self.get_state(timeout=timeout) == ConnectivityState.FULL

    def get_state(self, timeout=DEFAULT_TIMEOUT) -> ConnectivityState:
        """Gets the current connectivity state."""
        self._ensure_thread_started()

        self._state_ready.clear()
        self._state_requested.set()
        self._state_ready.wait(timeout=timeout)

        return self._state

    def _ensure_thread_started(self):
        """Starts DBus thread if necessary"""
        if self._dbus_thread is None:
            self._dbus_thread = threading.Thread(
                target=self._dbus_thread_proc,
                daemon=True,
            )

            self._dbus_thread.start()

    def _dbus_thread_proc(self):
        """Run separate asyncio loop for DBus"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._dbus_thread_proc_async())
        loop.close()

    async def _dbus_thread_proc_async(self):
        """Connects to DBus and waits for requests from main thread."""
        try:
            if self._bus is None:
                # Connect to bus
                if self._dbus_address:
                    # Use custom session bus
                    bus = DbusMessageBus(bus_address=self._dbus_address)
                else:
                    # Use system bus
                    bus = DbusMessageBus(bus_type=BusType.SYSTEM)

                await bus.connect()
            else:
                # Use message bus from constructor
                bus = self._bus

            while True:
                # State update requested from main thread
                self._state_requested.wait()
                self._state = ConnectivityState.UNKNOWN

                reply = await bus.call(
                    DbusMessage(
                        destination="org.freedesktop.NetworkManager",
                        path="/org/freedesktop/NetworkManager",
                        interface="org.freedesktop.NetworkManager",
                        member="CheckConnectivity"
                    ))

                if reply.message_type != DbusMessageType.ERROR:
                    self._state = ConnectivityState(reply.body[0])

                # Signal main thread that state is ready
                self._state_requested.clear()
                self._state_ready.set()
        except Exception:
            LOG.exception("error occurred while waiting for DBus reply")

        # Thread will be restarted if there was an error
        self._dbus_thread = None


class NetworkManagerEvents(PHALPlugin):
    def __init__(self, bus=None):
        super().__init__(bus, "network_manager")
        self.sleep_time = 60
        self.net_manager = NetworkManager()
        self.bus.on("ovos.phal.internet_check", self.handle_check)
        self.bus.emit(Message("ovos.phal.internet_check"))

    def handle_check(self, message):
        state = self.net_manager.get_state()
        if state == ConnectivityState.FULL:
            # has internet
            self.bus.emit(message.reply("ovos.phal.connectivity.internet.connected"))
            self.bus.emit(message.reply("mycroft.internet.connected"))
        elif state > ConnectivityState.NONE:
            # connected to network, but no internet
            self.bus.emit(message.reply("ovos.phal.connectivity.network.connected"))
        else:
            # no internet, not connected
            self.bus.emit(message.reply("ovos.phal.connectivity.disconnected"))
            self.bus.emit(message.reply("enclosure.notify.no_internet"))

        # check again in self.sleep_time
        time.sleep(self.sleep_time)
        self.bus.emit(message)




