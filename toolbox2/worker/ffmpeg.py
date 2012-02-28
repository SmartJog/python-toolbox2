# -*- coding: utf-8 -*-

import re

from toolbox2.worker import Worker, WorkerException


class FFmpegWorkerException(WorkerException):
    pass


class FFmpegWorker(Worker):

    class InputFile(Worker.InputFile):
        def __init__(self, path, params):
            Worker.InputFile.__init__(self, path, params)

        def get_args(self):
            return ['-i', self.path]

    class OutputFile(Worker.OutputFile):
        def __init__(self, path, params=None):
            Worker.OutputFile.__init__(self, path, params)
            self.params = params or {}
            if 'args' in self.params:
                self.args = self.params['args']
            else:
                self.args = []

        def get_args(self):
            return self.args + [self.path]

    def __init__(self, log, params):
        Worker.__init__(self, log, params)
        self.nb_frames = 0
        self.tool = 'ffmpeg-static'

    def _handle_output(self, stdout, stderr):
        Worker._handle_output(self, stdout, stderr)

        res = re.findall('frame=\s*(\d+)', self.stderr)
        if len(res) > 0 and self.nb_frames > 0:
            frame = float(res[-1])
            self.progress = (frame / self.nb_frames) * 100
            if self.progress > 99:
                self.progress = 99

    def set_nb_frames(self, nb_frames):
        self.nb_frames = nb_frames

    def get_args(self):
        args = []

        for input_file in self.input_files:
            args += input_file.get_args()

        args += Worker.get_args(self)

        for output_file in self.output_files:
            args += output_file.get_args()

        return args

    def make_thumbnail(self):
        self.params.update({
            '-filter:v': 'thumbnail',
            '-frames:v': 1,
        })

    def _setup(self, base_dir):
        pass
