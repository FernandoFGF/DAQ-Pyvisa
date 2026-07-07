"""
In-memory fake of ``InstrumentConnection`` for testing the
acquisition adapters without pyvisa or real hardware.

The fake records every ``write``/``query`` so tests can assert both
the SCPI command sequence and the parsed return values. Responses are
programmed with ``set_response(cmd, value)`` (exact match) or
``set_default_response(value)`` (fallback). Use ``set_response_prefix``
to match by SCPI command prefix (e.g. for queries that include
arguments like ``:FETC:ARR:CURR?``).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Union


Response = Union[str, bytes, float, int]


class FakeConnection:
    def __init__(self) -> None:
        self.writes: List[str] = []
        self.queries: List[str] = []
        self._exact: Dict[str, str] = {}
        self._prefix: List[Tuple[str, str]] = []
        self._default: Optional[str] = None
        self.closed = False

    # ---- Programming responses ----

    def set_response(self, command: str, value: Response) -> None:
        self._exact[command] = self._coerce(value)

    def set_response_prefix(self, prefix: str, value: Response) -> None:
        self._prefix.append((prefix, self._coerce(value)))

    def set_default_response(self, value: Response) -> None:
        self._default = self._coerce(value)

    @staticmethod
    def _coerce(value: Response) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    # ---- Protocol surface ----

    def write(self, command: str) -> None:
        self.writes.append(command)

    def query(self, command: str) -> str:
        self.queries.append(command)
        if command in self._exact:
            return self._exact[command]
        for prefix, value in self._prefix:
            if command.startswith(prefix):
                return value
        if self._default is not None:
            return self._default
        raise AssertionError(f"FakeConnection: no programmed response for {command!r}")

    def read_raw(self) -> bytes:
        return b""

    def close(self) -> None:
        self.closed = True

    # Convenience attribute used by the adapters
    @property
    def timeout(self):
        return None

    @timeout.setter
    def timeout(self, value):
        pass

    def __delattr__(self, name):
        # Used by ``del conn.timeout`` in the adapters. Swallow it.
        if name == "timeout":
            return
        super().__delattr__(name)
