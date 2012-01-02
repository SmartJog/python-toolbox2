# -*- coding: utf-8 -*-

import re

from toolbox2.worker import Worker, WorkerException


class VideoparserWorkerException(WorkerException):
    pass


class VideoparserWorker(Worker):
    """
    videoparser worker.
    """
    def __init__(self, log, params):
        Worker.__init__(self, log, params)
        self.stdout = ''
        self.stderr = ''
        self.stdout_buf = ''
        self.full_desc = False
        self.tool = 'videoparser'
        self.metadatas = {}
        self.memory_limit = 150 * 1024 * 1024

    def _handle_output(self, stdout, stderr):
        self.stdout += stdout
        self.stderr += stderr
        self.stdout_buf += stdout

        while '\n' in self.stdout_buf:
            line, self.stdout_buf = self.stdout_buf.split('\n', 1)
            res = re.findall('(\w+):\s+([^\n]+)', line)
            if not self.full_desc:
                if len(res) > 0:
                    if res[0][0] == 'full_desc':
                        self.full_desc = True
                    else:
                        self.metadatas[res[0][0]] = res[0][1]

            else:
                if len(res) > 0:
                    if res[0][0] == 'full_desc':
                        self.full_desc = False
                        self.metadatas['full_desc'] = self.metadatas['full_desc'].rstrip('\n')
                    else:
                        if 'full_desc' not in self.metadatas:
                            self.metadatas['full_desc'] = ''
                        self.metadatas['full_desc'] += '%s\n' % re.sub(', from.*', '', line)

    def get_args(self):
        args = Worker.get_args(self)

        for input_file in self.input_files:
            args += input_file.get_args()

        return args

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

    def _setup(self, base_dir):
        pass
