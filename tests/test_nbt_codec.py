import gzip
from pathlib import Path
import struct
import sys
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import nbt_codec as nbt


def sample():
    return nbt.compound({
        "size": nbt.tag_list(nbt.INT, [nbt.integer(2), nbt.integer(1), nbt.integer(1)]),
        "flag": nbt.byte(1), "short": nbt.Tag(nbt.SHORT, -2), "long": nbt.Tag(nbt.LONG, 1 << 40),
        "float": nbt.Tag(nbt.FLOAT, 0.5), "double": nbt.Tag(nbt.DOUBLE, float("nan")),
        "bytes": nbt.Tag(nbt.BYTE_ARRAY, (1, -1)), "ints": nbt.Tag(nbt.INT_ARRAY, (7, -7)),
        "longs": nbt.Tag(nbt.LONG_ARRAY, (-1, 2)), "empty": nbt.tag_list(nbt.END, []),
        "text": nbt.string("fire 🔥"),
        "nested": nbt.compound({"name": nbt.string("minecraft:air")}),
    })


class NbtCodecTest(unittest.TestCase):
    def test_strings_use_the_bytes_java_reads_and_writes(self):
        # DataOutput.writeUTF: a character outside the BMP is two three-byte surrogates, NUL is C0 80.
        data = nbt.serialize(nbt.compound({"t": nbt.string("a\x00🔥")}))
        self.assertIn(bytes.fromhex("0009") + b"a" + bytes.fromhex("c080eda0bdedb4a5"), data)
        self.assertNotIn(bytes.fromhex("f09f94a5"), data)
        self.assertEqual(nbt.parse(data)[1]["t"].value, "a\x00🔥")

    def test_every_tag_type_round_trips_byte_for_byte(self):
        data = nbt.serialize(sample(), "root")
        name, parsed = nbt.parse(data)
        self.assertEqual(name, "root")
        self.assertEqual(parsed, sample())
        self.assertEqual(nbt.serialize(parsed, name), data)
        self.assertEqual(parsed["nested"].text("name"), "minecraft:air")
        self.assertEqual(parsed.number("flag"), 1)
        self.assertEqual(parsed.text("missing", "fallback"), "fallback")

    def test_gzip_output_is_deterministic_and_readable_by_gzip(self):
        first, second = nbt.dump_gzip(sample()), nbt.dump_gzip(sample())
        self.assertEqual(first, second)
        self.assertEqual(gzip.decompress(first), nbt.serialize(sample()))
        self.assertEqual(nbt.load_gzip(first), sample())

    def test_malformed_input_is_rejected(self):
        good = nbt.serialize(sample())
        duplicate = (bytes([nbt.COMPOUND]) + b"\x00\x00" + (bytes([nbt.BYTE]) + b"\x00\x01a\x01") * 2 + b"\x00")
        cases = [good[:-1], good + b"\x00", b"\x01\x00\x00\x00", duplicate,
                 bytes([nbt.COMPOUND]) + b"\x00\x00" + bytes([99]) + b"\x00\x01a\x00",
                 bytes([nbt.COMPOUND]) + b"\x00\x00" + bytes([nbt.LIST]) + b"\x00\x01a" + bytes([nbt.END]) + struct.pack(">i", 3) + b"\x00"]
        for data in cases:
            with self.subTest(data=data[:12]), self.assertRaises(ValueError):
                nbt.parse(data)
        with self.assertRaises(ValueError):
            nbt.serialize(nbt.compound({"mixed": nbt.tag_list(nbt.INT, [nbt.byte(1)])}))

    def test_region_reader_returns_each_stored_chunk(self):
        chunk = nbt.serialize(nbt.compound({"xPos": nbt.integer(33), "zPos": nbt.integer(-1)}))
        payloads = {(1, 31): (2, zlib.compress(chunk)), (2, 0): (1, gzip.compress(chunk)), (3, 0): (3, chunk)}
        header, body, sector = bytearray(8192), b"", 2
        for (local_x, local_z), (kind, data) in payloads.items():
            record = struct.pack(">IB", len(data) + 1, kind) + data
            record += b"\x00" * (-len(record) % 4096)
            index = (local_z * 32 + local_x) * 4
            header[index:index + 4] = struct.pack(">I", (sector << 8) | (len(record) // 4096))
            body += record
            sector += len(record) // 4096
        found = {(x, z): root.number("xPos") for x, z, root in nbt.read_region_chunks(bytes(header) + body)}
        self.assertEqual(found, {key: 33 for key in payloads})
        self.assertEqual(list(nbt.read_region_chunks(b"")), [])
        broken = bytearray(bytes(header) + body)
        broken[8192 + 4] = 9
        with self.assertRaises(ValueError):
            list(nbt.read_region_chunks(bytes(broken)))


if __name__ == "__main__":
    unittest.main()
