import sys
sys.path.append('.')
 
import socket
import logging

from Services import GameService
from Services import GamePlayer

from thrift import Thrift

from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

ACTION_HIT = 1
ACTION_KILL = 2
ACTION_FINISH = 3
MAX_HEALTH = 10
ACTION_RESET = 4
ACTION_SHOT = 5
ACTION_STATS = 6

INIT_PIN = 22

ipTable = {}

ipSearchList = (15,42)

def MyIP():
  return ((([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0])

class Game:
  def __init__(self, gameMode, players,server):
    self.gameMode = gameMode
    self.players = players
    self.kills = {}
    self.deaths = {}
    self.shots = {}
    self.hits = {}
    self.server = server
    for player in self.players:
      logging.info("Resetting player " + str(player))
      self.kills[player] = 0
      self.deaths[player] = 0
      self.shots[player] = 0
      self.hits[player] = 0

  def update(self, source, target, action, data):
    logging.info("Updating stats")
    logging.info(str(source) + ", " + str(target) + ", " + str(action) + ", " + str(data))
    if action == ACTION_HIT:
      self.hits[source] += 1
    if action == ACTION_KILL:
      logging.info("Current kills for " + str(source) + " = " + str(self.kills[source]))
      self.kills[source] += 1
      logging.info("Current kills for " + str(source) + " = " + str(self.kills[source]))
      self.deaths[target] += 1
      logging.info("Recorded kill")
    if action == ACTION_FINISH:
      self.shots[source] = data

  def checkComplete(self):
    return True

  def reset(self):
    logging.info("reset")
    for player in self.players:
      logging.info("Resetting player " + str(player))
      self.kills[player] = 0
      self.deaths[player] = 0
      self.shots[player] = 0
      self.hits[player] = 0
    self.server.initGame(self.gameMode)

  def printStats(self):
    logging.info( str(self.players) )
    for player in self.players:
      logging.info("==================")
      logging.info("Player " + str(player))
      logging.info("  kills: " + str(self.kills[player]))
      logging.info("  hits: " + str(self.hits[player]))
      logging.info("  shots: " + str(self.shots[player]))
      logging.info("  deaths: " + str(self.deaths[player]))
      logging.info("==================")

class DeathMatch(Game):
  def __init__(self, gameMode, players,server, maxKills):
    Game.__init__(self, gameMode,players,server)
    self.maxKills = maxKills

  def checkComplete(self):
    logging.info("Check complete")
    nPlayers = len(self.players)
    print str(nPlayers)
    totalKills = 0
    for (playerID,killCount) in self.kills.items():
      totalKills += killCount
      print str(playerID) + " has " + str(killCount) + " kills"
      if killCount == self.maxKills:
        return True
    print str(totalKills)
    return False

  def update(self, source, target, action, data):
    Game.update(self, source, target, action, data)
    logging.info("len(Players) = " + str(len(self.players)))
    print str(self.players)
    logging.info("foo")
    if action == ACTION_KILL:
      logging.info("reviving player " + str(target))
      key = int(target)
      logging.info("player address = " + self.server.players[key])
      transport,client = self.server.getPlayerClient(self.server.players[target],28900)
      transport.open()
      client.revive()
      transport.close()

  def printStats(self):
    logging.info("Calling Game.printStats()")
    Game.printStats(self)
    
class GameServerHandler:
  def __init__(self):
    self.log = {}
    self.players = {} 
    self.updatePlayerList()
    self.hostName = MyIP()
    self.port = 9090
    dm5 = DeathMatch(1, self.players.keys(), self, 5)
    dm10 = DeathMatch(2, self.players.keys(), self, 10)
    self.games = {1:dm5, 2:dm10}
    self.game = self.games[1]
    self.myIP = MyIP()

  def updatePlayerList(self):
    for i in ipSearchList:
      ip = '192.168.0.' + str(i)
      transport,pc = self.getPlayerClient(ip, 28900)
      try:
        transport.open()
        playerName = pc.getName()
        ipTable[playerName] = ip
        pid = pc.readID()
        logging.info("Found player " + playerName + " at " + ip + " with id " + str(pid))
        self.players[pid] = playerName
        transport.close()
      except:
        logging.info(ip + ' not available')

  def s16(self, value):
    return -(value & 0x8000) | (value & 0x7fff)

  def initGame(self, gameMode):
    logging.info("init game")
    self.game = self.games[gameMode]
    logging.info("players")
    print len(self.players)
    print str(self.players)
    for (playerID,playerName) in self.players.items():
      logging.info("Connecting to " + playerName + " at " + ipTable[playerName])
      transport,client = self.getPlayerClient(ipTable[playerName], 28900)
      logging.info("Opening transport")
      transport.open()
      logging.info("Sending command") 
      print self.hostName
      print str(gameMode)
      print str(playerID)
      plyr = self.s16(playerID)
      client.startGame(self.hostName, gameMode, plyr, 0)
      logging.info("Command sent")
      transport.close()
      logging.info("Done")

  def update(self, source, target, action, data):
    logging.info("===================================")
    logging.info("update()")
    logging.info("Source is " + str(source))
    logging.info("Target is " + str(target))
    logging.info("Action is " + str(action))
    logging.info("Data   is " + str(data))
    logging.info("===================================")
    if action == ACTION_RESET:
      self.initGame(1)
      return
    self.game.update(source, target, action, data)
    if self.game.checkComplete():
      for (playerID,playerName) in self.players.items():
        transport,client = self.getPlayerClient(ipTable[playerName], 28900)
        transport.open()
        logging.info("Sending endGame()")
        client.endGame()
        transport.close()
      logging.info("Printing stats")
      self.game.printStats()
      self.game.reset()

  def message(self, source, target, message):
    logging.info("===================================")
    logging.info("message()")
    logging.info("Source is " + str(source))
    logging.info("Target is " + str(target))
    logging.info("Message is " + message)

  def getPlayerClient(self, ip, port):
    logging.info("creating transport")
    transport = TSocket.TSocket(ip, port)
    logging.info("creating protocol")
    transport = TTransport.TBufferedTransport(transport)
    protocol = TBinaryProtocol.TBinaryProtocol(transport)
    logging.info("creating client")
    client = GamePlayer.Client(protocol)
    return (transport, client)

if __name__ == '__main__':
    logging.basicConfig(filename='/home/pi/Server.log',level=logging.DEBUG)
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.info("Main server method")
    handler = GameServerHandler()
    handler.port = 9090
    processor = GameService.Processor(handler)
    transport = TSocket.TServerSocket(handler.hostName, handler.port)
    tfactory = TTransport.TBufferedTransportFactory()
    pfactory = TBinaryProtocol.TBinaryProtocolFactory()

    server = TServer.TSimpleServer(processor, transport, tfactory, pfactory)

    handler.updatePlayerList()

    logging.info("Created handler")


    logging.info('Starting the server...')
    server.serve()
    logging.info('done.')

