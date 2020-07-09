INSTALL=install

all: plugin_rtsl.so

plugin_rtsl.o: plugin_rtsl.c
	$(CC) -g -Wall -fPIC -D_GNU_SOURCE -Iinclude/traceevent/ -c -o plugin_rtsl.o plugin_rtsl.c

plugin_rtsl.so: plugin_rtsl.o
	$(CC) -shared -lsqlite3 -o plugin_rtsl.so plugin_rtsl.o

.PHONY: install_local
install_local: all
	$(INSTALL) plugin_rtsl.so -D -m 644 ~/.local/lib/traceevent/plugins/plugin_rtsl.so
	$(INSTALL) plugin_rtsl.so -D -m 644 ~/.trace-cmd/plugins/plugin_rtsl.so

.PHONY: install
install: all
	$(INSTALL) plugin_rtsl.so -D -m 644 $(DESTDIR)/usr/lib64/traceevent/plugins/plugin_rtsl.so
	$(INSTALL) plugin_rtsl.so -D -m 644 $(DESTDIR)/usr/lib64/trace-cmd/plugins/plugin_rtsl.so

.PHONY: clean
clean:
	@test ! -f plugin_rtsl.so || rm plugin_rtsl.so
	@test ! -f plugin_rtsl.o || rm plugin_rtsl.o
