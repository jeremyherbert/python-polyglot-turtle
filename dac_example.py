import time

from polyglot_turtle import PolyglotTurtleXiao, PinDirection

if __name__ == "__main__":
    pt = PolyglotTurtleXiao()

    maximum_dac_value, maximum_dac_voltage = pt.dac_get_info()
    print("DAC will output", maximum_dac_voltage, "volts at the maximum level of", maximum_dac_value)

    dac_gpio = 0

    # the following code will output a ramp from 0 to the maximum value from the DAC on GPIO 0
    for i in range(5):
        pt.dac_set(dac_gpio, i*10)
        time.sleep(1)

    # the DAC will hold the last value sent to it, if we wish to turn it back into a GPIO we can set the pin direction
    pt.gpio_set_direction(dac_gpio, PinDirection.OUTPUT)
    pt.gpio_set_level(dac_gpio, False)