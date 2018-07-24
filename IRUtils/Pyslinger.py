#!/usr/bin/env python3
# Python IR transmitter
# Requires pigpio library
# Supports NEC, RC-5 and raw IR.
# Danijel Tudek, Aug 2016 << Thank you Danijel for original source -AFS

import ctypes
import time
import sys

import pigpio
import logging

# Since both NEC and RC-5 protocols use the same method for generating waveform,
# it can be put in a separate class and called from both protocol's classes.
class Wave_generator():
    def __init__(self,protocol):
        self.protocol = protocol
        self.pulses = [] #Pulses_array()
        self.pulse_count = 0

    def add_pulse(self, gpioOn, gpioOff, usDelay):
        self.pulses.append(pigpio.pulse(gpioOn, gpioOff, usDelay)) 

    # Pull the specified output pin low
    def zero(self, duration):
        self.add_pulse(0, 1 << self.protocol.master.gpio_pin, duration)

    # Protocol-agnostic square wave generator
    def one(self, duration):
        period_time = 1000000.0 / self.protocol.frequency
        on_duration = int(round(period_time * self.protocol.duty_cycle))
        off_duration = int(round(period_time * (1.0 - self.protocol.duty_cycle)))
        total_periods = int(round(duration/period_time))
        total_pulses = total_periods * 2

        # Generate square wave on the specified output pin
        for i in range(total_pulses):
            if i % 2 == 0:
                self.add_pulse(1 << self.protocol.master.gpio_pin, 0, on_duration)
            else:
                self.add_pulse(0, 1 << self.protocol.master.gpio_pin, off_duration)

    def clear(self):
        self.__init__(self.protocol)

# NEC protocol class
class NEC():
    def __init__(self,
                master,
                frequency=38000,
                duty_cycle=0.33,
                leading_pulse_duration=9000,
                leading_gap_duration=4500,
                one_pulse_duration = 562,
                one_gap_duration = 1686,
                zero_pulse_duration = 562,
                zero_gap_duration = 562,
                trailing_pulse = 0):
        self.master = master
        self.wave_generator = Wave_generator(self)
        self.frequency = frequency # in Hz, 38000 per specification
        self.duty_cycle = duty_cycle # duty cycle of high state pulse
        # Durations of high pulse and low "gap".
        # The NEC protocol defines pulse and gap lengths, but we can never expect
        # that any given TV will follow the protocol specification.
        self.leading_pulse_duration = leading_pulse_duration # in microseconds, 9000 per specification
        self.leading_gap_duration = leading_gap_duration # in microseconds, 4500 per specification
        self.one_pulse_duration = one_pulse_duration # in microseconds, 562 per specification
        self.one_gap_duration = one_gap_duration # in microseconds, 1686 per specification
        self.zero_pulse_duration = zero_pulse_duration # in microseconds, 562 per specification
        self.zero_gap_duration = zero_gap_duration # in microseconds, 562 per specification
        self.trailing_pulse = trailing_pulse # trailing 562 microseconds pulse, some remotes send it, some don't
        logging.info("NEC protocol initialized")

    # Send AGC burst before transmission
    def send_agc(self):
        logging.info("Sending AGC burst")
        self.wave_generator.one(self.leading_pulse_duration)
        self.wave_generator.zero(self.leading_gap_duration)

    # Trailing pulse is just a burst with the duration of standard pulse.
    def send_trailing_pulse(self):
        logging.info("Sending trailing pulse")
        self.wave_generator.one(self.one_pulse_duration)

    # This function is processing IR code. Leaves room for possible manipulation
    # of the code before processing it.
    def process_code(self, ircode):
        if (self.leading_pulse_duration > 0) or (self.leading_gap_duration > 0):
            self.send_agc()
        for i in ircode:
            if i == "0":
                self.zero()
            elif i == "1":
                self.one()
            else:
                logging.info("ERROR! Non-binary digit!")
                return 1
        if self.trailing_pulse == 1:
            self.send_trailing_pulse()
        return 0

    # Generate zero or one in NEC protocol
    # Zero is represented by a pulse and a gap of the same length
    def zero(self):
        self.wave_generator.one(self.zero_pulse_duration)
        self.wave_generator.zero(self.zero_gap_duration)

    # One is represented by a pulse and a gap three times longer than the pulse
    def one(self):
        self.wave_generator.one(self.one_pulse_duration)
        self.wave_generator.zero(self.one_gap_duration)

    def clear(self):
        self.wave_generator.clear()

class Pyslinger:
    def __init__(self,pi, gpio_pin):
        self.pigpio = pi
        logging.info("Starting IR")
        logging.info("Loading libpigpio.so")
        protocol = "NEC"
        protocol_config = dict() 
        #self.pigpio = ctypes.CDLL('libpigpio.so')
        logging.info("Initializing pigpio")
        #PI_OUTPUT = 1 # from pigpio.h
        #self.pigpio.initialise()
        self.gpio_pin = gpio_pin
        logging.info("Configuring pin %d as output" % self.gpio_pin)
        self.pigpio.set_mode(self.gpio_pin, pigpio.OUTPUT) # pin 17 is used in LIRC by default
        logging.info("Initializing protocol")
        if protocol == "NEC":
            self.protocol = NEC(self, **protocol_config)
        elif protocol == "RC-5":
            self.protocol = RC5(self, **protocol_config)
        elif protocol == "RAW":
            self.protocol = RAW(self, **protocol_config)
        else:
            logging.info("Protocol not specified! Exiting...")
            return 1
        logging.info("IR ready")

    # send_code takes care of sending the processed IR code to pigpio.
    # IR code itself is processed and converted to pigpio structs by protocol's classes.
    def send_code(self, ircode):
        logging.info("Processing IR code: %s" % ircode)
        code = self.protocol.process_code(ircode)
        if code != 0:
            logging.info("Error in processing IR code!")
            return 1
        clear = self.pigpio.wave_clear()
        if clear != 0:
            logging.info("Error in clearing wave!")
            return 1
        pulses = self.pigpio.wave_add_generic(self.protocol.wave_generator.pulses)
        if pulses < 0:
            logging.info("Error in adding wave!")
            return 1
        wave_id = self.pigpio.wave_create()
        # Unlike the C implementation, in Python the wave_id seems to always be 0.
        if wave_id >= 0:
            logging.info("Sending wave...")
            result = self.pigpio.wave_send_once(wave_id)
            if result >= 0:
                logging.info("Success! (result: %d)" % result)
            else:
                logging.info("Error! (result: %d)" % result)
                return 1
        else:
            logging.info("Error creating wave: %d" % wave_id)
            return 1
        while self.pigpio.wave_tx_busy():
            time.sleep(0.1)
        logging.info("Deleting wave")
        self.pigpio.wave_delete(wave_id)
        self.protocol.clear()

    def cleanup(self):
        logging.info("Terminating pigpio")
        self.pigpio.stop()

# Simply define the GPIO pin, protocol (NEC, RC-5 or RAW) and
# override the protocol defaults with the dictionary if required.
# Provide the IR code to the send_code() method.
# An example is given below.
if __name__ == "__main__":
    protocol = "NEC"
    gpio_pin = int(sys.argv[5])
    protocol_config = dict() #one_duration = 820,
                            #zero_duration = 820)
    pi = pigpio.pi()
    ir = Pyslinger(pi, gpio_pin)

    #print str(len(sys.argv))
    if len(sys.argv) > 2:
        code = (int(sys.argv[1]) << 24) | (int(sys.argv[2]) << 16) | (int(sys.argv[3]) << 8) | int(sys.argv[4])
    else:
        code = int(sys.argv[1],16)
    binc = format(code,'#034b')[2:] + "1"
    print binc
    ir.send_code(binc)
    logging.info("Exiting IR")
