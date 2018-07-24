import math
import os
from datetime import datetime
from time import sleep
import pigpio
import logging

class ReadPin:
  def __init__(self, pi):
    logging.info("readpin")
    self.pi = pi

  def readMessageFull(self, channel, level, ticks):
    return self.readMessage(channel)

  def readMessage(self, channel):
    value = self.pi.read(channel)
    if value != 0:
      return (False, 0) #already missed it?                                      
    # Loop until we read a 0, but should already be zero since this was triggered by
    # detecting a FALLING event
    while value:
      value = self.pi.read(channel)

    # Grab the start time of the command
    startTime = datetime.now()

    # Used to buffer the command pulses
    command = []

    # The end of the "command" happens when we read more than
    # a certain number of 1s (1 is off for my IR receiver)
    numOnes = 0

    # Used to keep track of transitions from 1 to 0
    previousVal = 0
    sum = 0

    while True:
      if value != previousVal:
        # The value has changed, so calculate the length of this run
        now = datetime.now()
        pulseLength = now - startTime

        if len(command) == 1:
          if abs(pulseLength.microseconds - 4500) > 1000:
            logging.info("header pulse 2: " + str(pulseLength.microseconds))
            return (False, 0)  

        else:
          if pulseLength.microseconds > 2000:
            logging.info("data pulse: " + str(pulseLength.microseconds))
            return (False, 0)

        startTime = now

        command.append((previousVal, pulseLength.microseconds))
        sum += pulseLength.microseconds
      if value:
          numOnes = numOnes + 1
      else:
          numOnes = 0
      
      if numOnes > 1000:
        break

      previousVal = value
      value = self.pi.read(channel)
	
    logging.info(str(sum/1000) + " millis total")
    result = 0
    print str(len(command))
    if len(command) == 67:
      print str(command)
      i = 2
      while i < 66:
        if not(command[i+1][1]/command[i][1] > 1 and command[i+1][1]>1000):
          result <<= 1
        else:
          result = (result << 1) | 1
        i+=2
      print format(result,'#034b')
      return (True, result)
    else:
      return (False, 0)



if __name__=='__main__':
  INPUT_WIRE = 23
  pi = pigpio.pi()
  pi.set_glitch_filter(INPUT_WIRE, 7000)
  rp = ReadPin(pi)
  pi.set_mode(INPUT_WIRE, pigpio.INPUT)
  pi.callback(INPUT_WIRE, pigpio.FALLING_EDGE, rp.readMessageFull) #, bouncetime=150)

  while True:
    sleep(1000) 
  
