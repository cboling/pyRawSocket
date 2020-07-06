#!/usr/bin/env python3
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
import pprint
from twisted.internet.defer import inlineCallbacks, returnValue, Deferred, succeed, fail, failure
from twisted.internet import reactor, threads
from rawsocket.iothread import IOThread, BpfProgramFilter

try:
    import sys

    REMOTE_DBG_HOST = '192.168.0.216'

    import pydevd_pycharm

    # Initial breakpoint
    pydevd_pycharm.settrace(REMOTE_DBG_HOST, port=5678, stdoutToServer=True, stderrToServer=True, suspend=False)

except ImportError:
    print('Error importing pydevd package.')
    print('REMOTE DEBUGGING will not be supported in this run...')
    # Continue on, you do not want to completely kill VOLTHA, you just need to fix it.

except AttributeError:
    print('Attribute error. Perhaps try to explicitly set PYTHONPATH to'
          'pydevd directory and run again?')
    print('REMOTE DEBUGGING will not be supported in this run...')
    # Continue on, you do not want to completely kill VOLTHA, you just need to fix it.

except:
    print("pydevd startup exception: %s" % sys.exc_info()[0])
    print('REMOTE DEBUGGING will not be supported in this run...')


def asleep(dt):
    """
    Async (event driven) wait for given time period (in seconds)
    :param dt: Delay in seconds
    :return: Deferred to be fired with value None when time expires.
    """
    d = Deferred()
    reactor.callLater(dt, lambda: d.callback(None))
    return d


class Main(object):
    def __init__(self):
        self.interface = 'eth0'
        self.io_thread = IOThread(verbose=True)
        self._mac_address = None
        self._destination_macs = set()
        self._source_macs = set()
        self._ether_types = set()
        self._send_deferred = None

    @inlineCallbacks
    def big_loop(self):
        # pause before listening (make sure this works)
        print('\nSpinning wheels for 3 seconds so we know visually we are at least running')
        for tick in range(3):
            print('.', end='', flush=True)
            _d = yield asleep(1)

        # Get some info on interface

        # Open interface
        # self.io_thread.start()    #  optional as open below starts it if needed

        etype = 0x806  # Just arps
        src_mac = '08:95:2a:1b:19:ae'
        dst_mac = '08:95:2a:1b:19:ae'
        vlan = 4090
        tpid = 0x8100
        try:
            _bpf_etype = 'ether[12:2] = 0x{:04x}'.format(etype)
            _bpf_vlan = 'ether[12:2] = 0x{:04x}'.format(tpid) + ' and ' + \
                        '(ether[14:2] & 0xfff) = 0x{:03x}'.format(vlan)
            _bpf_src = 'ether src host {}'.format(src_mac)
            _bpf_dst = 'ether dst host {}'.format(dst_mac)
            _bpf_any_vlan = 'ether[12:2] = 0x{:04x}'.format(tpid)

            # bpf_filter = None
            # bpf_filter = BpfProgramFilter(_bpf_etype)
            # bpf_filter = BpfProgramFilter(_bpf_src)
            # bpf_filter = BpfProgramFilter(_bpf_dst)
            # bpf_filter = BpfProgramFilter(_bpf_vlan)
            bpf_filter = BpfProgramFilter(_bpf_any_vlan)

            print(os.linesep + 'Opening interface {}'.format(self.interface), flush=True)
            _d = yield threads.deferToThread(self.io_thread.open, self.interface,
                                             self.rx_callback, bpf_filter=bpf_filter,
                                             keep_closed=True)

            self._send_deferred = self._ping(5)

            print('sleeping 15 seconds', flush=True)
            _x = yield asleep(15)

        except Exception as _e:
            pass

        print('stopping', flush=True)
        self.stop()

        print(os.linesep + 'Big loop exiting, stopping reactor')
        reactor.stop()

    def start(self):
        reactor.addSystemEventTrigger('before', 'shutdown', self.stop)
        reactor.callWhenRunning(self.big_loop)
        return self

    @inlineCallbacks
    def stop(self):
        d, self._source_macs = self._send_deferred, None
        if d is not None:
            print('Stopping tx loop')
            d.cancel()

        print('Stopping background thread')

        io_thread, self.io_thread = self.io_thread, None
        if io_thread is not None:
            pp = pprint.PrettyPrinter(indent=4, )
            stats = io_thread.statistics(self.interface)
            print('Statistics:')
            pp.pprint(stats)

            try:
                # may block during brief join
                _d = yield threads.deferToThread(io_thread.stop, 0.2)

                pp = pprint.PrettyPrinter(indent=4, )
                stats = io_thread.statistics(self.interface)
                print('Statistics:')
                pp.pprint(stats)
                print('dst macs: ', self._destination_macs)
                print('src macs: ', self._source_macs)
                print('etypes  : ', self._ether_types)

            except Exception as _e:
                pass

        returnValue(io_thread)

    def send(self, frame):
        """
        Send a frame
        :param frame: (bytes) frame to send
        :return: (deferred) deferred
        """
        if self.io_thread is None:
            return fail(failure.Failure(Exception('IOThread is not initialized')))

        # Not sure if it will block or not, just to be safe
        print('Sending {} bytes'.format(len(frame)))

        d = threads.deferToThread(self.io_thread.send, frame)

        def success(bytes_sent):
            print(os.linesep + 'Tx success: {} bytes'.format(bytes_sent), flush=True)
            return bytes_sent

        return d.addCallback(success)

    def _rcv_io(self, frame):
        from scapy.layers.l2 import Ether
        eth_hdr = Ether(frame)
        self._source_macs.add(eth_hdr.src)
        self._destination_macs.add(eth_hdr.dst)
        self._ether_types.add(eth_hdr.type)

    def rx_callback(self, frame):
        """
        Rx Callback

        This is called from the IOThread and schedules the rx on the reactor thread

        :param frame:
        """
        reactor.callFromThread(self._rcv_io, frame)

    def _ping(self, seconds):
        mac = self._mac_address or self.io_thread.port(self.interface).mac_address
        # TODO: Work in progress
        return None


if __name__ == '__main__':
    main = Main().start()
    reactor.run()
    print(os.linesep + 'Done')
