import time
from polyglot_turtle import PolyglotTurtleXiao, PinDirection, PinPullMode


if __name__ == "__main__":
    pt = PolyglotTurtleXiao()

    button_pin = 1
    red_led_pin = 2
    green_led_pin = 3

    pt.gpio_set_direction(button_pin, PinDirection.INPUT)
    pt.gpio_set_pull(button_pin, PinPullMode.NONE)

    pt.gpio_set_direction(red_led_pin, PinDirection.OUTPUT)
    pt.gpio_set_direction(green_led_pin, PinDirection.OUTPUT)

    while 1:
        pt.gpio_set_level(red_led_pin, True)
        pt.gpio_set_level(green_led_pin, False)
        time.sleep(0.5)

        pt.gpio_set_level(red_led_pin, False)
        pt.gpio_set_level(green_led_pin, True)
        time.sleep(0.5)

        while pt.gpio_get_level(button_pin):
            time.sleep(0.01)
