#!/bin/python3
import sys
import configuration
import json
import threading
import time
import socket


# representation of the router routing table containing route entries
class RoutingTable:
    def __init__(self):
        self.entries = []
        self.lock = threading.Lock()

    def add_entry(self, route_entry):
        self.entries.append(route_entry)

    def remove_entry_with_address(self, address):
        for entry in self.entries:
            if entry.get_address() == address:
                self.entries.remove(entry)

    def expose_lock(self):
        return self.lock

    # function to convert table to json for UDP payload
    def to_json(self):
        json_arr = []
        for entry in self.entries:
            json_arr.append(entry.to_dict())
        return json.dumps(json_arr)


# represents a route to a destination address space
class RouteEntry:
    def __init__(self, address, mask_bits, nexthop, cost):
        self.address = address
        self.mask_bits = mask_bits
        self.nexthop = nexthop
        self.cost = cost

    def get_address(self):
        return self.address

    def to_dict(self):
        return {
            "address": str(self.address),
            "mask_bits": self.mask_bits,
            "next_hop": str(self.nexthop),
            "cost": self.cost
        }


class SenderT(threading.Thread):
    def __init__(self, s, routing_table, connections, port, *args, **kwargs):
        super(SenderT, self).__init__(*args, **kwargs)
        self.routing_table = routing_table
        self.connections = connections
        self.port = port
        self.socket = s

    def run(self):
        # send the routing table to each node in connections
        print(str(threading.current_thread()) + "Started") if configuration.D_SEND else print("", end='')
        while True:
            for connection in self.connections:
                while self.routing_table.expose_lock().locked():  # wait in case the table is being modified
                    pass
                print(str(threading.current_thread()) + " Sending table to " + str(connection)) if configuration.D_SEND else print("", end='')
                sent = self.socket.sendto(self.routing_table.to_json().encode(), connection)
                print(str(threading.current_thread()) + " Bytes sent: " + str(sent)) if configuration.D_SEND else print("", end='')
            time.sleep(configuration.SEND_CADENCE)


class PrinterT(threading.Thread):
    def __init__(self, routing_table, *args, **kwargs):
        super(PrinterT, self).__init__(*args, **kwargs)
        self.routing_table = routing_table

    def run(self):
        print(str(threading.current_thread()) + "Started") if configuration.D_PRNT else print("", end='')
        while True:
            while self.routing_table.expose_lock().locked():  # wait in case the table is being modified
                pass
            print(str(threading.current_thread()) + " Table:" + self.routing_table.to_json())  if configuration.D_PRNT else print("", end='')
            time.sleep(configuration.PRINT_CADENCE)


class ReceiverT(threading.Thread):
    def __init__(self, s, routing_table, connections, port, *args, **kwargs):
        super(ReceiverT, self).__init__(*args, **kwargs)
        self.routing_table = routing_table
        self.connections = connections
        self.port = port
        self.socket = s

    def run(self):
        print(str(threading.current_thread()) + "Started")  if configuration.D_RECV else print("", end='')
        while True:
            data, addr = self.socket.recvfrom(4096)
            print(str(threading.current_thread()) + 'Connection received from: ' + str(addr)) if configuration.D_RECV else print("", end='')
            print(str(threading.current_thread()) + 'Data:' + str(json.loads(data.decode('utf-8'))))  if configuration.D_RECV else print("", end='')
            self.routing_table.expose_lock().acquire()
            self.update_table(addr, json.loads(data.decode('utf-8')))
            self.routing_table.expose_lock().release()

    def update_table(self, source_of_update, sources_table):
        print(source_of_update)
        print(sources_table)


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
            exit()
        self.ip = self.configuration[0]
        self.port = self.configuration[1]
        self.routing_table = RoutingTable()
        # socket to be used for communication
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('', self.port))

    def start_rip(self):
        # prepare local router entry
        self_entry = RouteEntry(self.ip, 24, self.ip, 0)
        self.routing_table.add_entry(self_entry)

        # define threads
        threads = [SenderT(self.socket, self.routing_table, self.connections, self.port, name="Sender"),
                   PrinterT(self.routing_table, name="Printer"),
                   ReceiverT(self.socket, self.routing_table, self.connections, self.port, name="Receiver")]
        # start the threads
        for thread in threads:
            thread.start()

        # join all the threads
        for thread in threads:
            thread.join()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("not enough args. exiting.")
        exit()
    else:
        router = Router(sys.argv[1])
        router.start_rip()