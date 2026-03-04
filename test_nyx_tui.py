#!/usr/bin/env python3
"""
Tests for nyx_tui.py - Nyx Memory System TUI

Tests cover:
- Menu option handling
- Input validation
- Core functions
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add the memory directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import the module under test
import nyx_tui


class TestMenuOptions:
    """Test menu option handling."""
    
    def test_main_menu_displays_options(self, capsys):
        """Test that main menu displays all options."""
        # Capture the printed output using capsys instead of mock
        with patch('builtins.input', side_effect=['0']):  # Exit immediately
            with patch('nyx_tui.clear_screen'):
                nyx_tui.main_menu()
                
                captured = capsys.readouterr()
                output = captured.out
                # Check that output contains expected menu items
                assert "Search memory" in output
                assert "List recent problems" in output
                assert "Record access" in output
                assert "Show all tags" in output
                assert "Clear cache" in output
                assert "Exit" in output
    
    def test_menu_accepts_numeric_input(self):
        """Test that menu accepts numeric menu choices."""
        # Test exit option (0)
        with patch('builtins.input', side_effect=['0']):
            with patch('nyx_tui.clear_screen'):
                try:
                    nyx_tui.main_menu()
                except SystemExit:
                    pass  # Expected for exit option
        # Test passes if no exception raised


class TestInputHandling:
    """Test input handling and validation."""
    
    def test_search_empty_query(self, capsys):
        """Test search with empty query."""
        with patch('builtins.input', side_effect=['', '0']):
            with patch('nyx_tui.clear_screen'):
                nyx_tui.menu_search()
                captured = capsys.readouterr()
                output = captured.out
                assert "Empty query" in output or "returning" in output.lower()
    
    def test_search_with_query(self):
        """Test search with valid query."""
        with patch('builtins.input', side_effect=['test', '0']):
            with patch('nyx_tui.clear_screen'):
                with patch('nyx_tui.search_memory', return_value=[]):
                    with patch('sys.stdout'):
                        nyx_tui.menu_search()
    
    def test_record_access_empty_slug(self, capsys):
        """Test record access with empty slug."""
        with patch('builtins.input', side_effect=['', '0']):
            with patch('nyx_tui.clear_screen'):
                nyx_tui.menu_record_access()
                captured = capsys.readouterr()
                output = captured.out
                assert "Empty slug" in output or "returning" in output.lower()
    
    def test_record_access_with_slug(self):
        """Test record access with valid slug."""
        with patch('builtins.input', side_effect=['test-problem', '0']):
            with patch('nyx_tui.clear_screen'):
                with patch('nyx_tui.load_activation_log', return_value={"version": "1.0", "last_updated": None, "items": {}}):
                    with patch('nyx_tui.save_activation_log'):
                        with patch('sys.stdout'):
                            nyx_tui.menu_record_access()
    
    def test_clear_cache_confirmation(self):
        """Test cache clear with confirmation."""
        with patch('builtins.input', side_effect=['y', '0']):
            with patch('nyx_tui.clear_screen'):
                with patch('nyx_tui.clear_cache', return_value=True):
                    with patch('sys.stdout'):
                        nyx_tui.menu_clear_cache()
    
    def test_clear_cache_cancellation(self):
        """Test cache clear cancellation."""
        with patch('builtins.input', side_effect=['n', '0']):
            with patch('nyx_tui.clear_screen'):
                with patch('sys.stdout'):
                    nyx_tui.menu_clear_cache()


class TestCoreFunctions:
    """Test core utility functions."""
    
    def test_load_activation_log_empty(self, tmp_path):
        """Test loading empty/non-existent activation log."""
        # Create a temporary directory for testing
        test_dir = tmp_path / "test_memory"
        test_dir.mkdir()
        
        # Override the activation log path
        with patch.object(nyx_tui, 'MEMORY_BASE_DIR', test_dir):
            with patch.object(nyx_tui, 'ACTIVATION_LOG', test_dir / "activation-log.json"):
                result = nyx_tui.load_activation_log()
                assert result["version"] == "1.0"
                assert "items" in result
    
    def test_load_activation_log_existing(self, tmp_path):
        """Test loading existing activation log."""
        test_dir = tmp_path / "test_memory"
        test_dir.mkdir()
        
        activation_data = {
            "version": "1.0",
            "last_updated": "2024-01-01T00:00:00",
            "items": {
                "test-problem": {
                    "slug": "test-problem",
                    "access_count": 5,
                    "access_times": ["2024-01-01T00:00:00"],
                    "created": "2024-01-01T00:00:00"
                }
            }
        }
        
        log_file = test_dir / "activation-log.json"
        log_file.write_text(json.dumps(activation_data))
        
        with patch.object(nyx_tui, 'MEMORY_BASE_DIR', test_dir):
            with patch.object(nyx_tui, 'ACTIVATION_LOG', log_file):
                result = nyx_tui.load_activation_log()
                assert "test-problem" in result["items"]
                assert result["items"]["test-problem"]["access_count"] == 5
    
    def test_calculate_activation(self):
        """Test ACT-R activation calculation."""
        item_data = {
            "created": "2024-01-01T00:00:00+00:00",
            "access_times": ["2024-01-02T00:00:00+00:00"]
        }
        
        current_time = datetime(2024, 1, 3, 0, 0, 0, tzinfo=timezone.utc)
        
        # Should return a value between 0 and 1
        activation = nyx_tui.calculate_activation(item_data, current_time)
        assert 0.0 <= activation <= 1.0
    
    def test_calculate_activation_no_accesses(self):
        """Test activation calculation with no accesses."""
        item_data = {
            "created": "2024-01-01T00:00:00+00:00",
            "access_times": []
        }
        
        current_time = datetime(2024, 1, 3, 0, 0, 0, tzinfo=timezone.utc)
        
        # Should return base level
        activation = nyx_tui.calculate_activation(item_data, current_time)
        assert activation >= 0.0
    
    def test_record_access_new_item(self, tmp_path):
        """Test recording access for new item."""
        test_dir = tmp_path / "test_memory"
        test_dir.mkdir()
        
        log_file = test_dir / "activation-log.json"
        log_file.write_text(json.dumps({"version": "1.0", "last_updated": None, "items": {}}))
        
        with patch.object(nyx_tui, 'MEMORY_BASE_DIR', test_dir):
            with patch.object(nyx_tui, 'ACTIVATION_LOG', log_file):
                activation = nyx_tui.record_access("new-problem")
                assert activation >= 0.0
                
                # Verify it was saved
                result = nyx_tui.load_activation_log()
                assert "new-problem" in result["items"]
                assert result["items"]["new-problem"]["access_count"] == 1
    
    def test_get_tags_from_file(self, tmp_path):
        """Test extracting tags from problem file."""
        test_dir = tmp_path / "test_memory"
        test_dir.mkdir()
        
        # Create a test problem file
        problem_dir = test_dir / "workspace" / "memory" / "problems"
        problem_dir.mkdir(parents=True)
        
        content = """# Problem: Test Problem

**Status:** open
**Priority:** high
**Tags:** python, testing, bug

## Problem Description
Test content here.
"""
        
        problem_file = problem_dir / "test-problem.md"
        problem_file.write_text(content)
        
        with patch.object(nyx_tui, 'MEMORY_DIR', test_dir / "workspace"):
            tags = nyx_tui.get_tags_from_file("test-problem")
            assert "python" in tags or "testing" in tags or "bug" in tags
    
    def test_get_status_from_file(self, tmp_path):
        """Test extracting status from problem file."""
        test_dir = tmp_path / "test_memory"
        test_dir.mkdir()
        
        problem_dir = test_dir / "workspace" / "memory" / "problems"
        problem_dir.mkdir(parents=True)
        
        content = """# Problem: Test Problem

**Status:** resolved
**Priority:** high

## Problem Description
Test content here.
"""
        
        problem_file = problem_dir / "test-problem.md"
        problem_file.write_text(content)
        
        with patch.object(nyx_tui, 'MEMORY_DIR', test_dir / "workspace"):
            status = nyx_tui.get_status_from_file("test-problem")
            assert status == "resolved"


class TestColorFunctions:
    """Test color and formatting functions."""
    
    def test_colorize(self):
        """Test colorize function."""
        result = nyx_tui.colorize("test", nyx_tui.GREEN)
        assert "test" in result
        assert nyx_tui.GREEN in result
        assert nyx_tui.RESET in result
    
    def test_success(self):
        """Test success function."""
        result = nyx_tui.success("Done")
        assert "Done" in result
        assert nyx_tui.GREEN in result
    
    def test_warning(self):
        """Test warning function."""
        result = nyx_tui.warning("Warning")
        assert "Warning" in result
        assert nyx_tui.YELLOW in result
    
    def test_error(self):
        """Test error function."""
        result = nyx_tui.error("Error")
        assert "Error" in result
        assert nyx_tui.RED in result
    
    def test_header(self):
        """Test header function."""
        result = nyx_tui.header("Header")
        assert "Header" in result
        assert nyx_tui.BLUE in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
