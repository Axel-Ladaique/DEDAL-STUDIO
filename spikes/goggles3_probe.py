#!/usr/bin/env python3
"""Throwaway spike: can this computer receive the DJI Goggles 3 live video over USB-C?

This is NOT product code. It answers one question before anything is designed:
does the wired "OTG to computer" live view of the Goggles 3 work on this machine,
and how good is the stream?

What it does
------------
1. Reports the platform and looks for the goggles' USB network link.
2. Opens a UDP session with the goggles (192.168.60.2:9003) and asks for video.
3. Receives the H.264 stream for a few seconds, writes it to a file, and prints
   bitrate, frame rate and whether a keyframe was seen.
4. Writes a plain-text report you can paste back into the conversation.

Standard library only. Python 3.9+.

Usage
-----
    python spikes/goggles3_probe.py                 # 20 s capture
    python spikes/goggles3_probe.py --seconds 60    # longer stability run
    python spikes/goggles3_probe.py --play          # live preview (needs ffplay)
    python spikes/goggles3_probe.py --selftest      # protocol check, no hardware

Before running
--------------
- Goggles 3 powered on and linked to the air unit (the O4 must be powered).
- On the goggles: Settings > About > "OTG Wired Connection to Computer" ON.
  Unplug the USB cable before toggling it, then plug it back.
- Start live view sharing on the goggles.
- Use a USB-C cable that carries data (not a charge-only cable).

Windows: the goggles show up as a Microsoft RNDIS network adapter. That adapter
needs the address 192.168.60.1/24 once (administrator PowerShell). The script
prints the exact command if the address is missing.

macOS: the system RNDIS driver does not bring the link up, so the capture step
is expected to fail here. The script still reports whether the goggles are seen
on USB, which is the useful data point on a Mac.

Protocol credit
---------------
The UDP session below is a Python port of the session logic in
"Goggle 3 LiveView" (https://github.com/knpuma/goggle-3-liveview), MIT License,
Copyright (c) 2026 Goggle 3 LiveView contributors. Unofficial, not affiliated
with or endorsed by DJI. A DJI firmware update may break it.
"""

from __future__ import annotations

import argparse
import collections
import datetime
import os
import platform
import random
import shutil
import socket
import struct
import subprocess
import sys
import time

GOGGLES_IP = "192.168.60.2"
GOGGLES_PORT = 9003
HOST_IP = "192.168.60.1"
HOST_PORT = 12346
USB_VENDOR_ID = "2ca3"
USB_PRODUCT_ID = "0020"

_HANDSHAKE_TEMPLATE = bytes([
    0x30, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xD0, 0xE9, 0x64, 0x00, 0x64, 0x00, 0xC0, 0x05,
    0x14, 0x00, 0x00, 0x0A, 0x00, 0x64, 0x00, 0x64, 0x00, 0xC0, 0x05, 0x14, 0x00, 0x00, 0x64, 0x00,
    0x14, 0x00, 0x64, 0x00, 0xC0, 0x05, 0x14, 0x00, 0x00, 0x64, 0x00, 0x01, 0x01, 0x04, 0x0A, 0x02,
])

_ACK_TEMPLATE = bytes([
    0x1E, 0x80, 0x00, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xD0, 0xE9,
    0xD0, 0xE9, 0x00, 0x00, 0xD0, 0xE9, 0xD8, 0xE9, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
])

MAX_PENDING_UNITS = 32


def header_xor(packet: bytes) -> int:
    """Return the XOR of the first 7 header bytes (stored in byte 7)."""
    result = 0
    for value in packet[:7]:
        result ^= value
    return result


class LiveProtocol:
    """UDP live view session: handshake, acknowledgements and unit reassembly."""

    def __init__(self, session_id: int | None = None) -> None:
        # A random id per connection is required: a fixed one breaks keyframe
        # delivery on reconnect (reported by the GogglesView project).
        self.session = random.randrange(65536) if session_id is None else session_id
        self.video_bytes = 0
        self._units: dict[int, dict] = {}
        self._order: collections.deque[int] = collections.deque()

    def create_handshake(self) -> bytes:
        packet = bytearray(_HANDSHAKE_TEMPLATE)
        struct.pack_into("<H", packet, 2, self.session)
        packet[7] = header_xor(packet)
        return bytes(packet)

    def create_ack(self, sequence: int) -> bytes:
        packet = bytearray(_ACK_TEMPLATE)
        struct.pack_into("<H", packet, 2, self.session)
        struct.pack_into("<H", packet, 8, sequence)
        struct.pack_into("<H", packet, 10, sequence)
        packet[7] = header_xor(packet)
        return bytes(packet)

    def accept(self, message: bytes) -> tuple[bytes | None, bytes | None, bool]:
        """Process one datagram.

        Returns (video_unit, acknowledgement_to_send, handshake_confirmed).
        """
        if (
            len(message) < 8
            or (struct.unpack_from("<H", message, 0)[0] & 0x7FFF) != len(message)
            or struct.unpack_from("<H", message, 2)[0] != self.session
            or message[7] != header_xor(message)
        ):
            return None, None, False
        if message[6] == 0:
            return None, None, True
        if message[6] != 2 or len(message) < 20:
            return None, None, False

        count = message[17] & 0x7F
        part = (message[17] >> 7) | (message[18] << 1) | (message[19] << 9)
        if count == 0 or part >= count:
            return None, None, False

        sequence = struct.unpack_from("<H", message, 4)[0]
        key = ((sequence & 0xFFF8) - part * 8) & 0xFFFF
        unit = self._units.get(key)
        if unit is None:
            if len(self._units) >= MAX_PENDING_UNITS:
                self._units.pop(self._order.popleft(), None)
            unit = {"parts": [None] * count, "received": 0, "complete": False}
            self._units[key] = unit
            self._order.append(key)
        if len(unit["parts"]) != count:
            return None, None, False

        ack = self.create_ack(sequence) if part + 1 == count else None
        if unit["complete"] or unit["parts"][part] is not None:
            return None, ack, False

        unit["parts"][part] = message[20:]
        self.video_bytes += len(message) - 20
        unit["received"] += 1
        if unit["received"] != count:
            return None, ack, False

        frame = b"".join(unit["parts"])
        unit["parts"] = [None] * count
        unit["complete"] = True
        return frame, ack, False


def nal_types(unit: bytes) -> list[int]:
    """Return the H.264 NAL unit types found in an Annex-B chunk."""
    found = []
    index = 0
    while True:
        index = unit.find(b"\x00\x00\x01", index)
        if index < 0 or index + 3 >= len(unit):
            return found
        found.append(unit[index + 3] & 0x1F)
        index += 3


class Report:
    """Collects lines for the console and for the report file."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def add(self, text: str = "") -> None:
        print(text, flush=True)
        self.lines.append(text)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(self.lines) + "\n")


def run_command(arguments: list[str], timeout: float = 20.0) -> str:
    try:
        completed = subprocess.run(
            arguments, capture_output=True, text=True, timeout=timeout, errors="replace"
        )
        return (completed.stdout or "") + (completed.stderr or "")
    except (OSError, subprocess.SubprocessError) as error:
        return f"<could not run {arguments[0]}: {error}>"


def is_admin() -> bool:
    if os.name == "nt":
        try:
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def describe_platform(report: Report) -> None:
    report.add("== Platform")
    report.add(f"date            : {datetime.datetime.now().isoformat(timespec='seconds')}")
    report.add(f"system          : {platform.system()} {platform.release()} ({platform.machine()})")
    report.add(f"python          : {platform.python_version()}")
    report.add(f"admin / root    : {'yes' if is_admin() else 'no'}")
    report.add(f"ffplay on PATH  : {'yes' if shutil.which('ffplay') else 'no'}")
    report.add(f"ffmpeg on PATH  : {'yes' if shutil.which('ffmpeg') else 'no'}")
    report.add()


def detect_windows(report: Report) -> None:
    report.add("== USB network adapters (Windows)")
    script = (
        "Get-NetAdapter | Where-Object { $_.InterfaceDescription -match 'NDIS' } | "
        "Format-List Name,InterfaceDescription,Status,PnPDeviceID; "
        "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '192.168.60.*' } | "
        "Format-List InterfaceAlias,IPAddress,PrefixLength"
    )
    output = run_command(["powershell", "-NoProfile", "-Command", script]).strip()
    report.add(output or "No RNDIS adapter found. Are the goggles plugged in with OTG enabled?")
    seen = f"VID_{USB_VENDOR_ID}".lower() in output.lower()
    report.add(f"goggles adapter seen (VID {USB_VENDOR_ID}) : {'yes' if seen else 'not confirmed'}")
    report.add()


def detect_macos(report: Report) -> None:
    report.add("== USB devices (macOS)")
    output = run_command(["ioreg", "-p", "IOUSB", "-l", "-w", "0"])
    vendor_decimal = str(int(USB_VENDOR_ID, 16))
    seen = f'"idVendor" = {vendor_decimal}' in output
    report.add(f"goggles seen on USB (vendor 0x{USB_VENDOR_ID}) : {'yes' if seen else 'no'}")
    if seen:
        for line in output.splitlines():
            if any(key in line for key in ('"USB Product Name"', '"idProduct"', '"idVendor"', '"USB Serial Number"')):
                if "USB Serial Number" in line:
                    continue  # keep serial numbers out of a report that gets pasted around
                report.add("  " + line.strip(" |"))
    interfaces = run_command(["ifconfig"])
    has_address = "192.168.60." in interfaces
    report.add(f"an interface holds 192.168.60.x : {'yes' if has_address else 'no'}")
    report.add("Note: on macOS the system RNDIS driver does not bring this link up, so the")
    report.add("capture below is expected to fail. A userspace RNDIS driver is needed (not in this spike).")
    report.add()


def detect_linux(report: Report) -> None:
    report.add("== USB devices (Linux)")
    output = run_command(["lsusb"])
    seen = f"{USB_VENDOR_ID}:" in output.lower()
    report.add(f"goggles seen on USB (vendor 0x{USB_VENDOR_ID}) : {'yes' if seen else 'no'}")
    report.add()


def print_address_help(report: Report) -> None:
    report.add(f"Could not use local address {HOST_IP}: the goggles' network link is not configured.")
    system = platform.system()
    if system == "Windows":
        report.add("In an ADMINISTRATOR PowerShell, using the adapter Name listed above:")
        report.add(f'  New-NetIPAddress -InterfaceAlias "<Name>" -IPAddress {HOST_IP} -PrefixLength 24')
        report.add("To undo it later:")
        report.add(f'  Remove-NetIPAddress -InterfaceAlias "<Name>" -IPAddress {HOST_IP} -Confirm:$false')
        report.add("This only adds an address to that one adapter. It does not touch other networks.")
    elif system == "Darwin":
        report.add("Expected on macOS: see the note above.")
    else:
        report.add(f"Give the goggles' usb network interface the address {HOST_IP}/24, e.g.:")
        report.add(f"  sudo ip addr add {HOST_IP}/24 dev <usb-interface>")


def capture(report: Report, seconds: float, output_path: str, play: bool) -> bool:
    """Run the live view session. Returns True when video was received."""
    report.add("== Live view session")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
    except OSError:
        pass
    try:
        # Binding to the goggles' own subnet keeps traffic off Wi-Fi / the default route.
        sock.bind((HOST_IP, HOST_PORT))
    except OSError as error:
        report.add(f"bind {HOST_IP}:{HOST_PORT} failed: {error}")
        print_address_help(report)
        sock.close()
        return False
    sock.settimeout(0.25)
    peer = (GOGGLES_IP, GOGGLES_PORT)

    player = None
    if play:
        if shutil.which("ffplay"):
            player = subprocess.Popen(
                ["ffplay", "-loglevel", "warning", "-fflags", "nobuffer", "-flags", "low_delay",
                 "-framedrop", "-f", "h264", "-i", "-"],
                stdin=subprocess.PIPE,
            )
        else:
            report.add("--play ignored: ffplay is not on PATH.")

    protocol = LiveProtocol()
    handshake = protocol.create_handshake()
    start = time.monotonic()
    last_subscribe = -1.0
    last_stats = 0.0
    last_bytes = 0
    started = False
    confirmed = False
    first_video_at = None
    first_keyframe_at = None
    units = 0
    pictures = 0
    last_pictures = 0
    datagrams = 0
    rejected = 0
    longest_gap = 0.0
    last_unit_at = None
    counts = collections.Counter()
    bitrates: list[float] = []
    rates: list[float] = []

    with open(output_path, "wb") as output:
        try:
            while True:
                now = time.monotonic() - start
                if now >= seconds:
                    break
                if not started and now - last_subscribe >= 1.0:
                    try:
                        sock.sendto(handshake, peer)
                    except OSError as error:
                        report.add(f"send failed: {error}")
                        break
                    last_subscribe = now
                try:
                    message, _ = sock.recvfrom(65535)
                except socket.timeout:
                    message = None
                except OSError as error:
                    # Windows raises WSAECONNRESET when the peer answers "port unreachable".
                    if getattr(error, "winerror", None) == 10054:
                        message = None
                    else:
                        report.add(f"receive failed: {error}")
                        break
                if message is not None:
                    datagrams += 1
                    video, ack, handshake_ok = protocol.accept(message)
                    if handshake_ok and not confirmed:
                        confirmed = True
                        report.add(f"[{now:6.2f}s] session confirmed by the goggles")
                    if video is None and ack is None and not handshake_ok:
                        rejected += 1
                    if ack is not None:
                        sock.sendto(ack, peer)
                    if video is not None:
                        now = time.monotonic() - start
                        if not started:
                            started = True
                            first_video_at = now
                            report.add(f"[{now:6.2f}s] first video data")
                        if last_unit_at is not None:
                            longest_gap = max(longest_gap, now - last_unit_at)
                        last_unit_at = now
                        units += 1
                        types = nal_types(video)
                        counts.update(types)
                        if any(kind in (1, 5) for kind in types):
                            pictures += 1
                        if first_keyframe_at is None and 5 in types:
                            first_keyframe_at = now
                            report.add(f"[{now:6.2f}s] first keyframe (IDR)")
                        output.write(video)
                        if player is not None and player.stdin is not None:
                            try:
                                player.stdin.write(video)
                                player.stdin.flush()
                            except OSError:
                                player = None
                now = time.monotonic() - start
                if now - last_stats >= 1.0:
                    if started:
                        megabits = (protocol.video_bytes - last_bytes) * 8 / (now - last_stats) / 1e6
                        rate = (pictures - last_pictures) / (now - last_stats)
                        bitrates.append(megabits)
                        rates.append(rate)
                        print(f"[{now:6.2f}s] {megabits:5.1f} Mbit/s  {rate:5.1f} pictures/s", flush=True)
                    last_stats = now
                    last_bytes = protocol.video_bytes
                    last_pictures = pictures
        except KeyboardInterrupt:
            report.add("stopped by user")
    sock.close()
    if player is not None and player.stdin is not None:
        try:
            player.stdin.close()
        except OSError:
            pass

    report.add()
    report.add("== Result")
    report.add(f"datagrams received     : {datagrams} ({rejected} not understood)")
    report.add(f"session confirmed      : {'yes' if confirmed else 'no'}")
    report.add(f"video received         : {'yes' if started else 'no'}")
    if started:
        report.add(f"first video after      : {first_video_at:.2f} s")
        report.add("first keyframe after   : " + (f"{first_keyframe_at:.2f} s" if first_keyframe_at is not None else "none seen"))
        report.add(f"video data             : {protocol.video_bytes / 1e6:.1f} MB in {units} units")
        if bitrates:
            report.add(f"bitrate avg / min      : {sum(bitrates) / len(bitrates):.1f} / {min(bitrates):.1f} Mbit/s")
            report.add(f"pictures per second    : avg {sum(rates) / len(rates):.1f}, min {min(rates):.1f}")
        report.add(f"longest gap            : {longest_gap * 1000:.0f} ms")
        report.add(f"NAL types (type:count) : {dict(sorted(counts.items()))}")
        report.add(f"capture file           : {output_path}")
        report.add("Play it with:  ffplay " + os.path.basename(output_path))
        if first_keyframe_at is None:
            report.add("No keyframe seen: the file may not decode. On the goggles, toggle live view")
            report.add("sharing off then on while the script runs, and try again.")
    elif datagrams == 0:
        report.add("Nothing came back from the goggles. Check, in this order:")
        report.add("  1. goggles linked to a powered air unit, live view visible in the goggles")
        report.add("  2. OTG Wired Connection to Computer is ON (toggle it with the cable unplugged)")
        report.add("  3. live view sharing is started on the goggles")
        report.add("  4. data-capable USB-C cable, try another port")
        report.add("  5. Windows firewall: allow python on private networks when prompted")
    else:
        report.add("The goggles answered but sent no video. Start live view sharing on the goggles.")
    return started


def selftest() -> int:
    """Check the session logic without hardware. Returns a process exit code."""
    protocol = LiveProtocol(session_id=0x1234)
    handshake = protocol.create_handshake()
    assert len(handshake) == 48 and handshake[0] == 0x30 and handshake[1] == 0x80
    assert handshake[2:4] == b"\x34\x12" and handshake[7] == header_xor(handshake)
    ack = protocol.create_ack(0x0BB8)
    assert len(ack) == 30 and ack[8:12] == b"\xb8\x0b\xb8\x0b" and ack[7] == header_xor(ack)

    def packet(kind: int, sequence: int, part: int = 0, count: int = 0, payload: bytes = b"", session: int = 0x1234) -> bytes:
        body = bytearray(20 if kind == 2 else 8)
        body += payload
        struct.pack_into("<H", body, 0, len(body) | 0x8000)
        struct.pack_into("<H", body, 2, session)
        struct.pack_into("<H", body, 4, sequence)
        body[6] = kind
        if kind == 2:
            body[17] = (count & 0x7F) | ((part & 1) << 7)
            body[18] = (part >> 1) & 0xFF
            body[19] = (part >> 9) & 0xFF
        body[7] = header_xor(body)
        return bytes(body)

    assert protocol.accept(packet(0, 0)) == (None, None, True)
    assert protocol.accept(packet(0, 0, session=0x9999)) == (None, None, False)
    assert protocol.accept(b"\x00" * 4) == (None, None, False)

    chunks = [b"\x00\x00\x00\x01\x67AAAA", b"BBBB", b"\x00\x00\x01\x65CCCC"]
    base = 0x0100
    packets = [packet(2, base + index * 8, index, 3, chunk) for index, chunk in enumerate(chunks)]
    # Out of order, with a duplicate: the unit must still come out once, in order.
    video, ack, _ = protocol.accept(packets[1])
    assert video is None and ack is None
    video, ack, _ = protocol.accept(packets[2])
    assert video is None and ack is not None
    assert protocol.accept(packets[1])[0] is None
    video, ack, _ = protocol.accept(packets[0])
    assert video == b"".join(chunks) and ack is None
    assert protocol.accept(packets[0])[0] is None
    assert nal_types(video) == [7, 5]
    assert protocol.video_bytes == sum(len(chunk) for chunk in chunks)

    # Pending units stay bounded.
    for index in range(100):
        protocol.accept(packet(2, 0x2000 + index * 16, 0, 2, b"x"))
    assert len(protocol._units) <= MAX_PENDING_UNITS
    print("selftest OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe the DJI Goggles 3 wired live view (throwaway spike).")
    parser.add_argument("--seconds", type=float, default=20.0, help="capture duration (default 20)")
    parser.add_argument("--output", default="goggles3_capture.h264", help="raw H.264 output file")
    parser.add_argument("--report", default="goggles3_report.txt", help="text report file")
    parser.add_argument("--play", action="store_true", help="live preview through ffplay")
    parser.add_argument("--selftest", action="store_true", help="check the protocol code, no hardware")
    arguments = parser.parse_args()

    if arguments.selftest:
        return selftest()

    report = Report()
    report.add("DJI Goggles 3 wired live view probe (unofficial, throwaway)")
    report.add()
    describe_platform(report)
    system = platform.system()
    if system == "Windows":
        detect_windows(report)
    elif system == "Darwin":
        detect_macos(report)
    else:
        detect_linux(report)
    received = capture(report, arguments.seconds, arguments.output, arguments.play)
    report.save(arguments.report)
    print()
    print(f"Report saved to {arguments.report} - paste it back to Claude.")
    return 0 if received else 1


if __name__ == "__main__":
    sys.exit(main())
