import json
import mmap
import os
import struct

_INITIAL_MMAP_SIZE = 1 << 20
_pack_integer = struct.Struct(b'i').pack_into
_pack_double = struct.Struct(b'd').pack_into
_unpack_integer = struct.Struct(b'i').unpack_from
_unpack_double = struct.Struct(b'd').unpack_from


class _MmapedDict(object):
    """A dict of doubles, backed by an mmapped file.

    The file starts with a 4 byte int, indicating how much of it is used.
    Then 4 bytes of padding.
    There's then a number of entries, consisting of a 4 byte int which is the
    size of the next field, a utf-8 encoded string key, padding to a 8 byte
    alignment, and then a 8 byte float which is the value.

    Not thread safe.
    """

    def __init__(self, filename, read_mode=False):
        self._f = open(filename, 'rb' if read_mode else 'a+b')
        if os.fstat(self._f.fileno()).st_size == 0:
            self._f.truncate(_INITIAL_MMAP_SIZE)
        self._capacity = os.fstat(self._f.fileno()).st_size
        self._m = mmap.mmap(self._f.fileno(), self._capacity, access=mmap.ACCESS_READ if read_mode else mmap.ACCESS_WRITE)

        self._positions = {}
        self._used = _unpack_integer(self._m, 0)[0]
        if self._used == 0:
            self._used = 8
            _pack_integer(self._m, 0, self._used)
        else:
            if not read_mode:
                for key, _, pos in self._read_all_values():
                    self._positions[key] = pos

    def _init_value(self, key):
        """Initialize a value. Lock must be held by caller."""
        encoded = key.encode('utf-8')
        # Pad to be 8-byte aligned.
        padded = encoded + (b' ' * (8 - (len(encoded) + 4) % 8))
        value = struct.pack('i{0}sd'.format(len(padded)).encode(), len(encoded), padded, 0.0)
        while self._used + len(value) > self._capacity:
            self._capacity *= 2
            self._f.truncate(self._capacity)
            self._m = mmap.mmap(self._f.fileno(), self._capacity)
        self._m[self._used:self._used + len(value)] = value

        # Update how much space we've used.
        self._used += len(value)
        _pack_integer(self._m, 0, self._used)
        self._positions[key] = self._used - 8

    def _read_all_values(self):
        """Yield (key, value, pos). No locking is performed."""

        pos = 8

        # cache variables to local ones and prevent attributes lookup
        # on every loop iteration
        used = self._used
        data = self._m
        unpack_from = struct.unpack_from

        while pos < used:
            encoded_len = _unpack_integer(data, pos)[0]
            pos += 4
            encoded = unpack_from(('%ss' % encoded_len).encode(), data, pos)[0]
            padded_len = encoded_len + (8 - (encoded_len + 4) % 8)
            pos += padded_len
            value = _unpack_double(data, pos)[0]
            yield encoded.decode('utf-8'), value, pos
            pos += 8

    def read_all_values(self):
        """Yield (key, value, pos). No locking is performed."""
        for k, v, _ in self._read_all_values():
            yield k, v

    def read_value(self, key):
        if key not in self._positions:
            self._init_value(key)
        pos = self._positions[key]
        # We assume that reading from an 8 byte aligned value is atomic
        return _unpack_double(self._m, pos)[0]

    def write_value(self, key, value):
        if key not in self._positions:
            self._init_value(key)
        pos = self._positions[key]
        # We assume that writing to an 8 byte aligned value is atomic
        _pack_double(self._m, pos, value)

    def close(self):
        if self._f:
            self._m.close()
            self._m = None
            self._f.close()
            self._f = None


def _mmap_key(metric_name, name, labelnames, labelvalues):
    """Format a key for use in the mmap file."""
    # ensure labels are in consistent order for identity
    labels = dict(zip(labelnames, labelvalues))
    return json.dumps([metric_name, name, labels], sort_keys=True)
