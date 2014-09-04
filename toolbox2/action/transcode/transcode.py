# -*- coding: utf-8 -*-

import os
import os.path

from toolbox2.action import Action, ActionException
from toolbox2.action.extract.avinfo_extract import AVInfoAction
from toolbox2.worker.bmx import Raw2BmxWorker
from toolbox2.worker.flvtools2 import FLVTool2Worker
from toolbox2.worker.ffmpeg import FFmpegWorker
from toolbox2.worker.omneon import OmneonCopyWorker, OmneonQueryWorker
from toolbox2.worker.qtfaststart import QtFastStartWorker


class TranscodeException(ActionException):
    pass


class TranscodeAction(Action):
    """
    Transcode and mux to various codecs/formats
    """

    name = 'transcode'
    engine = ['ffmpeg', 'ommq', 'ommcp']
    category = 'transcode'
    description = 'transcode to mpeg2 video and mux to various formats'
    required_params = {}

    def __init__(self, log, base_dir, _id, params=None, resources=None):
        Action.__init__(self, log, base_dir, _id, params, resources)

        if not os.path.isdir(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        self.video_codec = self.params.get('video_codec', 'imx')
        self.video_bitrate = int(self.params.get('video_bitrate', 50000))
        self.video_letterbox = int(self.params.get('video_letterbox', 0))
        self.video_aspect_ratio = self.params.get('video_aspect_ratio', 'default')
        self.video_pix_fmt = self.params.get('video_pix_fmt', 'yuv422p')
        self.video_gop_size = int(self.params.get('video_gop_size', 0))
        self.video_closed_gop = int(self.params.get('video_closed_gop', 0))
        self.video_interlaced = int(self.params.get('video_interlaced', 1))
        self.video_resolution = self.params.get('video_resolution', 'default')
        self.video_burn = int(self.params.get('video_burn', 0))

        self.audio_codec = self.params.get('audio_codec', 'pcm')
        self.audio_format = self.params.get('audio_format', 'default')
        self.audio_sample_rate = int(self.params.get('audio_sample_rate', 48000))
        self.audio_bitrate = int(self.params.get('audio_bitrate', 0))
        self.audio_min_streams = self.params.get('audio_min_streams')
        self.audio_channels_per_stream = int(self.params.get('audio_channels_per_stream', 0))

        self.container = self.params.get('container', 'mxf')
        self.container_mapping = self.params.get('container_mapping', 'default')
        self.container_version = self.params.get('container_version', 'default')
        self.container_reference = int(self.params.get('container_reference', 0))
        self.container_hinting = int(self.params.get('container_hinting', 0))
        self.container_essence_dir = self.params.get('container_essence_dir', 'media.dir/').lstrip('/')
        self.container_abs_essence_dir = os.path.join(self.tmp_dir, self.container_essence_dir)

        self.muxer = self.params.get('muxer', 'ffmpeg')

        self.decoding_threads = int(self.params.get('decoding_threads', 1))
        self.encoding_threads = int(self.params.get('encoding_threads', 1))

        self.audio_codec_options = {
            'format': self.audio_format,
            'bitrate': self.audio_bitrate,
            'sample_rate': self.audio_sample_rate,
        }

        self.video_codec_options = {
            'bitrate': self.video_bitrate,
            'pix_fmt': self.video_pix_fmt,
            'enable_fourcc_tagging': self.container == 'mov',
            'gop_size': self.video_gop_size,
            'closed_gop': self.video_closed_gop,
            'interlaced': self.video_interlaced,
            'resolution': self.video_resolution,
        }

        self.container_options = {
            'mapping': self.container_mapping,
            'version': self.container_version,
            'reference': self.container_reference,
        }

        self.burn_options = {
            'box': int(self.params.get('video_burn_box', 0)),
            'text': self.params.get('video_burn_text', ''),
            'timecode': int(self.params.get('video_burn_timecode', 0)),
            'position': self.params.get('video_burn_position', 'center'),
            'fontname': self.params.get('video_burn_fontname', 'vera'),
            'fontsize': int(self.params.get('video_burn_fontsize', 12)),
            'padding': int(self.params.get('video_burn_padding', 10)),
            'date': int(self.params.get('video_burn_date', 0)),
            'hostname': int(self.params.get('video_burn_hostname', 0)),
        }

        if not os.path.isdir(self.container_abs_essence_dir):
            os.makedirs(self.container_abs_essence_dir)

        if self.muxer == 'ffmpeg' and self.container_reference:
            raise TranscodeException('Reference files are not supported with ffmpeg muxer')

        if self.muxer == 'bmx' and self.container != 'mxf':
            raise TranscodeException('BMX only support MXF muxing')

        if self.container == 'mxf':
            if self.video_codec == 'xdcamhd' and self.container_mapping == 'rdd9':
                self.audio_channels_per_stream = 1
            if self.video_codec == 'imx' and self.container_mapping == 'd10':
                self.audio_channels_per_stream = 8

        if self.container_hinting and self.muxer != 'ffmpeg':
            self.log.warning('Only ffmpeg muxer support file hinting for streaming')

        if self.container_hinting and self.container not in ['flv', 'mp4', 'mov']:
            self.log.warning('Only flv, mp4 and mov container support hinting')
            self.container_hinting = 0

    def _setup(self):
        self.input_file = self.get_input_resource(1).get('path')
        nb_video_frames = int(self.get_input_resource(1).get('nb_video_frames', 0))
        self.input_basename = os.path.splitext(os.path.basename(self.input_file))[0]

        avinfo_action = AVInfoAction(self.log, self.base_dir, self.id)
        avinfo_action.add_input_resource(1, {'path': self.input_file})
        avinfo = avinfo_action.run()

        ffmpeg = self._new_worker(FFmpegWorker)
        ffmpeg.add_input_file(self.input_file, {}, avinfo)
        ffmpeg.set_nb_frames(nb_video_frames)
        ffmpeg.set_audio_min_streams(self.audio_min_streams)
        ffmpeg.set_timecode(avinfo.timecode)
        ffmpeg.set_threads(self.decoding_threads, self.encoding_threads)
        ffmpeg.set_channels_per_stream(self.audio_channels_per_stream)

        if self.audio_format == 'default':
            if avinfo.audio_format:
                self.audio_format = avinfo.audio_format
            else:
                self.audio_format = 's16le'
            self.audio_codec_options['format'] = self.audio_format

        ffmpeg.transcode(self.video_codec, self.video_codec_options)
        ffmpeg.transcode(self.audio_codec, self.audio_codec_options, 'audio')

        if self.video_aspect_ratio == 'default':
            if avinfo.video_is_HD():
                ffmpeg.set_aspect_ratio('16:9')
            else:
                num, den = avinfo.video_dar.split(':')
                dar = float(num) / float(den)
                if dar > 1.5:
                    ffmpeg.set_aspect_ratio('16:9')
                else:
                    ffmpeg.set_aspect_ratio('4:3')
        elif self.video_aspect_ratio == 'copy':
            ffmpeg.set_aspect_ratio(avinfo.video_dar)
        else:
            ffmpeg.set_aspect_ratio(self.video_aspect_ratio)

        if self.video_letterbox:
            ffmpeg.letterbox()

        if self.video_burn:
            ffmpeg.drawtext(self.tmp_dir, self.burn_options)

        # FFmpeg muxer
        if self.muxer == 'ffmpeg':
            ffmpeg.mux(self.tmp_dir, self.container, self.container_options)
            self.workers.append(ffmpeg)
            if not self.container_hinting:
                for index, output_file in enumerate(ffmpeg.output_files):
                    self.add_output_resource(index + 1, {'path': output_file.path})
            else:
                if self.container in ['flv']:
                    for index, output_file in enumerate(ffmpeg.output_files):
                        hinting_worker = self._new_worker(FLVTool2Worker)
                        hinting_worker.params = {'-U': ''}
                        hinting_worker.add_input_file(output_file.path)
                        self.workers.append(hinting_worker)
                        self.add_output_resource(index + 1, {'path': output_file.path})

                elif self.container in ['mp4', 'mov']:
                    for index, output_file in enumerate(ffmpeg.output_files):
                        base, ext = os.path.splitext(output_file.path)
                        hinting_output_path = '%s-hint%s' % (base, ext)
                        hinting_worker = self._new_worker(QtFastStartWorker)
                        hinting_worker.add_input_file(output_file.path)
                        hinting_worker.add_output_file(hinting_output_path)
                        self.workers.append(hinting_worker)
                        self.add_output_resource(index + 1, {'path': hinting_output_path})

        # Omneon muxer
        elif self.muxer == 'omneon':
            ffmpeg.demux(self.container_abs_essence_dir)

            ommcp = self._new_worker(OmneonCopyWorker)
            for output_file in ffmpeg.output_files:
                params = {}
                if self.video_codec == 'copy' and output_file.path.endswith('.dv'):
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
                self.add_output_resource(index + 1, {'path': output_file.path})
                index += 1

            if self.container_reference:
                for output_file in ffmpeg.output_files:
                    self.add_output_resource(index + 1, {'path': output_file.path})
                    index += 1

            self.workers.append(ffmpeg)
            self.workers.append(ommcp)
            self.workers.append(ommq)

        # BMX muxer
        elif self.muxer == 'bmx':
            ffmpeg.demux(self.container_abs_essence_dir)

            raw2bmx = self._new_worker(Raw2BmxWorker)
            for output_file in ffmpeg.output_files:
                params = {}
                if output_file.type == 'video':
                    params['codec'] = self.video_codec
                elif output_file.type == 'audio':
                    params['codec'] = self.audio_codec
                raw2bmx.add_input_file(output_file.path, params)

            base_path = os.path.join(self.tmp_dir, self.input_basename)
            raw2bmx.set_timecode(avinfo.timecode)
            raw2bmx.mux(base_path, self.container_options)
            index = 0
            for output_file in raw2bmx.output_files:
                self.add_output_resource(index + 1, {'path': output_file.path})
                index += 1

            self.workers.append(ffmpeg)
            self.workers.append(raw2bmx)

        # Unsupported muxer
        else:
            raise TranscodeException('Unsupported muxer: %s' % self.muxer)

    def _finalize(self):
        pass
