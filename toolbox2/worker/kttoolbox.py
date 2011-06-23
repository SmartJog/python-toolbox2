# -*- coding: utf-8 -*-

import re

from toolbox2.worker import Worker, WorkerException


option_map = {
    'basename': {'-b': ''},
    'vbi_teletext_line_number': {'-gxf-lt': ''},
    'original_program_title': {'-stl-op': ''},
    'original_episode_title': {'-stl-oe': ''},
    'translated_program_title': {'-stl-tp': ''},
    'translated_episode_title': {'-stl-te': ''},
    'translator_name': {'-stl-tn': ''},
    'translator_contact_details': {'-stl-td': ''},
    'translator_country_origin': {'-stl-co': ''},
    'publisher': {'-stl-p': ''},
    'editor_name': {'-stl-en': ''},
    'editor_contact_details': {'-stl-ed': ''},
    'user_defined_area': {'-stl-ud': ''},
}


class KTToolboxWorkerException(WorkerException):
    pass


class KTToolboxWorker(Worker):
    """
    kt-toolbox worker.
    """

    class InputFile(Worker.InputFile):
        def __init__(self, path, params):
            Worker.InputFile.__init__(self, path, params)

        def get_args(self):
            return ['-i', self.path]

    class OutputFile(Worker.OutputFile):
        def __init__(self, path, params):
            Worker.OutputFile.__init__(self, path, params)

        def get_args(self):
            return ['-o', self.path]

    def __init__(self, log, params):
        Worker.__init__(self, log, params)
        self.stdout = ''
        self.stderr = ''
        self.tool = 'kt-toolbox'
        self.stls = {}

        self.args = params.get('args', [])
        self.action = params.get('action', 'VBITOSTL')
        self.options = []

        for key, value in option_map.iteritems():
            option = value.keys()[0]
            default = value.values()[0]
            option_value = params.get(key, default)
            if option_value != '':
                self.options.append(option)
                self.options.append(option_value)

    def _handle_output(self, stdout, stderr):
        self.stdout += stdout
        self.stderr += stderr

        res = re.findall('Progress: (\d+)%', self.stdout)
        if len(res) > 0:
            progress = int(res[-1])
            if progress > 99:
                progress = 99
            self.progress = progress

        res = re.findall('output-(\d+): (.*)', self.stdout)
        for output in res:
            _id = output[0]
            path = output[1]
            self.stls[_id] = path

    def get_error(self):
        lines = self.stderr.split('\n')
        error_lines = []
        lines.reverse()

        i = 0
        max_lines = 4
        for line in lines:
            if not line == '':
                i += 1
                error_lines.append(line)
            if i >= max_lines:
                break

        error_lines.reverse()
        return "\n".join(error_lines)

    def get_args(self):
        args = []

        args += [self.action]

        for input_file in self.input_files:
            args += input_file.get_args()

        for output_file in self.output_files:
            args += output_file.get_args()

        args += self.options

        return args

    def _setup(self, base_dir):
        pass
