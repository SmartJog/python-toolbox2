# -*- coding: utf-8 -*-

import re

from toolbox2.action import Action, ActionException
from toolbox2.worker.ffprobe import FFprobeWorker
from toolbox2.worker.ffmpeg import FFmpegWorker


class GetCapabilityActionException(ActionException):
    pass


class GetCapabilityAction(Action):
    """Get availability of command line options"""

    name = 'getcapability'
    engine = ['ffmpeg', 'ffprobe']
    category = 'getcapability'
    description = 'get availability of command line options'
    required_params = {}

    def __init__(self, log, basedir, id_, params=None, resources=None):
        # We don't need a basedir or an id for this action...
        Action.__init__(self, log, '.', None, params, resources)
        self.worker = None
        self.log = log

        self.tool = self.params.get('tool')
        if self.tool is None:
            raise GetCapabilityActionException('required parameter: tool')
        self.option = self.params.get('option')
        if self.option is None:
            raise GetCapabilityActionException('required parameter: option')
        self.regex = self.params.get('regex', False)
        self.success = False

    def _setup(self):
        pass

    def _execute(self, callback=None):
        if self.tool == 'ffmpeg':
            self.extract_help(callback)
        elif self.tool == 'ffprobe':
            self.extract_help(callback)
        else:
            raise GetCapabilityActionException(
                'getcapability does not support %s' % self.tool
            )

    def _finalize(self):
        pass

    def extract_help(self, callback=None):
        if self.tool == 'ffmpeg':
            worker = self._new_worker(FFmpegWorker)
        elif self.tool == 'ffprobe':
            worker = self._new_worker(FFprobeWorker)
        else:
            raise GetCapabilityActionException(
                'getcapability via help extraction is not supported for %s'
                % self.tool
            )
        worker.make_fullhelp()

        self.workers.append(worker)
        self.worker_idx = 0
        self._execute_current_worker(callback)

        lines = worker.stdout.split('\n')
        for line in lines:
            if self.regex:
                if re.search(self.option, line):
                    self.success = True
            else:
                availableoption = line.strip().partition(' ')
                if '-'+self.option == availableoption[0]:
                    self.success = True
        self.add_metadata('available', self.success)

        self.progress = 100
        self._callback(callback)

    def run(self, callback=None):
        Action.run(self, callback)
        return self.success
