#!/usr/bin/env python3
"""Small typed NBT reader/writer for structure templates and saved chunks.

Only the Java Edition big-endian binary format is handled. Values keep their
tag types so a parsed file can be written back byte-for-byte (before
compression). The module has no third-party dependency so the staging tools
and tests run on a plain Python 3.9 installation.
"""
import gzip
import io
import struct
import zlib

END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BYTE_ARRAY, STRING, LIST, COMPOUND, INT_ARRAY, LONG_ARRAY = range(13)
_NUMERIC = {BYTE: ">b", SHORT: ">h", INT: ">i", LONG: ">q", FLOAT: ">f", DOUBLE: ">d"}
_ARRAY = {BYTE_ARRAY: "b", INT_ARRAY: "i", LONG_ARRAY: "q"}
MAX_DEPTH = 512


class Tag:
    """One typed NBT value. `value` is a Python number, str, tuple, list or dict."""
    __slots__ = ("type", "value", "element_type")

    def __init__(self, tag_type, value, element_type=None):
        self.type = tag_type
        self.value = value
        self.element_type = element_type  # only for LIST

    def __eq__(self, other):
        if not isinstance(other, Tag) or self.type != other.type:
            return False
        if self.type == LIST and self.element_type != other.element_type:
            return False
        if self.type in (FLOAT, DOUBLE):
            code = _NUMERIC[self.type]
            return struct.pack(code, self.value) == struct.pack(code, other.value)
        return self.value == other.value

    def __repr__(self):
        return "Tag(%d, %r)" % (self.type, self.value)

    # Convenience accessors used by the worldgen tools.
    def __getitem__(self, key):
        return self.value[key]

    def __contains__(self, key):
        return key in self.value

    def get(self, key, default=None):
        return self.value.get(key, default) if self.type == COMPOUND else default

    def text(self, key, default=""):
        item = self.get(key)
        return item.value if item is not None and item.type == STRING else default

    def number(self, key, default=0):
        item = self.get(key)
        return item.value if item is not None and item.type in _NUMERIC else default


def byte(value):
    return Tag(BYTE, value)


def integer(value):
    return Tag(INT, value)


def string(value):
    return Tag(STRING, value)


def compound(value=None):
    return Tag(COMPOUND, dict(value or {}))


def tag_list(element_type, values):
    return Tag(LIST, list(values), element_type)


def _read_string(stream):
    # Java's modified UTF-8: NUL is C0 80 and a character outside the BMP is two encoded surrogates.
    (length,) = struct.unpack(">H", _exact(stream, 2))
    text = _exact(stream, length).replace(b"\xc0\x80", b"\x00").decode("utf-8", "surrogatepass")
    return text.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "surrogatepass")


def _exact(stream, count):
    data = stream.read(count)
    if len(data) != count:
        raise ValueError("Truncated NBT data")
    return data


def _read_payload(stream, tag_type, depth):
    if depth > MAX_DEPTH:
        raise ValueError("NBT nesting too deep")
    if tag_type in _NUMERIC:
        code = _NUMERIC[tag_type]
        return Tag(tag_type, struct.unpack(code, _exact(stream, struct.calcsize(code)))[0])
    if tag_type in _ARRAY:
        (length,) = struct.unpack(">i", _exact(stream, 4))
        if length < 0:
            raise ValueError("Negative NBT array length")
        code = _ARRAY[tag_type]
        size = struct.calcsize(">" + code)
        return Tag(tag_type, struct.unpack(">%d%s" % (length, code), _exact(stream, length * size)))
    if tag_type == STRING:
        return Tag(STRING, _read_string(stream))
    if tag_type == LIST:
        element_type = _exact(stream, 1)[0]
        (length,) = struct.unpack(">i", _exact(stream, 4))
        if length < 0 or (element_type == END and length > 0) or element_type > LONG_ARRAY:
            raise ValueError("Invalid NBT list header")
        return Tag(LIST, [_read_payload(stream, element_type, depth + 1) for _ in range(length)], element_type)
    if tag_type == COMPOUND:
        values = {}
        while True:
            child_type = _exact(stream, 1)[0]
            if child_type == END:
                return Tag(COMPOUND, values)
            if child_type > LONG_ARRAY:
                raise ValueError("Unknown NBT tag type")
            name = _read_string(stream)
            if name in values:
                raise ValueError("Duplicate NBT compound key: " + name)
            values[name] = _read_payload(stream, child_type, depth + 1)
    raise ValueError("Unknown NBT tag type")


def _write_string(stream, value):
    units = value.encode("utf-16-be", "surrogatepass")
    data = b"".join(chr(struct.unpack(">H", units[index:index + 2])[0]).encode("utf-8", "surrogatepass")
                    for index in range(0, len(units), 2)).replace(b"\x00", b"\xc0\x80")
    if len(data) > 0xFFFF:
        raise ValueError("NBT string too long")
    stream.write(struct.pack(">H", len(data)))
    stream.write(data)


def _write_payload(stream, tag):
    if tag.type in _NUMERIC:
        stream.write(struct.pack(_NUMERIC[tag.type], tag.value))
    elif tag.type in _ARRAY:
        stream.write(struct.pack(">i", len(tag.value)))
        stream.write(struct.pack(">%d%s" % (len(tag.value), _ARRAY[tag.type]), *tag.value))
    elif tag.type == STRING:
        _write_string(stream, tag.value)
    elif tag.type == LIST:
        element_type = tag.element_type if tag.element_type is not None else END
        if any(item.type != element_type for item in tag.value):
            raise ValueError("Mixed NBT list element types")
        stream.write(bytes([element_type]))
        stream.write(struct.pack(">i", len(tag.value)))
        for item in tag.value:
            _write_payload(stream, item)
    elif tag.type == COMPOUND:
        for name, child in tag.value.items():
            stream.write(bytes([child.type]))
            _write_string(stream, name)
            _write_payload(stream, child)
        stream.write(bytes([END]))
    else:
        raise ValueError("Unknown NBT tag type")


def parse(data):
    """Parse an uncompressed named root compound. Returns (root_name, Tag)."""
    stream = io.BytesIO(data)
    if _exact(stream, 1)[0] != COMPOUND:
        raise ValueError("NBT root must be a compound")
    name = _read_string(stream)
    root = _read_payload(stream, COMPOUND, 0)
    if stream.read(1):
        raise ValueError("Trailing bytes after NBT root")
    return name, root


def serialize(root, name=""):
    if root.type != COMPOUND:
        raise ValueError("NBT root must be a compound")
    stream = io.BytesIO()
    stream.write(bytes([COMPOUND]))
    _write_string(stream, name)
    _write_payload(stream, root)
    return stream.getvalue()


def load_gzip(data):
    """Parse a gzip-compressed NBT file (structure templates, level.dat)."""
    return parse(gzip.decompress(data))[1]


def dump_gzip(root, name=""):
    """Deterministic gzip output: fixed header timestamp and compression level."""
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, compresslevel=9, mtime=0) as stream:
        stream.write(serialize(root, name))
    return buffer.getvalue()


def read_region_chunks(data):
    """Yield (local_x, local_z, root Tag) for every chunk in an Anvil region file."""
    if len(data) < 8192:
        return
    for index in range(1024):
        offset, sectors = struct.unpack(">I", b"\x00" + data[index * 4:index * 4 + 3])[0], data[index * 4 + 3]
        if offset == 0 or sectors == 0:
            continue
        start = offset * 4096
        if start + 5 > len(data):
            raise ValueError("Region chunk offset outside file")
        (length,) = struct.unpack(">I", data[start:start + 4])
        compression = data[start + 4]
        payload = data[start + 5:start + 4 + length]
        if len(payload) != length - 1:
            raise ValueError("Truncated region chunk")
        if compression == 2:
            raw = zlib.decompress(payload)
        elif compression == 1:
            raw = gzip.decompress(payload)
        elif compression == 3:
            raw = payload
        else:
            raise ValueError("Unsupported region chunk compression %d" % compression)
        yield index % 32, index // 32, parse(raw)[1]
