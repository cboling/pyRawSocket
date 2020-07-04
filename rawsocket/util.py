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

"""
Network utilities with some originally from the OpenFlow test framework

oftest from: http://github.com/floodlight/oftest
"""
from socket import socket
from fcntl import ioctl
from struct import pack, unpack

# From bits/ioctls.h
SIOCGIFINDEX = 0x8933          # name -> if_index mapping

# From netpacket/packet.h
PACKET_ADD_MEMBERSHIP = 1
PACKET_DROP_MEMBERSHIP = 2
PACKET_MR_PROMISC = 1

# From bits/socket.h
SOL_PACKET = 263


def interface_ioctl(iface, ioctl_cmd, sock=None):
    """
    Execute the ioctl command on the given interface

    :param iface:     (str) Interface name
    :param ioctl_cmd: (int) ioctl command to execute
    :param sock:      (socket) socket handle to use, if None, a temporary socket will be opened

    :return: (bytes) Return output of the ioctl()
    """
    s = sock or socket()

    try:
        ifreq = ioctl(s, ioctl_cmd, pack("16s16x", str(iface).encode('utf-8')))

    except Exception as _e:
        pass    # Primarily here for placement of a debug breakpoint
        raise

    finally:
        if sock is None:
            s.close()

    return ifreq


def get_if_index(iface, sock=None):
    """
    Get the ifIndex of an interface

    :param iface: (str) Interface name
    :param sock:  (socket) socket handle to use, if None, a temporary socket will be opened

    :return: (int) ifIndex
    """
    try:
        data = interface_ioctl(iface, SIOCGIFINDEX, sock)
        index = int(unpack("I", data[16:20])[0])
        return index

    except Exception as _e:
        pass    # Primarily here for placement of a debug breakpoint
        raise


def set_promiscuous_mode(sock, iface, enable=True):
    """
    Enable/disable promiscous mode on a network interface

    :param sock:   (socket) socket handle to use
    :param iface:  (str) Interface name
    :param enable: (bool) True to enable promiscuous mode

    :return: (bool) True if successful
    """
    try:
        ifindex = get_if_index(iface, sock)
        mreq = pack("IHH8s", ifindex, PACKET_MR_PROMISC, 0, b"")

        cmd = PACKET_ADD_MEMBERSHIP if enable else PACKET_DROP_MEMBERSHIP
        sock.setsockopt(SOL_PACKET, cmd, mreq)
        return True

    except Exception as _e:
        pass    # Primarily here for placement of a debug breakpoint
        raise
