toolbox2dir = $(pyexecdir)/toolbox2
nobase_toolbox2_PYTHON = \
	__init__.py \
	command.py \
	exception.py \
	action/extract/__init__.py \
	action/extract/avinfo_extract.py \
	action/extract/kttoolbox_extract.py \
	action/rewrap/__init__.py \
	action/rewrap/manzanita_rewrap.py \
	action/transcode/__init__.py \
	action/transcode/transcode.py \
	worker/__init__.py \
	worker/bmx.py \
	worker/flvtools2.py \
	worker/ffmpeg.py \
	worker/ffprobe.py \
	worker/kttoolbox.py \
	worker/manzanita.py \
	worker/omneon.py \
	worker/qtfaststart.py \
	worker/videoparser.py

nobase_nodist_toolbox2_PYTHON = action/__init__.py

edit = $(SED) \
	-e 's|@sysconfdir[@]|$(sysconfdir)|g'

$(nobase_nodist_toolbox2_PYTHON): $(nobase_nodist_toolbox2_PYTHON:=.in) Makefile
	$(edit) $(srcdir)/$@.in > $(builddir)/$@

BUILT_SOURCES = $(nobase_nodist_toolbox2_PYTHON)
EXTRA_DIST = $(nobase_nodist_toolbox2_PYTHON:=.in)
