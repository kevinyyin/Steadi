"""Base stations. Each one has:

    cue(name)   start | stop | done | error | rep   (buzzer)
    led(color)  off | blue | green | amber | red
    pressed() -> bool   the physical button was pressed since the last call
    close()
    kind: str, connected: bool

The dashboard always shows the LED and the on-screen button; with the virtual base it also plays the tones.
"""

import logging

log = logging.getLogger(__name__)
CUES = ("start", "stop", "done", "error", "rep")
COLORS = ("off", "blue", "green", "amber", "red")


class VirtualBase:
    kind = "virtual"
    connected = True

    def cue(self, name):
        pass

    def led(self, color):
        pass

    def pressed(self):
        return False

    def close(self):
        pass


class SerialBase:
    """Arduino base station over USB serial, line protocol in firmware/PROTOCOL.md."""

    kind = "serial"

    def __init__(self, port):
        self.port = port  # pyserial-like: write(bytes), read(n), in_waiting
        self.connected = False
        self._buf = b""
        self._send("PING")

    @classmethod
    def open(cls, path, baud=115200):
        import serial  # only needed with real hardware

        return cls(serial.Serial(path, baud, timeout=0, write_timeout=0.5))

    def _send(self, line):
        try:
            self.port.write((line + "\n").encode())
        except Exception as e:  # unplugged mid-session: keep the session running
            if self.connected:
                log.warning("base station write failed: %s", e)
            self.connected = False

    def cue(self, name):
        self._send(f"CUE {name}")

    def led(self, color):
        self._send(f"LED {color}")

    def pressed(self):
        try:
            waiting = self.port.in_waiting
            self._buf += self.port.read(waiting) if waiting else b""
        except Exception as e:
            if self.connected:
                log.warning("base station read failed: %s", e)
            self.connected = False
            return False
        *lines, self._buf = self._buf.split(b"\n")
        pressed = False
        for raw in lines:
            line = raw.strip().decode("ascii", "ignore")
            if line == "BTN":
                pressed = True
            elif line in ("READY", "PONG"):
                self.connected = True
            elif line.startswith("ERR"):
                log.warning("base station: %s", line)
        return pressed

    def close(self):
        try:
            self.port.close()
        except Exception:
            pass


def open_base(spec, serial_port=None):
    if spec == "virtual":
        return VirtualBase()
    if spec == "serial":
        if not serial_port:
            raise ValueError("--base serial needs --serial-port (e.g. /dev/cu.usbmodem1101 or COM3)")
        return SerialBase.open(serial_port)
    raise ValueError(f"unknown base {spec!r}: use virtual or serial")
