.PHONY: all
all:
	make -C perf
	make -C python
	make -C trace_plugin

install:
	make -C perf install
	make -C python install
	make -C trace_plugin install

clean:
	make -C perf clean
	make -C python clean
	make -C trace_plugin clean
