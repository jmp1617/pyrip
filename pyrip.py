#!/bin/python3
import sys
import configuration

class Route_Entry:
    def __init__(self):
        pass

class Router:
    def __init__(self, ip):
        # load in configurations
        if configuration.QUEEG[0] == ip:
            self.name = "queeg"
            self.configuration = configuration.QUEEG
            self.connections = configuration.QUEEG_CONNECTIONS
        elif configuration.COMET[0] == ip:
            self.name = "comet"
            self.configuration = configuration.COMET
            self.connections = configuration.COMET_CONNECTIONS
        elif configuration.RHEA[0] == ip:
            self.name = "rhea"
            self.configuration = configuration.RHEA
            self.connections = configuration.RHEA_CONNECTIONS
        elif configuration.GLADOS[0] == ip:
            self.name = "glados"
            self.configuration = configuration.GLADOS
            self.connections = configuration.GLADOS_CONNECTIONS
        else:
            print("ip address not associated with any configuration. exiting.")
        self.ip = self.configuration[0]
        self.port = self.configuration[1]

    def start_rip(self):
        pass


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("not enough args. exiting.")
        exit()
    else:
        router = Router(sys.argv[1])
        router.start_rip()