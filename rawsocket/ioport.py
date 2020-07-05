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

    def __init__(self, iface_name, rx_callback, bpf_filter=None, verbose=False):
        self.iface_name = iface_name
        self._filter = bpf_filter
        self._rx_callback = rx_callback
        self._verbose = verbose

        # Statistics
        self._rx_frames = 0
        self._rx_octets = 0
        self._rx_discards = 0
        self._tx_frames = 0
        self._tx_octets = 0
        self._tx_errors = 0

        # Following are just for debugging and will be removed
        self._destination_macs = set()
        self._source_macs = set()
        self._ether_types = set()

        # Open the raw socket
        try:
            self._socket = self._open_socket(self.iface_name, filter)
            
        except Exception as _e:
            self._socket = None
            raise

    @staticmethod
    def create(iface_name, rx_callback, bpf_filter=None, verbose=False):
        return _IOPort(iface_name, rx_callback, bpf_filter=bpf_filter, verbose=verbose)

    def _open_socket(self, iface_name, filter):
        raise NotImplementedError('to be implemented by derived class')

    def _rcv_frame(self):
        raise NotImplementedError('to be implemented by derived class')

    def __del__(self):
        self.close()
            
    def close(self):
        self._rx_callback = None
        sock, self._socket = self._socket, None

        if sock is not None:
            try:
                sock.close()
                
            except Exception as _e:
                pass

    def fileno(self):
        return self._socket.fileno()

    def recv(self):
        """Called on the select thread when a packet arrives"""
        try:
            # Get the frame from the O/S Specific Layer
            frame = self._rcv_frame()
            callback = self._rx_callback

            if callback is None or (self._filter is not None and self._filter(frame) == 0):
                self._rx_discards += 1

            else:
                self._rx_frames += 1
                self._rx_octets += len(frame)
                callback(frame)

                # Following is for debug only
                from scapy.layers.l2 import Ether
                eth_hdr = Ether(frame)
                self._source_macs.add(eth_hdr.src)
                self._destination_macs.add(eth_hdr.dst)
                self._ether_types.add(eth_hdr.type)

        except RuntimeError as _e:
            # we observed this happens sometimes right after the _socket was
            # attached to a newly created veth interface. So we log it, but
            # allow to continue.
            return

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

            # Following are just for debugging and will be removed
            'destination_macs': self._destination_macs,
            'source_macs': self._source_macs,
            'etypes': self._ether_types,
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

        def _rcv_frame(self):
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
                    print('TODO: Support compiled BFPs')        # TODO: Support BPF as compiled

                return s

            except Exception as e:
                pass
                raise

        def _rcv_frame(self):
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
