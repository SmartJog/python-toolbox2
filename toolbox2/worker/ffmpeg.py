# -*- coding: utf-8 -*-

import re
import copy
import os.path
from collections import defaultdict

from toolbox2.worker import Worker, WorkerException


codec_extension_map = {
    # Video
    'mpegvideo'  : '.m1v',
    'mpeg2video' : '.m2v',
    'mpeg4video' : '.m4v',
    'dvvideo'    : '.dv',
    'dnxhd':       '.dnxhd',

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
        self.audio_filter_chain = []
        self.keep_vbi_lines = False
        self.mov_imx_header = False
        self.decoding_threads = 1
        self.encoding_threads = 1
        self.fps = 0

    def _handle_output(self, stdout, stderr):
        Worker._handle_output(self, stdout, stderr)

        res = re.findall('frame=\s*(\d+)', self.stderr)
        if len(res) > 0 and self.nb_frames > 0:
            frame = float(res[-1])
            self.progress = (frame / self.nb_frames) * 100
            if self.progress > 99:
                self.progress = 99
        res = re.findall('fps=\s*(\d+)', self.stderr)
        if res:
            self.fps = int(res[-1])

    def add_input_file(self, path, params=None, avinfo=None):
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

        if self.audio_filter_chain:
            args += ['-filter_complex']
            args += [','.join([flt[1] for flt in self.audio_filter_chain])]

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

    @staticmethod
    def get_audio_layout_mapping(avinfo, o_channels_per_stream=2):

        def output_stream_dict():
            return {'input_channels': [], 'input_streams': {}}

        o_stream_idx = 0
        o_stream_map = defaultdict(output_stream_dict)
        for audio_stream in avinfo.audio_streams:
            channels = audio_stream['channels']
            if o_channels_per_stream > 0:
                channels_left = o_channels_per_stream - len(o_stream_map[o_stream_idx]['input_channels'])
            else:
                channels_left = channels
            if channels == channels_left:
                o_stream_map[o_stream_idx]['input_streams'][audio_stream['index']] = audio_stream
                o_stream_map[o_stream_idx]['input_channels'].append((audio_stream['index'], 0))
                o_stream_idx += 1
            else:
                for channel_idx in range(channels):
                    o_stream_map[o_stream_idx]['input_streams'][audio_stream['index']] = audio_stream
                    o_stream_map[o_stream_idx]['input_channels'].append((audio_stream['index'], channel_idx))
                    if channels > channels_left and len(o_stream_map[o_stream_idx]['input_channels']) == o_channels_per_stream:
                            o_stream_idx += 1

        filter_chain = ''
        map_chain = []
        for index, output_stream in o_stream_map.iteritems():
            if len(output_stream['input_streams']) == 1:
                input_stream = output_stream['input_streams'].values()[0]
                if input_stream['channels'] == o_channels_per_stream or o_channels_per_stream == 0:
                    map_chain.append(('-map', '0:%s' % input_stream['index']))
                else:
                    filter_merge = ''
                    for input_channel in output_stream['input_channels']:
                        filter_chain += '[0:%s]pan=mono:c0=c%s' % (input_channel[0], input_channel[1])
                        filter_chain += '[p%s_%s];' % (input_channel[0], input_channel[1])
                        filter_merge += '[p%s_%s]' % (input_channel[0], input_channel[1])

                    if len(output_stream['input_channels']) > 1:
                        filter_chain += filter_merge
                        filter_chain += 'amerge=inputs=%s[m%s];' % (len(output_stream['input_channels']), index)
                        map_chain.append(('-map', '[m%s]' % (index)))
                    else:
                        map_chain.append(('-map', '[p%s_%s]' % (output_stream['input_channels'][0][0], output_stream['input_channels'][0][1])))
            else:
                filter_merge = ''
                for input_channel in output_stream['input_channels']:
                    filter_chain += '[0:%s]pan=mono:c0=c%s' % (input_channel[0], input_channel[1])
                    filter_chain += '[p%s_%s];' % (input_channel[0], input_channel[1])
                    filter_merge += '[p%s_%s]' % (input_channel[0], input_channel[1])

                filter_chain += filter_merge
                filter_chain += 'amerge=inputs=%s[m%s];' % (len(output_stream['input_channels']), index)
                map_chain.append(('-map', '[m%s]' % (index)))
        return (filter_chain.rstrip(';'), map_chain)

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

    def demux(self, basedir, channels_per_stream=0):
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

        filter_chain, mapping = self.get_audio_layout_mapping(avinfo, channels_per_stream)
        if filter_chain:
            self.audio_filter_chain += [('mapping_audio', filter_chain)]
        index = 0
        for audio_map in mapping:
            path = os.path.join(basedir, '%s_a%s' % (basename, index))
            extension = self._get_codec_extension(audio_codec or stream['codec_name'])
            path = '%s%s' % (path, extension)

            opts = [('-acodec', 'copy')]
            if audio_codec:
                opts = copy.copy(self.audio_opts)
            opts += [audio_map]

            self.add_output_file(path, {'audio_opts': opts}, 'audio')
            index += 1

        # Clean global audio/video options
        self.video_opts = []
        self.audio_opts = []

    def copy_video(self):
        self.video_opts.append(('-vcodec', 'copy'))

    def transcode_aac(self, options=None):
        if not options:
            options = {}
        bitrate = options.get('bitrate', 0)
        if bitrate == 0:
            bitrate = 192

        self.audio_opts = [
            ('-acodec', 'libfaac'),
            ('-b:a', '%sk' % bitrate)
        ]

    def get_dnxhd_profile(self, profile):
        dnxhd_profiles = [
            # 23.976 fps
            {'cid': 1235, 'fps': 23.97, 'pix_fmt': 'yuv422p10le',  'bitrate': 175000, 'interlaced': 0},
            {'cid': 1237, 'fps': 23.97, 'pix_fmt': 'yuv422p',      'bitrate': 115000, 'interlaced': 0},
            {'cid': 1238, 'fps': 23.97, 'pix_fmt': 'yuv422p',      'bitrate': 175000, 'interlaced': 0},
            {'cid': 1253, 'fps': 23.97, 'pix_fmt': 'yuv422p',      'bitrate': 36000,  'interlaced': 0},
            # 25 fps
            {'cid': 1235, 'fps': 25,     'pix_fmt': 'yuv422p10le', 'bitrate': 185000, 'interlaced': 0},
            {'cid': 1237, 'fps': 25,     'pix_fmt': 'yuv422p',     'bitrate': 120000, 'interlaced': 0},
            {'cid': 1238, 'fps': 25,     'pix_fmt': 'yuv422p',     'bitrate': 185000, 'interlaced': 0},
            {'cid': 1241, 'fps': 25,     'pix_fmt': 'yuv422p10le', 'bitrate': 185000, 'interlaced': 1},
            {'cid': 1242, 'fps': 25,     'pix_fmt': 'yuv422p',     'bitrate': 120000, 'interlaced': 1},
            {'cid': 1243, 'fps': 25,     'pix_fmt': 'yuv422p',     'bitrate': 185000, 'interlaced': 1},
            # 29.97 fps
            {'cid': 1235, 'fps': 29.97,  'pix_fmt': 'yuv422p10le', 'bitrate': 220000, 'interlaced': 1},
            {'cid': 1237, 'fps': 29.97,  'pix_fmt': 'yuv422p',     'bitrate': 145000, 'interlaced': 1},
            {'cid': 1238, 'fps': 29.97,  'pix_fmt': 'yuv422p',     'bitrate': 220000, 'interlaced': 1},
            # 50 fps
            {'cid': 1235, 'fps': 50,     'pix_fmt': 'yuv422p10le', 'bitrate': 365000, 'interlaced': 0},
            {'cid': 1237, 'fps': 50,     'pix_fmt': 'yuv422p',     'bitrate': 240000, 'interlaced': 0},
            {'cid': 1238, 'fps': 50,     'pix_fmt': 'yuv422p',     'bitrate': 365000, 'interlaced': 0},
            # 59.94
            {'cid': 1235, 'fps': 59.94,  'pix_fmt': 'yuv422p10le', 'bitrate': 440000, 'interlaced': 0},
            {'cid': 1237, 'fps': 59.94,  'pix_fmt': 'yuv422p',     'bitrate': 290000, 'interlaced': 0},
            {'cid': 1238, 'fps': 59.94,  'pix_fmt': 'yuv422p',     'bitrate': 440000, 'interlaced': 0},
        ]

        for dnxhd_profile in dnxhd_profiles:
            if profile['bitrate'] == dnxhd_profile['bitrate'] and \
               profile['pix_fmt'] == dnxhd_profile['pix_fmt'] and \
               profile['interlaced'] == dnxhd_profile['interlaced'] and \
               abs(profile['fps'] - dnxhd_profile['fps']) < 0.1:
                   return dnxhd_profile

    def transcode_dnxhd(self, options=None):
        if not options:
            options = {}
        bitrate = options.get('bitrate', 220000)
        bitrate_m = bitrate / 1000
        pix_fmt = options.get('pix_fmt', 'yuv422p')
        interlaced = options.get('interlaced', 1)

        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input file: %s' % self.input_files[0].path)

        if not avinfo.video_is_HD():
            raise FFmpegWorkerException('DNxHD transcode does not support input at %s, only 1920x1080 is supported' % avinfo.video_res)

        dnxhd_profile = self.get_dnxhd_profile({
            'fps':        avinfo.video_fps,
            'pix_fmt':    pix_fmt,
            'bitrate':    bitrate,
            'interlaced': interlaced,
        })

        if not dnxhd_profile:
            raise FFmpegWorkerException('DNxHD output settings are not valid: %sMbps 1920x1080%s %sbit @ %sfps' % (
                bitrate_m, 'i' if interlaced else 'p', 10 if pix_fmt == 'yuv422p10le' else 8, avinfo.video_fps,
            ))

        self.video_opts = [
            ('-vcodec', 'dnxhd'),
            ('-b:v', '%sk' % bitrate),
            ('-pix_fmt', pix_fmt)
        ]

        if bitrate == 36000:
            self.video_opts += [('-qmax', 1024)]

        if interlaced:
            self.video_opts += [('-flags', '+ildct')]

    def transcode_simple_h264(self, options=None):
        if not options:
            options = {}
        bitrate = options.get('bitrate', 1500)

        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input file: %s' % self.input_files[0].path)

        self.video_opts = [
            ('-vcodec', 'libx264'),
            ('-b:v', '%sk' % bitrate),
            ('-bf', 3),
            ('-b_strategy', 1),
            ('-g', 125),
            ('-coder', 1),
            ('-flags', '+loop'),
            ('-me_method', 'hex'),
            ('-cmp', '+chroma'),
            ('-subq', 5),
            ('-me_range', 16),
            ('-keyint_min', 25),
            ('-sc_threshold', 40),
            ('-i_qfactor', 0.71),
            ('-qcomp', 0.6),
            ('-qmin', 10),
            ('-qmax', 51),
            ('-qdiff', 4),
            ('-direct-pred', 1),
            ('-fast-pskip', 1),
            ('-trellis', 0),
            ('-refs', 1),
            ('-x264opts', 'partitions=i8x8,i4x4'),
        ]

        if avinfo.video_has_vbi:
            if avinfo.video_is_SD_NTSC():
                height = 480
            elif avinfo.video_is_SD_PAL():
                height = 576
            self.video_filter_chain.insert(0,
                ('crop_vbi', 'crop=720:%s:00:32' % height)
            )

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
            raise FFmpegWorkerException('IMX codec only supports PAL and NTSC frame rates')

        if bitrate not in [30000, 50000]:
            raise FFmpegWorkerException('IMX codec does not support bitrate at %sk' % bitrate)

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
        gop_size = options.get('gop_size', 0)
        closed_gop = options.get('closed_gop', 0)

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
            raise FFmpegWorkerException('MPEG-2 video codec does not support %s pixel format' % pix_fmt)


        if gop_size == 0:
            if avinfo.video_fps in avinfo.FPS_NTSC:
                gop_size = 15
            else:
                gop_size = 12

        flags = '+ilme+ildct'
        if closed_gop:
            flags += '+cgop'

        self.video_opts = [
            ('-vcodec', 'mpeg2video'),
            ('-pix_fmt', pix_fmt),
            ('-b:v', '%sk' % bitrate),
            ('-minrate', '%sk' % bitrate),
            ('-maxrate', '%sk' % bitrate),
            ('-bufsize', bufsize),
            ('-bf', 2),
            ('-g', gop_size),
            ('-flags', flags),
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

        if avinfo.video_has_vbi:
            # Preserve vbi lines for mpeg2 422@ML
            if pix_fmt == 'yuv422p':
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

        bitrate = options.get('bitrate', 0)
        if bitrate == 0:
            if avinfo.audio_streams[0].get('sample_rate', 48000) < 44100:
                bitrate = '128'
            else:
                bitrate = '384'

        self.audio_opts = [
            ('-acodec', 'mp2'),
            ('-b:a', '%sk' % bitrate),
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
        gop_size = options.get('gop_size', 0)
        closed_gop = options.get('closed_gop', 0)
        interlaced = options.get('interlaced', 1)
        enable_fourcc_tagging = options.get('enable_fourcc_tagging', False)

        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input file: %s' % self.input_files[0].path)

        if avinfo.video_res != avinfo.RES_HD:
            raise FFmpegWorkerException('XDCAMHD transcode does not support input at %s, only 1920x1080 is supported' % avinfo.video_res)

        if bitrate not in [50000]:
            raise FFmpegWorkerException('XDCAMHD does not support bitrate at %sk' % bitrate)

        if avinfo.video_fps in avinfo.FPS_NTSC:
            codec_tag = 'xd5b'
            if interlaced:
                self.video_filter_chain.append(('setfield', 'setfield=bff'))
        elif avinfo.video_fps in avinfo.FPS_PAL:
            codec_tag = 'xd5c'
            if interlaced:
                self.video_filter_chain.append(('setfield', 'setfield=tff'))
        elif avinfo.video_fps in avinfo.FPS_FILM:
            codec_tag = 'xd5d'
        else:
            raise FFmpegWorkerException('XDCAMHD does not support input at %s fps' % avinfo.video_fps)

        if gop_size == 0:
            if avinfo.video_fps in avinfo.FPS_NTSC:
                gop_size = 15
            else:
                gop_size = 12

        flags = ''
        if interlaced:
            flags += '+ilme+ildct'
        if closed_gop:
            flags += '+cgop'

        self.video_opts = []
        self.video_opts += [
            ('-vcodec', 'mpeg2video'),
            ('-pix_fmt', 'yuv422p'),
            ('-b:v', '%sk' % bitrate),
            ('-minrate', '%sk' % bitrate),
            ('-maxrate', '%sk' % bitrate),
            ('-bufsize', 17825792),
            ('-rc_init_occupancy', 17825792),
            ('-sc_threshold', 1000000000),
            ('-bf', 2),
            ('-g', gop_size),
            ('-intra_vlc', 1),
            ('-non_linear_quant', 1),
            ('-dc', 10),
            ('-qmin', 1),
            ('-qmax', 12),
            ('-s', '1920x1080'),
        ]

        if flags:
            self.video_opts += [
                ('-flags', flags),
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

    def mux_flv(self, basedir, options=None):
        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        basename = os.path.splitext(os.path.basename(self.input_files[0].path))[0]
        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input fi1e: %s' % self.input_files[0].path)

        self.video_opts += [('-map', '0:v')]
        self.format_opts += [('-f', 'flv')]

        filter_chain, mapping = self.get_audio_layout_mapping(avinfo, 2)
        if filter_chain:
            self.audio_filter_chain += [('audio_mapping', filter_chain)]
        self.audio_opts += mapping

        path = '%s%s' % (os.path.join(basedir, basename), '.flv')
        self.add_output_file(path)

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
            raise FFmpegWorkerException('MPEG-2 PS does not support audio codec: %s' % acodec)

        if vcodec not in ['mpeg1video', 'mpeg2video']:
            raise FFmpegWorkerException('MPEG-2 PS does not support video codec: %s' % vcodec)

        self.video_opts += [('-map', '0:v')]
        self.format_opts += [('-f', 'vob')]

        filter_chain, mapping = self.get_audio_layout_mapping(avinfo, 2)
        if filter_chain:
            self.audio_filter_chain += [('audio_mapping', filter_chain)]
        self.audio_opts += mapping

        path = '%s%s' % (os.path.join(basedir, basename), '.mpg')
        self.add_output_file(path)

    def mux_mpeg4(self, basedir, options=None):
        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        basename = os.path.splitext(os.path.basename(self.input_files[0].path))[0]
        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No AVInfo specified for input fi1e: %s' % self.input_files[0].path)

        self.video_opts += [('-map', '0:v')]
        self.format_opts += [('-f', 'mp4')]

        filter_chain, mapping = self.get_audio_layout_mapping(avinfo, 2)
        if filter_chain:
            self.audio_filter_chain += [('audio_mapping', filter_chain)]
        self.audio_opts += mapping

        path = '%s%s' % (os.path.join(basedir, basename), '.mp4')
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
            raise FFmpegWorkerException('MXF only supports audio at 48000Hz')

        self.video_opts += [('-map', '0:v')]

        mxf_format = 'mxf'
        channels_per_stream = 0
        if mapping == 'rdd9':
            channels_per_stream = 1
        elif mapping == 'd10':
            channels_per_stream = 8
            mxf_format = 'mxf_d10'

        self.format_opts += [('-f', mxf_format)]

        filter_chain, mapping = self.get_audio_layout_mapping(avinfo, channels_per_stream)
        if filter_chain:
            self.audio_filter_chain += [('audio_mapping', filter_chain)]
        self.audio_opts += mapping

        path = '%s%s' % (os.path.join(basedir, basename), '.mxf')
        self.add_output_file(path)

    def mux_mov(self, basedir, options=None):
        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        basename = os.path.splitext(os.path.basename(self.input_files[0].path))[0]
        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No avinfo specified for input fi1e: %s' % self.input_files[0].path)

        self.video_opts += [('-map', '0:v')]
        if self.mov_imx_header:
            self.video_opts += [('-vbsf', 'imxdump')]
        self.audio_opts += [('-map', '0:a')]
        self.format_opts += [('-f', 'mov')]

        path = '%s%s' % (os.path.join(basedir, basename), '.mov')
        self.add_output_file(path)

    def mux_gxf(self, basedir, options=None):
        if not self.input_files:
            raise FFmpegWorkerException('No input file specified')

        basename = os.path.splitext(os.path.basename(self.input_files[0].path))[0]
        avinfo = self.input_files[0].avinfo
        if not avinfo:
            raise FFmpegWorkerException('No avinfo specified for input fi1e: %s' % self.input_files[0].path)

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
            raise FFmpegWorkerException('SD Letterboxing only supports input at PAL or NTSC resolutions')

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
