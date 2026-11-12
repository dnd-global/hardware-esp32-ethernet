"""Netlist and placement the board was built from, one entry per part.

PARTS  reference -> (footprint, value, LCSC part number, x, y, rotation, {pad: net}, not fitted)
POS    reference -> (x, y, rotation) on the board in mm; overrides the coordinates written in PARTS

A footprint is written "library:name". "lcsc" is kicad/lcsc.pretty; the other libraries ship with KiCad.
The board file in kicad/ is the master: it was placed from this table, autorouted, then edited further.
The schematic (tools/schematic) and the assembly files (tools/fab) are generated from this table and
checked against the board.
"""


def std(lib, name):
    return lib + ":" + name


def lc(name):
    return "lcsc:" + name


W, H = 80.0, 66.0          # board size (mm)
MOD_X, MOD_Y = 14.0, 16.6  # ESP32-S3-WROOM-1 centre; antenna end flush with the top edge
RJ_X, RJ_Y = 11.0, 55.0    # HR911105A centre; opening overhangs the bottom edge by ~2 mm
ETH_X, ETH_Y = 26.0, 39.0  # W5500 centre
ISO_X, ISO_Y = 47.0, 45.0  # CA-IS3642 centre; isolation barrier runs vertically through it

R0603 = std("Resistor_SMD", "R_0603_1608Metric")
C0603 = std("Capacitor_SMD", "C_0603_1608Metric")
C0805 = std("Capacitor_SMD", "C_0805_2012Metric")
C1206 = std("Capacitor_SMD", "C_1206_3216Metric")
C1210 = std("Capacitor_SMD", "C_1210_3225Metric")
LED0603 = std("LED_SMD", "LED_0603_1608Metric")

# ref: (footprint, value, LCSC, x, y, rot, {pad: net}, dnp)
PARTS = {
    # ---- power input 9-36 V ----
    "J1": (lc("CONN-TH_2P-P5.08_KF128-5.08-2P"), "KF128-5.08-2P (+ / -)", "C474952", 69.5, 8.0, 90,
           {"1": "VIN_RAW", "2": "GND"}, False),
    "F1": (lc("F1812"), "PTC 0.5A 60V", "C70113", 66.0, 19.5, 0, {"2": "VIN_RAW", "1": "VIN_F"}, False),
    "D1": (std("Diode_SMD", "D_SMA"), "SS210", "C14996", 60.0, 19.5, 0, {"2": "VIN_F", "1": "VIN_P"}, False),
    "D2": (std("Diode_SMD", "D_SMB"), "SMBJ36A", "C353364", 55.0, 19.5, 90, {"1": "VIN_P", "2": "GND"}, False),
    "C1": (C1210, "4.7uF 100V", "C381466", 51.5, 19.5, 90, {"1": "VIN_P", "2": "GND"}, False),
    "L1": (lc("IND-SMD_L4.0-W4.0"), "10uH", "C38117", 47.0, 19.5, 0, {"1": "VIN_P", "2": "VIN_FLT"}, False),
    "C5": (std("Capacitor_SMD", "CP_Elec_6.3x7.7"), "47uF 63V", "C48971005", 51.0, 6.5, 0,
           {"1": "VIN_FLT", "2": "GND"}, False),
    "C2": (C1210, "4.7uF 100V", "C381466", 45.0, 7.0, 90, {"1": "VIN_FLT", "2": "GND"}, False),
    "C3": (C1210, "4.7uF 100V", "C381466", 42.0, 7.0, 90, {"1": "VIN_FLT", "2": "GND"}, False),
    "C4": (C0603, "220nF 100V", "C36911431", 38.6, 8.0, 0, {"1": "VIN_FLT", "2": "GND"}, False),
    "U1": (lc("POWERPAD-SO-8_L4.9-W3.9-P1.27-LS6.0-BL-EP"), "LMR36520", "C1858395", 38.0, 13.0, 180,
           {"1": "GND", "2": "VIN_FLT", "3": "VIN_FLT", "4": "PG", "5": "FB", "6": "VCC_BUCK",
            "7": "BOOT", "8": "SW", "9": "GND"}, False),
    "C6": (C0603, "100nF", "C14663", 42.5, 16.5, 90, {"1": "BOOT", "2": "SW"}, False),
    "C7": (C0603, "1uF", "C15849", 37.4, 18.5, 90, {"1": "VCC_BUCK", "2": "GND"}, False),
    "R1": (R0603, "51k", "C23196", 33.5, 12.0, 90, {"1": "+3V3", "2": "FB"}, False),   # 51k/22k -> 3.32 V, both JLCPCB basic parts
    "R2": (R0603, "22k", "C31850", 33.5, 16.0, 90, {"1": "FB", "2": "GND"}, False),
    "L2": (lc("IND-SMD_L7.0-W6.6"), "6.8uH 4A", "C357230", 40.0, 23.5, 0, {"1": "SW", "2": "+3V3"}, False),
    "C8": (C1206, "22uF 25V", "C12891", 46.5, 24.5, 90, {"1": "+3V3", "2": "GND"}, False),
    "C9": (C1206, "22uF 25V", "C12891", 49.5, 24.5, 90, {"1": "+3V3", "2": "GND"}, False),
    "C10": (C1206, "22uF 25V", "C12891", 52.5, 24.5, 90, {"1": "+3V3", "2": "GND"}, False),
    # ---- ESP32-S3 module: W5500 on IO15 / 13 / 14 / 16 / 12 / 39, UART1 on IO17 / 18 ----
    "U2": (lc("WIFIM-SMD_ESP32-S3-WROOM-1-N8"), "ESP32-S3-WROOM-1-N8", "C2913198", MOD_X, MOD_Y, 0,
           {"1": "GND", "40": "GND", "41": "GND", "2": "+3V3", "3": "EN",
            "8": "SPI_SCLK", "9": "SPI_CS", "10": "UART_TX", "11": "UART_RX",
            "13": "USB_DM", "14": "USB_DP", "20": "ETH_INT", "21": "SPI_MOSI", "22": "SPI_MISO",
            "27": "IO0", "31": "STATUS", "32": "ETH_RST", "36": "PROG_RX", "37": "PROG_TX"}, False),
    "C11": (C1206, "22uF 25V", "C12891", 2.4, 19.5, 90, {"1": "+3V3", "2": "GND"}, False),
    "C12": (C0603, "100nF", "C14663", 2.4, 9.6, 90, {"1": "+3V3", "2": "GND"}, False),
    "R9": (R0603, "10k", "C25804", 2.4, 12.6, 90, {"1": "+3V3", "2": "EN"}, False),
    "C13": (C0603, "1uF", "C15849", 2.4, 15.2, 90, {"1": "EN", "2": "GND"}, False),
    "SW1": (lc("SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5"), "RESET", "C318884", 35.0, 53.0, 0,
            {"1": "EN", "2": "EN", "3": "GND", "4": "GND"}, False),
    "SW2": (lc("SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5"), "BOOT", "C318884", 35.5, 35.0, 0,
            {"1": "IO0", "2": "IO0", "3": "GND", "4": "GND"}, False),
    "J5": (std("Connector_PinHeader_2.54mm", "PinHeader_1x05_P2.54mm_Vertical"), "PROG GND/TX0/RX0/D-/D+", "",
           31.0, 58.2, 90, {"1": "GND", "2": "PROG_TX", "3": "PROG_RX", "4": "USB_DM", "5": "USB_DP"}, True),
    "R3": (R0603, "1k", "C21190", 34.0, 28.5, 0, {"1": "+3V3", "2": "LED1_A"}, False),
    "LED1": (LED0603, "PWR red", "C2286", 37.0, 28.5, 0, {"1": "GND", "2": "LED1_A"}, False),
    "R4": (R0603, "150R", "C22808", 34.0, 31.0, 0, {"1": "STATUS", "2": "LED2_A"}, False),
    "LED2": (LED0603, "STATUS white", "C2290", 37.0, 31.0, 0, {"1": "GND", "2": "LED2_A"}, False),
    # ---- W5500 Ethernet (WIZnet reference schematic, RJ45 with magnetics) ----
    "U5": (std("Package_QFP", "LQFP-48_7x7mm_P0.5mm"), "W5500", "C32843", ETH_X, ETH_Y, 90,
           {"1": "ETH_TXN", "2": "ETH_TXP", "3": "GND", "4": "+3V3A", "5": "ETH_RXN", "6": "ETH_RXP",
            "8": "+3V3A", "9": "GND", "10": "EXRES", "11": "+3V3A", "14": "GND", "15": "+3V3A",
            "16": "GND", "17": "+3V3A", "19": "GND", "20": "TOCAP", "21": "+3V3A", "22": "V1V2",
            "23": "GND", "25": "LINKLED", "27": "ACTLED", "28": "+3V3", "29": "GND", "30": "XI",
            "31": "XO", "32": "SPI_CS", "33": "SPI_SCLK", "34": "SPI_MISO", "35": "SPI_MOSI",
            "36": "ETH_INT", "37": "ETH_RST", "48": "GND"}, False),
    "Y1": (std("Crystal", "Crystal_SMD_3225-4Pin_3.2x2.5mm"), "25MHz 12pF", "C9006", 20.0, 29.5, 0,
           {"1": "XI", "2": "GND", "3": "XO", "4": "GND"}, False),
    "C34": (C0603, "18pF", "C1647", 17.4, 29.5, 90, {"1": "XI", "2": "GND"}, False),
    "C35": (C0603, "18pF", "C1647", 22.6, 29.5, 90, {"1": "XO", "2": "GND"}, False),
    "R10": (R0603, "1M", "C22935", 20.0, 27.4, 0, {"1": "XI", "2": "XO"}, False),
    "R18": (R0603, "12.4k 1%", "C2930060", 20.0, 33.0, 90, {"1": "EXRES", "2": "GND"}, False),
    "C26": (C0603, "4.7uF", "C19666", 31.0, 30.5, 90, {"1": "TOCAP", "2": "GND"}, False),
    "C27": (C0603, "10nF", "C57112", 31.0, 33.0, 90, {"1": "V1V2", "2": "GND"}, False),
    "FB1": (std("Inductor_SMD", "L_0603_1608Metric"), "120R@100MHz", "C14709", 31.0, 26.5, 90,
            {"1": "+3V3", "2": "+3V3A"}, False),
    "C28": (C0603, "100nF", "C14663", 28.6, 38.6, 0, {"1": "+3V3A", "2": "GND"}, False),
    "C29": (C0603, "100nF", "C14663", 22.0, 36.6, 90, {"1": "+3V3A", "2": "GND"}, False),
    "C30": (C0603, "100nF", "C14663", 31.0, 35.6, 90, {"1": "+3V3A", "2": "GND"}, False),
    "C31": (C0603, "100nF", "C14663", 28.4, 27.6, 0, {"1": "+3V3A", "2": "GND"}, False),
    "C32": (C0805, "10uF", "C15850", 31.0, 38.6, 90, {"1": "+3V3A", "2": "GND"}, False),
    "C33": (C0603, "100nF", "C14663", 24.0, 27.6, 0, {"1": "+3V3", "2": "GND"}, False),
    "R19": (R0603, "10k", "C25804", 26.0, 27.6, 0, {"1": "+3V3", "2": "ETH_RST"}, False),
    "R20": (R0603, "10k", "C25804", 17.4, 33.0, 90, {"1": "+3V3", "2": "ETH_INT"}, False),
    "R21": (R0603, "10k", "C25804", 29.5, 28.1, 180, {"1": "+3V3", "2": "SPI_CS"}, False),   # SCSn pull-up
    "R11": (R0603, "49.9R 1%", "C23185", 22.5, 41.0, 0, {"1": "+3V3A", "2": "ETH_TXP"}, False),
    "R12": (R0603, "49.9R 1%", "C23185", 22.5, 42.8, 0, {"1": "+3V3A", "2": "ETH_TXN"}, False),
    "R13": (R0603, "10R", "C22859", 22.5, 44.6, 0, {"1": "+3V3A", "2": "TCT"}, False),
    "C22": (C0603, "22nF", "C21122", 22.5, 46.4, 0, {"1": "TCT", "2": "GND"}, False),
    "C23": (C0603, "6.8nF", "C1631", 26.5, 41.0, 0, {"1": "ETH_RXP", "2": "MAG_RDP"}, False),
    "C24": (C0603, "6.8nF", "C1631", 26.5, 42.8, 0, {"1": "ETH_RXN", "2": "MAG_RDN"}, False),
    "R14": (R0603, "49.9R 1%", "C23185", 26.5, 44.6, 0, {"1": "ETH_RXP", "2": "RCT"}, False),
    "R15": (R0603, "49.9R 1%", "C23185", 26.5, 46.4, 0, {"1": "ETH_RXN", "2": "RCT"}, False),
    "C25": (C0603, "10nF", "C57112", 26.5, 48.2, 0, {"1": "RCT", "2": "GND"}, False),
    "R16": (R0603, "330R", "C23138", 22.5, 53.0, 0, {"1": "LED_ACT_K", "2": "ACTLED"}, False),
    "R17": (R0603, "330R", "C23138", 22.5, 55.0, 0, {"1": "LED_LINK_K", "2": "LINKLED"}, False),
    "J3": (lc("RJ45-TH_HR911105A"), "HR911105A", "C12074", RJ_X, RJ_Y, 0,
           {"1": "ETH_TXP", "2": "ETH_TXN", "3": "MAG_RDP", "4": "TCT", "5": "RCT", "6": "MAG_RDN",
            "8": "GND", "9": "+3V3", "10": "LED_ACT_K", "11": "LED_LINK_K", "12": "+3V3",
            "SH1": "GND", "SH2": "GND"}, False),
    # ---- isolated UART ----
    "U3": (lc("SOIC-16_L10.3-W7.5-P1.27-LS10.3-TL"), "CA-IS3642HVW", "C5440874", ISO_X, ISO_Y, 0,
           {"1": "+3V3", "2": "GND", "3": "UART_TX", "4": "GND", "5": "UART_RX", "7": "+3V3", "8": "GND",
            "9": "GND_ISO", "10": "GND_ISO", "11": "GND_ISO", "12": "ISO_RX_BUF", "14": "ISO_TX",
            "15": "GND_ISO", "16": "VISO"}, False),
    "C14": (C0805, "10uF", "C15850", 38.0, 41.0, 0, {"1": "+3V3", "2": "GND"}, False),
    "C16": (C0603, "100nF", "C14663", 38.0, 43.5, 0, {"1": "+3V3", "2": "GND"}, False),
    "C17": (C0603, "1uF", "C15849", 38.0, 48.5, 0, {"1": "+3V3", "2": "GND"}, False),
    "C15": (C0805, "10uF", "C15850", 56.0, 38.5, 0, {"1": "VISO", "2": "GND_ISO"}, False),
    "C18": (C0603, "100nF", "C14663", 56.0, 41.0, 0, {"1": "VISO", "2": "GND_ISO"}, False),
    # U4 was 74LVC1G17W5-7 (Diodes, C151394; 94 pcs left at JLCPCB on 2026-11-11). The TI part has the same
    # pinout and fits the same pads, but JLCPCB draws it a quarter turn from the Diodes one: see fab/fab.sh.
    "U4": (lc("SOT-25-5_L3.0-W1.8-P0.95-LS3.0-BL"), "SN74LVC1G17DBVR", "C7836", 59.0, 47.5, 0,
           {"2": "ISO_RX_IN", "3": "GND_ISO", "4": "ISO_RX_BUF", "5": "VISO"}, False),
    "C21": (C0603, "100nF", "C14663", 59.0, 44.0, 0, {"1": "VISO", "2": "GND_ISO"}, False),
    "R8": (R0603, "10k", "C25804", 60.5, 52.5, 90, {"1": "VISO", "2": "ISO_RX_IN"}, False),
    "R7": (R0603, "220R", "C22962", 64.5, 52.5, 0, {"1": "PORT_DP", "2": "ISO_RX_IN"}, False),
    "R6": (R0603, "100R", "C22775", 63.5, 42.0, 0, {"1": "ISO_TX", "2": "PORT_DM"}, False),
    "D3": (std("Package_TO_SOT_SMD", "SOT-23"), "PESD5V0S2BT", "C49338", 70.5, 55.5, 0,
           {"1": "PORT_DM", "2": "PORT_DP", "3": "GND_ISO"}, False),
    "J6": (std("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12"), "UART-ISO", "C165948", 76.0, 47.0, 90,
           {"A6": "PORT_DP", "B6": "PORT_DP", "A7": "PORT_DM", "B7": "PORT_DM",
            "A1": "GND_ISO", "A12": "GND_ISO", "B1": "GND_ISO", "B12": "GND_ISO", "S1": "GND_ISO",
            "A4": "VBUS_NC", "A9": "VBUS_NC", "B4": "VBUS_NC", "B9": "VBUS_NC"}, False),
}

# Final placement (x, y, rotation); overrides the coordinates written in PARTS.
POS = {
    # power input chain, right to left along y = 16
    "J1": (69.5, 8.0, 90), "F1": (69.6, 16.0, 0), "D1": (63.0, 16.0, 0), "D2": (57.0, 15.5, 90),
    "C1": (53.0, 15.5, 90), "L1": (48.9, 15.5, 180), "C5": (50.1, 5.6, 0), "C2": (43.6, 4.2, 270),
    # buck: input caps directly above VIN/PGND pins, boot cap under BOOT/SW, inductor under SW
    "U1": (38.0, 13.0, 180), "C3": (39.3, 5.8, 0), "C4": (39.3, 8.2, 0),
    "C6": (39.6, 17.9, 0), "C7": (37.37, 18.3, 270), "R2": (34.0, 16.0, 180), "R1": (34.0, 17.6, 0),
    "L2": (43.2, 22.2, 0), "C8": (49.0, 22.2, 90), "C9": (51.3, 22.2, 90), "C10": (53.6, 22.2, 90),
    # ESP32 module support parts, left of the module
    "C12": (2.9, 8.3, 90), "C11": (2.6, 12.1, 270), "C13": (2.6, 15.15, 180), "R9": (2.6, 16.7, 0),
    # W5500: crystal on pins 30/31, decoupling on the right-hand pin row
    "Y1": (26.0, 30.7, 180), "C34": (29.6, 29.85, 0), "C35": (22.3, 30.5, 180), "R10": (26.5, 27.9, 180),
    "C33": (30.2, 32.9, 180), "R19": (32.6, 28.4, 0), "R20": (32.6, 30.0, 0),
    "C27": (33.3, 36.0, 0), "C31": (33.3, 37.8, 0), "C26": (33.3, 39.3, 0), "C30": (33.3, 40.8, 0),
    "C32": (33.0, 42.95, 0), "FB1": (32.6, 45.6, 90), "C28": (29.0, 45.0, 0),
    # Ethernet termination between the W5500 MDI pins and the jack
    "R12": (21.7, 44.275, 270), "C29": (17.9, 44.0, 180), "R11": (20.2, 45.1, 270),
    "R15": (23.6, 46.9, 180), "R14": (27.4, 46.9, 0), "C25": (30.0, 48.6, 0),
    "C24": (23.2, 48.4, 180), "C23": (23.2, 49.9, 180), "R18": (27.4, 49.2, 270),
    "C22": (15.0, 42.4, 180), "R13": (18.0, 42.4, 180),
    "R16": (21.4, 55.6, 0), "R17": (21.4, 57.2, 0), "J5": (31.0, 63.4, 90),
    "R3": (37.4, 28.6, 0), "LED1": (40.4, 28.6, 0), "R4": (37.4, 30.6, 0), "LED2": (40.4, 30.6, 0),
    "SW2": (39.4, 36.6, 0), "SW1": (35.0, 59.0, 0),
    # isolator: 100 nF within 2 mm of the supply pins, on the IC layer
    "C16": (39.6, 41.2, 270), "C14": (37.75, 41.2, 270), "C17": (39.6, 48.8, 270),
    "U3": (47.0, 45.0, 0), "C18": (54.4, 41.2, 270), "C15": (56.25, 41.2, 270), "U4": (59.0, 47.5, 0),
    "C21": (59.0, 44.0, 0), "R6": (63.5, 42.0, 0), "R8": (60.5, 52.5, 90), "R7": (64.5, 52.5, 0),
    "D3": (70.5, 55.5, 0), "J6": (76.0, 47.0, 90),
}
