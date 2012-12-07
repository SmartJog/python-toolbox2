dist_man1_MANS = toolbox2.man toolbox2-transcode.man

CLEANFILES = $(dist_man1_MANS)
EXTRA_DIST = $(wildcard $(srcdir)/*.t2t)

SUFFIXES = .t2t

.t2t.man:
	$(TXT2TAGS) -o $@ $<
