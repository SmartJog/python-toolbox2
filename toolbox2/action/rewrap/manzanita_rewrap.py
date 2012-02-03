# -*- coding: utf-8 -*-

import os
import sys

import sjfs

from toolbox2.action import Action, ActionException
from toolbox2.worker.manzanita import ManzanitaMuxWorker
from toolbox2.worker.ffmpeg import FFmpegWorker

sys.path.append('/usr/share/libtoolbox')
import mediaparser


class ManzanitaRewrapException(ActionException):
    pass


class ManzanitaRewrapAction(Action):

    name = 'manzanita_rewrap'
    engine = 'manzanita'
    category = 'rewrap'
    description = 'Manzanita rewrap tool'
    required_params = {}

    def __init__(self, log, base_dir, _id, params, ressources):
        Action.__init__(self, log, base_dir, _id, params, ressources)
        self.input_file = None
        self.output_file = None

    def _setup(self):

        # FIXME: more customization needed for output paths
        # Set input_file
        self.input_file = self.get_input_ressource(1).get('path')
        if not self.input_file:
            raise ManzanitaRewrapException('No path specified for input (index = 1)')

        # Compute tmp output path
        filename = os.path.basename(self.input_file)
        filename, _ = os.path.splitext(filename)
        if self.get_output_ressource(1):
            extension = self.get_output_ressource(1).get('extension')
        if not extension:
            extension = '.ts'
        output_filename = '%s%s' % (filename, extension)

        self.output_file = os.path.join(self.tmp_dir, output_filename)
        self.add_output_ressource(1, {'path': self.output_file})

        stream_count = 0
        video_streams = []
        audio_streams = []

        # Parse video/audio streams
        streams = mediaparser.streams(self.input_file)

        for stream in streams['video']:
            stream_count += 1
            path = os.path.join(self.tmp_dir, 'stream_%s' % stream_count)
            if stream['codec'] == 'mpeg1video':
                path += '.m1v'
            elif stream['codec'] == 'mpeg2video':
                path += '.m2v'
            else:
                raise ManzanitaRewrapException('Unsuported video codec: %s' % stream['codec'])

            video_streams.append({'path': path, 'infos': stream})

        for stream in streams['audio']:
            stream_count += 1
            path = os.path.join(self.tmp_dir, 'stream_%s' % stream_count)
            args = ['-y']
            args += ['-ar', stream['samplerate'], '-ac', stream['channels']]
            args += ['-acodec', 'copy']
            if stream['codec'].startswith('pcm_'):
                codec = stream['codec'][len('pcm_'):]
                args += ['-f', codec]
            elif stream['codec'] == 'mp2':
                args += ['-f', 'mp2']
            elif stream['codec'] == 'libfaad':
                path += '.aac'
            else:
                raise ManzanitaRewrapException('Unsupported audio codec: %s' % stream['codec'])

            audio_streams.append({'path': path, 'infos': stream, 'demux_args': args})

        # Fetch video nbframes in order to compute demuxing progress
        fid = sjfs.get_fid(0, self.input_file)
        if fid:
            nbframes = sjfs.get_key(fid, 'video_nbframes', 'media')
            if nbframes is not None:
                nbframes = int(nbframes)
        else:
            nbframes = 0

        # Setup demuxing worker
        demux = FFmpegWorker(self.log, {'args': []})
        demux.set_nb_frames(nbframes)
        demux.add_input_file(self.input_file)

        for video_stream in video_streams:
            demux.add_output_file(video_stream['path'], {'args': ['-vsync', '0', '-vcodec', 'copy', '-y']})

        for audio_stream in audio_streams:
            demux.add_output_file(audio_stream['path'], {'args': audio_stream['demux_args']})

        if 'manzanita' not in self.params:
            self.params['manzanita'] = {}

        if 'global' not in self.params['manzanita']:
            self.params['manzanita']['global'] = {}

        # Setup manzanita muxing worker
        mux = ManzanitaMuxWorker(self.log, self.params['manzanita']['global'])

        if 'stream' not in self.params['manzanita']:
            self.params['manzanita']['stream'] = {}

        if 'video' not in self.params['manzanita']['stream']:
            self.params['manzanita']['stream']['video'] = {}

        if 'audio' not in self.params['manzanita']['stream']:
            self.params['manzanita']['stream']['audio'] = {}

        for i, video_stream in enumerate(video_streams):
            index = str(i + 1)
            params = self.params['manzanita']['stream']['video'].get(index, {})
            params['type'] = 'video'
            mux.add_input_file(video_stream['path'], params)

        for i, audio_stream in enumerate(audio_streams):
            index = str(i + 1)
            params = self.params['manzanita']['stream']['audio'].get(index, {})
            params['type'] = 'audio'
            mux.add_input_file(audio_stream['path'], params)

        mux.add_output_file(self.output_file)

        # Add demuxing and muxing workers to worker list
        self.workers.append(demux)
        self.workers.append(mux)

    def _finalize(self):
        pass
