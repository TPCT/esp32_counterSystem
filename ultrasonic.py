from machine import Pin, time_pulse_us
from utime import sleep_us


class ultraSonic:
    def __init__(self, trig: int, echo: int):
        self.trig = Pin(trig, Pin.OUT, value=0)
        self.echo = Pin(echo, Pin.IN, value=0)

    def readDistance(self):
        """
        =--------------------------------------------------------------------------------------------------------------=
                                            *specifications and requirements*
        this function reads the distance between the sensor and the object by using PWM reader (time_pulse_us)
        sending high pulse with width of 10 US to the trigger pin then setting it to low
        reading the duration of high pulse from echo (which equal to the time take by the sound to move the whole distance)
        to get the distance between object and sensor:
            1- divide the duration by 2 (as the duration is total time take back and forth)
            2- distance = time * velocity => (340 cm * 100 / 10 ^ (6)) * duration / 2
        time_pulse_us (measure the time taken by a pulse to change from state to another)
        =--------------------------------------------------------------------------------------------------------------=
        :return: None
        """
        self.trig.value(0x01)
        sleep_us(10)
        self.trig.value(0x00)
        duration = time_pulse_us(self.echo, 0x01)
        distance = duration * (340 * 100 / 10 ** 6) / 2
        return distance
