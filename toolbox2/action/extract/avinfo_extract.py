import os
import os.path
import re

from toolbox2.action import Action, ActionException
from toolbox2.worker.ffprobe import FFprobeWorker
from toolbox2.worker.ffmpeg import FFmpegWorker


class AVInfo(object):

    RES_SD_PAL = "720x576"
    RES_SD_PAL_VBI = "720x608"
    RES_SD_NTSC = "720x480"
    RES_SD_NTSC_VBI = "720x512"
    RES_HD = "1920x1080"
    RES_HD_1280 = "1280x1080"
    RES_HD_1440 = "1440x1080"

    FPS_PAL = [25, 50]
    FPS_NTSC = [29.97, 30, 59.94, 60]
    FPS_FILM = [23.97, 23.98, 24]

    def __init__(self, data):
        self.data = data
        self.audio_format = None
        self.video_res = None
        self.video_has_vbi = False
        self.video_fps = 0
        self.video_dar = "16:9"
        self.timecode = "00:00:00:00"
        self.video_streams = []
        self.audio_streams = []
        self.data_streams = []
        self.format = data["format"]

        for stream in data["streams"]:
            if stream["codec_type"] == "video":
                self.video_streams.append(stream)
            elif stream["codec_type"] == "audio":
                self.audio_streams.append(stream)
            else:
                self.data_streams.append(stream)

        self._init_res()
        self._init_fps()
        self._init_pix_fmt()
        self._init_dar()
        self._init_timecode()
        self._init_audio_format()

    def _init_res(self):
        if self.video_streams:
            self.video_res = "%sx%s" % (
                self.video_streams[0]["width"],
                self.video_streams[0]["height"],
            )

        if self.video_res in [self.RES_SD_PAL_VBI, self.RES_SD_NTSC_VBI]:
            self.video_has_vbi = True

    def _init_fps(self):
        if not self.video_streams:
            return

        match = re.match(r"(\d+)/(\d+)", self.video_streams[0]["r_frame_rate"])
        if match:
            (num, den) = match.groups()
            self.video_fps = round(float(num) / float(den), 2)

    def _init_pix_fmt(self):
        if self.video_streams:
            self.pix_fmt = self.video_streams[0]["pix_fmt"]

    def _init_dar(self):
        if not self.video_streams:
            return

        if "display_aspect_ratio" in self.video_streams[0]:
            self.video_dar = self.video_streams[0]["display_aspect_ratio"]

    def _init_timecode(self):
        self.timecode = "00:00:00:00"
        metadata = self.format.get("tags", {})
        if "timecode" in metadata:
            self.timecode = metadata["timecode"]
        elif "timecode_at_mark_in" in metadata:
            self.timecode = metadata["timecode_at_mark_in"]
        elif len(self.video_streams) > 0 and "timecode" in self.video_streams[0]:
            self.timecode = self.video_streams[0]["timecode"]
        else:
            for stream in self.data_streams:
                stream_metadata = stream.get("tags", {})
                if "timecode" in stream_metadata:
                    self.timecode = stream_metadata["timecode"]
                    break

    def _init_audio_format(self):
        if not self.audio_streams:
            return

        match = re.match("pcm_(.*)", self.audio_streams[0]["codec_name"])
        if match:
            self.audio_format = match.groups()[0]

    def video_has_VBI(self):
        return self.video_has_vbi

    def video_is_SD_PAL(self):
        return self.video_res in [self.RES_SD_PAL, self.RES_SD_PAL_VBI]

    def video_is_SD_NTSC(self):
        return self.video_res in [self.RES_SD_NTSC, self.RES_SD_NTSC_VBI]

    def video_is_HD(self):
        # We consider anything bigger than 1280x1080 as HD
        width, height = self.video_res.split("x")
        if int(width) * int(height) >= 1280 * 1080:
            return True
        else:
            return False

    def video_is_SD(self):
        return not self.video_is_HD()

    def __repr__(self):
        return "AVInfo (video_res=%s, video_has_vbi=%s, timecode=%s)" % (
            self.video_res,
            self.video_has_vbi,
            self.timecode,
        )


class AVInfoActionException(ActionException):
    pass


class AVInfoAction(Action):
    """
    Extract audio/video information from media files using ffprobe/ffmpeg.
    """

    name = "avinfo_extract"
    engine = "ffmpeg"
    category = "extract"
    description = "audio/video information extract tool"
    required_params = {}

    def __init__(self, log, base_dir, _id, params=None, resources=None):
        Action.__init__(self, log, base_dir, _id, params, resources)
        self.input_file = None
        self.thumbnail = None
        self.probe_worker = None
        self.probe2_worker = None
        self.ffmpeg_worker = None

        if not os.path.isdir(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        self.do_thumbnail = self.params.get("thumbnail", False)
        self.do_count_frames = self.params.get("count_frames", False)
        self.do_count_packets = self.params.get("count_packets", False)

        self.thumbnail_options = {
            "width": int(self.params.get("thumbnail_width", 0)),
        }

    def _setup(self):
        self.input_file = self.get_input_resource(1).get("path")
        self.thumbnail = os.path.join(self.tmp_dir, "thumbnail.jpg")

    def _execute(self, callback=None):
        self.probe_worker = self._new_worker(FFprobeWorker)
        self.probe_worker.add_input_file(self.input_file)
        self.workers.append(self.probe_worker)
        self.worker_idx = 0
        self._execute_current_worker(callback)
        self.update_metadata(self.probe_worker.metadata)
        avinfo = AVInfo(self.probe_worker.metadata)

        has_video_streams = len(avinfo.video_streams) > 0

        if has_video_streams and self.do_thumbnail:
            self.ffmpeg_worker = self._new_worker(FFmpegWorker)
            self.ffmpeg_worker.add_input_file(self.input_file, {}, avinfo)
            self.ffmpeg_worker.add_output_file(self.thumbnail)
            self.ffmpeg_worker.make_thumbnail(self.thumbnail_options)

            self.workers.append(self.ffmpeg_worker)
            self.worker_idx = 1
            self._execute_current_worker(callback)
            self.update_metadata({"thumbnail": self.thumbnail})
            self.add_output_resource("thumbnail", self.thumbnail)

        if has_video_streams and (self.do_count_frames or self.do_count_packets):
            self.probe2_worker = self._new_worker(FFprobeWorker)
            self.probe2_worker.add_input_file(self.input_file)
            if self.do_count_packets:
                self.probe2_worker.count_packets()
            if self.do_count_frames:
                self.probe2_worker.count_frames()

            self.workers.append(self.probe2_worker)
            self.worker_idx = 2
            self.workers.append(self.probe2_worker)
            self._execute_current_worker(callback)
            self.update_metadata(self.probe2_worker.metadata)

        self.progress = 100
        self._callback(callback)

    def _finalize(self):
        pass

    def run(self, callback=None):
        Action.run(self, callback)
        return AVInfo(self.get_metadata())
