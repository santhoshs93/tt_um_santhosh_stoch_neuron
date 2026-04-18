/*
 * Copyright (c) 2026 Prof. Santhosh Sivasubramani, IIT Delhi
 * SPDX-License-Identifier: Apache-2.0
 *
 * LFSR-Based Stochastic Neuron
 * - 16-bit configurable-polynomial LFSR for random number generation
 * - 8-entry x 8-bit programmable sigmoid activation LUT
 * - 16-bit leaky integrator / accumulator
 * - SPI-configurable parameters (polynomial, seed, threshold, decay, LUT)
 * - Designed as standalone IP for spintronic/memristive device interfaces
 */

`default_nettype none

module tt_um_santhosh_stoch_neuron (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

    // ============================================================
    // Input assignments
    // ============================================================
    wire       ext_spike   = ui_in[0];     // External spike input
    wire       mode_sel    = ui_in[1];     // 0=free-run, 1=SPI-controlled
    wire       neuron_en   = ui_in[2];     // Neuron enable
    wire [3:0] weight_in   = ui_in[7:4];   // 4-bit parallel weight input

    // SPI signals
    wire spi_cs_n = uio_in[0];
    wire spi_mosi = uio_in[1];
    wire spi_miso;
    wire spi_sck  = uio_in[3];

    // ============================================================
    // SPI Slave & Register File
    // ============================================================
    wire        wr_en;
    wire [7:0]  wr_addr, wr_data, rd_addr;
    reg  [7:0]  rd_data;

    spi_slave #(.NUM_REGS(16)) u_spi (
        .clk      (clk),
        .rst_n    (rst_n),
        .spi_cs_n (spi_cs_n),
        .spi_mosi (spi_mosi),
        .spi_miso (spi_miso),
        .spi_sck  (spi_sck),
        .wr_en    (wr_en),
        .wr_addr  (wr_addr),
        .wr_data  (wr_data),
        .rd_addr  (rd_addr),
        .rd_data  (rd_data)
    );

    // Configuration registers
    reg [7:0] reg_ctrl;        // 0x00: [0]=enable, [1]=reset_accum, [2]=free_run
    reg [7:0] reg_poly_l;     // 0x01: LFSR polynomial [7:0]
    reg [7:0] reg_poly_h;     // 0x02: LFSR polynomial [15:8]
    reg [7:0] reg_seed_l;     // 0x03: LFSR seed [7:0]
    reg [7:0] reg_seed_h;     // 0x04: LFSR seed [15:8]
    reg [7:0] reg_threshold;  // 0x05: Spike threshold
    reg [7:0] reg_decay;      // 0x06: Decay rate
    wire [7:0] reg_status;     // 0x07: Status (read-only)

    // LUT storage: 8 entries x 8 bits = 64 bits (implemented as register file)
    reg [7:0] lut_mem [0:7]; // 0x08-0x0F

    // Register write logic
    integer j;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            reg_ctrl      <= 8'h01;
            reg_poly_l    <= 8'h2D;  // x^16+x^5+x^3+x^2+1 taps (maximal-length)
            reg_poly_h    <= 8'h00;
            reg_seed_l    <= 8'h01;
            reg_seed_h    <= 8'h00;
            reg_threshold <= 8'h80;
            reg_decay     <= 8'h04;
            // Default sigmoid approximation (8 points)
            lut_mem[0] <= 8'd16;
            lut_mem[1] <= 8'd32;
            lut_mem[2] <= 8'd64;
            lut_mem[3] <= 8'd128;
            lut_mem[4] <= 8'd192;
            lut_mem[5] <= 8'd224;
            lut_mem[6] <= 8'd240;
            lut_mem[7] <= 8'd248;
        end else if (wr_en) begin
            case (wr_addr)
                8'h00: reg_ctrl      <= wr_data;
                8'h01: reg_poly_l    <= wr_data;
                8'h02: reg_poly_h    <= wr_data;
                8'h03: reg_seed_l    <= wr_data;
                8'h04: reg_seed_h    <= wr_data;
                8'h05: reg_threshold <= wr_data;
                8'h06: reg_decay     <= wr_data;
                default: begin
                    if (wr_addr >= 8'h08 && wr_addr <= 8'h0F)
                        lut_mem[wr_addr[2:0]] <= wr_data;
                end
            endcase
        end
    end

    // Register read mux
    always @(*) begin
        case (rd_addr)
            8'h00: rd_data = reg_ctrl;
            8'h01: rd_data = reg_poly_l;
            8'h02: rd_data = reg_poly_h;
            8'h03: rd_data = reg_seed_l;
            8'h04: rd_data = reg_seed_h;
            8'h05: rd_data = reg_threshold;
            8'h06: rd_data = reg_decay;
            8'h07: rd_data = reg_status;
            default: begin
                if (rd_addr >= 8'h08 && rd_addr <= 8'h0F)
                    rd_data = lut_mem[rd_addr[2:0]];
                else
                    rd_data = 8'h00;
            end
        endcase
    end

    // ============================================================
    // 16-bit LFSR (Fibonacci, configurable polynomial)
    // ============================================================
    wire [15:0] lfsr_poly = {reg_poly_h, reg_poly_l};
    wire [15:0] lfsr_seed = {reg_seed_h, reg_seed_l};

    reg [15:0] lfsr;
    wire lfsr_feedback;

    // XOR selected taps based on polynomial register
    assign lfsr_feedback = ^(lfsr & lfsr_poly);

    wire lfsr_en = neuron_en || reg_ctrl[0];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            lfsr <= 16'h0001;
        end else if (reg_ctrl[1]) begin
            // Reload seed
            lfsr <= (lfsr_seed == 16'h0) ? 16'h0001 : lfsr_seed;
        end else if (lfsr_en) begin
            // Zero-lock protection: if LFSR reaches all-zero, re-seed
            if (lfsr == 16'h0000)
                lfsr <= 16'h0001;
            else
                lfsr <= {lfsr[14:0], lfsr_feedback};
        end
    end

    // ============================================================
    // Stochastic comparison & activation
    // ============================================================
    // Use top 3 bits of LFSR as LUT address
    wire [2:0] lut_addr = lfsr[15:13];
    wire [7:0] activation = lut_mem[lut_addr];

    // Stochastic comparison: fire if random < activation(input)
    wire stoch_fire = (lfsr[7:0] < activation);

    // ============================================================
    // Leaky Integrate-and-Fire
    // ============================================================
    reg [15:0] membrane;
    reg        spike_out;
    reg        spike_latched;

    wire [7:0] input_current = mode_sel ? {4'b0, weight_in} : activation;
    wire [7:0] decay_val = reg_decay;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            membrane      <= 16'd0;
            spike_out     <= 1'b0;
            spike_latched <= 1'b0;
        end else if (reg_ctrl[1]) begin
            membrane      <= 16'd0;
            spike_out     <= 1'b0;
            spike_latched <= 1'b0;
        end else if (lfsr_en) begin
            spike_out <= 1'b0;

            // Integrate: add input if stochastic comparison passes or external spike
            if (stoch_fire || ext_spike) begin
                // Saturate at 16'hFFFF instead of wrapping
                if (membrane > (16'hFFFF - {8'b0, input_current}))
                    membrane <= 16'hFFFF;
                else
                    membrane <= membrane + {8'b0, input_current};
            end else begin
                // Leak: subtract decay only when NOT integrating
                if (membrane > {8'b0, decay_val})
                    membrane <= membrane - {8'b0, decay_val};
                else
                    membrane <= 16'd0;
            end

            // Fire check
            if (membrane[15:8] >= reg_threshold) begin
                spike_out     <= 1'b1;
                spike_latched <= 1'b1;
                membrane      <= 16'd0;  // Reset after spike
            end
        end
    end

    // ============================================================
    // Status register
    // ============================================================
    assign reg_status = {4'b0, membrane[15], spike_latched, (membrane == 16'hFFFF), spike_out};

    // ============================================================
    // Output assignments
    // ============================================================
    assign uo_out[0]   = spike_out;                // Spike output
    assign uo_out[1]   = lfsr[15];                 // LFSR MSB (randomness monitor)
    assign uo_out[2]   = (membrane == 16'hFFFF);   // Accumulator overflow
    assign uo_out[3]   = spike_latched;            // Threshold crossed flag
    assign uo_out[7:4] = membrane[15:12];          // Membrane potential top 4 bits

    assign uio_out[0]  = 1'b0;        // CS is input
    assign uio_out[1]  = 1'b0;        // MOSI is input
    assign uio_out[2]  = spi_miso;    // MISO is output
    assign uio_out[3]  = 1'b0;        // SCK is input
    assign uio_out[7:4] = {lfsr[10], lfsr[5], stoch_fire, neuron_en}; // Debug

    assign uio_oe = {4'b1111, 1'b0, ~spi_cs_n, 2'b00};
    // uio[7:4]=debug(1), uio[3]=SCK in(0), uio[2]=MISO(dynamic), uio[1]=MOSI in(0), uio[0]=CS in(0)

    // Unused inputs
    wire _unused = &{ena, ui_in[3], uio_in[2], uio_in[7:4], 1'b0};

endmodule
