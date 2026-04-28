"""
法律法规台账生成模块
"""

__all__ = ["LedgerGenerator"]


def __getattr__(name):
    """Lazily import optional report exporters and their heavy dependencies."""
    if name == "LedgerGenerator":
        from .ledger_generator import LedgerGenerator

        return LedgerGenerator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
