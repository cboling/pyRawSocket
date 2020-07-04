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
from twisted.internet import reactor
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
        self.io_thread = IOThread()

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

        print('Opening interface {}'.format(self.interface))
        self.io_thread.open(self.interface)

        _x = yield asleep(10)
        _x = yield asleep(10)
        _x = yield asleep(10)

        self.stop()

        print(os.linesep + 'Big loop exiting, stopping reactor')
        reactor.stop()

    def start(self):
        print('Starting background thread')
        reactor.addSystemEventTrigger('before', 'shutdown', self.stop)
        reactor.callWhenRunning(self.big_loop)
        return self

    @inlineCallbacks
    def stop(self):
        print('Stopping background thread')

        io_thread, self.io_thread = self.io_thread, None
        if io_thread is not None:
            reactor.callFromThread(io_thread.stop, 0.2)

        returnValue(io_thread)


if __name__ == '__main__':
    main = Main().start()
    reactor.run()
    print(os.linesep + 'Done')

