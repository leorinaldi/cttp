"""Extractors: what a definition is, per language."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Page:
    """What an address points at: a definition or a script."""

    kind: str  # "script" | "function" | "class" | "constant"
    source: str  # normalized source text
    language: str
    span: tuple[int, int]  # 1-based inclusive line range in the origin file
