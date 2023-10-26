import getopt, sys, json
from modelisator.stresser import Stresser

def print_usage():
    print("")

if __name__ == '__main__':

    short_options = "h"
    long_options = ["help"]

    # Arguments management
    try:
        arguments, values = getopt.getopt(sys.argv[1:], short_options, long_options)
    except getopt.error as err:
        print(str(err))
        print_usage()
    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            print_usage()
        elif current_argument in('-d', '--distribution'):
            pass
        else:
            print_usage()
            
    # Entrypoint
    try:
        stresser = Stresser()
        stresser.start()
    except KeyboardInterrupt:
        print("Program interrupted")
