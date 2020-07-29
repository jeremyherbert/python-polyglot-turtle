# SPDX-License-Identifier: MIT

import time
from polyglot_turtle import PolyglotTurtleXiao, PinDirection

# the following code blinks LEDs on GPIO 2 and 3

if __name__ == "__main__":
    pt = PolyglotTurtleXiao()  # you may need to provide a serial number here to select the correct device

    pt.gpio_set_direction(2, PinDirection.OUTPUT)
    pt.gpio_set_direction(3, PinDirection.OUTPUT)

    while True:
        pt.gpio_set_level(2, True)
        pt.gpio_set_level(3, True)
        time.sleep(0.1)

        pt.gpio_set_level(2, False)
        pt.gpio_set_level(3, False)
        time.sleep(0.1)
