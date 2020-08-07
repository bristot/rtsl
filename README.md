# rtsl

*WARN: This is still a proof-of-concept tool*

rtsl stands for Real-Time Linux Scheduling Latency. The background of this tool is presented in the paper:

  D. B. de Oliveira, D. Casini, R. S. de Oliveira, T. Cucinotta. "Demystifying the Real-Time Linux Scheduling Latency," in Proceedings of the 32nd Euromicro Conference on Real-Time Systems (ECRTS 2020), July 7-10, 2020, Modena, Italy.

In this paper, a theoretically sound bound for the real-time Linux scheduling latency is presented. To find more about the paper, visit the [paper's companion page](https://bristot.me/demystifying-the-real-time-linux-latency/).

## Installation

The `rtsl` is a tookit, and has a  _kernel_ component and a _user-space_ component.

### rtsl tracer

This user-space tool depends on `rtsl tracer` in the kernel. The `rtsl tracer` parses the kernel events, translating them into the variables used in the theorem presented in the paper, exporting the values via `tracepoints.`

You can apply yourself the patches present in [kernel_patches](kernel/kernel_patches/), or use [the kernel available here](https://github.com/bristot/linux-rt-rtsl/tree/linux-5.6.y-rt-rtsl). Either way, the kernel needs to be compiled with the `FULLY_PREEMPTIVE` mode (a.k.a. PREEMPT_RT), and the `rtsl` tracer. To do so, on the kernel configuration menu, you need to select:

```
  General Setup -> Configure standard kernel features (expert users) (NEW)
  General Setup -> Fully Preemptible Kernel (Real-Time)
  Kernel hacking -> Tracers -> Real-time Linux Scheduling Latency Tracer (NEW)
```

#### I am lazy, how can I easily compile this kernel?

On a Fedora 32 box, in the directory of a patched kernel, I run:

```
# make localmodconfig
```

Then select the kernel options as mentioned above options and compile it, as easy as this. It works for me.

### rtsl tool

The [rtsl tool](src/python/rtsl/) runs in user-space. It is a python program that automates the tracing and analysis of the data. It depends on:

 - trace-cmd or perf
 - python3
 - sqlite3
 - python-matplotlib (to plot charts)
 - BCC (to run the stats command)

It also depends on a `trace-plugin` to speed up the trace parser.

#### Trace plugin

The trace-plugin is a `C` program used by perf/trace-cmd to convert the trace into a `sqlite3` database used in the analysis.

#### Installing the rtsl tool

Inside the [src directory](src/), run:

```
make
make install
```

## Usage

The rtsl tool has three modes:
 - record
 - report
 - stats
 
### Record mode

In the *record mode*, the kernel is traced, collecting the value for the thread variables and the IRQ/NMI execution. The tool uses *trace-cmd* or *perf* to collect data (the *trace-cmd* is used by default, to use *perf*, add the cmd-line option `--tracer=perf`).

As an example of usage, the command line for tracing the system for 2 minutes is:

```
rtsl record -d 2m
```

The trace file will be saved in the `rtsl_data` directory:

### Report mode

The report mode parses the trace data, transforming it into a `per-cpu` sqlite3 database in the `rtsl_data` directory. The database is then analyzed (in parallel), reporting the hypothetical latency using a giving interrupt characterization.

For example, the command line below will run the analysis, reporting the results.

```
[root@mundissa bristot]# rtsl report
  ==== Latency Analisyis! ==== 
	Time unit is nanosecods
	poid  = Preemption or Interrupt disabled [ not to schedule ] window
	paie  = Preemption and Interrupts enabled
	psd   = Preemption disabled to schedule window
	dst   = Delay of scheduling tail
	ifl   = Interference free latency
	INT   = Interrupts
	IRQ   = Maskable interrupts
	NMI   = Non-maskable interrupts
	oWCET = Observed Worst Case Execution Time
	oMIAT = Observed Minimun Inter-arrival Time

CPU:   0
	Interference Free Latency:
		  latency = max(     poid,       dst) +      paie +       psd
		   109453 = max(    56194,     45883) +      5167 +     48092
	Considering the worst interrupt burst (sliding window):
		Window: 109453
		       NMI:        0
		       125:    30522
		       236:    46687
		       246:     3463
		       251:    13735
		       252:    24572
		       253:    27098
		Window: 255530
		       236:    49321 <- new!
		Window: 258164
		Converged!
		Latency =    258164 with Sliding Window
[other cpus...]
```

The ```--help``` argument shows all available options for each command, for instance:

```
[root@mundissa bristot]# rtsl report --help
usage: rtsl report [-h] [--reparse] [--plot] [-N] [-W] [-E] [-P] [-S] [-O]

optional arguments:
  -h, --help            show this help message and exit
  --reparse             force re-parsing the trace file
  --plot                plot results
  -N, --irq_none        Latency without IRQs
  -W, --irq_worst_single
                        Latency with a single (worst) IRQs
  -E, --irq_worst_each  Latency with a single (worst) occurence of each IRQ
  -P, --irq_periodic    Latency with periodic/sporadic interrupts
  -S, --irq_sliding_window
                        Latency with sliding window with the worst busrt occurence of all IRQs
  -O, --irq_sliding_window_owcet
                        Latency with sliding window with the worst busrt occurence of all IRQs considering their oWCET
```

### Stats mode

The *stats* command uses eBPF/BCC to observe the value for the _thread variables_ at runtime. For example, the command:

```
rtsl stats poid
```

Will report a page like this, refreshing every second with new values:

```
Histogram for poid
y-axis = duration in us, x-axis = CPU, cell: times that a given y-duration happened on a x-CPU
              0         1         2         3         4         5         6         7        TOTAL
  1:       7826      4562     24006      8778      9630      1865      1028     17187 =      74882
  2:        444       214       156       151       491        99        34       161 =       1750
  3:        119        38        43        42       130        23         7        44 =        446
  4:         41        25        34        19        43        13         0        42 =        217
  5:         30        17        13         8        44         8         2        12 =        134
  6:          9         5         4         1        22         4         1         3 =         49
  7:         12         3         4         2        19         2         2         3 =         47
  8:         13         2         3         3        24         4         0         7 =         56
  9:          3         3         3         5         6         1         1         3 =         25
 10:          2        11         0         2         3         0         0         2 =         20
 11:          6         1         6        11         2         3         0         3 =         32
 12:          5         1         3         5         1         6         0         0 =         21
 13:          8         0         3         1         1         1         0         1 =         15
 14:          3         1         6         2         2         0         0         3 =         17
 15:          1         0         1         0         0         0         0         0 =          2
 16:          0         0         0         0         0         1         0         0 =          1
```

## FAQ

### Why sqlite3?

The trace analysis is not linear, and the tool needs to access the data back and forth. Considering that the traces can easily reach the tens of gigabytes order for a day-long trace, it is not possible to use the data in memory. `sqlite3` works out of the box.

### Why using a per-cpu database?

To process the data in parallel.

### Why python?

I like it, and it is straightforward to prototype using python.

### How much overhead does it add to the system

See [paper's FAQ in the companion page](http://bristot.me/demystifying-the-real-time-linux-latency/).

### Is this the end of cyclictest?

NO! See [FAQ in the companion page](http://bristot.me/demystifying-the-real-time-linux-latency/).
