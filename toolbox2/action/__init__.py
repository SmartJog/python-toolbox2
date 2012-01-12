# -*- coding: utf-8 -*-

import os
import time
import math
import shutil
from toolbox2.exception import Toolbox2Exception
from toolbox2.worker import WorkerException


class ActionException(Toolbox2Exception):
    pass


class Action(object):

    name = ''
    engine = ''
    category = ''
    description = ''
    required_params = {}

    def __init__(self, log, base_dir, _id, params=None, ressources=None):
        self.id = _id
        self.log = log
        self.base_dir = base_dir
        self.params = params or {}

        self.ressources = {
            'inputs': {},
            'outputs': {},
            'metadata': {}
        }

        self.ressources.update(ressources or {})

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
        for self.worker_idx, worker in enumerate(self.workers):
            self._execute_worker(worker, callback)

        self.progress = 100
        self._callback(self.workers[-1], callback)

    def _execute_worker(self, worker, callback=None):

        worker.run(self.tmp_dir)

        ret = None
        while ret is None:
            ret = worker.wait_noloop()
            # Fetch progress from worker
            self.progress = worker.progress / self.worker_count + (math.ceil(self.worker_idx) / self.worker_count) * 100
            self.progress = int(self.progress)
            self.running_time = time.time() - self.started_at
            self._callback(worker, callback)
            time.sleep(self.loop_interval)
        if ret != 0:
            raise WorkerException(worker.get_error())

    def _callback(self, worker, user_callback):
        if callable(user_callback):
            user_callback(self)

    def add_ressource(self, section, index, ressource):
        index = str(index)
        if section not in self.ressources:
            self.ressources[section] = {}
        if index in self.ressources[section]:
            raise ActionException('Ressource (section = %s) (index = %s) already exist' % (section, index))
        self.ressources[section][index] = ressource

    def get_ressource(self, section, index):
        index = str(index)
        if section not in self.ressources:
            raise ActionException('Section %s does not exist' % section)
        if index not in self.ressources[section]:
            raise ActionException('Ressource (section = %s) (index = %s) does not exist' % (section, index))
        return self.ressources[section][index]

    def add_input_ressource(self, index, ressource):
        return self.add_ressource('inputs', index, ressource)

    def get_input_ressource(self, index):
        return self.get_ressource('inputs', index)

    def add_output_ressource(self, index, ressource):
        return self.add_ressource('outputs', index, ressource)

    def get_output_ressource(self, index):
        return self.get_ressource('outputs', index)

    def get_input_ressources(self):
        return self.ressources['inputs']

    def get_output_ressources(self):
        return self.ressources['outputs']

    def get_metadata(self):
        return self.ressources['metadata']

    def add_metadata(self, key, value):
        self.ressources['metadata'][key] = value

    def update_metadata(self, metadata):
        self.ressources['metadata'].update(metadata)

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
        Run action by calling _setup and _execute methods. If an error
        occured raise an ActionException.
        """
        self.started_at = time.time()

        try:
            self._setup()
            self._execute(callback)
            self._finalize()
        except WorkerException, exc:
            self.log.exception('An error occurred')
            raise ActionException(exc)
        finally:
            self.ended_at = time.time()
