INSTALL=install

PERF_CORE ?= /usr/libexec/perf-core

.PHONY: all
all: 

.PHONY: clean
clean:

.PHONY: install
install:
	$(INSTALL) -d -m 755 $(DESTDIR)$(PERF_CORE)/scripts/python/bin/
	$(INSTALL) latency_analysis.py $(DESTDIR)$(PERF_CORE)/scripts/python/
	$(INSTALL) rtsl-record $(DESTDIR)$(PERF_CORE)/scripts/python/bin/
	$(INSTALL) rtsl-report $(DESTDIR)$(PERF_CORE)/scripts/python/bin/
	@# The lines bellow would install the perf script that parses the database
	@# But that is not needed because c plugin is working fine...
	@#$(INSTALL) -d -m 755 $(DESTDIR)/usr/lib64/rtsl/python/
	@#$(INSTALL) perf_report_script.py  $(DESTDIR)/usr/lib64/rtsl/python/perf_report_script.py
