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
import select
from threading import Thread
import time


class IOThread(Thread):
    def __init__(self, verbose=False):
        super(IOThread, self).__init__(name='IOThread')
        self._interface = None
        self._stopped = True
        self._verbose = verbose
        self._port = None
        self._rx_queue = None
        self._rx_callback = None

    def __del__(self):
        self.stop()

    def __str__(self):
        return 'TODO'

    def open(self, interface, bpf=None):
        assert self._interface is not None, 'Interface already Opened'
        return True

    def close(self):
        return self

    def start(self):
        if self._stopped:
            self._stopped = False
            super(IOThread, self).start()
        return self

    def stop(self):
        if not self._stopped:
            self._stopped = True
            super(IOThread, self).stop()
        return self

    def send(self, frame):
        pass

    def run(self):
        while not self._stopped:
            try:
                time.sleep(0.5)
                if self._verbose:
                    print('-', end='', flush=True)

            except Exception as e:
                break

        if self._verbose:
            print(os.linesep + 'exiting background thread', flush=True)
