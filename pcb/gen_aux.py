"""Generate BOM, Pick&Place and Gerber placeholders for all 3 nodes."""
import os

BOM_HDR = "Reference,Value,Footprint,Qty,Manufacturer,PartNumber,Supplier,Description\n"

BOMS = {
"sensor_node": BOM_HDR + """\
U1,AMS1117-3.3,SOT-223-3_TabPin2,1,AMS,AMS1117-3.3,LCSC C6186,3.3V 1A LDO
U2,ESP32-S3-DevKitC-1,Module:ESP32-S3-DevKitC-1,1,Espressif,ESP32-S3-DevKitC-1,Mouser 356-ESP32S3DEVKITC1,MCU module
U3,W5500-EVB,Module:W5500-EVB,1,WIZnet,W5500,Mouser 720-W5500,SPI Ethernet
PS1,HLK-PM05,Module:HLK-PM05,1,Hi-Link,HLK-PM05,LCSC C167067,AC-DC 5V 0.6A
C1,100uF,CP_Radial_D8.0mm_P3.50mm,1,Nichicon,UVR1E101MED,Mouser,Bulk LDO in
C2,100uF,CP_Radial_D8.0mm_P3.50mm,1,Nichicon,UVR1E101MED,Mouser,Bulk LDO out
C3,10uF,C_1206_3216Metric,1,Murata,GRM31CR61E106KA12,Mouser,MLCC LDO in
C4,10uF,C_1206_3216Metric,1,Murata,GRM31CR61E106KA12,Mouser,MLCC LDO out
C5,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,Decoupling
C6,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,Decoupling
C7,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,Decoupling
C8,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,Decoupling
C9,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,Decoupling
C10,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,Decoupling
R1,4.7k,R_0805_2012Metric,1,Yageo,RC0805FR-074K7L,Mouser,I2C SDA pull-up
R2,4.7k,R_0805_2012Metric,1,Yageo,RC0805FR-074K7L,Mouser,I2C SCL pull-up
R3,330,R_0805_2012Metric,1,Yageo,RC0805FR-07330RL,Mouser,LED PWR
R4,330,R_0805_2012Metric,1,Yageo,RC0805FR-07330RL,Mouser,LED WiFi
R5,330,R_0805_2012Metric,1,Yageo,RC0805FR-07330RL,Mouser,LED ERR
D1,LED_GREEN,LED_SMD:LED_0805,1,Wurth,150080VS75000,Mouser,PWR green
D2,LED_BLUE,LED_SMD:LED_0805,1,Wurth,150080BS75000,Mouser,WiFi blue
D3,LED_RED,LED_SMD:LED_0805,1,Wurth,150080RS75000,Mouser,ERR red
D4,SMBJ5.0A,Diode_SMD:D_SMB,1,Vishay,SMBJ5.0A-E3/61,Mouser,TVS 5V power line
D5,BAT54,Package_TO_SOT_SMD:SOT-23,1,Vishay,BAT54-GS08,Mouser,Schottky SDI-12 3.6V
J1,SHT40_I2C,JST_XH_B4B-XH-A_1x04,1,JST,B4B-XH-A,Mouser 306-B4B-XH-A,SHT40 connector
J2,SCD41_I2C,JST_XH_B4B-XH-A_1x04,1,JST,B4B-XH-A,Mouser 306-B4B-XH-A,SCD41 CO2
J3,AS7341_I2C,JST_XH_B4B-XH-A_1x04,1,JST,B4B-XH-A,Mouser 306-B4B-XH-A,AS7341 spectral
J4,TEROS12_SDI12,JST_XH_B3B-XH-A_1x03,1,JST,B3B-XH-A,Mouser 306-B3B-XH-A,TEROS-12
J5,DC_Jack_2.1mm,BarrelJack_Kycon,1,Kycon,KLDX-0202-A,Mouser,5V DC input
J6,UART_DEBUG,PinHeader_1x04_P2.54mm,1,Wurth,61300411121,Mouser,UART debug
J7,HR911105A,RJ45_Horizontal,1,Hanrun,HR911105A,Mouser,Ethernet RJ45
SW1,RESET,SW_SPST_SKQG,1,Alps,SKQGAFE010,Mouser 688-SKQGAFE010,Reset button
MH1,M3_Hole,MountingHole_3.2mm_M3,4,,,,Corner mounting hole
""",

"climate_node": BOM_HDR + """\
U1,AMS1117-3.3,SOT-223-3_TabPin2,1,AMS,AMS1117-3.3,LCSC C6186,3.3V LDO
U2,ESP32-S3-DevKitC-1,Module:ESP32-S3-DevKitC-1,1,Espressif,ESP32-S3-DevKitC-1,Mouser,MCU module
U3,W5500-EVB,Module:W5500-EVB,1,WIZnet,W5500,Mouser 720-W5500,SPI Ethernet
U4,PC817_FAN,Package_DIP:DIP-4,1,OnSemi,PC817X1NSZ1F,Mouser 512-PC817X1NSZ1F,Opto FAN
U5,PC817_ISITICI,Package_DIP:DIP-4,1,OnSemi,PC817X1NSZ1F,Mouser 512-PC817X1NSZ1F,Opto ISITICI
U6,PC817_SOGUTMA,Package_DIP:DIP-4,1,OnSemi,PC817X1NSZ1F,Mouser 512-PC817X1NSZ1F,Opto SOGUTMA
U7,PC817_HAVALANDIRMA,Package_DIP:DIP-4,1,OnSemi,PC817X1NSZ1F,Mouser,Opto HAVALANDIRMA
PS1,HLK-PM05,Module:HLK-PM05,1,Hi-Link,HLK-PM05,LCSC C167067,AC-DC 5V
K1,SSR_FAN,G3MB-202P,1,Omron,G3MB-202P,Mouser,SSR 2A FAN
K2,SSR_ISITICI,G3MB-202P,1,Omron,G3MB-202P,Mouser,SSR 2A ISITICI
K3,SSR_SOGUTMA,G3MB-202P,1,Omron,G3MB-202P,Mouser,SSR 2A SOGUTMA
K4,SSR_HAVALANDIRMA,G3MB-202P,1,Omron,G3MB-202P,Mouser,SSR 2A HAVALANDIRMA
C1,100uF,CP_Radial_D8.0mm_P3.50mm,1,Nichicon,UVR1E101MED,Mouser,Bulk cap
C2,100uF,CP_Radial_D8.0mm_P3.50mm,1,Nichicon,UVR1E101MED,Mouser,Bulk cap
C3,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,Bypass
C4,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,Bypass
R1,330,R_0805_2012Metric,1,Yageo,RC0805FR-07330RL,Mouser,Opto FAN input
R2,330,R_0805_2012Metric,1,Yageo,RC0805FR-07330RL,Mouser,Opto ISITICI
R3,330,R_0805_2012Metric,1,Yageo,RC0805FR-07330RL,Mouser,Opto SOGUTMA
R4,330,R_0805_2012Metric,1,Yageo,RC0805FR-07330RL,Mouser,Opto HAVALANDIRMA
R5,330,R_0805_2012Metric,1,Yageo,RC0805FR-07330RL,Mouser,LED R5
R6,330,R_0805_2012Metric,1,Yageo,RC0805FR-07330RL,Mouser,LED R6
R7,330,R_0805_2012Metric,1,Yageo,RC0805FR-07330RL,Mouser,LED R7
R8,330,R_0805_2012Metric,1,Yageo,RC0805FR-07330RL,Mouser,LED R8
D1,LED_SSR1,LED_SMD:LED_0805,1,Wurth,150080VS75000,Mouser,SSR1 status LED
D2,LED_SSR2,LED_SMD:LED_0805,1,Wurth,150080VS75000,Mouser,SSR2 status LED
D3,LED_SSR3,LED_SMD:LED_0805,1,Wurth,150080VS75000,Mouser,SSR3 status LED
D4,LED_SSR4,LED_SMD:LED_0805,1,Wurth,150080VS75000,Mouser,SSR4 status LED
RV1,S14K275,RV_Disc_D14mm,1,TDK,B72214S0271K101,Mouser,MOV 275VAC
F1,Fuse_10A,Fuse_THT,1,Littelfuse,0312010.HXP,Mouser,10A 250V glass fuse
J5,DC_Jack_2.1mm,BarrelJack_Kycon,1,Kycon,KLDX-0202-A,Mouser,5V DC input
J6,UART_DEBUG,PinHeader_1x04_P2.54mm,1,Wurth,61300411121,Mouser,UART debug
J7,HR911105A,RJ45_Horizontal,1,Hanrun,HR911105A,Mouser,Ethernet RJ45
J8,AC_TERM_5pin,TerminalBlock_5p,1,Phoenix,MKDS 1.5/5,Mouser,L+N+PE+Load1+Load2
SW1,RESET,SW_SPST_SKQG,1,Alps,SKQGAFE010,Mouser,Reset button
MH1,M3_Hole,MountingHole_3.2mm_M3,4,,,,Corner mounting hole
""",

"irrigation_node": BOM_HDR + """\
U1,AMS1117-3.3,SOT-223-3_TabPin2,1,AMS,AMS1117-3.3,LCSC C6186,3.3V LDO
U2,ESP32-S3-DevKitC-1,Module:ESP32-S3-DevKitC-1,1,Espressif,ESP32-S3-DevKitC-1,Mouser,MCU module
U3,W5500-EVB,Module:W5500-EVB,1,WIZnet,W5500,Mouser 720-W5500,SPI Ethernet
U4,LM2596-12V,TO-263-5_TabPin3,1,TI,LM2596S-12/NOPB,Mouser 595-LM2596S-12NOPB,5V->12V buck
PS1,HLK-PM05,Module:HLK-PM05,1,Hi-Link,HLK-PM05,LCSC C167067,AC-DC 5V
J_PH,EZO-pH_0x63,JST_XH_B4B-XH-A,1,JST,B4B-XH-A,Mouser,Atlas EZO-pH I2C 0x63
J_EC,EZO-EC_0x64,JST_XH_B4B-XH-A,1,JST,B4B-XH-A,Mouser,Atlas EZO-EC I2C 0x64
J_DO,EZO-DO_0x61,JST_XH_B4B-XH-A,1,JST,B4B-XH-A,Mouser,Atlas EZO-DO I2C 0x61
J_RTD,EZO-RTD_0x66,JST_XH_B4B-XH-A,1,JST,B4B-XH-A,Mouser,Atlas EZO-RTD I2C 0x66
J_PMP,EZO-PMP_0x67,JST_XH_B4B-XH-A,1,JST,B4B-XH-A,Mouser,Atlas EZO-PMP I2C 0x67
C1,100uF,CP_Radial_D8.0mm_P3.50mm,1,Nichicon,UVR1E101MED,Mouser,Bulk LDO
C2,10uF,C_1206_3216Metric,1,Murata,GRM31CR61E106KA12,Mouser,MLCC LDO
C3,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,Bypass
C4,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,Bypass
C11,220uF,CP_Radial_D10.0mm,1,Nichicon,UVR1E221MED,Mouser,LM2596 output cap
C12,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,EZO-pH bypass
C13,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,EZO-EC bypass
C14,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,EZO-DO bypass
C15,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,EZO-RTD bypass
C16,100nF,C_0805_2012Metric,1,Yageo,CC0805ZRY5V9BB104,Mouser,EZO-PMP bypass
L1,100uH,Inductor_Axial,1,Bourns,RLB9012-101KL,Mouser 652-RLB9012-101K,LM2596 inductor
Q1,IRLZ44N_VALVE1,TO-220-3_Vertical,1,Vishay,IRLZ44NPBF,Mouser 942-IRLZ44NPBF,N-MOSFET valve 1
Q2,IRLZ44N_VALVE2,TO-220-3_Vertical,1,Vishay,IRLZ44NPBF,Mouser 942-IRLZ44NPBF,N-MOSFET valve 2
D6,1N4007,D_DO-41_P12.70mm,1,Vishay,1N4007,Mouser,Flyback Q1
D7,1N4007,D_DO-41_P12.70mm,1,Vishay,1N4007,Mouser,Flyback Q2
R6,100,R_0805_2012Metric,1,Yageo,RC0805FR-07100RL,Mouser,Gate R Q1
R7,100,R_0805_2012Metric,1,Yageo,RC0805FR-07100RL,Mouser,Gate R Q2
R8,10k,R_0805_2012Metric,1,Yageo,RC0805FR-0710KL,Mouser,Flow sensor pull-up
J_V1,VALVE_1_TERMINAL,TerminalBlock_2p,1,Phoenix,MKDS 1.5/2,Mouser,Valve 1 screw terminal
J_V2,VALVE_2_TERMINAL,TerminalBlock_2p,1,Phoenix,MKDS 1.5/2,Mouser,Valve 2 screw terminal
J_FLOW,YF-S201_FLOW,JST_XH_B3B-XH-A,1,JST,B3B-XH-A,Mouser,Flow sensor YF-S201
J5,DC_Jack_2.1mm,BarrelJack_Kycon,1,Kycon,KLDX-0202-A,Mouser,5V DC input
J6,UART_DEBUG,PinHeader_1x04_P2.54mm,1,Wurth,61300411121,Mouser,UART debug
J7,HR911105A,RJ45_Horizontal,1,Hanrun,HR911105A,Mouser,Ethernet RJ45
SW1,RESET,SW_SPST_SKQG,1,Alps,SKQGAFE010,Mouser,Reset button
MH1,M3_Hole,MountingHole_3.2mm_M3,4,,,,Corner mounting hole
""",
}

PNP_HDR = "Reference,Value,Package,PosX_mm,PosY_mm,Rotation,Side\n"

PNPS = {
"sensor_node": PNP_HDR + """\
U1,AMS1117-3.3,SOT-223-3,15.00,15.00,0,F
C5,100nF,C_0805,65.00,110.00,0,F
C6,100nF,C_0805,75.00,110.00,0,F
C7,100nF,C_0805,85.00,110.00,0,F
C8,100nF,C_0805,95.00,110.00,0,F
C9,100nF,C_0805,105.00,110.00,0,F
C10,100nF,C_0805,115.00,110.00,0,F
C3,10uF,C_1206,45.00,110.00,0,F
C4,10uF,C_1206,55.00,110.00,0,F
R1,4.7k,R_0805,130.00,80.00,0,F
R2,4.7k,R_0805,140.00,80.00,0,F
R3,330,R_0805,150.00,80.00,0,F
R4,330,R_0805,160.00,80.00,0,F
R5,330,R_0805,170.00,80.00,0,F
D1,LED_GREEN,LED_0805,150.00,100.00,0,F
D2,LED_BLUE,LED_0805,160.00,100.00,0,F
D3,LED_RED,LED_0805,170.00,100.00,0,F
D4,SMBJ5.0A,D_SMB,15.00,130.00,0,F
D5,BAT54,SOT-23,25.00,130.00,0,F
SW1,RESET,SKQG,93.00,72.00,0,F
""",
"climate_node": PNP_HDR + """\
U1,AMS1117-3.3,SOT-223-3,15.00,15.00,0,F
R1,330,R_0805,30.00,22.00,0,F
R2,330,R_0805,52.00,22.00,0,F
R3,330,R_0805,74.00,22.00,0,F
R4,330,R_0805,96.00,22.00,0,F
D1,LED_SSR1,LED_0805,30.00,60.00,0,F
D2,LED_SSR2,LED_0805,52.00,60.00,0,F
D3,LED_SSR3,LED_0805,74.00,60.00,0,F
D4,LED_SSR4,LED_0805,96.00,60.00,0,F
RV1,S14K275,RV_Disc,15.00,140.00,0,F
SW1,RESET,SKQG,93.00,72.00,0,F
""",
"irrigation_node": PNP_HDR + """\
U1,AMS1117-3.3,SOT-223-3,15.00,15.00,0,F
U4,LM2596-12V,TO-263-5,90.00,20.00,0,F
C3,100nF,C_0805,45.00,110.00,0,F
C4,100nF,C_0805,55.00,110.00,0,F
C12,100nF,C_0805,20.00,55.00,0,F
C13,100nF,C_0805,33.00,55.00,0,F
C14,100nF,C_0805,46.00,55.00,0,F
C15,100nF,C_0805,59.00,55.00,0,F
C16,100nF,C_0805,72.00,55.00,0,F
R6,100,R_0805,88.00,65.00,0,F
R7,100,R_0805,102.00,65.00,0,F
R8,10k,R_0805,108.00,55.00,0,F
SW1,RESET,SKQG,93.00,72.00,0,F
""",
}

GERBER_NOTE = """\
; PLACEHOLDER — Export from KiCad to get real Gerbers
; File -> Fabrication Outputs -> Gerbers (JLCPCB format)
; Or: kicad-cli pcb export gerbers --output gerber/ <node>.kicad_pcb
"""

base = os.path.dirname(os.path.abspath(__file__))
for node in ["sensor_node", "climate_node", "irrigation_node"]:
    ndir = os.path.join(base, node)
    os.makedirs(ndir, exist_ok=True)
    open(os.path.join(ndir, "bom.csv"), "w").write(BOMS[node])
    open(os.path.join(ndir, "pick_and_place.csv"), "w").write(PNPS[node])
    gdir = os.path.join(ndir, "gerber")
    os.makedirs(gdir, exist_ok=True)
    for ext, desc in [
        (f"{node}-F_Cu.gtl",          "Front copper layer"),
        (f"{node}-B_Cu.gbl",          "Back copper (GND plane)"),
        (f"{node}-F_Silkscreen.gto",  "Front silkscreen"),
        (f"{node}-B_Silkscreen.gbo",  "Back silkscreen"),
        (f"{node}-F_Mask.gts",        "Front soldermask"),
        (f"{node}-B_Mask.gbs",        "Back soldermask"),
        (f"{node}-Edge_Cuts.gm1",     "Board outline"),
        (f"{node}.drl",               "Excellon drill file"),
    ]:
        open(os.path.join(gdir, ext), "w").write(f"; {desc}\n{GERBER_NOTE}")

print("Tum yardimci dosyalar olusturuldu.")
