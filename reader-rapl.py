import re
from os import listdir

ROOT_FS       ='/sys/class/powercap/'
PRECISION     = 5

class ReaderRapl(object):

    def __init__(self):
        self.sysfs = self.find_rapl_sysfs()

    ###########################################
    # Find relevant sysfs
    ###########################################
    def find_rapl_sysfs():
        regex = '^intel-rapl:[0-9]+.*$'
        folders = [f for f in listdir(ROOT_FS) if re.match(regex, f)]
        # package0: cpu, cores: cores of cpu, uncore : gpu, psys: platform ...
        sysfs = dict()
        for folder in folders:
            base = ROOT_FS + folder
            with open(base + '/name') as f:
                domain = f.read().replace('\n','')
            if '-' not in domain: domain+= '-' + folder.split(':')[1] # We guarantee name unicity
            sysfs[domain] = base + '/energy_uj'
        return sysfs

    ###########################################
    # Read joule file, convert to watt
    ###########################################
    def read_rapl(self, hist : dict, current_time : int):
        measures = dict()
        overflow = False
        package_global = 0
        for domain, file in self.sysfs.items():
            watt = self.__read_joule_file(domain=domain, file=file, hist=hist, current_time=current_time)
            if watt !=None:
                measures[domain] = round(watt,PRECISION)
                if 'package-' in domain: package_global+=watt
            else: overflow=True

        # Track time for next round
        hist['time'] = current_time

        if measures:
            if not overflow: measures['package-global'] = round(package_global,PRECISION)
        return measures

    def __read_joule_file(self, domain : str, file : str, hist : dict, current_time : int):
        # Read file
        with open(file, 'r') as f: current_uj_count = int(f.read())

        # Compute delta
        current_uj_delta = current_uj_count - hist[domain] if hist[domain] != None else None
        hist[domain] = current_uj_count # Manage hist for next delta

        # Manage exceptional cases
        if current_uj_delta == None: return None # First call
        if current_uj_delta < 0: return None # Overflow

        # Convert to watt
        current_us_delta = (current_time - hist['time'])/1000 #delta with ns to us
        current_watt = current_uj_delta/current_us_delta

        return current_watt