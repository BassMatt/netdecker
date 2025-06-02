"""Tests for NetDecker CLI result handling."""

import pytest

from netdecker.cli.result import (
    CommandResult,
    MessageType,
    error,
    info,
    success,
    warning,
)


class TestMessageType:
    """Test cases for MessageType enum."""

    def test_message_type_values(self):
        """Test that MessageType enum has expected values."""
        assert MessageType.INFO.value == "info"
        assert MessageType.WARNING.value == "warning"
        assert MessageType.ERROR.value == "error"
        assert MessageType.SUCCESS.value == "success"


class TestCommandResult:
    """Test cases for CommandResult class."""

    def test_command_result_success_exit_code(self):
        """Test that successful results have exit code 0."""
        result = CommandResult(success=True)
        assert result.exit_code == 0

    def test_command_result_failure_exit_code(self):
        """Test that failed results have exit code 1."""
        result = CommandResult(success=False)
        assert result.exit_code == 1

    def test_command_result_defaults(self):
        """Test CommandResult default values."""
        result = CommandResult(success=True)

        assert result.success is True
        assert result.message is None
        assert result.message_type == MessageType.INFO
        assert result.data is None

    def test_command_result_with_data(self):
        """Test CommandResult with custom data."""
        test_data = {"key": "value", "items": [1, 2, 3]}
        result = CommandResult(success=True, data=test_data)

        assert result.data == test_data

    def test_log_no_message(self, mock_logger):
        """Test logging when no message is set."""
        result = CommandResult(success=True)
        result.log()

        # No logger methods should be called
        mock_logger["info"].assert_not_called()
        mock_logger["error"].assert_not_called()
        mock_logger["warning"].assert_not_called()

    def test_log_error_message(self, mock_logger):
        """Test logging error messages."""
        result = CommandResult(
            success=False, message="Test error message", message_type=MessageType.ERROR
        )
        result.log()

        mock_logger["error"].assert_called_once_with("Test error message")

    def test_log_warning_message(self, mock_logger):
        """Test logging warning messages."""
        result = CommandResult(
            success=True,
            message="Test warning message",
            message_type=MessageType.WARNING,
        )
        result.log()

        mock_logger["warning"].assert_called_once_with("Test warning message")

    def test_log_success_message(self, mock_logger):
        """Test logging success messages."""
        result = CommandResult(
            success=True,
            message="Test success message",
            message_type=MessageType.SUCCESS,
        )
        result.log()

        mock_logger["info"].assert_called_once_with("✓ Test success message")

    def test_log_info_message(self, mock_logger):
        """Test logging info messages."""
        result = CommandResult(
            success=True, message="Test info message", message_type=MessageType.INFO
        )
        result.log()

        mock_logger["info"].assert_called_once_with("Test info message")


class TestConvenienceConstructors:
    """Test cases for convenience constructor functions."""

    def test_success_no_message(self):
        """Test success constructor without message."""
        result = success()

        assert result.success is True
        assert result.message is None
        assert result.message_type == MessageType.INFO
        assert result.data is None

    def test_success_with_message(self):
        """Test success constructor with message."""
        result = success("Operation completed successfully")

        assert result.success is True
        assert result.message == "Operation completed successfully"
        assert result.message_type == MessageType.SUCCESS
        assert result.data is None

    def test_success_with_data(self):
        """Test success constructor with data."""
        test_data = {"result": "data"}
        result = success("Success", data=test_data)

        assert result.success is True
        assert result.message == "Success"
        assert result.message_type == MessageType.SUCCESS
        assert result.data == test_data

    def test_error_constructor(self):
        """Test error constructor."""
        result = error("Something went wrong")

        assert result.success is False
        assert result.message == "Something went wrong"
        assert result.message_type == MessageType.ERROR
        assert result.data is None

    def test_error_with_data(self):
        """Test error constructor with data."""
        test_data = {"error_code": 404}
        result = error("Not found", data=test_data)

        assert result.success is False
        assert result.message == "Not found"
        assert result.message_type == MessageType.ERROR
        assert result.data == test_data

    def test_warning_constructor(self):
        """Test warning constructor."""
        result = warning("This is a warning")

        assert result.success is True  # Warnings are still successful
        assert result.message == "This is a warning"
        assert result.message_type == MessageType.WARNING
        assert result.data is None

    def test_warning_with_data(self):
        """Test warning constructor with data."""
        test_data = {"warning_details": "deprecated feature"}
        result = warning("Deprecated feature used", data=test_data)

        assert result.success is True
        assert result.message == "Deprecated feature used"
        assert result.message_type == MessageType.WARNING
        assert result.data == test_data

    def test_info_constructor(self):
        """Test info constructor."""
        result = info("Informational message")

        assert result.success is True
        assert result.message == "Informational message"
        assert result.message_type == MessageType.INFO
        assert result.data is None

    def test_info_with_data(self):
        """Test info constructor with data."""
        test_data = {"count": 42}
        result = info("Process completed", data=test_data)

        assert result.success is True
        assert result.message == "Process completed"
        assert result.message_type == MessageType.INFO
        assert result.data == test_data

    @pytest.mark.parametrize(
        "constructor,expected_success,expected_type",
        [
            (success, True, MessageType.SUCCESS),
            (error, False, MessageType.ERROR),
            (warning, True, MessageType.WARNING),
            (info, True, MessageType.INFO),
        ],
    )
    def test_constructor_types(self, constructor, expected_success, expected_type):
        """Test that constructors create results with correct types."""
        result = constructor("Test message")

        assert result.success == expected_success
        assert result.message_type == expected_type
        assert result.message == "Test message"

    def test_chained_operations(self):
        """Test that results can be used in chained operations."""
        # Simulate a workflow where we might chain results
        result1 = success("First step completed")

        if result1.success:
            result2 = success("Second step completed")
        else:
            result2 = error("First step failed")

        assert result1.success is True
        assert result2.success is True
        assert result1.message == "First step completed"
        assert result2.message == "Second step completed"

    def test_exit_code_consistency(self):
        """Test that exit codes are consistent with success status."""
        success_result = success("Success")
        error_result = error("Error")
        warning_result = warning("Warning")
        info_result = info("Info")

        assert success_result.exit_code == 0
        assert error_result.exit_code == 1
        assert warning_result.exit_code == 0  # Warnings are still successful
        assert info_result.exit_code == 0
