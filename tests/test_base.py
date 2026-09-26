import pytest

from checkin.base import SerialBase, VirtualBase, open_base


class FakePort:
    def __init__(self):
        self.written = b""
        self.incoming = b""
        self.broken = False

    def write(self, data):
        if self.broken:
            raise OSError("device unplugged")
        self.written += data

    @property
    def in_waiting(self):
        if self.broken:
            raise OSError("device unplugged")
        return len(self.incoming)

    def read(self, n):
        data, self.incoming = self.incoming[:n], self.incoming[n:]
        return data

    def close(self):
        pass


def test_serial_base_speaks_the_protocol():
    port = FakePort()
    base = SerialBase(port)
    assert port.written == b"PING\n" and not base.connected
    base.cue("start")
    base.led("amber")
    assert port.written.endswith(b"CUE start\nLED amber\n")
    port.incoming = b"READY\nBT"
    assert base.pressed() is False and base.connected
    port.incoming = b"N\r\n"  # a line split across reads, with a Windows line ending
    assert base.pressed() is True
    assert base.pressed() is False


def test_serial_base_survives_being_unplugged():
    port = FakePort()
    base = SerialBase(port)
    port.incoming = b"PONG\n"
    base.pressed()
    port.broken = True
    base.cue("stop")
    assert base.pressed() is False and not base.connected


def test_open_base():
    assert isinstance(open_base("virtual"), VirtualBase)
    with pytest.raises(ValueError, match="--serial-port"):
        open_base("serial")
    with pytest.raises(ValueError):
        open_base("bluetooth")
