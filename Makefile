# This stub Makefile is here to convince Jenkins to run our tests. The exported
# tarball does not include this file because .gitattributes instructs
# git-archive to exclude it.
.PHONY: all distcheck

all:

distcheck:
	py.test-3 -v
	git archive --format=tgz --prefix=$(distdir)/ HEAD > $(distdir).tar.gz
