"""Command parsing and result types for the text-world frontend."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import StrEnum


class CommandKind(StrEnum):
    LOOK = "look"
    MAP = "map"
    MOVE = "move"
    ADVANCE = "advance"
    ATTACK = "attack"
    INSPECT = "inspect"
    WAIT = "wait"
    STATUS = "status"
    TAKE = "take"
    PUT = "put"
    DROP = "drop"
    INVENTORY = "inventory"
    TALK = "talk"
    OPEN = "open"
    CLOSE = "close"
    SHOOT = "shoot"
    HELP = "help"
    QUIT = "quit"


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    kind: CommandKind
    args: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: ParsedCommand
    output: str
    elapsed_seconds: float
    quit: bool = False


def parse_command(text: str) -> ParsedCommand:
    try:
        parts = shlex.split(text)
    except ValueError as exc:
        raise ValueError(f"invalid command syntax: {exc}") from exc
    if not parts:
        raise ValueError("command may not be empty")
    try:
        kind = CommandKind(parts[0].lower())
    except ValueError as exc:
        raise ValueError(f"unknown command: {parts[0]}") from exc
    return ParsedCommand(kind, tuple(parts[1:]))
