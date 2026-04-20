<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This design is a standalone stochastic leaky integrate-and-fire (sLIF) neuron with a 16-bit configurable-polynomial LFSR, an 8-entry programmable sigmoid activation LUT, a 16-bit leaky membrane accumulator, and a post-spike refractory period of 0–7 clock cycles. On every clock, the LFSR advances, the top 8 bits are compared against the sigmoid LUT output (indexed by a small slice of the membrane potential), and if the random number is below the activation value and the neuron is not in the refractory state, the input current (4-bit parallel `weight_in` plus an optional external `ext_spike`) is added to the accumulator. The accumulator also leaks by the 8-bit `reg_decay` each cycle. When the accumulator exceeds the 8-bit `reg_threshold`, `spike_out` asserts for one cycle, the accumulator resets, and the refractory counter loads with `reg_ctrl[7:5]` — suppressing further integration for that many cycles.

Two operating modes are supported: `mode_sel=0` (parallel / free-run) runs the neuron under the hard input controls `ext_spike` (`ui_in[0]`), `neuron_enable` (`ui_in[2]`), and `weight_in[3:0]` (`ui_in[7:4]`); `mode_sel=1` (SPI-controlled) moves the enable to the SPI `reg_ctrl[0]` bit and lets the user drive behavior entirely from the register file. A 16-bit SPI slave (Mode 0, MSB-first; CS=`uio_in[0]`, MOSI=`uio_in[1]`, MISO=`uio_out[2]`, SCK=`uio_in[3]`) exposes the registers: `reg_ctrl` (0x00: `[0]=enable`, `[1]=reset_accum`, `[2]=free_run`, `[7:5]=refractory_period`), `reg_poly_l/h` (0x01/0x02 — 16-bit LFSR tap polynomial), `reg_seed_l/h` (0x03/0x04 — 16-bit seed loaded on write), `reg_threshold` (0x05), `reg_decay` (0x06), read-only `reg_status` (0x07: spike flag, overflow, refractory active), and an 8-entry programmable sigmoid LUT at 0x08–0x0F.

Outputs: `spike_out` on `uo_out[0]`, LFSR MSB (`lfsr[15]`, a cheap randomness monitor) on `uo_out[1]`, `accum_overflow` (`membrane == 16'hFFFF`) on `uo_out[2]`, `threshold_flag` (latched spike) on `uo_out[3]`, and the top 4 bits of the membrane potential on `uo_out[7:4]` for on-chip / oscilloscope observation. Four debug taps are exposed on `uio_out[7:4]`: `neuron_en`, `stoch_fire`, `lfsr[5]`, and `lfsr[10]`.

## How to test

1. Apply reset (`rst_n` low, then release) and configure over SPI: write the LFSR polynomial (typically `0x002D` for a maximal-length 16-bit LFSR) to 0x01/0x02, a non-zero seed to 0x03/0x04, a threshold to 0x05 (e.g. `0x80`), a decay rate to 0x06 (e.g. `0x01`), and `reg_ctrl` with the desired refractory period in `[7:5]` (e.g. `0x41` = enable + 2-cycle refractory).
2. (Optional) Program the sigmoid LUT at 0x08–0x0F. The default curve provides a reasonable S-shape.
3. For parallel mode (`mode_sel=0`, `ui_in[1]=0`): drive `neuron_enable=1` on `ui_in[2]` and present a 4-bit weight on `ui_in[7:4]`; optionally pulse `ext_spike` on `ui_in[0]`.
4. For SPI mode (`mode_sel=1`): enable via `reg_ctrl[0]=1`; the neuron integrates internal state even without external signals.
5. Monitor `spike_out` (`uo_out[0]`), read `reg_status` (0x07) for current flags, and observe the membrane MSBs on `uo_out[7:4]` as a slow analog-like signal.
6. To induce faster firing, either raise the input weight, lower the threshold (0x05), or lower the LUT values (which raises the probability the random number is below them).

A cocotb suite (18 tests in `test/test.py`) covers reset, SPI register roundtrip, LFSR polynomial and seed programming, LUT writes, threshold crossing, membrane leak/decay, refractory-period enforcement, overflow flagging, and `uio_oe` direction control. All tests pass in RTL and post-synthesis gate-level simulation.

## External hardware

An SPI master (microcontroller or FPGA) on `uio[0:3]` is needed to configure the polynomial, seed, threshold, decay rate, refractory period, and LUT. An external spike source may drive `ui_in[0]` (`ext_spike`), and any 4-bit signal (e.g. a DAC digital word representing a pre-synaptic input or a small parallel bus) can drive `ui_in[7:4]` as the weight input. `spike_out` on `uo_out[0]` is the single-bit event output that feeds a downstream synapse, router, or counter; the membrane-MSB bus on `uo_out[7:4]` can be inspected directly or fed into an ADC/scope for state-of-health monitoring.
