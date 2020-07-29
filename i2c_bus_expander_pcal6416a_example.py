# SPDX-License-Identifier: MIT

import time
from polyglot_turtle import PolyglotTurtleXiao

# the following code displays a "bouncing" LED pattern across the 8 pins on Port 0 of an I2C connected
# PCAL6416A. The address pin is connected to VCC via a 10k resistor. Ensure that you have pull up resistors on the
# SDA and SCL pins (4.7k ohms is a typical value)

if __name__ == "__main__":
    pt = PolyglotTurtleXiao()  # you may need to provide a serial number here to select the correct device

    # right aligned i2c address (no R/W bit)
    device_address = 0x21

    # configure port 0 as output
    pt.i2c_exchange(device_address, bytes([0x06, 0x00]))

    ticker = 0
    direction = 1
    while 1:
        if ticker == 7:
            direction = -1
        elif ticker == 0:
            direction = 1

        ticker += direction

        pt.i2c_exchange(device_address, bytes([0x02, 0xFF ^ (1 << ticker)]))
        time.sleep(0.1)
