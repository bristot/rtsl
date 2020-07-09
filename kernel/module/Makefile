ifneq ($(KERNELRELEASE),)
	obj-m +=  rtsl.o
CFLAGS_rtsl.o = -I$(src)
else
	KERNELDIR ?=  /lib/modules/`uname -r`/build/
	PWD := $(shell pwd)
default:
	$(MAKE) -C $(KERNELDIR) M=$(PWD) modules

clean:
	$(MAKE) -C $(KERNELDIR) M=$(PWD) clean

install:
	$(MAKE) -C $(KERNELDIR) M=$(PWD) modules_install

endif
