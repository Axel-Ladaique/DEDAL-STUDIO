"""
============================================================================
dedal_crsf.py
----------------------------------------------------------------------------
Parser CRSF Python pour DEDAL Studio.

Decode les trames CRSF standard (BATTERY, ATTITUDE, GPS, VARIO, BARO_ALT,
FLIGHT_MODE, LINK_STATS) ET les trames custom DEDAL (OUTPUTS, STATE, CELLS,
MAG) en provenance :
  - du Teensy directement via USB (debug au sol)
  - de la TX16S via USB passthrough (monitoring en vol)

Usage simple en standalone :
    python dedal_crsf.py --port COM5
    python dedal_crsf.py --port /dev/ttyACM0 --log telemetry.csv

Usage en lib dans DEDAL Studio :
    from dedal_crsf import CRSFReader, TELEMETRY_STATE
    reader = CRSFReader('COM5')
    reader.start()
    # ... dans le main loop UI :
    voltage = TELEMETRY_STATE.get('battery_voltage', 0)

Auteur : Axel (Claude assist)
============================================================================
"""

import argparse
import csv
import struct
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

import serial

# ---------------------------------------------------------------------------
# Constantes du protocole
# ---------------------------------------------------------------------------

CRSF_SYNC_BYTE = 0xC8
CRSF_VALID_SYNC = {0xC8, 0xEA, 0xEE, 0x00}  # EdgeTX mirror uses 0xEA
CRSF_MAX_PACKET = 64

# Types standard
FT_GPS                = 0x02
FT_VARIO              = 0x07
FT_BATTERY            = 0x08
FT_BARO_ALT           = 0x09
FT_LINK_STATS         = 0x14
FT_RC_CHANNELS        = 0x16
FT_ATTITUDE           = 0x1E
FT_FLIGHT_MODE        = 0x21

# Types custom DEDAL
FT_DEDAL_OUTPUTS      = 0xA0
FT_DEDAL_STATE        = 0xA1
FT_DEDAL_CELLS        = 0xA2
FT_DEDAL_MAG          = 0xA3

# Flags DEDAL_STATE
FLAG_ARMED       = 1 << 0
FLAG_GPS_VALID   = 1 << 1
FLAG_BARO_VALID  = 1 << 2
FLAG_MAG_VALID   = 1 << 3
FLAG_HOME_SET    = 1 << 4
FLAG_FAILSAFE    = 1 << 5
FLAG_LOW_BATT    = 1 << 6
FLAG_HIGH_VIBE   = 1 << 7

# Table CRC8 DVB-S2 poly 0xD5 - meme que cote Teensy
CRC8_TABLE = bytes([
    0x00, 0xD5, 0x7F, 0xAA, 0xFE, 0x2B, 0x81, 0x54, 0x29, 0xFC, 0x56, 0x83, 0xD7, 0x02, 0xA8, 0x7D,
    0x52, 0x87, 0x2D, 0xF8, 0xAC, 0x79, 0xD3, 0x06, 0x7B, 0xAE, 0x04, 0xD1, 0x85, 0x50, 0xFA, 0x2F,
    0xA4, 0x71, 0xDB, 0x0E, 0x5A, 0x8F, 0x25, 0xF0, 0x8D, 0x58, 0xF2, 0x27, 0x73, 0xA6, 0x0C, 0xD9,
    0xF6, 0x23, 0x89, 0x5C, 0x08, 0xDD, 0x77, 0xA2, 0xDF, 0x0A, 0xA0, 0x75, 0x21, 0xF4, 0x5E, 0x8B,
    0x9D, 0x48, 0xE2, 0x37, 0x63, 0xB6, 0x1C, 0xC9, 0xB4, 0x61, 0xCB, 0x1E, 0x4A, 0x9F, 0x35, 0xE0,
    0xCF, 0x1A, 0xB0, 0x65, 0x31, 0xE4, 0x4E, 0x9B, 0xE6, 0x33, 0x99, 0x4C, 0x18, 0xCD, 0x67, 0xB2,
    0x39, 0xEC, 0x46, 0x93, 0xC7, 0x12, 0xB8, 0x6D, 0x10, 0xC5, 0x6F, 0xBA, 0xEE, 0x3B, 0x91, 0x44,
    0x6B, 0xBE, 0x14, 0xC1, 0x95, 0x40, 0xEA, 0x3F, 0x42, 0x97, 0x3D, 0xE8, 0xBC, 0x69, 0xC3, 0x16,
    0xEF, 0x3A, 0x90, 0x45, 0x11, 0xC4, 0x6E, 0xBB, 0xC6, 0x13, 0xB9, 0x6C, 0x38, 0xED, 0x47, 0x92,
    0xBD, 0x68, 0xC2, 0x17, 0x43, 0x96, 0x3C, 0xE9, 0x94, 0x41, 0xEB, 0x3E, 0x6A, 0xBF, 0x15, 0xC0,
    0x4B, 0x9E, 0x34, 0xE1, 0xB5, 0x60, 0xCA, 0x1F, 0x62, 0xB7, 0x1D, 0xC8, 0x9C, 0x49, 0xE3, 0x36,
    0x19, 0xCC, 0x66, 0xB3, 0xE7, 0x32, 0x98, 0x4D, 0x30, 0xE5, 0x4F, 0x9A, 0xCE, 0x1B, 0xB1, 0x64,
    0x72, 0xA7, 0x0D, 0xD8, 0x8C, 0x59, 0xF3, 0x26, 0x5B, 0x8E, 0x24, 0xF1, 0xA5, 0x70, 0xDA, 0x0F,
    0x20, 0xF5, 0x5F, 0x8A, 0xDE, 0x0B, 0xA1, 0x74, 0x09, 0xDC, 0x76, 0xA3, 0xF7, 0x22, 0x88, 0x5D,
    0xD6, 0x03, 0xA9, 0x7C, 0x28, 0xFD, 0x57, 0x82, 0xFF, 0x2A, 0x80, 0x55, 0x01, 0xD4, 0x7E, 0xAB,
    0x84, 0x51, 0xFB, 0x2E, 0x7A, 0xAF, 0x05, 0xD0, 0xAD, 0x78, 0xD2, 0x07, 0x53, 0x86, 0x2C, 0xF9
])


def crc8(data: bytes) -> int:
    """CRC8 DVB-S2 (poly 0xD5) - meme algo que cote Teensy."""
    crc = 0
    for b in data:
        crc = CRC8_TABLE[crc ^ b]
    return crc


# ---------------------------------------------------------------------------
# Etat global de telemetrie (partage entre thread reader et UI)
# ---------------------------------------------------------------------------

TELEMETRY_STATE: Dict[str, object] = {}
TELEMETRY_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Decodeurs de trames
# ---------------------------------------------------------------------------

def decode_battery(p: bytes) -> dict:
    """BATTERY_SENSOR (0x08) - 8 octets"""
    v_dV = struct.unpack('>H', p[0:2])[0]
    c_dA = struct.unpack('>H', p[2:4])[0]
    cap = (p[4] << 16) | (p[5] << 8) | p[6]
    pct = p[7]
    return {
        'battery_voltage':   v_dV / 10.0,
        'battery_current':   c_dA / 10.0,
        'battery_capacity':  cap,
        'battery_percent':   pct,
    }


def decode_attitude(p: bytes) -> dict:
    """ATTITUDE (0x1E) - 6 octets"""
    pitch, roll, yaw = struct.unpack('>hhh', p[0:6])
    rad2deg = 57.29577951308232
    return {
        'attitude_pitch_deg': (pitch / 10000.0) * rad2deg,
        'attitude_roll_deg':  (roll  / 10000.0) * rad2deg,
        'attitude_yaw_deg':   (yaw   / 10000.0) * rad2deg,
    }


def decode_gps(p: bytes) -> dict:
    """GPS (0x02) - 15 octets"""
    lat = struct.unpack('>i', p[0:4])[0] / 1e7
    lon = struct.unpack('>i', p[4:8])[0] / 1e7
    spd = struct.unpack('>H', p[8:10])[0] / 10.0
    hdg = struct.unpack('>H', p[10:12])[0] / 100.0
    alt = struct.unpack('>H', p[12:14])[0] - 1000
    sats = p[14]
    return {
        'gps_lat':       lat,
        'gps_lon':       lon,
        'gps_speed_kmh': spd,
        'gps_heading':   hdg,
        'gps_alt_m':     alt,
        'gps_sats':      sats,
    }


def decode_vario(p: bytes) -> dict:
    """VARIO (0x07) - 2 octets"""
    vs = struct.unpack('>h', p[0:2])[0]
    return {'vario_m_s': vs / 100.0}


def decode_baro_alt(p: bytes) -> dict:
    """BARO_ALT (0x09) - 2 octets"""
    a = struct.unpack('>H', p[0:2])[0]
    return {'baro_alt_m': (a - 10000) / 10.0}


def decode_flight_mode(p: bytes) -> dict:
    """FLIGHT_MODE (0x21) - string null-term"""
    s = p.split(b'\x00', 1)[0].decode('ascii', errors='replace')
    return {'flight_mode': s}


def decode_link_stats(p: bytes) -> dict:
    """LINK_STATISTICS (0x14) - 10 octets"""
    return {
        'link_rssi_1':       -p[0],
        'link_rssi_2':       -p[1],
        'link_lq':            p[2],
        'link_snr':           struct.unpack('b', p[3:4])[0],
        'link_active_ant':    p[4],
        'link_rf_mode':       p[5],
        'link_tx_power_idx':  p[6],
        'link_dl_rssi':      -p[7],
        'link_dl_lq':         p[8],
        'link_dl_snr':        struct.unpack('b', p[9:10])[0],
    }


def decode_dedal_outputs(p: bytes) -> dict:
    """DEDAL_OUTPUTS (0xA0) - 26 octets : 6 moteurs + 7 servos en us"""
    motors = struct.unpack('>6H', p[0:12])
    servos = struct.unpack('>7H', p[12:26])
    out = {}
    for i in range(6):
        out[f'motor_M{i+1}_us'] = motors[i]
    for i in range(7):
        out[f'servo_S{i+1}_us'] = servos[i]
    return out


def decode_dedal_state(p: bytes) -> dict:
    """DEDAL_STATE (0xA1) - 12 octets"""
    arming_ms = struct.unpack('>I', p[0:4])[0]
    dist = struct.unpack('>H', p[4:6])[0]
    bearing = struct.unpack('>H', p[6:8])[0] / 100.0
    loop_us = struct.unpack('>H', p[8:10])[0]
    flags = p[10]
    return {
        'arming_time_s':   arming_ms / 1000.0,
        'distance_home_m': dist,
        'bearing_home':    bearing,
        'loop_time_us':    loop_us,
        'flag_armed':       bool(flags & FLAG_ARMED),
        'flag_gps_valid':   bool(flags & FLAG_GPS_VALID),
        'flag_baro_valid':  bool(flags & FLAG_BARO_VALID),
        'flag_mag_valid':   bool(flags & FLAG_MAG_VALID),
        'flag_home_set':    bool(flags & FLAG_HOME_SET),
        'flag_failsafe':    bool(flags & FLAG_FAILSAFE),
        'flag_low_batt':    bool(flags & FLAG_LOW_BATT),
        'flag_high_vibe':   bool(flags & FLAG_HIGH_VIBE),
    }


def decode_dedal_cells(p: bytes) -> dict:
    """DEDAL_CELLS (0xA2) - 1 + 2N octets"""
    n = p[0]
    if n == 0 or len(p) < 1 + 2*n:
        return {}
    cells = struct.unpack(f'>{n}H', p[1:1+2*n])
    out = {'cell_count': n}
    for i, mv in enumerate(cells):
        out[f'cell_{i+1}_V'] = mv / 1000.0
    return out


def decode_dedal_mag(p: bytes) -> dict:
    """DEDAL_MAG (0xA3) - 8 octets"""
    hdg = struct.unpack('>H', p[0:2])[0] / 100.0
    mx, my, mz = struct.unpack('>3h', p[2:8])
    return {
        'mag_heading_deg': hdg,
        'mag_x_uT':        mx / 10.0,
        'mag_y_uT':        my / 10.0,
        'mag_z_uT':        mz / 10.0,
    }


def decode_rc_channels(p: bytes) -> dict:
    """RC_CHANNELS_PACKED (0x16) - 22 octets, 16 canaux x 11 bits"""
    bits = int.from_bytes(p[0:22], 'little')
    chans = []
    for i in range(16):
        t = (bits >> (i * 11)) & 0x7FF
        us = int(t * 5 / 8 + 880)
        chans.append(us)
    return {f'rc_ch{i+1}_us': v for i, v in enumerate(chans)}


# Table de dispatch
DECODERS: Dict[int, Callable[[bytes], dict]] = {
    FT_BATTERY:        decode_battery,
    FT_ATTITUDE:       decode_attitude,
    FT_GPS:            decode_gps,
    FT_VARIO:          decode_vario,
    FT_BARO_ALT:       decode_baro_alt,
    FT_FLIGHT_MODE:    decode_flight_mode,
    FT_LINK_STATS:     decode_link_stats,
    FT_RC_CHANNELS:    decode_rc_channels,
    FT_DEDAL_OUTPUTS:  decode_dedal_outputs,
    FT_DEDAL_STATE:    decode_dedal_state,
    FT_DEDAL_CELLS:    decode_dedal_cells,
    FT_DEDAL_MAG:      decode_dedal_mag,
}

FRAME_NAMES = {
    FT_BATTERY:        'BATTERY',
    FT_ATTITUDE:       'ATTITUDE',
    FT_GPS:             'GPS',
    FT_VARIO:           'VARIO',
    FT_BARO_ALT:        'BARO_ALT',
    FT_FLIGHT_MODE:     'FLIGHT_MODE',
    FT_LINK_STATS:      'LINK_STATS',
    FT_RC_CHANNELS:     'RC_CHANNELS',
    FT_DEDAL_OUTPUTS:   'DEDAL_OUTPUTS',
    FT_DEDAL_STATE:     'DEDAL_STATE',
    FT_DEDAL_CELLS:     'DEDAL_CELLS',
    FT_DEDAL_MAG:       'DEDAL_MAG',
}


# ---------------------------------------------------------------------------
# Lecteur CRSF threade
# ---------------------------------------------------------------------------

class CRSFReader:
    """
    Lecteur CRSF en thread separe. Parse les trames en continu et met a jour
    TELEMETRY_STATE (dict thread-safe).
    """

    def __init__(self, port: str, baud: int = 921600, on_frame: Optional[Callable] = None):
        """
        :param port:      port serie (COM5, /dev/ttyACM0, etc.)
        :param baud:      baudrate (921600 pour TX16S USB, 500000 pour Teensy USB)
        :param on_frame:  callback(frame_type, decoded_dict) appele a chaque trame valide
        """
        self.port = port
        self.baud = baud
        self.on_frame = on_frame
        self.ser: Optional[serial.Serial] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.stats = {
            'frames_ok':  0,
            'crc_errors': 0,
            'bad_length': 0,
            'unknown_type': 0,
        }

    def start(self):
        self.ser = serial.Serial(self.port, self.baud, timeout=0.02)
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        if self.ser:
            self.ser.close()

    def _loop(self):
        ser = self.ser
        while not self._stop.is_set():
            try:
                b = ser.read(1)
                if not b:
                    continue
                if b[0] not in CRSF_VALID_SYNC:
                    continue

                # Lire length
                lb = ser.read(1)
                if not lb:
                    continue
                length = lb[0]
                if length < 2 or length > 62:
                    self.stats['bad_length'] += 1
                    continue

                # Lire type + payload + crc
                rest = ser.read(length)
                if len(rest) != length:
                    continue

                ftype = rest[0]
                payload = rest[1:-1]
                recv_crc = rest[-1]
                comp_crc = crc8(bytes([ftype]) + payload)

                if recv_crc != comp_crc:
                    self.stats['crc_errors'] += 1
                    continue

                self.stats['frames_ok'] += 1

                # Decoder
                dec = DECODERS.get(ftype)
                if dec is None:
                    self.stats['unknown_type'] += 1
                    continue

                try:
                    data = dec(payload)
                except Exception as e:
                    print(f"[ERR] decode {FRAME_NAMES.get(ftype, hex(ftype))}: {e}",
                          file=sys.stderr)
                    continue

                # Update global state
                with TELEMETRY_LOCK:
                    TELEMETRY_STATE.update(data)
                    TELEMETRY_STATE['last_update_ts'] = time.time()

                # Callback eventuel
                if self.on_frame:
                    self.on_frame(ftype, data)

            except serial.SerialException as e:
                print(f"[SERIAL] {e}", file=sys.stderr)
                time.sleep(0.5)
            except Exception as e:
                print(f"[LOOP] {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CSV logger optionnel
# ---------------------------------------------------------------------------

class CSVLogger:
    def __init__(self, filepath: str, interval_s: float = 0.1):
        self.filepath = filepath
        self.interval_s = interval_s
        self.fh = open(filepath, 'w', newline='')
        self.writer: Optional[csv.DictWriter] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self.fh.close()

    def _loop(self):
        while not self._stop.is_set():
            with TELEMETRY_LOCK:
                snapshot = dict(TELEMETRY_STATE)
            if snapshot:
                if self.writer is None:
                    self.writer = csv.DictWriter(self.fh, fieldnames=sorted(snapshot.keys()))
                    self.writer.writeheader()
                else:
                    # Si nouvelles cles : on les ajoute pas (CSV fige sur la 1re ligne)
                    pass
                row = {k: snapshot.get(k, '') for k in self.writer.fieldnames}
                self.writer.writerow(row)
                self.fh.flush()
            time.sleep(self.interval_s)


# ---------------------------------------------------------------------------
# Main standalone (debug)
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="DEDAL CRSF telemetry reader")
    ap.add_argument('--port', required=True, help="Port serie (COM5, /dev/ttyACM0, ...)")
    ap.add_argument('--baud', type=int, default=921600, help="Baudrate (921600 par defaut)")
    ap.add_argument('--log', default=None, help="Fichier CSV pour enregistrer")
    ap.add_argument('--rate', type=float, default=1.0, help="Frequence d'affichage Hz")
    args = ap.parse_args()

    reader = CRSFReader(args.port, args.baud)
    reader.start()

    logger = None
    if args.log:
        logger = CSVLogger(args.log, interval_s=0.05)  # 20 Hz log
        logger.start()
        print(f"[LOG] Enregistrement -> {args.log}")

    print(f"[DEDAL] Lecture sur {args.port} @ {args.baud} bauds")
    print(f"[DEDAL] Ctrl-C pour arreter\n")

    try:
        while True:
            with TELEMETRY_LOCK:
                s = dict(TELEMETRY_STATE)

            # Affichage condense
            print("\033[2J\033[H", end='')  # clear screen ANSI
            print(f"=== DEDAL telemetry @ {time.strftime('%H:%M:%S')} ===")
            print(f"frames OK={reader.stats['frames_ok']:6d}  CRC err={reader.stats['crc_errors']:3d}  unknown={reader.stats['unknown_type']:3d}")
            print()
            if 'battery_voltage' in s:
                print(f"BAT    : {s['battery_voltage']:5.2f} V  {s.get('battery_current', 0):5.2f} A  {s.get('battery_percent', 0):3d} %  {s.get('battery_capacity', 0):5d} mAh")
            if 'cell_count' in s:
                cs = [s.get(f'cell_{i+1}_V', 0) for i in range(s['cell_count'])]
                print(f"CELLS  : " + " ".join(f"{v:.3f}" for v in cs) + " V")
            if 'attitude_pitch_deg' in s:
                print(f"ATT    : P={s['attitude_pitch_deg']:+6.1f}  R={s['attitude_roll_deg']:+6.1f}  Y={s['attitude_yaw_deg']:+6.1f} deg")
            if 'gps_lat' in s:
                print(f"GPS    : {s['gps_lat']:.6f}, {s['gps_lon']:.6f}  spd={s.get('gps_speed_kmh',0):.1f} km/h  alt={s.get('gps_alt_m',0)} m  sats={s.get('gps_sats',0)}")
            if 'vario_m_s' in s:
                print(f"VARIO  : {s['vario_m_s']:+5.2f} m/s   baro={s.get('baro_alt_m', 0):.1f} m")
            if 'flight_mode' in s:
                print(f"MODE   : {s['flight_mode']}")
            if 'link_lq' in s:
                print(f"LINK   : LQ={s['link_lq']:3d}%  RSSI={s['link_rssi_1']} dBm  SNR={s['link_snr']} dB")
            if 'arming_time_s' in s:
                t = s['arming_time_s']
                print(f"ARMING : {int(t//60):02d}:{int(t%60):02d}  dist_home={s.get('distance_home_m',0)} m  bearing={s.get('bearing_home',0):.1f} deg  loop={s.get('loop_time_us',0)} us")
                flags = [k.replace('flag_','').upper() for k in s if k.startswith('flag_') and s[k]]
                print(f"FLAGS  : " + " ".join(flags))
            if 'motor_M1_us' in s:
                ms = [s.get(f'motor_M{i+1}_us', 0) for i in range(6)]
                ss = [s.get(f'servo_S{i+1}_us', 0) for i in range(7)]
                print(f"MOTORS : " + " ".join(f"{v:4d}" for v in ms))
                print(f"SERVOS : " + " ".join(f"{v:4d}" for v in ss))
            if 'mag_heading_deg' in s:
                print(f"MAG    : hdg={s['mag_heading_deg']:6.2f} deg  ({s.get('mag_x_uT',0):+.1f}, {s.get('mag_y_uT',0):+.1f}, {s.get('mag_z_uT',0):+.1f}) uT")

            time.sleep(1.0 / args.rate)
    except KeyboardInterrupt:
        print("\n[DEDAL] Arret demande")
    finally:
        reader.stop()
        if logger:
            logger.stop()


if __name__ == '__main__':
    main()
