import json
import mmap
import os
import struct
from typing import List

_INITIAL_MMAP_SIZE = 1 << 16
_pack_integer_func = struct.Struct(b'i').pack
_pack_two_doubles_func = struct.Struct(b'dd').pack
_unpack_integer = struct.Struct(b'i').unpack_from
_unpack_two_doubles = struct.Struct(b'dd').unpack_from


def _pack_two_doubles(data, pos, value, timestamp):
    data[pos:pos + 16] = _pack_two_doubles_func(value, timestamp)


def _pack_integer(data, pos, value):
    data[pos:pos + 4] = _pack_integer_func(value)


def _read_all_values(data, used=0):
    """Yield (key, value, timestamp, pos). No locking is performed."""

    if used <= 0:
        used = _unpack_integer(data, 0)[0]

    pos = 8

    while pos < used:
        encoded_len = _unpack_integer(data, pos)[0]
        if encoded_len + pos > used:
            raise RuntimeError('Read beyond file size detected, file is corrupted.')
        pos += 4
        encoded_key = data[pos:pos + encoded_len]
        padded_len = encoded_len + (8 - (encoded_len + 4) % 8)
        pos += padded_len
        value, timestamp = _unpack_two_doubles(data, pos)
        yield encoded_key.decode('utf-8'), value, timestamp, pos
        pos += 16


class MmapedDict:
    """A dict of doubles, backed by an mmapped file."""

    def __init__(self, filename, read_mode=False):
        self._f = open(filename, 'rb' if read_mode else 'a+b')
        self._fname = filename
        capacity = os.fstat(self._f.fileno()).st_size
        if capacity == 0:
            self._f.truncate(_INITIAL_MMAP_SIZE)
            capacity = _INITIAL_MMAP_SIZE
        self._capacity = capacity
        self._m = mmap.mmap(self._f.fileno(), self._capacity,
                            access=mmap.ACCESS_READ if read_mode else mmap.ACCESS_WRITE)

        self._positions = {}
        self._used = _unpack_integer(self._m, 0)[0]
        if self._used == 0:
            self._used = 8
            _pack_integer(self._m, 0, self._used)
        else:
            if not read_mode:
                for key, _, _, pos in self._read_all_values():
                    self._positions[key] = pos

    @staticmethod
    def read_all_values_from_file(filename):
        with open(filename, 'rb') as infp:
            data = infp.read(mmap.PAGESIZE)
            used = _unpack_integer(data, 0)[0]
            if used > len(data):
                data += infp.read(used - len(data))
        return _read_all_values(data, used)

    def _init_value(self, key):
        """Initialize a value. Lock must be held by caller."""
        encoded = key.encode('utf-8')
        padded = encoded + (b' ' * (8 - (len(encoded) + 4) % 8))
        value = struct.pack(f'i{len(padded)}sdd'.encode(), len(encoded), padded, 0.0, 0.0)
        while self._used + len(value) > self._capacity:
            self._capacity *= 2
            self._f.truncate(self._capacity)
            self._m.close()
            self._m = mmap.mmap(self._f.fileno(), self._capacity, access=mmap.ACCESS_WRITE)
        self._m[self._used:self._used + len(value)] = value

        self._used += len(value)
        _pack_integer(self._m, 0, self._used)
        self._positions[key] = self._used - 16

    def _read_all_values(self):
        return _read_all_values(data=self._m, used=self._used)

    def read_all_values(self):
        for k, v, ts, _ in self._read_all_values():
            yield k, v, ts

    def read_value(self, key):
        if key not in self._positions:
            self._init_value(key)
        pos = self._positions[key]
        return _unpack_two_doubles(self._m, pos)

    def write_value(self, key, value, timestamp):
        if key not in self._positions:
            self._init_value(key)
        pos = self._positions[key]
        _pack_two_doubles(self._m, pos, value, timestamp)

    def close(self):
        if getattr(self, "_m", None) is not None:
            self._m.close()
            self._m = None
        if getattr(self, "_f", None) is not None:
            self._f.close()
            self._f = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def mmap_key(metric_name: str, name: str, labelnames: List[str], labelvalues: List[str], help_text: str) -> str:
    labels = dict(zip(labelnames, labelvalues))
    return json.dumps([metric_name, name, labels, help_text], sort_keys=True)
