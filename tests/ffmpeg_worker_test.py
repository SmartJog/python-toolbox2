#!/usr/bin/python                                                                                                                         
# -*- coding: utf-8 -*-

"""Test file for the FFmpeg worker"""

import os
import logging
import unittest

from toolbox2.worker.ffmpeg import FFmpegWorker
from toolbox2.action.extract.avinfo_extract import AVInfo


class FfmpegWorkerTestCase(unittest.TestCase):
    """Test functions from the toolbox2.worker.FFmpegWorker class"""

    def setUp(self):
        logger = logging.getLogger('toolbox2_test')
        logger.setLevel(logging.DEBUG)
        self.ffw = FFmpegWorker(logger)
        # Create a basic AVInfo object, it may be modified in individual tests
        self.avinfo = AVInfo({'format': {}, 'streams': []})

    def test_prores_bitrate_lookup_existing(self):
        """Test the _prores_bitrate_lookup function

        Simple, existing, lookup.
        """
        self.avinfo.video_res = '1280x720'
        self.avinfo.video_fps = '29.97'
        self.assertEqual(self.ffw._prores_bitrate_lookup(self.avinfo, 'hq'),
                         '110M',
                         'The looked-up bitrate is wrong.')

    def test_prores_bitrate_lookup_approximate(self):
        """Test the _prores_bitrate_lookup function

        Test the approximate lookup.
        """
        # This should fallback to 720x486 @ 25.0
        self.avinfo.video_res = '320x240'
        self.avinfo.video_fps = '24'
        self.assertEqual(self.ffw._prores_bitrate_lookup(self.avinfo, 'lt'),
                         '24M',
                         'The looked-up bitrate is wrong.')

if __name__ == '__main__':
    unittest.main()  # run all tests
