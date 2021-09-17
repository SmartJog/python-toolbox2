========
toolbox2
========

--------------------------------
Test and use the toolbox2 module
--------------------------------

:Authors: Written an maintained by the good folks at the CJI company
:Version: 0.10.0
:Date: |date|
:Copyright: LGPL2+
:Manual section: 1
:Manual group: Toolbox2 Manual


.. |date| date::


SYNOPSIS
========

toolbox2 --path input.json

DESCRIPTION
===========

The toolbox2 command is a simple tool to test and use the toolbox2 Python module.

OPTIONS
=======

-**p**, --**path**
  Path of the file containing a json encoded action description.


JSON
====

Long story short, here is the needed json to launch the default transcode
action on a file:

::

  {
      "action": "transcode",
      "params": {},
      "resources": {
          "inputs": {
              "1": {"path": "/path/to/the/file.mov"}
          }
      }
  }


Multiple input files can be passed (which explains the "1" in the "inputs"
section).

Pass all your parameters in the "params" section.
An example of such a modified section could be:

::

  {
      "video_codec": "dv",
      "audio_codec": "copy",
      "video_burn": "1",
      "video_burn_timecode": "1",
      "encoding_threads": "8"
  }


