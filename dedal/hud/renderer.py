"""HUD renderer — extracted from hud_generator.py v7.

Contains only the drawing code: palette, FlightFrame dataclass,
build_gps_map(), and ProfessionalHUD class.

EKF, CSV parsing, and video generation have been removed; those
values come pre-computed from flight_pack.json.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

HUD_VERSION = "v7"

# ── Palette (BGR, alpha separate) ─────────────────────────────────────────
C = {
    "bg":      (  8,  10,  14),
    "surface": ( 14,  18,  26),
    "border":  ( 45,  35,  20),
    "accent":  (255, 205,   0),
    "accent2": ( 35,  80, 255),
    "accent3": ( 14, 230,  50),
    "warn":    (  0, 130, 255),
    "text":    (200, 195, 180),
    "dim":     ( 55,  47,  36),
    "sky_top": (140,  70,  25),
    "sky_bot": (190, 130,  60),
    "gnd_top": ( 35,  60,  90),
    "gnd_bot": ( 16,  28,  44),
}

A_PANEL  = 210
A_BORDER = 255
A_DIM    = 160

def bgra(col: tuple, a: int = 255) -> tuple:
    return (*col, a)

FM_LABELS = {0: "HOVER", 1: "TRANS", 2: "PLANE"}
FM_COLORS = {0: C["accent3"], 1: C["accent"], 2: C["warn"]}
RE = 6_371_000.0
G  = 9.80665


# ── Flight frame (one row of telemetry) ───────────────────────────────────
@dataclass
class FlightFrame:
    timestamp_us: int
    armed:        int   = 0
    flight_mode:  int   = 0
    pitch_deg:    float = 0.0
    roll_deg:     float = 0.0
    yaw_deg:      float = 0.0
    gps_alt_m:    float = 0.0
    gps_speed_ms: float = 0.0
    gps_lat:      float = 0.0
    gps_lon:      float = 0.0
    gps_sats:     int   = 0
    gps_valid:    int   = 0
    m1_pwm:       int   = 0
    m3_pwm:       int   = 0
    vbat_v:       float = 0.0
    accel_z:      float = 1.0
    # EKF velocities — pre-computed by the viewer and stored in flight_pack.json
    Vfwd:         float = 0.0
    Vlat:         float = 0.0
    Vz:           float = 0.0
    Vh:           float = 0.0


# ── GPS trajectory map ─────────────────────────────────────────────────────
def build_gps_map(
    frames: list[FlightFrame],
    W: int,
    H: int,
    min_sats: int = 0,
) -> tuple | None:
    valid = [
        (f.gps_lat, f.gps_lon, i)
        for i, f in enumerate(frames)
        if f.gps_valid and f.gps_lat != 0 and f.gps_sats >= min_sats
    ]
    if len(valid) < 4:
        return None

    avg_lat = math.radians(sum(v[0] for v in valid) / len(valid))
    ref_lat, ref_lon = valid[0][0], valid[0][1]

    def to_m(lat: float, lon: float) -> tuple[float, float]:
        return (
            RE * math.cos(avg_lat) * math.radians(lon - ref_lon),
            RE * math.radians(lat - ref_lat),
        )

    coords = [to_m(v[0], v[1]) for v in valid]
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    PAD = 16
    rx = max(max(xs) - min(xs), 1.0)
    ry = max(max(ys) - min(ys), 1.0)
    sc = min((W - 2 * PAD) / rx, (H - 2 * PAD) / ry)
    ox = PAD - min(xs) * sc
    oy = H - PAD + min(ys) * sc

    def to_px(lat: float, lon: float) -> tuple[int, int]:
        ex, ey = to_m(lat, lon)
        return (int(ox + ex * sc), int(oy - ey * sc))

    bg = np.zeros((H, W, 4), dtype=np.uint8)
    cv2.rectangle(bg, (0, 0), (W, H), bgra(C["surface"], 160), -1)
    for i in range(5):
        gx = PAD + (W - 2 * PAD) * i // 4
        gy = PAD + (H - 2 * PAD) * i // 4
        cv2.line(bg, (gx, PAD), (gx, H - PAD), bgra((22, 28, 36), 180), 1)
        cv2.line(bg, (PAD, gy), (W - PAD, gy), bgra((22, 28, 36), 180), 1)
    cv2.arrowedLine(bg, (W - 22, 26), (W - 22, 8), bgra(C["dim"], 200), 1, tipLength=0.5)
    cv2.putText(bg, "N", (W - 27, 36), cv2.FONT_HERSHEY_PLAIN, 0.85, bgra(C["dim"], 200), 1)
    prev = None
    for lat, lon, _ in valid:
        px = to_px(lat, lon)
        if prev:
            cv2.line(bg, prev, px, bgra(C["dim"], 180), 1)
        prev = px

    pts_px: list[tuple[int, int] | None] = [None] * len(frames)
    for lat, lon, i in valid:
        pts_px[i] = to_px(lat, lon)
    return bg, pts_px


# ── HUD Renderer (RGBA transparent background) ────────────────────────────
class ProfessionalHUD:
    def __init__(
        self,
        w: int,
        h: int,
        cells: int = 6,
        gps_map_data: tuple | None = None,
        min_gps_sats: int = 0,
    ) -> None:
        self.w = w
        self.h = h
        self.sc = min(w, h) / 1080.0
        self.cells = cells
        self.min_gps_sats = min_gps_sats
        self.font_d = cv2.FONT_HERSHEY_DUPLEX
        self.font_p = cv2.FONT_HERSHEY_PLAIN
        self.gps_map_bg = None
        self.gps_pts_px = None
        if gps_map_data:
            self.gps_map_bg, self.gps_pts_px = gps_map_data

    def _s(self, v: float) -> int:
        return max(1, int(v * self.sc))

    # ── Primitives ────────────────────────────────────────────────────────
    def _panel(self, f, x1, y1, x2, y2, title="", col=None, fill=True):
        col = col or C["accent"]
        if fill:
            cv2.rectangle(f, (x1, y1), (x2, y2), bgra(C["surface"], A_PANEL), -1)
        L = min(self._s(14), (x2 - x1) // 4, (y2 - y1) // 4)
        for bx, by, sx, sy in [
            (x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)
        ]:
            cv2.line(f, (bx, by), (bx + sx * L, by), bgra(col, A_BORDER), 1)
            cv2.line(f, (bx, by), (bx, by + sy * L), bgra(col, A_BORDER), 1)
        if title:
            cv2.putText(
                f, title, (x1 + self._s(5), y1 + self._s(12)),
                self.font_p, self.sc * 0.78, bgra(col, A_BORDER), 1, cv2.LINE_AA,
            )
            cv2.line(
                f, (x1 + self._s(5), y1 + self._s(15)),
                (x2 - self._s(5), y1 + self._s(15)), bgra(col, A_DIM), 1,
            )

    def _txt(self, f, text, pos, font, fs, col, thick=1, a=A_BORDER):
        cv2.putText(f, text, pos, font, fs, bgra(col, a), thick, cv2.LINE_AA)

    def _line(self, f, p1, p2, col, thick=1, a=A_BORDER):
        cv2.line(f, p1, p2, bgra(col, a), thick)

    def _circle(self, f, center, r, col, thick=-1, a=A_BORDER):
        cv2.circle(f, center, r, bgra(col, a), thick)

    def _rect(self, f, p1, p2, col, thick=-1, a=A_BORDER):
        cv2.rectangle(f, p1, p2, bgra(col, a), thick)

    def _vbar(self, f, cx, y_bot, bar_h, val, vmin, vmax, col_fn, bw):
        t = float(np.clip((val - vmin) / max(vmax - vmin, 1e-6), 0, 1))
        fh = int(bar_h * t)
        self._rect(f, (cx - bw // 2, y_bot - bar_h), (cx + bw // 2, y_bot), C["border"], a=A_DIM)
        if fh > 0:
            self._rect(f, (cx - bw // 2, y_bot - fh), (cx + bw // 2, y_bot), col_fn(t), a=A_BORDER)
        for q in (0.25, 0.5, 0.75):
            gy = y_bot - int(bar_h * q)
            self._line(f, (cx - bw // 2, gy), (cx + bw // 2, gy), (0, 0, 0), a=180)

    # ── Top bar ───────────────────────────────────────────────────────────
    def render_top_bar(self, f, fl: FlightFrame, t0_us: int) -> None:
        x1 = self._s(8); x2 = self.w - self._s(8)
        y1 = self._s(6); y2 = self._s(64)
        self._rect(f, (x1, y1), (x2, y2), C["surface"], a=A_PANEL)
        for bx, by, sx, sy in [(x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)]:
            L = self._s(12)
            self._line(f, (bx, by), (bx + sx * L, by), C["accent"], a=A_BORDER)
            self._line(f, (bx, by), (bx, by + sy * L), C["accent"], a=A_BORDER)

        cy = (y1 + y2) // 2 + self._s(7)
        x = x1 + self._s(12)
        fs = self.sc * 0.88

        armed = fl.armed == 1
        acol = C["accent3"] if armed else C["accent2"]
        self._circle(f, (x, cy - self._s(3)), self._s(5), acol)
        x += self._s(12)
        arm_txt = "ARM" if armed else "DIS"
        (tw, _), _ = cv2.getTextSize(arm_txt, self.font_d, fs * 1.1, self._s(2))
        self._txt(f, arm_txt, (x, cy), self.font_d, fs * 1.1, acol, self._s(2))
        x += tw + self._s(14)
        self._line(f, (x, y1 + self._s(8)), (x, y2 - self._s(8)), C["border"], a=A_DIM)
        x += self._s(12)

        gcol = C["accent3"] if fl.gps_sats >= 6 else C["warn"] if fl.gps_sats >= 4 else C["accent2"]
        gps_txt = f"GPS {fl.gps_sats} SAT"
        (tw, _), _ = cv2.getTextSize(gps_txt, self.font_p, fs, 1)
        self._txt(f, gps_txt, (x, cy), self.font_p, fs, gcol)
        x += tw + self._s(14)
        self._line(f, (x, y1 + self._s(8)), (x, y2 - self._s(8)), C["border"], a=A_DIM)
        x += self._s(12)

        el = (fl.timestamp_us - t0_us) / 1e6
        mm, ss = divmod(el, 60)
        rec = f"REC {int(mm):02d}:{ss:04.1f}"
        (tw, _), _ = cv2.getTextSize(rec, self.font_d, fs, 1)
        self._txt(f, rec, (x, cy), self.font_d, fs, C["text"])
        x += tw + self._s(14)
        self._line(f, (x, y1 + self._s(8)), (x, y2 - self._s(8)), C["border"], a=A_DIM)
        x += self._s(12)

        fm = fl.flight_mode
        fmcol = FM_COLORS.get(fm, C["text"])
        fm_txt = FM_LABELS.get(fm, f"MODE{fm}")
        (tw, _), _ = cv2.getTextSize(fm_txt, self.font_d, fs * 1.15, self._s(2))
        self._txt(f, fm_txt, (x, cy), self.font_d, fs * 1.15, fmcol, self._s(2))
        x += tw + self._s(14)
        self._line(f, (x, y1 + self._s(8)), (x, y2 - self._s(8)), C["border"], a=A_DIM)
        x += self._s(12)

        att = f"P{fl.pitch_deg:+.1f}  R{fl.roll_deg:+.1f}  Y{fl.yaw_deg % 360:.1f}"
        self._txt(f, att, (x, cy), self.font_p, fs * 0.92, C["dim"], a=A_DIM)

        t = f"{int(mm):02d}:{ss:05.2f}"
        fs_t = self.sc * 1.5
        (tw2, _), _ = cv2.getTextSize(t, self.font_d, fs_t, 2)
        buf = np.zeros_like(f)
        cv2.putText(buf, t, (x2 - tw2 - self._s(4), cy),
                    self.font_d, fs_t, bgra(C["accent"], A_BORDER), 6, cv2.LINE_AA)
        k = self._s(11) | 1
        blurred = cv2.GaussianBlur(buf, (k, k), 0)
        tmp = f.astype(np.int16) + (blurred // 2).astype(np.int16)
        np.clip(tmp, 0, 255, out=tmp)
        f[:] = tmp.astype(np.uint8)
        self._txt(f, t, (x2 - tw2 - self._s(4), cy), self.font_d, fs_t, C["accent"], 2)

    # ── Left column ───────────────────────────────────────────────────────
    def render_left_col(self, f, fl: FlightFrame) -> None:
        x1 = self._s(8); x2 = self._s(120); pw = x2 - x1
        vcpc = fl.vbat_v / max(self.cells, 1) if fl.vbat_v > 0 else 0
        pct_c = np.clip((vcpc - 3.5) / (4.2 - 3.5), 0, 1)
        bat_col = C["accent3"] if pct_c > 0.5 else C["warn"] if pct_c > 0.2 else C["accent2"]
        g_col = C["warn"] if abs(fl.accel_z) > 2.5 else C["accent3"]

        items = [
            ("SPD", f"{fl.gps_speed_ms:.1f}", "m/s", C["accent3"]),
            ("ALT", f"{fl.gps_alt_m:.0f}",    "m",   C["accent3"]),
            ("HDG", f"{int(fl.yaw_deg) % 360}", "",   C["accent3"]),
            ("BAT", f"{vcpc:.2f}",              "V/c", bat_col),
            ("G",   f"{fl.accel_z:.2f}G",       "",    g_col),
        ]
        ih = self._s(98); y0 = self._s(72)
        for i, (lbl, val, unit, vcol) in enumerate(items):
            iy1 = y0 + i * ih; iy2 = iy1 + ih - self._s(4)
            self._panel(f, x1, iy1, x2, iy2, lbl)
            for fst in (1.35, 1.12, 0.92, 0.78):
                (tw, th), _ = cv2.getTextSize(val, self.font_d, self.sc * fst, 2)
                if tw <= pw - self._s(6):
                    fs = self.sc * fst
                    break
            tx = x1 + (pw - tw) // 2
            ty = iy1 + self._s(18) + (iy2 - iy1 - self._s(18) + th) // 2
            self._txt(f, val, (tx, ty), self.font_d, fs, vcol, self._s(2))
            if unit:
                (uw, _), _ = cv2.getTextSize(unit, self.font_p, self.sc * 0.73, 1)
                self._txt(f, unit, (x1 + (pw - uw) // 2, ty + self._s(11)),
                          self.font_p, self.sc * 0.73, C["dim"], a=A_DIM)
            if lbl == "BAT":
                bx1 = x1 + self._s(6); bx2 = x2 - self._s(6)
                self._rect(f, (bx1, iy2 - self._s(11)), (bx2, iy2 - self._s(4)), C["border"], a=A_DIM)
                fw = int((bx2 - bx1) * float(pct_c))
                if fw > 0:
                    self._rect(f, (bx1, iy2 - self._s(11)), (bx1 + fw, iy2 - self._s(4)), bat_col)

    # ── Motors M1/M3 ─────────────────────────────────────────────────────
    def render_motors(self, f, m1: int, m3: int) -> None:
        x1 = self._s(8); x2 = self._s(120)
        y_top = self._s(72) + 5 * self._s(98) + self._s(4)
        y_bot = self.h - self._s(8)
        H = y_bot - y_top
        if H < 40:
            return
        self._panel(f, x1, y_top, x2, y_bot, "MOTORS", C["accent"])
        pw = x2 - x1
        bar_h = H - self._s(48); bar_w = self._s(20)
        bar_y_bot = y_bot - self._s(20)
        cx1 = x1 + pw // 4; cx3 = x1 + 3 * pw // 4
        col_fn = lambda t: C["accent3"] if t < 0.55 else C["warn"] if t < 0.85 else C["accent2"]

        for cx, pwm, lbl in [(cx1, m3, "M3"), (cx3, m1, "M1")]:
            self._vbar(f, cx, bar_y_bot, bar_h, pwm, 125, 250, col_fn, bar_w)
            self._txt(f, lbl, (cx - self._s(7), bar_y_bot + self._s(13)), self.font_p, self.sc * 0.85, C["text"])
            val = str(pwm)
            (tw, _), _ = cv2.getTextSize(val, self.font_p, self.sc * 0.80, 1)
            self._txt(f, val, (cx - tw // 2, y_top + self._s(22)), self.font_p, self.sc * 0.80, C["dim"], a=A_DIM)
            pct = int((pwm - 125) / 125 * 100)
            pp = f"{pct}%"
            (pw2, _), _ = cv2.getTextSize(pp, self.font_p, self.sc * 0.75, 1)
            self._txt(f, pp, (cx - pw2 // 2, bar_y_bot - bar_h - self._s(3)),
                      self.font_p, self.sc * 0.75,
                      C["accent3"] if pct > 10 else C["dim"], a=A_DIM)
        self._line(f, (x1 + pw // 2, y_top + self._s(18)), (x1 + pw // 2, y_bot - self._s(5)), C["border"], a=A_DIM)

    # ── Artificial horizon ────────────────────────────────────────────────
    def render_attitude(self, f, roll: float, pitch: float, cx: int, cy: int, R: int) -> None:
        ppd = R / 22.0
        sz = (R + self._s(12)) * 2
        ax = ay = sz // 2
        ai = np.zeros((sz, sz, 3), dtype=np.uint8)
        hy = int(np.clip(ay + pitch * ppd, 0, sz))
        sk = np.array(C["sky_top"], np.float32); sb = np.array(C["sky_bot"], np.float32)
        gt = np.array(C["gnd_top"], np.float32); gb = np.array(C["gnd_bot"], np.float32)
        if hy > 0:
            ai[:hy] = cv2.resize(np.array([[sk], [sb]], dtype=np.uint8), (sz, hy), interpolation=cv2.INTER_LINEAR)
        if hy < sz:
            n = sz - hy
            ai[hy:] = cv2.resize(np.array([[gt], [gb]], dtype=np.uint8), (sz, n), interpolation=cv2.INTER_LINEAR)
        for pm in range(-40, 41, 5):
            if pm == 0:
                continue
            ym = int(hy - pm * ppd)
            if not self._s(4) < ym < sz - self._s(4):
                continue
            hw = self._s(28 if abs(pm) % 10 == 0 else 14)
            cv2.line(ai, (ax - hw, ym), (ax + hw, ym), (190, 190, 190), 1)
            if abs(pm) % 10 == 0:
                for xo in (ax + hw + self._s(3), ax - hw - self._s(14)):
                    cv2.putText(ai, str(abs(pm)), (xo, ym + self._s(4)),
                                self.font_p, 0.60 * self.sc, (185, 185, 185), 1)
        cv2.line(ai, (0, hy), (sz, hy), (255, 255, 255), self._s(2))
        M = cv2.getRotationMatrix2D((float(ax), float(ay)), roll, 1.0)
        ai = cv2.warpAffine(ai, M, (sz, sz), flags=cv2.INTER_LINEAR)

        msk = np.zeros((sz, sz), dtype=np.uint8)
        cv2.circle(msk, (ax, ay), R, 255, -1)
        x0, y0 = cx - ax, cy - ay
        sy1 = max(0, -y0); sy2 = min(sz, self.h - y0)
        sx1 = max(0, -x0); sx2 = min(sz, self.w - x0)
        if sy1 >= sy2 or sx1 >= sx2:
            return
        roi_f  = f[y0 + sy1:y0 + sy2, x0 + sx1:x0 + sx2]
        roi_ai = ai[sy1:sy2, sx1:sx2]
        roi_m  = msk[sy1:sy2, sx1:sx2]
        for c in range(3):
            roi_f[:, :, c] = np.where(roi_m, roi_ai[:, :, c], roi_f[:, :, c])
        roi_f[:, :, 3] = np.where(roi_m, 255, roi_f[:, :, 3])

        cv2.circle(f, (cx, cy), R + 4, bgra(C["border"], 200), 5)
        cv2.circle(f, (cx, cy), R + 1, bgra(C["accent"], A_BORDER), 2)
        for deg in (-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60):
            a = math.radians(deg - 90); ri = R - self._s(7); ro = R + self._s(1)
            cv2.line(f, (cx + int(ri * math.cos(a)), cy + int(ri * math.sin(a))),
                        (cx + int(ro * math.cos(a)), cy + int(ro * math.sin(a))),
                     bgra(C["accent"] if deg % 30 == 0 else C["dim"], A_BORDER),
                     2 if deg % 30 == 0 else 1)
        rr = math.radians(-roll - 90); r1 = R - self._s(3); r2 = R - self._s(13)
        p1 = (cx + int(r1 * math.cos(rr)), cy + int(r1 * math.sin(rr)))
        p2 = (cx + int(r2 * math.cos(rr)), cy + int(r2 * math.sin(rr)))
        self._line(f, p1, p2, C["accent3"], self._s(3))
        self._circle(f, p1, self._s(3), C["accent3"])
        arm = self._s(46); gap = self._s(9)
        self._line(f, (cx - arm, cy), (cx - gap, cy), C["accent3"], self._s(3))
        self._line(f, (cx + gap, cy), (cx + arm, cy), C["accent3"], self._s(3))
        self._circle(f, (cx, cy), gap, C["accent3"], self._s(2))
        self._circle(f, (cx, cy), self._s(3), C["accent3"])

    # ── 3D drone wireframe ────────────────────────────────────────────────
    def render_drone_3d(self, f, roll: float, pitch: float, yaw: float,
                        x1: int, y1: int, x2: int, y2: int) -> None:
        cx = (x1 + x2) // 2; cy = (y1 + y2) // 2
        sc = min(x2 - x1, y2 - y1) * 0.42
        self._panel(f, x1, y1, x2, y2, "3D ATT", C["accent"])
        pts = {
            "nose":    np.array([-.47,  .0,   .0 ]),
            "tail":    np.array([ .47,  .0,   .0 ]),
            "wing_l":  np.array([ .05, -.40,  .0 ]),
            "wing_r":  np.array([ .05,  .40,  .0 ]),
            "vstab_b": np.array([ .47,  .0,   .0 ]),
            "vstab_t": np.array([ .47,  .0,   .13]),
            "hstab_l": np.array([ .47, -.20,  .13]),
            "hstab_r": np.array([ .47,  .20,  .13]),
        }
        edges = [
            ("nose",    "tail",    C["accent"]),
            ("wing_l",  "wing_r",  C["accent"]),
            ("vstab_b", "vstab_t", C["accent"]),
            ("hstab_l", "vstab_t", C["dim"]),
            ("vstab_t", "hstab_r", C["dim"]),
        ]
        def Rx(a): c, s = math.cos(a), math.sin(a); return np.array([[1,0,0],[0,c,-s],[0,s,c]], np.float32)
        def Ry(a): c, s = math.cos(a), math.sin(a); return np.array([[c,0,s],[0,1,0],[-s,0,c]], np.float32)
        def Rz(a): c, s = math.cos(a), math.sin(a); return np.array([[c,-s,0],[s,c,0],[0,0,1]], np.float32)
        Rtot = (Rx(math.radians(5)) @ Rz(math.radians(5))) @ \
               (Rz(math.radians(yaw)) @ Ry(math.radians(pitch)) @ Rx(math.radians(-roll)))
        def proj(p): v = Rtot @ p; return (cx + int(sc * v[1]), cy - int(sc * v[2])), float(v[0])
        th = self._s(2)
        for a, b, col in edges:
            p1, d1 = proj(pts[a]); p2, d2 = proj(pts[b])
            al = int((0.5 + 0.5 * max(0, min(1, 0.5 - ((d1 + d2) / 2) * 0.6))) * 255)
            cv2.line(f, p1, p2, bgra(col, al), th, cv2.LINE_AA)
        for mk in ("wing_l", "wing_r"):
            p, _ = proj(pts[mk]); r = self._s(9)
            cv2.ellipse(f, p, (r, max(1, r // 3)), 0, 0, 360, bgra(C["accent3"], A_BORDER), th)
            self._circle(f, p, self._s(3), C["accent3"])
        pn, _ = proj(pts["nose"]); self._circle(f, pn, self._s(3), C["warn"])
        self._txt(f, f"R{roll:+.0f} P{pitch:+.0f}", (x1 + self._s(5), y2 - self._s(5)),
                  self.font_p, self.sc * 0.72, C["dim"], a=A_DIM)

    # ── GPS map ───────────────────────────────────────────────────────────
    def render_gps_map(self, f, frame_idx: int, x1: int, y1: int, x2: int, y2: int) -> None:
        W = x2 - x1; H = y2 - y1
        if self.gps_map_bg is None:
            self._panel(f, x1, y1, x2, y2, "GPS MAP", C["dim"])
            msg = "PAS ASSEZ DE DONNEES GPS"
            msg2 = f"(min {self.min_gps_sats} SAT)"
            (tw, _), _ = cv2.getTextSize(msg, self.font_p, self.sc * 0.88, 1)
            self._txt(f, msg, (x1 + (W - tw) // 2, (y1 + y2) // 2 - self._s(10)),
                      self.font_p, self.sc * 0.88, C["dim"], a=A_DIM)
            (tw2, _), _ = cv2.getTextSize(msg2, self.font_p, self.sc * 0.78, 1)
            self._txt(f, msg2, (x1 + (W - tw2) // 2, (y1 + y2) // 2 + self._s(8)),
                      self.font_p, self.sc * 0.78, C["dim"], a=A_DIM)
            return

        mr = cv2.resize(self.gps_map_bg, (W, H))
        roi = f[y1:y2, x1:x2]
        alpha = mr[:, :, 3].astype(np.float32) / 255.0
        for c in range(3):
            roi[:, :, c] = (mr[:, :, c] * alpha + roi[:, :, c] * (1 - alpha)).astype(np.uint8)
        roi[:, :, 3] = np.maximum(roi[:, :, 3], mr[:, :, 3])
        f[y1:y2, x1:x2] = roi
        self._panel(f, x1, y1, x2, y2, "GPS MAP", C["accent"], fill=False)

        sx = W / self.gps_map_bg.shape[1]; sy = H / self.gps_map_bg.shape[0]
        prev = None; step = max(1, frame_idx // 400)
        for idx in range(0, frame_idx + 1, step):
            raw = self.gps_pts_px[idx] if idx < len(self.gps_pts_px) else None
            if raw is None:
                prev = None; continue
            px = (x1 + int(raw[0] * sx), y1 + int(raw[1] * sy))
            if prev:
                cv2.line(f, prev, px, bgra(C["accent3"], 220), 1)
            prev = px
        cur = self.gps_pts_px[frame_idx] if frame_idx < len(self.gps_pts_px) else None
        if cur:
            cp = (x1 + int(cur[0] * sx), y1 + int(cur[1] * sy))
            self._circle(f, cp, self._s(8), C["accent"])
            self._circle(f, cp, self._s(10), C["accent"], self._s(2))
        first = next((p for p in self.gps_pts_px if p is not None), None)
        if first:
            hp = (x1 + int(first[0] * sx), y1 + int(first[1] * sy))
            cv2.drawMarker(f, hp, bgra(C["accent3"], A_BORDER), cv2.MARKER_TRIANGLE_UP, self._s(10), 1, cv2.LINE_AA)

    # ── EKF XY velocity panel ─────────────────────────────────────────────
    def render_ekf(self, f, fl: FlightFrame, x1: int, y1: int, x2: int, y2: int) -> None:
        self._panel(f, x1, y1, x2, y2, "EKF XY", C["accent"])
        W = x2 - x1; H = y2 - y1
        gh = int(H * 0.60)
        acx = x1 + W // 2; acy = y1 + self._s(20) + gh // 2
        r_max = min(W // 2, gh // 2) - self._s(10)
        V_SC = 5.0
        for vr in (1.0, 3.0, 5.0):
            r = int(r_max * vr / V_SC)
            cv2.circle(f, (acx, acy), r, bgra(C["border"], 180), 1)
            self._txt(f, f"{int(vr)}", (acx + r + 2, acy - 2), self.font_p, self.sc * 0.70, C["dim"], a=A_DIM)
        self._line(f, (acx - r_max, acy), (acx + r_max, acy), C["border"], a=A_DIM)
        self._line(f, (acx, acy - r_max), (acx, acy + r_max), C["border"], a=A_DIM)
        self._txt(f, "fwd", (acx - self._s(12), acy - r_max - 2), self.font_p, self.sc * 0.72, C["dim"], a=A_DIM)
        self._txt(f, "lat", (acx + r_max + 3, acy + 4), self.font_p, self.sc * 0.72, C["dim"], a=A_DIM)

        Vf = fl.Vfwd; Vl = fl.Vlat; Vh = fl.Vh
        if Vh > 0.15:
            scl = min(Vh, V_SC) / V_SC * r_max
            ex = acx + int(Vl / Vh * scl); ey = acy - int(Vf / Vh * scl)
            col = C["warn"] if Vh > 3 else C["accent3"]
            cv2.line(f, (acx, acy), (ex, ey), bgra(col, 120), self._s(6))
            cv2.arrowedLine(f, (acx, acy), (ex, ey), bgra(col, A_BORDER), self._s(2), tipLength=0.32)

        ty = y1 + gh + self._s(22); lh = self._s(20)
        for txt, col in [
            (f"Vfwd {fl.Vfwd:+.2f} m/s", C["accent3"]),
            (f"Vlat {fl.Vlat:+.2f} m/s", C["warn"]),
            (f"|Vh|  {fl.Vh:.2f} m/s",   C["accent"]),
            (f"Vz   {fl.Vz:+.2f} m/s",   C["text"]),
        ]:
            self._txt(f, txt, (x1 + self._s(8), ty), self.font_p, self.sc * 0.92, col)
            ty += lh

    # ── Full RGBA frame ───────────────────────────────────────────────────
    def render(self, fl: FlightFrame, frame_idx: int, t0_us: int) -> np.ndarray:
        f = np.zeros((self.h, self.w, 4), dtype=np.uint8)

        RC_X1 = self._s(1520); RC_X2 = self.w - self._s(8)
        GPS_X1 = RC_X1;  GPS_X2 = RC_X2
        GPS_Y1 = self._s(72);  GPS_Y2 = self._s(630)
        EKF_X1 = RC_X1;  EKF_X2 = RC_X2
        EKF_Y1 = self._s(636); EKF_Y2 = self.h - self._s(8)
        BOT_Y  = self._s(690); BOT_Y2 = self.h - self._s(8)
        D3_X1  = self._s(133); D3_X2  = self._s(445)
        AI_CX  = self._s(980); AI_CY  = self._s(881); AI_R = self._s(127)

        self.render_top_bar(f, fl, t0_us)
        self.render_left_col(f, fl)
        self.render_motors(f, fl.m1_pwm, fl.m3_pwm)
        self.render_gps_map(f, frame_idx, GPS_X1, GPS_Y1, GPS_X2, GPS_Y2)
        self.render_drone_3d(f, fl.roll_deg, fl.pitch_deg, fl.yaw_deg, D3_X1, BOT_Y, D3_X2, BOT_Y2)
        self.render_attitude(f, fl.roll_deg, fl.pitch_deg, AI_CX, AI_CY, AI_R)
        self.render_ekf(f, fl, EKF_X1, BOT_Y, EKF_X2, BOT_Y2)

        return f
