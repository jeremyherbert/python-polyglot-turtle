import telnetlib

def print_label_for_device(serial, copies=1):
    template = f"""SIZE 17.5 mm, 16 mm
    GAP 3 mm, 0 mm
    DIRECTION 0,0
    REFERENCE 0,0
    OFFSET 0 mm
    SET PEEL OFF
    SET CUTTER OFF
    SET PARTIAL_CUTTER OFF
    SET TEAR ON
    CLS
    QRCODE 310,300,L,8,M,180,M2,S7,"A{serial}"
    CODEPAGE 1252
    PRINT 1,{copies}
    """

    with telnetlib.Telnet("192.168.3.212", 9100) as t:
        t.write(template.encode())


if __name__ == "__main__":
    print_label_for_device("FB8BEA2550573651302E3120FF130421")