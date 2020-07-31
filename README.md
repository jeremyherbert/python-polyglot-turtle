# python-polyglot-turtle

This repository contains a python library for communicating with the polyglot-turtle firmware. It has been tested to work on Windows, Mac and Linux.

To install, run

```
pip install polyglot-turtle
```

Only python 3.6+ is supported. This driver does not expose any USB-to-serial functionality, for that you should use something like [pyserial](https://pypi.org/project/pyserial/).

## Extra install instructions for Linux users

This library depends on [cython-hidapi](https://github.com/trezor/cython-hidapi) which requires you to install some extra binary dependencies. On Ubuntu (tested on 18.04), you can install these dependencies using the following command:

```
sudo apt-get install python3-dev libusb-1.0-0-dev libudev-dev
```

By default, Linux does not allow access to USB or HID devices for a non-root user. To give access to your own user is simple. First, in `/etc/udev/rules.d`, create a new file called `00-polyglot-turtle.rules` and paste the following two lines in:

```
ATTR{idVendor}=="04d8", ATTR{idProduct}=="eb74", ENV{ID_MM_DEVICE_IGNORE}="1"
KERNEL=="hidraw*", ATTRS{idVendor}=="04d8", ATTRS{idProduct}=="eb74", MODE="0660", GROUP="plugdev", TAG+="uaccess"
```

This will give access to any user in the `plugdev` group. Now, just add yourself to the group:

```
sudo usermod -a -G plugdev <your username>
```

(you need to replace `<your username>` with your actual username on your computer).

Once this is done, reboot and everything should work.

## Usage

Almost all code using this library will need two lines:

```python
from polyglot_turtle import PolyglotTurtleXiao

pt = PolyglotTurtleXiao()
```

The first line imports the main class from the library, and the second line connects to the device. After that, you simply use the `pt` object to interact with your device.

You can connect to a specific device using its serial number if more than one is present:

```python
from polyglot_turtle import PolyglotTurtleXiao

pt = PolyglotTurtleXiao(serial_number="9B1EC96D5053574C342E3120FF02110D")
```

All devices have a unique serial number that is associated with the USB device. You can find this number in Windows using Device Manager, in Mac OS using System Report, and in Linux using `lsusb`.

### GPIO

There are 4 GPIO pins on the polyglot-turtle-xiao numbered 0-3. All four of these pins can be used as a digital input or output by setting the pin direction:

```python
from polyglot_turtle import PolyglotTurtleXiao, PinDirection

pt = PolyglotTurtleXiao()

pt.gpio_set_direction(0, PinDirection.OUTPUT)  # set GPIO 0 to output
pt.gpio_set_direction(1, PinDirection.INPUT)  # set GPIO 1 to input
```

To read from an input or write to an output, use the `gpio_set_level` and `gpio_get_level` functions respectively:

```python
from polyglot_turtle import PolyglotTurtleXiao, PinDirection

pt = PolyglotTurtleXiao()

pt.gpio_set_direction(0, PinDirection.OUTPUT)  # set GPIO0 to output
pt.gpio_set_level(0, True)  # set GPIO 0 to high
pt.gpio_set_level(0, False)  # set GPIO 0 to low

pt.gpio_set_direction(1, PinDirection.INPUT)  # set GPIO1 to input
print(pt.gpio_get_level(1))  # prints "True" or "False" depending on the state of GPIO1
```

When using a pin as an input, you can additionally enable a weak internal pullup or pulldown resistor:

```python
from polyglot_turtle import PolyglotTurtleXiao, PinDirection, PinPullMode

pt = PolyglotTurtleXiao()
pt.gpio_set_direction(1, PinDirection.INPUT)  # set GPIO1 to input

pt.gpio_set_pull(1, PinPullMode.PULL_UP)  # enable the pullup
pt.gpio_set_pull(1, PinPullMode.PULL_DOWN)  # enable the pulldown
pt.gpio_set_pull(1, PinPullMode.NONE)  # leave the input floating

```

### SPI

To use the SPI interface, connect one of the GPIO pins to the CS pin of your target device, and otherwise connect MISO, MOSI and SCK as usual.

The polyglot-turtle firmware supports a single SPI operation, called 'exchange'. This can be used to interact with any SPI device, and even some non-SPI devices too! In an exchange operation, the polyglot-turtle firmware will write all of the bytes provided to the target device, and return all of the bytes read back from the device. As SPI requires the device to shift out one byte for every byte shifted in, you will receive the same number of bytes that was written.

An SPI exchange requires you to send the following parameters to the device:

- The data to send
- The SPI clock rate (100kHz to 10MHz)
- The [SPI mode](https://en.wikipedia.org/wiki/Serial_Peripheral_Interface#Mode_numbers) (default 0 if not specified)
- The transaction timeout in milliseconds, after which it will be assumed that the command execution failed (default 50ms if not specified)
- the CS pin to set low and then high automatically (default is to not change any GPIO pins unless one is specified)

```python
from polyglot_turtle import PolyglotTurtleXiao, PinDirection

pt = PolyglotTurtleXiao()
pt.gpio_set_direction(0, PinDirection.OUTPUT)  # GPIO0 will be used as the CS pin
pt.gpio_set_level(0, True)  # set the CS pin to high by default

# perform a transaction with manual CS control
pt.gpio_set_level(0, False)  # set CS low
print(pt.spi_exchange(b"\x01\x02\x03", clock_rate=100000, mode=0))
pt.gpio_set_level(0, True)  # set CS high

# perform the same transaction but with automatic CS control
print(pt.spi_exchange(b"\x01\x02\x03", clock_rate=100000, mode=0, cs_pin=0))

# perform the same automatic CS transaction but with a 1 second timeout
print(pt.spi_exchange(b"\x01\x02\x03", clock_rate=100000, mode=0, cs_pin=0, transaction_timeout_ms=1000))
```

### I2C

Almost all I2C transactions can be broken down into combinations of three operations:

1. (Write operation) START, Address + Write, write N bytes, STOP
2. (Read operation) START, Address + Read, read N bytes, STOP
2. (Write-then-read operation) START, Address + Write, write N bytes, REPEATED START, Address + Read, read N bytes, STOP

The polyglot-turtle firmware supports all three of these operations using a single function, `i2c_exchange`. This function takes the following arguments:

- The target device address (right aligned, between 0 and 127 inclusive)
- The data to write (default is empty)
- The number of bytes to read (default is 0)
- The I2C bus clock rate (one of three specific values)
- The transaction timeout in milliseconds, after which it will be assumed that the command execution failed (default 50ms if not specified)

The type of operation is selected simply by the number of bytes provided to write, and the number of bytes requested to read. 

1. (Write operation) If there are bytes to write and the number of bytes to read is 0
2. (Read operation) If there are no bytes to write and the number of bytes to read is > 0
3. (Write-then-read operation) If there are both bytes to write and the number of bytes to read is > 0

See below for some examples:

```python
from polyglot_turtle import PolyglotTurtleXiao, I2cClockRate

pt = PolyglotTurtleXiao()
address = 0x32  # device we are talking to is at address 0x32

# perform a write transction with the bytes 0x12 0x34
pt.i2c_exchange(address, write_data=b"\x12\x34", clock_rate=I2cClockRate.STANDARD)  

# perform a read operation and read 4 bytes
pt.i2c_exchange(address, read_size=4, clock_rate=I2cClockRate.STANDARD)  

# perform a write-then-read operation where 0x12 0x34 is written and then 4 bytes are read back
pt.i2c_exchange(address, write_data=b"\x12\x34", read_size=4, clock_rate=I2cClockRate.STANDARD)  
```

Since the I2C standard only allows three specific clock rates, the polyglot-turtle firmware also only supports these three speeds:

- `STANDARD`: 100kHz
- `FAST`: 400kHz
- `FAST_PLUS`: 1MHz

## Further examples

There are some simple examples in the git repository you can look at for more information.
