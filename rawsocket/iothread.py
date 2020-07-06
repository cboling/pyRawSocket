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
import socket
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
        self._ports = dict()
        self._ports_modified = False
        self._cvar = Condition()
        self._waker = _SelectWakerDescriptor()

    def __del__(self):
        self._rx_callback = None
        self.stop()

    def __str__(self):
        return 'TODO'

    @property
    def interfaces(self):
        return [key for key, _ in self._ports]

    def port(self, interface):
        return self._ports.get(interface)

    @property
    def is_running(self):
        return not self._stopped and self.is_alive()

    def open(self, iface, rx_callback, bpf_filter=None, verbose=False, keep_closed=False):
        assert iface not in self._ports, 'Interface already Opened'

        self._ports[iface] = IOPort.create(iface, rx_callback,
                                           bpf_filter=bpf_filter,
                                           verbose=self._verbose or verbose)
        # Make sure rx thread is running if not suppressed
        if not keep_closed:
            self.start()

        self._ports_modified = True
        self._waker.notify()
        return True

    def close(self, interface=None):
        port = self._ports.pop(interface, None)
        if port is None:
            return False

        port.close()
        self._ports_modified = True
        self._waker.notify()
        return True

    def _close_all(self):
        ports, self._ports = self._ports, None

        if len(ports):
            for _, port in ports.items():
                port.close()

            self._ports_modified = True
            self._waker.notify()
        return True

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
            waker, self._waker = self._waker, None

            self._close_all()
            if waker is not None:
                waker.notify()

            if timeout is None or timeout > 0.0:
                self.join(timeout)

        return self

    def send(self, interface, frame):
        port = self._ports.get(interface, None)
        if port is not None:
            return port.send(frame)
        return -1

    def run(self):
        # Outer loop invoked on port change
        while not self._stopped:
            fds = [self._waker] + [port for _, port in self._ports.items()]
            self._ports_modified = False
            empty = []

            while not self._stopped:
                try:
                    _in, _out, _err = select.select(fds, empty, empty, 1)

                except Exception as _e:
                    break

                except socket.timeout:
                    if self._verbose:
                        print('Timeout')
                    break

                with self._cvar:
                    for fd in _in:
                        try:
                            if fd is self._waker:
                                self._waker.wait()
                                continue

                            elif isinstance(fd, IOPort):
                                fd.recv()

                            else:
                                pass  # Stale port or waker, may be shutting down

                            self._cvar.notify_all()

                        except Exception as _e:
                            pass  # for debug purposes

                    if self._ports_modified:
                        break

        if self._verbose:
            print(os.linesep + 'exiting background I/O thread', flush=True)

    def statistics(self, interface):
        port = self._ports.get(interface)
        return port.statistics() if port is not None else None


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

    def get_bpf(self):
        return self._bpf.get_bpf()
