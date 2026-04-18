<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This design implements a stochastic neuron with a 16-bit configurable LFSR for random number generation, an 8-entry programmable sigmoid activation LUT, and a 16-bit leaky integrate-and-fire (LIF) model. The LFSR polynomial, seed, threshold, and decay rate are all configurable via an SPI slave interface. In operation, the LFSR generates a random number which is compared against the sigmoid LUT output — if the random number is below the activation value, the neuron integrates the input current. When the membrane potential exceeds the threshold, a spike is emitted and the membrane resets.

## How to test

1. Apply reset and configure via SPI (CS=uio_in[0], MOSI=uio_in[1], SCK=uio_in[3], MISO=uio_out[2]).
2. Write LFSR polynomial (regs 0x01-0x02), seed (0x03-0x04), threshold (0x05), and decay rate (0x06).
3. Optionally program the sigmoid LUT (registers 0x08-0x0F).
4. Enable the neuron via ui_in[2] or CTRL register bit 0.
5. Provide external spikes on ui_in[0] and/or parallel weight on ui_in[7:4].
6. Monitor spike_out on uo_out[0], LFSR MSB on uo_out[1], and membrane potential MSBs on uo_out[7:4].

## External hardware

SPI master (microcontroller or FPGA) connected to uio_in[0] (CS), uio_in[1] (MOSI), uio_in[3] (SCK), and uio_out[2] (MISO). External spike source on ui_in[0].
