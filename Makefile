MAKE=make

.PHONY: all
all: make_rtsl make_ftrace make_perf

.PHONY: install
install: make_rtsl_install make_perf_install make_ftrace_install

# -------------------- kernel module -------------------- 
.PHONY: module
module:
	$(MAKE) -C kernel/module 

.PHONY: module_install
module_install:
	$(MAKE) -C kernel/module install

# -------------------- user-space -------------------- 
.PHONY: make_rtsl
make_rtsl:
	$(MAKE) -C src/python


.PHONY: make_rtsl_install
make_rtsl_install:
	$(MAKE) -C src/python install

# -------------------- user-space: perf -------------------- 
.PHONY: make_perf
make_perf: make_rtsl
	$(MAKE) -C src/perf

.PHONY: make_perf_install
make_perf_install: make_perf make_rtsl_install
	$(MAKE) -C src/perf install

# -------------------- user-space: ftrace -------------------- 
.PHONY: make_ftrace
make_ftrace: make_rtsl
	$(MAKE) -C src/trace_plugin

.PHONY: make_ftrace_install
make_ftrace_install: make_ftrace make_rtsl_install
	$(MAKE) -C src/trace_plugin install

.PHONY: clean
clean:
	$(MAKE) -C src/ clean
	$(MAKE) -C kernel/module clean
