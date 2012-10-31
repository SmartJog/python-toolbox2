# -*- coding: utf-8 -*-

import re
import os
import os.path
from toolbox2.worker import Worker, WorkerException


class Raw2BmxWorkerException(WorkerException):
    pass


class Raw2BmxWorker(Worker):

    class InputFile(Worker.InputFile):
        def get_args(self):
            opts = []
            codec = self.params.get('codec')
            if codec == 'dnxhd':
                opts += ['--vc3']
            elif codec == 'dvvideo':
                opts += ['--dv']
            elif codec == 'imx':
                opts += ['--d10']
            elif codec == 'xdcamhd':
                opts += ['--mpeg2lg']
            elif codec == 'pcm':
                opts += ['--wave']
            else:
                raise Raw2BmxWorkerException('BMX worker does not support the %s codec yet' % codec)

            opts += [self.path]
            return opts

    class OutputFile(Worker.OutputFile):
        def get_args(self):
            args = ['-o', self.path]
            return args

    def __init__(self, log, params=None):
        Worker.__init__(self, log, params)
        self.tool = 'raw2bmx'

    def add_output_file(self, path, params=None):
        if len(self.output_files) > 0:
            raise Raw2BmxWorkerException('BMX tool only support one output file')
        Worker.add_output_file(self, path, params)

    def get_args(self):
        args = []
        args += Worker.get_args(self)

        for output_file in self.output_files:
            args += output_file.get_args()

        for input_file in self.input_files:
            args += input_file.get_args()

        return args

    def set_timecode(self, timecode):
        match = re.match('(\d{2}):(\d{2}):(\d{2})([:;])(\d{2})', timecode)
        if not match:
            raise Raw2BmxWorkerException('Timecode must be something like hh:mm:ss[:|;]ff')

        self.params.update({'-y': timecode})

    def mux(self, basepath, options=None):
        if not options:
            options = {}
        mapping = options.get('mapping', 'op1a')
        if mapping == 'default' or mapping == 'rdd9':
            mapping = 'op1a'
        self.params.update({'-t': mapping})

        if not len(self.input_files) > 0:
            raise Raw2BmxWorkerException('No input file specified')

        path = '%s%s' % (basepath, '.mxf')
        self.add_output_file(path)
