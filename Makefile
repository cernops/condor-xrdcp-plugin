SPECFILE            = condor-xrdcp-plugin.spec
SOURCE_NAME         = condor-xrdcp-plugin
SPECFILE_VERSION    = $(shell awk '$$1 == "Version:"  { print $$2 }' $(SPECFILE) )
SPECFILE_RELEASE    = $(shell awk '$$1 == "Release:"  { print $$2 }' $(SPECFILE) )
TARFILE             = $(SOURCE_NAME)-$(SPECFILE_VERSION).tar.gz
DIST               ?= $(shell rpm --eval %{dist})

sources:
	tar -zcvf $(TARFILE) --exclude-vcs --transform 's,^,$(SOURCE_NAME)-$(SPECFILE_VERSION)/,' src/*

clean:
	rm -rf build/ $(TARFILE)

srpm: sources
	rpmbuild -bs --define 'dist $(DIST)' --define "_topdir $(PWD)/build" --define '_sourcedir $(PWD)' $(SPECFILE)

rpm: sources
	rpmbuild -bb --define 'dist $(DIST)' --define "_topdir $(PWD)/build" --define '_sourcedir $(PWD)' $(SPECFILE)
