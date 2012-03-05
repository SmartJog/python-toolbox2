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

    def __init__(self, log, base_dir, _id, params=None, ressources=None):
        Action.__init__(self, log, base_dir, _id, params, ressources)
        self.input_file = None
        self.kttoolbox_worker = None

        if not os.path.isdir(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        if self.name not in self.params:
            self.params[self.name] = {}

        self.kttoolbox_params = self.params.get(self.name)

    def _setup(self):

        #FIXME: check if input file is a gxf container
        self.input_file = self.get_input_ressource(1).get('path')
        if self.input_file is None:
            raise KTToolboxActionException('No specified path for input (index = 1)')

        worker = KTToolboxWorker(self.log, self.kttoolbox_params)
        worker.add_input_file(self.input_file)
        worker.add_output_file(self.tmp_dir)

        self.kttoolbox_worker = worker
        self.workers.append(worker)

    def _finalize(self):
        index = 1
        for _id, path in self.kttoolbox_worker.stls.iteritems():
            output = self.kttoolbox_params.get('teletext_track_output_path_%s' % _id, None)

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

            rel_path = os.path.relpath(path, self.tmp_dir)
            self.add_output_ressource(index, {'path': path, 'rel_path': rel_path})

            # Create entry if it does not exist.
            # User of kt-toolbox extract can retrieve specific STL file using it.
            metadata = {'teletext_track_output_path_%s' % _id: path}
            self.kttoolbox_params.update(metadata)
            self.update_metadata(metadata)

            index = index + 1
