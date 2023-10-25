import os, sys, getopt, threading, subprocess

class StressThread(object):

    def __init__(self):
        pass

    def launch(self, core : int , level : int = 100) -> None:
        core = 1
        level = 100
        def stress(core : int, level : int = 100):
            command = 'stress-ng --cpu ' + str(core) + ' -l ' + str(level) + ' --timeout ' + str(2)
            subproc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.pid = subproc.pid
            #print("shell command result :", subproc.stdout.read().decode('ascii'))

        self.thread = threading.Thread(target=stress, args=(core, level))
        self.thread.start()

    def wait_for_completion(self):
        if self.thread != None: self.thread.join()


t = StressThread()
t.launch(1)
t.wait_for_completion()