# SPDX-License-Identifier: MIT

from polyglot_turtle import PolyglotTurtleXiao, CommandExecutionFailedException, I2cClockRate

# This code allows one to detect if there are any I2C devices on the bus. It achieves this by performing a 1 byte
# read to all possible addresses and checks if there is any response. Note that this is not perfect, as a device can
# NACK an arbitrary read and this scan functionality is not guaranteed by the I2C standard. It seems to work fine with
# most devices though.

if __name__ == "__main__":
    pt = PolyglotTurtleXiao()  # you may need to provide a serial number here to select the correct device

    # as the address is always right aligned, we are only checking up to 127 or 0x7F inclusive
    for i in range(128):
        try:
            pt.i2c_exchange(i, b'', read_size=1, clock_rate=I2cClockRate.FAST)
            print("Found device at: 0x{:02X}".format(i))
        except CommandExecutionFailedException:
            pass
