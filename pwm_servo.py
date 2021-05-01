from polyglot_turtle import PolyglotTurtleXiao, PinDirection

import time

if __name__ == "__main__":
    pt = PolyglotTurtleXiao()

    # We are asssuming the servo needs a period of 20ms, with a duty cycle of between 1ms to 2ms (5% to 10%).
    # The duty cycle controls the position of the servo. All servos are different, so you would have to adjust this
    #  depending on the servo you use.

    max_counter_val, max_duty_cycle_val, clock_rates = pt.pwm_get_info()

    print("maximum counter value:", max_counter_val)
    print("possible counter clock rates:", clock_rates)

    gpio_pin = 3
    clock_rate_index = 1  # note that the fastest clock rate will always be index 0
    clock_rate = clock_rates[clock_rate_index]

    print("using clock rate", clock_rate, "at index", clock_rate_index)

    # first calculate the longest period that can be used, and check that it works for us
    if (max_counter_val+1) * (1/clock_rate) < 20e-3:
        raise ValueError("Cannot generate a 20ms period PWM signal with the current timing parameters")

    # calculate the counter value for a 20ms period
    counter_period = int(20e-3/(1/clock_rate))

    # calculate the number of ticks in 1ms
    duty_cycle_range = int(1e-3/(1/clock_rate))

    print("Counter period:", counter_period)
    print("Servo duty cycle min:", duty_cycle_range)  # ticks for 1ms
    print("Servo duty cycle max:", duty_cycle_range*2)  # ticks for 2ms

    for i in range(10):
        angle = i*180/10
        duty_cycle = int((angle * duty_cycle_range/180) + duty_cycle_range)
        print("Changing duty cycle to {} (angle is {} degrees)".format(duty_cycle, angle))
        pt.pwm_set(gpio_pin, counter_period=counter_period, duty_cycle=duty_cycle, clock_rate_index=clock_rate_index)
        time.sleep(1)

    # PWM will continue to be output forever, we need to set the pin direction to turn it back into a GPIO if we wish
    #  to turn it off
    pt.gpio_set_direction(gpio_pin, PinDirection.OUTPUT)
    pt.gpio_set_level(gpio_pin, False)
