from machine import Pin, time_pulse_us
from utime import sleep_us


class ultraSonic:
    def __init__(self, trig: int, echo: int):
        self.trig = Pin(trig, Pin.OUT, value=0)
        self.echo = Pin(echo, Pin.IN, value=0)

    def readDistance(self):
        self.trig.value(0x01)
        sleep_us(10)
        self.trig.value(0x00)
        duration = time_pulse_us(self.echo, 0x01)
        distance = duration / (2 * 29)
        return distance
