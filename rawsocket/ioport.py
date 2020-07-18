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
from struct import pack
from binascii import hexlify

_IOPort = None  # Set later based on O/S platform type


class IOPort(object):
    """
    Represents a network interface which we can send/receive raw Ethernet frames.
    """
    RCV_SIZE_DEFAULT = 4096
    ETH_P_ALL = 0x03
    # RCV_TIMEOUT = 10
    RCV_TIMEOUT = 24 * 3600
    MIN_PKT_SIZE = 60

    def __init__(self, iface_name, rx_callback, bpf_filter=None, verbose=False):
        """
        Class initializer

        :param iface_name:  (str) Interface Name to open
        :param rx_callback: (func) Function to process received frames (bytes)
        :param bpf_filter:  (BpfProgramFilter) Berkley Packet Filter to filter Rx Frames
        :param verbose:     (bool) True if verbose, debug output, should be shown
        """
        self._iface_name = iface_name
        self._mac_address = None
        self._filter = bpf_filter
        self._rx_callback = rx_callback
        self._verbose = verbose
        self._must_pad = False

        # Statistics
        self._rx_frames = 0
        self._rx_octets = 0
        self._rx_discards = 0
        self._tx_frames = 0
        self._tx_octets = 0
        self._tx_errors = 0

        # Open the raw socket
        try:
            self._socket = self._open_socket()

        except Exception as _e:
            self._socket = None
            raise

    def __del__(self):
        self.close()

    @staticmethod
    def create(iface_name, rx_callback, bpf_filter=None, verbose=False):
        return _IOPort(iface_name, rx_callback, bpf_filter=bpf_filter, verbose=verbose)

    @property
    def name(self):
        """
        Get the name of the interface
        :return: (str) interface name
        """
        return self._iface_name

    @property
    def mac_address(self):
        """
        Get MAC Address of port interface

        :return: (bytes) MAC Address (6 octets) or None on failure
        """
        return self._mac_address or self._get_mac_address()

    def _open_socket(self):
        raise NotImplementedError('to be implemented by derived class')

    def _rcv_frame(self):
        raise NotImplementedError('to be implemented by derived class')

    def _get_mac_address(self):
        raise NotImplementedError('to be implemented by derived class')

    def close(self):
        """
        Close the IO Port socket
        """
        self._rx_callback = None
        sock, self._socket = self._socket, None

        if sock is not None:
            try:
                sock.close()

            except Exception as _e:
                pass

    def fileno(self):
        """
        Return the socket's file descriptor

        :return: file descriptor
        """
        sock = self._socket
        return sock.fileno() if sock is not None else None

    def recv(self):
        """Called on the select thread when a packet arrives"""
        try:
            # Get the frame from the O/S Specific Layer
            frame = self._rcv_frame()
            callback = self._rx_callback

            if callback is None or frame is None:
                self._rx_discards += 1

            else:
                self._rx_frames += 1
                self._rx_octets += len(frame)
                callback(frame)

        except RuntimeError as _e:
            # we observed this happens sometimes right after the _socket was
            # attached to a newly created veth interface. So we log it, but
            # allow to continue.
            return

    def send(self, frame):
        """
        Send a frame on the interface

        :param frame: (bytes) Frame to send

        :return: (int) number of bytes sent, -1 on error
        """
        sent_bytes = self._send_frame(frame)

        if sent_bytes != len(frame):
            self._tx_errors += 1
        else:
            self._tx_frames += 1
            self._tx_octets += sent_bytes

        return sent_bytes

    def _pad_frame(self, frame):
        padding = '\x00' * (self.MIN_PKT_SIZE - len(frame))
        return frame + padding

    def _send_frame(self, frame):
        if self._socket is None:
            return -1

        if self._must_pad and len(frame) < self.MIN_PKT_SIZE:
            frame = self._pad_frame(frame)

        try:
            return self._socket.send(frame)

        except socket.error as err:
            import errno
            if err.args[0] == errno.EINVAL:
                if len(frame) < self.MIN_PKT_SIZE:
                    self._must_pad = True
                    return self._socket.send(self._pad_frame(frame))
            else:
                raise

    def up(self):
        """
        Enable the IOPort's interface

        :return: (IOPort) self reference
        """
        raise NotImplementedError('to be implemented by derived class')

    def down(self):
        """
        Disable the IOPort's interface

        :return: (IOPort) self reference
        """
        raise NotImplementedError('to be implemented by derived class')

    def statistics(self):
        """
        Get rx/tx statistics for the port

        :return: (dict) statistics
        """
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

    conf.use_pcap = True

    class DarwinIOPort(IOPort):
        def _open_socket(self):
            # TODO: Allow parameters to be set by caller
            try:
                # sin = pcapdnet.open_pcap(iface_name, 1600, 1, 100)
                # fcntl.ioctl(sin.fileno(), BIOCIMMEDIATE, pack("I", 1))
                # sin = pcapdnet.L2pcapSocket(iface=iface_name, promisc=1, filter=filter)
                devices = pcapy.findalldevs()
                sin = pcapy.open_live(self._iface_name, 1600, 1, 10)
                net = sin.net

            except Exception as _e:
                pass

            return sin

        def _rcv_frame(self):
            pkt = next(self._socket)
            if pkt is not None:
                ts, pkt = pkt
                if self._filter is not None and self._filter(pkt) == 0:
                    pkt = None
            return pkt

        def up(self):
            return self

        def down(self):
            return self

        def _get_mac_address(self):
            raise NotImplementedError('TODO: Not yet implemented')


    _IOPort = DarwinIOPort

elif sys.platform.startswith('linux'):

    from rawsocket.afpacket import enable_auxdata, recv
    from rawsocket.util import set_promiscuous_mode
    from ctypes import create_string_buffer, addressof

    # As defined in asm/socket.h
    SO_ATTACH_FILTER = 26


    class LinuxIOPort(IOPort):
        def _open_socket(self):
            try:
                s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, 0)
                enable_auxdata(s)

                if self._filter is not None:
                    # Convert to byte code
                    filters = b''
                    tuple_list = self._filter.get_bpf()
                    for (code, jt, jf, k) in tuple_list:
                        data = pack('HBBI', code, jt, jf, k)
                        filters += data

                    b = create_string_buffer(filters)
                    mem_addr_of_filters = addressof(b)
                    fprog = pack('HL', len(tuple_list), mem_addr_of_filters)

                    s.setsockopt(socket.SOL_SOCKET, SO_ATTACH_FILTER, fprog)

                s.bind((self._iface_name, self.ETH_P_ALL))
                set_promiscuous_mode(s, self._iface_name, True)
                s.settimeout(self.RCV_TIMEOUT)

                return s

            except Exception as e:
                pass
                raise

        def _rcv_frame(self):
            return recv(self._socket, self.RCV_SIZE_DEFAULT)

        def up(self):
            os.system('ip link set {} up'.format(self._iface_name))
            return self

        def down(self):
            os.system('ip link set {} down'.format(self._iface_name))
            return self

        def _get_mac_address(self):
            if self._socket is None:
                return None

            # extract mac address
            mac = hexlify(self._socket.getsockname()[4])
            return mac


    _IOPort = LinuxIOPort
else:
    raise Exception('Unsupported platform {}'.format(sys.platform))
