![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg)

# LFSR-Based Stochastic Neuron

A digital stochastic neuron with a 16-bit configurable-polynomial LFSR, 8-entry programmable sigmoid activation LUT, and a leaky integrate-and-fire (LIF) model. All parameters are configurable via SPI. Targets the SkyWater 130 nm process node.

- [Detailed documentation](docs/info.md)

## Architecture

The LFSR generates pseudo-random numbers used for stochastic activation: the top 3 bits address the sigmoid LUT, and the lower 8 bits are compared against the LUT output. When the comparison passes (or an external spike arrives), the input current is integrated into a 16-bit membrane potential with saturation. Leak is applied every cycle. When the upper byte of the membrane exceeds the programmed threshold, a spike is emitted and the membrane resets.

## Key Features

- 16-bit LFSR with SPI-programmable polynomial and seed
- Zero-lock protection (LFSR cannot trap at all-zeros)
- 8-entry sigmoid LUT (registers 0x08-0x0F)
- 16-bit membrane with saturation (no wraparound)
- Configurable threshold and decay rate
- Parallel weight input on `ui_in[7:4]`
- SPI Mode 0 interface (CS, MOSI, SCK, MISO)

## Pin Summary

| Pin | Direction | Function |
|-----|-----------|----------|
| `ui_in[0]` | Input | External spike |
| `ui_in[1]` | Input | Mode select |
| `ui_in[2]` | Input | Neuron enable |
| `ui_in[7:4]` | Input | Parallel weight input |
| `uo_out[0]` | Output | Spike output |
| `uo_out[1]` | Output | LFSR MSB |
| `uo_out[7:4]` | Output | Membrane potential MSBs |
| `uio[0]` | Input | SPI CS |
| `uio[1]` | Input | SPI MOSI |
| `uio[2]` | Output | SPI MISO |
| `uio[3]` | Input | SPI SCK |

## Simulation

```bash
cd test
make
```

Requires cocotb and Icarus Verilog.

## Target

Tiny Tapeout [TTSKY26a](https://tinytapeout.com) shuttle, 1x1 tile, SkyWater 130 nm.
