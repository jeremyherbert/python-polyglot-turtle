from polyglot_turtle import PolyglotTurtleXiao

# Connect GPIO 0 to the RESET pin on the AVR, and also connect MOSI, MISO and SCK between the two devices


def program():
    pt = PolyglotTurtleXiao()

    # flash the file
    pt.avrdude_exec("-p atmega328p -U flash:w:firmware.hex", reset_gpio=0)


if __name__ == "__main__":
    program()
