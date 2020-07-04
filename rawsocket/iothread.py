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
import pcapy
import fcntl
import select
from threading import Thread, Condition
from .ioport import IOPort


class IOThread(Thread):
    def __init__(self, verbose=False):
        super(IOThread, self).__init__(name='IOThread')
        self._interface = None
        self._stopped = True
        self._verbose = verbose
        self._port = None
        self._cvar = Condition()
        self._waker = _SelectWakerDescriptor()
        self._rx_queue = None
        self._rx_callback = None

        # Statistics
        self._rx_frames = 0
        self._rx_octets = 0
        self._rx_discards = 0
        self._tx_frames = 0
        self._tx_octets = 0
        self._tx_errors = 0

    def __del__(self):
        self.stop()

    def __str__(self):
        return 'TODO'

    @property
    def interface_name(self):
        return self._interface

    @property
    def is_running(self):
        return not self.stopped and self.is_alive()

    def open(self, iface, bpf=None):
        assert self._port is None, 'Interface already Opened'

        self._port = IOPort.create(iface)
        if bpf is not None:
            print('BPF not supported at this time')
            pass

        # devices = pcapy.findalldevs()
        # self._port = pcapy.open_live(iface, 1600, 1, 10)
        # net = self._port.getnet()

        self._interface = iface

        if self._port is not None:
            self.start()

        return True

    def close(self):
        port, self._port = self._port, None
        if port is not None:
            port.close()
        return self

    def start(self):
        """
        Start the background I/O Thread

        If the background I/O Thread is not running prior to an 'open' call setting the interface
        into promiscuous mode, it will be started automatically,

        :return:
        """
        if self._stopped:
            self._stopped = False
            super(IOThread, self).start()

        return self

    def stop(self, timeout=None):
        """
        Stop the IO Thread, optionally waiting on I/O thread termination

        When the timeout argument is present and not None, it should be a floating point number
        specifying a timeout for the operation in seconds (or fractions thereof). If it is 0.0,
        no join will occur and this function will return immediately after signalling for the''
        I/O thread to terminate.

        When the timeout argument is not present or None, the join operation will block until
        the thread terminates.

        :param timeout: (float) Seconds to wait

        :return: (Thread) thread object
        """
        if not self._stopped:
            self._stopped = True

        port, self._port = self._port, None
        waker, self._waker = self._waker, None

        if waker is not None:
            waker.notify()

        if port is not None:
            port.close()

        if timeout is None or timeout > 0.0:
            self.join(timeout)

        return self

    def send(self, frame):
        port = self._port
        if port is not None:
            return port.send(frame)
        return -1

    def run(self):
        # wait for a port to be attached
        while not self._stopped and self._port is None:
            time.sleep(0.010)

        port = self._port
        if port is not None:
            sockets = [self._waker, port]

            while not self._stopped:
                empty = []
                try:
                    _in, _out, _err = select.select(sockets, empty, empty, 10000)  #TODO: Reduce timeout to 1

                except Exception as _e:
                    break

                with self._cvar:
                    for port in _in:
                        if port is self._waker:
                            self._waker.wait()
                            continue
                        else:
                            port.recv()

                    self._cvar.notify_all()

        if self._verbose:
            print(os.linesep + 'exiting background I/O thread', flush=True)

    def statistics(self):
        return {
            'rx_frames': self._rx_frames,
            'rx_octets': self._rx_octets,
            'rx_discards': self._rx_discards,
            'tx_frames': self._tx_frames,
            'tx_octets': self._tx_octets,
            'tx_errors': self._tx_errors,
        }


class _SelectWakerDescriptor(object):
    """
    A descriptor that can be mixed into a select loop to wake it up.
    """
    def __init__(self):
        self.pipe_read, self.pipe_write = os.pipe()
        fcntl.fcntl(self.pipe_write, fcntl.F_SETFL, os.O_NONBLOCK)

    def __del__(self):
        os.close(self.pipe_read)
        os.close(self.pipe_write)

    def fileno(self):
        return self.pipe_read

    def wait(self):
        os.read(self.pipe_read, 1)

    def notify(self):
        """Trigger a select loop"""
        try:
            os.write(self.pipe_write, b'\x00')

        except Exception as e:
            pass
