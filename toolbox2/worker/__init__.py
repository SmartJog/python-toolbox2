# -*- coding: utf-8 -*-

from toolbox2.command import Command
from toolbox2.exception import Toolbox2Exception


class WorkerException(Toolbox2Exception):
    pass


class Worker(object):

    class File(object):
        def __init__(self, path, params=None):
            self.path = path
            self.params = params or {}

        def get_args(self):
            return [self.path]

    class InputFile(File):
        pass

    class OutputFile(File):
        pass

    def __init__(self, log, params):
        self.log = log
        self.params = params or {}
        self.command = None
        self.tool = None
        self.is_running = False
        self.input_files = []
        self.output_files = []

        self.time = 0
        self.timeleft = 0
        self.progress = 0
        self.memory_limit = 0

        self.stdout = ''
        self.stderr = ''
        self.error_lines = 1

    def add_input_file(self, path, params=None):
        """
        Add an input file with associated parameters.
        """
        self.input_files.append(self.InputFile(path, params))

    def add_output_file(self, path, params=None):
        """
        Add an output file with associated parameters.
        """
        self.output_files.append(self.OutputFile(path, params))

    def _handle_output(self, stdout, stderr):
        """
        Virtual method to handle stdout and stderr from running process.
        Compute progress and timeleft here.
        """
        raise NotImplementedError

    def get_args(self):
        """
        Return command line parameters as a string list.
        """
        args = []
        for key, value in self.params.iteritems():
            args.append(key)
            if not value is None:
                args.append(value)

        return args

    def get_process_args(self):
        """
        Return command line as a string list.
        """
        args = [self.tool]
        args += self.get_args()
        return args

    def get_error(self):
        """
        Return the last lines from stderr. The number of lines returned
        could be configured with Worker.error_lines attribute.
        """
        lines = self.stderr.split('\n')
        lines.reverse()

        i = 0
        error_lines = []
        for line in lines:
            if not line == '':
                i += 1
                error_lines.append(line)
            if i >= self.error_lines:
                break

        error_lines.reverse()
        return '\n'.join(error_lines)

    def _setup(self, base_dir):
        """
        Virtual method called by run method.
        """
        raise NotImplementedError

    def _finalize(self):
        """
        This method is called at end of command or job.
        """
        pass

    def run(self, base_dir):
        """
        Compute and launch command line.
        """
        self._setup(base_dir)

        args = self.get_process_args()
        args = [str(arg) for arg in args]
        cmd = ' '.join(args)
        self.log.info('Running command: %s', cmd)

        self.command = Command(base_dir)
        self.command.run(args, self.memory_limit)

        self.is_running = True

    def wait(self):
        """
        Wait running process. If an error occurs raise a WorkerException,
        otherwise returns 0
        """
        ret = self.command.wait(self._handle_output)
        self._finalize()
        if ret != 0:
            error = self.get_error()
            raise WorkerException(error)
        return ret

    def wait_noloop(self):
        """
        Wait (non-blocking) running process and return its exit code.
        If process has not exited yet, this method returns None otherwise,
        it returns its exit code.
        """
        ret = self.command.wait(self._handle_output, loop=False)
        if ret != None:
            self._finalize()
        return ret
