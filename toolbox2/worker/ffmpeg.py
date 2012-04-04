# -*- coding: utf-8 -*-

import re
import copy
import os.path

from toolbox2.worker import Worker, WorkerException


codec_extension_map = {
    # Video
    'mpegvideo'  : '.m1v',
    'mpeg2video' : '.m2v',
    'mpeg4video' : '.m4v',
    'dvvideo'    : '.dv',

    # Audio
    'pcm_'       : '.wav',
    'mp2'        : '.mp2',
    'mp3'        : '.mp3',
    'flac'       : '.flac',
}


class FFmpegWorkerException(WorkerException):
    pass


class FFmpegWorker(Worker):

    class InputFile(Worker.InputFile):
        def __init__(self, path, params=None, avinfo=None):
            Worker.InputFile.__init__(self, path, params)
            self.avinfo = avinfo

        def get_args(self):
            return ['-i', self.path]

    class OutputFile(Worker.OutputFile):
        def __init__(self, path, params=None, output_type='mixed'):
            Worker.OutputFile.__init__(self, path, params)
            self.params = params or {}
            self.video_opts = self.params.get('video_opts', [])
            self.audio_opts = self.params.get('audio_opts', [])
            self.format_opts = self.params.get('format_opts', [])
            self.type = output_type

        def get_args(self):
            args = []
            all_opts = self.video_opts + self.audio_opts + self.format_opts

            for option in all_opts:
                if isinstance(option, list):
                    args += option
                if isinstance(option, tuple):
                    args += list(option)
                else:
                    raise FFmpegWorkerException('FFmpeg options must be of type tuple or list')

            return args + [self.path]

    def __init__(self, log, params=None):
        Worker.__init__(self, log, params)
        self.nb_frames = 0
        self.tool = 'ffmpeg'
        self.video_opts = self.params.get('video_opts', [])
        self.audio_opts = self.params.get('audio_opts', [])
        self.format_opts = self.params.get('format_opts', [])
        self.video_filter_chain = []

    def _handle_output(self, stdout, stderr):
        Worker._handle_output(self, stdout, stderr)

        res = re.findall('frame=\s*(\d+)', self.stderr)
        if len(res) > 0 and self.nb_frames > 0:
            frame = float(res[-1])
            self.progress = (frame / self.nb_frames) * 100
            if self.progress > 99:
                self.progress = 99

    def add_input_file(self, path, params, avinfo):
        self.input_files.append(self.InputFile(path, params, avinfo))

    def add_output_file(self, path, params=None, output_type='mixed'):
        self.output_files.append(self.OutputFile(path, params, output_type))

    def set_nb_frames(self, nb_frames):
        self.nb_frames = nb_frames

    def set_timecode(self, timecode):
        self.format_opts = [opt for opt in self.format_opts if opt[0] != '-timecode']
        self.format_opts += [
            ('-timecode', timecode)
        ]

    def set_aspect_ratio(self, aspect_ratio):
        self.video_opts = [opt for opt in self.video_opts if opt[0] != '-aspect']
        self.video_opts += [
            ('-aspect', aspect_ratio)
        ]

    def get_args(self):
        args = ['-y']

        for input_file in self.input_files:
            args += input_file.get_args()

        if self.video_filter_chain:
            args += ['-vf']
            args += [','.join([flt[1] for flt in self.video_filter_chain])]

        for opts in [self.video_opts, self.audio_opts, self.format_opts]:
            for opt in opts:
                if isinstance(opt, list):
                    args += opt
                if isinstance(opt, tuple):
                    args += list(opt)
                else:
                    raise FFmpegWorkerException('FFmpeg options must be of type tuple or list')

        for output_file in self.output_files:
            args += output_file.get_args()

        return args

    def _get_codec_extension(self, codec):
        extension = ''

        for key in codec_extension_map.keys():
            if key in codec:
                extension = codec_extension_map[key]
                break

        return extension

    def make_thumbnail(self):
        self.video_opts += [
            ('-frames:v', 1),
        ]

        self.video_filter_chain += [
            ('thumbnail', 'thumbnail'),
        ]

    def get_opt(self, opt_name, opt_default=None):
        for opts in [self.video_opts, self.audio_opts, self.format_opts]:
            for opt in opts:
                if opt[0] == opt_name:
                    return opt
        return opt_default

    def get_opt_value(self, opt_name, opt_default=None):
        opt = self.get_opt(opt_name)
        if opt and len(opt) > 1:
            return opt[1]
        return opt_default

    def demux(self, basedir, channel_layout='default'):
        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        avinfo = self.input_files[0].avinfo
        basename = os.path.splitext(os.path.basename(self.input_files[0].path))[0]
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input fi1e: %s' % self.input_files[0].path)

        # Reset ouput_files
        self.output_files = []

        video_codec = self.get_opt_value('-vcodec', False)
        if video_codec == 'copy':
            video_codec = False
        audio_codec = self.get_opt_value('-acodec', False)
        if audio_codec == 'copy':
            audio_codec = False

        for stream in avinfo.video_streams:
            path = os.path.join(basedir, '%s_v%s' % (basename, stream['index']))
            extension = self._get_codec_extension(video_codec or stream['codec_name'])
            path = '%s%s' % (path, extension)

            opts = [('-vcodec', 'copy')]
            if video_codec:
                opts = copy.copy(self.video_opts)
            opts += [('-map', '0:%s' % stream['index'])]

            self.add_output_file(path, {'video_opts': opts}, 'video')

        if channel_layout == 'split':
            index = 0
            for stream in avinfo.audio_streams:
                for channel_index in range(stream['channels']):
                    path = os.path.join(basedir, '%s_a%s' % (basename, index))
                    extension = self._get_codec_extension(audio_codec or stream['codec_name'])
                    path = '%s%s' % (path, extension)

                    opts = [('-acodec', 'copy')]
                    if audio_codec:
                        opts = copy.copy(self.audio_opts)
                    opts += [('-map', '0:%s' % stream['index'])]
                    opts += [('-map_channel', '%s.%s.%s:0.%s' % (0, stream['index'], channel_index, index))]

                    self.add_output_file(path, {'audio_opts': opts}, 'audio')

                    index += 1
        elif channel_layout == 'default':
            for stream in avinfo.audio_streams:
                path = os.path.join(basedir, '%s_a%s' % (basename, stream['index']))
                extension = self._get_codec_extension(audio_codec or stream['codec_name'])
                path = '%s%s' % (path, extension)

                opts = [('-acodec', 'copy')]
                if audio_codec:
                    opts = copy.copy(self.audio_opts)
                opts += [('-map', '0:%s' % stream['index'])]

                self.add_output_file(path, {'audio_opts': opts}, 'audio')
        else:
            raise FFmpegWorkerException('Unknown channel layout: %s' % channel_layout)

        # Clean global audio/video options
        self.video_opts = []
        self.audio_opts = []

    def copy_video(self):
        self.video_opts.append(('-vcodec', 'copy'))
