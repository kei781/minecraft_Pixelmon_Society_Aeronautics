"""Give the Pixelmon keys that act together with a Society key a default key of their own.

Pixelmon sets its default keys in code and Society's default key file does not list them, so
some Pixelmon keys share a key with a Society binding and one press runs both. This adds one
line per moved Pixelmon binding to the pack's default key file. No Society line is changed.
Configured Defaults fills in a default only where the player's own options have no value, so
an installation that has already saved its keys keeps them.
"""
import hashlib
import json
from pathlib import Path

OPTIONS = "configureddefaults/options.txt"
# Every keyboard key name Minecraft 1.20.1 reads from an options file, except the unbound key.
# A name outside this list stops the game from reading the rest of the options.
KEYBOARD_KEYS = frozenset("key.keyboard." + name for name in (
    list("abcdefghijklmnopqrstuvwxyz0123456789") + ["f%d" % number for number in range(1, 26)]
    + ["keypad.%d" % number for number in range(10)]
    + ("keypad.add keypad.decimal keypad.divide keypad.enter keypad.equal keypad.multiply keypad.subtract "
       "apostrophe backslash backspace caps.lock comma delete down end enter equal escape grave.accent home "
       "insert left left.alt left.bracket left.control left.shift left.win menu minus num.lock page.down "
       "page.up pause period print.screen right right.alt right.bracket right.control right.shift right.win "
       "scroll.lock semicolon slash space tab up world.1 world.2").split()))


def key_and_modifier(value):
    key, _, modifier = value.partition(":")
    return key, modifier or "NONE"


def bindings(lines):
    """Binding name -> (key, modifier) for the key lines of an options file."""
    found = {}
    for line in lines:
        if not line.startswith("key_"):
            continue
        name, _, value = line[len("key_"):].partition(":")
        if not name or not value.partition(":")[0] or name in found:
            raise ValueError("Unreadable default key line: " + line)
        found[name] = key_and_modifier(value)
    return found


def apply(overrides, table_path, pixelmon_sha256, port_sha256, mods_lock_sha256, expected):
    table_bytes = Path(table_path).read_bytes()
    table = json.loads(table_bytes)
    # The coded defaults in the table were read from these exact JARs; other JARs need a new look.
    pinned = {"pixelmon_sha256": pixelmon_sha256, "port_sha256": port_sha256, "mods_lock_sha256": mods_lock_sha256}
    if any(table.get(name) != value for name, value in pinned.items()):
        raise ValueError("Default key table belongs to a different set of mod JARs")
    coded = {name: key_and_modifier(value) for name, value in table["coded_defaults"].items()}
    moves = table["moved"]
    if len(moves) != expected or len({move["binding"] for move in moves}) != len(moves):
        raise ValueError("Unexpected default key table")
    lines = overrides[OPTIONS].decode().splitlines()
    shipped = bindings(lines)
    if set(coded) & set(shipped):
        raise ValueError("Default key file already sets a binding the table lists as coded")
    defaults = dict(shipped, **coded)
    added = []
    for move in moves:
        name, old, new, others = move["binding"], move["from"], move["to"], move["acts_together_with"]
        if coded.get(name) != (old, "NONE"):
            raise ValueError("Coded default differs: " + name)
        # The move is only justified while a Society binding still sits on the same plain key.
        if not others or any(shipped.get(other) != (old, "NONE") for other in others):
            raise ValueError("Shared default key differs: " + name)
        # With any modifier: Forge treats a plain key and the same key with a modifier as a conflict.
        on_new_key = sorted(other for other, (key, _) in defaults.items() if key == new and other != name)
        if new not in KEYBOARD_KEYS or on_new_key != sorted(move["shares_new_key_with"]):
            raise ValueError("Free keyboard key required: " + name)
        defaults[name] = (new, "NONE")
        added.append("key_%s:%s:NONE" % (name, new))
    if added:
        last = max(index for index, line in enumerate(lines) if line.startswith("key_"))
        lines[last + 1:last + 1] = added
        overrides[OPTIONS] = ("\n".join(lines) + "\n").encode()
    return {"path": OPTIONS, "added": added, "table": "compat/client-keys/default-keys.json",
            "table_sha256": hashlib.sha256(table_bytes).hexdigest()}
