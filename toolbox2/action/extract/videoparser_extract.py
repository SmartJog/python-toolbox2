# -*- coding: utf-8 -*-

import os
import os.path

from toolbox2.action import Action, ActionException
from toolbox2.worker.videoparser import VideoparserWorker


class KTToolboxActionException(ActionException):
    pass


class KTToolboxAction(Action):
    """
    Extract audio/video metadata from media files using sj videoparser.
    """

    name = 'videoparser_extract'
    engine = 'videoparser'
    category = 'extract'
    description = 'videoparser extract tool'
    required_params = {}

    def __init__(self, log, base_dir, _id, params):
        Action.__init__(self, log, base_dir, _id, params)
        self.input_file = None
        self.snapshot = None
        self.videoparser_worker = None

        if not os.path.isdir(self.tmp_dir):
            os.makedirs(self.tmp_dir)

    def _check(self):
        pass

    def _setup(self):

        self.input_file = self._get_input_path(1)
        self.snapshot = os.path.join(self.tmp_dir, 'snapshot.jpg')
        params = {'-travisf': None, '-S': self.snapshot}
        worker = VideoparserWorker(self.log, params)
        worker.add_input_file(self.input_file)

        self.videoparser_worker = worker
        self.workers.append(worker)

    def _callback(self, worker, user_callback):
        if self.videoparser_worker == worker:
            self.params['infos'] = worker.metadatas
        Action._callback(self, worker, user_callback)

    def _finalize(self):
        pass
