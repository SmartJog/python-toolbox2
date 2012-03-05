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
        """
        Create a new action.
        base_dir and _id are used to create a unique temporary directory to work in.

        :param log: logger instance to use
        :type log: logging.Logger

        :param base_dir: working base directory
        :type base_dir: string

        :param _id: a unique identifier
        :type _id: string

        :param params: action parameters
        :type params: dict

        :param ressources: action input/output/metadata ressources
        :type resssources: dict
        """
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
        self.debug = self.params.get('debug', False)
        self.loop_interval = self.params.get('loop_interval', 1)

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
        Override this method if you want to control workers' inputs/outputs at
        runtime.

        :param callback: user defined callback called every loop interval.
        :type calback: callable(action)
        """
        self.worker_count = len(self.workers)
        for self.worker_idx, worker in enumerate(self.workers):
            self._execute_worker(worker, callback)

        self.progress = 100
        self._callback(self.workers[-1], callback)

    def _execute_worker(self, worker, callback=None):
        """
        Execute a worker, update progress, and launch callback.

        :param worker: worker to execute
        :type worker: toolbox2.worker.Worker

        :param callback: user defined callback called every loop interval.
        :type calback: callable(action)
        """
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
            if ret is None:
                time.sleep(self.loop_interval)
        if ret != 0:
            raise WorkerException(worker.get_error())

    def _callback(self, worker, user_callback):
        """
        Execute user defined callback.
        Overload this method is you want to update action metadata
        with current worker metadata for example.

        :param worker: current worker being executed
        :type worker: toolbox2.worker.Worker

        :param user_callback: user defined callback to execute
        :type user_callback: callable(action)
        """
        if callable(user_callback):
            user_callback(self)

    def add_ressource(self, section, index, ressource):
        """
        Add a ressource to specified section and index.
        An ActionException is raised if a ressource already exists at specified section and index.

        :param section: ressource section. For example inputs, outputs, metadata.
        :type section: string

        :param index: ressource identifier. Most actions use index=1 to get the first input ressource.
        :param type: string or int

        :param ressource: ressource represented as a dict. For example, files minimum representation is {'path': '/path'}
        :type ressource: dict

        :raise: AnctionException
        """
        index = str(index)
        if section not in self.ressources:
            self.ressources[section] = {}
        if index in self.ressources[section]:
            raise ActionException('Ressource (section = %s) (index = %s) already exist' % (section, index))
        self.ressources[section][index] = ressource

    def get_ressource(self, section, index):
        """
        Get a ressource from specified section and index.
        If ressource does not exist raise an ActionException.

        :param section: ressource section. For example inputs, outputs, metadata.
        :type section: string

        :param index: unique indentifier for ressource. Most action use index=1 for the first input ressource.
        :param type: string or int

        :return: ressource
        :rtype: dict
        """
        index = str(index)
        if section not in self.ressources:
            raise ActionException('Section %s does not exist' % section)
        if index not in self.ressources[section]:
            raise ActionException('Ressource (section = %s) (index = %s) does not exist' % (section, index))
        return self.ressources[section][index]

    def add_input_ressource(self, index, ressource):
        """
        Add an input ressource to specified index.
        An ActionException is raised if a ressource already exists at specified index.

        :param index: ressource identifier. Most actions use index=1 to get the first input ressource.
        :param type: string or int

        :param ressource: ressource represented as a dict. For example, files minimum representation is {'path': '/path'}
        :type ressource: dict

        :raise: AnctionException
        """

        return self.add_ressource('inputs', index, ressource)

    def get_input_ressource(self, index):
        """
        Get an input ressource from specified index.
        If ressource does not exist raise an ActionException.

        :param section: ressource section. For example inputs, outputs, metadata.
        :type section: string

        :param index: unique indentifier for ressource. Most action use index=1 for the first input ressource.
        :param type: string or int

        :return: ressource
        :rtype: dict
        """

        return self.get_ressource('inputs', index)

    def add_output_ressource(self, index, ressource):
        """
        Add an output ressource to specified index.
        An ActionException is raised if a ressource already exists at specified index.

        :param index: ressource identifier. Most actions use index=1 to get the first input ressource.
        :param type: string or int

        :param ressource: ressource represented as a dict. For example, files minimum representation is {'path': '/path'}
        :type ressource: dict

        :raise: AnctionException
        """

        return self.add_ressource('outputs', index, ressource)

    def get_output_ressource(self, index):
        """
        Get an output ressource from specified index.
        If ressource does not exist raise an ActionException

        :param index: unique indentifier for ressource. Most action use index=1 for the first input ressource.
        :param type: string or int

        :return: ressource
        :rtype: dict
        """
        return self.get_ressource('outputs', index)

    def get_input_ressources(self):
        """
        Get all input ressources.

        :return ressources
        :rtype: dict
        """
        return self.ressources['inputs']

    def get_output_ressources(self):
        """
        Get all output ressources.

        :return ressources
        :rtype dict
        """
        return self.ressources['outputs']

    def get_metadata(self):
        """
        Return action metadata.
        """
        return self.ressources['metadata']

    def add_metadata(self, key, value):
        """
        Add key/value to metadata.
        """
        self.ressources['metadata'][key] = value

    def update_metadata(self, metadata):
        """
        Update metadata.
        """
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
        Run action by calling _setup,_execute and _finalize methods. If an error
        occurs, it raises an ActionException. User defined callback is executed every
        loop_interval. callback should be a callable and must accept one parameter.

        :param callback: user defined callable function
        :type callback: callable(action)
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
