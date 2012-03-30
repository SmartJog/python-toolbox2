# -*- coding: utf-8 -*-

import re
import json

from toolbox2.worker import Worker, WorkerException


class FFprobeWorkerException(WorkerException):
    pass


class FFprobeWorker(Worker):
    """
    FFprobe worker.
    """
    def __init__(self, log, params=None):
        Worker.__init__(self, log, params)
        self.tool = 'ffprobe-static'
        self.metadata = {}
        self.params.update({
            '-print_format': 'json',
            '-show_format': None,
            '-show_streams': None,
        })

    def count_frames(self):
        self.params.update({
            '-count_frames': None,
        })

    def count_packets(self):
        self.params.update({
            '-count_packets': None,
        })

    def get_args(self):
        args = Worker.get_args(self)

        for input_file in self.input_files:
            args += input_file.get_args()

        return args

    def _finalize(self):
        try:
            self.metadata = json.loads(self.stdout)
        except ValueError, exc:
            raise FFprobeWorkerException('FFProbe output could not be decoded: %s, %s' % (exc, self.stdout))

        nb_audio_streams = 0
        nb_video_streams = 0
        for stream in self.metadata['streams']:
            if stream['codec_type'] == 'video':
                nb_video_streams = nb_video_streams + 1
            elif stream['codec_type'] == 'audio':
                nb_audio_streams = nb_audio_streams + 1

        self.metadata['format']['nb_audio_streams'] = nb_audio_streams
        self.metadata['format']['nb_video_streams'] = nb_video_streams
        self.metadata['description'] = self._get_description()

    def _get_description(self):
        desc = ''
        lines = self.stderr.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('Input') or line.startswith('Duration') or line.startswith('Stream'):
                if line.startswith('Input'):
                    line = re.sub(', from.*', '', line)
                desc += line + '\n'
        return desc.strip()
