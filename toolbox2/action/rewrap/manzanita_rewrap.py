# -*- coding: utf-8 -*-

import os

from toolbox2.action import Action, ActionException
from toolbox2.action.extract.avinfo_extract import AVInfoAction
from toolbox2.worker.manzanita import ManzanitaMuxWorker
from toolbox2.worker.ffmpeg import FFmpegWorker


class ManzanitaRewrapException(ActionException):
    pass


class ManzanitaRewrapAction(Action):

    name = "manzanita_rewrap"
    engine = "manzanita"
    category = "rewrap"
    description = "Manzanita rewrap tool"
    required_params = {}

    def __init__(self, log, base_dir, _id, params=None, resources=None):
        Action.__init__(self, log, base_dir, _id, params, resources)
        self.input_file = None
        self.output_file = None

        if "manzanita" not in self.params:
            self.params["manzanita"] = {}

        if "global" not in self.params["manzanita"]:
            self.params["manzanita"]["global"] = {}

        if "stream" not in self.params["manzanita"]:
            self.params["manzanita"]["stream"] = {}

        if "video" not in self.params["manzanita"]["stream"]:
            self.params["manzanita"]["stream"]["video"] = {}

        if "audio" not in self.params["manzanita"]["stream"]:
            self.params["manzanita"]["stream"]["audio"] = {}

    def _setup(self):
        self.input_file = self.get_input_resource(1).get("path")
        if not self.input_file:
            raise ManzanitaRewrapException("No path specified for input (index = 1)")
        nb_video_frames = int(self.get_input_resource(1).get("nb_video_frames", 0))

        # Compute tmp output path
        filename = os.path.basename(self.input_file)
        filename, _ = os.path.splitext(filename)
        extension = ".ts"
        try:
            extension = self.get_output_resource(1).get("extension", ".ts")
        except ActionException:
            # Silent exception is file does not exist
            pass
        output_filename = "%s%s" % (filename, extension)

        self.output_file = os.path.join(self.tmp_dir, output_filename)
        self.add_output_resource(1, {"path": self.output_file})

        avinfo_action = AVInfoAction(self.log, self.base_dir, self.id)
        avinfo_action.add_input_resource(1, {"path": self.input_file})
        avinfo = avinfo_action.run()

        # Setup ffmpeg demuxer
        ffmpeg = self._new_worker(FFmpegWorker)
        ffmpeg.add_input_file(self.input_file, {}, avinfo)
        ffmpeg.set_nb_frames(nb_video_frames)
        ffmpeg.demux(self.tmp_dir)

        # Setup mp2tsms muxer
        mp2tsms = self._new_worker(
            ManzanitaMuxWorker, self.params["manzanita"]["global"]
        )

        indexes = {"audio": 0, "video": 0}
        for output in ffmpeg.output_files:
            if output.type not in ["audio", "video"]:
                continue
            index = str(indexes[output.type] + 1)
            params = self.params["manzanita"]["stream"][output.type].get(index, {})
            params["type"] = output.type
            mp2tsms.add_input_file(output.path, params)
            indexes[output.type] += 1

        mp2tsms.add_output_file(self.output_file)

        # Add demuxing and muxing workers to worker list
        self.workers.append(ffmpeg)
        self.workers.append(mp2tsms)

    def _finalize(self):
        pass
