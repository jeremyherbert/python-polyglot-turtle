import struct
from polyglot_turtle import PolyglotTurtleXiao, PinDirection

# This code reads the JEDEC ID information from a SPI flash device. This is a unique code that allows the device to
# be identified as coming from a particular manufacturer and having a particular model number. This process is performed
# twice, once with software controlled CS activation and once with firmware controlled CS activation.

# The part used in this example is a Winbond W25Q128JVSIQ SPI flash. GPIO2 is connected to the flash CS pin.

if __name__ == "__main__":
    pt = PolyglotTurtleXiao()  # you may need to provide a serial number here to select the correct device

    FLASH_CS_PIN = 2
    pt.gpio_set_direction(FLASH_CS_PIN, PinDirection.OUTPUT)
    pt.gpio_set_level(FLASH_CS_PIN, True)  # set to idle

    print("First read:")

    # Command 0x9F is "Read JEDEC ID". After transmitting the command code, the device returns 3 bytes which are the
    # Manufacturer code and JEDEC ID. To read the three bytes, we need to send 3 padding bytes (0x00) as SPI always
    # requires an exchange of data. The exact value of the padding bytes is not necessary
    pt.gpio_set_level(FLASH_CS_PIN, False)
    jedec_id_data = pt.spi_exchange(b"\x9F\x00\x00\x00", clock_rate=1000000)
    pt.gpio_set_level(FLASH_CS_PIN, True)

    # note that jedec_id_data[0] is the data that the device exchanged for the command byte, so it is not useful to us.
    manufacturer_id = jedec_id_data[1]
    jedec_id_msb = jedec_id_data[2]
    jedec_id_lsb = jedec_id_data[3]

    # combine the Most Significant Bit (MSB) and Least Significant Bit (LSB) to make the ID
    jedec_id = (jedec_id_msb << 8) | jedec_id_lsb

    print("Manufacturer ID: 0x{:02X}".format(manufacturer_id))
    print("JEDEC device ID: 0x{:04X}".format(jedec_id))

    # for the W25Q128JVSIQ, the datasheet says the manufacturer code should be 0xEF and JEDEC ID should be 0x4018
    if manufacturer_id != 0xEF:
        raise ValueError("Invalid manufacturer ID")

    if jedec_id != 0x4018:
        raise ValueError("Invalid JEDEC ID")

    # now we will read the same data again and process it using a slightly different method
    print("\nSecond read:")

    # we don't have to manually toggle the CS pin when using the polyglot-turtle firmware, the device can take care
    # of this automatically for us using the 'cs_pin' argument
    jedec_id_data_again = pt.spi_exchange(b"\x9F\x00\x00\x00", clock_rate=1000000, cs_pin=FLASH_CS_PIN)

    if jedec_id_data_again != jedec_id_data:
        raise ValueError("The data did not match from the second read")

    # the polyglot-turtle firmware can also add the padding bytes for us (always 0x00), you just need to tell it the
    # total number of bytes to exchange using the 'read_size' argument (in this case, 1 padding byte + 3 data bytes = 4
    # bytes)
    jedec_id_data_again_again = pt.spi_exchange(b"\x9F", clock_rate=1000000, cs_pin=FLASH_CS_PIN, read_size=4)

    if jedec_id_data_again_again != jedec_id_data:
        raise ValueError("The data did not match from the third read")

    # unpacking byte strings is a fairly common thing when working with hardware, so python provides a library to
    # help with this called 'struct'. You just need to tell your library what format the data is in (this is known as
    # a 'format string') and then it will handle the rest. You can look up the format string details in the python
    # documentation: https://docs.python.org/library/struct.html
    #
    # In this case, we have:
    #   - 1 byte of unused data that we don't care about
    #   - 8 bit/1 byte manufacturer ID
    #   - 16 bit or 2 byte JEDEC ID
    # also note that the data is sent MSB first, meaning that it is encoded in big-endian format. The format string
    # is therefore:
    #
    # >xBH
    #    ^--- 'H' means unsigned integer, 2 byte
    #   ^---- 'B' means unsigned char, 1 byte
    #  ^----- 'x' is a padding or unused byte
    # ^------ '>' means big-endian; this has to be the first character in the format string

    manufacturer_id_again, jedec_id_again = struct.unpack(">xBH", jedec_id_data_again)

    print("Manufacturer ID: 0x{:02X}".format(manufacturer_id_again))
    print("JEDEC device ID: 0x{:04X}".format(jedec_id_again))

    # check the IDs again for completeness sake
    if manufacturer_id_again != 0xEF:
        raise ValueError("Invalid manufacturer ID")

    if jedec_id_again != 0x4018:
        raise ValueError("Invalid JEDEC ID")



