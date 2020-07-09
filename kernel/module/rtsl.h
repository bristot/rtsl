/* SPDX-License-Identifier: GPL-2.0 */
#undef TRACE_SYSTEM
#define TRACE_SYSTEM rtsl

#if !defined(_RT_SCHED_LATENCY_TRACE_H) || defined(TRACE_HEADER_MULTI_READ)
#define _RT_SCHED_LATENCY_TRACE_H

#include <linux/tracepoint.h>

TRACE_EVENT(irq_execution,

	TP_PROTO(int vector, u64 start, u64 duration),

	TP_ARGS(vector, start, duration),

	TP_STRUCT__entry(
		__field(	int,		vector	)
		__field(	u64,		start	)
		__field(	u64,		duration)
	),

	TP_fast_assign(
		__entry->vector = vector;
		__entry->start = start;
		__entry->duration = duration;
	),

	TP_printk("IRQ %d: start %llu duration %llu",
		__entry->vector,
		__entry->start,
		__entry->duration)
);

TRACE_EVENT(nmi_execution,

	TP_PROTO(u64 start, u64 duration),

	TP_ARGS(start, duration),

	TP_STRUCT__entry(
		__field(	u64,		start	)
		__field(	u64,		duration)
	),

	TP_fast_assign(
		__entry->start = start;
		__entry->duration = duration;
	),

	TP_printk("NMI: start %llu duration %llu",
		__entry->start,
		__entry->duration)
);

DECLARE_EVENT_CLASS(window,

	TP_PROTO(u64 value),

	TP_ARGS(value),

	TP_STRUCT__entry(
		__field(	u64,		value	)
        ),

	TP_fast_assign(
		__entry->value = value;
	),

	TP_printk("%llu", __entry->value)
);

DEFINE_EVENT(window, poid,

	TP_PROTO(u64 value),

	TP_ARGS(value)
);

DEFINE_EVENT(window, max_poid,

	TP_PROTO(u64 value),

	TP_ARGS(value)
);

DEFINE_EVENT(window, psd,

	TP_PROTO(u64 value),

	TP_ARGS(value)
);

DEFINE_EVENT(window, max_psd,

	TP_PROTO(u64 value),

	TP_ARGS(value)
);

DEFINE_EVENT(window, dst,

	TP_PROTO(u64 value),

	TP_ARGS(value)
);

DEFINE_EVENT(window, max_dst,

	TP_PROTO(u64 value),

	TP_ARGS(value)
);

DEFINE_EVENT(window, paie,

	TP_PROTO(u64 value),

	TP_ARGS(value)
);

DEFINE_EVENT(window, max_paie,

	TP_PROTO(u64 value),

	TP_ARGS(value)
);

#endif /* _TRACE_LATENCY_H */

/* This part ust be outside protection */
#undef TRACE_INCLUDE_PATH
#define TRACE_INCLUDE_PATH .
#define TRACE_INCLUDE_FILE rtsl
#include <trace/define_trace.h>
