from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from threading import RLock

from runtime.state import SensitiveCategory


@dataclass
class TokenVault:
    """In-memory local token vault for Phase 1.

    The mapping deliberately lives outside sanitized state. Production builds
    should swap this for an encrypted local store with process isolation.
    """

    _values: dict[str, str] = field(default_factory=dict)
    _reverse: dict[tuple[SensitiveCategory, str], str] = field(default_factory=dict)
    _counters: defaultdict[SensitiveCategory, int] = field(default_factory=lambda: defaultdict(int))
    _lock: RLock = field(default_factory=RLock)

    def tokenize(self, category: SensitiveCategory, value: str) -> str:
        with self._lock:
            key = (category, value)
            if key in self._reverse:
                return self._reverse[key]
            self._counters[category] += 1
            token = f"{category.value}_{self._counters[category]:03d}"
            self._values[token] = value
            self._reverse[key] = token
            return token

    def resolve(self, token: str) -> str:
        with self._lock:
            if token not in self._values:
                raise KeyError(f"Unknown sensitive token: {token}")
            return self._values[token]

    def has(self, token: str) -> bool:
        with self._lock:
            return token in self._values

    def stats(self) -> dict[str, int]:
        with self._lock:
            by_prefix: dict[str, int] = {}
            for token in self._values:
                prefix = token.rsplit("_", 1)[0]
                by_prefix[prefix] = by_prefix.get(prefix, 0) + 1
            return by_prefix

