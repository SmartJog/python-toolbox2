# -*- coding: utf-8 -*-

import os
import fcntl
import resource
import subprocess
import select
import signal
import errno

COMMAND_DEFAULT_TIMEOUT = 3600
COMMAND_DEFAULT_READ_SIZE = 4096


class CommandException(Exception):
    pass


class Command(object):

    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.process = None
        self.memory_limit = 0
        self.timeout = COMMAND_DEFAULT_TIMEOUT
        self.read_size = COMMAND_DEFAULT_READ_SIZE

    def set_timeout(self, timeout):
        self.timeout = timeout

    def set_read_size(self, read_size):
        self.read_size = read_size

    def _reset_sigpipe_handler(self):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    def _set_memory_limit(self):
        if self.memory_limit > 0:
            resource.setrlimit(resource.RLIMIT_AS, (self.memory_limit, self.memory_limit))

    def _preexec_fn(self):
        self._reset_sigpipe_handler()
        self._set_memory_limit()

    def run(self, args, memory_limit=0):
        self.memory_limit = memory_limit
        if (os.path.isdir(self.base_dir) == False):
            os.makedirs(self.base_dir)

        self.process = subprocess.Popen(args,
                                        cwd=self.base_dir,
                                        bufsize=-1,
                                        close_fds=True,
                                        preexec_fn=self._preexec_fn,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)

        fl = fcntl.fcntl(self.process.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.process.stdout, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        fl = fcntl.fcntl(self.process.stderr, fcntl.F_GETFL)
        fcntl.fcntl(self.process.stderr, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    def wait(self, callback=None, loop=True):

        while self.process.returncode is None:

            self.process.poll()

            file_r, file_w, file_x, = select.select([self.process.stdout, self.process.stderr],
                                                    [],
                                                    [],
                                                    self.timeout)

            if not file_r and not file_w and not file_x:
                self.process.kill()
                raise CommandException('Process (pid = %s) has timed out' %
                                        (self.process.pid))
            else:
                stdout = ''
                stderr = ''
                for _file in file_r:
                    buf = self._read_all(_file)
                    if _file == self.process.stdout:
                        stdout = buf
                    elif _file == self.process.stderr:
                        stderr = buf
                if stdout != '' or stderr != '':
                    if callback:
                        callback(stdout, stderr)
            if not loop:
                break

        return self.process.returncode

    def _read_no_intr(self, _file, size):
        while True:
            try:
                return _file.read(size)
            except (OSError, IOError), e:
                if e.errno == errno.EINTR:
                    continue
                elif e.errno == errno.EAGAIN or e.errno == errno.EWOULDBLOCK:
                    return ''
                else:
                    raise

    def _read_all(self, _file,):
        buf = ''
        while True:
            content = self._read_no_intr(_file, self.read_size)
            buf += content
            if content == '':
                break
        return buf
