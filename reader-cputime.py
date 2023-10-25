import time, os
from os import listdir, walk
from os.path import isfile, join, exists

SYSFS_STAT    = '/proc/stat'
SYSFS_FREQ    = '/sys/devices/system/cpu/{core}/cpufreq/scaling_cur_freq'
# From https://www.kernel.org/doc/Documentation/filesystems/proc.txt
SYSFS_STATS_KEYS  = {'cpuid':0, 'user':1, 'nice':2 , 'system':3, 'idle':4, 'iowait':5, 'irq':6, 'softirq':7, 'steal':8, 'guest':9, 'guest_nice':10}
SYSFS_STATS_IDLE  = ['idle', 'iowait']
SYSFS_STATS_NTID  = ['user', 'nice', 'system', 'irq', 'softirq', 'steal']

SYSFS_STATS_PID_KEYS  = {'pid':0, 'comm':1, 'state':2 , 'ppid':3, 'pgrp':4, 'session':5, 'tty_nr':6, 'tpgid':7, 'flags':8, 'minflt':9, 'cminflt':10, 'majflt':11, 'cmajflt':12 , 'utime':13, 'stime':14, 'cutime':15, 'cstime':16, 'priority':17, 'nice':18, 'num_threads':19} # ...
SYSFS_STATS_PID_NTID  = ['utime', 'stime']

class CpuTime(object):
    def has_time(self):
        return hasattr(self, 'idle') and hasattr(self, 'not_idle')

    def set_time(self, idle : int, not_idle : int):
        setattr(self, 'idle', idle)
        setattr(self, 'not_idle', not_idle)

    def get_time(self):
        return getattr(self, 'idle'), getattr(self, 'not_idle')

    def clear_time(self):
        if hasattr(self, 'idle'): delattr(self, 'idle')
        if hasattr(self, 'not_idle'): delattr(self, 'not_idle')

class ReaderCpu(object):

    def __init__(self):
        self.hist_global  = dict()
        self.hist_cores   = dict()
        self.hist_process = dict()
        self.precision = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
        self.get_usage_per_core_of_pid(66511)

    def get_usage_per_core_of_pid(self, pid : int):
        
        root = '/proc/' + str(pid)
        with open(root + '/stat', 'r') as f:
            split = f.readlines()[0].split()
        # utime and stime are in clock tick
        cumul_in_centi_seconds = sum([int(split[SYSFS_STATS_PID_KEYS[not_idle_key]]) for not_idle_key in SYSFS_STATS_PID_NTID])
        centiseconds = time.time_ns() // 100_000
        # TODO: compute automatically precision
        # TODO: elapsed time and histo
        cumul_in_sec = cumul_in_centi_seconds/centiseconds

        # Find children
        childloc = [root + '/task/' + tid + '/children' for tid in listdir(root + '/task')]
        children = list()
        for loc in childloc:
            with open(loc, 'r') as f: children.extend([int(pid)for pid in f.read().split()])
        
        # Call recursively and manage output
        for child in children: self.get_usage_per_core_of_pid(child)

    def get_usage_global(self):
        with open(SYSFS_STAT, 'r') as f:
            split = f.readlines()[0].split(' ')
            split.remove('')
        if 'global' not in self.hist_global: self.hist_global['global'] = CpuTime()
        return self.__get_usage_of_line(split=split, hist_object=self.hist_global['global'])

    def get_usage_per_core(self):
        cumulated_cpu_usage = 0
        with open(SYSFS_STAT, 'r') as f:
            lines = f.readlines()

        measures_core = dict()
        overflow = False
        for line in lines:
            split = line.split(' ')
            if not split[SYSFS_STATS_KEYS['cpuid']].startswith('cpu'): break

            if split[SYSFS_STATS_KEYS['cpuid']] not in self.hist_cores: self.hist_cores[split[SYSFS_STATS_KEYS['cpuid']]] = CpuTime()
            cpu_usage = self.__get_usage_of_line(split=split, hist_object=self.hist_cores[split[SYSFS_STATS_KEYS['cpuid']]])

            if cpu_usage == None:
                overflow = True
            else:
                measures_core[split[SYSFS_STATS_KEYS['cpuid']]] = cpu_usage

        if overflow:
            return None
        return cumulated_cpu_usage

    def __get_usage_of_line(self, split : list, hist_object : object, update_history : bool = True):
        idle          = sum([ int(split[SYSFS_STATS_KEYS[idle_key]])     for idle_key     in SYSFS_STATS_IDLE])
        not_idle      = sum([ int(split[SYSFS_STATS_KEYS[not_idle_key]]) for not_idle_key in SYSFS_STATS_NTID])

        # Compute delta
        cpu_usage  = None
        if hist_object.has_time():
            prev_idle, prev_not_idle = hist_object.get_time()
            delta_idle     = idle - prev_idle
            delta_total    = (idle + not_idle) - (prev_idle + prev_not_idle)
            if delta_total>0: # Manage overflow
                cpu_usage = ((delta_total-delta_idle)/delta_total)*100
        
        if update_history: hist_object.set_time(idle=idle, not_idle=not_idle)
        return cpu_usage

    def get_freq_of(self, server_cpu_list : list):
        cumulated_cpu_freq = 0
        for cpu in server_cpu_list:
            with open(SYSFS_FREQ.replace('{core}', str(cpu)), 'r') as f:
                cumulated_cpu_freq+= int(f.read())
        return round(cumulated_cpu_freq/len(server_cpu_list), 2)

r = ReaderCpu()