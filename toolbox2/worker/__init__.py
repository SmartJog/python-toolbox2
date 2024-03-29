from toolbox2.command import Command
from toolbox2.command import COMMAND_DEFAULT_KILL_TIMEOUT
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

    def __init__(self, log, params=None):
        """
        Create a new worker.

        :param log: logger instance to use
        :type log: logging.Logger

        :param params: worker parameters
        :type params: dict
        """
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
        self.kill_timeout = COMMAND_DEFAULT_KILL_TIMEOUT

        self.stdout = ""
        self.stderr = ""
        self.error_lines = 1

    def add_input_file(self, path, params=None):
        """
        Add an input file with associated parameters.

        :param path: absolute path of the input file.
        :type path: string

        :param params: parameters associated with input file
        :type params: dict
        """
        self.input_files.append(self.InputFile(path, params))

    def add_output_file(self, path, params=None):
        """
        Add an output file with associated parameters.

        :param path: absolute path of the input file.
        :type path: string

        :param params: parameters associated with input file
        :type params: dict
        """
        self.output_files.append(self.OutputFile(path, params))

    def _handle_output(self, stdout, stderr):
        """
        Store stdout and stderr from command line.
        """
        self.stdout += stdout
        self.stderr += stderr

    def get_args(self):
        """
        Return command line parameters as a string list.
        """
        args = []
        for key, value in list(self.params.items()):
            args.append(key)
            if value != None and value != "":
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
        lines = self.stderr.split("\n")
        lines.reverse()

        i = 0
        error_lines = []
        for line in lines:
            if not line == "":
                i += 1
                error_lines.append(line)
            if i >= self.error_lines:
                break

        error_lines.reverse()
        return "\n".join(error_lines)

    def _setup(self, base_dir):
        """
        Initialize the worker. This method should be implemented by subclasses
        if needed.
        """
        pass

    def _finalize(self):
        """
        Do some processing at the end of the worker job. This method
        should be implemented by subclasses.
        """
        pass

    def run(self, base_dir):
        """
        Compute and launch command line.
        """
        self._setup(base_dir)

        args = self.get_process_args()
        args = [str(arg) for arg in args]
        cmd = " ".join(args)
        self.log.info("Running command: %s", cmd)

        self.command = Command(base_dir)
        self.command.memory_limit = self.memory_limit
        self.command.kill_timeout = self.kill_timeout
        self.command.run(args)

        self.is_running = True

    def wait(self):
        """
        Wait running process. If an error occurs raise a WorkerException,
        otherwise returns 0
        """
        ret = self.command.wait(self._handle_output)
        if ret != 0:
            error = self.get_error()
            raise WorkerException(error)
        self._finalize()
        return ret

    def cancel(self):
        """Cancel a running command"""
        self.command.cancel()

    def wait_noloop(self):
        """
        Wait (non-blocking) running process and return its exit code.
        If process has not exited yet, this method returns None otherwise,
        it returns its exit code.
        """
        ret = self.command.wait(self._handle_output, loop=False)
        if ret == 0:
            self._finalize()
        return ret
