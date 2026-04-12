from pathlib import Path


import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, ClockCycles
from common import TTPins
from spimemory import SpiMemoryDevice, SpiFlash, SpiRam


async def reset_dut(dut):
    dut.rst_n.value = 0
    dut.uio_in.value = 0
    dut.ui_in.value = 0
    dut.ena.value = 1

    await Timer(100, unit="ns")
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)


async def boot_cpu(dut) -> tuple[TTPins, SpiMemoryDevice, SpiMemoryDevice]:
    dut._log.info("Booting CPU ")
    cocotb.start_soon(Clock(dut.clk, 40, unit="ns").start())
    pins = TTPins(dut)
    flash = SpiFlash(dut, pins, verbose=False)
    ram = SpiRam(dut, pins)
    return pins, flash, ram


def _u16(x: int) -> int:
    return x & 0xFFFF


@cocotb.test()
async def test_cpu_add_reg(dut):
    dut._log.info("Starting ADD test")
    pins, flash, ram = await boot_cpu(dut)

    flash.trace_fetch = True

    # 0:0 |    0 |       ; start:
    # 0:0 |    0 | 3d 02 ; jump main
    # 2:0 |    1 | 00 00 ; nop
    # 4:0 |    2 |       ; interrupt_routine:
    # 4:0 |    2 | 44 00 ; reti
    # 6:0 |    3 |       ; main:
    # 6:0 |    3 | 0a 05 ; ldi r0 , 5
    # 8:0 |    4 | 0a 12 ; ldi r1 , 2
    # a:0 |    5 | 02 01 ; add r0, r1
    # c:0 |    6 | 3f b0 ; putoutput r0
    # e:0 |    7 |       ; foreverloop:
    # e:0 |    7 | 3d fb ; jump foreverloop
    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A05)
    flash.poke16w(0x0004, 0x0A12)
    flash.poke16w(0x0005, 0x0201)
    flash.poke16w(0x0006, 0x3F10)
    flash.poke16w(0x0007, 0x3DFF)
    for i in range(20):
        prgo = flash.peek8(i)
        dut._log.info("flash[%02x] = %02x", i, prgo)
    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(7)

    cocotb.log.info("ADD for uo_out is %d", (dut.uo_out.value))
    assert dut.uo_out.value == 7, f"Expected 7 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_mov_reg(dut):
    dut._log.info("Starting MOV test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    # 0:0 |    0 |       ; start:
    # 0:0 |    0 | 3d 02 ; jump main
    # 2:0 |    1 | 00 00 ; nop
    # 4:0 |    2 | 44 00 ; reti
    # 6:0 |    3 |       ; main:
    # 6:0 |    3 | 0a 19 ; ldi r1, 9
    # 8:0 |    4 | 01 01 ; mov r0, r1
    # a:0 |    5 | 3f 10 ; putoutput r0
    # c:0 |    6 |       ; forever:
    # c:0 |    6 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A19)
    flash.poke16w(0x0004, 0x0101)
    flash.poke16w(0x0005, 0x3F10)
    flash.poke16w(0x0006, 0x3DFF)
    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(6)
    assert dut.uo_out.value == 9, f"Expected 9 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_add_reg(dut):
    dut._log.info("Starting ADD REG test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    # 0:0 |    0 |       ; start:
    # 0:0 |    0 | 3d 02 ; jump main
    # 2:0 |    1 | 00 00 ; nop
    # 4:0 |    2 | 44 00 ; reti
    # 6:0 |    3 |       ; main:
    # 6:0 |    3 | 0a 05 ; ldi r0, 5
    # 8:0 |    4 | 0a 12 ; ldi r1, 2
    # a:0 |    5 | 02 01 ; add r0, r1
    # c:0 |    6 | 3f 10 ; putoutput r0
    # e:0 |    7 |       ; forever:
    # e:0 |    7 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A05)
    flash.poke16w(0x0004, 0x0A12)
    flash.poke16w(0x0005, 0x0201)
    flash.poke16w(0x0006, 0x3F10)
    flash.poke16w(0x0007, 0x3DFF)
    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(7)
    assert dut.uo_out.value == 7, f"Expected 7 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_add_imm4(dut):
    dut._log.info("Starting ADD IMM4 test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    # 0:0 |    0 |       ; start:
    # 0:0 |    0 | 3d 02 ; jump main
    # 2:0 |    1 | 00 00 ; nop
    # 4:0 |    2 | 44 00 ; reti
    # 6:0 |    3 |       ; main:
    # 6:0 |    3 | 0a 05 ; ldi r0, 5
    # 8:0 |    4 | 0c 03 ; add r0, 3
    # a:0 |    5 | 3f 10 ; putoutput r0
    # c:0 |    6 |       ; forever:
    # c:0 |    6 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A05)
    flash.poke16w(0x0004, 0x0C03)
    flash.poke16w(0x0005, 0x3F10)
    flash.poke16w(0x0006, 0x3DFF)
    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(6)
    assert dut.uo_out.value == 8, f"Expected 8 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_sub_reg(dut):
    dut._log.info("Starting SUB REG test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    # 0:0 |    0 |       ; start:
    # 0:0 |    0 | 3d 02 ; jump main
    # 2:0 |    1 | 00 00 ; nop
    # 4:0 |    2 | 44 00 ; reti
    # 6:0 |    3 |       ; main:
    # 6:0 |    3 | 0a 09 ; ldi r0, 9
    # 8:0 |    4 | 0a 12 ; ldi r1, 2
    # a:0 |    5 | 04 01 ; sub r0, r1
    # c:0 |    6 | 3f 10 ; putoutput r0
    # e:0 |    7 |       ; forever:
    # e:0 |    7 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A09)
    flash.poke16w(0x0004, 0x0A12)
    flash.poke16w(0x0005, 0x0401)
    flash.poke16w(0x0006, 0x3F10)
    flash.poke16w(0x0007, 0x3DFF)
    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(7)
    assert dut.uo_out.value == 7, f"Expected 7 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_and_reg(dut):
    dut._log.info("Starting AND REG test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #   0:0 |    0 |       ; start:
    #   0:0 |    0 | 3d 02 ; jump main
    #   2:0 |    1 | 00 00 ; nop
    #   4:0 |    2 | 44 00 ; reti
    #   6:0 |    3 |       ; main:
    #   6:0 |    3 | 0a 0e ; ldi r0, 14
    #   8:0 |    4 | 0a 1b ; ldi r1, 11
    #   a:0 |    5 | 06 01 ; and r0, r1
    #   c:0 |    6 | 3f 10 ; putoutput r0
    #   e:0 |    7 |       ; forever:
    #   e:0 |    7 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A0E)
    flash.poke16w(0x0004, 0x0A1B)
    flash.poke16w(0x0005, 0x0601)
    flash.poke16w(0x0006, 0x3F10)
    flash.poke16w(0x0007, 0x3DFF)
    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(7)
    assert dut.uo_out.value == 10, f"Expected 10 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_or_reg(dut):
    dut._log.info("Starting OR REG test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |       ; start:
    #  0:0 |    0 | 3d 02 ; jump main
    #  2:0 |    1 | 00 00 ; nop
    #  4:0 |    2 | 44 00 ; reti
    #  6:0 |    3 |       ; main:
    #  6:0 |    3 | 0a 0a ; ldi r0, 10
    #  8:0 |    4 | 0a 15 ; ldi r1, 5
    #  a:0 |    5 | 07 01 ; or  r0, r1
    #  c:0 |    6 | 3f 10 ; putoutput r0
    #  e:0 |    7 |       ; forever:
    #  e:0 |    7 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A0A)
    flash.poke16w(0x0004, 0x0A15)
    flash.poke16w(0x0005, 0x0701)
    flash.poke16w(0x0006, 0x3F10)
    flash.poke16w(0x0007, 0x3DFF)
    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(7)
    assert dut.uo_out.value == 15, f"Expected 15 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_xor_reg(dut):
    dut._log.info("Starting XOR REG test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    # 0:0 |    0 |       ; start:
    # 0:0 |    0 | 3d 02 ; jump main
    # 2:0 |    1 | 00 00 ; nop
    # 4:0 |    2 | 44 00 ; reti
    # 6:0 |    3 |       ; main:
    # 6:0 |    3 | 0a 0f ; ldi r0, 15
    # 8:0 |    4 | 0a 1a ; ldi r1, 10
    # a:0 |    5 | 08 01 ; xor r0, r1
    # c:0 |    6 | 3f 10 ; putoutput r0
    # e:0 |    7 |       ; forever:
    # e:0 |    7 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A0F)
    flash.poke16w(0x0004, 0x0A1A)
    flash.poke16w(0x0005, 0x0801)
    flash.poke16w(0x0006, 0x3F10)
    flash.poke16w(0x0007, 0x3DFF)
    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(7)
    assert dut.uo_out.value == 5, f"Expected 5 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_neg(dut):
    dut._log.info("Starting NEG test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    # 0:0 |    0 |       ; start:
    # 0:0 |    0 | 3d 02 ; jump main
    # 2:0 |    1 | 00 00 ; nop
    # 4:0 |    2 | 44 00 ; reti
    # 6:0 |    3 |       ; main:
    # 6:0 |    3 | 0a 01 ; ldi r0, 1
    # 8:0 |    4 | 13 00 ; neg r0
    # a:0 |    5 | 3f 10 ; putoutput r0
    # c:0 |    6 |       ; forever:
    # c:0 |    6 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A01)
    flash.poke16w(0x0004, 0x1300)
    flash.poke16w(0x0005, 0x3F10)
    flash.poke16w(0x0006, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(6)
    assert dut.uo_out.value == 255, f"Expected 255 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_not(dut):
    dut._log.info("Starting NOT test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    # 0:0 |    0 |       ; start:
    # 0:0 |    0 | 3d 02 ; jump main
    # 2:0 |    1 | 00 00 ; nop
    # 4:0 |    2 | 44 00 ; reti
    # 6:0 |    3 |       ; main:
    # 6:0 |    3 | 0a 00 ; ldi r0, 0
    # 8:0 |    4 | 1a 00 ; not r0
    # a:0 |    5 | 3f 10 ; putoutput r0
    # c:0 |    6 |       ; forever:
    # c:0 |    6 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A00)
    flash.poke16w(0x0004, 0x1A00)
    flash.poke16w(0x0005, 0x3F10)
    flash.poke16w(0x0006, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(6)
    assert dut.uo_out.value == 255, f"Expected 255 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_lsl(dut):
    dut._log.info("Starting LSL test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    # 0:0 |    0 |       ; start:
    # 0:0 |    0 | 3d 02 ; jump main
    # 2:0 |    1 | 00 00 ; nop
    # 4:0 |    2 | 44 00 ; reti
    # 6:0 |    3 |       ; main:
    # 6:0 |    3 | 0a 03 ; ldi r0, 3
    # 8:0 |    4 | 24 00 ; lsl r0
    # a:0 |    5 | 3f 10 ; putoutput r0
    # c:0 |    6 |       ; forever:
    # c:0 |    6 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A03)
    flash.poke16w(0x0004, 0x2400)
    flash.poke16w(0x0005, 0x3F10)
    flash.poke16w(0x0006, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(6)
    assert dut.uo_out.value == 6, f"Expected 6 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_lsr(dut):
    dut._log.info("Starting LSR test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    # 0:0 |    0 |       ; start:
    # 0:0 |    0 | 3d 02 ; jump main
    # 2:0 |    1 | 00 00 ; nop
    # 4:0 |    2 | 44 00 ; reti
    # 6:0 |    3 |       ; main:
    # 6:0 |    3 | 0a 08 ; ldi r0, 8
    # 8:0 |    4 | 25 00 ; lsr r0
    # a:0 |    5 | 3f 10 ; putoutput r0
    # c:0 |    6 |       ; forever:
    # c:0 |    6 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A08)
    flash.poke16w(0x0004, 0x2500)
    flash.poke16w(0x0005, 0x3F10)
    flash.poke16w(0x0006, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(6)
    assert dut.uo_out.value == 4, f"Expected 4 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_asr(dut):
    dut._log.info("Starting ASR test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 02       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; main:
    #  6:0 |    3 | ff fe 09 01 ; ldi r0, -2
    #  a:0 |    5 | 28 00       ; asr r0
    #  c:0 |    6 | 3f 10       ; putoutput r0
    #  e:0 |    7 |             ; forever:
    #  e:0 |    7 | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0xFFFE)
    flash.poke16w(0x0004, 0x0901)
    flash.poke16w(0x0005, 0x2800)
    flash.poke16w(0x0006, 0x3F10)
    flash.poke16w(0x0007, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(6)
    assert dut.uo_out.value == 255, f"Expected 255 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_swap(dut):
    dut._log.info("Starting SWAP test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    # 0:0 |    0 |             ; start:
    # 0:0 |    0 | 3d 02       ; jump main
    # 2:0 |    1 | 00 00       ; nop
    # 4:0 |    2 | 44 00       ; reti
    # 6:0 |    3 |             ; main:
    # 6:0 |    3 | 92 34 09 00 ; ldi r0, 0x1234
    # a:0 |    5 | 29 00       ; swap r0
    # c:0 |    6 | 3f 10       ; putoutput r0
    # e:0 |    7 |             ; forever:
    # e:0 |    7 | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x9234)
    flash.poke16w(0x0004, 0x0900)
    flash.poke16w(0x0005, 0x2900)
    flash.poke16w(0x0006, 0x3F10)
    flash.poke16w(0x0007, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(6)
    assert dut.uo_out.value == 0x12, f"Expected 0x12 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_swapn(dut):
    dut._log.info("Starting SWAPN test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    # 0:0 |    0 |             ; start:
    # 0:0 |    0 | 3d 02       ; jump main
    # 2:0 |    1 | 00 00       ; nop
    # 4:0 |    2 | 44 00       ; reti
    # 6:0 |    3 |             ; main:
    # 6:0 |    3 | 92 34 09 00 ; ldi r0, 0x1234
    # a:0 |    5 | 2a 00       ; swapn r0
    # c:0 |    6 | 3f 10       ; putoutput r0
    # e:0 |    7 |             ; forever:
    # e:0 |    7 | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x9234)
    flash.poke16w(0x0004, 0x0900)
    flash.poke16w(0x0005, 0x2A00)
    flash.poke16w(0x0006, 0x3F10)
    flash.poke16w(0x0007, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(6)
    assert dut.uo_out.value == 0x43, f"Expected 0x43 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_cmp_jumpzero(dut):
    dut._log.info("Starting CMP/JZ test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #   0:0 |    0 |       ; start:
    #   0:0 |    0 | 3d 02 ; jump main
    #   2:0 |    1 | 00 00 ; nop
    #   4:0 |    2 | 44 00 ; reti
    #   6:0 |    3 |       ; main:
    #   6:0 |    3 | 0a 05 ; ldi r0, 5
    #   8:0 |    4 | 0a 15 ; ldi r1, 5
    #   a:0 |    5 | 1e 01 ; cmp r0, r1
    #   c:0 |    6 | 35 03 ; jumpZero equal_label
    #   e:0 |    7 | 0a 21 ; ldi r2, 1
    #  10:0 |    8 | 3f 12 ; putoutput r2
    #  12:0 |    9 | 3d 02 ; jump forever
    #  14:0 |    a |       ; equal_label:
    #  14:0 |    a | 0a 29 ; ldi r2, 9
    #  16:0 |    b | 3f 12 ; putoutput r2
    #  18:0 |    c |       ; forever:
    #  18:0 |    c | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A05)
    flash.poke16w(0x0004, 0x0A15)
    flash.poke16w(0x0005, 0x1E01)
    flash.poke16w(0x0006, 0x3503)
    flash.poke16w(0x0007, 0x0A21)
    flash.poke16w(0x0008, 0x3F12)
    flash.poke16w(0x0009, 0x3D02)
    flash.poke16w(0x000A, 0x0A29)
    flash.poke16w(0x000B, 0x3F12)
    flash.poke16w(0x000C, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(10)
    assert dut.uo_out.value == 9, f"Expected 9 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_cmp_jumpnotzero(dut):
    dut._log.info("Starting CMP/JNZ test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #   0:0 |    0 |       ; start:
    #   0:0 |    0 | 3d 02 ; jump main
    #   2:0 |    1 | 00 00 ; nop
    #   4:0 |    2 | 44 00 ; reti
    #   6:0 |    3 |       ; main:
    #   6:0 |    3 | 0a 05 ; ldi r0, 5
    #   8:0 |    4 | 0a 14 ; ldi r1, 4
    #   a:0 |    5 | 1e 01 ; cmp r0, r1
    #   c:0 |    6 | 38 03 ; jumpNotZero noteq_label
    #   e:0 |    7 | 0a 21 ; ldi r2, 1
    #  10:0 |    8 | 3f 12 ; putoutput r2
    #  12:0 |    9 | 3d 02 ; jump forever
    #  14:0 |    a |       ; noteq_label:
    #  14:0 |    a | 0a 28 ; ldi r2, 8
    #  16:0 |    b | 3f 12 ; putoutput r2
    #  18:0 |    c |       ; forever:
    #  18:0 |    c | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A05)
    flash.poke16w(0x0004, 0x0A14)
    flash.poke16w(0x0005, 0x1E01)
    flash.poke16w(0x0006, 0x3803)
    flash.poke16w(0x0007, 0x0A21)
    flash.poke16w(0x0008, 0x3F12)
    flash.poke16w(0x0009, 0x3D02)
    flash.poke16w(0x000A, 0x0A28)
    flash.poke16w(0x000B, 0x3F12)
    flash.poke16w(0x000C, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(10)
    assert dut.uo_out.value == 8, f"Expected 8 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_jump_abs(dut):
    dut._log.info("Starting ABS JUMP test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #   0:0 |    0 |             ; start:
    #   0:0 |    0 | 80 ff 3c 00 ; jump main
    #                            ; #addr 0xff <-- this  put assembly next to the address
    # 1fe:0 |   ff |             ; main:
    # 1fe:0 |   ff | 0a 0c       ; ldi r0, 12
    # 200:0 |  100 | 3f 10       ; putoutput r0
    # 202:0 |  101 |             ; forever:
    # 202:0 |  101 | 82 ff 3c 00 ; jump jumplabel
    #                            ; #addr 0x02ff <-- this  put assembly next to the address
    # 5fe:0 |  2ff |             ; jumplabel:
    # 5fe:0 |  2ff | 81 01 3c 00 ; jump forever
    
    flash.poke16w(0x0000, 0x80FF)
    flash.poke16w(0x0001, 0x3C00)
    flash.poke16w(0x00FF, 0x0A0C)
    flash.poke16w(0x0100, 0x3F10) 
    flash.poke16w(0x0101, 0x82FF)
    flash.poke16w(0x0102, 0x3C00)
    flash.poke16w(0x02FF, 0x8101)
    flash.poke16w(0x0300, 0x3C00)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(9)
    assert dut.uo_out.value == 12, f"Expected 12 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_st_ld_absolute(dut):
    dut._log.info("Starting ST/LD absolute test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 02       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; main:
    #  6:0 |    3 | 80 34 09 00 ; ldi r0, 0x34
    #  a:0 |    5 | 80 10 2d 00 ; st  0x0010, r0
    #  e:0 |    7 | 80 10 2f 10 ; ld  r1, 0x0010
    # 12:0 |    9 | 3f 11       ; putoutput r1
    # 14:0 |    a |             ; forever:
    # 14:0 |    a | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x8034)
    flash.poke16w(0x0004, 0x0900)
    flash.poke16w(0x0005, 0x8010)
    flash.poke16w(0x0006, 0x2D00)
    flash.poke16w(0x0007, 0x8010)
    flash.poke16w(0x0008, 0x2F10)
    flash.poke16w(0x0009, 0x3F11)
    flash.poke16w(0x000A, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(7)
    assert dut.uo_out.value == 0x34, f"Expected 0x34 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_st_ld_ptr(dut):
    dut._log.info("Starting ST/LD pointer test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #   0:0 |    0 |             ; start:
    #   0:0 |    0 | 3d 02       ; jump main
    #   2:0 |    1 | 00 00       ; nop
    #   4:0 |    2 | 44 00       ; reti
    #   6:0 |    3 |             ; main:
    #   6:0 |    3 | 80 12 09 20 ; ldi r2, 0x0012
    #   a:0 |    5 | 80 56 09 00 ; ldi r0, 0x56
    #   e:0 |    7 | 2b 20       ; st  [r2], r0
    #  10:0 |    8 | 2c 12       ; ld  r1, [r2]
    #  12:0 |    9 | 3f 11       ; putoutput r1
    #  14:0 |    a |             ; forever:
    #  14:0 |    a | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x8012)
    flash.poke16w(0x0004, 0x0920)
    flash.poke16w(0x0005, 0x8056)
    flash.poke16w(0x0006, 0x0900)
    flash.poke16w(0x0007, 0x2B20)
    flash.poke16w(0x0008, 0x2C12)
    flash.poke16w(0x0009, 0x3F11)
    flash.poke16w(0x000A, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(8)
    assert dut.uo_out.value == 0x56, f"Expected 0x56 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_st_ld_offset(dut):
    dut._log.info("Starting ST/LD offset test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 02       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; main:
    #  6:0 |    3 | 80 20 09 20 ; ldi r2, 0x0020
    #  a:0 |    5 | 80 77 09 00 ; ldi r0, 0x77
    #  e:0 |    7 | 80 03 31 20 ; st  [r2 + 3], r0
    # 12:0 |    9 | 80 03 32 12 ; ld  r1, [r2 + 3]
    # 16:0 |    b | 3f 11       ; putoutput r1
    # 18:0 |    c |             ; forever:
    # 18:0 |    c | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x8020)
    flash.poke16w(0x0004, 0x0920)
    flash.poke16w(0x0005, 0x8077)
    flash.poke16w(0x0006, 0x0900)
    flash.poke16w(0x0007, 0x8003)
    flash.poke16w(0x0008, 0x3120)
    flash.poke16w(0x0009, 0x8003)
    flash.poke16w(0x000A, 0x3212)
    flash.poke16w(0x000B, 0x3F11)
    flash.poke16w(0x000C, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(8)
    assert dut.uo_out.value == 0x77, f"Expected 0x77 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_rcall_rret(dut):
    dut._log.info("Starting RCALL/RRET test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 04       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; func:
    #  6:0 |    3 | 0a 0b       ; ldi r0, 11
    #  8:0 |    4 | 3b 0f       ; rret RA
    #  a:0 |    5 |             ; main:
    #  a:0 |    5 | 80 03 3a f0 ; rcall RA, func
    #  e:0 |    7 | 3f 10       ; putoutput r0
    # 10:0 |    8 |             ; forever:
    # 10:0 |    8 | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D04)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A0B)
    flash.poke16w(0x0004, 0x3B0F)
    flash.poke16w(0x0005, 0x8003)
    flash.poke16w(0x0006, 0x3AF0)
    flash.poke16w(0x0007, 0x3F10)
    flash.poke16w(0x0008, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(8)
    assert dut.uo_out.value == 11, f"Expected 11 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_in_inputreg(dut):
    dut._log.info("Starting IN InputReg test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    dut.ui_in.value = 0xA5

    #  0:0 |    0 |       ; start:
    #  0:0 |    0 | 3d 02 ; jump main
    #  2:0 |    1 | 00 00 ; nop
    #  4:0 |    2 | 44 00 ; reti
    #  6:0 |    3 |       ; main:
    #  6:0 |    3 | 42 02 ; in  r0, InputReg
    #  8:0 |    4 | 3f 10 ; putoutput r0
    #  a:0 |    5 |       ; forever:
    #  a:0 |    5 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x4200)
    flash.poke16w(0x0004, 0x3F10)
    flash.poke16w(0x0005, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    dut.ui_in.value = 0xA5
    await flash.wait_instructions(6)
    assert dut.uo_out.value == 0xA5, f"Expected 0xA5 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_adc_no_carry_in(dut):
    dut._log.info("Starting ADC no-carry test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #   0:0 |    0 |       ; start:
    #   0:0 |    0 | 3d 02 ; jump main
    #   2:0 |    1 | 00 00 ; nop
    #   4:0 |    2 | 44 00 ; reti
    #   6:0 |    3 |       ; main:
    #   6:0 |    3 | 0a 05 ; ldi r0, 5
    #   8:0 |    4 | 0a 12 ; ldi r1, 2
    #   a:0 |    5 | 1e 22 ; cmp r2, r2
    #   c:0 |    6 | 03 01 ; adc r0, r1
    #   e:0 |    7 | 3f 10 ; putoutput r0
    #  10:0 |    8 |       ; forever:
    #  10:0 |    8 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A05)
    flash.poke16w(0x0004, 0x0A12)
    flash.poke16w(0x0005, 0x1E22)
    flash.poke16w(0x0006, 0x0301)
    flash.poke16w(0x0007, 0x3F10)
    flash.poke16w(0x0008, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(8)
    assert dut.uo_out.value == 7, f"Expected 7 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_adc_with_carry_in(dut):
    dut._log.info("Starting ADC carry-in test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |       ; start:
    #  0:0 |    0 | 3d 02 ; jump main
    #  2:0 |    1 | 00 00 ; nop
    #  4:0 |    2 | 44 00 ; reti
    #  6:0 |    3 |       ; main:
    #  6:0 |    3 | 0a 20 ; ldi r2, 0
    #  8:0 |    4 | 10 21 ; sub r2, 1c
    #  a:0 |    5 | 0a 05 ; ldi r0, 5
    #  c:0 |    6 | 0a 12 ; ldi r1, 2
    #  e:0 |    7 | 03 01 ; adc r0, r1
    # 10:0 |    8 | 3f 10 ; putoutput r0
    # 12:0 |    9 |       ; forever:
    # 12:0 |    9 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A20)
    flash.poke16w(0x0004, 0x1021)
    flash.poke16w(0x0005, 0x0A05)
    flash.poke16w(0x0006, 0x0A12)
    flash.poke16w(0x0007, 0x0301)
    flash.poke16w(0x0008, 0x3F10)
    flash.poke16w(0x0009, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(9)
    assert dut.uo_out.value == 8, f"Expected 8 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_sbc_with_borrow(dut):
    dut._log.info("Starting SBC test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |       ; start:
    #  0:0 |    0 | 3d 02 ; jump main
    #  2:0 |    1 | 00 00 ; nop
    #  4:0 |    2 | 44 00 ; reti
    #  6:0 |    3 |       ; main:
    #  6:0 |    3 | 0a 20 ; ldi r2, 0
    #  8:0 |    4 | 10 21 ; sub r2, 1
    #  a:0 |    5 | 0a 09 ; ldi r0, 9
    #  c:0 |    6 | 0a 12 ; ldi r1, 2
    #  e:0 |    7 | 05 01 ; sbc r0, r1
    # 10:0 |    8 | 3f 10 ; putoutput r0
    # 12:0 |    9 |       ; forever:
    # 12:0 |    9 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A20)
    flash.poke16w(0x0004, 0x1021)
    flash.poke16w(0x0005, 0x0A09)
    flash.poke16w(0x0006, 0x0A12)
    flash.poke16w(0x0007, 0x0501)
    flash.poke16w(0x0008, 0x3F10)
    flash.poke16w(0x0009, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(9)
    assert dut.uo_out.value == 6, f"Expected 6 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_jumpzero_taken(dut):
    dut._log.info("Starting JZ taken test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |       ; start:
    #  0:0 |    0 | 3d 02 ; jump main
    #  2:0 |    1 | 00 00 ; nop
    #  4:0 |    2 | 44 00 ; reti
    #  6:0 |    3 |       ; main:
    #  6:0 |    3 | 0a 05 ; ldi r0, 5
    #  8:0 |    4 | 21 05 ; cmp r0, 5
    #  a:0 |    5 | 35 03 ; jumpZero equal_label
    #  c:0 |    6 | 0a 11 ; ldi r1, 1
    #  e:0 |    7 | 3f 11 ; putoutput r1
    # 10:0 |    8 | 3d 02 ; jump forever
    # 12:0 |    9 |       ; equal_label:
    # 12:0 |    9 | 0a 19 ; ldi r1, 9
    # 14:0 |    a | 3f 11 ; putoutput r1
    # 16:0 |    b |       ; forever:
    # 16:0 |    b | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A05)
    flash.poke16w(0x0004, 0x2105)
    flash.poke16w(0x0005, 0x3503)
    flash.poke16w(0x0006, 0x0A11)
    flash.poke16w(0x0007, 0x3F11)
    flash.poke16w(0x0008, 0x3D02)
    flash.poke16w(0x0009, 0x0A19)
    flash.poke16w(0x000A, 0x3F11)
    flash.poke16w(0x000B, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(10)
    assert dut.uo_out.value == 9, f"Expected 9 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_jumpnotzero_taken(dut):
    dut._log.info("Starting JNZ taken test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |       ; start:
    #  0:0 |    0 | 3d 02 ; jump main
    #  2:0 |    1 | 00 00 ; nop
    #  4:0 |    2 | 44 00 ; reti
    #  6:0 |    3 |       ; main:
    #  6:0 |    3 | 0a 05 ; ldi r0, 5
    #  8:0 |    4 | 21 04 ; cmp r0, 4
    #  a:0 |    5 | 38 03 ; jumpNotZero noteq_label
    #  c:0 |    6 | 0a 11 ; ldi r1, 1
    #  e:0 |    7 | 3f 11 ; putoutput r1
    # 10:0 |    8 | 3d 02 ; jump forever
    # 12:0 |    9 |       ; noteq_label:
    # 12:0 |    9 | 0a 18 ; ldi r1, 8
    # 14:0 |    a | 3f 11 ; putoutput r1
    # 16:0 |    b |       ; forever:
    # 16:0 |    b | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A05)
    flash.poke16w(0x0004, 0x2104)
    flash.poke16w(0x0005, 0x3803)
    flash.poke16w(0x0006, 0x0A11)
    flash.poke16w(0x0007, 0x3F11)
    flash.poke16w(0x0008, 0x3D02)
    flash.poke16w(0x0009, 0x0A18)
    flash.poke16w(0x000A, 0x3F11)
    flash.poke16w(0x000B, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(10)
    assert dut.uo_out.value == 8, f"Expected 8 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_jumpnegative_taken(dut):
    dut._log.info("Starting JN taken test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |       ; start:
    #  0:0 |    0 | 3d 02 ; jump main
    #  2:0 |    1 | 00 00 ; nop
    #  4:0 |    2 | 44 00 ; reti
    #  6:0 |    3 |       ; main:
    #  6:0 |    3 | 0a 01 ; ldi r0, 1
    #  8:0 |    4 | 21 02 ; cmp r0, 2
    #  a:0 |    5 | 36 03 ; jumpNegative neg_label
    #  c:0 |    6 | 0a 11 ; ldi r1, 1
    #  e:0 |    7 | 3f 11 ; putoutput r1
    # 10:0 |    8 | 3d 02 ; jump forever
    # 12:0 |    9 |       ; neg_label:
    # 12:0 |    9 | 0a 17 ; ldi r1, 7
    # 14:0 |    a | 3f 11 ; putoutput r1
    # 16:0 |    b |       ; forever:
    # 16:0 |    b | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A01)
    flash.poke16w(0x0004, 0x2102)
    flash.poke16w(0x0005, 0x3603)
    flash.poke16w(0x0006, 0x0A11)
    flash.poke16w(0x0007, 0x3F11)
    flash.poke16w(0x0008, 0x3D02)
    flash.poke16w(0x0009, 0x0A17)
    flash.poke16w(0x000A, 0x3F11)
    flash.poke16w(0x000B, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(10)
    assert dut.uo_out.value == 7, f"Expected 7 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_jumpcarry_taken(dut):
    dut._log.info("Starting JC taken test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 02       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; main:
    #  6:0 |    3 | ff ff 09 01 ; ldi r0, 0xFFFF
    #  a:0 |    5 | 0c 01       ; add r0, 1
    #  c:0 |    6 | 34 03       ; jumpCarry carry_label
    #  e:0 |    7 | 0a 11       ; ldi r1, 1
    # 10:0 |    8 | 3f 11       ; putoutput r1
    # 12:0 |    9 | 3d 02       ; jump forever
    # 14:0 |    a |             ; carry_label:
    # 14:0 |    a | 0a 16       ; ldi r1, 6
    # 16:0 |    b | 3f 11       ; putoutput r1
    # 18:0 |    c |             ; forever:
    # 18:0 |    c | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0xFFFF)
    flash.poke16w(0x0004, 0x0901)
    flash.poke16w(0x0005, 0x0C01)
    flash.poke16w(0x0006, 0x3403)
    flash.poke16w(0x0007, 0x0A11)
    flash.poke16w(0x0008, 0x3F11)
    flash.poke16w(0x0009, 0x3D02)
    flash.poke16w(0x000A, 0x0A16)
    flash.poke16w(0x000B, 0x3F11)
    flash.poke16w(0x000C, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(10)
    assert dut.uo_out.value == 6, f"Expected 6 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_lsl_sets_carry(dut):
    dut._log.info("Starting LSL carry test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 02       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; main:
    #  6:0 |    3 | 80 00 09 01 ; ldi r0, 0x8000
    #  a:0 |    5 | 24 00       ; lsl r0
    #  c:0 |    6 | 34 03       ; jumpCarry carry_label
    #  e:0 |    7 | 0a 11       ; ldi r1, 1
    # 10:0 |    8 | 3f 11       ; putoutput r1
    # 12:0 |    9 | 3d 02       ; jump forever
    # 14:0 |    a |             ; carry_label:
    # 14:0 |    a | 0a 15       ; ldi r1, 5
    # 16:0 |    b | 3f 11       ; putoutput r1
    # 18:0 |    c |             ; forever:
    # 18:0 |    c | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x8000)
    flash.poke16w(0x0004, 0x0901)
    flash.poke16w(0x0005, 0x2400)
    flash.poke16w(0x0006, 0x3403)
    flash.poke16w(0x0007, 0x0A11)
    flash.poke16w(0x0008, 0x3F11)
    flash.poke16w(0x0009, 0x3D02)
    flash.poke16w(0x000A, 0x0A15)
    flash.poke16w(0x000B, 0x3F11)
    flash.poke16w(0x000C, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(9)
    assert dut.uo_out.value == 5, f"Expected 5 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_lsr_sets_carry(dut):
    dut._log.info("Starting LSR carry test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |       ; start:
    #  0:0 |    0 | 3d 02 ; jump main
    #  2:0 |    1 | 00 00 ; nop
    #  4:0 |    2 | 44 00 ; reti
    #  6:0 |    3 |       ; main:
    #  6:0 |    3 | 0a 01 ; ldi r0, 1
    #  8:0 |    4 | 25 00 ; lsr r0
    #  a:0 |    5 | 34 03 ; jumpCarry carry_label
    #  c:0 |    6 | 0a 11 ; ldi r1, 1
    #  e:0 |    7 | 3f 11 ; putoutput r1
    # 10:0 |    8 | 3d 02 ; jump forever
    # 12:0 |    9 |       ; carry_label:
    # 12:0 |    9 | 0a 14 ; ldi r1, 4
    # 14:0 |    a | 3f 11 ; putoutput r1
    # 16:0 |    b |       ; forever:
    # 16:0 |    b | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A01)
    flash.poke16w(0x0004, 0x2500)
    flash.poke16w(0x0005, 0x3403)
    flash.poke16w(0x0006, 0x0A11)
    flash.poke16w(0x0007, 0x3F11)
    flash.poke16w(0x0008, 0x3D02)
    flash.poke16w(0x0009, 0x0A14)
    flash.poke16w(0x000A, 0x3F11)
    flash.poke16w(0x000B, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(9)
    assert dut.uo_out.value == 4, f"Expected 4 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_rol_uses_carry(dut):
    dut._log.info("Starting ROL carry-use test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |       ; start:
    #  0:0 |    0 | 3d 02 ; jump main
    #  2:0 |    1 | 00 00 ; nop
    #  4:0 |    2 | 44 00 ; reti
    #  6:0 |    3 |       ; main:
    #  6:0 |    3 | 0a 20 ; ldi r2, 0
    #  8:0 |    4 | 10 21 ; sub r2, 1
    #  a:0 |    5 | 0a 00 ; ldi r0, 0
    #  c:0 |    6 | 26 00 ; rol r0
    #  e:0 |    7 | 3f 10 ; putoutput r0
    # 10:0 |    8 |       ; forever:
    # 10:0 |    8 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A20)
    flash.poke16w(0x0004, 0x1021)
    flash.poke16w(0x0005, 0x0A00)
    flash.poke16w(0x0006, 0x2600)
    flash.poke16w(0x0007, 0x3F10)
    flash.poke16w(0x0008, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(8)
    assert dut.uo_out.value == 1, f"Expected 1 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_ror_uses_carry(dut):
    dut._log.info("Starting ROR carry-use test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |       ; start:
    #  0:0 |    0 | 3d 02 ; jump main
    #  2:0 |    1 | 00 00 ; nop
    #  4:0 |    2 | 44 00 ; reti
    #  6:0 |    3 |       ; main:
    #  6:0 |    3 | 0a 20 ; ldi r2, 0
    #  8:0 |    4 | 10 21 ; sub r2, 1
    #  a:0 |    5 | 0a 00 ; ldi r0, 0
    #  c:0 |    6 | 27 00 ; ror r0
    #  e:0 |    7 | 36 03 ; jumpNegative neg_label
    # 10:0 |    8 | 0a 11 ; ldi r1, 1
    # 12:0 |    9 | 3f 11 ; putoutput r1
    # 14:0 |    a | 3d 02 ; jump forever
    # 16:0 |    b |       ; neg_label:
    # 16:0 |    b | 0a 13 ; ldi r1, 3
    # 18:0 |    c | 3f 11 ; putoutput r1
    # 1a:0 |    d |       ; forever:
    # 1a:0 |    d | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A20)
    flash.poke16w(0x0004, 0x1021)
    flash.poke16w(0x0005, 0x0A00)
    flash.poke16w(0x0006, 0x2700)
    flash.poke16w(0x0007, 0x3603)
    flash.poke16w(0x0008, 0x0A11)
    flash.poke16w(0x0009, 0x3F11)
    flash.poke16w(0x000A, 0x3D02)
    flash.poke16w(0x000B, 0x0A13)
    flash.poke16w(0x000C, 0x3F11)
    flash.poke16w(0x000D, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(10)
    assert dut.uo_out.value == 3, f"Expected 3 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_ldi_i16_positive(dut):
    dut._log.info("Starting LDI i16 positive test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 02       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; main:
    #  6:0 |    3 | 92 34 09 00 ; ldi r0, 0x1234
    #  a:0 |    5 | 3f 10       ; putoutput r0
    #  c:0 |    6 |             ; forever:
    #  c:0 |    6 | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x9234)
    flash.poke16w(0x0004, 0x0900)
    flash.poke16w(0x0005, 0x3F10)
    flash.poke16w(0x0006, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(6)
    assert dut.uo_out.value == 0x34, f"Expected 0x34 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_add_i16_negative(dut):
    dut._log.info("Starting ADD i16 negative test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 02       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; main:
    #  6:0 |    3 | 0a 05       ; ldi r0, 5
    #  8:0 |    4 | ff fe 0b 01 ; add r0, -2
    #  c:0 |    6 | 3f 10       ; putoutput r0
    #  e:0 |    7 |             ; forever:
    #  e:0 |    7 | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A05)
    flash.poke16w(0x0004, 0xFFFE)
    flash.poke16w(0x0005, 0x0B01)
    flash.poke16w(0x0006, 0x3F10)
    flash.poke16w(0x0007, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(6)
    assert dut.uo_out.value == 3, f"Expected 3 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_countdown_loop(dut):
    dut._log.info("Starting countdown loop test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |       ; start:
    #  0:0 |    0 | 3d 02 ; jump main
    #  2:0 |    1 | 00 00 ; nop
    #  4:0 |    2 | 44 00 ; reti
    #  6:0 |    3 |       ; main:
    #  6:0 |    3 | 0a 05 ; ldi r0, 5
    #  8:0 |    4 |       ; loop:
    #  8:0 |    4 | 10 01 ; sub r0, 1
    #  a:0 |    5 | 38 fe ; jumpNotZero loop
    #  c:0 |    6 | 3f 10 ; putoutput r0
    #  e:0 |    7 |       ; forever:
    #  e:0 |    7 | 3d ff ; jump foreve

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A05)
    flash.poke16w(0x0004, 0x1001)
    flash.poke16w(0x0005, 0x38FE)
    flash.poke16w(0x0006, 0x3F10)
    flash.poke16w(0x0007, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(20)
    assert dut.uo_out.value == 0, f"Expected 0 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_mem_addr_zero(dut):
    dut._log.info("Starting RAM addr 0 test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 02       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; main:
    #  6:0 |    3 | 80 44 09 00 ; ldi r0, 0x44
    #  a:0 |    5 | 2e 00       ; st  0x0000, r0
    #  c:0 |    6 | 30 10       ; ld  r1, 0x0000
    #  e:0 |    7 | 3f 11       ; putoutput r1
    # 10:0 |    8 |             ; forever:
    # 10:0 |    8 | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x8044)
    flash.poke16w(0x0004, 0x0900)
    flash.poke16w(0x0005, 0x2E00)
    flash.poke16w(0x0006, 0x3010)
    flash.poke16w(0x0007, 0x3F11)
    flash.poke16w(0x0008, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(7)
    assert dut.uo_out.value == 0x44, f"Expected 0x44 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_mem_high_addr(dut):
    dut._log.info("Starting RAM high address test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 02       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; main:
    #  6:0 |    3 | 80 66 09 00 ; ldi r0, 0x66
    #  a:0 |    5 | ff ff 2d 10 ; st  0xFFFF, r0
    #  e:0 |    7 | ff ff 2f 11 ; ld  r1, 0xFFFF
    # 12:0 |    9 | 3f 11       ; putoutput r1
    # 14:0 |    a |             ; forever:
    # 14:0 |    a | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x8066)
    flash.poke16w(0x0004, 0x0900)
    flash.poke16w(0x0005, 0xFFFF)
    flash.poke16w(0x0006, 0x2D10)
    flash.poke16w(0x0007, 0xFFFF)
    flash.poke16w(0x0008, 0x2F11)
    flash.poke16w(0x0009, 0x3F11)
    flash.poke16w(0x000A, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(7)
    assert dut.uo_out.value == 0x66, f"Expected 0x66 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_reset_restarts_program(dut):
    dut._log.info("Starting reset restart test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |       ; start:
    #  0:0 |    0 | 3d 02 ; jump main
    #  2:0 |    1 | 00 00 ; nop
    #  4:0 |    2 | 44 00 ; reti
    #  6:0 |    3 |       ; main:
    #  6:0 |    3 | 0a 09 ; ldi r0, 9
    #  8:0 |    4 | 3f 10 ; putoutput r0
    #  a:0 |    5 |       ; forever:
    #  a:0 |    5 | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0a09)
    flash.poke16w(0x0004, 0x3F10)
    flash.poke16w(0x0005, 0x3DFF)


    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(6)
    assert dut.uo_out.value == 9, f"Expected 9 but got {dut.uo_out.value}"

    await reset_dut(dut)
    await flash.wait_instructions(6)
    assert dut.uo_out.value == 9, f"Expected 9 after reset but got {dut.uo_out.value}"



@cocotb.test()
async def test_cpu_push_pop_basic(dut):
    dut._log.info("Starting PUSH/POP basic test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 02       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; main:
    #  6:0 |    3 | 81 00 09 e0 ; ldi SP, 0x0100
    #  a:0 |    5 | 80 34 09 00 ; ldi r0, 0x34
    #  e:0 |    7 | 10 e1 2b e0 ; push r0
    # 12:0 |    9 | 0a 00       ; zero r0
    # 14:0 |    a | 2c 1e 0c e1 ; pop r1
    # 18:0 |    c | 3f 11       ; putoutput r1
    # 1a:0 |    d |             ; forever:
    # 1a:0 |    d | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D02)       
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x8100)
    flash.poke16w(0x0004, 0x09E0)
    flash.poke16w(0x0005, 0x8034)
    flash.poke16w(0x0006, 0x0900)
    flash.poke16w(0x0007, 0x10E1)
    flash.poke16w(0x0008, 0x2BE0)
    flash.poke16w(0x0009, 0x0A00)
    flash.poke16w(0x000A, 0x2C1E)
    flash.poke16w(0x000B, 0x0CE1)
    flash.poke16w(0x000C, 0x3F11)
    flash.poke16w(0x000D, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(10)
    assert dut.uo_out.value == 0x34, f"Expected 0x34 but got {dut.uo_out.value}"



@cocotb.test()
async def test_cpu_push_pop_lifo(dut):
    dut._log.info("Starting PUSH/POP LIFO test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 02       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; main:
    #  6:0 |    3 | ff ff 09 e1 ; ldi SP, 0xffff
    #  a:0 |    5 | 80 11 09 00 ; ldi r0, 0x11
    #  e:0 |    7 | 80 22 09 10 ; ldi r1, 0x22
    # 12:0 |    9 | 80 10 09 20 ; ldi r2 , 0x10
    # 16:0 |    b | 10 e1 2b e0 ; push r0
    # 1a:0 |    d | 10 e1 2b e1 ; push r1
    # 1e:0 |    f | 2c 2e 0c e1 ; pop r2
    # 22:0 |   11 | 2c 3e 0c e1 ; pop r3
    # 26:0 |   13 | 3f 12       ; putoutput r2
    # 28:0 |   14 |             ; forever:
    # 28:0 |   14 | 80 14 3c 00 ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0xFFFF)
    flash.poke16w(0x0004, 0x09E1)
    flash.poke16w(0x0005, 0x8011)
    flash.poke16w(0x0006, 0x0900)
    flash.poke16w(0x0007, 0x8022)
    flash.poke16w(0x0008, 0x0910)
    flash.poke16w(0x0009, 0x8010)
    flash.poke16w(0x000A, 0x0920)
    flash.poke16w(0x000B, 0x10E1)
    flash.poke16w(0x000C, 0x2BE0)
    flash.poke16w(0x000D, 0x10E1)
    flash.poke16w(0x000E, 0x2BE1)
    flash.poke16w(0x000F, 0x2C2E)
    flash.poke16w(0x0010, 0x0CE1)
    flash.poke16w(0x0011, 0x2C3E)
    flash.poke16w(0x0012, 0x0CE1)
    flash.poke16w(0x0013, 0x3F12)
    flash.poke16w(0x0014, 0x8014)
    flash.poke16w(0x0015, 0x3C00)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(15)
    assert dut.uo_out.value == 0x22, f"Expected 0x22 but got {dut.uo_out.value}"



@cocotb.test()
async def test_cpu_push_pop_lifo_second_value(dut):
    dut._log.info("Starting PUSH/POP second value test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 02       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; main:
    #  6:0 |    3 | 81 00 09 e0 ; ldi SP, 0x0100
    #  a:0 |    5 | 80 11 09 00 ; ldi r0, 0x11
    #  e:0 |    7 | 80 22 09 10 ; ldi r1, 0x22
    # 12:0 |    9 | 10 e1 2b e0 ; push r0
    # 16:0 |    b | 10 e1 2b e1 ; push r1
    # 1a:0 |    d | 2c 2e 0c e1 ; pop r2
    # 1e:0 |    f | 2c 3e 0c e1 ; pop r3
    # 22:0 |   11 | 3f 13       ; putoutput r3
    # 24:0 |   12 |             ; forever:
    # 24:0 |   12 | 80 12 3c 00 ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x8100)
    flash.poke16w(0x0004, 0x09E0)
    flash.poke16w(0x0005, 0x8011)
    flash.poke16w(0x0006, 0x0900)
    flash.poke16w(0x0007, 0x8022)
    flash.poke16w(0x0008, 0x0910)
    flash.poke16w(0x0009, 0x10E1)
    flash.poke16w(0x000A, 0x2BE0)
    flash.poke16w(0x000B, 0x10E1)
    flash.poke16w(0x000C, 0x2BE1)
    flash.poke16w(0x000D, 0x2C2E)
    flash.poke16w(0x000E, 0x0CE1)
    flash.poke16w(0x000F, 0x2C3E)
    flash.poke16w(0x0010, 0x0CE1)
    flash.poke16w(0x0011, 0x3F13)
    flash.poke16w(0x0012, 0x8012)
    flash.poke16w(0x0013, 0x3C00)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(15)
    assert dut.uo_out.value == 0x11, f"Expected 0x11 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_rcall_rret_basic(dut):
    dut._log.info("Starting RCALL/RRET basic test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 05       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; func:
    #  6:0 |    3 | 80 55 09 00 ; ldi r0, 0x55
    #  a:0 |    5 | 3b 0f       ; rret RA
    #  c:0 |    6 |             ; main:
    #  c:0 |    6 | 80 03 3a f0 ; rcall RA, func
    # 10:0 |    8 | 3f 10       ; putoutput r0
    # 12:0 |    9 |             ; forever:
    # 12:0 |    9 | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D05)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x8055)
    flash.poke16w(0x0004, 0x0900)
    flash.poke16w(0x0005, 0x3B0F)
    flash.poke16w(0x0006, 0x8003)
    flash.poke16w(0x0007, 0x3AF0)
    flash.poke16w(0x0008, 0x3F10)
    flash.poke16w(0x0009, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(9)
    assert dut.uo_out.value == 0x55, f"Expected 0x55 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_call_macro_basic(dut):
    dut._log.info("Starting CALL macro test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 07       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; func:
    #  6:0 |    3 | 80 66 09 00 ; ldi r0, 0x66
    #  a:0 |    5 | 2c fe 0c e1 3b 0f ; ret 0
    # 10:0 |    8 |             ; main:
    # 10:0 |    8 | 81 00 09 e0 ; ldi SP, 0x0100
    # 14:0 |    a | 10 e1 80 10 09 f0 2b ef 80 03 3c 00 ; call func
    # 20:0 |   10 | 3f 10       ; putoutput r0
    # 22:0 |   11 |             ; forever:
    # 22:0 |   11 | 80 11 3c 00 ; jump forever

    flash.poke16w(0x0000, 0x3D07)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x8066)
    flash.poke16w(0x0004, 0x0900)
    flash.poke16w(0x0005, 0x2CFE)
    flash.poke16w(0x0006, 0x0CE1)
    flash.poke16w(0x0007, 0x3B0F)
    flash.poke16w(0x0008, 0x8100)
    flash.poke16w(0x0009, 0x09E0)
    flash.poke16w(0x000A, 0x10E1)
    flash.poke16w(0x000B, 0x8010)
    flash.poke16w(0x000C, 0x09F0)
    flash.poke16w(0x000D, 0x2BEF)
    flash.poke16w(0x000E, 0x8003)
    flash.poke16w(0x000F, 0x3C00)
    flash.poke16w(0x0010, 0x3F10)
    flash.poke16w(0x0011, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(12)
    assert dut.uo_out.value == 0x66, f"Expected 0x66 but got {dut.uo_out.value}"

@cocotb.test()
async def test_cpu_call_ret_cleanup(dut):
    dut._log.info("Starting CALL/RET cleanup test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 07       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; func:
    #  6:0 |    3 | 80 44 09 00 ; ldi r0, 0x44
    #  a:0 |    5 | 2c fe 0c e2 3b 0f ; ret 1
    # 10:0 |    8 |             ; main:
    # 10:0 |    8 | 81 00 09 e0 ; ldi SP, 0x0100
    # 14:0 |    a | 10 e1 2b e2 ; push r2
    # 18:0 |    c | 10 e1 80 12 09 f0 2b ef 80 03 3c 00 ; call func
    # 24:0 |   12 | 10 e1 2b e0 ; push r0
    # 28:0 |   14 | 2c 1e 0c e1 ; pop r1
    # 2c:0 |   16 | 3f 11       ; putoutput r1
    # 2e:0 |   17 |             ; forever:
    # 2e:0 |   17 | 80 17 3c 00 ; jump forever

    flash.poke16w(0x0000, 0x3D07)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x8044)
    flash.poke16w(0x0004, 0x0900)
    flash.poke16w(0x0005, 0x2CFE)
    flash.poke16w(0x0006, 0x0CE2)
    flash.poke16w(0x0007, 0x3B0F)
    flash.poke16w(0x0008, 0x8100)
    flash.poke16w(0x0009, 0x09E0)
    flash.poke16w(0x000A, 0x10E1)
    flash.poke16w(0x000B, 0x8012)
    flash.poke16w(0x000C, 0x09F0)
    flash.poke16w(0x000D, 0x2BEF)
    flash.poke16w(0x000E, 0x8003)
    flash.poke16w(0x000F, 0x3C00)
    flash.poke16w(0x0010, 0x10E1)
    flash.poke16w(0x0011, 0x2BE0)
    flash.poke16w(0x0012, 0x2C1E)
    flash.poke16w(0x0013, 0x0CE1)
    flash.poke16w(0x0014, 0x3F11)
    flash.poke16w(0x0015, 0x8017)
    flash.poke16w(0x0016, 0x3C00)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(15)
    assert dut.uo_out.value == 0x44, f"Expected 0x44 but got {dut.uo_out.value}"

@cocotb.test()
async def test_cpu_enter_leave_basic(dut):
    dut._log.info("Starting ENTER/LEAVE basic test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 80 10 3c 00 ; jump main
    #  4:0 |    2 | 00 00       ; nop
    #  6:0 |    3 | 44 00       ; reti
    #  8:0 |    4 |             ; func:
    #  8:0 |    4 | 10 e1 2b ed 01 de 10 e2 ; enter 2
    # 10:0 |    8 | 80 21 09 00 ; ldi r0, 0x21
    # 14:0 |    a | 01 ed 2c de 0c e1 ; leave
    # 1a:0 |    d | 2c fe 0c e1 3b 0f ; ret 0
    # 20:0 |   10 |             ; main:
    # 20:0 |   10 | 81 00 09 e0 ; ldi SP, 0x0100
    # 24:0 |   12 | 10 e1 80 18 09 f0 2b ef 80 04 3c 00 ; call func
    # 30:0 |   18 | 3f 10       ; putoutput r0
    # 32:0 |   19 |             ; forever:
    # 32:0 |   19 | 80 19 3c 00 ; jump forever

    flash.poke16w(0x0000, 0x8010)
    flash.poke16w(0x0001, 0x3C00)
    flash.poke16w(0x0002, 0x0000)
    flash.poke16w(0x0003, 0x4400)
    flash.poke16w(0x0004, 0x10E1)
    flash.poke16w(0x0005, 0x2BED)
    flash.poke16w(0x0006, 0x01DE)
    flash.poke16w(0x0007, 0x10E2)
    flash.poke16w(0x0008, 0x8021)
    flash.poke16w(0x0009, 0x0900)
    flash.poke16w(0x000A, 0x01ED)
    flash.poke16w(0x000B, 0x2CDE)
    flash.poke16w(0x000C, 0x0CE1)
    flash.poke16w(0x000D, 0x2CFE)
    flash.poke16w(0x000E, 0x0CE1)
    flash.poke16w(0x000F, 0x3B0F)
    flash.poke16w(0x0010, 0x8100)
    flash.poke16w(0x0011, 0x09E0)
    flash.poke16w(0x0012, 0x10E1)
    flash.poke16w(0x0013, 0x8018)
    flash.poke16w(0x0014, 0x09F0)
    flash.poke16w(0x0015, 0x2BEF)
    flash.poke16w(0x0016, 0x8004)
    flash.poke16w(0x0017, 0x3C00)
    flash.poke16w(0x0018, 0x3F10)
    flash.poke16w(0x0019, 0x8019)
    flash.poke16w(0x001A, 0x3C00)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(30)
    assert dut.uo_out.value == 0x21, f"Expected 0x21 but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_enter_leave_restores_stack(dut):
    dut._log.info("Starting ENTER/LEAVE stack-restore test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |                                     ; start:
    #  0:0 |    0 | 80 10 3c 00                         ; jump main
    #  4:0 |    2 | 00 00                               ; nop
    #  6:0 |    3 | 44 00                               ; reti
    #  8:0 |    4 |                                     ; func:
    #  8:0 |    4 | 10 e1 2b ed 01 de 10 e3             ; enter 3
    # 10:0 |    8 | 80 77 09 00                         ; ldi r0, 0x77
    # 14:0 |    a | 01 ed 2c de 0c e1                   ; leave
    # 1a:0 |    d | 2c fe 0c e1 3b 0f                   ; ret 0
    # 20:0 |   10 |                                     ; main:
    # 20:0 |   10 | 81 00 09 e0                         ; ldi SP, 0x0100
    # 24:0 |   12 | 80 12 09 10                         ; ldi r1, 0x12
    # 28:0 |   14 | 10 e1 2b e1                         ; push r1
    # 2c:0 |   16 | 10 e1 80 1c 09 f0 2b ef 80 04 3c 00 ; call func
    # 38:0 |   1c | 2c 2e 0c e1                         ; pop r2
    # 3c:0 |   1e | 3f 12                               ; putoutput r2
    # 3e:0 |   1f |                                     ; forever:
    # 3e:0 |   1f | 80 1f 3c 00                         ; jump forever

    flash.poke16w(0x0000, 0x8010)
    flash.poke16w(0x0001, 0x3C00)
    flash.poke16w(0x0002, 0x0000)
    flash.poke16w(0x0003, 0x4400)
    flash.poke16w(0x0004, 0x10E1)
    flash.poke16w(0x0005, 0x2BED)
    flash.poke16w(0x0006, 0x01DE)
    flash.poke16w(0x0007, 0x10E3)
    flash.poke16w(0x0008, 0x8077)
    flash.poke16w(0x0009, 0x0900)
    flash.poke16w(0x000A, 0x01ED)
    flash.poke16w(0x000B, 0x2CDE)
    flash.poke16w(0x000C, 0x0CE1)
    flash.poke16w(0x000D, 0x2CFE)
    flash.poke16w(0x000E, 0x0CE1)
    flash.poke16w(0x000F, 0x3B0F)
    flash.poke16w(0x0010, 0x8100)
    flash.poke16w(0x0011, 0x09E0)
    flash.poke16w(0x0012, 0x8012)
    flash.poke16w(0x0013, 0x0910)
    flash.poke16w(0x0014, 0x10E1)
    flash.poke16w(0x0015, 0x801C)
    flash.poke16w(0x0016, 0x09F0)
    flash.poke16w(0x0017, 0x2BEF)
    flash.poke16w(0x0018, 0x8004)
    flash.poke16w(0x0019, 0x3C00)
    flash.poke16w(0x001A, 0x2C2E)
    flash.poke16w(0x001B, 0x0CE1)
    flash.poke16w(0x001C, 0x3F12)
    flash.poke16w(0x001D, 0x3dff)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(35)
    assert dut.uo_out.value == 0x12, f"Expected 0x12 but got {dut.uo_out.value}"

@cocotb.test()
async def test_cpu_bp_local_access_style(dut):
    dut._log.info("Starting BP local access style test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 80 15 3c 00 ; jump main
    #  4:0 |    2 | 00 00       ; nop
    #  6:0 |    3 | 44 00       ; reti
    #  8:0 |    4 |             ; func:
    #  8:0 |    4 | 10 e1 2b ed 01 de 10 e2 ; enter 2
    # 10:0 |    8 | 80 5a 09 00 ; ldi r0, 0x5A
    # 14:0 |    a | ff ff 31 d0 ; st  [BP - 1], r0
    # 18:0 |    c | ff ff 32 1d ; ld  r1, [BP - 1]
    # 1c:0 |    e | 3f 11       ; putoutput r1
    # 1e:0 |    f | 01 ed 2c de 0c e1 ; leave
    # 24:0 |   12 | 2c fe 0c e1 3b 0f ; ret 0
    # 2a:0 |   15 |             ; main:
    # 2a:0 |   15 | 81 00 09 e0 ; ldi SP, 0x0100
    # 2e:0 |   17 | 10 e1 80 1d 09 f0 2b ef 80 04 3c 00 ; call func
    # 3a:0 |   1d |             ; forever:
    # 3a:0 |   1d | 80 1d 3c 00 ; jump forever

    flash.poke16w(0x0000, 0x8015)
    flash.poke16w(0x0001, 0x3C00)
    flash.poke16w(0x0002, 0x0000)
    flash.poke16w(0x0003, 0x4400)
    flash.poke16w(0x0004, 0x10E1)
    flash.poke16w(0x0005, 0x2BED)
    flash.poke16w(0x0006, 0x01DE)
    flash.poke16w(0x0007, 0x10E2)
    flash.poke16w(0x0008, 0x805A)
    flash.poke16w(0x0009, 0x0900)
    flash.poke16w(0x000A, 0xFFFF)
    flash.poke16w(0x000B, 0x31D0)
    flash.poke16w(0x000C, 0xFFFF)
    flash.poke16w(0x000D, 0x321D)
    flash.poke16w(0x000E, 0x3F11)
    flash.poke16w(0x000F, 0x01ED)
    flash.poke16w(0x0010, 0x2CDE)
    flash.poke16w(0x0011, 0x0CE1)
    flash.poke16w(0x0012, 0x2CFE)
    flash.poke16w(0x0013, 0x0CE1)
    flash.poke16w(0x0014, 0x3B0F)
    flash.poke16w(0x0015, 0x8100)
    flash.poke16w(0x0016, 0x09E0)
    flash.poke16w(0x0017, 0x10E1)
    flash.poke16w(0x0018, 0x801D)
    flash.poke16w(0x0019, 0x09F0)
    flash.poke16w(0x001A, 0x2BEF)
    flash.poke16w(0x001B, 0x8004)
    flash.poke16w(0x001C, 0x3C00)
    flash.poke16w(0x001D, 0x801D)
    flash.poke16w(0x001E, 0x3C00)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(30)
    assert dut.uo_out.value == 0x5A, f"Expected 0x5A but got {dut.uo_out.value}"


@cocotb.test()
async def test_cpu_scall_macro(dut):
    dut._log.info("Starting _SCALL macro test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 05       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; func:
    #  6:0 |    3 | 80 2b 09 00 ; ldi r0, 0x2B
    #  a:0 |    5 | 3b 0f       ; rret RA
    #  c:0 |    6 |             ; main:
    #  c:0 |    6 | 81 00 09 e0 ; ldi SP, 0x0100
    # 10:0 |    8 | 10 e1 2b ef 80 03 3a f0 2c fe 0c e1 ; _scall func
    # 1c:0 |    e | 3f 10       ; putoutput r0
    # 1e:0 |    f |             ; forever:
    # 1e:0 |    f | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D05)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x802B)
    flash.poke16w(0x0004, 0x0900)
    flash.poke16w(0x0005, 0x3B0F)
    flash.poke16w(0x0006, 0x8100)
    flash.poke16w(0x0007, 0x09E0)
    flash.poke16w(0x0008, 0x10E1)
    flash.poke16w(0x0009, 0x2BEF)
    flash.poke16w(0x000A, 0x8003)
    flash.poke16w(0x000B, 0x3AF0)
    flash.poke16w(0x000C, 0x2CFE)
    flash.poke16w(0x000D, 0x0CE1)
    flash.poke16w(0x000E, 0x3F10)
    flash.poke16w(0x000F, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(20)
    assert dut.uo_out.value == 0x2B, f"Expected 0x2B but got {dut.uo_out.value}"

@cocotb.test()
async def test_cpu_push_writes_stack_memory(dut):
    dut._log.info("Starting PUSH RAM write test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |             ; start:
    #  0:0 |    0 | 3d 02       ; jump main
    #  2:0 |    1 | 00 00       ; nop
    #  4:0 |    2 | 44 00       ; reti
    #  6:0 |    3 |             ; main:
    #  6:0 |    3 | 81 00 09 e0 ; ldi SP, 0x0100
    #  a:0 |    5 | 80 4d 09 00 ; ldi r0, 0x4D
    #  e:0 |    7 | 10 e1 2b e0 ; push r0
    # 12:0 |    9 | 3f 10       ; putoutput r0
    # 14:0 |    a |             ; forever:
    # 14:0 |    a | 3d ff       ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x8100)
    flash.poke16w(0x0004, 0x09E0)
    flash.poke16w(0x0005, 0x804D)
    flash.poke16w(0x0006, 0x0900)
    flash.poke16w(0x0007, 0x10E1)
    flash.poke16w(0x0008, 0x2BE0)
    flash.poke16w(0x0009, 0x3F10)
    flash.poke16w(0x000A, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(8)

    assert dut.uo_out.value == 0x4D, f"Expected 0x4D but got {dut.uo_out.value}"
    # Optional: check actual RAM slot if you know exact post-decrement behavior
    # assert ram.peek16w(0x00FF) == 0x004D

@cocotb.test()
async def test_cpu_rng_seed_and_read(dut):
    dut._log.info("Starting RNG seed/read test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |                      ; start:
    #  0:0 |    0 | 3d 02                ; jump main
    #  2:0 |    1 | 00 00                ; nop
    #  4:0 |    2 | 44 00                ; reti
    #  6:0 |    3 |                      ; main:
    #  6:0 |    3 | 92 34 09 c0 3f bc    ; RandomSeed 0x1234
    #  c:0 |    6 | 42 0c                ; in  r0, RandomReg
    #  e:0 |    7 | 3f 10                ; putoutput r0
    # 10:0 |    8 |                      ; forever:
    # 10:0 |    8 | 3d ff                ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x9234)
    flash.poke16w(0x0004, 0x09C0)
    flash.poke16w(0x0005, 0x3FBC)
    flash.poke16w(0x0006, 0x420C)
    flash.poke16w(0x0007, 0x3F10)
    flash.poke16w(0x0008, 0x3DFF)
    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(7)
    cocotb.log.info(f"RNG output: {int(dut.uo_out.value):04X}")
    assert int(dut.uo_out.value) > 0

@cocotb.test()
async def test_cpu_rng_changes(dut):
    dut._log.info("Starting RNG change test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |       ; start:
    #  0:0 |    0 | 3d 02 ; jump main
    #  2:0 |    1 | 00 00 ; nop
    #  4:0 |    2 | 44 00 ; reti
    #  6:0 |    3 |       ; main:
    #  6:0 |    3 | 92 34 09 c0 3f bc ; RandomSeed 0x1234
    #  c:0 |    6 | 42 0c ; in  r0, RandomReg
    #  e:0 |    7 | 42 1c ; in  r1, RandomReg
    # 10:0 |    8 | 08 01 ; xor r0, r1
    # 12:0 |    9 | 3f 10 ; putoutput r0
    # 14:0 |    a |       ; forever:
    # 14:0 |    a | 3d ff ; jump forever

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x9234)
    flash.poke16w(0x0004, 0x09C0)
    flash.poke16w(0x0005, 0x3FBC)
    flash.poke16w(0x0006, 0x420C)
    flash.poke16w(0x0007, 0x421C)
    flash.poke16w(0x0008, 0x0801)
    flash.poke16w(0x0009, 0x3F10)
    flash.poke16w(0x000A, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(9)
    assert dut.uo_out.value != 0, "Expected RNG values to differ"

@cocotb.test()
async def test_cpu_timer1_poll_basic(dut):
    dut._log.info("Starting timer1 poll test")
    pins, flash, ram = await boot_cpu(dut)
    flash.trace_fetch = True

    #  0:0 |    0 |       ; start:
    #  0:0 |    0 | 3d 02 ; jump main
    #  2:0 |    1 | 00 00 ; nop
    #  4:0 |    2 | 44 00 ; reti
    #  6:0 |    3 |       ; main:
    #  6:0 |    3 | 0a 01 ; ldi r0, 1
    #  8:0 |    4 | 3f 20 ; out timer1Config, r0
    #  a:0 |    5 |       ; poll:
    #  a:0 |    5 | 42 15 ; in  r1, timer1ReadAdr
    #  c:0 |    6 | 21 13 ; cmp r1, 3
    #  e:0 |    7 | 38 fd ; jumpNotZero poll
    # 10:0 |    8 | 3f 11 ; putoutput r1
    # 12:0 |    9 |       ; forever:
    # 12:0 |    9 | 3d ff ; jump forever
    #
    # Expect:
    #   eventually uo_out = 3

    flash.poke16w(0x0000, 0x3D02)
    flash.poke16w(0x0001, 0x0000)
    flash.poke16w(0x0002, 0x4400)
    flash.poke16w(0x0003, 0x0A01)
    flash.poke16w(0x0004, 0x3F20)
    flash.poke16w(0x0005, 0x4215)
    flash.poke16w(0x0006, 0x2113)
    flash.poke16w(0x0007, 0x38FD)
    flash.poke16w(0x0008, 0x3F11)
    flash.poke16w(0x0009, 0x3DFF)

    cocotb.start_soon(flash.run())
    cocotb.start_soon(ram.run())
    await reset_dut(dut)

    await flash.wait_instructions(40)
    assert dut.uo_out.value == 3, f"Expected 3 but got {dut.uo_out.value}"


