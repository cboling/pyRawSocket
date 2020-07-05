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
import socketserver

from twisted.internet.defer import inlineCallbacks, returnValue, Deferred
from twisted.internet import reactor, threads
from rawsocket.iothread import IOThread

try:
    import sys
    REMOTE_DBG_HOST = '192.168.0.216'

    # sys.path.append('/voltha/voltha/pydevd/pydevd-pycharm.egg')
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

        bpf = None

        print(os.linesep + 'Opening interface {}'.format(self.interface), flush=True)
        reactor.callInThread(self.io_thread.open, self.interface, self.rx_callback)

        print('sleeping 10 seconds', flush=True)
        _x = yield asleep(10)

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
        print('Stopping background thread')

        io_thread, self.io_thread = self.io_thread, None
        if io_thread is not None:
            import pprint
            pp = pprint.PrettyPrinter(indent=4,)
            stats = io_thread.statistics()

            print('Statistics:')
            pp.pprint(stats)

            try:
                # may block during brief join
                _d = yield threads.deferToThread(io_thread.stop, 0.2)

            except Exception as _e:
                pass

        returnValue(io_thread)

    @inlineCallbacks
    def send(self, frame):
        if self.io_thread is None:
            returnValue(-1)

        try:
            # Not sure if it will block or not, just to be safe
            print('Sending {} bytes'.format(len(frame)))

            bytes_sent = yield reactor.deferToThread(self.io_thread.send, frame)

            print('Tx success: {} bytes'.format(bytes_sent))
            returnValue(bytes_sent)

        except Exception as _e:
            returnValue(-2)

    def _rcv_io(self, frame):
        from scapy.layers.l2 import Ether, Dot1Q

        # Decode the received frame
        _str_frame = frame.hex()
        response = Ether(frame)

        if response.haslayer(Dot1Q):
            first_layer_info = response.getlayer(Dot1Q)
            # print(first_layer_info)

        # print(response)

    def rx_callback(self, frame):
        """
        Rx Callback

        This is called from the IOThread and schedules the rx on the reactor thread

        :param frame:
        """
        reactor.callFromThread(self._rcv_io, frame)


if __name__ == '__main__':
    main = Main().start()
    reactor.run()
    print(os.linesep + 'Done')

