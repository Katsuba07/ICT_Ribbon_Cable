"""UART communication with the cable tester board."""
import json
import time
import serial
import serial.tools.list_ports
from PySide6.QtCore import QThread, Signal


def list_serial_ports():
    return [p.device for p in serial.tools.list_ports.comports()]


def mask_to_hex(mask_bools) -> str:
    """Convert a list of 80 bools -> 20-char hex string, matching the firmware
    convention (idx 0..79 = Pin1..Pin80, packed into 10 bytes, 8 bits/byte)."""
    assert len(mask_bools) == 80, "mask must have exactly 80 elements"
    b = bytearray(10)
    for idx, active in enumerate(mask_bools):
        if active:
            chip = idx // 8
            bit = idx % 8
            b[chip] |= (1 << bit)
    return b.hex().upper()


# Opening a serial port toggles DTR on most boards, which resets an Arduino
# Nano. The board needs time to reboot and re-run setup() before it can
# receive/parse a command - sending immediately after open() will be missed.
BOARD_RESET_WAIT_SECONDS = 2.0


class TestWorker(QThread):
    """Runs a single test on a background thread so the UI doesn't freeze."""
    finished = Signal(dict)   # {"open": [...], "short": [[a,b],...]}
    error = Signal(str)

    def __init__(self, port: str, baudrate: int, mask_hex: str, timeout: float = 5.0, parent=None):
        super().__init__(parent)
        self.port = port
        self.baudrate = baudrate
        self.mask_hex = mask_hex
        self.timeout = timeout

    def run(self):
        line = ""
        try:
            with serial.Serial(self.port, self.baudrate, timeout=self.timeout) as ser:
                # Wait for the board to finish rebooting after the port was opened.
                time.sleep(BOARD_RESET_WAIT_SECONDS)
                ser.reset_input_buffer()

                cmd = f"T:{self.mask_hex}\n".encode("ascii")
                ser.write(cmd)

                # Skip any blank/garbage lines and wait for a valid JSON response,
                # bounded by the overall serial timeout.
                deadline = time.time() + self.timeout
                data = None
                while time.time() < deadline:
                    line = ser.readline().decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue  # e.g. a stray boot message, keep waiting

                if data is None:
                    self.error.emit(
                        "No response received from the board (timeout). "
                        "Check the COM port/baudrate and that the firmware is flashed."
                    )
                    return
                if "error" in data:
                    self.error.emit(f"Board reported an error: {data['error']}")
                    return
                self.finished.emit(data)
        except serial.SerialException as e:
            self.error.emit(f"Serial connection error: {e}")
        except Exception as e:
            self.error.emit(f"Unexpected error: {e}")
