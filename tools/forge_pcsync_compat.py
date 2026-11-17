#!/usr/bin/env python3
"""Add the authored Pixelmon PC resend to the common JAR without rewriting upstream payloads.

Pixelmon 9.2.3 can send a player's PC before the login packet that makes the client forget
every PC it knows. The client then ignores all PC changes for that session. One mixin class
sends the PC once more after Pixelmon's login packets. This tool adds the compiled class and
its mixin configuration to the accepted common JAR; every other entry is carried over byte
for byte.
"""
import argparse
import json
from pathlib import Path

from forge_portfix_compat import overlay

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "compat/pc-resync-build.json"
CONFIG = ROOT / "compat/forge-port/psa-pc-resync.mixins.json"
NAMES = ("PixelmonPcResyncMixin",)
SOURCES = {name: ROOT / ("compat/forge-port/%s.java" % name) for name in NAMES}
CLASSES = {name: "dev/psa/pcsync/mixin/%s.class" % name for name in NAMES}
EXPECTED_CONFIG = {"required": True, "minVersion": "0.8", "package": "dev.psa.pcsync.mixin",
                   "compatibilityLevel": "JAVA_17", "mixins": list(NAMES), "injectors": {"defaultRequire": 1}}


def build(base, tested_patch, destination):
    # The class it changes is Pixelmon's, which is not in this JAR; the staging tool pins Pixelmon.
    return overlay(base, tested_patch, destination, MANIFEST, CONFIG, SOURCES, CLASSES, EXPECTED_CONFIG, None,
                   "PSA authored Pixelmon PC resend after login")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("base", "tested-patch", "output"):
        parser.add_argument("--" + argument, type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.base, arguments.tested_patch, arguments.output), indent=2))
