#!/usr/bin/python

import sys
sys.path.append('.')

#import RPi.GPIO as GPIO

import pigpio
import socket
import time
import logging

from Services import GamePlayer
from Services import GameService

from threading import Timer

from IRUtils import Pyslinger
from IRUtils import ReadPin

from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer

ACTION_HIT = 1
ACTION_KILL = 2
ACTION_FINISH = 3
MAX_HEALTH = 5

def MyIP():
  return ((([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0])

ipTable = {} 

class GamePlayerHandler:
  def __init__(self, triggerPin, irReadPin, irSendPin, resetPin, id1Pin, id2Pin):
    self.log = {}

    ipTable[socket.getfqdn()] = MyIP()    

    self.playerID = 0
    self.health = 0
    self.weapon = 0
    self.teamMask = 0 
    self.shotCount = 0
    self.gameServer = ipTable[socket.getfqdn()]
    self.gameServerPort = 9090

    self.readIREnabled = True

    self.pi = pigpio.pi()

    self.pi.set_mode(irSendPin, pigpio.OUTPUT)
    self.pi.set_mode(irReadPin, pigpio.INPUT)
    self.pi.set_mode(triggerPin, pigpio.INPUT)
    self.pi.set_mode(id1Pin, pigpio.INPUT)
    self.pi.set_mode(id2Pin, pigpio.INPUT)
    self.pi.set_mode(resetPin, pigpio.INPUT)
    self.pi.set_pull_up_down(resetPin, pigpio.PUD_UP)
    self.pi.set_pull_up_down(triggerPin, pigpio.PUD_UP)
    self.pi.set_pull_up_down(id1Pin, pigpio.PUD_UP)
    self.pi.set_pull_up_down(id2Pin, pigpio.PUD_UP)

    self.irSend = Pyslinger.Pyslinger(self.pi, irSendPin)
    self.irRead = ReadPin.ReadPin(self.pi)

    self.teamMask = 85
    self.team = 0

    self.pi.set_glitch_filter(triggerPin, 500)
    self.pi.set_glitch_filter(irReadPin, 7000)
    self.pi.set_glitch_filter(resetPin, 8000)
    self.pi.callback(triggerPin, pigpio.FALLING_EDGE,self.trigger)
    self.pi.callback(irReadPin, pigpio.FALLING_EDGE,self.readIR)
    self.pi.callback(resetPin, pigpio.FALLING_EDGE,self.reset)
    self.id1Pin = id1Pin
    self.id2Pin = id2Pin
    self.readID()
    logging.info("Constructor Finished")

  def discover(self, serverName, serverIP):
    ipTable[serverName] = serverIP
    return self.readID()

  def readID(self):
    b1 = self.pi.read(self.id1Pin)
    b2 = self.pi.read(self.id2Pin)
    self.playerID = 1 << (b1 + 2*b2)
    if b1 == 0:
        self.teamMask = self.teamMask << 1
    logging.info("PlayerPin1 state is " + str(b1))
    logging.info("PlayerPin2 state is " + str(b2))
    logging.info("Player ID is " + str(self.playerID))
    return self.playerID

  def getName(self):
    return socket.getfqdn()

  def getTeam(self):
    return self.team

  def trigger(self, channel,level,tick):
    self.readIREnabled = False
    logging.info("TRIGGER!")
    self.fire()
    self.readIREnabled = True
 
  def startGame(self, server, gameMode, playerID, teamMask):
    logging.info("===================================")
    logging.info("start()")
    logging.info("gameMode is " + str(gameMode))
    #self.playerID = playerID
    self.teamMask = teamMask
    self.health = MAX_HEALTH
    self.weapon = 0
    self.gameServer = server
    self.gameServerPort = 9090
    logging.info("===================================")

  def endGame(self):
    #self.updateServer(0, self.playerID, ACTION_FINISH, self.shotCount)
    self.health = 0
    self.shotCount = 0
    logging.info("===================================")
    logging.info("endGame()")
    logging.info("===================================")
 
  def message(self, source, message):
    logging.info("===================================")
    logging.info("message()")
    logging.info("Source is  " +str(source))
    logging.info("Message is " + message)
    logging.info("===================================")

  def fire(self):
    logging.info("===================================")
    logging.info("fire()")
    logging.info("Weapon is    " + str(self.weapon))
    logging.info("Team Mask is " + str(self.teamMask))
    logging.info("Player id is " +str(self.playerID))
    if self.health > 0:
      code = 0xFFFFFFFF & ((self.weapon << 16) | self.playerID)
      #code = 0xF0F0F0F0
      binc = format(code,'#034b')[2:] + "1"
      logging.info( binc )
      #irSender = Pyslinger.Pyslinger(self.irSendPin)
      self.irSend.send_code(binc)
      logging.info("ir message sent")
      self.shotCount += 1
      os.system('aplay /home/pi/irpy/fire.wav')
    else:
      logging.info("No fire, health = 0!")
    logging.info("===================================")

  def hit(self, source, weapon):
    logging.info("===================================")
    logging.info("hit()")
    logging.info("Source is " + str(source))
    logging.info("Weapon is " + str(weapon))
    if source & self.teamMask != 0:
      logging.info("Same team")
    else:
      damage = 1
      if self.health - damage <= 0:
        logging.info("Kill shot!")
        self.die()
        self.updateServer(source, self.playerID, ACTION_KILL, weapon)
      else:
        logging.info("Health was " + str(self.health))
        self.health -= damage
        logging.info("Health is now " + str(self.health))
        self.updateServer(source, self.playerID, ACTION_HIT, weapon)
    logging.info("===================================")

  def die(self):
    logging.info("Death!")
    self.health = 0

  def revive(self):
    logging.info("Revive!")
    t = Timer(10, self.regenerate)
    self.readIREnabled = False
    t.start() #self.health = MAX_HEALTH

  def regenerate(self):
    self.health = MAX_HEALTH
    self.readIREnabled = True
    logging.info("Regenerated")

  def reset(self,channel,level,tick):
    self.updateServer(0,0,4,0)

  def updateServer(self, source, target, action, data):    
    try:
        
        # Make socket
        transport = TSocket.TSocket(self.gameServer, self.gameServerPort)
        # Buffering is critical. Raw sockets are very slow
        transport = TTransport.TBufferedTransport(transport)
        # Wrap in a protocol
        protocol = TBinaryProtocol.TBinaryProtocol(transport)
        # Create a client to use the protocol encoder
        client = GameService.Client(protocol)
        # Connect!
        transport.open()
        result = client.update(source, target, action, data)
        logging.info(str(result))
        # Close!
        transport.close()
    except Thrift.TException, tx:
        logging.info(tx.message)

  def readIR(self, channel,level,tick):
        if  not self.readIREnabled:
          return
        if self.irSend.pigpio.wave_tx_busy():
          logging.info("Busy sending")
          return

        #logging.info("read ir" + str(channel))
        result = self.irRead.readMessage(channel)
        
        if result[0]:
            logging.info(format(result[1], '#034b'))
            value = result[1]
            shooterID = value & 0x0000FFFF
            weapon = (value & 0xFFFF0000) >> 16
            self.hit(shooterID, weapon)

if __name__ == '__main__':
    logging.basicConfig(filename='/home/pi/Player.log',level=logging.DEBUG)
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.info("Logging initialized")

    while True:
        try:
            logging.info("Creating GamePlayerHandler")
            handler = GamePlayerHandler(17, 23, 18,  22, 5, 6) #irsend pin is always bcm
            logging.info("Creating Processor")
            processor = GamePlayer.Processor(handler)  
            #ip = getLocalIP()
            logging.info("Getting hostname")
            ip = socket.getfqdn()
            if len(sys.argv) > 1:
                ip = sys.argv[1]
            logging.info("Player IP = " + MyIP())
            ip = MyIP()
            transport = TSocket.TServerSocket(host=ip, port=28900)
            tfactory = TTransport.TBufferedTransportFactory()
            pfactory = TBinaryProtocol.TBinaryProtocolFactory()
            server = TServer.TSimpleServer(processor, transport, tfactory, pfactory)
            logging.info('Starting the player server...')
            server.serve()
        except (SystemExit, KeyboardInterrupt):
            logging.info("bad exception")
            transport.close()
            handler.irSend.cleanup()
            exit(0)
        except:
            logging.info("sleeping for a bit")
            time.sleep(5)
            logging.info("done sleeping")
        
    logging.info('done.')

