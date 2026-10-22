"""Descriptor-based private text files for POSIX and local Windows disks.

POSIX requires O_NOFOLLOW, a regular file owned by the current UID, and no
group/other permissions. Windows requires persistent ACLs, a non-reparse regular
file owned by the process user, and a DACL granting rights only to that user,
LocalSystem or Builtin Administrators. Unknown effective ACE types fail closed.
Windows device/UNC paths and alternate data streams are outside this contract.
As with POSIX O_NOFOLLOW, the no-link check covers the final path component;
ancestors must be trusted. Neither platform protects against its own user or
privileged administrators changing permissions/content concurrently.
"""

import os
import secrets
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

if os.name == "nt":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _SecurityAttributes(ctypes.Structure):
        _fields_ = [
            ("length", wintypes.DWORD),
            ("descriptor", wintypes.LPVOID),
            ("inherit", wintypes.BOOL),
        ]

    class _Acl(ctypes.Structure):
        _fields_ = [
            ("revision", wintypes.BYTE),
            ("reserved", wintypes.BYTE),
            ("size", wintypes.WORD),
            ("count", wintypes.WORD),
            ("reserved2", wintypes.WORD),
        ]

    class _AceHeader(ctypes.Structure):
        _fields_ = [
            ("kind", wintypes.BYTE),
            ("flags", wintypes.BYTE),
            ("size", wintypes.WORD),
        ]

    class _AttributeTag(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]

    def _native(dll, name, result, *arguments):
        function = getattr(dll, name)
        function.restype = result
        function.argtypes = list(arguments)
        return function

    _kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    _ptr = wintypes.LPVOID
    _out = ctypes.POINTER(_ptr)
    _dword_out = ctypes.POINTER(wintypes.DWORD)
    _create_file = _native(
        _kernel,
        "CreateFileW",
        wintypes.HANDLE,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        _ptr,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    _create_directory = _native(
        _kernel, "CreateDirectoryW", wintypes.BOOL, wintypes.LPCWSTR, _ptr
    )
    _close = _native(_kernel, "CloseHandle", wintypes.BOOL, wintypes.HANDLE)
    _free = _native(_kernel, "LocalFree", _ptr, _ptr)
    _process = _native(_kernel, "GetCurrentProcess", wintypes.HANDLE)
    _file_type = _native(_kernel, "GetFileType", wintypes.DWORD, wintypes.HANDLE)
    _attributes = _native(
        _kernel,
        "GetFileInformationByHandleEx",
        wintypes.BOOL,
        wintypes.HANDLE,
        ctypes.c_int,
        _ptr,
        wintypes.DWORD,
    )
    _volume = _native(
        _kernel,
        "GetVolumeInformationByHandleW",
        wintypes.BOOL,
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        _dword_out,
        _dword_out,
        _dword_out,
        wintypes.LPWSTR,
        wintypes.DWORD,
    )
    _open_token = _native(
        _advapi,
        "OpenProcessToken",
        wintypes.BOOL,
        wintypes.HANDLE,
        wintypes.DWORD,
        _out,
    )
    _token_info = _native(
        _advapi,
        "GetTokenInformation",
        wintypes.BOOL,
        wintypes.HANDLE,
        ctypes.c_int,
        _ptr,
        wintypes.DWORD,
        _dword_out,
    )
    _sid_text = _native(_advapi, "ConvertSidToStringSidW", wintypes.BOOL, _ptr, _out)
    _security_info = _native(
        _advapi,
        "GetSecurityInfo",
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.DWORD,
        _out,
        _out,
        _out,
        _out,
        _out,
    )
    _get_ace = _native(_advapi, "GetAce", wintypes.BOOL, _ptr, wintypes.DWORD, _out)
    _convert_sddl = _native(
        _advapi,
        "ConvertStringSecurityDescriptorToSecurityDescriptorW",
        wintypes.BOOL,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        _out,
        _dword_out,
    )

    def _check(result):
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        return result

    def _sid_string(sid):
        text = _ptr()
        _check(_sid_text(sid, ctypes.byref(text)))
        try:
            return ctypes.wstring_at(text)
        finally:
            _free(text)

    def _current_sid():
        token = _ptr()
        _check(_open_token(_process(), 0x0008, ctypes.byref(token)))  # TOKEN_QUERY
        try:
            size = wintypes.DWORD()
            if (
                not _token_info(token, 1, None, 0, ctypes.byref(size))
                and ctypes.get_last_error() != 122  # ERROR_INSUFFICIENT_BUFFER
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            buffer = ctypes.create_string_buffer(size.value)
            _check(_token_info(token, 1, buffer, size, ctypes.byref(size)))
            return _sid_string(_ptr.from_buffer(buffer).value)  # TOKEN_USER.Sid
        finally:
            _close(token)

    @contextmanager
    def _security_attributes():
        sid = _current_sid()
        descriptor = _ptr()
        # Protected DACL: no inherited grants, including on Python 3.11/3.12.
        _check(
            _convert_sddl(
                f"O:{sid}D:P(A;;FA;;;{sid})", 1, ctypes.byref(descriptor), None
            )
        )
        try:
            yield _SecurityAttributes(
                ctypes.sizeof(_SecurityAttributes), descriptor, False
            )
        finally:
            _free(descriptor)

    def _windows_path(path):
        path = os.path.abspath(path)
        drive, tail = os.path.splitdrive(path)
        if len(drive) != 2 or drive[1] != ":" or ":" in tail:
            raise ValueError("Private files require a local Windows disk path")
        return "\\\\?\\" + path

    def _windows_handle(path, *, create=False, security=None):
        handle = _create_file(
            _windows_path(path),
            0xC0000000 if create else 0x80000000,
            1,  # FILE_SHARE_READ: readers may reopen; no writes/deletes.
            ctypes.byref(security) if security is not None else None,
            1 if create else 3,  # CREATE_NEW / OPEN_EXISTING
            0x02200000,  # OPEN_REPARSE_POINT | BACKUP_SEMANTICS
            None,
        )
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    def _validate_windows(handle, *, directory=False):
        attributes = _AttributeTag()
        _check(
            _attributes(handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes))
        )
        if attributes.attributes & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
            raise ValueError("Private file must not be a symlink/reparse point")
        if _file_type(handle) != 1 or bool(attributes.attributes & 0x10) != directory:
            raise ValueError("Private file must be a regular file")
        flags = wintypes.DWORD()
        _check(_volume(handle, None, 0, None, None, ctypes.byref(flags), None, 0))
        if not flags.value & 0x8:  # FS_PERSISTENT_ACLS
            raise ValueError("Private files require persistent Windows ACLs")
        owner, dacl, descriptor = _ptr(), _ptr(), _ptr()
        result = _security_info(
            handle,
            1,
            0x5,
            ctypes.byref(owner),
            None,
            ctypes.byref(dacl),
            None,
            ctypes.byref(descriptor),
        )  # SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION
        if result:
            raise ctypes.WinError(result)
        try:
            user = _current_sid()
            if not owner or _sid_string(owner) != user:
                raise ValueError("Private file must be owned by this user")
            if not dacl:
                raise ValueError("Unsafe private file permissions: null DACL")
            trusted = {user, "S-1-5-18", "S-1-5-32-544"}
            for index in range(_Acl.from_address(dacl.value).count):
                ace = _ptr()
                _check(_get_ace(dacl, index, ctypes.byref(ace)))
                header = _AceHeader.from_address(ace.value)
                if header.flags & 0x08 or header.kind == 1:  # INHERIT_ONLY / deny
                    continue
                if header.kind != 0 or header.size < 16:
                    raise ValueError("Unsafe private file permissions: unsupported ACE")
                mask = wintypes.DWORD.from_address(ace.value + 4).value
                if mask and _sid_string(ace.value + 8) not in trusted:
                    raise ValueError(
                        "Unsafe private file permissions: non-private DACL"
                    )
        finally:
            _free(descriptor)

    def _windows_descriptor(path, *, create=False, security=None):
        handle = _windows_handle(path, create=create, security=security)
        try:
            _validate_windows(handle)
            descriptor = msvcrt.open_osfhandle(
                handle, (os.O_RDWR if create else os.O_RDONLY) | os.O_BINARY
            )
        except BaseException:
            _close(handle)
            if create:
                Path(path).unlink()
            raise
        return descriptor  # The CRT descriptor now owns the native handle.


@contextmanager
def open_private_text(path):
    """Validate the opened object before any UTF-8 content is read."""
    if os.name == "nt":
        descriptor = _windows_descriptor(path)
    elif os.name == "posix" and hasattr(os, "O_NOFOLLOW"):
        # NONBLOCK avoids hanging on a FIFO before fstat rejects it.
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Private file must be a regular file")
            if info.st_uid != os.getuid():
                raise ValueError("Private file must be owned by this user")
            if info.st_mode & 0o077:
                raise ValueError("Unsafe private file permissions; require mode 0600")
        except BaseException:
            os.close(descriptor)
            raise
    else:
        raise RuntimeError("Private files are unsupported on this platform")
    try:
        handle = os.fdopen(descriptor, "r", encoding="utf-8")
    except BaseException:
        os.close(descriptor)
        raise
    with handle:
        yield handle


@contextmanager
def private_text_file(content):
    """Yield a private temporary pathname; clean up on normal/exceptional context exit.

    The containing directory and the file are private before secrets are written.
    On Windows, hold both open without delete sharing while the consumer runs.
    """
    directory_handle = None
    if os.name == "nt":
        directory = Path(tempfile.gettempdir()) / (
            "cnc-private-" + secrets.token_hex(16)
        )
        with _security_attributes() as security:
            _check(_create_directory(_windows_path(directory), ctypes.byref(security)))
    elif os.name == "posix" and hasattr(os, "O_NOFOLLOW"):
        directory = Path(tempfile.mkdtemp(prefix="cnc-private-"))
    else:
        raise RuntimeError("Private files are unsupported on this platform")
    path = directory / "credentials.auth"
    created = False
    try:
        if os.name == "nt":
            directory_handle = _windows_handle(directory)
            _validate_windows(directory_handle, directory=True)
            with _security_attributes() as security:
                descriptor = _windows_descriptor(path, create=True, security=security)
        else:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        try:
            handle = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        except BaseException:
            os.close(descriptor)
            raise
        with handle:
            handle.write(content)
        with open_private_text(path):
            yield path
    finally:
        if directory_handle is not None:
            _close(directory_handle)
        if created:
            path.unlink()
        directory.rmdir()
