from __future__ import print_function

import os
import sys

sys.path.append(os.environ['PERF_EXEC_PATH'] + \
	'/scripts/python/Perf-Trace-Util/lib/Perf/Trace')

from perf_trace_context import *
from Core import *

import rt_sched_latency

config_memory=False

rtsl=None

def trace_begin():
    global rtsl

    try:
        db_name=os.environ["RTSL_RECORD_DB"]
    except:
        db_name="trace.rtsl"

    if config_memory:
        rtsl=rt_sched_latency.Rtsl('perf', database_file=":memory:")
    else:
        rtsl=rt_sched_latency.Rtsl('perf', database_file=db_name)


def trace_end():
    rtsl.create_database_cache()
    rtsl.process_results()
    try:
        rtsl.plot_results()
    except Exception as e:
        print('Error: '+ str(e))

def rtsl__max_psd(event_name, context, common_cpu, common_secs,
                            common_nsecs, common_pid, common_comm,
                            common_callchain, value, perf_sample_dict):

    rtsl.record_max_ps_disable(common_cpu, value)

def rtsl__max_dst(event_name, context, common_cpu, common_secs,
                            common_nsecs, common_pid, common_comm,
                            common_callchain, value, perf_sample_dict):

    rtsl.record_max_dst_disable(common_cpu, value)

def rtsl__max_paie(event_name, context, common_cpu, common_secs,
                            common_nsecs, common_pid, common_comm,
                            common_callchain, value, perf_sample_dict):

    rtsl.record_max_paie_disable(common_cpu, value)


def rtsl__max_poid(event_name, context, common_cpu, common_secs,
                             common_nsecs, common_pid, common_comm,
                             common_callchain, value, perf_sample_dict):
    rtsl.record_max_poi_disable(common_cpu, value)

def rtsl__nmi_execution(event_name, context, common_cpu, common_secs,
                           common_nsecs, common_pid, common_comm,
                           common_callchain, start, duration, perf_sample_dict):

    rtsl.record_nmi_execution(common_cpu, start, duration)

def rtsl__irq_execution(event_name, context, common_cpu, common_secs,
                           common_nsecs, common_pid, common_comm,
                           common_callchain, vector, start, duration,
                           perf_sample_dict):
    rtsl.record_irq_execution(common_cpu, vector, start, duration)
