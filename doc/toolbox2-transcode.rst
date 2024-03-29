==================
toolbox2-transcode
==================

-------------------------------------
CLI for the toolbox2 transcode action
-------------------------------------

:Authors: Written an maintained by the good folks at the CJI company
:Version: 0.10.0
:Date: |date|
:Copyright: LGPL2+
:Manual section: 1
:Manual group: Toolbox2 Manual

.. |date| date::

SYNOPSIS
========

toolbox2-transcode [OPTIONS] input

DESCRIPTION
===========

The **toolbox2-transcode** command offers a conveniant interface for Toolbox2 transcode actions.

OPTIONS
=======

--**count-packets**
  Enable packet counting and thus transcode progress.

--**tmp-path** path
  Path of the temporary directory used to store output files.

--**container** container
  Container type: mxf, mov, mp4, flv.

--**container-reference**
  Enable container reference files. This option is only valid for mov and mxf with the omneon muxer.

--**container-hinting**
  Enable container hinting for streaming. This option is only valid for mov, mp4 and flv containers.

--**container-mapping** mapping
  Container mapping: default, d10, rdd9.

--**container-version** version
  Container version: qt6, qt7. This option is only valid for mov with the omneon muxer.

--**video-codec** codec
  Video codec: mpeg2video, imx, xdcamhd, dnxhd, simple_h264, prores.

--**prores-profile** profile
  Only used if **--video-codec** is set to prores: proxy (default), lt, standard or hq.

--**video-bitrate** bitrate
  Video bitrate in kbit/s.

--**video-pix-fmt** pix_fmt
  Video pixel format: yuv411p, yuv420p, yuv422p, yuv422p10le.

--**video-letterbox**
  Enable video letterboxing. This option override video_aspect_ratio and should only be valid for 16/9 SD content.

--**video-aspect-ratio** aspect_ratio
  Video aspect ratio: default, copy, 4:3, 16:9, ...
  "default" tries to chose between 4:3 and 16:9 depending on the input file.
  "copy" reuses the input file aspect ratio.

--**video-gop-size** gop_size
  Video gop size: 12, 15, ... This option is only valid for the mpeg2video and xdcamhd codecs.

--**video-closed-gop**
  Force closed gop. This option is only valid for the mpeg2video and xdcamhd codecs.

--**video-interlaced** interlaced
  Enable interlaced mode: 0, 1.

--**video-resolution** resolution
  Force output resolution. This option is only valid for the simple_h264 codec.

--**video-burn**
  Enable text and timecode burning.

--**video-burn-box**
  Add a black background.

--**video-burn-text** text
  Burn specified text.

--**video-burn-date**
  Add the date to the burned text.

--**video-burn-hostname**
  Add the hostname to the burned text.

--**video-burn-timecode**
  Enable timecode burning.

--**video-burn-position** position
  Burning position: center, top-left, top-center, top-right, bottom-left, [...], <x>x<y> (eg. '1337x42').

--**video-burn-fontsize** fontsize
  Burn font size.

--**video-burn-fontname** fontname
  Burn font name: dejavu, vera (same as dejavu), liberation, arial (same as liberation).

--**video-burn-padding** padding
  Burn padding in pixel: 10, ...

--**audio-codec** codec
  Audio codec: pcm, aac.

--**audio-bitrate** bitrate
  Audio bitrate in kbit/s.

--**audio-format** format
  Audio format for pcm codecs: s16le, s16be, s24le, ...

--**audio-sample-rate** sample_rate
  Audio sample rate: 44100, 48000, 96000, ...

--**audio-min-streams** min_streams
  List of audio min streams to align to: '2, 4, 8', '4, 8', ...

--**audio-channels-per-stream** channels
  Audio channels per streams: 0, 1, 2, ...

--**muxer** muxer
  Muxing library to use: ffmpeg, omneon, bmx.

--**decoding-threads** thread_count
  How many threads should be used to decode.

--**encoding-threads** thread_count
  How many threads should be used to encode.

--**single-frame**
  Extract a single frame (output a .jpg).

--**seek** seconds
  Start the transcode from a specified offset.


EXAMPLES
========

**imx50/mxf pcm @ 24bit muxed by bmx**
  toolbox2-transcode --video-codec imx --video-bitrate 50000 --container mxf --container-mapping d10 --audio-format s24le --muxer bmx input.mxf


**dnxhd/mxf 220mbp 1920x1080i 29.97fps 10bit pcm @ 24bit muxed by ffmpeg**
  toolbox2-transcode --video-codec dnxhd --video-bitrate 220000 --video-pix-fmt yuv422p10le --container mxf --audio-format s24le input.mov

**Preview of a burned text at the 10th second**
  toolbox2-transcode --seek=10 --single-frame --video-burn --video-burn-date --video-burn-hostname --video-burn-timecode input.mpg
