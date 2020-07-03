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
import time
import types
import sys
import socketserver
import configparser

from twisted.internet.defer import inlineCallbacks, returnValue, Deferred
from twisted.internet.task import LoopingCall
from zope.interface import implementer
from twisted.internet import reactor
from ..rawsocket.iothread import IOThread


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
        self.interface = 'en0'
        self.io_thread = IOThread()
        self.src_mac = None

    @inlineCallbacks
    def big_loop(self):
        # pause before listening (make sure this works)
        print('\nSpinning wheels for 5 seconds')
        for tick in range(5):
            print('.', end='', flush=True)
            _d = yield asleep(1)

        # Get some info on interface

        # Open interface


        main.stop()

        print('Opening interface {}'.format(self.interface))
        self.mgmt.open(self.interface, self.olt_mac)

        print(os.linesep + 'Big loop exiting, stoping reactor')
        reactor.stop()

    def start(self):
        print('Starting background thread')
        reactor.addSystemEventTrigger('before', 'shutdown', self.stop)
        self.mgmt.start()

        reactor.callWhenRunning(self.big_loop)
        return self

    def stop(self):
        print('Stopping background thread')
        mgmt, self.mgmt = self.mgmt, None
        if mgmt is not None:
            mgmt.stop()


if __name__ == '__main__':
    main = Main().start()
    reactor.run()
    print(os.linesep + 'Done')

