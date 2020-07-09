#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# rt_sched_latency: trace analysis. For more information, see:
#   https://bristot.me/demystifying-the-real-time-linux-latency/
#
# This program was written in the development of this paper:
#
# de Oliveira, D. B., Casini, D., de Oliveira, R. S., Cucinotta, T.
# "Demystifying the Real-Time Linux Scheduling Latency". 2020, In
# 32nd Euromicro Conference on Real-time Systems (ECRTS 2020).
#
# Copyright 2018-2020 Red Hat, Inc.
#
# Author:
#  Daniel Bristot de Oliveira <bristot@redhat.com>

import math
import sqlite3
import os

class Rtsl:
    __modes={ "record" : 1, "report" : 2, "perf": 3 }
    __mode=""

    conn=None
    infinito=999999999

    has_cyclictest_results=False
    __cyclictest_data=[]

    __print_sync=True

    per_case_results={}
    std_output={}

    bar_colors=[ '#142459', '#7d3ac1', '#de542c', '#1ac9e6', '#ea7369', '#e7e34e', '#c7f9ee' ]

    def __init__(self, mode, database_file="trace.rtsl", print_sync=True):
        self.__mode=self.__modes.get(mode)
        if self.__mode == None:
            raise Exception("Unknown mode: %s" % mode)

        # perf does record and report in a single step (perf report)
        if mode == "perf":
            self.__init_database(database_file)

        # for the future record step
        if mode == "record":
            self.__init_database(database_file)

        # Report of an existing database
        if mode == "report":
            if os.path.exists(database_file) == False:
                raise Exception("Database %s does not exist" % database_file)

            # Init the cache in the case it was not created
            self.__conn_database(database_file)
            self.__print_sync=print_sync

# -------------------- Database management --------------------
    def __move_old_database(self, database_file="trace.rtsl"):
        if os.path.exists(database_file):
            try:
                old_database_file=database_file + '.old'
                os.rename(database_file, old_database_file)
            except:
                raise Exception("Old database exist, but it cannot be moved.")

    def __init_database(self, database_file="trace.rtsl"):
        self.__move_old_database(database_file)

        self.conn = sqlite3.connect(database_file, isolation_level=None)
        self.conn.execute('pragma journal_mode=wal')
        self.conn.execute('pragma synchronous=0')

        c = self.conn.cursor()
        c.execute('''CREATE TABLE poid      (cpu integer PRIMARY KEY, value integer)''')
        c.execute('''CREATE TABLE dst       (cpu integer PRIMARY KEY, value integer)''')
        c.execute('''CREATE TABLE paie      (cpu integer PRIMARY KEY, value integer)''')
        c.execute('''CREATE TABLE psd       (cpu integer PRIMARY KEY, value integer)''')
        c.execute('''CREATE TABLE irq       (cpu integer, vector integer, start_time integer PRIMARY KEY, duration integer)''')
        c.execute('''CREATE TABLE nmi       (cpu integer, start_time integer PRIMARY KEY, duration integer)''')
        c.execute('''CREATE TABLE results   (cpu integer, name TEXT, latency integer, PRIMARY KEY(cpu, name))''')

        self.conn.commit()

    def __conn_database(self, database_file="trace.rtsl"):
        self.conn = sqlite3.connect(database_file, isolation_level=None, check_same_thread=False)
        self.conn.execute('pragma journal_mode = wal')
        self.conn.execute('pragma synchronous = 0')
        self.conn.execute('pragma query_only = on')
        self.conn.execute('pragma cache_size = -200000')

    def create_database_cache(self):
        c = self.conn.cursor()
        c.execute('''DROP TABLE IF EXISTS cache_nmi_owcet''')
        c.execute('''DROP TABLE IF EXISTS cache_nmi_omiat''')
        c.execute('''DROP TABLE IF EXISTS cache_irq_owcet''')
        c.execute('''DROP TABLE IF EXISTS cache_irq_omiat''')

        c.execute('''CREATE TABLE cache_nmi_owcet (cpu integer PRIMARY KEY, duration integer)''')
        c.execute('''CREATE TABLE cache_irq_owcet (cpu integer, vector integer, duration integer, PRIMARY KEY(cpu, vector))''')
        c.execute('''CREATE TABLE cache_nmi_omiat (cpu integer PRIMARY KEY, miat integer)''')
        c.execute('''CREATE TABLE cache_irq_omiat (cpu integer, vector integer, miat integer, PRIMARY KEY(cpu, vector))''')

        cpus=self.get_cpu_list()

        for cpu in cpus:
            owcet = self.__get_nmi_cpu_owcet(cpu)
            c.execute("INSERT OR REPLACE INTO cache_nmi_owcet VALUES (?, ?)", (cpu, owcet))

            miat = self.__get_nmi_cpu_miat(cpu)
            c.execute("INSERT OR REPLACE INTO cache_nmi_omiat VALUES (?, ?)", (cpu, miat))

            vectors = self.get_irq_vectors_of_a_cpu(cpu)
            for vector in vectors:
                owcet = self.__get_irq_vector_owcet(cpu, vector)
                miat = self.__get_irq_vector_miat(cpu, vector)

                c.execute("INSERT OR REPLACE INTO cache_irq_owcet VALUES (?, ?, ?)", (cpu, vector, owcet))
                c.execute("INSERT OR REPLACE INTO cache_irq_omiat VALUES (?, ?, ?)", (cpu, vector, miat))
        self.conn.commit()

# -------------------- SETs --------------------
    def set_poid(self, cpu, value):
        self.conn.execute("INSERT OR REPLACE INTO poid VALUES (?, ?)", (cpu, value))

    def set_paie(self, cpu, value):
        self.conn.execute("INSERT OR REPLACE INTO paie VALUES (?, ?)", (cpu, value))

    def set_psd(self, cpu, value):
        self.conn.execute("INSERT OR REPLACE INTO psd VALUES (?, ?)", (cpu, value))

    def set_dst(self, cpu, value):
        self.conn.execute("INSERT OR REPLACE INTO dst VALUES (?, ?)", (cpu, value))

    def insert_irq(self, cpu, vector, start_time, duration):
        self.conn.execute("INSERT OR REPLACE INTO irq VALUES (?, ?, ?, ?)", (cpu, vector, start_time, duration))

    def insert_nmi(self, cpu, start_time, duration):
        self.conn.execute("INSERT INTO nmi VALUES (?, ?, ?)", (cpu, start_time, duration))

# -------------------- python set interface --------------------
    # Interface: callbacks to be used to insert data
    def record_max_ps_disable(self, cpu, value):
        self.set_psd(cpu, value)

    def record_max_dst_disable(self, cpu, value):
        self.set_dst(cpu, value)

    def record_max_poi_disable(self, cpu, value):
        self.set_poid(cpu, value)

    def record_max_paie_disable(self, cpu, value):
        self.set_paie(cpu, value)

    def record_nmi_execution(self, cpu, start, duration):
        self.insert_nmi(cpu, start, duration)

    def record_irq_execution(self, cpu, vector, start, duration):
        self.insert_irq(cpu, vector, start, duration)

# -------------------- CPU gets --------------------
    def get_cpu_list(self):
        """
        Returns the list[] of CPUs in the database, based on the CPU id's that
        reported passing by a POID.
        """
        cpu_list=[]
        for entry in self.conn.execute("SELECT DISTINCT(cpu) from poid"):
            cpu_list.append(entry[0])
        cpu_list.sort()
        return cpu_list

# -------------------- Thread variable GETs --------------------
    def get_poid(self, cpu):
        """
        Returns the POID of a given CPU
        """
        try:
            return self.conn.execute("SELECT * from poid WHERE cpu=?", (cpu,)).fetchone()[1]
        except:
            return 0

    def get_paie(self, cpu):
        """
        Returns the PAIE of a given CPU
        """
        try:
            return self.conn.execute("SELECT * from paie WHERE cpu=?", (cpu,)).fetchone()[1]
        except:
            return 0

    def get_psd(self, cpu):
        """
        Returns the PSD of a given CPU
        """
        try:
            return self.conn.execute("SELECT value from psd WHERE cpu=?", (cpu,)).fetchone()[0]
        except:
            return 0

    def get_dst(self, cpu):
        """
        Returns the DST of a given CPU
        """
        try:
            return self.conn.execute("SELECT * from dst WHERE cpu=?", (cpu,)).fetchone()[1]
        except:
            return 0

# -------------------- IRQ GETs --------------------
    def get_irq_cpu_owcet(self, cpu):
        """
        returns the duration of the longest IRQ execution of a given CPU.
        """
        return self.conn.execute("select MAX(duration) from irq where cpu=?", (cpu,)).fetchone()[0]

    def get_irq_vectors_of_a_cpu(self, cpu):
        """
        return the list[] of IRQ entries of a given CPU
        """

        vector_list=[]

        for vector in self.conn.execute("select DISTINCT(vector) from irq where cpu=?", (cpu,)):
            vector_list.append(vector[0])

        vector_list.sort()

        return vector_list

    def get_irq_entries_of_a_vector(self, cpu, vector):
        """
        returns a list[] with all IRQ occurrences of a given vector of a given CPU.

        Each element contains a tuple() with the start_time and duration of the
        IRQ occurrence.

        This function consumes lots of memory, but speeds up things.

        XXX: X Needs to create a version to be used by low memory systems.
        """

        irq_list=[]

        for irq in self.conn.execute("SELECT start_time, duration from irq WHERE cpu=? AND vector=?", (cpu, vector)):
            irq_list.append(irq)

        return irq_list

    def __get_irq_vector_owcet(self, cpu, vector):
        """
        returns the worst execution time of a given IRQ on a given CPU.
        """

        return self.conn.execute("select MAX(duration) from irq where cpu=? and vector=?", (cpu, vector)).fetchone()[0]

    def get_irq_vector_owcet(self, cpu, vector):
        """
        returns the worst execution time of a given IRQ on a given CPU.

        But it tries to check the cache first.
        """

        try:
            return self.conn.execute("select duration from cache_irq_owcet where cpu=? and vector=?", (cpu,vector)).fetchone()[0]
        except:
            return self.__get_irq_vector_owcet(cpu, vector)

    def __get_irq_vector_miat(self, cpu, vector):
        """
        returns the minimum inter-arrival time of a given IRQ on a given CPU.

        The minimum inter-arrival time is the shortest delta between two IRQ occurrence.
        """

        min_iat=self.infinito
        last_arrival=0

        for irq in self.conn.execute("SELECT start_time from irq WHERE cpu=? AND vector=?", (cpu, vector)):
            curr_irq=irq[0]

            if last_arrival:
                iat=curr_irq - last_arrival
                if iat < min_iat:
                    min_iat=iat

            last_arrival=curr_irq

        return min_iat

    def get_irq_vector_miat(self, cpu, vector):
        """
        returns the minimum inter-arrival time of a given IRQ on a given CPU.

        But it tries to check the cache first.
        """

        try:
            return self.conn.execute("select miat from cache_irq_omiat where cpu=? and vector=?", (cpu,vector)).fetchone()[0]
        except:
            return self.__get_irq_vector_miat(cpu, vector)

# -------------------- IRQ GETs --------------------
    def get_nmi_cpu_miat(self, cpu):
        """
        returns the duration of the longest NMI execution of a given CPU.
        """
        try:
            return self.conn.execute("select miat from cache_nmi_omiat where cpu=?", (cpu,)).fetchone()[0]
        except:
            return self.__get_nmi_cpu_owcet(cpu)

    def get_nmi_entries_of_cpu(self, cpu):
        """
        returns a list[] with all NMI occurrences of a given CPU.

        Each element contains a tuple() with the start_time and duration of the
        NMI occurrence.

        This function consumes lots of memory, but speeds up things.

        XXX: X Needs to create a version to be used by low memory systems.
        """
        nmi_list=[]

        for nmi in self.conn.execute("SELECT start_time, duration from nmi WHERE cpu=?", (cpu,)):
            nmi_list.append(nmi)

        return nmi_list

    def __get_nmi_cpu_owcet(self, cpu):
        """
        returns the worst execution time of a NMI on a given CPU.
        """
        owcet = self.conn.execute("select MAX(duration) from nmi where cpu=?", (cpu,)).fetchone()[0]
        try:
            return int(owcet)
        except:
            return 0

    def get_nmi_cpu_owcet(self, cpu):
        """
        returns the worst execution time of a given IRQ on a given CPU.

        returns the worst execution time of a NMI on a given CPU.
        """
        try:
            return self.conn.execute("select duration from cache_nmi_owcet where cpu=?", (cpu,)).fetchone()[0]
        except:
            return self.__get_nmi_cpu_owcet(cpu)

    def __get_nmi_cpu_miat(self, cpu):
        """
        returns the minimum inter-arrival time of a NMI on a given CPU.

        The minimum inter-arrival time is the shortest delta between two NMI occurrence.
        """
        min_iat=self.infinito
        last_arrival=0
        for nmi in self.conn.execute("SELECT start_time from nmi WHERE cpu=?", (cpu,)):
            curr_nmi=nmi[0]
            if last_arrival:
                iat=curr_nmi - last_arrival
                if iat < min_iat:
                    min_iat=iat
            last_arrival=curr_nmi

        return min_iat

# -------------------- Output buffers --------------------
    def print_header(self, line):
        """
        Adds a line to the header
        """

        if (self.__print_sync):
            print(line)
            return

        try:
            header=self.std_output["header"]
        except:
            self.std_output["header"]=[]
            header=self.std_output["header"]

        header.append(line)

    def print_cpu_analysis(self, cpu, line):
        """
        Adds a line of analysis to the per-cpu analysis.
        """
        if (self.__print_sync):
            print(line)
            return

        try:
            cpu_buffer=self.std_output[cpu]
        except:
            self.std_output[cpu]=[]
            cpu_buffer=self.std_output[cpu]

        cpu_buffer.append(line)

    def print_latency(self, cpu, latency, case):
        """
        Adds a line with the results of the analysis.
        """
        out_string="\t\tLatency = %9d with %s" % (latency, case)
        if (self.__print_sync):
            print(out_string)
            return

        try:
            cpu_buffer=self.std_output[cpu]
        except:
            self.std_output[cpu]=[]
            cpu_buffer=self.std_output[cpu]

        cpu_buffer.append(out_string)

    def save_results(self, cpu, latency, case):
        try:
            results = self.per_case_results[case]
        except:
            self.per_case_results[case]={}
            results = self.per_case_results[case]

        results[cpu]=latency

# -------------------- Analysis --------------------
    def open_cyclictest(self, file_path="cyclictest.txt"):
        """
        Open cyclyctest output.

        The output must be generated with "-q" option.
        """
        try:
            cyclic_file = open(file_path)
        except OSError:
            return False

        self.__cyclictest_data = cyclic_file.read().splitlines()
        cyclic_file.close()
        return True

    def print_cyclictest(self, cpu):
        """
        returns the cyclictest's latency of a CPU.
        """

        self.print_cpu_analysis(cpu, "\tCyclictest:")

        for line in self.__cyclictest_data:
            vector=line[2:].split()
            try:
                cpu_vector=int(vector[0])
            except:
                continue

            if cpu_vector == cpu:
                self.print_latency(cpu, int(vector[-1])*1000, "Cyclictest")
                return int(vector[-1])*1000, "Cyclictest"

    def interference_free_latency(self, cpu, poid, paie, psd, dst):
        """
        returns the interference free latency of a given CPU.
        """
        self.print_cpu_analysis(cpu, "\tInterference Free Latency:")
        self.print_cpu_analysis(cpu, "\t\t  latency = max(     poid,       dst) +      paie +       psd")

        latency = max(poid, dst) + paie + psd

        self.print_cpu_analysis(cpu, "\t\t%9d = max(%9d, %9d) + %9d + %9d" % (latency, poid, dst, paie, psd))

        return latency

    def no_interrupt(self, cpu, ifl):
        """
        latency considering only the threads of a given CPU.
        """
        self.print_cpu_analysis(cpu, "\tNo interrupts:")
        self.print_latency(cpu, ifl, "No Interrupts")
        return ifl, "No Interrupts"

    def single_interrupt(self, cpu, ifl):
        """
        latency considering a single NMI and a single IRQ (the worst).
        """
        max_irq=0
        max_nmi=0

        self.print_cpu_analysis(cpu, "\tConsidering a single NMI and IRQ (the worst):")
        self.print_cpu_analysis(cpu, "\t\t  latency =       ifl +       IRQ +      NMI")

        max_irq = self.get_irq_cpu_owcet(cpu)
        max_nmi = self.get_nmi_cpu_owcet(cpu)
 
        latency = ifl + max_irq + max_nmi
 
        self.print_cpu_analysis(cpu, "\t\t%9d = %9d + %9d +%9d" % (latency, ifl, max_irq, max_nmi))
        self.print_latency(cpu, latency, "Worst Single Interrupt")

        return latency, "Worst Single Interrupt"

    def single_of_each_interrupt(self, cpu, ifl):
        """
        Latency considering a single NMI and the sum of one occurence of each Interrupt (the worst).
        """
        self.print_cpu_analysis(cpu, "\tConsidering a single NMI and the sum of one occurence of each Interrupt (the worst):")

        max_nmi=0
        max_irq=0
        sum_irq=0

        vector_list=self.get_irq_vectors_of_a_cpu(cpu)

        self.print_cpu_analysis(cpu, "\t\t%3s: %9s" % ("INT", "oWCET"))

        max_nmi = self.get_nmi_cpu_owcet(cpu)
        self.print_cpu_analysis(cpu, "\t\tNMI: %9d" % (max_nmi))

        for vector in vector_list:
            max_irq = self.get_irq_vector_owcet(cpu, vector)
            self.print_cpu_analysis(cpu, "\t\t%3d: %9d" % (vector, max_irq))
            sum_irq += max_irq

        latency = ifl + sum_irq + max_nmi
        
        self.print_cpu_analysis(cpu, "\t\t  latency =       ifl +  sum(IRQ) +      NMI")

        self.print_cpu_analysis(cpu, "\t\t%9d = %9d + %9d +%9d" % (latency, ifl, sum_irq, max_nmi))

        self.print_latency(cpu, latency, "Single (Worst) of Each Interrupt")

        return latency, "Single (Worst) of Each Interrupt"

    def __rta_irq_interference(self, window, irq_param):
        """
        A round of RTA
        """
        sum_irq=0
        for vector in irq_param:
            c, t = irq_param[vector]

            # if no NMI...
            if t == 0:
                continue

            irq_uw = math.ceil(window/t)*c
            sum_irq += irq_uw
        return sum_irq
     
    def sporadic_interrupt(self, cpu, ifl):
        """
        Latency considering sporadic interrupt
        """
        self.print_cpu_analysis(cpu, "\tConsidering sporadic interrupts:")
        wont_converge=0
        irq_param={}
        vector_list=self.get_irq_vectors_of_a_cpu(cpu)

        self.print_cpu_analysis(cpu, "\t\t%3s: %9s %15s" % ("INT", "oWCET", "oMIAT"))

        # NMI
        try:
            wcet = self.get_nmi_cpu_owcet(cpu)
            miat = self.get_nmi_cpu_miat(cpu)
        except:
            wcet = miat = 0

        irq_param['NMI'] = wcet, miat 

        self.print_cpu_analysis(cpu, "\t\t%3s: %9d %15d" % ('NMI', wcet, miat))

        for vector in vector_list:
            wcet = self.get_irq_vector_owcet(cpu, vector)
            miat = self.get_irq_vector_miat(cpu, vector)

            if miat < wcet:
                self.print_cpu_analysis(cpu, "\t\t%3d: %9d %15d <- oWCET > oMIAT: won't converge" % (vector, wcet, miat))
                wont_converge=1
            else:
                if miat == self.infinito:
                    self.print_cpu_analysis(cpu, "\t\t%3d: %9d %15s" % (vector, wcet, "infinite"))
                else:
                    self.print_cpu_analysis(cpu, "\t\t%3d: %9d %15d" % (vector, wcet, miat))
            irq_param[vector] = wcet, miat

        if wont_converge:
            self.print_cpu_analysis(cpu, "\t\tDid not converge.")
            return

        c_latency=ifl
        window=c_latency
        self.print_cpu_analysis(cpu, "\t\t%9s: %9s" % ("initial w", "ifl"))
        self.print_cpu_analysis(cpu, "\t\t%9d: %9d" % (window, ifl))
        while True:
            new_window  = c_latency + self.__rta_irq_interference(window, irq_param)
            self.print_cpu_analysis(cpu, "\t\t%9s= %d" % ("w'", new_window))

            if new_window == window:
                self.print_cpu_analysis(cpu, "\t\tConverged!")
                break
            window = new_window
            if window > 100000000:
                self.print_cpu_analysis(cpu, "\t\tlatency higher than 100ms, Did not converge")
                break

        latency = window
        self.print_latency(cpu, latency, "Sporadic")
        return latency, "Sporadic"

    def __max_exec_in_a_windown(self, vector, window):
        """
        Maximum interference an interrupt can add to a given window.
        """
        max_exec=0
        stack={}
        last_arrival=0
        for entry in vector:
            # add the new entry in the stack
            arrival = entry[0]
            exec_time = entry[1]
            stack[arrival]=exec_time

            # for each occurence in the stack, remove thoses that
            # arrived before window units of time ago.
            for item in sorted(stack.keys()):
                delta = arrival - item
                if delta > window:
                    stack.pop(item)

            curr_exec = 0
            for item in stack.keys():
                curr_exec += stack[item] 

            if curr_exec > max_exec:
                max_exec = curr_exec

        return max_exec

    def sliding_window_interrupt(self, cpu, ifl):
        """
        return the latency considering the sliding windown.
        """
        self.print_cpu_analysis(cpu, "\tConsidering the worst interrupt window (sliding window):" )

        # saved results for each int entry:
        saved_int_interference={}

        # base window:
        window=ifl
        self.print_cpu_analysis(cpu, "\t\tWindow: " + str(window))

        # get the IRQ vector list of a CPU
        vector_list=self.get_irq_vectors_of_a_cpu(cpu)

        # cache all the IRQ entries of an CPU.
        # this improves the speed, while consuming memory
        # it can be avoided by consulting the database anytime a
        # vector is tried.
        # 
        # TODO: create an option for low memory systems to fallback.
        irq_vector_entries={}
        for vector in vector_list:
            irq_entires = self.get_irq_entries_of_a_vector(cpu, vector)
            irq_vector_entries[vector]=irq_entires

        # cache all the NMI entries of a CPU
        nmi_entries=self.get_nmi_entries_of_cpu(cpu)

        # First try for NMI
        vector="NMI"
        try:
            max_exec = self.__max_exec_in_a_windown(nmi_entries, window)
        except:
            max_exec = 0

        self.print_cpu_analysis(cpu, "\t\t %9s:%9d" % (vector, max_exec))

        # Save the NMI disturbance.
        saved_int_interference[vector] = max_exec

        # increase the window:
        window += max_exec

        # try each IRQ
        for vector in vector_list:
            max_exec = self.__max_exec_in_a_windown(irq_vector_entries[vector], window)
            self.print_cpu_analysis(cpu, "\t\t %9d:%9d" % (vector, max_exec))
            saved_int_interference[vector] = max_exec

            # increase the window already, to try to save time.
            window += max_exec

        self.print_cpu_analysis(cpu, "\t\tWindow: " + str(window))

        # Loop until the new_window == window.
        # IOW: when the worst window is found.
        new_window = window
        while True:

            # NMI first
            vector="NMI"
            try:
                max_exec = self.__max_exec_in_a_windown(nmi_entries, new_window - saved_int_interference[vector])
            except:
                max_exec = 0

            # if worse interference is found, update the results,
            # and add it to the new_window.
            if (max_exec > saved_int_interference[vector]):
                self.print_cpu_analysis(cpu, "\t\t %9s:%9d <- new!" % (vector, max_exec))
                new_window -= saved_int_interference[vector]
                new_window += max_exec
                saved_int_interference[vector]=max_exec

            # same for IRQs.
            for vector in vector_list:
                max_exec = self.__max_exec_in_a_windown(irq_vector_entries[vector], new_window - saved_int_interference[vector])
                if (max_exec > saved_int_interference[vector]):
                    self.print_cpu_analysis(cpu, "\t\t %9d:%9d <- new!" % (vector, max_exec))
                    new_window -= saved_int_interference[vector]
                    new_window += max_exec
                    saved_int_interference[vector]=max_exec

            if new_window == window:
                self.print_cpu_analysis(cpu, "\t\tConverged!")
                break

            window = new_window
            self.print_cpu_analysis(cpu, "\t\tWindow: " + str(window))

        self.print_latency(cpu, window, "Sliding Window")
        return window, "Sliding Window"

    def __max_exec_in_a_windown_owcet(self, vector, window, owcet):
        """
        Maximum interference an interrupt can add to a given window considering oWCET.
        """
        max_exec=0
        stack={}
        last_arrival=0
        for entry in vector:
            # add the new entry in the stack
            arrival = entry[0]
            exec_time = entry[1]
            stack[arrival]=exec_time

            # for each occurence in the stack, remove thoses that
            # arrived before window units of time ago.
            for item in sorted(stack.keys()):
                delta = arrival - item
                if delta > window:
                    stack.pop(item)

            curr_exec = 0
            for item in stack.keys():
                curr_exec += owcet

            if curr_exec > max_exec:
                max_exec = curr_exec

        return max_exec

    def sliding_window_interrupt_owcet(self, cpu, ifl):
        """
        return the latency considering the sliding windown using the
        worst case execution time of each interrupt.
        """
        self.print_cpu_analysis(cpu, "\tConsidering the worst interrupt window (sliding window) and oWCET:" )
        saved_int_interference={}
        window=ifl

        # get the IRQ vector list of a CPU
        vector_list=self.get_irq_vectors_of_a_cpu(cpu)

        # cache all the IRQ entries of an CPU.
        # this improves the speed, while consuming memory
        # it can be avoided by consulting the database anytime a
        # vector is tried.
        # 
        # TODO: create an option for low memory systems to fallback.
        irq_vector_entries={}
        for vector in vector_list:
            irq_entires = self.get_irq_entries_of_a_vector(cpu, vector)
            irq_vector_entries[vector]=irq_entires

        # cache all the NMI entries of a CPU
        nmi_entries=self.get_nmi_entries_of_cpu(cpu)

        # cache the oWCET of each interrupt
        irq_owcet={}
        try:
            irq_owcet["NMI"] = self.get_nmi_cpu_owcet(cpu)
        except:
            irq_owcet["NMI"] = 0

        for vector in vector_list:
            irq_owcet[vector] = self.get_irq_vector_owcet(cpu, vector)

        self.print_cpu_analysis(cpu, "\t\tWindow: " + str(window))

        # NMI
        vector="NMI"
        try:
            max_exec = self.__max_exec_in_a_windown_owcet(nmi_entries, window, irq_owcet[vector])
        except:
            max_exec = 0

        self.print_cpu_analysis(cpu, "\t\t %9s:%9d" % (vector, max_exec))
        saved_int_interference[vector] = max_exec

        window += max_exec

        for vector in vector_list:
            max_exec = self.__max_exec_in_a_windown_owcet(irq_vector_entries[vector], window, irq_owcet[vector])
            self.print_cpu_analysis(cpu, "\t\t %9d:%9d" % (vector, max_exec))
            saved_int_interference[vector] = max_exec
            window += max_exec

        self.print_cpu_analysis(cpu, "\t\tWindow: " + str(window))

        new_window = window
        while True:

            # NMI first
            vector="NMI"
            try:
                max_exec = self.__max_exec_in_a_windown_owcet(nmi_entries, new_window - saved_int_interference[vector], irq_owcet[vector])
            except:
                max_exec = 0

            if (max_exec > saved_int_interference[vector]):
                self.print_cpu_analysis(cpu, "\t\t %9s:%9d <- new!" % (vector, max_exec))
                new_window -= saved_int_interference[vector]
                new_window += max_exec
                saved_int_interference[vector]=max_exec

            # Then IRQ
            for vector in vector_list:
                max_exec = self.__max_exec_in_a_windown_owcet(irq_vector_entries[vector], new_window - saved_int_interference[vector], irq_owcet[vector])
                if (max_exec > saved_int_interference[vector]):
                    self.print_cpu_analysis(cpu, "\t\t %9d:%9d <- new!" % (vector, max_exec))
                    new_window -= saved_int_interference[vector]
                    new_window += max_exec
                    saved_int_interference[vector]=max_exec

            if new_window == window:
                self.print_cpu_analysis(cpu, "\t\tConverged!")
                break

            window = new_window
            self.print_cpu_analysis(cpu, "\t\tWindow: " + str(window))

        self.print_latency(cpu, window, "Sliding Window with oWCET")
        return window, "Sliding Window with oWCET"

# -------------------- process traces --------------------

    def __process_trace_cpu(self, cpu):
        self.print_cpu_analysis(cpu, "CPU: %3d" % cpu)

        poid=self.get_poid(cpu)
        paie=self.get_paie(cpu)
        psd=self.get_psd(cpu)
        dst=self.get_dst(cpu)

        if self.has_cyclictest_results:
            latency, case = self.print_cyclictest(cpu)
            self.save_results(cpu, latency, case)

        ifl = self.interference_free_latency(cpu, poid, paie, psd, dst)

        latency, case = self.no_interrupt(cpu, ifl)
        self.save_results(cpu, latency, case)

        latency, case = self.single_interrupt(cpu, ifl)
        self.save_results(cpu, latency, case)
   
        latency, case = self.single_of_each_interrupt(cpu, ifl)
        self.save_results(cpu, latency, case)

        self.sporadic_interrupt(cpu, ifl)

        latency, case = self.sliding_window_interrupt(cpu, ifl)
        self.save_results(cpu, latency, case)

        latency, case = self.sliding_window_interrupt_owcet(cpu, ifl)
        self.save_results(cpu, latency, case)

    def process_trace(self, cyclictest="cyclictest.txt"):
        cpus = self.get_cpu_list()
        cpus.sort()

        self.has_cyclictest_results = self.open_cyclictest(cyclictest)

        for cpu in cpus:
            self.__process_trace_cpu(cpu)

    def add_header(self):
        self.print_header("  ==== Latency Analisyis! ==== ")
        self.print_header("\tTime unit is nanosecods")
        self.print_header("\tpoid  = Preemption or Interrupt disabled [ not to schedule ] window")
        self.print_header("\tpaie  = Preemption and Interrupts enabled")
        self.print_header("\tpsd   = Preemption disabled to schedule window")
        self.print_header("\tdst   = Delay of scheduling tail")
        self.print_header("\tifl   = Interference free latency")
        self.print_header("\tINT   = Interrupts")
        self.print_header("\tIRQ   = Maskable interrupts")
        self.print_header("\tNMI   = Non-maskable interrupts")
        self.print_header("\toWCET = Observed Worst Case Execution Time")
        self.print_header("\toMIAT = Observed Minimun Inter-arrival Time")
        self.print_header("")

    def print_trace_cpu(self, cpu):
        try:
            print_buff=self.std_output[cpu]
        except:
            raise Exception("Printing a CPU that was not processed")

        for line in print_buff:
            print(line)

    def print_trace(self, print_header=True):
        # it only makes sense to print if we are assync
        if self.__print_sync:
            return

        if print_header:
            try:
                print_buff=self.std_output["header"]
            except:
                raise Exception("The trace was not processed")

            for line in print_buff:
                print(line)

        cpus = self.get_cpu_list()
        cpus.sort()

        for cpu in cpus:
            self.print_trace_cpu(cpu)

    def process_results(self, cyclictest="cyclictest.txt"):
        self.add_header()
        self.process_trace(cyclictest)
        self.print_trace()

# -------------------- Plot --------------------
    def __xticks_format_labels(self, cpus, results, xticks_step):
        xticks_labels=[]
        xticks_position=[]

        if cpus.__len__() == 1:
            return [], [];

        i=0
        for case in results:
            for cpu in results[case]:
                i+=1
                xticks_position.append(i)
                # print only the steps
                if (cpu % xticks_step) == 0:
                    xticks_labels.append(cpu)
                else:
                    xticks_labels.append('')

        return xticks_labels, xticks_position;

    # examples from the paper:
    # plot_results()
    # plot_results(output_file="output_compact.svg", hsize=7, vsize=4, title="", ymax=60 , ylabel="", xlabel="", legend=False, xtick_distance=4)
    # plot_results(output_file="output_ultra_compact.svg", hsize=4, vsize=4, title="", ymax=60 , ylabel="", xlabel="", legend=False, xtick_distance=0)

    def plot_results(self, output_file="output.svg", hsize=16, vsize=7, title="Latency analysys", ymax=0 , ylabel="Latency (microseconds)", xlabel="CPU", legend=True, legend_loc="upper center", legend_ncol=8, xtick_distance=1):

        try:
            import matplotlib
            import matplotlib.pyplot as plt
            import numpy as np
        except:
            raise Exception("Cannot use matplotlib or numpy")

        number_of_cpus=0
        number_of_case=0

        cpus = self.get_cpu_list()

        fig = plt.figure(figsize=(hsize,vsize), frameon=False)
        ax = fig.add_subplot()

        x = np.arange(len(cpus))
        width = 0.90

        tick_distance=1
        color_index=0

        for case in self.per_case_results:
            results_case=[]
            for cpu in self.per_case_results[case]:
                latency=self.per_case_results[case][cpu]/1000
                results_case.append(latency)
            ax.bar((x)+tick_distance, results_case, width, label=case, color=self.bar_colors[color_index])
            tick_distance+=cpus.__len__()
            color_index += 1

        if title.__len__() != 0:
            ax.set_title(title)
        if ylabel.__len__() != 0:
            ax.set_ylabel(ylabel)

        if xlabel.__len__() != 0:
            ax.set_xlabel(xlabel)

        if ymax != 0:
            ax.set_ylim(0, ymax)

        if xtick_distance == 0:
            ax.set_xticks([])
            ax.set_xticklabels([])
        else:
            xticks_labels, xticks_position = self.__xticks_format_labels(cpus, self.per_case_results, xtick_distance)
            ax.set_xticks(xticks_position)
            ax.set_xticklabels(xticks_labels)

        if legend:
            ax.legend(loc=legend_loc, ncol=legend_ncol)

        fig.tight_layout()
        plt.savefig(output_file)



from time import sleep
from bcc import BPF

class RTSLThreadVarStats:
    __vars={ "poid" : 1, "paie" : 2, "psd": 3, "dst" : 4 }
    __var=""

    __cpus=0
    __max_value=0
    __results_micro={}

    __bpf_program=None

    __base_program="""
    BPF_PERCPU_ARRAY(micro, u64, 1001);

    TRACEPOINT_PROBE(rtsl, VAR) {
            u64 value = args->value;
            u64 *entry, new;
            int idx;

            if (value < 1000000) {
                /*
                 * This is an upper bound that means within a given
                 * microsecond. So increase 999 ns, to fit in the next
                 * bucket, unless it is an rounded number.
                 */
                value += 999;
                idx = value/1000;

                entry = micro.lookup(&idx);
                if (entry) {
                    new = *entry + 1;
                    micro.update(&idx, &new);
                }
            } else {
                /*
                 * A millisecond value is not expected on the RT.
                 * At least not in a correct enviroment.
                 * In this case, put in the last bucket a sing that
                 * there is something really wrong.
                 */
                idx = 1001;
                entry = micro.lookup(&idx);
                if (entry) {
                    new = *entry + 1;
                    micro.update(&idx, &new);
                }
            }

            return 0;
    }
    """

    __program=""

    def __init__(self, var="poid"):
        if self.__vars.get(var) == None:
            raise Exception("Unknown mode: %s" % mode)
        self.__var=var

        self.__program=self.__base_program.replace("VAR", var)

    def run(self):
        print("Tracing... Hit Ctrl-C to end.")
        self.__bpf_program = BPF(text=self.__program)

    def stop(self):
        event="rtsl:" + self.__var
        self.__bpf_program.detach_tracepoint(event)

    def __parse_results(self, micro):
        # Save the number of CPdUs
        self.__cpus=micro.total_cpu

        self.__results_micro={}
       
        # initialize the values with 0
        for i in range(self.__cpus):
            self.__results_micro[i]={}
            for y in range(1001):
                self.__results_micro[i][y]=0

        for duration in micro.keys():
            # each value is a per_cpu counter of number of times a given key duration happened. 
            cpu=0
            for value in micro.getvalue(duration):
                self.__results_micro[cpu][duration.value]=value
                cpu+=1

    def updata_results(self):
        micro = self.__bpf_program.get_table("micro")
        self.__parse_results(micro)

    def cpu_duration_list(self, cpu):
        duration_list=[]
        for duration in self.__results_micro[cpu]:
            duration_list.append(self.__results_micro[cpu][duration])
        return duration_list

    def duration_cpu_list(self, duration):
        cpu_list=[]
        for cpu in range(self.__cpus):
            cpu_list.append(self.__results_micro[cpu][duration])

        return cpu_list

    def print(self):

        print("y-axis = duration in us, x-axis = CPU, cell: times that a given y-duration happened on a x-CPU")

        cpus="     "
        for i in range(self.__cpus):
            cpus = "%s %9d" % (cpus, i)
        print(cpus + "        TOTAL")

        for index in range(1000):
            duration=self.duration_cpu_list(index)
            output=""
            total_count=0
            for cpu_count in duration:
                output = "%s %9d" % (output, cpu_count)
                total_count += cpu_count

            if total_count:
                print("%3d: %10s = %10d" % (index, output, total_count))

    def __get_max_and_hide_after(self, counters):
            max_idx = 0

            # Get the largest index that has entries.
            for idx in range(1001):
                if counters[idx] != 0:
                    max_idx = idx

            # change the zeros do nan so the are not displayed by
            # matplotlib
            for idx in range(max_idx+1, 1001):
                counters[idx] = float('nan')

            return max_idx, counters


    def __plot_all_in_one(self, plt, hsize=16, vsize=7, output_file="stats.svg"):
        cpus=[x for x in range(self.__cpus)]
        buckets=[x for x in range(1001)]
        x_max=0

        fig, ax = plt.subplots(figsize=(hsize,vsize), frameon=False)
        for cpu in cpus:
            counters=self.cpu_duration_list(cpu)
            max_idx, counters = self.__get_max_and_hide_after(counters)

            # If the largest is largest over all, save it.
            if x_max < max_idx:
                x_max = max_idx + 1

            label="%d (max = %d)" % (cpu, max_idx)
            ax.plot(buckets, counters, 'o', ls='-', label=label, markevery=1)

        # Trucate the x-axis with largest delay
        ax.set_xlim(1, x_max)

        ax.legend()

        fig.tight_layout()
        plt.savefig(output_file)


    def __plot_all(self, plt, hsize=16, vsize=7, output_file="stats.svg", plots_per_line=4):
        cpus=[x for x in range(self.__cpus)]
        buckets=[x for x in range(1001)]
        x_max=0

        lines = int(self.__cpus/ plots_per_line)
        if self.__cpus % plots_per_line:
            lines += 1

        fig, axs = plt.subplots(lines, plots_per_line, sharey=True, figsize=(hsize,vsize), frameon=False)

        for cpu in cpus:
            counters=self.cpu_duration_list(cpu)
            max_idx, counters = self.__get_max_and_hide_after(counters)


            # If the largest is largest over all, save it.
            if x_max < max_idx:
                x_max = max_idx + 1

            label="%d (max = %d)" % (cpu, max_idx)

            line=int(cpu / plots_per_line)
            col=int(cpu % plots_per_line)
            axs[line, col].plot(buckets, counters, 'o', ls='-', label=label, markevery=1)

        # Trucate the x-axis with largest delay (plus one)
        for cpu in cpus:
            line=int(cpu / plots_per_line)
            col=int(cpu % plots_per_line)

            axs[line, col].set_xlim(1, x_max)
            axs[line, col].set_ylim(0)
            axs[line, col].legend()

        fig.tight_layout()
        plt.savefig(output_file)

    def plot(self, hsize=16, vsize=7, merge=False, output_file="stats.svg"):
        try:
            import matplotlib.pyplot as plt
        except:
            raise Exception("Cannot use matplotlib")

        if merge:
            self.__plot_all_in_one(plt, hsize, vsize, output_file=output_file)
        else:
            self.__plot_all(plt, hsize, vsize, output_file=output_file)
