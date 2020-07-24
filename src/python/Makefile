INSTALL=install

prefix  ?= /usr/local
bindir  ?= $(prefix)/bin
mandir  ?= $(prefix)/share/man
srcdir  ?= $(prefix)/src


PYLIB  ?= $(shell python3 -c 'import distutils.sysconfig;  print (distutils.sysconfig.get_python_lib())')

.PHONY: all
all: 

.PHONY: clean
clean: 

.PHONY: install
install:
	$(INSTALL) rtsl -D -m 755 $(DESTDIR)${bindir}/rtsl
