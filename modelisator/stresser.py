import subprocess, time
from probe.reader_cputime import *
from probe.reader_rapl import *

class Stresser(object):

    def __init__(self):
        self.reader_cpu  = ReaderCpu()
        self.reader_rapl = ReaderRapl()

    def start(self):
        # Launch the targeted process and some noise
        target = self.launch_stress(core=4)
        noise  = self.launch_stress(core=4, level=50)
        while(target.poll() is None): # Target is alive
            print('####')
            print('global',self.reader_cpu.get_usage_global())
            print('core',self.reader_cpu.get_usage_per_core())
            print('pid', self.reader_cpu.get_usage_per_core_of_pid(target.pid))
            print('rapl',self.reader_rapl.read_rapl())
            time.sleep(1)

    def launch_stress(self, core : int , level : int = 100) -> None:
        command = 'stress-ng --cpu ' + str(core) + ' -l ' + str(level) + ' --timeout ' + str(10)
        subproc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #print("shell command result :", subproc.stdout.read().decode('ascii'))
        return subproc

    def wait_for_completion(self) -> None :
        if self.thread != None: self.thread.join()