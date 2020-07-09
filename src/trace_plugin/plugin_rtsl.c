// SPDX-License-Identifier: LGPL-2.1
/*
 * Copyright (C) 2020 Red Hat Inc, Daniel Bristot de Oliveira <bristot@redhat.com>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sqlite3.h>
#include <sys/stat.h>

#include "event-parse.h"
#include "trace-seq.h"

char *db_name = "trace.rtsl";

struct tep_plugin_option trace_rtsl_options[] = {
        {
                .name = "record_db",
                .plugin_alias = "rtsl",
                .description =
                "save the results in the sqlite database expected by rtsl",
		.set = 0,
        },
        {
                .name = NULL,
        }
};

static struct tep_plugin_option *option_record_db = &trace_rtsl_options[0];

/*
 * This is the internal option, to know if the DB is open and working.
 */
int recording_db = 0;

sqlite3 *db_connection;

/*
 * This is the option: Is it set to record?
 */
static int record_db(void)
{
	return option_record_db->set;
}

/*
 * This is the runtime: is the db recoding?
 */
static int db_recording(void)
{
	return recording_db;
}

#ifdef CALLBACK
static int callback(void *NotUsed, int argc, char **argv, char **col_name)
{
	int i;
	for (i = 0; i < argc; i++)
		printf("%s = %s\n", col_name[i], argv[i] ? argv[i] : "NULL");

	printf("\n");

	return 0;
}
#endif

int try_to_move_db(char *db_name)
{
	struct stat buffer;
	char new_name[128];

	if (stat(db_name, &buffer))
		return 0;
	snprintf(new_name, 128, "%s.old", db_name);

	if (!rename(db_name, new_name))
		return 0;

	printf("error moving the old database (%s), the database will not be created\n", db_name);

	return 1;
}

int __sql_exec(char *command)
{
	char *sqlite_error_msg = 0;
	int rc;

	rc = sqlite3_exec(db_connection, command, 0, 0, &sqlite_error_msg);

	if (rc != SQLITE_OK) {
		printf("SQL error: %s\n", sqlite_error_msg);
		sqlite3_free(sqlite_error_msg);
		sqlite3_close(db_connection);
		recording_db = 0;
		option_record_db->set = 0;
		return 1;
	}
	return 0;
}


int init_db(void)
{
	char *create_db_cmd = \
				"CREATE TABLE poid (cpu integer PRIMARY KEY, value integer);" 	\
				"CREATE TABLE paie (cpu integer PRIMARY KEY, value integer);"	\
				"CREATE TABLE psd (cpu integer PRIMARY KEY, value integer);"	\
				"CREATE TABLE dst (cpu integer PRIMARY KEY, value integer);" 	\
				"CREATE TABLE nmi (cpu integer, start_time integer PRIMARY KEY, duration integer);"	\
				"CREATE TABLE irq (cpu integer, vector integer, start_time integer PRIMARY KEY, duration integer);";
	char *pragma = "pragma journal_mode=wal;"\
		       	"pragma synchronous=0;";
	int rc;

	if (try_to_move_db(db_name))
		return 1;

	rc = sqlite3_open(db_name, &db_connection);

	if (rc != SQLITE_OK) {
		printf("Error opening db\n");
		return 1;
	}

	recording_db = 1;

	if (__sql_exec(create_db_cmd)) {
		printf("Error creating tables");
		goto out_error;
	}

	if (__sql_exec(pragma)) {
		printf("Error setting pragma");
		goto out_error;
	}

	return 0;

out_error:
	recording_db = 0;
	return 1;
}

int sql_exec(char *command)
{

	if (!record_db())
		return 0;

	if (!db_recording()) {
		if (init_db()) {
			/*
			 * If fails to create the db, disable the option.
			 */
			option_record_db->set = 0;
			return 0;
		}
	}

	return __sql_exec(command);
}


int sql_insert_variable(char *variable, int cpu, unsigned long long value)
{
	char insert[1024];

	if (!record_db())
		return 0;

	snprintf(insert, 1024, "INSERT OR REPLACE INTO %s VALUES (%d, %llu);",
				variable, cpu, value);

	return sql_exec(insert);
}

void close_db(void)
{
	sqlite3_close(db_connection);
}

static int print_handler(struct trace_seq *s, struct tep_record *record,
				struct tep_event *event)
{
	unsigned long long value;

	if (tep_get_field_val(s, event, "value", record, &value, 1))
		return trace_seq_putc(s, '!');

	trace_seq_printf(s, "%llu", value);

	return 0;

}

static int poid_handler(struct trace_seq *s, struct tep_record *record,
				struct tep_event *event, void *context)
{
	unsigned long long value;
	/* error handling */
	tep_get_field_val(s, event, "value", record, &value, 1);

	sql_insert_variable("poid", record->cpu, value);

	return print_handler(s, record, event);
}

static int paie_handler(struct trace_seq *s, struct tep_record *record,
				struct tep_event *event, void *context)
{
	unsigned long long value;
	/* error handling */
	tep_get_field_val(s, event, "value", record, &value, 1);

	sql_insert_variable("paie", record->cpu, value);
	return print_handler(s, record, event);
}

static int psd_handler(struct trace_seq *s, struct tep_record *record,
				struct tep_event *event, void *context)
{
	unsigned long long value;
	/* error handling */
	tep_get_field_val(s, event, "value", record, &value, 1);

	sql_insert_variable("psd", record->cpu, value);
	return print_handler(s, record, event);
}

static int dst_handler(struct trace_seq *s, struct tep_record *record,
				struct tep_event *event, void *context)
{
	unsigned long long value;
	/* error handling */
	tep_get_field_val(s, event, "value", record, &value, 1);

	sql_insert_variable("dst", record->cpu, value);
	return print_handler(s, record, event);
}

static int irq_handler(struct trace_seq *s, struct tep_record *record,
				struct tep_event *event, void *context)
{
	unsigned long long duration;
	unsigned long long vector;
	unsigned long long start;
	char insert[1024];

	if (tep_get_field_val(s, event, "vector", record, &vector, 1))
		return trace_seq_putc(s, '!');

	if (tep_get_field_val(s, event, "start", record, &start, 1))
		return trace_seq_putc(s, '!');

	if (tep_get_field_val(s, event, "duration", record, &duration, 1))
		return trace_seq_putc(s, '!');

	trace_seq_printf(s, "IRQ %llu: start %llu duration %llu", vector, start, duration);

	if (!record_db())
		return 0;

	snprintf(insert, 1024, "INSERT OR REPLACE INTO irq VALUES (%d, %llu, %llu, %llu);",
				record->cpu, vector, start, duration);

	sql_exec(insert);

	return 0;
}

void get_options(void)
{
	char *env_db_bame  = getenv("RTSL_DB_NAME");
#ifndef PLUGIN_OPTION_WORKING
	char *env_record_db = getenv("RTSL_RECORD_DB");
	if (!env_record_db)
		return;

	if (env_record_db[0] == '1')
		option_record_db->set = 1;
#else
	/*
	 * It is not working, I need to investigate, but...
	 * let's work around it for now.
	 */
	tep_plugin_add_options("rtsl", trace_rtsl_options);
#endif

	if (env_db_bame)
		db_name = env_db_bame;
}

void free_options(void)
{
	if (record_db())
		close_db();

#ifdef PLUGIN_OPTION_WORKING
	tep_plugin_remove_options(trace_rtsl_options);
#endif
}
int TEP_PLUGIN_LOADER(struct tep_handle *tep)
{

	tep_register_event_handler(tep, -1, "rtsl", "max_poid",
				   poid_handler, NULL);

	tep_register_event_handler(tep, -1, "rtsl", "max_paie",
				   paie_handler, NULL);

	tep_register_event_handler(tep, -1, "rtsl", "max_psd",
				   psd_handler, NULL);

	tep_register_event_handler(tep, -1, "rtsl", "max_dst",
				   dst_handler, NULL);

	tep_register_event_handler(tep, -1, "rtsl", "irq_execution",
				   irq_handler, NULL);

	get_options();
	return 0;
}

void TEP_PLUGIN_UNLOADER(struct tep_handle *tep)
{

	tep_unregister_event_handler(tep, -1, "rtsl", "max_poid",
				     poid_handler, NULL);

	tep_unregister_event_handler(tep, -1, "rtsl", "max_paie",
				     paie_handler, NULL);

	tep_unregister_event_handler(tep, -1, "rtsl", "max_psd",
				     psd_handler, NULL);

	tep_unregister_event_handler(tep, -1, "rtsl", "max_dst",
				     dst_handler, NULL);

	tep_unregister_event_handler(tep, -1, "rtsl", "irq_execution",
				   irq_handler, NULL);

	free_options();
}
