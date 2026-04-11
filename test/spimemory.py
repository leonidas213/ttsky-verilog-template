from pathlib import Path
from collections import deque

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, ClockCycles, Event
from common import TTPins

from pathlib import Path
from collections import deque

from cocotb.triggers import RisingEdge, Event


class SpiMemoryDevice:
    def __init__(
        self,
        dut,
        pins: TTPins,
        cs_bit: int,
        name: str,
        size_bytes: int = 65536,
        fill: int = 0x00,
        require_wren: bool = False,
        support_fast_read: bool = False,
        strict_upper_addr_zero: bool = True,
        verbose: bool = False,
        log_bytes: bool = False,
        trace_fetch: bool = False,
    ):
        self.dut = dut
        self.pins = pins
        self.cs_bit = cs_bit
        self.name = name
        self.size = size_bytes
        self.mem = bytearray([fill] * self.size)

        self.require_wren = require_wren
        self.support_fast_read = support_fast_read
        self.strict_upper_addr_zero = strict_upper_addr_zero

        self.verbose = verbose
        self.log_bytes = log_bytes
        self.trace_fetch = trace_fetch

        self.write_enable = False

        self.prev_cs = 1
        self.prev_sclk = 0

        # fetch / instruction trace
        self.fetch_word_count = 0
        self.instr_count = 0
        self.literal_count = 0

        self.last_fetch_byte_addr = None
        self.last_fetch_word_addr = None
        self.last_fetch_word = None

        self._word_event = Event()
        self._instr_event = Event()

        self._clear_transaction_state()

    def _clear_transaction_state(self):
        self.cmd = None
        self.mode = None

        self.rx_shift = 0
        self.rx_count = 0

        self.tx_shift = 0
        self.tx_count = 0
        self.tx_queue = deque()

        self.addr_bytes = []
        self.addr = 0

        self.was_writing = False

        # read-stream tracking for fetch tracing
        self._stream_start_addr = None
        self._stream_bytes_from_mem = 0

    def _log(self, msg, *args):
        if self.verbose:
            self.dut._log.info(f"[SPI-{self.name}] " + msg, *args)

    def _log_byte(self, direction: str, value: int):
        if self.verbose and self.log_bytes:
            self.dut._log.info("[SPI-%s] %s 0x%02X", self.name, direction, value & 0xFF)

    def _cs(self) -> int:
        return self.pins.out_bit(self.cs_bit)

    def _queue_byte(self, value: int):
        self.tx_queue.append(value & 0xFF)
        self._log_byte("QUEUE", value)

    def _status_reg(self) -> int:
        return 0x02 if self.write_enable else 0x00

    def _decode_24bit_addr(self, addr24: int) -> int:
        upper = (addr24 >> 16) & 0xFF
        if self.strict_upper_addr_zero:
            assert upper <= 1, (
                f"{self.name}: upper address byte must be not bigger than 0x01, "
                f"got 0x{upper:02X} in 24-bit address 0x{addr24:06X}"
            )

        addr16 = addr24 & 0xFFFF
        self._log("ADDR24=0x%06X ADDR16=0x%04X", addr24, addr16)
        return addr16

    def load_bytes(self, data: bytes, base_addr: int = 0):
        base_addr &= 0xFFFF
        for i, b in enumerate(data):
            self.mem[(base_addr + i) & 0xFFFF] = b
        self._log("Loaded %d bytes at 0x%04X", len(data), base_addr)

    def load_file(self, path, base_addr: int = 0):
        data = Path(path).read_bytes()
        self.load_bytes(data, base_addr=base_addr)
        self._log("Loaded file %s at 0x%04X", str(path), base_addr & 0xFFFF)

    def poke8(self, addr: int, value: int):
        self.mem[addr & 0xFFFF] = value & 0xFF
        self._log("POKE8  [0x%04X] = 0x%02X", addr & 0xFFFF, value & 0xFF)

    def peek8(self, addr: int) -> int:
        return self.mem[addr & 0xFFFF]

    def poke16(self, addr: int, value: int, little_endian: bool = True):
        addr &= 0xFFFF
        lo = value & 0xFF
        hi = (value >> 8) & 0xFF
        if little_endian:
            self.mem[addr] = lo
            self.mem[(addr + 1) & 0xFFFF] = hi
        else:
            self.mem[addr] = hi
            self.mem[(addr + 1) & 0xFFFF] = lo
        self._log("POKE16 [0x%04X] = 0x%04X", addr, value & 0xFFFF)

    def peek16(self, addr: int, little_endian: bool = True) -> int:
        addr &= 0xFFFF
        b0 = self.mem[addr]
        b1 = self.mem[(addr + 1) & 0xFFFF]
        if little_endian:
            return b0 | (b1 << 8)
        return (b0 << 8) | b1

    # word-address helpers
    def poke16w(self, word_addr: int, value: int, little_endian: bool = False):
        self.poke16((word_addr & 0xFFFF) << 1, value, little_endian=little_endian)

    def peek16w(self, word_addr: int, little_endian: bool = False) -> int:
        return self.peek16((word_addr & 0xFFFF) << 1, little_endian=little_endian)

    def _write_byte(self, addr: int, value: int):
        if self.require_wren and not self.write_enable:
            self.dut._log.warning(
                "%s: ignoring write to 0x%04X because WREN is not set",
                self.name,
                addr & 0xFFFF,
            )
            return

        self.mem[addr & 0xFFFF] = value & 0xFF
        self._log("WRITE [0x%04X] = 0x%02X", addr & 0xFFFF, value & 0xFF)

    def _queue_mem_read_byte(self):
        byte_addr = self.addr & 0xFFFF
        data = self.peek8(byte_addr)
        self._queue_byte(data)
        self.addr = (self.addr + 1) & 0xFFFF
        self._stream_bytes_from_mem += 1
        self._trace_fetched_word_if_ready(byte_addr)

    def _trace_fetched_word_if_ready(self, last_byte_addr: int):
        if not self.trace_fetch:
            return
        
        if self.cmd not in (0x03, 0x0B):
            return

        # Only trace every 2 streamed bytes = 1 fetched 16-bit word
        if (self._stream_bytes_from_mem & 1) != 0:
            return

        word_start = (last_byte_addr - 1) & 0xFFFF

        if word_start & 1:
            self._log(
                "Fetched word starts at odd byte address 0x%04X, ignoring",
                word_start,
            )
            return

        word = self.peek16(word_start, little_endian=False)
        word_addr = word_start >> 1

        self.fetch_word_count += 1
        self.last_fetch_byte_addr = word_start
        self.last_fetch_word_addr = word_addr
        self.last_fetch_word = word

        self._log("FETCH word_addr=0x%04X word=0x%04X", word_addr, word)
        
        self._fire_word_event()

        # In your ISA, literal/immediate extension words have bit15 = 1
        if word & 0x8000:
            self.literal_count += 1
        else:
            self.instr_count += 1
            self._fire_instr_event()

    def _fire_word_event(self):
        old = self._word_event
        old.set()
        self._word_event = Event()

    def _fire_instr_event(self):
        old = self._instr_event
        old.set()
        self._instr_event = Event()

    def _handle_rx_byte(self, byte: int):
        self._log_byte("RX", byte)

        if self.cmd is None:
            self.cmd = byte
            self._log("CMD 0x%02X", byte)

            if byte == 0x06 and self.require_wren:
                self.write_enable = True
                self.mode = "ignore"
                self._log("WREN set")

            elif byte == 0x04 and self.require_wren:
                self.write_enable = False
                self.mode = "ignore"
                self._log("WREN cleared")

            elif byte == 0x05:
                self.mode = "read_status"
                sr = self._status_reg()
                self._log("RDSR -> 0x%02X", sr)
                self._queue_byte(sr)

            elif byte == 0x03:
                self.mode = "addr"
                self._log("READ command")

            elif byte == 0x0B and self.support_fast_read:
                self.mode = "addr_fast"
                self._log("FAST READ command")

            elif byte == 0x02:
                self.mode = "addr_write"
                self._log("WRITE/PROGRAM command")

            else:
                self.mode = "ignore"
                self.dut._log.warning(
                    "%s: unsupported SPI opcode 0x%02X", self.name, byte
                )

            return

        if self.mode in ("addr", "addr_fast", "addr_write"):
            self.addr_bytes.append(byte)
            self._log("ADDR byte %d = 0x%02X", len(self.addr_bytes), byte)

            if len(self.addr_bytes) == 3:
                addr24 = (
                    (self.addr_bytes[0] << 16)
                    | (self.addr_bytes[1] << 8)
                    | self.addr_bytes[2]
                )
                self.addr = self._decode_24bit_addr(addr24)

                if self.mode == "addr":
                    self.mode = "read_stream"
                    self._stream_start_addr = self.addr
                    self._stream_bytes_from_mem = 0
                    self._log(
                        "READ start @ 0x%04X -> 0x%02X",
                        self.addr,
                        self.peek8(self.addr),
                    )
                    self._queue_mem_read_byte()

                elif self.mode == "addr_fast":
                    self.mode = "fast_dummy"
                    self._log("FAST READ waiting for dummy byte")

                elif self.mode == "addr_write":
                    self.mode = "write_stream"
                    self.was_writing = True
                    self._log("WRITE stream start @ 0x%04X", self.addr)

            return

        if self.mode == "fast_dummy":
            self._log("FAST READ dummy = 0x%02X", byte)
            self.mode = "read_stream"
            self._stream_start_addr = self.addr
            self._stream_bytes_from_mem = 0
            self._log(
                "FAST READ start @ 0x%04X -> 0x%02X", self.addr, self.peek8(self.addr)
            )
            self._queue_mem_read_byte()
            return

        if self.mode == "read_stream":
            self._log("READ next @ 0x%04X -> 0x%02X", self.addr, self.peek8(self.addr))
            self._queue_mem_read_byte()
            return

        if self.mode == "read_status":
            sr = self._status_reg()
            self._log("RDSR continue -> 0x%02X", sr)
            self._queue_byte(sr)
            return

        if self.mode == "write_stream":
            self._write_byte(self.addr, byte)
            self.addr = (self.addr + 1) & 0xFFFF
            return

    def _on_spi_rising(self):
        bit = self.pins.mosi & 1
        self.rx_shift = ((self.rx_shift << 1) | bit) & 0xFF
        self.rx_count += 1

        if self.rx_count == 8:
            self._handle_rx_byte(self.rx_shift)
            self.rx_shift = 0
            self.rx_count = 0

    def _on_spi_falling(self):
        if self.tx_count == 0 and self.tx_queue:
            self.tx_shift = self.tx_queue.popleft()
            self.tx_count = 8
            self._log_byte("TX", self.tx_shift)

        if self.tx_count > 0:
            bit = (self.tx_shift >> 7) & 1
            self.pins.set_in_bit(TTPins.SPI_MISO, bit)
            self.tx_shift = (self.tx_shift << 1) & 0xFF
            self.tx_count -= 1
        else:
            self.pins.set_in_bit(TTPins.SPI_MISO, 0)

    async def run(self):
        self.pins.set_in_bit(TTPins.SPI_MISO, 0)

        while True:
            await RisingEdge(self.dut.clk)
            if str(self.dut.rst_n.value) == "1":
                break

        while True:
            await RisingEdge(self.dut.clk)
            cs = self._cs()
            if cs == 1:
                self.prev_cs = 1
                self.prev_sclk = self.pins.sclk
                break

        while True:
            await RisingEdge(self.dut.clk)

            cs = self._cs()
            sclk = self.pins.sclk

            if cs not in (0, 1) or sclk not in (0, 1):
                continue

            if cs == 1:
                if self.prev_cs == 0:
                    self._log("CS high -> end transaction")

                    if self.require_wren and self.was_writing:
                        self.write_enable = False
                        self._log("Auto clear WREN after write/program")

                    self._clear_transaction_state()
                    self.pins.set_in_bit(TTPins.SPI_MISO, 0)

                self.prev_cs = cs
                self.prev_sclk = sclk
                continue

            if self.prev_cs == 1 and cs == 0:
                self._clear_transaction_state()
                self.rx_shift = 0
                self.rx_count = 0
                self.tx_shift = 0
                self.tx_count = 0
                self._log("CS low -> begin transaction")

            if self.prev_sclk == 0 and sclk == 1:
                self._on_spi_rising()

            if self.prev_sclk == 1 and sclk == 0:
                self._on_spi_falling()

            self.prev_cs = cs
            self.prev_sclk = sclk


class SpiFlash(SpiMemoryDevice):
    def __init__(
        self,
        dut,
        pins: TTPins,
        size_bytes: int = 65536,
        verbose: bool = False,
        log_bytes: bool = False,
    ):
        super().__init__(
            dut=dut,
            pins=pins,
            cs_bit=TTPins.SPI_FLASH_CS,
            name="flash",
            size_bytes=size_bytes,
            fill=0x00,  # or 0xFF if you want
            require_wren=True,
            support_fast_read=True,
            strict_upper_addr_zero=True,
            verbose=verbose,
            log_bytes=log_bytes,
        )

        # program fetch tracking
        self.fetch_word_count = 0
        self.instr_count = 0
        self.literal_count = 0

        self.last_fetch_byte_addr = None
        self.last_fetch_word_addr = None
        self.last_fetch_word = None

        self._word_event = Event()
        self._instr_event = Event()

        self._stream_start_addr = None
        self._stream_bytes_from_mem = 0

    async def wait_instructions(self, count: int = 1):
        target = self.instr_count + count+1
        cocotb.log.info(
            "Waiting for %d instructions (current count: %d)", count, self.instr_count
        )
        while self.instr_count < target:
            evt = self._instr_event
            if self.instr_count >= target:
                break
            await evt.wait()

    async def wait_fetch_words(self, count: int = 1):
        target = self.fetch_word_count + count
        while self.fetch_word_count < target:
            evt = self._word_event
            if self.fetch_word_count >= target:
                break
            await evt.wait()

    async def step_instruction(self):
        await self.wait_instructions(1)
        return self.last_fetch_word_addr, self.last_fetch_word


class SpiRam(SpiMemoryDevice):
    def __init__(
        self,
        dut,
        pins: TTPins,
        size_bytes: int = 65536,
        verbose: bool = False,
        log_bytes: bool = False,
    ):
        super().__init__(
            dut=dut,
            pins=pins,
            cs_bit=TTPins.SPI_RAM_CS,
            name="ram",
            size_bytes=size_bytes,
            fill=0x00,
            require_wren=False,
            support_fast_read=False,
            strict_upper_addr_zero=True,
            verbose=verbose,
            log_bytes=log_bytes,
        )
