import time
import socket
import struct
import os
import shutil
import threading
import select

from enum import IntEnum, Enum
from typing import Optional

from polyglot_turtle import PolyglotTurtle, PolyglotTurtleXiao, PinDirection, PinPullMode


class STK500v2Markers(IntEnum):
    MESSAGE_START = 0x1B
    TOKEN = 0x0E


class STK500v2Commands(IntEnum):
    SIGN_ON = 0x01
    SET_PARAMETER = 0x02
    GET_PARAMETER = 0x03
    SET_DEVICE_PARAMETERS = 0x04
    OSCCAL = 0x05
    LOAD_ADDRESS = 0x06
    FIRMWARE_UPGRADE = 0x07

    ENTER_PROGMODE_ISP = 0x10
    LEAVE_PROGMODE_ISP = 0x11
    CHIP_ERASE_ISP = 0x12
    PROGRAM_FLASH_ISP = 0x13
    READ_FLASH_ISP = 0x14
    PROGRAM_EEPROM_ISP = 0x15
    READ_EEPROM_ISP = 0x16
    PROGRAM_FUSE_ISP = 0x17
    READ_FUSE_ISP = 0x18
    PROGRAM_LOCK_ISP = 0x19
    READ_LOCK_ISP = 0x1A
    READ_SIGNATURE_ISP = 0x1B
    READ_OSCCAL_ISP = 0x1C
    SPI_MULTI = 0x1D

    # this is not really a command, it is just used in the response if there is a checksum error
    ANSWER_CKSUM_ERROR = 0xB0


class STK500v2Parameters(IntEnum):
    BUILD_NUMBER_LOW = 0x80
    BUILD_NUMBER_HIGH = 0x81
    HW_VERSION = 0x90
    SW_MAJOR = 0x91
    SW_MINOR = 0x92
    VTARGET = 0x94
    VADJUST = 0x95
    OSC_PSCALE = 0x96
    OSC_CMATCH = 0x97
    SCK_DURATION = 0x98

    TOPCARD_DETECT = 0x9A

    DATA = 0x9D

    RESET_POLARITY = 0x9E
    CONTROLLER_INIT = 0x9F


class STK500v2StatusCodes(IntEnum):
    CMD_OK = 0x00

    CMD_TIMEOUT = 0x80
    CMD_READY_BUSY_TIMEOUT = 0x81

    CMD_FAILED = 0xC0
    CHECKSUM_ERROR = 0xC1
    CMD_UNKNOWN = 0xC9


class ParseState(Enum):
    IDLE = 0
    WAIT_SEQNUM = 1
    WAIT_SIZE1 = 2
    WAIT_SIZE2 = 3
    WAIT_TOKEN = 4
    WAIT_MSG = 5
    WAIT_CKSUM = 6


def build_stk500_response(sequence_number: int, command: int, payload):
    response_length = len(payload) + 1

    response = [
        STK500v2Markers.MESSAGE_START,
        sequence_number,
        (response_length >> 8) & 0xFF,
        response_length & 0xFF,
        STK500v2Markers.TOKEN,
        command
    ]
    response += payload

    checksum = 0
    for b in response:
        checksum ^= b

    return bytes(response) + bytes([checksum])


class ProgrammingServer(object):
    BUILD_NUMBER_LOW = 0
    BUILD_NUMBER_HIGH = 1
    HW_VERSION = 2  # needed for STK500v2
    SW_MAJOR = 2
    SW_MINOR = 4
    VTARGET = 33
    VADJUST = 0
    OSC_PSCALE = 2
    OSC_CMATCH = 1

    def __init__(self, pt: PolyglotTurtle, reset_pin=0, oe_pin: Optional[int] = None, host="localhost", port=5556):
        self._pt = pt
        self._reset_pin = reset_pin
        self._oe_pin = oe_pin

        self._host = host
        self._port = port

        self._parse_state = ParseState.IDLE
        self._checksum = 0
        self._sequence_number = 0
        self._expected_length = 0
        self._message_bytes_received = []

        self._sck_duration = 0
        self._reset_polarity = 0
        self._controller_init = 0

        self._address = 0
        self._larger_than_64k = False
        self._extended_address = None
        self._new_address = False

        self._spi_freq = int(1_500_000)

        self._terminate = threading.Event()
        self._run_thread = threading.Thread(target=self._run_thread_func, daemon=True)

        # set reset pin to HiZ
        self._pt.gpio_set_direction(self._reset_pin, PinDirection.INPUT)
        self._pt.gpio_set_pull(self._reset_pin, PinPullMode.NONE)

        # set oe pin to low
        if self._oe_pin is not None:
            self._pt.gpio_set_direction(self._oe_pin, PinDirection.OUTPUT)
            self._pt.gpio_set_level(self._oe_pin, False)

    def start_server(self):
        if self._terminate.is_set():
            raise RuntimeError("Server has already stopped")

        self._run_thread.start()

        return self

    def stop_server(self):
        self._terminate.set()
        self._run_thread.join()

    def __enter__(self):
        self.start_server()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_server()

    def _run_thread_func(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind((self._host, self._port))
            server_socket.listen()

            read_list = [server_socket]
            while True:
                readable, _, _ = select.select(read_list, [], [], 1.0)
                for sock in readable:
                    if sock is server_socket:
                        client_socket, address = server_socket.accept()
                        client_socket.setblocking(False)
                        read_list.append(client_socket)
                    else:
                        data = sock.recv(1024)

                        if data:
                            #print()
                            #print("Request:", ' '.join("{:02X}".format(x) for x in data))
                            response = self._process_data(data)

                            if response:
                                #print("\tResponse:", ' '.join("{:02X}".format(x) for x in response))
                                sock.send(response)
                        else:
                            sock.close()
                            read_list.remove(sock)
                            break

                if self._terminate.is_set():
                    for sock in read_list:
                        if sock == server_socket:
                            continue
                        sock.close()
                    # server_socket.close()
                    break

    def _process_data(self, data: bytes):
        response = b""
        for b in data:
            if self._parse_state == ParseState.IDLE:
                self._parse_state = ParseState.WAIT_SEQNUM
                self._checksum = b
                continue

            if self._parse_state == ParseState.WAIT_SEQNUM:
                self._sequence_number = b
                self._checksum ^= b
                self._parse_state = ParseState.WAIT_SIZE1
                continue

            if self._parse_state == ParseState.WAIT_SIZE1:
                self._expected_length = b << 8
                self._checksum ^= b
                self._parse_state = ParseState.WAIT_SIZE2
                continue

            if self._parse_state == ParseState.WAIT_SIZE2:
                self._expected_length |= b
                self._checksum ^= b
                self._parse_state = ParseState.WAIT_TOKEN
                continue

            if self._parse_state == ParseState.WAIT_TOKEN:
                if b == STK500v2Markers.TOKEN:
                    self._parse_state = ParseState.WAIT_MSG
                    self._message_bytes_received = []
                else:
                    self._parse_state = ParseState.IDLE

                self._checksum ^= b
                continue

            if self._parse_state == ParseState.WAIT_MSG:
                self._message_bytes_received.append(b)
                self._checksum ^= b
                if len(self._message_bytes_received) == self._expected_length:
                    self._parse_state = ParseState.WAIT_CKSUM
                continue

            if self._parse_state == ParseState.WAIT_CKSUM:
                if b == self._checksum and len(self._message_bytes_received) > 0:
                    response += self._execute_command(self._sequence_number, bytes(self._message_bytes_received))
                else:
                    response += build_stk500_response(self._sequence_number,
                                                      STK500v2Commands.ANSWER_CKSUM_ERROR,
                                                      bytes([STK500v2StatusCodes.CHECKSUM_ERROR]))

            self._parse_state = ParseState.IDLE
            self._expected_length = 0
            self._sequence_number = 0
            self._message_bytes_received = []

        return response

    def _execute_command(self, sequence_number: int, message_bytes: bytes):
        command = message_bytes[0]

        # try:
        #     print("Executing command {} (0x{:02X})".format(STK500v2Commands(command).name, command))
        # except ValueError:
        #     print("Executing unknown command 0x{:02X}".format(command))

        if command == STK500v2Commands.SIGN_ON:
            return build_stk500_response(sequence_number, command,
                                         bytes([STK500v2StatusCodes.CMD_OK, 8]) + b"AVRISP_2\0")

        elif command == STK500v2Commands.SET_PARAMETER:
            param_type = message_bytes[1]
            param_value = message_bytes[2]

            if param_type == STK500v2Parameters.SCK_DURATION:
                self._sck_duration = param_value
            elif param_type == STK500v2Parameters.RESET_POLARITY:
                self._reset_polarity = param_value
            elif param_type == STK500v2Parameters.CONTROLLER_INIT:
                self._controller_init = param_value

            return build_stk500_response(sequence_number, command, bytes([STK500v2StatusCodes.CMD_OK]))

        elif command == STK500v2Commands.GET_PARAMETER:
            param_type = message_bytes[1]
            param_value = 0xFF
            if param_type == STK500v2Parameters.BUILD_NUMBER_LOW:
                param_value = self.BUILD_NUMBER_LOW
            elif param_type == STK500v2Parameters.BUILD_NUMBER_HIGH:
                param_value = self.BUILD_NUMBER_HIGH
            elif param_type == STK500v2Parameters.HW_VERSION:
                param_value = self.HW_VERSION
            elif param_type == STK500v2Parameters.SW_MAJOR:
                param_value = self.SW_MAJOR
            elif param_type == STK500v2Parameters.SW_MINOR:
                param_value = self.SW_MINOR
            elif param_type == STK500v2Parameters.VTARGET:
                param_value = self.VTARGET
            elif param_type == STK500v2Parameters.VADJUST:
                param_value = self.VADJUST
            elif param_type == STK500v2Parameters.SCK_DURATION:
                param_value = self._sck_duration
            elif param_type == STK500v2Parameters.RESET_POLARITY:
                param_value = self._reset_polarity
            elif param_type == STK500v2Parameters.CONTROLLER_INIT:
                param_value = self._controller_init
            elif param_type == STK500v2Parameters.OSC_PSCALE:
                param_value = self.OSC_PSCALE
            elif param_type == STK500v2Parameters.OSC_CMATCH:
                param_value = self.OSC_CMATCH
            elif param_type == STK500v2Parameters.TOPCARD_DETECT:
                param_value = 0x8C  # always this value for STK500
            elif param_type == STK500v2Parameters.DATA:
                param_value = 0

            if param_value == 0xFF:
                return build_stk500_response(sequence_number, command, bytes([STK500v2StatusCodes.CMD_UNKNOWN]))
            else:
                return build_stk500_response(sequence_number, command, bytes([STK500v2StatusCodes.CMD_OK, param_value]))

        elif command == STK500v2Commands.LOAD_ADDRESS:
            self._address = struct.unpack(">I", message_bytes[1:])[0]

            if message_bytes[1] >= 0x80:
                self._larger_than_64k = True
            else:
                self._larger_than_64k = False

            self._extended_address = message_bytes[2]
            self._new_address = True

            return build_stk500_response(sequence_number, command, bytes([STK500v2StatusCodes.CMD_OK]))

        elif command == STK500v2Commands.FIRMWARE_UPGRADE:
            return build_stk500_response(sequence_number, command, bytes([STK500v2StatusCodes.CMD_FAILED]))

        elif command == STK500v2Commands.ENTER_PROGMODE_ISP:
            timeout_ms = message_bytes[1]
            stab_delay_ms = message_bytes[2]
            cmd_exe_delay_ms = message_bytes[3]
            sync_loops = message_bytes[4]
            byte_delay_ms = message_bytes[5]
            poll_value = message_bytes[6]
            poll_index = message_bytes[7]
            passthrough_command = message_bytes[8:]

            # turn on outputs
            if self._oe_pin is not None:
                self._pt.gpio_set_level(self._oe_pin, True)

            # drive reset pin high
            self._pt.gpio_set_direction(self._reset_pin, PinDirection.OUTPUT)
            self._pt.gpio_set_level(self._reset_pin, True)
            time.sleep(1e-3)

            # Drive SCK low by putting the device into mode 0
            self._pt.spi_exchange(b"\x00", self._spi_freq, mode=0)
            time.sleep(20e-3)

            # drive reset pin low
            self._pt.gpio_set_level(self._reset_pin, False)
            time.sleep(20e-3)

            # reset again to make sure the device is definitely in ISP mode
            self._pt.gpio_set_level(self._reset_pin, True)
            self._pt.gpio_set_level(self._reset_pin, False)
            time.sleep(20e-3)

            if sync_loops > 48:
                sync_loops = 48
            if byte_delay_ms < 1:
                byte_delay_ms = 1

            loop_count = 0
            while loop_count < sync_loops:
                time.sleep(1e-3 * cmd_exe_delay_ms)
                loop_count += 1

                self._pt.spi_exchange(bytes([passthrough_command[0]]), clock_rate=self._spi_freq)
                time.sleep(1e-3 * byte_delay_ms)

                self._pt.spi_exchange(bytes([passthrough_command[1]]), clock_rate=self._spi_freq)
                time.sleep(1e-3 * byte_delay_ms)

                resp1 = self._pt.spi_exchange(bytes([passthrough_command[2]]), clock_rate=self._spi_freq)
                time.sleep(1e-3 * byte_delay_ms)

                resp2 = self._pt.spi_exchange(bytes([passthrough_command[3]]), clock_rate=self._spi_freq)
                time.sleep(1e-3 * byte_delay_ms)

                if (poll_index == 3 and resp1[0] == poll_value) or \
                        (poll_index != 3 and resp2[0] == poll_value) or \
                        (poll_index == 0):
                    return build_stk500_response(sequence_number, command, bytes([STK500v2StatusCodes.CMD_OK]))
                else:
                    # TODO: maybe pulse SCK once
                    # self._pt.gpio_set_level(self._reset_pin, True)
                    # self._pt.gpio_set_level(self._reset_pin, False)
                    pass

            return build_stk500_response(sequence_number, command, bytes([STK500v2StatusCodes.CMD_FAILED]))

        elif command == STK500v2Commands.LEAVE_PROGMODE_ISP:
            # set SCK high by changing into mode 3
            self._pt.spi_exchange(b"\x00", clock_rate=self._spi_freq, mode=3)

            # set reset pin to HiZ
            self._pt.gpio_set_direction(self._reset_pin, PinDirection.INPUT)
            self._pt.gpio_set_pull(self._reset_pin, PinPullMode.NONE)

            # turn off outputs
            if self._oe_pin is not None:
                self._pt.gpio_set_level(self._oe_pin, False)

            time.sleep(20e-3)

            return build_stk500_response(sequence_number, command, bytes([STK500v2StatusCodes.CMD_OK]))

        elif command == STK500v2Commands.CHIP_ERASE_ISP:
            erase_delay_ms = message_bytes[1]
            poll_method = message_bytes[2]

            self._pt.spi_exchange(message_bytes[3:7], clock_rate=self._spi_freq)

            if poll_method == 2:
                time.sleep(1e-3 * erase_delay_ms)
            else:
                for i in range(150):
                    resp = self._pt.spi_exchange(bytes([0xF0, 0x00, 0x00, 0x00]), clock_rate=self._spi_freq)
                    if resp[0] & 1 == 0:
                        break

            return build_stk500_response(sequence_number, command, bytes([STK500v2StatusCodes.CMD_OK]))

        elif command == STK500v2Commands.PROGRAM_EEPROM_ISP or \
                command == STK500v2Commands.PROGRAM_FLASH_ISP:

            if command == STK500v2Commands.PROGRAM_EEPROM_ISP:
                use_word_addressing = False
            else:
                use_word_addressing = True

            byte_count = struct.unpack(">H", message_bytes[1:3])[0]
            mode = message_bytes[3]
            delay_ms = message_bytes[4]
            cmd1 = message_bytes[5]
            cmd2 = message_bytes[6]
            cmd3 = message_bytes[7]
            poll1 = message_bytes[8]
            poll2 = message_bytes[9]
            program_data = message_bytes[10:]

            poll_address = 0

            if delay_ms < 4:
                delay_ms = 4
            elif delay_ms > 32:
                delay_ms = 32

            start_address = self._address & 0xFFFF

            if byte_count > 280:
                return build_stk500_response(sequence_number, command, bytes([STK500v2StatusCodes.CMD_FAILED]))

            original_mode = mode
            if (mode & 1) == 0:
                # word write mode
                for i in range(byte_count):
                    chunk = [
                        cmd1,
                        (self._address >> 8) & 0xFF,
                        self._address & 0xFF,
                        message_bytes[i + 10]
                    ]
                    if use_word_addressing and i & 1:
                        chunk[0] |= (1 << 3)  # set low/high selection bit

                    self._pt.spi_exchange(bytes(chunk), clock_rate=self._spi_freq)

                    if poll1 != message_bytes[i + 10]:
                        poll_address = self._address & 0xFFFF
                        mode = original_mode
                    else:
                        mode = 0x02

                    if not use_word_addressing:
                        # sleep extra for eeprom write
                        time.sleep(2e-3)

                    if mode & 0x04:
                        for j in range(150):
                            if use_word_addressing and i & 1:
                                chunk = [
                                    cmd3,
                                    (poll_address >> 8) & 0xFF,
                                    poll_address & 0xFF,
                                    0x00
                                ]
                                if use_word_addressing and i & 1:
                                    chunk[0] |= (1 << 3)  # set low/high selection bit

                                resp = self._pt.spi_exchange(bytes(chunk), clock_rate=self._spi_freq)

                                if resp[-1] == poll1:
                                    break
                        else:
                            return build_stk500_response(sequence_number, command,
                                                         bytes([STK500v2StatusCodes.CMD_TIMEOUT]))
                    elif mode & 0x08:
                        for j in range(150):
                            resp = self._pt.spi_exchange(bytes([0xF0, 0x00, 0x00, 0x00]), clock_rate=self._spi_freq)
                            if resp[-1] & 1 == 0:
                                break
                        else:
                            return build_stk500_response(sequence_number, command,
                                                         bytes([STK500v2StatusCodes.CMD_READY_BUSY_TIMEOUT]))
                    else:
                        time.sleep(1e-3 * delay_ms)

                    if use_word_addressing:
                        if i & 1:
                            self._address += 1
                    else:
                        self._address += 1
            else:
                #print("page write mode")
                # page write mode

                spi_buf = []
                for i in range(byte_count):
                    chunk = []
                    if self._larger_than_64k and (self._address & 0xFFFF == 0 or self._new_address):
                        chunk += [
                            0x4D,  # load extended addr byte
                            0x00,
                            self._extended_address,
                            0x00
                        ]

                        self._new_address = False

                    chunk.append(cmd1)
                    if use_word_addressing and i & 1:
                        chunk[-1] |= (1 << 3)

                    chunk += [
                        (self._address >> 8) & 0xFF,
                        self._address & 0xFF,
                        program_data[i]
                    ]

                    spi_buf += chunk

                    if poll1 != program_data[i]:
                        poll_address = self._address & 0xFFFF
                    else:
                        mode = (mode & 0x80) | 0x10

                    if use_word_addressing:
                        if i & 1:
                            self._address += 1
                            if (self._address & 0xFFFF) == 0xFFFF:
                                self._extended_address += 1
                    else:
                        self._address += 1

                self._pt.spi_exchange(bytes(spi_buf), clock_rate=self._spi_freq)

                if mode & 0x80:
                    chunk = [
                        cmd2,
                        (start_address >> 8) & 0xFF,
                        start_address & 0xFF,
                        0x00
                    ]
                    self._pt.spi_exchange(bytes(chunk), clock_rate=self._spi_freq)

                    time.sleep(1e-6)

                    if mode & 0x20 and poll_address:
                        for j in range(150):
                            chunk = [
                                cmd3,
                                (poll_address >> 8) & 0xFF,
                                poll_address & 0xFF,
                                0x00
                            ]
                            if poll_address & 1:
                                chunk[0] |= (1 << 3)  # set low/high selection bit

                            resp = self._pt.spi_exchange(bytes(chunk), clock_rate=self._spi_freq)

                            if resp[-1] == poll1:
                                break
                        else:
                            return build_stk500_response(sequence_number, command,
                                                         bytes([STK500v2StatusCodes.CMD_TIMEOUT]))
                    elif mode & 0x40:
                        for j in range(150):
                            resp = self._pt.spi_exchange(bytes([0xF0, 0x00, 0x00, 0x00]), clock_rate=self._spi_freq)
                            if resp[-1] & 1 == 0:
                                break
                        else:
                            return build_stk500_response(sequence_number, command,
                                                         bytes([STK500v2StatusCodes.CMD_READY_BUSY_TIMEOUT]))
                    else:
                        time.sleep(1e-3 * delay_ms)

            return build_stk500_response(sequence_number, command, bytes([STK500v2StatusCodes.CMD_OK]))

        elif command == STK500v2Commands.READ_EEPROM_ISP or command == STK500v2Commands.READ_FLASH_ISP:
            if command == STK500v2Commands.READ_EEPROM_ISP:
                use_word_addressing = False
            else:
                use_word_addressing = True

            byte_count = struct.unpack(">H", message_bytes[1:3])[0]

            cmd = message_bytes[3]

            if byte_count > 280:
                byte_count = 280

            #print("reading {} bytes".format(byte_count))

            spi_buf = []
            read_index = []

            for i in range(byte_count):
                chunk = []
                if self._larger_than_64k and (self._address & 0xFFFF == 0 or self._new_address):
                    chunk += [
                        0x4D,  # load extended addr byte
                        0x00,
                        self._extended_address,
                        0x00
                    ]

                    self._new_address = False

                chunk.append(cmd)
                if use_word_addressing and i & 1:
                    chunk[-1] |= (1 << 3)

                chunk += [
                    (self._address >> 8) & 0xFF,
                    self._address & 0xFF,
                    0x00
                ]

                spi_buf += chunk
                read_index.append(len(spi_buf)-1)

                if use_word_addressing:
                    if i & 1:
                        self._address += 1
                        if (self._address & 0xFFFF) == 0xFFFF:
                            self._extended_address += 1
                else:
                    self._address += 1

            resp = self._pt.spi_exchange(bytes(spi_buf), clock_rate=self._spi_freq)
            read_data = [resp[x] for x in read_index]

            return build_stk500_response(sequence_number, command,
                                         bytes([STK500v2StatusCodes.CMD_OK] + read_data + [STK500v2StatusCodes.CMD_OK]))

        elif command == STK500v2Commands.PROGRAM_LOCK_ISP or command == STK500v2Commands.PROGRAM_FUSE_ISP:
            self._pt.spi_exchange(message_bytes[1:5], clock_rate=self._spi_freq)
            return build_stk500_response(sequence_number, command, bytes([STK500v2StatusCodes.CMD_OK,
                                                                          STK500v2StatusCodes.CMD_OK]))

        elif command == STK500v2Commands.READ_OSCCAL_ISP or \
                command == STK500v2Commands.READ_SIGNATURE_ISP or \
                command == STK500v2Commands.READ_LOCK_ISP or \
                command == STK500v2Commands.READ_FUSE_ISP:

            result_byte = 0x00
            for i in range(4):
                resp = self._pt.spi_exchange(bytes([message_bytes[i + 2]]), clock_rate=self._spi_freq)
                if message_bytes[1] == i + 1:
                    result_byte = resp[0]
                time.sleep(5e-3)

            return build_stk500_response(sequence_number, command, bytes([
                STK500v2StatusCodes.CMD_OK,
                result_byte,
                STK500v2StatusCodes.CMD_OK
            ]))

        elif command == STK500v2Commands.SPI_MULTI:
            return build_stk500_response(sequence_number, command, bytes([STK500v2StatusCodes.CMD_UNKNOWN]))

        else:
            return build_stk500_response(sequence_number, command, bytes([STK500v2StatusCodes.CMD_UNKNOWN]))


def _find_avrdude():
    avrdude_path = None
    try:
        from avrdude_windows import get_avrdude_path
        avrdude_path = get_avrdude_path()
    except ImportError:
        pass

    if avrdude_path is None:
        avrdude_path = shutil.which("avrdude")
        if avrdude_path is None:
            raise FileNotFoundError("avrdude is not installed - please see the python-polyglot-turtle documentation "
                                    "for more info.")

    return avrdude_path


def avrdude_exec(pt: PolyglotTurtle, avrdude_arguments: str, reset_gpio: int, oe_gpio: Optional[int], host: str, port: int):
    avrdude_path = _find_avrdude()

    with ProgrammingServer(pt, reset_gpio, oe_gpio, host, port) as ps:
        os.system(avrdude_path + " -c stk500v2 -P net:{}:{} {}".format(host, port, avrdude_arguments))


def program_avr(pt: PolyglotTurtle, hex_path: str, part_name: str, reset_gpio: int, oe_gpio: Optional[int], host, port: int):
    if not os.path.exists(hex_path):
        raise FileNotFoundError()

    if not hex_path.endswith(".hex"):
        raise ValueError("Hex file must end with '.hex' extension")

    avrdude_exec(pt,
                 " -p {} -e -U flash:w:{}".format(host, port, part_name, hex_path),
                 reset_gpio,
                 oe_gpio,
                 host,
                 port)
