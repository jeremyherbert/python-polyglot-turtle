import queue
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


class JtagServer(object):
    def __init__(self, pt: PolyglotTurtle, tdi_pin: int, tdo_pin: int, tms_pin: int, tck_pin: int, host="localhost", port=33334):
        self._pt = pt

        if not 0 <= tdi_pin <= 3:
            raise ValueError("TDI pin out of range")
        if not 0 <= tdo_pin <= 3:
            raise ValueError("TDO pin out of range")
        if not 0 <= tms_pin <= 3:
            raise ValueError("TMS pin out of range")
        if not 0 <= tck_pin <= 3:
            raise ValueError("TCK pin out of range")

        self._tdi_pin = tdi_pin
        self._tdo_pin = tdo_pin
        self._tms_pin = tms_pin
        self._tck_pin = tck_pin

        self._pt.gpio_set_direction(self._tdi_pin, PinDirection.OUTPUT)
        self._pt.gpio_set_direction(self._tms_pin, PinDirection.OUTPUT)
        self._pt.gpio_set_direction(self._tck_pin, PinDirection.OUTPUT)

        self._pt.gpio_set_direction(self._tdo_pin, PinDirection.INPUT)
        self._pt.gpio_set_pull(self._tdo_pin, PinPullMode.NONE)

        self._host = host
        self._port = port

        self._terminate = threading.Event()
        self._run_thread = threading.Thread(target=self._run_thread_func, daemon=True)
        self._process_data_thread = threading.Thread(target=self._process_data_func, daemon=True)

        self._input_queue = queue.Queue()

        self._sock = None

    def start_server(self):
        if self._terminate.is_set():
            raise RuntimeError("Server has already stopped")

        self._run_thread.start()
        self._process_data_thread.start()

        return self

    def stop_server(self):
        self._terminate.set()
        self._run_thread.join()
        self._process_data_thread.join()

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
                        self._sock = client_socket
                        read_list.append(client_socket)
                    else:
                        data = sock.recv(1500)

                        if data:
                            self._input_queue.put(data)
                        else:
                            sock.close()
                            read_list.remove(sock)
                            break

                if self._terminate.is_set():
                    for sock in read_list:
                        if sock == server_socket:
                            continue
                        sock.close()
                    break

    def _process_data_func(self):
        count = 0
        while not self._terminate.is_set():
            try:
                data = self._input_queue.get(block=True, timeout=0.5)
            except queue.Empty:
                continue

            response = self._pt.openocd_jtag(self._tdi_pin,
                                             self._tdo_pin,
                                             self._tms_pin,
                                             self._tck_pin,
                                             data)

            if response and self._sock is not None:
                self._sock.send(response)


if __name__ == "__main__":
    pt = PolyglotTurtleXiao()
    with JtagServer(pt=pt, tdi_pin=2, tdo_pin=1, tms_pin=3, tck_pin=0):
        print("jtag server started")
        while True:
            time.sleep(10)
