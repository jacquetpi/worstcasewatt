import subprocess, time
from probe.reader_cputime import *
from probe.reader_rapl import *

class Stresser(object):

    def __init__(self):
        self.reader_cpu  = ReaderCpu()
        self.reader_rapl = ReaderRapl()
        self.delay    = 1
        self.display  = True
        self.duration = 15
        self.output_csv = 'wcw.csv'
        self.output_nl  = '\n'
        self.output_init()

    def start(self):
        self.run(target_core=1, target_level=100, noise_core=2, noise_level=100)

    def run(self, target_core : int, noise_core : int, target_level : int = 100, noise_level : int = 100):
        # Launch the targeted process and some noise
        target = self.launch_stress(core=target_core, level=target_level)
        noise  = self.launch_stress(core=noise_core,  level=noise_level)
        iteration = 0
        while(target.poll() is None): # Target is alive
            usage_global  = self.reader_cpu.get_usage_global()
            usage_cores   = self.reader_cpu.get_usage_per_core()
            usage_process = self.reader_cpu.get_usage_per_core_of_pid(target.pid)
            usage_noise   = self.reader_cpu.get_usage_per_core_of_pid(noise.pid)
            watt_global   = self.reader_rapl.read_rapl()
            if self.display:
                print('####')
                print('usage_global ', usage_global)
                print('usage_cores  ', usage_cores)
                print('usage_process', usage_process)
                print('usage_noise  ', usage_noise)
                print('watt_global  ', watt_global)
            if iteration>0: # exclude first iteration as values are not initialised (or were initialised in previous run)
                self.output_append(iteration=iteration, target_core=target_core, target_level=target_level,\
                    noise_core=noise_core, noise_level=noise_level,\
                    usage_global=usage_global, usage_cores=usage_cores, usage_noise=usage_noise, watt_global=watt_global)
            iteration+=1
            time.sleep(self.delay)
        noise.wait() # Be sure that both pid are finished before returning to caller

    def launch_stress(self, core : int , level : int = 100) -> None:
        command = 'stress-ng --cpu ' + str(core) + ' -l ' + str(level) + ' --timeout ' + str(self.duration)
        subproc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #print("shell command result :", subproc.stdout.read().decode('ascii'))
        return subproc

    def output_init(self):
        header = 'label,iteration,target_core,target_level,noise_core,noise_level,TODO'
        with open(self.output_csv, 'w') as f: 
            f.write(header + self.output_nl)

    def output_append(self, iteration: int, target_core : int, noise_core : int, target_level : int, noise_level : int, usage_global : float, usage_cores : dict, usage_noise : dict, watt_global : dict):
        label= str(target_core) + '(' + str(target_level) + '%)_' + str(noise_core) + '(' + str(noise_level) + '%)'
        line = label + ',' + str(iteration) + ',' +\
            str(target_core) + ',' + str(target_level) + ',' +\
            str(noise_core) + ',' + str(noise_level) + ',' +\
            'TODO'
        with open(self.output_csv, 'a') as f: 
            f.write(line + self.output_nl)