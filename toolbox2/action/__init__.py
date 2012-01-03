# -*- coding: utf-8 -*-

import os
import time
import math
import shutil
from toolbox2.worker import WorkerException


class ActionException(Exception):
    pass


class Action(object):

    name = ''
    engine = ''
    category = ''
    description = ''
    required_params = {}

    def __init__(self, log, base_dir, _id, params):
        self.id = _id
        self.log = log
        self.base_dir = base_dir
        self.params = params

        if not isinstance(params, dict):
            raise ActionException('Action params must an instance of dict: %s given' % type(params))

        self.workers = []
        self.worker_idx = 0
        self.worker_count = 1

        self.progress = 0
        self.running_time = 0

        self.started_at = 0
        self.ended_at = 0

        self.tmp_dir = os.path.join(self.base_dir, 'job-%s' % self.id)
        self.debug = params.get('debug', False)
        self.loop_interval = params.get('loop_interval', 1)

        if not os.path.isdir(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        if 'out' not in self.params:
            self.params['out'] = {}

        if 'path' not in self.params:
            self.params['out']['path'] = {}

        if 'infos' not in self.params:
            self.params['infos'] = {}

    def _check(self):
        """
        Check action parameters.
        """
        raise NotImplementedError

    def _setup(self):
        """
        Setup all workers you have to execute.
        """
        raise NotImplementedError

    def _finalize(self):
        """
        Run some code after successful action execution.
        """
        raise NotImplementedError

    def _execute(self, callback=None):
        """
        Process all workers defined in workers list attribute and update progress.
        Override this method if you want to control action's inputs/outputs at
        runtime.
        """
        self.worker_count = len(self.workers)
        for self.worker_idx, action in enumerate(self.workers):
            self._execute_worker(action, callback)

        self.progress = 100
        self._callback(self.workers[-1], callback)

    def _execute_worker(self, action, callback=None):

        action.run(self.tmp_dir)

        ret = None
        while ret is None:
            ret = action.wait_noloop()
            # Fetch progress from action
            self.progress = action.progress / self.worker_count + (math.ceil(self.worker_idx) / self.worker_count) * 100
            self.progress = int(self.progress)
            self.running_time = time.time() - self.started_at
            self._callback(action, callback)
            time.sleep(self.loop_interval)
        if ret != 0:
            raise WorkerException(action.get_error())

    def _callback(self, worker, user_callback):
        if callable(user_callback):
            user_callback(self.progress)

    def _get_input_path(self, index):
        index = str(index)
        try:
            path = self.params['in']['path'][index]
        except TypeError, exc:
            raise ActionException('Missing input path at index %s: %s' % (index, exc))
        return path

    def _add_output_path(self, index, path):
        index = str(index)
        self.params['out']['path'][index] = path

    def _get_output_extension(self, index):
        index = str(index)
        if not 'ext' in self.params['out']:
            return False
        if not index in self.params['out']['ext']:
            return False

        return self.params['out']['ext'][index]

    def _get_output_path(self, index, relative=False):
        index = str(index)
        try:
            path = self.params['out']['path'][index]
            if relative:
                path = path.replace(self.tmp_dir, '')
        except TypeError, exc:
            raise ActionException('Missing output path at index %s: %s' % (index, exc))
        return path

    def get_output_paths(self):
        return self.params['out']['path']

    def get_tmp_dir(self):
        return self.tmp_dir

    def _add_infos(self, key, value):
        self.params['infos'][key] = value

    def get_infos(self):
        return self.params['infos']

    def clean(self):
        """
        Clean action working directory. This method must be called manually by user.
        """
        if self.debug:
            return
        try:
            shutil.rmtree(self.tmp_dir)
        except OSError:
            self.log.exception('An error occured')

    def run(self, callback=None):
        """
        Run action by calling _check, _setup and _execute methods. If an error
        occured raise an ActionException.
        """
        self.started_at = time.time()

        try:
            self._check()
            self._setup()
            self._execute(callback)
            self._finalize()
        except WorkerException, exc:
            self.log.exception('An error occurred')
            raise ActionException(exc)
        finally:
            self.ended_at = time.time()
