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
        self.kttoolbox_worker = None

        if not os.path.isdir(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        self.kttoolbox_params = self.params.get(self.name, {})

    def _check(self):
        """
        #FIXME: Check if input file is a gxf container
        """
        pass

    def _setup(self):

        self.input_file = self._get_input_path(1)

        worker = KTToolboxWorker(self.log, self.kttoolbox_params)
        worker.add_input_file(self.input_file)
        worker.add_output_file(self.tmp_dir)

        self.kttoolbox_worker = worker
        self.workers.append(worker)

    def _finalize(self):
        index = 1
        for _id, path in self.kttoolbox_worker.stls.iteritems():
            output = self.kttoolbox_params.get('track_%s_path' % _id, None)

            if output:
                dest = os.path.realpath(self.tmp_dir + '/' + output)
                basedir = os.path.dirname(dest)

                # Silent here if output directory is self.tmp_dir
                try:
                    os.makedirs(basedir)
                except OSError:
                    pass

                os.rename(path, dest)
                path = dest

            self._add_infos('%s-track_%s_path' % (self.name, _id), path)

            self._add_output_path(index, path)
            index = index + 1
