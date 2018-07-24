import sys
sys.path.append('.')
 
from Services import GameService
from Services import GamePlayer

from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer
 
import socket

ipTable = {'voyager':'192.168.0.34', 'viking':'192.168.0.42'}

if __name__ == "__main__":
    ip = sys.argv[1]
    ip = ipTable[ip]
    port = 9090
    source = int(sys.argv[2])
    target = int(sys.argv[3])
    action = int(sys.argv[4])
    data = int(sys.argv[5])
    # Make socket
    transport = TSocket.TSocket(ip, port)
    # Buffering is critical. Raw sockets are very slow
    transport = TTransport.TBufferedTransport(transport)
    # Wrap in a protocol
    protocol = TBinaryProtocol.TBinaryProtocol(transport)
    # Create a client to use the protocol encoder
    client = GameService.Client(protocol)
    transport.open()
    client.update(source, target, action, data)
    transport.close()
