import os
import copy
from toolbox2.worker import Worker, WorkerException

default_params = {}
default_params["transport"] = {
    "FileSize": "0",
    "Rate": "0",
    "Duration": "0",
    "Leader": "0",
    "PSIPATrep": "10.000",
    "PSIPMTrep": "10.000",
    "PATtsid": "0",
    "PATvsn": "0",
    "DIT": "No",
    "DITTransition": "0",
    "SIT": "No",
    "SITPeriod": "0",
    "SITVersion": "0",
    "SITTransDescr": None,
    "SITServiceID": 2,
    "SITRunningStatus": 0,
    "SITSvcDescr": None,
    "NoEmptyAF": "No",
    "HDVModeHD2": "No",
    "AUXVPID": None,
    "AUXAPID": None,
    "HDVDropFrame": "No",
}

default_params["program"] = {
    "ProgramNumber": 2,
    "PMTPID": 32,
    "PMTvsn": 0,
    "Descriptors": None,
    "PCRPID": -1,
    "PCRPES": "No",
}

default_params["video"] = {
    "Rate": 0,
    "QuadByte": "No",
    "StreamType": 0,
    "Descriptors": None,
    "PID": 33,
    "InitDI": "No",
    "RAI": "No",
    "PESalign": "No",
    "PEScopyrt": "No",
    "PESid": 0,
    "PESnau": 1,
    "StreamDelay": 0,
    "Delay": 0,
}

default_params["audio"] = {
    "StreamType": 0,
    "Descriptors": None,
    "PID": 36,
    "InitDI": "No",
    "RAI": "No",
    "PESalign": "No",
    "PEScopyrt": "No",
    "PESid": 0,
    "PESnau": 2,
    "StreamDelay": 0,
    "Delay": 0,
    "SkipFrames": 0,
}


def get_default_params(section):
    return copy.copy(default_params[section])


class ManzanitaException(WorkerException):
    pass


class ManzanitaWorker(Worker):
    def __init__(self, log, params):
        Worker.__init__(self, log, params)
        self.tool = "mp2tsms"
        self.error_lines = 4


class ManzanitaDemuxWorker(ManzanitaWorker):
    class InputFile(ManzanitaWorker.InputFile):
        def __init__(self, path, params=None):
            ManzanitaWorker.InputFile.__init__(self, path, params)

        def get_args(self):
            return ["-dd", self.path]

    class OutputFile(ManzanitaWorker.OutputFile):
        def __init__(self, path, params):
            ManzanitaWorker.OutputFile.__init__(self, path)
            if not "stream_id" in params:
                raise TypeError
            self.stream_id = params["stream_id"]
            self.params = params or []

        def get_args(self):
            return [self.stream_id, self.path]

    def __init__(self, log, params=None):
        ManzanitaWorker.__init__(self, log, params)

    def get_args(self):
        args = []
        for input_file in self.input_files:
            args += input_file.get_args()
        for output_file in self.output_files:
            args += output_file.get_args()
        return args


class ManzanitaMuxWorker(ManzanitaWorker):
    class InputFile(ManzanitaWorker.InputFile):
        def __init__(self, path, params=None):
            ManzanitaWorker.InputFile.__init__(self, path, params)

            self.type = params.get("type", "")
            if self.type not in ["audio", "video"]:
                raise TypeError("Input file type not specified")

            del params["type"]

            self.params = get_default_params(self.type)

            for key, value in list(params.items()):
                if key in self.params:
                    if self.params[key] is None and (value == "" or value == "None"):
                        pass
                    else:
                        self.params[key] = value

    class OutputFile(ManzanitaWorker.OutputFile):
        def __init__(self, path, params=None):
            ManzanitaWorker.OutputFile.__init__(self, path, params)

    def __init__(self, log, params):
        ManzanitaWorker.__init__(self, log, params)

        self.config_file = None

        self.manzanita_params = {}
        self.manzanita_params["program"] = get_default_params("program")
        self.manzanita_params["transport"] = get_default_params("transport")
        self.manzanita_params["video"] = {}
        self.manzanita_params["audio"] = {}

        for section in ["program", "transport", "video", "audio"]:
            section_params = params.get(section, {})
            for key, value in list(section_params.items()):
                if key in self.manzanita_params[section]:
                    if self.manzanita_params[section][key] is None and (
                        value == "" or value == "None"
                    ):
                        pass
                    else:
                        self.manzanita_params[section][key] = value

    def _setup(self, base_dir):

        self.config_file = os.path.join(base_dir, "manzanita.conf")
        with open(self.config_file, "w") as fileobj:

            fileobj.write("Transport*\n")
            fileobj.write("File = %s\n" % self.output_files[0].path)
            for key, value in list(self.manzanita_params["transport"].items()):
                if not value is None:
                    fileobj.write("%s = %s\n" % (key, value))

            fileobj.write("\n\n")

            fileobj.write("Program1*\n")
            for key, value in list(self.manzanita_params["program"].items()):
                if not value is None:
                    fileobj.write("%s = %s\n" % (key, value))

            fileobj.write("\n\n")

            stream_video_count = 0
            stream_audio_count = 0
            for stream in self.input_files:

                if stream.type == "video":
                    stream_video_count += 1
                    fileobj.write("Video%s$\n" % (stream_video_count))
                    fileobj.write("File = %s\n" % stream.path)
                    stream.params.update(self.manzanita_params["video"])
                    for key, value in list(stream.params.items()):
                        if not value is None:
                            fileobj.write("%s = %s\n" % (key, value))

                elif stream.type == "audio":
                    stream_audio_count += 1
                    fileobj.write("Audio%s$\n" % (stream_audio_count))
                    fileobj.write("File = %s\n" % stream.path)
                    stream.params.update(self.manzanita_params["audio"])
                    for key, value in list(stream.params.items()):
                        if not value is None:
                            fileobj.write("%s = %s\n" % (key, value))
                fileobj.write("\n\n")

    def get_args(self):
        return [self.config_file]
