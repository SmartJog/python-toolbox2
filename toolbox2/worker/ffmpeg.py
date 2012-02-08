# -*- coding: utf-8 -*-

import re

from toolbox2.worker import Worker, WorkerException


class FFMpegWorkerException(WorkerException):
    pass


class FFMpegWorker(Worker):

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
        self.nbframes = 0
        self.tool = 'ffmpeg'
        self.args = params.get('args', [])

    def add_input_file(self, path, params=None):
        Worker.add_input_file(self, path, params)
        if 'nbframes' in params:
            if params['nbframes'] > self.nbframes:
                self.nbframes = params['nbframes']
            del params['nbframes']

    def _handle_output(self, stdout, stderr):
        self.stdout += stdout
        self.stderr += stderr

        res = re.findall('frame=\s*(\d+)', self.stderr)
        if len(res) > 0 and self.nbframes > 0:
            frame = float(res[-1])
            self.progress = (frame / self.nbframes) * 100
            if self.progress > 99:
                self.progress = 99

    def get_args(self):
        args = []

        for input_file in self.input_files:
            args += input_file.get_args()

        for output_file in self.output_files:
            args += output_file.get_args()

        args += self.args

        return args

    def _setup(self, base_dir):
        pass
