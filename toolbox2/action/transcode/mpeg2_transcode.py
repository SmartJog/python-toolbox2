# -*- coding: utf-8 -*-

import os
import os.path

from toolbox2.action import Action, ActionException
from toolbox2.action.extract.avinfo_extract import AVInfoAction
from toolbox2.worker.ffmpeg import FFmpegWorker
from toolbox2.worker.omneon import OmneonCopyWorker, OmneonQueryWorker


class Mpeg2TranscodeException(ActionException):
    pass


class Mpeg2TranscodeAction(Action):
    """
    Transcode to mpeg2 video and mux to various formats
    """

    name = 'mpeg2_transcode'
    engine = ['ffmpeg', 'ommq', 'ommcp']
    category = 'transcode'
    description = 'transcode to mpeg2 video and mux to various formats'
    required_params = {}

    def __init__(self, log, base_dir, _id, params=None, ressources=None):
        Action.__init__(self, log, base_dir, _id, params, ressources)

        if not os.path.isdir(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        self.codec = self.params.get('codec', 'imx')
        self.audio_codec = self.params.get('audio_codec', 'pcm_s16le')
        self.container = self.params.get('container', 'mxf')
        self.container_mapping = self.params.get('container_mapping', 'default')
        self.container_version = self.params.get('container_version', 'default')
        self.muxer = self.params.get('muxer', 'ffmpeg')
        self.bitrate = int(self.params.get('bitrate', 30000))
        self.reference = int(self.params.get('reference', 0))
        self.letterbox = int(self.params.get('letterbox', 0))
        self.aspect_ratio = self.params.get('aspect_ratio', 'auto')
        self.essence_dir = self.params.get('essence_dir', 'media.dir/').lstrip('/')
        self.abs_essence_dir = os.path.join(self.tmp_dir, self.essence_dir)

        self.demux_channel_layout = 'default'
        self.codec_options = {
            'bitrate': self.bitrate,
        }
        self.container_options = {
            'mapping': self.container_mapping,
            'version': self.container_version,
        }

        if not os.path.isdir(self.abs_essence_dir):
            os.makedirs(self.abs_essence_dir)

        if self.muxer == 'ffmpeg' and self.reference:
            raise Mpeg2TranscodeException('Reference files are not supported with ffmpeg muxer')

        if self.container == 'mxf' and self.codec == 'xdcamhd' and self.container_options.get('mapping') == 'rdd9':
            self.demux_channel_layout = 'split'

    def _setup(self):
        self.input_file = self.get_input_ressource(1).get('path')
        nb_video_frames = int(self.get_input_ressource(1).get('nb_video_frames'))
        self.input_basename = os.path.splitext(os.path.basename(self.input_file))[0]

        avinfo_action = AVInfoAction(self.log, self.base_dir, self.id)
        avinfo_action.add_input_ressource(1, {'path': self.input_file})
        avinfo = avinfo_action.run()

        ffmpeg = self._new_worker(FFmpegWorker)
        ffmpeg.add_input_file(self.input_file, {}, avinfo)
        ffmpeg.set_nb_frames(nb_video_frames)
        ffmpeg.set_timecode(avinfo.timecode)

        ffmpeg.transcode(self.codec, self.codec_options)

        if self.aspect_ratio == 'auto':
            if avinfo.video_dar == '16:9':
                ffmpeg.set_aspect_ratio('16:9')
            else:
                ffmpeg.set_aspect_ratio('4:3')
        else:
            ffmpeg.set_aspect_ratio(self.aspect_ratio)

        if self.letterbox:
            ffmpeg.letterbox()

        ffmpeg.audio_opts += [
            ('-acodec', self.audio_codec),
            ('-ar', 48000),
        ]

        # FFmpeg muxer
        if self.muxer == 'ffmpeg':
            ffmpeg.mux(self.tmp_dir, self.container, self.container_options)
            for index, output_file in enumerate(ffmpeg.output_files):
                self.add_output_ressource(index + 1, {'path': output_file.path})
            self.workers.append(ffmpeg)

        # Omneon muxer
        elif self.muxer == 'omneon':
            ffmpeg.demux(self.abs_essence_dir, self.demux_channel_layout)

            ommcp = self._new_worker(OmneonCopyWorker)
            for output_file in ffmpeg.output_files:
                params = {}
                if self.codec == 'copy' and output_file.path.endswith('.dv'):
                    params['srctrack'] = 0
                ommcp.add_input_file(output_file.path, params)

            base_path = os.path.join(self.tmp_dir, self.input_basename)
            ommcp.mux(base_path, self.container, self.container_options)

            ommq = self._new_worker(OmneonQueryWorker)
            for output_file in ommcp.output_files:
                ommq.add_input_file(output_file.path)

            ommq.set_timecode(avinfo.timecode)

            index = 0
            for output_file in ommcp.output_files:
                self.add_output_ressource(index + 1, {'path': output_file.path})
                index += 1

            if self.reference:
                for output_file in ffmpeg.output_files:
                    self.add_output_ressource(index + 1, {'path': output_file.path})
                    index += 1

            self.workers.append(ffmpeg)
            self.workers.append(ommcp)
            self.workers.append(ommq)

    def _finalize(self):
        pass
