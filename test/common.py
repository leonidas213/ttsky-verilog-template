from pathlib import Path
from collections import deque

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, ClockCycles
class TTPins:
    SPI_MISO = 0
    SPI_RAM_CS = 1
    SPI_FLASH_CS = 2
    SPI_MOSI = 3
    SPI_SCLK = 4

    def __init__(self, dut):
        self.dut = dut
        self._uio_in_shadow = 0
        self.dut.uio_in.value = 0

    def _get_vec_str(self, sig) -> str:
        s = str(sig.value).strip()
        return s

    def out_bit(self, idx: int) -> int:
        s = str(self.dut.uio_out.value).strip()

        if not s or len(s) <= idx:
            return 0

        ch = s[-1 - idx]

        if ch == "1":
            return 1
        if ch == "0":
            return 0
        return 0

    def set_in_bit(self, idx: int, value: int):
        if value:
            self._uio_in_shadow |= (1 << idx)
        else:
            self._uio_in_shadow &= ~(1 << idx)
        self.dut.uio_in.value = self._uio_in_shadow

    @property
    def sclk(self) -> int:
        return self.out_bit(self.SPI_SCLK)

    @property
    def mosi(self) -> int:
        return self.out_bit(self.SPI_MOSI)

