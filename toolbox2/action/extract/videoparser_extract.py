# -*- coding: utf-8 -*-

import os
import os.path

from toolbox2.action import Action, ActionException
from toolbox2.worker.videoparser import VideoparserWorker


class VideoparserActionException(ActionException):
    pass


class VideoparserAction(Action):
    """
    Extract audio/video metadata from media files using sj videoparser.
    """

    name = 'videoparser_extract'
    engine = 'videoparser'
    category = 'extract'
    description = 'videoparser extract tool'
    required_params = {}

    def __init__(self, log, base_dir, _id, params=None, ressources=None):
        Action.__init__(self, log, base_dir, _id, params, ressources)
        self.input_file = None
        self.snapshot = None
        self.videoparser_worker = None

        if not os.path.isdir(self.tmp_dir):
            os.makedirs(self.tmp_dir)

    def _setup(self):

        self.input_file = self.get_input_ressource(1).get('path')
        self.snapshot = os.path.join(self.tmp_dir, 'snapshot.jpg')
        params = {'-travisf': None, '-S': self.snapshot}
        worker = self._new_worker(VideoparserWorker, params)
        worker.add_input_file(self.input_file)

        self.videoparser_worker = worker
        self.workers.append(worker)

    def _callback(self, worker, user_callback):
        if self.videoparser_worker == worker:
            self.update_metadata(worker.metadata)
        Action._callback(self, worker, user_callback)

    def _finalize(self):
        pass
