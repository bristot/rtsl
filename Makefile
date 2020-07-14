MAKE=make

.PHONY: all
all: make_rtsl make_trace

.PHONY: install
install: make_rtsl_install make_trace_install

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

# -------------------- user-space: trace -------------------- 
.PHONY: make_trace
make_trace: make_rtsl
	$(MAKE) -C src/trace_plugin

.PHONY: make_trace_install
make_trace_install: make_trace make_rtsl_install
	$(MAKE) -C src/trace_plugin install

.PHONY: clean
clean:
	$(MAKE) -C src/ clean
	$(MAKE) -C kernel/module clean
