import re
import os.path
from toolbox2.worker import Worker, WorkerException


class OmneonWorkerException(WorkerException):
    pass


class OmneonCopyWorker(Worker):
    class InputFile(Worker.InputFile):
        def get_args(self, base_dir="/"):
            path = os.path.relpath(self.path, base_dir)
            srctrack = self.params.get("srctrack", -1)
            if srctrack >= 0:
                path += ":srctrack=0"

            return ["-in", path]

    class OutputFile(Worker.OutputFile):
        def get_args(self):
            args = []
            for key, value in list(self.params.items()):
                args.append(key)
                if value != None and value != "":
                    args.append(value)
            args.append("-out")
            args.append(self.path)
            return args

    def __init__(self, log, params=None):
        Worker.__init__(self, log, params)
        self.tool = "ommcp"
        self.base_dir = "/"

    def _handle_output(self, stdout, stderr):
        Worker._handle_output(self, stdout, stderr)
        res = re.findall(r"progress=(\d+)", stdout)
        if res:
            self.progress = int(res[-1])

    def add_output_file(self, path, params=None):
        if len(self.output_files) > 0:
            raise OmneonWorkerException("Omneon copy tool only support one output file")
        Worker.add_output_file(self, path, params)

    def get_args(self):
        args = ["-replace"]

        args += Worker.get_args(self)

        for output_file in self.output_files:
            args += output_file.get_args()

        for input_file in self.input_files:
            args += input_file.get_args(self.base_dir)

        return args

    def mux_mxf(self, basepath, options=None):
        if not options:
            options = {}

        mapping = options.get("mapping", "default")
        reference = options.get("reference", False)

        if not len(self.input_files) > 0:
            raise OmneonWorkerException("No input file specified")

        if mapping == "rdd9":
            self.params.update({"-clip": "rdd9"})

        if reference:
            self.params.update({"-ref": ""})
        else:
            self.params.update({"-embedded": ""})

        path = "%s%s" % (basepath, ".mxf")
        self.add_output_file(path)

    def mux_mov(self, basepath, options=None):
        if not options:
            options = {}

        version = options.get("version", "default")
        reference = options.get("reference", False)

        if not len(self.input_files) > 0:
            raise OmneonWorkerException("No input file specified")

        if version == "qt6":
            self.params.update({"-clip": "qt6"})
        elif version == "qt7":
            self.params.update({"-clip": "qt7"})

        if reference:
            self.params.update({"-ref": ""})
        else:
            self.params.update({"-embedded": ""})

        path = "%s%s" % (basepath, ".mov")
        self.add_output_file(path)

    def mux(self, basepath, container, options=None):
        if container == "mxf":
            self.mux_mxf(basepath, options)
        elif container == "mov":
            self.mux_mov(basepath, options)
        else:
            raise OmneonWorkerException(
                "Omneon library does not support %s container" % container
            )

    def _setup(self, base_dir):
        self.base_dir = base_dir


class OmneonQueryWorker(Worker):
    def __init__(self, log, params=None):
        Worker.__init__(self, log, params)
        self.tool = "ommq"

    def add_input_file(self, path, params=None):
        if len(self.input_files) > 0:
            raise OmneonWorkerException("Omneon query tool only support one input file")
        Worker.add_input_file(self, path, params)

    def add_output_file(self, path, params=None):
        return OmneonWorkerException("Omneon query tool does output any files")

    def get_args(self):
        args = Worker.get_args(self)

        for input_file in self.input_files:
            args += input_file.get_args()

        return args

    def set_timecode(self, timecode):
        match = re.match(r"(\d{2}):(\d{2}):(\d{2})([:;])(\d{2})", timecode)
        if not match:
            raise OmneonWorkerException(
                "Timecode must be something like hh:mm:ss[:|;]ff"
            )

        matches = match.groups()
        timecode = "%s:%s:%s.%s" % (matches[0], matches[1], matches[2], matches[4])
        drop = 1 if matches[3] in [";"] else 0

        self.params.update(
            {
                "-tc": timecode,
                "-df": drop,
            }
        )
