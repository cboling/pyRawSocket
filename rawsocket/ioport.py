# Copyright 2020, Boling Consulting Solutions
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import socket
import fcntl

_IOPort = None   # Set later based on platform


class IOPort(object):
    """
    Represents a network interface which we can send/receive raw Ethernet frames.
    """
    RCV_SIZE_DEFAULT = 4096
    ETH_P_ALL = 0x03
    RCV_TIMEOUT = 10000
    MIN_PKT_SIZE = 60

    def __init__(self, iface_name, filter=None):
        self.iface_name = iface_name
        self.filter = filter

        # Statistics
        self._rx_frames = 0
        self._rx_octets = 0
        self._rx_discards = 0
        self._tx_frames = 0
        self._tx_octets = 0
        self._tx_errors = 0

        # Open the raw socket
        try:
            self._socket = self._open_socket(self.iface_name, filter)
            
        except Exception as _e:
            self._socket = None
            raise

    @staticmethod
    def create(iface_name):
        return _IOPort(iface_name)

    def _open_socket(self, iface_name, filter):
        raise NotImplementedError('to be implemented by derived class')

    def rcv_frame(self):
        raise NotImplementedError('to be implemented by derived class')

    def __del__(self):
        self.close()
            
    def close(self):
        sock, self._socket = self._socket, None
        if sock is not None:
            try:
                sock.close()
                
            except Exception as _e:
                pass

    def fileno(self):
        return self._socket.fileno()

    def _dispatch(self, proxy, frame):
        try:
            proxy.callback(proxy, frame)

        except Exception as _e:
            pass
            raise

    def recv(self):
        """Called on the select thread when a packet arrives"""
        try:
            frame = self.rcv_frame()
            _str_frame = frame.hex()

        except RuntimeError as _e:
            # we observed this happens sometimes right after the _socket was
            # attached to a newly created veth interface. So we log it, but
            # allow to continue.
            return

        self._rx_frames += 1
        dispatched = False

        # for proxy in self.proxies:
        #     if proxy.filter is None or proxy.filter(frame):
        #         dispatched = True
        #         # reactor.callFromThread(self._dispatch, proxy, frame)

        if not dispatched:
            self._rx_discards += 1

    def send(self, frame):
        sent_bytes = self.send_frame(frame)
        if sent_bytes != len(frame):
            self._tx_errors += 1
        else:
            self._tx_frames += 1
            self._tx_octets += sent_bytes

        return sent_bytes

    def send_frame(self, frame):
        try:
            return self._socket.send(frame)

        except socket.error as err:
            import errno
            if err.args[0] == errno.EINVAL:
                if len(frame) < self.MIN_PKT_SIZE:
                    padding = '\x00' * (self.MIN_PKT_SIZE - len(frame))
                    frame = frame + padding
                    return self._socket.send(frame)
            else:
                raise

    def up(self):
        raise NotImplementedError('to be implemented by derived class')

    def down(self):
        raise NotImplementedError('to be implemented by derived class')

    def statistics(self):
        return {
            'rx_frames': self._rx_frames,
            'rx_octets': self._rx_octets,
            'rx_discards': self._rx_discards,
            'tx_frames': self._tx_frames,
            'tx_octets': self._tx_octets,
            'tx_errors': self._tx_errors,
        }


if sys.platform == 'darwin':
    # config is per https://scapy.readthedocs.io/en/latest/installation.html#mac-os-x
    from scapy.config import conf
    from scapy.arch import pcapdnet, BIOCIMMEDIATE
    import pcapy
    from struct import pack

    conf.use_pcap = True

    class DarwinIOPort(IOPort):
        def _open_socket(self, iface_name, filter=None):
            # TODO: Allow parameters to be set by caller
            try:
                # sin = pcapdnet.open_pcap(iface_name, 1600, 1, 100)
                # fcntl.ioctl(sin.fileno(), BIOCIMMEDIATE, pack("I", 1))
                # sin = pcapdnet.L2pcapSocket(iface=iface_name, promisc=1, filter=filter)
                devices = pcapy.findalldevs()
                sin = pcapy.open_live(iface_name, 1600, 1, 10)
                net = sin.net

            except Exception as _e:
                pass

            return sin

        def rcv_frame(self):
            pkt = next(self._socket)
            if pkt is not None:
                ts, pkt = pkt
            return pkt

        def up(self):
            return self

        def down(self):
            return self

    _IOPort = DarwinIOPort

elif sys.platform.startswith('linux'):

    from rawsocket.afpacket import enable_auxdata, recv
    from rawsocket.util import set_promiscuous_mode

    class LinuxIOPort(IOPort):
        def _open_socket(self, iface_name, filter=None):
            try:
                s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, 0)
                enable_auxdata(s)
                s.bind((self.iface_name, self.ETH_P_ALL))
                set_promiscuous_mode(s, iface_name, True)
                s.settimeout(self.RCV_TIMEOUT)

                if filter is not None:
                    pass        # TODO: Support BPF

                return s

            except Exception as e:
                pass
                raise

        def rcv_frame(self):
            return recv(self._socket, self.RCV_SIZE_DEFAULT)

        def up(self):
            os.system('ip link set {} up'.format(self.iface_name))
            return self

        def down(self):
            os.system('ip link set {} down'.format(self.iface_name))
            return self

    _IOPort = LinuxIOPort
else:
    raise Exception('Unsupported platform {}'.format(sys.platform))
