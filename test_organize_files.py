import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import json
import shutil
from io import StringIO
from file_organizer import (
    load_custom_rules, 
    save_custom_rules, 
    add_custom_rule, 
    log_movement, 
    undo_selected_moves, 
    reset_custom_rules,
    alert_user,
    categorize_error,
    retry_move_file
)

CUSTOM_RULES_FILE = 'custom_rules.json'
LOG_FILE = "file_movement_log.json"

class TestFileOrganizer(unittest.TestCase):

    @patch("os.rename")
    def test_retry_move_file_success(self, mock_rename):
        """Test file move success on the first try."""
        mock_rename.return_value = None  # Simulate successful rename
        result = retry_move_file("source.txt", "destination.txt")
        self.assertTrue(result)
        mock_rename.assert_called_once_with("source.txt", "destination.txt")

    @patch("os.rename")
    @patch("time.sleep", return_value=None)  # To skip actual sleep during test
    def test_retry_move_file_recoverable_error(self, mock_sleep, mock_rename):
        """Test file move with recoverable errors and eventual success."""
        mock_rename.side_effect = [PermissionError, None]  # Fail once, then succeed
        result = retry_move_file("source.txt", "destination.txt")
        self.assertTrue(result)
        self.assertEqual(mock_rename.call_count, 2)

    @patch("os.rename")
    @patch("time.sleep", return_value=None)
    @patch("file_organizer.alert_user")
    def test_retry_move_file_non_recoverable_error(self, mock_alert, mock_sleep, mock_rename):
        """Test file move with non-recoverable errors."""
        mock_rename.side_effect = FileNotFoundError  # Always fail with non-recoverable error
        result = retry_move_file("source.txt", "destination.txt")
        self.assertFalse(result)
        self.assertEqual(mock_rename.call_count, 1)
        mock_alert.assert_not_called()

    @patch("os.rename")
    @patch("time.sleep", return_value=None)
    @patch("file_organizer.alert_user")
    def test_retry_move_file_fail_after_retries(self, mock_alert, mock_sleep, mock_rename):
        """Test file move failure after all retries."""
        mock_rename.side_effect = PermissionError  # Always fail with recoverable error
        result = retry_move_file("source.txt", "destination.txt")
        self.assertFalse(result)
        self.assertEqual(mock_rename.call_count, 3)  # Should retry 3 times
        mock_alert.assert_called_once()

    def test_categorize_error_recoverable(self):
        """Test error categorization for recoverable errors."""
        error = PermissionError()
        result = categorize_error(error)
        self.assertEqual(result, "recoverable")

    def test_categorize_error_non_recoverable(self):
        """Test error categorization for non-recoverable errors."""
        error = FileNotFoundError()
        result = categorize_error(error)
        self.assertEqual(result, "non_recoverable")

    def test_categorize_error_unknown(self):
        """Test error categorization for unknown errors."""
        error = ValueError()
        result = categorize_error(error)
        self.assertEqual(result, "unknown")

    @patch("file_organizer.logger.critical")
    def test_alert_user(self, mock_critical):
        """Test user alert logging."""
        alert_user("Critical error occurred")
        mock_critical.assert_called_once_with("ALERT: Critical error occurred")
      
        
    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='{"custom_rule": "value"}')
    def test_load_custom_rules(self, mock_open, mock_exists):
        rules = load_custom_rules()
        mock_open.assert_called_once_with("custom_rules.json", "r")
        self.assertEqual(rules, {"custom_rule": "value"})


    @patch("builtins.open", new_callable=mock_open)
    @patch("json.dump")
    def test_save_custom_rules(self, mock_json_dump, mock_open):
        rules = {"image": "jpg", "document": "pdf"}
        
        save_custom_rules(rules)

        # Check that the file was opened in write mode
        mock_open.assert_called_once_with(CUSTOM_RULES_FILE, "w")
        mock_json_dump.assert_called_once_with(rules, mock_open(), indent=4)
        

    @patch("os.path.exists", return_value=False)
    def test_load_custom_rules_file_not_exist(self, mock_exists):
        rules = load_custom_rules()
        self.assertEqual(rules, {})

    @patch("file_organizer.load_custom_rules", return_value={})
    @patch("file_organizer.save_custom_rules")
    def test_add_custom_rule(self, mock_save_custom_rules, mock_load_custom_rules):
        add_custom_rule(".txt", "TextFiles")
        mock_load_custom_rules.assert_called_once()
        mock_save_custom_rules.assert_called_once_with({".txt": "TextFiles"})

    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    @patch("json.dump")
    @patch("os.path.exists")
    def test_log_movement_existing_log_file(self, mock_exists, mock_json_dump, mock_json_load, mock_open):
        # Test when the log file already exists
        mock_exists.return_value = True
        mock_json_load.return_value = {"old_file.txt": "old_destination.txt"}

        src = "source_file.txt"
        dest = "destination_file.txt"

        log_movement(src, dest)

        # Verify the existing log file is read and the new movement data is added
        mock_json_load.assert_called_once_with(mock_open())
        mock_json_dump.assert_called_with({"old_file.txt": "old_destination.txt", src: dest}, mock_open(), indent=4)


    @patch("os.remove")
    @patch("os.path.exists", return_value=True)
    def test_reset_custom_rules(self, mock_exists, mock_remove):
        reset_custom_rules()
        mock_remove.assert_called_once_with("custom_rules.json")

    @patch("os.path.exists", return_value=False)
    @patch("builtins.print")
    def test_reset_custom_rules_no_file(self, mock_print, mock_exists):
        reset_custom_rules()
        mock_print.assert_called_once_with("No custom rules found to reset.")
        

    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    @patch("json.dump")
    @patch("os.path.exists")
    @patch("shutil.move")
    @patch("os.makedirs")
    def test_undo_selected_moves(self, mock_makedirs, mock_shutil_move, mock_exists, mock_json_dump, mock_json_load, mock_open):
        # Test undo selected moves
        mock_exists.return_value = True
        mock_json_load.return_value = {
            "destination_file1.txt": "source_file1.txt",
            "destination_file2.txt": "source_file2.txt"
        }

        # Simulate the input for directory to undo actions
        with patch('builtins.input', return_value="source_file1"):
            undo_selected_moves()

        # Check that the files were moved back
        mock_shutil_move.assert_called_once_with("destination_file1.txt", "source_file1.txt")
        mock_makedirs.assert_called_once_with(os.path.dirname("source_file1.txt"), exist_ok=True)

        # Check that the remaining movements are written back to the log
        mock_json_dump.assert_called_with(
            {"destination_file2.txt": "source_file2.txt"},
            mock_open(),
            indent=4
        )

if __name__ == "__main__":
    unittest.main()
