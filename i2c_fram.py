from polyglot_turtle import PolyglotTurtleXiao

# FRAM part number is: MB85RC16PN-G-AMERE1

# The base I2C address of the device from the datasheet
FRAM_I2C_BASE_ADDRESS = 0x50


def split_fram_memory_address(memory_address):
    upper_address_bits = (0x700 & memory_address) >> 8
    lower_address_bits = memory_address & 0xFF

    return upper_address_bits, lower_address_bits


def fram_read(pt, memory_address, size):
    upper_address_bits, lower_address_bits = split_fram_memory_address(memory_address)

    i2c_address = FRAM_I2C_BASE_ADDRESS | upper_address_bits
    return pt.i2c_exchange(i2c_address, bytes([lower_address_bits]), read_size=size)


def fram_write(pt, memory_address, data):
    upper_address_bits, lower_address_bits = split_fram_memory_address(memory_address)

    i2c_address = FRAM_I2C_BASE_ADDRESS | upper_address_bits
    pt.i2c_exchange(i2c_address, bytes([lower_address_bits]) + data)


if __name__ == "__main__":
    pt = PolyglotTurtleXiao()

    fram_write(pt, 0, bytes([0x12, 0x13, 0x14]))
    print(fram_read(pt, 0, 3))