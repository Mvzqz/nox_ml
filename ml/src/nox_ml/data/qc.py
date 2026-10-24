"""Quality-control result shared by the SIMAT and TEMPO checks."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Check:
    """One QC finding. `ok=None` is informational (neither pass nor fail)."""

    ok: bool | None
    message: str

    def __str__(self) -> str:
        mark = "info" if self.ok is None else ("ok" if self.ok else "FAIL")
        return f"[{mark}] {self.message}"


def render(checks: list[Check]) -> str:
    return "\n".join(str(c) for c in checks)
