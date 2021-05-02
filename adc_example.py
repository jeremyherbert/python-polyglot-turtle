import time

from polyglot_turtle import PolyglotTurtleXiao

# to use this example, connect the DAC pin (GPIO 0) to an ADC pin (in this case, GPIO 3)

if __name__ == "__main__":
    pt = PolyglotTurtleXiao()

    maximum_dac_value, maximum_dac_voltage = pt.dac_get_info()

    adc_gpio_pin = 3

    for i in range(1, 11):
        pt.dac_set(0, i*100)
        set_value = i*100 * maximum_dac_voltage/(maximum_dac_value+1)

        reading, max_reading, max_voltage = pt.adc_get(adc_gpio_pin)
        voltage_reading = reading * max_voltage / (max_reading+1)

        print("reading was {}/{}".format(reading, max_reading))
        print("set: {}, got: {}".format(set_value, voltage_reading))
        print("error:", 100 * (voltage_reading - set_value) / set_value, "%")

        print()

        time.sleep(0.1)


