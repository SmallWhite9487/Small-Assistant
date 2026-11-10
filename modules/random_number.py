"""Non-cryptographic number generation with explicitly reported seed sources."""

from __future__ import annotations

import itertools
import json
import math
import plistlib
import socket
import subprocess
import sys
import time
from pathlib import Path

MAX_SAFE_INTEGER = (1 << 53) - 1
MASK = (1 << 64) - 1
_sequence = itertools.count()


def collect_sources(client_ip: str | None) -> tuple[dict[str, str], list[str]]:
    sources = {
        "system_time": str(time.time_ns()),
        "monotonic_time": str(time.perf_counter_ns()),
        "sequence": str(next(_sequence)),
    }
    warnings = []
    if client_ip:
        sources["client_ip"] = client_ip
    else:
        warnings.append("Client IP is unavailable.")

    try:
        addresses = socket.getaddrinfo(socket.gethostname(), None, socket.AF_UNSPEC)
    except OSError:
        warnings.append("Server IP address lookup failed.")
        addresses = []
    for family, label in ((socket.AF_INET, "ipv4"), (socket.AF_INET6, "ipv6")):
        values = sorted({entry[4][0] for entry in addresses if entry[0] == family})
        if values:
            sources[label] = ",".join(values)
        else:
            warnings.append(f"Server {label.upper()} is unavailable.")

    try:
        if sys.platform == "darwin":
            result = subprocess.run(
                ["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice", "-a"],
                check=True, capture_output=True, timeout=2,
            )
            records = plistlib.loads(result.stdout)
            if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
                raise ValueError("Invalid machine information")
            machine_code = next(
                (record["IOPlatformUUID"] for record in records if record.get("IOPlatformUUID")),
                "",
            )
        elif sys.platform.startswith("linux"):
            machine_code = Path("/etc/machine-id").read_text().strip()
        else:
            machine_code = ""
        if not isinstance(machine_code, str) or not machine_code:
            raise ValueError("No machine code")
        sources["machine_code"] = machine_code
    except (OSError, ValueError, subprocess.SubprocessError, plistlib.InvalidFileException):
        warnings.append("Server machine code is unavailable on this system.")

    try:
        if sys.platform == "darwin":
            result = subprocess.run(
                ["/usr/sbin/sysctl", "-n", "hw.cpufrequency"],
                check=True, capture_output=True, text=True, timeout=2,
            )
            frequency = float(result.stdout.strip())
        elif sys.platform.startswith("linux"):
            cpu_info = Path("/proc/cpuinfo").read_text()
            mhz = next(line.split(":", 1)[1] for line in cpu_info.splitlines() if line.startswith("cpu MHz"))
            frequency = float(mhz) * 1_000_000
        else:
            frequency = 0
        if not 0 < frequency < float("inf"):
            raise ValueError("No CPU frequency")
        sources["cpu_frequency"] = str(frequency)
    except (OSError, ValueError, StopIteration, subprocess.SubprocessError):
        warnings.append("Server CPU frequency is unavailable; some CPUs do not expose it.")
    return sources, warnings


def validate_bounds(minimum: int | float, maximum: int | float, number_type: str) -> None:
    if number_type not in ("int", "float"):
        raise ValueError("Number type must be int or float.")
    if number_type == "int":
        if type(minimum) is not int or type(maximum) is not int:
            raise ValueError("Bounds must be integers.")
    elif type(minimum) not in (int, float) or type(maximum) not in (int, float):
        raise ValueError("Bounds must be finite numbers.")
    if not -MAX_SAFE_INTEGER <= minimum <= maximum <= MAX_SAFE_INTEGER:
        raise ValueError(
            f"Use bounds between {-MAX_SAFE_INTEGER} and {MAX_SAFE_INTEGER}, with minimum <= maximum."
        )


def integer_from_sources(sources: dict[str, str], minimum: int, maximum: int) -> int:
    validate_bounds(minimum, maximum, "int")
    # FNV-1a folds all sources into a seed; SplitMix64 supplies candidate values.
    state = 0xCBF29CE484222325
    for byte in json.dumps(sources, sort_keys=True, separators=(",", ":")).encode("utf-8"):
        state = ((state ^ byte) * 0x100000001B3) & MASK
    width = maximum - minimum + 1
    limit = (1 << 64) - ((1 << 64) % width)
    while True:
        state = (state + 0x9E3779B97F4A7C15) & MASK
        value = state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK
        value ^= value >> 31
        # Reject the incomplete bucket rather than biasing the result with modulo.
        if value < limit:
            return minimum + value % width


def float_from_sources(sources: dict[str, str], minimum: int | float, maximum: int | float) -> float:
    validate_bounds(minimum, maximum, "float")
    lower, upper = float(minimum), float(maximum)
    if lower == upper:
        return lower
    fraction = integer_from_sources(sources, 0, MAX_SAFE_INTEGER) / (1 << 53)
    value = lower + (upper - lower) * fraction
    # Rounding must not include the exclusive upper bound, even for adjacent floats.
    return max(lower, min(value, math.nextafter(upper, lower)))
