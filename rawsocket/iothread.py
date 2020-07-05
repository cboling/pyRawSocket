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
        self._rx_callback = None

    def __del__(self):
        self._rx_callback = None
        self.stop()

    def __str__(self):
        return 'TODO'

    @property
    def interface_name(self):
        return self._interface

    @property
    def is_running(self):
        return not self.stopped and self.is_alive()

    def open(self, iface, rx_callback, bpf_filter=None):
        assert self._port is None, 'Interface already Opened'

        if bpf_filter is not None:
            print("TODO: Support compile BPF")  # TODO: Compile and install filter in kernel if possible
            print("BFP is: '{}'".format(bpf_filter))
            pass

        self._rx_callback = rx_callback
        self._port = IOPort.create(iface, rx_callback, bpf_filter=bpf_filter, verbose=self._verbose)

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
        sockets = [self._waker, port]

        while not self._stopped and self._port is not None:
            empty = []
            try:
                # TODO: What is best timeout?
                _in, _out, _err = select.select(sockets, empty, empty, 10)  # TODO: Reduce timeout to 1

            except Exception as _e:
                break

            with self._cvar:
                for fd in _in:
                    try:
                        if fd is self._waker:
                            self._waker.wait()
                            continue

                        elif fd is port:
                            port.recv()
                        else:
                            pass    # Stale port or waker, may be shutting down

                        self._cvar.notify_all()

                    except Exception as _e:
                        pass

        if self._verbose:
            print(os.linesep + 'exiting background I/O thread', flush=True)

    def statistics(self):
        return self._port.statistics() if self._port is not None else None


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


class BpfProgramFilter(object):
    """
    Convenience packet filter based on the well-tried Berkeley Packet Filter,
    used by many well known open source tools such as pcap and tcpdump.
    """
    def __init__(self, program_string):
        """
        Create a filter using the BPF command syntax. To learn more,
        consult 'man pcap-filter'.
        :param program_string: The textual definition of the filter. Examples:
        'vlan 1000'
        'vlan 1000 and ip src host 10.10.10.10'
        """
        self._program_string = program_string
        self._bpf = pcapy.BPFProgram(program_string)

    def __call__(self, frame):
        """
        Return 1 if frame passes filter.
        :param frame: Raw frame provided as Python string
        :return: 1 if frame satisfies filter, 0 otherwise.
        """
        return self._bpf.filter(frame)

    def __str__(self):
        return self._program_string
