import os
import time
import math
import shutil
import configparser
from configparser import SafeConfigParser
from toolbox2.exception import Toolbox2Exception
from toolbox2.worker import WorkerException


TOOLBOX2_CONFIG_FILE = "/etc/toolbox2.conf"


class ActionException(Toolbox2Exception):
    pass


class Action(object):

    name = ""
    engine = ""
    category = ""
    description = ""
    required_params = {}

    def __init__(self, log, base_dir, _id=None, params=None, resources=None):
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

        :param resources: action input/output/metadata resources
        :type resssources: dict
        """
        self.id = _id
        self.log = log
        self.base_dir = base_dir
        self.params = params or {}

        self._cancel = False

        self.resources = {"inputs": {}, "outputs": {}, "metadata": {}}

        self.resources.update(resources or {})

        self.workers = []
        self.worker_idx = 0

        self.progress = 0
        self.running_time = 0

        self.started_at = 0
        self.ended_at = 0

        try:
            self.conf = None
            with open(TOOLBOX2_CONFIG_FILE, "r") as fp:
                self.conf = SafeConfigParser()
                self.conf.readfp(fp)
        except (Exception, IOError) as exc:
            self.log.warning("%s", exc)

        if self.id:
            self.tmp_dir = os.path.join(self.base_dir, "job-%s" % self.id)
        else:
            self.tmp_dir = self.base_dir
        self.debug = self.params.get("debug", False)
        self.last_callback = time.time()
        self.callback_interval = self.params.get("callback_interval", 1)

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
        for self.worker_idx, _ in enumerate(self.workers):
            if self._cancel:
                break  # no need to run other workers
            self._execute_current_worker(callback)

        if not self._cancel:
            self.progress = 100
        self._callback(callback)

    def _execute_current_worker(self, callback=None):
        """
        Execute current worker designed by worker_idx, update progress,
        and launch callback.

        :param worker: worker to execute
        :type worker: toolbox2.worker.Worker

        :param callback: user defined callback called every loop interval.
        :type calback: callable(action)
        """
        worker = self.workers[self.worker_idx]
        worker.run(self.tmp_dir)

        ret = None
        while ret is None and not self._cancel:
            ret = worker.wait_noloop()
            self._update_progress()
            self.running_time = time.time() - self.started_at
            if (time.time() - self.last_callback) > self.callback_interval:
                self.last_callback = time.time()
                self._callback(callback)

        if ret is None and self._cancel:
            self.log.info("Killing the running worker...")
            worker.cancel()
        elif ret != 0:
            raise WorkerException(worker.get_error())
        else:
            worker.progress = 100
        self._update_progress()
        self._callback(callback)

    def _update_progress(self):
        """
        Update action progress.

        :param worker: current worker being executed
        :type worker: toolbox2.worker.Worker
        """
        worker = self.workers[self.worker_idx]
        self.progress = int(
            (worker.progress + 100 * self.worker_idx) / len(self.workers)
        )

    def _callback(self, user_callback):
        """
        Execute user defined callback.
        Overload this method is you want to update action metadata
        with current worker metadata for example.

        :param user_callback: user defined callback to execute
        :type user_callback: callable(action)
        """
        if callable(user_callback):
            user_callback(self)

    def _new_worker(self, worker_class, *args, **kwargs):
        """
        Return a worker instance of a given class. If configuration specifies
        a custom worker tool path, created instance will use it.
        """
        worker = worker_class(self.log, *args, **kwargs)
        try:
            if self.conf:
                path = self.conf.get("tools", worker.tool)
                worker.tool = path
        except (configparser.NoSectionError, configparser.NoOptionError) as exc:
            self.log.warning("%s", exc)

        return worker

    def add_resource(self, section, index, resource):
        """
        Add a resource to specified section and index.
        An ActionException is raised if a resource already exists at specified section and index.

        :param section: resource section. For example inputs, outputs, metadata.
        :type section: string

        :param index: resource identifier. Most actions use index=1 to get the first input resource.
        :param type: string or int

        :param resource: resource represented as a dict. For example, files minimum representation is {'path': '/path'}
        :type resource: dict

        :raise: ActionException
        """
        index = str(index)
        if section not in self.resources:
            self.resources[section] = {}
        if index in self.resources[section]:
            raise ActionException(
                "Ressource (section = %s) (index = %s) already exist" % (section, index)
            )
        self.resources[section][index] = resource

    def get_resource(self, section, index):
        """
        Get a resource from specified section and index.
        If resource does not exist raise an ActionException.

        :param section: resource section. For example inputs, outputs, metadata.
        :type section: string

        :param index: unique indentifier for resource. Most action use index=1 for the first input resource.
        :param type: string or int

        :return: resource
        :rtype: dict
        """
        index = str(index)
        if section not in self.resources:
            raise ActionException("Section %s does not exist" % section)
        if index not in self.resources[section]:
            raise ActionException(
                "Ressource (section = %s) (index = %s) does not exist"
                % (section, index)
            )
        return self.resources[section][index]

    def add_input_resource(self, index, resource):
        """
        Add an input resource to specified index.
        An ActionException is raised if a resource already exists at specified index.

        :param index: resource identifier. Most actions use index=1 to get the first input resource.
        :param type: string or int

        :param resource: resource represented as a dict. For example, files minimum representation is {'path': '/path'}
        :type resource: dict

        :raise: ActionException
        """

        return self.add_resource("inputs", index, resource)

    def get_input_resource(self, index):
        """
        Get an input resource from specified index.
        If resource does not exist raise an ActionException.

        :param section: resource section. For example inputs, outputs, metadata.
        :type section: string

        :param index: unique indentifier for resource. Most action use index=1 for the first input resource.
        :param type: string or int

        :return: resource
        :rtype: dict
        """

        return self.get_resource("inputs", index)

    def add_output_resource(self, index, resource):
        """
        Add an output resource to specified index.
        An ActionException is raised if a resource already exists at specified index.

        :param index: resource identifier. Most actions use index=1 to get the first input resource.
        :param type: string or int

        :param resource: resource represented as a dict. For example, files minimum representation is {'path': '/path'}
        :type resource: dict

        :raise: ActionException
        """

        return self.add_resource("outputs", index, resource)

    def get_output_resource(self, index):
        """
        Get an output resource from specified index.
        If resource does not exist raise an ActionException

        :param index: unique indentifier for resource. Most action use index=1 for the first input resource.
        :param type: string or int

        :return: resource
        :rtype: dict
        """
        return self.get_resource("outputs", index)

    def get_input_resources(self):
        """
        Get all input resources.

        :return resources
        :rtype: dict
        """
        return self.resources["inputs"]

    def get_output_resources(self):
        """
        Get all output resources.

        :return resources
        :rtype dict
        """
        return self.resources["outputs"]

    def get_metadata(self):
        """
        Return action metadata.
        """
        return self.resources["metadata"]

    def add_metadata(self, key, value):
        """
        Add key/value to metadata.
        """
        self.resources["metadata"][key] = value

    def update_metadata(self, metadata):
        """
        Update metadata.
        """
        self.resources["metadata"].update(metadata)

    def clean(self):
        """
        Clean action working directory. This method must be called manually by user.
        """
        if self.debug:
            return
        try:
            shutil.rmtree(self.tmp_dir)
        except OSError:
            self.log.exception("An error occured")

    def cancel(self):
        """Cancel/abort the running action"""
        self._cancel = True

    def run(self, callback=None):
        """
        Run action by calling _setup,_execute and _finalize methods. If an error
        occurs, it raises an ActionException. User defined callback is executed every
        callback_interval. callback should be a callable and must accept one parameter.

        :param callback: user defined callable function
        :type callback: callable(action)
        """
        self.started_at = time.time()

        try:
            self._setup()
            self._execute(callback)
            self._finalize()
        except WorkerException as exc:
            self.log.exception("An error occurred")
            raise ActionException(exc)
        finally:
            self.ended_at = time.time()
