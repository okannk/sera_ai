# Sera AI — PCB Design Files

KiCad 7.0 PCB projects for the Sera AI greenhouse automation system.
Three independent ESP32-S3 based nodes, each with W5500 SPI Ethernet.

---

## Node Overview

| Node | Directory | Board Size | Purpose |
|------|-----------|------------|---------|
| Sensor Node | `sensor_node/` | 100 × 80 mm | Multi-sensor acquisition (SHT40, SCD41, AS7341, TEROS-12) |
| Climate Node | `climate_node/` | 120 × 100 mm | 4-channel SSR actuator control (230V AC) |
| Irrigation Node | `irrigation_node/` | 120 × 100 mm | Atlas EZO probes + MOSFET valve drive (12V DC) |

---

## Directory Structure

```
pcb/
├── README.md
├── sensor_node/
│   ├── sensor_node.kicad_pro      KiCad 7.0 project file
│   ├── sensor_node.kicad_sch      Schematic (S-expression format)
│   ├── sensor_node.kicad_pcb      PCB layout
│   ├── bom.csv                    Bill of materials
│   ├── pick_and_place.csv         SMT assembly coordinates
│   └── gerber/
│       ├── sensor_node-F_Cu.gtl       Front copper
│       ├── sensor_node-B_Cu.gbl       Back copper (GND plane)
│       ├── sensor_node-F_Silkscreen.gto  Front silkscreen
│       ├── sensor_node-Edge_Cuts.gm1  Board outline
│       └── sensor_node.drl            Drill file (Excellon MM)
├── climate_node/
│   ├── climate_node.kicad_pro
│   ├── climate_node.kicad_sch
│   ├── climate_node.kicad_pcb
│   ├── bom.csv
│   ├── pick_and_place.csv
│   └── gerber/
│       ├── climate_node-F_Cu.gtl
│       ├── climate_node-B_Cu.gbl
│       ├── climate_node-F_Silkscreen.gto
│       ├── climate_node-Edge_Cuts.gm1
│       └── climate_node.drl
└── irrigation_node/
    ├── irrigation_node.kicad_pro
    ├── irrigation_node.kicad_sch
    ├── irrigation_node.kicad_pcb
    ├── bom.csv
    ├── pick_and_place.csv
    └── gerber/
        ├── irrigation_node-F_Cu.gtl
        ├── irrigation_node-B_Cu.gbl
        ├── irrigation_node-F_Silkscreen.gto
        ├── irrigation_node-Edge_Cuts.gm1
        └── irrigation_node.drl
```

---

## Node 1 — Sensor Node (100 × 80 mm)

### Purpose
Multi-parameter environmental sensing. Collects temperature, humidity, CO₂,
full-spectrum light, and soil moisture. Sends data via MQTT over Ethernet.

### Key Components

| Reference | Component | Description |
|-----------|-----------|-------------|
| U2 | ESP32-S3-DevKitC-1 | Main MCU, 2×22 header 2.54mm pitch |
| U3 | W5500 | Hardwired TCP/IP SPI Ethernet module |
| U1 | AMS1117-3.3 | SOT-223 LDO, 5V → 3.3V |
| PS1 | HLK-PM05 | AC-DC isolated, 220V → 5V 600mA |
| J1 | JST-XH 4p | SHT40 (T+H, I2C 0x44) |
| J2 | JST-XH 4p | SCD41 (CO₂, I2C 0x62) |
| J3 | JST-XH 4p | AS7341 (light spectrum, I2C 0x39) |
| J4 | JST-XH 3p | TEROS-12 (soil, SDI-12) |
| J7 | HR911105A | RJ45 with integrated magnetics |
| D4 | SMBJ5.0A | TVS diode, transient protection |
| D5 | BAT54 | Schottky, reverse polarity |
| C1-C2 | 100µF | Bulk electrolytic caps |
| C3-C10 | 10µF / 100nF | Decoupling capacitors |
| R1-R2 | 4.7kΩ | I2C pull-up resistors |
| R3-R5 | 330Ω | LED current limiting |
| D1-D3 | LED 0805 | Status: green (power), blue (net), red (alarm) |

### Pin Assignment (ESP32-S3)

| Signal | GPIO |
|--------|------|
| I2C SDA | GPIO8 |
| I2C SCL | GPIO9 |
| SPI MOSI | GPIO11 |
| SPI MISO | GPIO13 |
| SPI SCK | GPIO12 |
| SPI CS W5500 | GPIO10 |
| W5500 INT | GPIO14 |
| W5500 RST | GPIO15 |
| UART TX (debug) | GPIO43 |
| UART RX (debug) | GPIO44 |
| SDI-12 DATA | GPIO16 |
| nRESET | EN |

---

## Node 2 — Climate Node (120 × 100 mm)

### Purpose
4-channel solid-state relay (SSR) control for AC loads: irrigation pump,
heater, cooling unit, fan. PC817 optocouplers provide full galvanic isolation
between ESP32 3.3V logic and SSR control inputs.

### WARNING — HIGH VOLTAGE
This board carries **230V AC mains voltage**. The board is divided into:
- **Low-voltage zone** (top half, y < 60mm): ESP32, W5500, logic, LEDs — 3.3V/5V DC
- **High-voltage zone** (bottom half, y > 60mm): AC mains, MOV, fuse, SSR connectors

**Design requirements:**
- Minimum 6mm creepage/clearance between LV and HV
- Conformal coating mandatory on HV zone
- Use IEC 60950 / IEC 62368 compliant assembly practices
- Fuse: 10A fast-blow ceramic 5×20mm in inline holder

### Key Components

| Reference | Component | Description |
|-----------|-----------|-------------|
| U4-U7 | PC817 | DIP-4 optocoupler, CTR ≥ 100% |
| K1-K4 | G3MB-202P | Panel-mount SSR, 250VAC 2A |
| RV1 | S14K275 | MOV varistor 275V, L-N surge clamp |
| F1 | 10A 250V | Fast-blow ceramic fuse + holder |
| J_AC | Phoenix 5p | L / N / PE / LOAD1 / LOAD2 screw terminal |
| R1-R4 | 330Ω | PC817 input LED current limiters |

### SSR Channel Mapping

| Channel | GPIO | Load |
|---------|------|------|
| CH1 | GPIO38 | Irrigation pump |
| CH2 | GPIO39 | Heater |
| CH3 | GPIO40 | Cooling |
| CH4 | GPIO41 | Fan |

---

## Node 3 — Irrigation Node (120 × 100 mm)

### Purpose
Precision water quality monitoring with Atlas Scientific EZO probes, plus
direct 12V solenoid valve drive via logic-level N-MOSFET and flow measurement
with YF-S201 pulse-output flow sensor.

### Key Components

| Reference | Component | Description |
|-----------|-----------|-------------|
| U4 | LM2596S-12 | TO-263-5 buck converter, 5V→12V at 3A |
| L1 | 100µH | Axial inductor, LM2596 output filter |
| C11 | 220µF 25V | LM2596 output capacitor |
| Q1-Q2 | IRLZ44N | TO-220 logic-level N-MOSFET, 55V/47A |
| D6-D7 | 1N4007 | DO-41 flyback diodes for inductive loads |
| R9-R10 | 100Ω | MOSFET gate resistors |
| J1 | JST-XH 4p | Atlas EZO-pH (I2C 0x63) |
| J2 | JST-XH 4p | Atlas EZO-EC (I2C 0x64) |
| J3 | JST-XH 4p | Atlas EZO-DO (I2C 0x61) |
| J4 | JST-XH 4p | Atlas EZO-RTD (I2C 0x66) |
| J5 | JST-XH 4p | Atlas EZO-PMP (I2C 0x67) |
| J6-J7 | Phoenix 2p | Solenoid valve screw terminals |
| J8 | JST-XH 3p | YF-S201 flow sensor |
| R11 | 10kΩ | Flow sensor signal pull-up |
| C5-C9 | 100nF | Per-probe bypass capacitors |

### EZO Probe I2C Addresses

| Probe | I2C Address | Parameter |
|-------|-------------|-----------|
| EZO-pH | 0x63 | pH 0.001 precision |
| EZO-EC | 0x64 | Conductivity / TDS / salinity |
| EZO-DO | 0x61 | Dissolved oxygen |
| EZO-RTD | 0x66 | Temperature (RTD) |
| EZO-PMP | 0x67 | Peristaltic pump control |

### Valve Drive

- Valve supply: 12V from LM2596 buck (input 15-24V via DC jack or HLK-PM05 variant)
- IRLZ44N: Vgs_th = 1.0-2.0V, fully enhanced at 3.3V ESP32 output
- Gate resistor 100Ω limits dI/dt and parasitic oscillation
- 1N4007 flyback diodes protect MOSFET from inductive kick

---

## Common Design Notes

### Power Architecture (all nodes)
```
AC 220V ──► HLK-PM05 ──► +5V ──► AMS1117-3.3 ──► +3.3V (MCU, sensors)
                           │
                           └──► W5500 (5V tolerant)
                           │
                  (irr. node only)
                           └──► LM2596-12 ──► +12V (valves)
```

### SPI Ethernet (W5500) — all nodes
- Interface: SPI up to 80MHz (typically 20-40MHz in firmware)
- GPIO11 MOSI / GPIO13 MISO / GPIO12 SCK / GPIO10 CS
- GPIO14 INT (active-low interrupt)
- GPIO15 RST (active-low hardware reset)
- Full TCP/IP stack offloaded from ESP32

### PCB Stack-up (all nodes)
- 2-layer FR4, 1.6mm thickness
- F.Cu: signal + power routing
- B.Cu: GND plane (full pour)
- Soldermask: LPI green both sides
- Silkscreen: white, F side only
- Finish: HASL or ENIG

### Design Rules
| Rule | Value |
|------|-------|
| Min clearance (signal) | 0.2mm |
| Min clearance (power) | 0.3mm |
| Min clearance (HV AC) | 6.0mm |
| Min trace width (signal) | 0.25mm |
| Power traces | 1.0mm (5V/3.3V), 2.0mm (12V/AC) |
| Via drill | 0.6mm |
| Via diameter | 1.0mm |
| Min hole | 0.3mm |
| Board thickness | 1.6mm |
| Copper weight | 1oz (35µm) |

---

## Manufacturing

### Gerber Files (per node)
| File | Extension | Description |
|------|-----------|-------------|
| F_Cu | .gtl | Front copper layer |
| B_Cu | .gbl | Back copper layer |
| F_Silkscreen | .gto | Front silkscreen |
| Edge_Cuts | .gm1 | Board outline |
| Drill | .drl | Excellon drill file (mm) |

### Recommended PCB Manufacturers
- JLCPCB (jlcpcb.com) — standard 2-layer, excellent price
- PCBWay (pcbway.com) — good for prototypes
- OSH Park (oshpark.com) — US-based, purple boards

### Assembly Notes
- All SMD components on F.Cu only (single-side SMT)
- THT components: ESP32 headers, connectors, caps, MOSFETs
- Hand-solder or selective soldering for THT after SMT reflow
- Apply conformal coating (Climate Node HV zone is mandatory)

---

## Revision History

| Rev | Date | Author | Notes |
|-----|------|--------|-------|
| 1.0 | 2026-03-11 | Sera AI | Initial release — all 3 nodes |

---

*Generated for Sera AI Greenhouse Automation System — KiCad 7.0*
