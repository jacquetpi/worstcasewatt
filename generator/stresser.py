import subprocess, time, base64
from probe.reader_cputime import *
from probe.reader_rapl import *
from datetime import datetime

class Stresser(object):

    def __init__(self):
        self.reader_cpu  = ReaderCpu()
        self.reader_rapl = ReaderRapl()
        self.delay    = 1
        self.display  = True
        self.duration = 3
        timestamp = str(int(time.time()))
        self.output_file_exp  = '_measures/' + timestamp + '-experiments.csv'
        self.output_file_data = '_measures/' + timestamp + '-data.csv'
        self.output_nl  = '\n'
        self.output_init()

    def start(self):
        cpu_config = 8
        levels = [50,100]
        run_count = self.__start(cpu_config, levels, no_launch=True)
        if self.display:
            print('>Estimated run', run_count, ' - duration : ', run_count*self.duration, 'seconds (', round(run_count*self.duration/60,1), 'minutes)')
            print('>End estimated at', datetime.fromtimestamp(int(time.time()+run_count*self.duration*1.1)))
        run_count = self.__start(cpu_config, levels, run_total=run_count)

    def __start(self, cpu_config : int, levels : list, no_launch : bool = False, run_total : int = None):
        run_count = 0
        for noise_core in range(0, cpu_config+1, 2):

            considered_noise_levels = levels if noise_core>0 else [100]
            for noise_level in considered_noise_levels:

                for target_core in range(0,cpu_config+1, 2):

                    considered_target_levels = levels if target_core>0 else [100]
                    for target_level in considered_target_levels:

                        estimated_usage = (target_core*(target_level/100)) + (noise_core*(noise_level/100))
                        if estimated_usage>cpu_config: continue
                        #print(target_core, target_level, '|', noise_core, noise_level, '|', estimated_usage)
                        if not no_launch: self.run(target_core=target_core, target_level=target_level, noise_core=noise_core, noise_level=noise_level)
                        run_count+=1
                        if (not no_launch) and (run_total is not None) and self.display: print('>Progress:', round((run_count/run_total*100),1), '%')
                        
        return run_count

    def run(self, target_core : int, noise_core : int, target_level : int = 100, noise_level : int = 100):
        # Launch the targeted process and some noise
        target = self.launch_stress(core=target_core, level=target_level)
        noise  = self.launch_stress(core=noise_core,  level=noise_level)
        iteration = 0
        while(self.is_alive(target, noise)):
            usage_global  = self.reader_cpu.get_usage_global()
            usage_cores   = self.reader_cpu.get_usage_per_core()
            usage_process = self.reader_cpu.get_usage_per_core_of_pid(target.pid) if target is not None else {}
            usage_noise   = self.reader_cpu.get_usage_per_core_of_pid(noise.pid)  if noise  is not None else {}
            watt_global   = self.reader_rapl.read_rapl()
            # if self.display:
            #     print('####')
            #     print('usage_global ', usage_global)
            #     print('usage_cores  ', usage_cores)
            #     print('usage_process', usage_process)
            #     print('usage_noise  ', usage_noise)
            #     print('watt_global  ', watt_global)
            if iteration>0: # exclude first iteration as values are not initialised (or were initialised in previous run)
                self.output_append(iteration=iteration, target_core=target_core, target_level=target_level,\
                    noise_core=noise_core, noise_level=noise_level,\
                    usage_global=usage_global, usage_cores=usage_cores, usage_process=usage_process, usage_noise=usage_noise, watt_global=watt_global)
            iteration+=1
            time.sleep(self.delay)

    def launch_stress(self, core : int , level : int = 100) -> None:
        if core<=0: 
            command = 'sleep ' + str(self.duration)
        else:
            command = 'stress-ng --cpu ' + str(core) + ' -l ' + str(level) + ' --timeout ' + str(self.duration)
        subproc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #print("shell command result :", subproc.stdout.read().decode('ascii'))
        return subproc

    def is_alive(self, target, noise):
        is_alive = False
        if  (target != None and target.poll() is None): is_alive = True
        elif(noise  != None and noise.poll() is None) : is_alive = True
        return is_alive

    def output_init(self):
        if self.output_file_exp is None: return
        header_exp  = 'situation_id,target_id,noise_id,target_core,target_level,noise_core,noise_level,iteration,global_usage,global_watt,measure_id' 
        header_data = 'measure_id,type,name,value'
        with open(self.output_file_exp, 'w')  as f: f.write(header_exp + self.output_nl)
        with open(self.output_file_data, 'w') as f: f.write(header_data + self.output_nl)

    def output_append(self, iteration: int, target_core : int, noise_core : int, target_level : int, noise_level : int, usage_global : float, usage_cores : dict, usage_process : dict, usage_noise : dict, watt_global : dict):
        if self.output_file_exp is None: return
        
        label_target = str(target_core) + '-' + str(target_level)
        label_noise  = str(noise_core) + '-' + str(noise_level)
        label        = label_target + '_' + label_noise
        target_id    = base64.b64encode((label_target).encode('ascii')).decode('ascii')
        noise_id     = base64.b64encode((label_noise).encode('ascii')).decode('ascii')
        situation_id = base64.b64encode((label).encode('ascii')).decode('ascii') 
        measure_id   = base64.b64encode((label + '-' + str(iteration)).encode('ascii')).decode('ascii') 

        line_exp  = situation_id + ',' + target_id + ',' + noise_id + ',' +\
            str(target_core) + ',' + str(target_level) + ',' +\
            str(noise_core) + ',' + str(noise_level) + ',' +\
            str(iteration) + ',' +\
            str(usage_global) + ',' + str(watt_global['package-global']) + ',' + measure_id

        with open(self.output_file_exp, 'a')  as f: f.write(line_exp + self.output_nl)

        for core_id, core_usage in usage_cores.items():
            line_data = measure_id + ',' + 'core' + ',' + str(core_id) + ',' + str(core_usage)
            with open(self.output_file_data, 'a') as f: f.write(line_data + self.output_nl)

        for process_id, process_usage in usage_process.items():
            if process_usage <= 0: continue
            line_data = measure_id + ',' + 'process' + ',' + str(process_id) + ',' + str(process_usage)
            with open(self.output_file_data, 'a') as f: f.write(line_data + self.output_nl)

        for noise_id, noise_usage in usage_noise.items():
            if noise_usage <= 0: continue
            line_data = measure_id + ',' + 'noise' + ',' + str(noise_id) + ',' + str(noise_usage)
            with open(self.output_file_data, 'a') as f: f.write(line_data + self.output_nl)

        for rapl_domain, rapl_value in watt_global.items():
            line_data = measure_id + ',' + 'rapl' + ',' + rapl_domain + ',' + str(rapl_value)
            with open(self.output_file_data, 'a') as f: f.write(line_data + self.output_nl)