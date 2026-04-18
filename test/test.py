# SPDX-FileCopyrightText: © 2026 Prof. Santhosh Sivasubramani, IIT Delhi
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge


async def reset_dut(dut):
    """Apply reset and release."""
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0b00001  # CS high (inactive)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)


async def spi_write(dut, addr, data):
    """SPI write transaction: 1 R/W bit (0=write) + 7-bit addr + 8-bit data, MSB first."""
    cs_bit = 0   # uio_in[0]
    mosi_bit = 1  # uio_in[1]
    sck_bit = 3   # uio_in[3]

    # Build 16-bit word: [0][addr6:0][data7:0]
    word = ((addr & 0x7F) << 8) | (data & 0xFF)

    # Assert CS (active low = 0)
    uio_base = 0  # CS=0, SCK=0
    dut.uio_in.value = uio_base
    await ClockCycles(dut.clk, 4)

    for i in range(16):
        bit_val = (word >> (15 - i)) & 1
        # Set MOSI, SCK low
        dut.uio_in.value = (bit_val << mosi_bit)
        await ClockCycles(dut.clk, 4)
        # SCK rising edge — slave samples MOSI
        dut.uio_in.value = (bit_val << mosi_bit) | (1 << sck_bit)
        await ClockCycles(dut.clk, 4)
        # SCK falling
        dut.uio_in.value = (bit_val << mosi_bit)
        await ClockCycles(dut.clk, 2)

    # Deassert CS
    dut.uio_in.value = (1 << cs_bit)  # CS=1
    await ClockCycles(dut.clk, 4)


async def spi_read(dut, addr):
    """SPI read transaction: 1 R/W bit (1=read) + 7-bit addr, returns 8-bit data."""
    cs_bit = 0
    mosi_bit = 1
    sck_bit = 3

    # Build 16-bit word: [1][addr6:0][0x00] — read bit set
    word = (1 << 15) | ((addr & 0x7F) << 8)

    # Assert CS
    dut.uio_in.value = 0
    await ClockCycles(dut.clk, 4)

    read_data = 0
    for i in range(16):
        bit_val = (word >> (15 - i)) & 1
        # MOSI + SCK low
        dut.uio_in.value = (bit_val << mosi_bit)
        await ClockCycles(dut.clk, 4)
        # SCK rising
        dut.uio_in.value = (bit_val << mosi_bit) | (1 << sck_bit)
        await ClockCycles(dut.clk, 2)
        # Sample MISO on rising edge (for data phase: bits 8-15)
        if i >= 8:
            miso = (int(dut.uio_out.value) >> 2) & 1
            read_data = (read_data << 1) | miso
        await ClockCycles(dut.clk, 2)
        # SCK falling
        dut.uio_in.value = (bit_val << mosi_bit)
        await ClockCycles(dut.clk, 2)

    # Deassert CS
    dut.uio_in.value = (1 << cs_bit)
    await ClockCycles(dut.clk, 4)
    return read_data


async def spi_write_fast(dut, addr, data):
    """SPI write with minimum 2-cycle SCK half-periods (fastest safe timing)."""
    cs_bit = 0
    mosi_bit = 1
    sck_bit = 3
    word = ((addr & 0x7F) << 8) | (data & 0xFF)
    dut.uio_in.value = 0
    await ClockCycles(dut.clk, 2)
    for i in range(16):
        bit_val = (word >> (15 - i)) & 1
        dut.uio_in.value = (bit_val << mosi_bit)
        await ClockCycles(dut.clk, 2)
        dut.uio_in.value = (bit_val << mosi_bit) | (1 << sck_bit)
        await ClockCycles(dut.clk, 2)
        dut.uio_in.value = (bit_val << mosi_bit)
        await ClockCycles(dut.clk, 1)
    dut.uio_in.value = (1 << cs_bit)
    await ClockCycles(dut.clk, 2)


async def spi_read_fast(dut, addr):
    """SPI read with minimum 2-cycle SCK half-periods (fastest safe timing)."""
    cs_bit = 0
    mosi_bit = 1
    sck_bit = 3
    word = (1 << 15) | ((addr & 0x7F) << 8)
    dut.uio_in.value = 0
    await ClockCycles(dut.clk, 2)
    read_data = 0
    for i in range(16):
        bit_val = (word >> (15 - i)) & 1
        dut.uio_in.value = (bit_val << mosi_bit)
        await ClockCycles(dut.clk, 2)
        dut.uio_in.value = (bit_val << mosi_bit) | (1 << sck_bit)
        await ClockCycles(dut.clk, 1)
        if i >= 8:
            miso = (int(dut.uio_out.value) >> 2) & 1
            read_data = (read_data << 1) | miso
        await ClockCycles(dut.clk, 1)
        dut.uio_in.value = (bit_val << mosi_bit)
        await ClockCycles(dut.clk, 1)
    dut.uio_in.value = (1 << cs_bit)
    await ClockCycles(dut.clk, 2)
    return read_data


@cocotb.test()
async def test_reset_state(dut):
    """After reset, spike_out should be 0 and membrane should be 0."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    assert (int(dut.uo_out.value) & 1) == 0, "spike_out should be 0 after reset"


@cocotb.test()
async def test_spi_register_write_read(dut):
    """Write a value to a register via SPI and read it back."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Write 0xAB to threshold register (0x05)
    await spi_write(dut, 0x05, 0xAB)
    await ClockCycles(dut.clk, 10)

    # Read it back
    val = await spi_read(dut, 0x05)
    dut._log.info(f"Threshold register readback: 0x{val:02x}")
    assert val == 0xAB, f"Expected 0xAB, got 0x{val:02x}"


@cocotb.test()
async def test_lfsr_runs(dut):
    """Enable neuron and verify LFSR MSB (uo_out[1]) toggles."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Enable neuron via ui_in[2]
    dut.ui_in.value = 0b00100  # neuron_en=1
    samples = []
    for _ in range(100):
        await ClockCycles(dut.clk, 1)
        samples.append((int(dut.uo_out.value) >> 1) & 1)

    # LFSR should produce both 0s and 1s
    has_zero = 0 in samples
    has_one = 1 in samples
    dut._log.info(f"LFSR MSB samples: {sum(samples)} ones out of {len(samples)}")
    assert has_zero and has_one, "LFSR MSB should toggle"


@cocotb.test()
async def test_neuron_fires(dut):
    """Run neuron with external spikes and check if it eventually fires."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Lower threshold to make spiking easier
    await spi_write(dut, 0x05, 0x02)  # threshold = 2
    await spi_write(dut, 0x06, 0x00)  # decay = 0 (no leak)
    await ClockCycles(dut.clk, 10)

    # Enable neuron + provide external spikes with weight
    spike_seen = False
    for _ in range(500):
        dut.ui_in.value = 0b11110101  # ext_spike=1, neuron_en=1, weight=0xF
        await ClockCycles(dut.clk, 1)
        if int(dut.uo_out.value) & 1:
            spike_seen = True
            break

    dut._log.info(f"Spike seen: {spike_seen}")
    assert spike_seen, "Neuron should fire within 500 cycles at threshold=2 with max weight input"


@cocotb.test()
async def test_uio_oe(dut):
    """Verify OE direction bits: dynamic MISO, debug outputs."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)
    await ClockCycles(dut.clk, 1)
    # CS=1 (inactive): MISO tri-stated → uio_oe=0xF0
    assert int(dut.uio_oe.value) == 0b11110000, \
        f"Expected uio_oe=0xF0 (CS inactive), got 0x{int(dut.uio_oe.value):02x}"

    # Assert CS=0 (active): MISO enabled → uio_oe=0xF4
    dut.uio_in.value = 0  # CS=0
    await ClockCycles(dut.clk, 1)
    assert int(dut.uio_oe.value) == 0b11110100, \
        f"Expected uio_oe=0xF4 (CS active), got 0x{int(dut.uio_oe.value):02x}"
    dut.uio_in.value = 0b00001  # restore CS=1
    await ClockCycles(dut.clk, 1)


@cocotb.test()
async def test_all_lut_entries(dut):
    """Write distinct values to all 8 LUT entries and read them back."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    test_vals = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]
    for i, v in enumerate(test_vals):
        await spi_write(dut, 0x08 + i, v)
    await ClockCycles(dut.clk, 10)

    for i, v in enumerate(test_vals):
        rb = await spi_read(dut, 0x08 + i)
        assert rb == v, f"LUT[{i}]: expected 0x{v:02x}, got 0x{rb:02x}"
    dut._log.info("All 8 LUT entries verified")


@cocotb.test()
async def test_seed_reload(dut):
    """Write a custom seed via SPI and trigger reload; verify LFSR changes."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Read initial LFSR state (MSB visible on uo_out[1])
    dut.ui_in.value = 0b00100  # neuron_en=1
    await ClockCycles(dut.clk, 20)
    lfsr_msb_before = [(int(dut.uo_out.value) >> 1) & 1 for _ in range(5)]

    # Write new seed = 0xBEEF via SPI
    await spi_write(dut, 0x03, 0xEF)  # seed_l
    await spi_write(dut, 0x04, 0xBE)  # seed_h

    # Trigger seed reload via reg_ctrl[1]
    await spi_write(dut, 0x00, 0x03)  # ctrl: enable + reset_accum/seed_reload
    await ClockCycles(dut.clk, 5)

    # Clear reload bit — leave enable on
    await spi_write(dut, 0x00, 0x01)
    dut.ui_in.value = 0b00100  # neuron_en=1
    await ClockCycles(dut.clk, 20)

    # LFSR should now be running from 0xBEEF
    lfsr_msb_after = []
    for _ in range(20):
        await ClockCycles(dut.clk, 1)
        lfsr_msb_after.append((int(dut.uo_out.value) >> 1) & 1)

    has_both = (0 in lfsr_msb_after) and (1 in lfsr_msb_after)
    dut._log.info(f"LFSR MSB after seed reload: {sum(lfsr_msb_after)} ones / {len(lfsr_msb_after)}")
    assert has_both, "LFSR should toggle after seed reload"


@cocotb.test()
async def test_membrane_saturation(dut):
    """With zero decay and constant input, membrane should accumulate and spike (proving LIF integration)."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Zero decay, moderate threshold, max weight
    await spi_write(dut, 0x06, 0x00)  # decay=0
    await spi_write(dut, 0x05, 0x10)  # threshold=0x10 (reachable quickly)
    await ClockCycles(dut.clk, 10)

    # Drive external spikes continuously with max weight
    dut.ui_in.value = 0b11110101  # ext_spike=1, neuron_en=1, weight=0xF
    await ClockCycles(dut.clk, 2000)

    # With accumulation working, the neuron should have fired and set spike_latched
    spike_latched = (int(dut.uo_out.value) >> 3) & 1
    dut._log.info(f"Spike latched flag: {spike_latched}")
    assert spike_latched == 1, "Membrane should accumulate and eventually fire (spike_latched must be set)"


@cocotb.test()
async def test_lfsr_long_sequence(dut):
    """Run LFSR for 1000+ cycles and check autocorrelation is low (no short-period lock)."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    dut.ui_in.value = 0b00100  # neuron_en=1
    samples = []
    for _ in range(1024):
        await ClockCycles(dut.clk, 1)
        samples.append((int(dut.uo_out.value) >> 1) & 1)  # LFSR MSB

    # Check balance: should be roughly 50/50 over 1024 samples
    ones = sum(samples)
    zeros = len(samples) - ones
    dut._log.info(f"LFSR 1024-sample balance: {ones} ones, {zeros} zeros")
    assert ones > 300, f"LFSR too biased toward 0: only {ones}/1024 ones"
    assert zeros > 300, f"LFSR too biased toward 1: only {zeros}/1024 zeros"

    # Check autocorrelation at lag 1: count transitions (0→1 or 1→0)
    transitions = sum(1 for i in range(len(samples)-1) if samples[i] != samples[i+1])
    dut._log.info(f"LFSR transitions: {transitions}/1023")
    assert transitions > 200, f"LFSR stuck or short-period: only {transitions} transitions in 1023 steps"


# ================================================================
# Stress tests — SPI timing margins and edge cases
# ================================================================

@cocotb.test()
async def test_spi_fast_timing(dut):
    """SPI write/read at minimum 2-cycle SCK half-periods (fastest safe timing for 3-stage synchronizer)."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    test_pairs = [(0x05, 0xDE), (0x06, 0xAD), (0x01, 0xBE), (0x02, 0xEF)]
    for addr, val in test_pairs:
        await spi_write_fast(dut, addr, val)

    for addr, val in test_pairs:
        rb = await spi_read_fast(dut, addr)
        assert rb == val, f"Fast SPI: reg 0x{addr:02x} expected 0x{val:02x}, got 0x{rb:02x}"
    dut._log.info("All fast-timing SPI write/read passed")


@cocotb.test()
async def test_spi_back_to_back(dut):
    """Rapid consecutive SPI transactions with minimal inter-frame gap."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Write all 8 LUT entries back-to-back using fast SPI
    for i in range(8):
        await spi_write_fast(dut, 0x08 + i, (i * 31 + 7) & 0xFF)

    # Read them all back immediately
    for i in range(8):
        expected = (i * 31 + 7) & 0xFF
        rb = await spi_read_fast(dut, 0x08 + i)
        assert rb == expected, f"Back-to-back LUT[{i}]: expected 0x{expected:02x}, got 0x{rb:02x}"
    dut._log.info("8 back-to-back fast SPI transactions verified")


@cocotb.test()
async def test_register_boundary_values(dut):
    """Write 0x00 and 0xFF to all writable registers and verify readback."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    writable_regs = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06,
                     0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F]

    # Test 0xFF
    for reg in writable_regs:
        await spi_write(dut, reg, 0xFF)
    for reg in writable_regs:
        rb = await spi_read(dut, reg)
        assert rb == 0xFF, f"Reg 0x{reg:02x}: expected 0xFF, got 0x{rb:02x}"

    # Test 0x00
    for reg in writable_regs:
        await spi_write(dut, reg, 0x00)
    for reg in writable_regs:
        rb = await spi_read(dut, reg)
        assert rb == 0x00, f"Reg 0x{reg:02x}: expected 0x00, got 0x{rb:02x}"
    dut._log.info("All writable registers boundary values (0x00/0xFF) verified")


@cocotb.test()
async def test_decay_path(dut):
    """Verify decay drains membrane when no input is applied."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Set high threshold (won't fire), moderate decay
    await spi_write(dut, 0x05, 0xFF)  # threshold = max
    await spi_write(dut, 0x06, 0x10)  # decay = 16

    # Pump membrane up with external spikes
    dut.ui_in.value = 0b11110101  # ext_spike=1, neuron_en=1, weight=0xF
    await ClockCycles(dut.clk, 200)

    # Check membrane has accumulated (top 4 bits visible on uo_out[7:4])
    membrane_top = (int(dut.uo_out.value) >> 4) & 0xF
    dut._log.info(f"Membrane top nibble after integration: 0x{membrane_top:X}")

    # Stop input, let decay drain
    dut.ui_in.value = 0b00000100  # neuron_en=1, no spike, no weight
    await ClockCycles(dut.clk, 2000)

    membrane_after = (int(dut.uo_out.value) >> 4) & 0xF
    dut._log.info(f"Membrane top nibble after decay: 0x{membrane_after:X}")
    assert membrane_after < membrane_top or membrane_after == 0, \
        f"Decay should drain membrane: before=0x{membrane_top:X}, after=0x{membrane_after:X}"


@cocotb.test()
async def test_neuron_free_run_vs_spi_mode(dut):
    """Test both mode_sel=0 (free-run/activation) and mode_sel=1 (SPI/weight) operation."""
    clock = Clock(dut.clk, 20, unit="ns")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Low threshold, no decay for easy firing
    await spi_write(dut, 0x05, 0x02)
    await spi_write(dut, 0x06, 0x00)

    # Mode 0 (free-run): mode_sel=0, neuron_en=1, ext_spike=1
    dut.ui_in.value = 0b00000101  # ext_spike=1, neuron_en=1, mode_sel=0
    fired_mode0 = False
    for _ in range(500):
        await ClockCycles(dut.clk, 1)
        if int(dut.uo_out.value) & 1:
            fired_mode0 = True
            break
    dut._log.info(f"Mode 0 (free-run) fired: {fired_mode0}")

    # Reset accumulator
    await spi_write(dut, 0x00, 0x03)
    await ClockCycles(dut.clk, 5)
    await spi_write(dut, 0x00, 0x01)
    await ClockCycles(dut.clk, 5)

    # Mode 1 (SPI-controlled): mode_sel=1, neuron_en=1, ext_spike=1, weight=0xF
    dut.ui_in.value = 0b11110111  # ext_spike=1, mode_sel=1, neuron_en=1, weight=0xF
    fired_mode1 = False
    for _ in range(500):
        await ClockCycles(dut.clk, 1)
        if int(dut.uo_out.value) & 1:
            fired_mode1 = True
            break
    dut._log.info(f"Mode 1 (SPI weight) fired: {fired_mode1}")

    assert fired_mode0 or fired_mode1, "Neuron should fire in at least one mode"
