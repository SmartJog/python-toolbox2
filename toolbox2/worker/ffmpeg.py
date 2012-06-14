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
                if isinstance(option, list) or isinstance(option, tuple):
                    if option[0] == '-threads':
                        continue
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
        self.keep_vbi_lines = False
        self.mov_imx_header = False
        self.decoding_threads = 1
        self.encoding_threads = 1

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
            if self.decoding_threads:
                args += ['-threads', self.decoding_threads]
            args += input_file.get_args()

        if self.video_filter_chain:
            args += ['-vf']
            args += [','.join([flt[1] for flt in self.video_filter_chain])]

        for opts in [self.video_opts, self.audio_opts, self.format_opts]:
            for opt in opts:
                if isinstance(opt, list) or isinstance(opt, tuple):
                    if opt[0] == '-threads':
                        continue
                    args += list(opt)
                else:
                    raise FFmpegWorkerException('FFmpeg options must be of type tuple or list')

        for output_file in self.output_files:
            if self.encoding_threads:
                args += ['-threads', self.encoding_threads]
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

    def transcode_dnxhd(self, options=None):
        if not options:
            options = {}
        bitrate = options.get('bitrate', 220000)
        interlaced = False
        if bitrate in [220000, 175000, 145000, 120000]:
            interlaced = True

        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input file: %s' % self.input_files[0].path)

        if not avinfo.video_is_HD():
            raise FFmpegWorkerException('Only 1920x1080 videos are supported')

        if avinfo.video_fps in avinfo.FPS_NTSC and bitrate not in [220000, 145000, 36000]:
            raise FFmpegWorkerException('NTSC input is not compatible with output bitrate: %s' % bitrate)

        if avinfo.video_fps in avinfo.FPS_PAL and bitrate not in [185000, 120000, 36000]:
            raise FFmpegWorkerException('PAL input is not compatible with output bitrate: %s' % bitrate)

        if avinfo.video_fps in avinfo.FPS_FILM and bitrate not in [175000, 115000, 36000]:
            raise FFmpegWorkerException('FILM input is not compatible with output bitrate: %s' % bitrate)

        self.video_opts = [
            ('-vcodec', 'dnxhd'),
            ('-b:v', '%sk' % bitrate),
        ]

        if bitrate == 36000:
            self.video_opts += [('-qmax', 1024)]

        if interlaced:
            self.video_opts += [('-flags', '+ildct')]

    def transcode_imx(self, options=None):
        if not options:
            options = {}
        bitrate = options.get('bitrate', 50000)
        enable_fourcc_tagging = options.get('enable_fourcc_tagging', False)

        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input file: %s' % self.input_files[0].path)

        codec_tag = None
        bufsize = 0

        if not (avinfo.video_is_SD_PAL() or avinfo.video_is_SD_NTSC()):
            raise FFmpegWorkerException('Only PAL and NTSC systems are supported')

        if bitrate not in [30000, 50000]:
            raise FFmpegWorkerException('Only IMX 30 and 50 is supported')

        self.video_opts = []
        self.video_opts += [
            ('-g', 0),
            ('-flags', '+ildct+low_delay'),
            ('-dc', 10),
            ('-intra_vlc', 1),
            ('-non_linear_quant', 1),
            ('-qscale', 1),
            ('-vcodec', 'mpeg2video'),
            ('-ps', 1),
            ('-qmin', 1),
            ('-qmax', 12),
            ('-lmin', '1*QP2LAMBDA'),
            ('-rc_max_vbv_use', 1),
            ('-pix_fmt', 'yuv422p'),
            ('-top', 1),
        ]

        if avinfo.video_is_SD_PAL() and bitrate == 30000:
            codec_tag = 'mx3p'
            bufsize = 1200000
        elif avinfo.video_is_SD_NTSC() and bitrate == 30000:
            codec_tag = 'mx3n'
            bufsize = 1001000
        elif avinfo.video_is_SD_PAL() and bitrate == 50000:
            codec_tag = 'mx5p'
            bufsize = 2000000
        elif avinfo.video_is_SD_NTSC() and bitrate == 50000:
            codec_tag = 'mx5n'
            bufsize = 1668334

        self.video_opts += [
            ('-minrate', '%sk' % bitrate),
            ('-maxrate', '%sk' % bitrate),
            ('-b:v', '%sk' % bitrate),
            ('-bufsize', bufsize),
            ('-rc_init_occupancy', bufsize),
        ]

        if enable_fourcc_tagging:
            self.video_opts += [
                ('-vtag', codec_tag)
            ]

        self.video_filter_chain = []
        if avinfo.video_is_SD_NTSC():
            self.video_filter_chain.append(('fieldorder', 'fieldorder=tff'))

        if not avinfo.video_has_vbi:
            if avinfo.video_is_SD_PAL():
                self.video_filter_chain.append(('add_vbi', 'pad=720:608:00:32'))
            elif avinfo.video_is_SD_NTSC():
                self.video_filter_chain.append(('add_vbi', 'pad=720:512:00:32'))

        self.keep_vbi_lines = True
        self.mov_imx_header = True

    def transcode_mpeg2video(self, options=None):
        if not options:
            options = {}

        bitrate = options.get('bitrate', 15000)
        pix_fmt = options.get('pix_fmt', 'yuv422p')

        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input file: %s' % self.input_files[0].path)

        bufsize = bitrate * 65536 / 90 - 5000
        if pix_fmt == 'yuv422p':
            if avinfo.video_is_HD():
                bufsize = bufsize > 47185920 and 47185920 or bufsize
            else:
                bufsize = bufsize > 9437184 and 9437184 or bufsize
        elif pix_fmt == 'yuv420p':
            if avinfo.video_is_HD():
                bufsize = bufsize > 9781248 and 9781248 or bufsize
            else:
                bufsize = bufsize > 1835008 and 1835008 or bufsize
        else:
            raise FFmpegWorkerException('Unsupported pixel format: %s' % pix_fmt)

        gop_size = 12
        if avinfo.video_fps in avinfo.FPS_NTSC:
            gop_size = 15

        self.video_opts = [
            ('-vcodec', 'mpeg2video'),
            ('-pix_fmt', pix_fmt),
            ('-b:v', '%sk' % bitrate),
            ('-minrate', '%sk' % bitrate),
            ('-maxrate', '%sk' % bitrate),
            ('-bufsize', bufsize),
            ('-bf', 2),
            ('-g', gop_size),
            ('-flags', '+ilme+ildct'),
            ('-flags2', 'sgop'),
            ('-intra_vlc', 1),
            ('-non_linear_quant', 1),
            ('-qdiff', 0.5),
            ('-dc', 10),
            ('-qmin', 1),
            ('-qmax', 12),
            ('-lmin', '1*QP2LAMBDA'),
            ('-rc_min_vbv_use', 1),
            ('-rc_max_vbv_use', 1),
        ]

        if not avinfo.video_is_HD():
            # Preserve vbi lines for mpeg2 422@ML
            if avinfo.video_has_vbi and pix_fmt == 'yuv422p':
                self.keep_vbi_lines = True
            else:
                if avinfo.video_is_SD_NTSC():
                    height = 480
                elif avinfo.video_is_SD_PAL():
                    height = 576
                self.video_filter_chain.insert(0,
                    ('crop_vbi', 'crop=720:%s:00:32' % height)
                )

    def transcode_mpeg2audio(self, options=None):
        if not options:
            options = {}

        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input file: %s' % self.input_files[0].path)

        if not avinfo.audio_streams:
            return

        if avinfo.audio_streams[0].get('sample_rate', 48000) < 44100:
            bitrate = '128'
        else:
            bitrate = '384'

        self.audio_opts = [
            ('-acodec', 'mp2'),
            ('-ab', '%sk' % bitrate),
        ]

    def transcode_pcm(self, options=None):
        if not options:
            options = {}
        audio_format = options.get('format', 's16le')
        sample_rate = options.get('sample_rate', 48000)

        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input file: %s' % self.input_files[0].path)

        self.audio_opts += [
            ('-acodec', 'pcm_%s' % audio_format),
            ('-ar', sample_rate),
        ]

    def transcode_xdcamhd(self, options=None):
        if not options:
            options = {}
        bitrate = options.get('bitrate', 50000)
        enable_fourcc_tagging = options.get('enable_fourcc_tagging', False)

        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input file: %s' % self.input_files[0].path)

        if avinfo.video_res != avinfo.RES_HD:
            raise FFmpegWorkerException('Only 1920x1080 videos are supported')

        if bitrate not in [50000]:
            raise FFmpegWorkerException('Only 50MBP XDCAM HD is supported')

        if avinfo.video_fps in avinfo.FPS_NTSC:
            codec_tag = 'xd5b'
        elif avinfo.video_fps in avinfo.FPS_PAL:
            codec_tag = 'xd5c'
        elif avinfo.video_fps in avinfo.FPS_FILM:
            codec_tag = 'xd5d'
        else:
            raise FFmpegWorkerException('Unsupported input frame rate: %s' % avinfo.video_fps)

        self.video_opts = []
        self.video_opts += [
            ('-vcodec', 'mpeg2video'),
            ('-pix_fmt', 'yuv422p'),
            ('-b:v', '%sk' % bitrate),
            ('-minrate', '%sk' % bitrate),
            ('-maxrate', '%sk' % bitrate),
            ('-bufsize', 36408333),
            ('-bf', 2),
            ('-flags', '+ilme+ildct'),
            ('-flags2', 'sgop'),
            ('-intra_vlc', 1),
            ('-non_linear_quant', 1),
            ('-qdiff', 0.5),
            ('-dc', 10),
            ('-qmin', 1),
            ('-qmax', 12),
            ('-lmin', '1*QP2LAMBDA'),
            ('-rc_max_vbv_use', 1),
            ('-s', '1920x1080'),
        ]

        if enable_fourcc_tagging:
            self.video_opts += [
                ('-vtag', codec_tag)
            ]

    def transcode(self, codec, options=None):
        if codec == 'copy':
            return self.copy_video()

        method = getattr(self, "transcode_%s" % codec)
        return method(options)

    def mux_mpegps(self, basedir, options=None):
        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        basename = os.path.splitext(os.path.basename(self.input_files[0].path))[0]
        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input fi1e: %s' % self.input_files[0].path)

        acodec = self.get_opt_value('acodec', 'mp2')
        vcodec = self.get_opt_value('vcodec', 'mpeg2video')

        if acodec != 'mp2':
            raise FFmpegWorkerException('Mpeg2 PS does not support audio codec:' % acodec)

        if vcodec not in ['mpeg1video', 'mpeg2video']:
            raise FFmpegWorkerException('Mpeg2 PS does not support video codec: %s' % vcodec)

        # FIXME: when -amerge is ready, we should force a stereo layout per audio stream
        self.audio_opts += [('-map', '0:a')]
        self.video_opts += [('-map', '0:v')]
        self.format_opts += [('-f', 'vob')]

        path = '%s%s' % (os.path.join(basedir, basename), '.mpg')
        self.add_output_file(path)

    def mux_mxf(self, basedir, options=None):
        if not options:
            options = {}
        mapping = options.get('mapping', 'default')

        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        basename = os.path.splitext(os.path.basename(self.input_files[0].path))[0]
        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input fi1e: %s' % self.input_files[0].path)

        audio_rate = self.get_opt_value('-ar')
        if not audio_rate:
            self.audio_opts += [('-ar', 48000)]
        elif audio_rate != 48000:
            raise FFmpegWorkerException('Only 48000Hz audio is supported in mxf for now')

        self.video_opts += [('-map', '0:v')]

        if mapping == 'rdd9':
            self.split_audio_channels = True
            self.format_opts += [('-f', 'mxf')]
            for stream in avinfo.audio_streams:
                index = len(avinfo.video_streams)
                for channel_index in range(stream['channels']):
                    self.audio_opts += [('-map', '0:%s' % stream['index'])]
                    self.audio_opts += [('-map_channel', '%s.%s.%s:0.%s' % (0, stream['index'], channel_index, index))]
                    index += 1
        else:
            self.format_opts += [('-f', 'mxf')]
            self.audio_opts += [('-map', '0:a')]

        path = '%s%s' % (os.path.join(basedir, basename), '.mxf')
        self.add_output_file(path)

    def mux_mov(self, basedir, options=None):
        if not self.input_files:
            raise FFmpegWorkerException('no input file specified')

        basename = os.path.splitext(os.path.basename(self.input_files[0].path))[0]
        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('no avinfo specified for input fi1e: %s' % self.input_files[0].path)

        self.video_opts += [('-map', '0:v')]
        if self.mov_imx_header:
            self.video_opts += [('-vbsf', 'imxdump')]
        self.audio_opts += [('-map', '0:a')]
        self.format_opts += [('-f', 'mov')]

        path = '%s%s' % (os.path.join(basedir, basename), '.mov')
        self.add_output_file(path)

    def mux_gxf(self, basedir, options=None):
        if not self.input_files:
            raise FFmpegWorkerException('no input file specified')

        basename = os.path.splitext(os.path.basename(self.input_files[0].path))[0]
        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('no avinfo specified for input fi1e: %s' % self.input_files[0].path)

        self.format_opts += [('-f', 'gxf')]
        self.video_opts += [('-map', '0:v')]

        for stream in avinfo.audio_streams:
            index = len(avinfo.video_streams)
            for channel_index in range(stream['channels']):
                self.audio_opts += [('-map', '0:%s' % stream['index'])]
                self.audio_opts += [('-map_channel', '%s.%s.%s:0.%s' % (0, stream['index'], channel_index, index))]
                index += 1

        path = '%s%s' % (os.path.join(basedir, basename), '.gxf')
        self.add_output_file(path)

    def mux(self, basedir, container, options=None):
        method = getattr(self, 'mux_%s' % container)
        return method(basedir, options)

    def letterbox(self):
        if not len(self.input_files) > 0:
            raise FFmpegWorkerException('No input file specified')

        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input fi1e: %s' % self.input_files[0].path)

        if not avinfo.video_is_SD_NTSC() and not avinfo.video_is_SD_PAL():
            raise FFmpegWorkerException('Only NTSC/PAL SD is supported')

        if avinfo.video_dar != '16:9':
            raise FFmpegWorkerException('Only 16:9 content is supported')

        self.set_aspect_ratio('4:3')

        if not avinfo.video_has_vbi or (avinfo.video_has_vbi and not self.keep_vbi_lines):
            # Remove previously insered vbi lines and re-add them at the end
            # of the filter chain
            self.video_filter_chain = [flt for flt in self.video_filter_chain if flt[0] not in ['add_vbi']]

            vbi_lines = 0
            if self.keep_vbi_lines:
                vbi_lines = 32
            if avinfo.video_is_SD_NTSC():
                scale_height = 360
                total_height = 480 + vbi_lines
                top_blank_lines = 60 + vbi_lines
            elif avinfo.video_is_SD_PAL():
                scale_height = 432
                total_height = 576 + vbi_lines
                top_blank_lines = 72 + vbi_lines
            self.video_filter_chain.append(
                ('letterbox', 'scale=720:%d,pad=720:%d:00:%d' % (scale_height, total_height, top_blank_lines)),
            )

        else:
            filter_chain = 'split[v1][v2];\n'
            if avinfo.video_is_SD_NTSC():
                filter_chain += '[v1]crop=720:480:00:32,scale=720:360,pad=720:512:00:92[videonovbi];\n'
            elif avinfo.video_is_SD_PAL():
                filter_chain += '[v1]crop=720:576:00:32,scale=720:432,pad=720:608:00:104[videonovbi];\n'

            filter_chain += '[v2]crop=720:32:00:00[vbi];\n'
            filter_chain += '[videonovbi][vbi]overlay=0:0'

            self.video_filter_chain.insert(0,
                ('letterbox', filter_chain),
            )
