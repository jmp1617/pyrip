# router_name = (address, port)

QUEEG = ('129.21.30.37', 5000)
COMET = ('129.21.34.80', 5000)
RHEA = ('129.21.27.49', 5000)
GLADOS = ('129.21.22.196', 5000)

# topology configuration
QUEEG_CONNECTIONS = [COMET, GLADOS]
COMET_CONNECTIONS = [QUEEG, RHEA]
RHEA_CONNECTIONS = [COMET, GLADOS]
GLADOS_CONNECTIONS = [RHEA, QUEEG]

# timers
SEND_CADENCE = 1  # seconds
PRINT_CADENCE = 5 # seconds

# debug
D_RECV = False  # print rec thread info
D_SEND = False  # print send thread info
D_PRNT = False  # print print thread info
D_POISON = False  # print ttl and cooldown information

# subnet mask bits. Example: 255.255.255.0 = 24 = /24
SUB_BITS = 24

# poison reverse
HOP_LIMIT = 16 # default to spec
# hold down time after receiving a router state change. Time needed for all updates or router state change to prop.
HOLD_DOWN = 3  # seconds

# allowances for no contact
# this refers to the amount of times a router can not hear from another router each send cycle before declaring dead.
# example: TTL = 4 * SEND_CADENCE = 30 = 2 minutes. must be greater than 1.
TTL = 5
