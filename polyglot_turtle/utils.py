import hid


def _list_devices(vendor_id: int, product_id: int):
    found_devices = []
    for device in hid.enumerate():
        if device['vendor_id'] == vendor_id and product_id == product_id:
            found_devices.append(device["serial_number"])

    return found_devices


def list_polyglot_turtle_xiao_devices():
    return _list_devices(vendor_id=0x04d8, product_id=0xeb74)


if __name__ == "__main__":
    print(list_polyglot_turtle_xiao_devices())
