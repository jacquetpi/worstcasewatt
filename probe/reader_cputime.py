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

class CpuTimeCore(object):
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

class CpuTimeProcess(object):

    def __init__(self):
        self.system_power = -1
        baseline =  os.sysconf(os.sysconf_names['SC_CLK_TCK'])
        while baseline>0:
            self.system_power+=1
            baseline = int(baseline/10)

    def has_time(self):
        return hasattr(self, 'not_idle') and hasattr(self, 'prev_time_ns')

    def read_usage_and_update(self, not_idle : int):
        if not self.has_time():
            self.set_time(not_idle)
            return None
        prev_not_idle     = self.not_idle
        prev_timestamp_ns = self.prev_time_ns
        self.set_time(not_idle)
        curr_not_idle     = self.not_idle
        curr_timestamp_ns = self.prev_time_ns
        delt_not_idle = curr_not_idle - prev_not_idle
        delt_time     = (curr_timestamp_ns - prev_timestamp_ns) // (10**(9-self.system_power)) # compute delta and convert from ns to ticks
        if delt_time>0:
            return round((delt_not_idle/delt_time)*100,2)
        return 0

    def set_time(self, not_idle : int):
        setattr(self, 'not_idle', not_idle)
        setattr(self, 'prev_time_ns', time.time_ns())

    def clear_time(self):
        if hasattr(self, 'not_idle'): delattr(self, 'not_idle')
        if hasattr(self, 'prev_time_ns'): delattr(self, 'prev_time_ns')

class ReaderCpu(object):

    def __init__(self):
        self.hist_global  = dict()
        self.hist_cores   = dict()
        self.hist_process = dict()

    def get_usage_per_core_of_pid(self, pid : int):
        measures_dict = {}
        if str(pid) not in self.hist_process: self.hist_process[str(pid)] = CpuTimeProcess()

        try:
            # Read CPU time of process
            root = '/proc/' + str(pid)
            with open(root + '/stat', 'r') as f:
                split = f.readlines()[0].split()
            cumul = sum([int(split[SYSFS_STATS_PID_KEYS[not_idle_key]]) for not_idle_key in SYSFS_STATS_PID_NTID])
            
            individual_usage = self.hist_process[str(pid)].read_usage_and_update(not_idle=cumul) # Is None on first call
            if individual_usage != None:
                measures_dict[str(pid)] = individual_usage

            # Find children for recursivity
            childloc = [root + '/task/' + tid + '/children' for tid in listdir(root + '/task')]
            children = list()
            for loc in childloc:
                with open(loc, 'r') as f: children.extend([int(pid)for pid in f.read().split()])
            for child in children: 
                measures_dict.update(self.get_usage_per_core_of_pid(child))
            return measures_dict
        except (FileNotFoundError,ProcessLookupError): # PID do not exist (anymore?)
            return {}


    def get_usage_global(self):
        with open(SYSFS_STAT, 'r') as f:
            split = f.readlines()[0].split(' ')
            split.remove('')
        if 'global' not in self.hist_global: self.hist_global['global'] = CpuTimeCore()
        return self.__get_usage_of_line(split=list(filter(lambda a: a != '', split)), hist_object=self.hist_global['global'])

    def get_usage_per_core(self):
        cumulated_cpu_usage = 0
        with open(SYSFS_STAT, 'r') as f:
            lines = f.readlines()

        measures_core = dict()
        for line in lines:
            split = line.split(' ')
            if split[SYSFS_STATS_KEYS['cpuid']] == 'cpu': continue # exclude first line 
            if not split[SYSFS_STATS_KEYS['cpuid']].startswith('cpu'): break
            
            if split[SYSFS_STATS_KEYS['cpuid']] not in self.hist_cores: self.hist_cores[split[SYSFS_STATS_KEYS['cpuid']]] = CpuTimeCore()
            cpu_usage = self.__get_usage_of_line(split=list(filter(lambda a: a != '', split)), hist_object=self.hist_cores[split[SYSFS_STATS_KEYS['cpuid']]])
            if cpu_usage != None:
                measures_core[split[SYSFS_STATS_KEYS['cpuid']]] = cpu_usage

        return measures_core

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
                cpu_usage = round(((delta_total-delta_idle)/delta_total)*100,2)
        
        if update_history: hist_object.set_time(idle=idle, not_idle=not_idle)
        return cpu_usage

    def get_freq_of(self, server_cpu_list : list):
        cumulated_cpu_freq = 0
        for cpu in server_cpu_list:
            with open(SYSFS_FREQ.replace('{core}', str(cpu)), 'r') as f:
                cumulated_cpu_freq+= int(f.read())
        return round(cumulated_cpu_freq/len(server_cpu_list), 2)