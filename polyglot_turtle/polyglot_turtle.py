# SPDX-License-Identifier: MIT

import enum

from packaging.version import Version
from .hidcborrpc import HidCborRpcDevice

POLYGLOT_API_VERSION = "0.2.0"


class PinDirection(enum.IntEnum):
    INPUT = 0
    OUTPUT = 1
    OFF = 2


class PinPullMode(enum.IntEnum):
    NONE = 0
    PULL_UP = 1
    PULL_DOWN = 2


class I2cClockRate(enum.IntEnum):
    STANDARD = 100000
    FAST = 400000
    FAST_PLUS = 1000000


class PolyglotTurtle(HidCborRpcDevice):
    def __init__(self, serial_number: str = None, vendor_id: int = 0x0000, product_id: int = 0x0000, timeout: int = 1):
        if vendor_id == 0x0000:
            raise ValueError("Vendor ID must be specified")

        super().__init__(serial_number, vendor_id, product_id, timeout)

    def gpio_set_direction(self, pin_number: int, direction: PinDirection):
        """
        Sets the direction (input/output/HiZ) for a given GPIO.

        :param pin_number: GPIO number
        :param direction: IO direction
        :return:
        """
        if pin_number > 4:
            raise ValueError("Invalid pin number")
        self._execute_command("gpio_set_dir", [pin_number, int(direction)])

    def gpio_set_pull(self, pin_number: int, pull: PinPullMode):
        """
        Sets the direction (up/down/off) for a given GPIO.

        :param pin_number:
        :param pull:
        :return:
        """
        if pin_number > 4:
            raise ValueError("Invalid pin number")
        self._execute_command("gpio_set_pull", [pin_number, int(pull)])

    def gpio_set_level(self, pin_number: int, level: bool):
        if pin_number > 4:
            raise ValueError("Invalid pin number")
        self._execute_command("gpio_set_level", [pin_number, level])

    def gpio_get_level(self, pin_number: int):
        if pin_number > 4:
            raise ValueError("Invalid pin number")
        return self._execute_command("gpio_get_level", [pin_number])

    def i2c_exchange_by_index(self,
                     i2c_index: int,
                     address: int,
                     write_data: bytes,
                     read_size: int = 0,
                     clock_rate: I2cClockRate = I2cClockRate.STANDARD,
                     transaction_timeout_ms: int = 50):
        if address > 127:
            raise ValueError("Invalid address")
        return self._execute_command("i2c_exchange", [i2c_index, address, write_data, read_size, clock_rate,
                                                      transaction_timeout_ms])

    def spi_exchange_by_index(self,
                     spi_index: int,
                     write_data: bytes,
                     clock_rate: int,
                     mode: 0,
                     transaction_timeout_ms: int = 50,
                     cs_pin: int= 0xFF,
                     read_size=None):
        if read_size is None:
            actual_read_size = len(write_data)
        else:
            actual_read_size = read_size
        return self._execute_command("spi_exchange", [spi_index, write_data, actual_read_size, clock_rate, mode,
                                                      transaction_timeout_ms, cs_pin])

    def i2c_exchange(self,
                     address: int,
                     write_data: bytes = b"",
                     read_size: int = 0,
                     clock_rate: I2cClockRate = I2cClockRate.STANDARD,
                     transaction_timeout_ms: int = 50):
        return self.i2c_exchange_by_index(0, address, write_data, read_size, clock_rate, transaction_timeout_ms)

    def spi_exchange(self,
                     write_data: bytes,
                     clock_rate: int,
                     mode: int = 0,
                     transaction_timeout_ms: int = 50,
                     cs_pin: int = 0xFF,
                     read_size=None):
        return self.spi_exchange_by_index(0, write_data, clock_rate, mode, transaction_timeout_ms, cs_pin, read_size)

    def pwm_get_info(self):
        return self._execute_command("pwm_get_info")

    def pwm_set(self, pin_number: int, counter_period: int, duty_cycle: int, clock_rate_index=0):
        if pin_number > 4:
            raise ValueError("Invalid pin number")

        self._execute_command("pwm_set", [pin_number, clock_rate_index, int(counter_period), int(duty_cycle)])

    def dac_get_info(self):
        return self._execute_command("dac_get_info")

    def dac_set(self, pin_number: int, dac_level: int):
        if pin_number > 4:
            raise ValueError("Invalid pin number")

        self._execute_command("dac_set", [pin_number, dac_level])

    def adc_get(self, pin_number: int):
        if pin_number > 4:
            raise ValueError("Invalid pin number")

        return self._execute_command("adc_get", [pin_number])


class PolyglotTurtleXiao(PolyglotTurtle):
    def __init__(self, serial_number: str = None, vendor_id: int = 0x04d8, product_id: int = 0xeb74, timeout: int = 1):
        super().__init__(serial_number, vendor_id, product_id, timeout)

        if Version(self._execute_command("polyglot_version")) > Version(POLYGLOT_API_VERSION):
            raise ValueError("Firmware version is too new. You need to upgrade this python library.")

        hw = self._execute_command("polyglot_hw")
        if hw != "seeeduino-xiao":
            raise ValueError("Unexpected hardware encountered: '{}', expected 'seeeduino-xiao'".format(str(hw)))
