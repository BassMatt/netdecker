"""Command result handling for NetDecker CLI."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from netdecker.config import LOGGER


class MessageType(Enum):
    """Types of messages that can be logged."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


@dataclass
class CommandResult:
    """Encapsulates the result of a CLI command execution."""

    success: bool
    message: str | None = None
    message_type: MessageType = MessageType.INFO
    data: Any = None  # For commands that return data

    @property
    def exit_code(self) -> int:
        """Convert success status to exit code."""
        return 0 if self.success else 1

    def log(self) -> None:
        """Log the message if present."""
        if not self.message:
            return

        if self.message_type == MessageType.ERROR:
            LOGGER.error(self.message)
        elif self.message_type == MessageType.WARNING:
            LOGGER.warning(self.message)
        elif self.message_type == MessageType.SUCCESS:
            LOGGER.info(f"✓ {self.message}")
        else:
            LOGGER.info(self.message)


# Convenience constructors
def success(message: str | None = None, data: Any = None) -> CommandResult:
    """Create a successful result."""
    return CommandResult(
        success=True,
        message=message,
        message_type=MessageType.SUCCESS if message else MessageType.INFO,
        data=data,
    )


def error(message: str, data: Any = None) -> CommandResult:
    """Create an error result."""
    return CommandResult(
        success=False, message=message, message_type=MessageType.ERROR, data=data
    )


def warning(message: str, data: Any = None) -> CommandResult:
    """Create a warning result (successful but with warning)."""
    return CommandResult(
        success=True, message=message, message_type=MessageType.WARNING, data=data
    )


def info(message: str, data: Any = None) -> CommandResult:
    """Create an info result."""
    return CommandResult(
        success=True, message=message, message_type=MessageType.INFO, data=data
    )
