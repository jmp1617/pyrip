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
SEND_CADENCE = 30  # seconds
PRINT_CADENCE = 10  # seconds

# debug
D_RECV = False
D_SEND = False
D_PRNT = False
