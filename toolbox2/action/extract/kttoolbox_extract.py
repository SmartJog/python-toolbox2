# -*- coding: utf-8 -*-

import os

from toolbox2.action import Action, ActionException
from toolbox2.worker.kttoolbox import KTToolboxWorker


class KTToolboxActionException(ActionException):
    pass


class KTToolboxAction(Action):
    """
    Extract subtitles from a gxf file using kt-toolbox from Keres Technologies.
    """

    name = 'kttoolbox_extract'
    engine = 'kt-toolbox'
    category = 'extract'
    description = 'kt-toolbox extract tool'
    required_params = {}

    def __init__(self, log, base_dir, _id, params):
        Action.__init__(self, log, base_dir, _id, params)
        self.input_file = None
        self.output_file = None
        self.tmp_output_dir = os.path.join(self.tmp_dir, 'extract')
        self.output_dir = None

        if not os.path.isdir(self.tmp_output_dir):
            os.makedirs(self.tmp_output_dir)

        self.kttoolbox_params = self.params.get('kttoolbox', {})

    def _check(self):
        """
        #FIXME: Check if input file is a gxf container
        """
        pass

    def _setup(self):

        self.input_file = self._get_input_path(1)
        self.output_dir = os.path.dirname(self.input_file)

        worker = KTToolboxWorker(self.log, self.kttoolbox_params)
        worker.add_input_file(self.input_file)
        worker.add_output_file(self.tmp_output_dir)
        self.workers.append(worker)

    def _finalize(self):
        index = 1
        for path, _, files in os.walk(self.tmp_output_dir):
            for filename in files:
                self._add_output_tmp_path(index, os.path.join(path, filename))
                self._add_output_path(index, os.path.join(self.output_dir, filename))
                index += 1
