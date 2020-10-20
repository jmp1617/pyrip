#!/bin/python3
import sys
import configuration
import json
import threading
import time
import socket


# calculate a subnet from an address in that subnet and the number of mask bits per octet
def calculate_subnet(ip_address, mask_bits):
    octet_arr = ip_address.split('.')
    subnet_octet_arr = []
    bits_remaining = mask_bits
    for octet in octet_arr:  # go through all octets and mask appropriately
        if bits_remaining >= 8:
            subnet_octet_arr.append(0xFF & int(octet))
            bits_remaining -= 8
        elif bits_remaining == 0:
            subnet_octet_arr.append(0)
        else:
            mask = 0
            bits_pushed = 0
            for bits_pushed in range(0, bits_remaining):
                mask = mask ^ 1
                mask = mask << 1
            for i in range(0, 7 - bits_pushed):  # already shifted once
                mask = mask << 1
            subnet_octet_arr.append(mask & int(octet))
    return str(
        subnet_octet_arr[0]
    ) + '.' + str(
        subnet_octet_arr[1]
    ) + '.' + str(
        subnet_octet_arr[2]
    ) + '.' + str(
        subnet_octet_arr[3]
    )


# representation of the router routing table containing route entries
class RoutingTable:
    def __init__(self):
        self.entries = []
        self.lock = threading.Lock()  # lock for sharing the table between the receiving and sending threads

    def add_entry(self, route_entry):
        self.entries.append(route_entry)

    def remove_entry_with_address(self, address):
        for entry in self.entries:
            if entry.get_address() == address:
                self.entries.remove(entry)

    def expose_lock(self):
        return self.lock

    # helper function to convert table to json for UDP payload
    def to_json(self, connection):
        json_arr = []
        for entry in self.entries:
            # dont send routes learned from neighbor to itself
            if entry.get_nexthop() != connection[0]:
                json_arr.append(entry.to_dict())
        return json.dumps(json_arr)

    def get_entries(self):
        return self.entries

    def get_all_subnets(self):
        subnets = []
        for entry in self.entries:
            subnets.append(entry.get_subnet())
        return subnets

    def get_cost_with_subnet(self, subnet):
        for entry in self.entries:
            if subnet == entry.get_subnet():
                return entry.get_cost()
        return -1

    def update_entry_with_subnet(self, subnet, address, mask_bits, nexthop, cost):
        for entry in self.entries:
            if subnet == entry.get_subnet():
                entry.update(address, mask_bits, nexthop, cost)

    def reset_ttl_of_entry_with_address(self, address):
        for entry in self.entries:
            if address == entry.get_address():
                entry.reset_ttl()


# represents a route to a destination address space
class RouteEntry:
    def __init__(self, address, mask_bits, nexthop, cost):
        self.address = address
        self.mask_bits = mask_bits
        self.nexthop = nexthop
        self.subnet = calculate_subnet(self.address, self.mask_bits)
        self.cost = cost
        self.ttl = configuration.TTL

    def get_address(self):
        return self.address

    def get_mask_bits(self):
        return self.mask_bits

    def get_nexthop(self):
        return self.nexthop

    def get_cost(self):
        return self.cost

    def poison(self):
        self.cost = configuration.HOP_LIMIT

    def get_subnet(self):
        return self.subnet

    def __eq__(self, other):
        return self.subnet == other.get_subnet()

    def reset_ttl(self):
        self.ttl = configuration.TTL

    def decrement_ttl(self):
        self.ttl = self.ttl - 1

    def get_ttl(self):
        return self.ttl

    # in place update of entry
    def update(self, address, mask_bits, nexthop, cost):
        self.address = address
        self.mask_bits = mask_bits
        self.nexthop = nexthop
        self.subnet = calculate_subnet(self.address, self.mask_bits)
        self.cost = cost

    def to_dict(self):
        return {
            "address": str(self.address),
            "mask_bits": self.mask_bits,
            "next_hop": str(self.nexthop),
            "subnet": str(self.subnet),
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
        # neighbors addresses
        conn_addr = []
        for connection in self.connections:
            conn_addr.append(connection[0])  # load in neighbors addresses for later
        # send the routing table to each node in connections
        print(str(threading.current_thread()) + "Started") if configuration.D_SEND else print("", end='')
        while True:
            for connection in self.connections:
                while self.routing_table.expose_lock().locked():  # wait in case the table is being modified
                    pass
                print(str(threading.current_thread()) + " Sending table to " + str(connection)) \
                    if configuration.D_SEND else print("", end='')
                # send all routes except those learned from the destination neighbor ( split horizon )
                sent = self.socket.sendto(self.routing_table.to_json(connection).encode(), connection)
                print(str(threading.current_thread()) + " Bytes sent: " + str(sent)) \
                    if configuration.D_SEND else print("", end='')
            # poison calculations
            while self.routing_table.expose_lock().locked():  # wait in case the table is being modified
                pass
            self.routing_table.expose_lock().acquire()
            for entry in self.routing_table.get_entries():
                ttl = entry.get_ttl()
                # don't have the router poison itself and only if neighbor
                if entry.get_cost() != 0 and entry.get_address() in conn_addr:
                    if ttl <= 0:  # the router hasn't been heard from in configuration.TTL send cycles
                        # of configuration.SEND_CADENCE seconds.
                        entry.poison()  # it got to low
                    else:
                        entry.decrement_ttl()
            self.routing_table.expose_lock().release()
            # sleep
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
            self.display()
            time.sleep(configuration.PRINT_CADENCE)

    def display(self):
        print("+-------------------+-------------------+-----------------+")
        print("|Address____________|Next-hop___________|Cost_____________|")
        print("+-------------------+-------------------+-----------------+")
        for entry in self.routing_table.get_entries():
            subnet = entry.get_subnet()
            print("|" + subnet + "/" + str(entry.get_mask_bits()), end='')
            for i in range(0, 18 - (len(subnet) + len(str(entry.get_mask_bits())))):
                print("_", end='')
            print("|" + entry.get_nexthop(), end='')
            for i in range(0, 19 - len(entry.get_nexthop())):
                print("_", end='')
            print("|" + str(entry.get_cost()), end='')
            for i in range(0, 17 - len(str(entry.get_cost()))):
                print("_", end='')
            print('|')
        print("+---------------------------------------------------------+\n")


class ReceiverT(threading.Thread):
    def __init__(self, s, routing_table, self_ip, connections, port, *args, **kwargs):
        super(ReceiverT, self).__init__(*args, **kwargs)
        self.routing_table = routing_table
        self.connections = connections
        self.port = port
        self.socket = s
        self.self_ip = self_ip

    def run(self):
        print(str(threading.current_thread()) + "Started") if configuration.D_RECV else print("", end='')
        while True:
            data, addr = self.socket.recvfrom(4096)
            print(str(threading.current_thread()) + 'Connection received from: ' + str(
                addr)) if configuration.D_RECV else print("", end='')
            print(str(threading.current_thread()) + 'Data:' + str(
                json.loads(data.decode('utf-8')))) if configuration.D_RECV else print("", end='')
            while self.routing_table.expose_lock().locked():  # wait in case the table is being modified
                pass
            self.routing_table.expose_lock().acquire()
            self.update_table(addr, json.loads(data.decode('utf-8')))
            # since we heard from the router we can reset its ttl as it is alive
            # only reset if the router is one of the neighbors
            conn_addr = []
            for connection in self.connections:
                conn_addr.append(connection[0])
            if addr[0] in conn_addr:
                self.routing_table.reset_ttl_of_entry_with_address(addr[0])
            self.routing_table.expose_lock().release()

    def update_table(self, source_of_update, sources_table):
        # if the entry doesnt exist in this routers table, add it and calculate the cost
        # ( add one to all as route cost is 1 )
        # add one because it is coming from a router 1 cost unit away aka neighbor
        for entry in sources_table:
            if entry['subnet'] not in self.routing_table.get_all_subnets():
                # this also takes care of looping. Since the router tracks itself, its network is always in the table
                # so count to infinity wont happen
                self.routing_table.add_entry(RouteEntry(
                    entry['address'], entry['mask_bits'], source_of_update[0], entry['cost'] + 1
                ))
            else:  # see if this new path is less than the one already present
                original_cost = self.routing_table.get_cost_with_subnet(entry['subnet'])
                if entry['cost'] == configuration.HOP_LIMIT:
                    new_possible_cost = configuration.HOP_LIMIT
                else:
                    new_possible_cost = entry['cost'] + 1
                # if the cost to get to the destination network is less from the new update table, update the routing
                # table to use this cheaper route. Dont accept a route back through self.
                if (
                        new_possible_cost < original_cost or
                        new_possible_cost == configuration.HOP_LIMIT
                ):
                    self.routing_table.update_entry_with_subnet(
                        entry['subnet'], entry['address'], entry['mask_bits'], source_of_update[0], new_possible_cost
                    )
                    if entry['cost'] == configuration.HOP_LIMIT and original_cost != configuration.HOP_LIMIT:
                        # poison reverse, send all routes
                        self.socket.sendto(self.routing_table.to_json(("", 0)).encode(), source_of_update)


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
        self_entry = RouteEntry(self.ip, configuration.SUB_BITS, self.ip, 0)
        self.routing_table.add_entry(self_entry)

        # define threads
        threads = [SenderT(self.socket, self.routing_table, self.connections, self.port, name="Sender"),
                   PrinterT(self.routing_table, name="Printer"),
                   ReceiverT(self.socket, self.routing_table, self.ip, self.connections, self.port, name="Receiver")]
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
