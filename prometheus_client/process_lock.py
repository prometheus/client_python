#!/usr/bin/env python
# coding=utf-8

import os

__all__ = ('LOCK_EX', 'LOCK_SH', 'LOCK_NB', 'lock', 'unlock')


def _fd(f):
    return f.fileno() if hasattr(f, 'fileno') else f


if os.name == 'nt':
    import msvcrt
    from ctypes import (sizeof, c_ulong, c_void_p, c_int64,
                        Structure, Union, POINTER, windll, byref)
    from ctypes.wintypes import BOOL, DWORD, HANDLE

    LOCK_SH = 0  # the default
    LOCK_NB = 0x1  # LOCKFILE_FAIL_IMMEDIATELY
    LOCK_EX = 0x2  # LOCKFILE_EXCLUSIVE_LOCK

    if sizeof(c_ulong) != sizeof(c_void_p):
        ULONG_PTR = c_int64
    else:
        ULONG_PTR = c_ulong
    PVOID = c_void_p


    class _OFFSET(Structure):
        _fields_ = [
            ('Offset', DWORD),
            ('OffsetHigh', DWORD)]


    class _OFFSET_UNION(Union):
        _anonymous_ = ['_offset']
        _fields_ = [
            ('_offset', _OFFSET),
            ('Pointer', PVOID)]


    class OVERLAPPED(Structure):
        _anonymous_ = ['_offset_union']
        _fields_ = [
            ('Internal', ULONG_PTR),
            ('InternalHigh', ULONG_PTR),
            ('_offset_union', _OFFSET_UNION),
            ('hEvent', HANDLE)]


    LPOVERLAPPED = POINTER(OVERLAPPED)

    LockFileEx = windll.kernel32.LockFileEx
    LockFileEx.restype = BOOL
    LockFileEx.argtypes = [HANDLE, DWORD, DWORD, DWORD, DWORD, LPOVERLAPPED]
    UnlockFileEx = windll.kernel32.UnlockFileEx
    UnlockFileEx.restype = BOOL
    UnlockFileEx.argtypes = [HANDLE, DWORD, DWORD, DWORD, LPOVERLAPPED]


    def lock(f, flags):
        hfile = msvcrt.get_osfhandle(_fd(f))
        overlapped = OVERLAPPED()
        ret = LockFileEx(hfile, flags, 0, 0, 0xFFFF0000, byref(overlapped))
        return bool(ret)


    def unlock(f):
        hfile = msvcrt.get_osfhandle(_fd(f))
        overlapped = OVERLAPPED()
        ret = UnlockFileEx(hfile, 0, 0, 0xFFFF0000, byref(overlapped))
        return bool(ret)
else:
    try:
        import fcntl

        LOCK_SH = fcntl.LOCK_SH  # shared lock
        LOCK_NB = fcntl.LOCK_NB  # non-blocking
        LOCK_EX = fcntl.LOCK_EX
    except (ImportError, AttributeError):
        LOCK_EX = LOCK_SH = LOCK_NB = 0


        def lock(f, flags):
            return False


        def unlock(f):
            return True
    else:
        def lock(f, flags):
            ret = fcntl.flock(_fd(f), flags)
            return ret == 0


        def unlock(f):
            ret = fcntl.flock(_fd(f), fcntl.LOCK_UN)
            return ret == 0
