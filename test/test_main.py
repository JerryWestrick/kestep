
# tests/test_main.py
import pytest
from kestep.main import main

def test_main(capsys):
    """Test the main function."""
    main()
    captured = capsys.readouterr()
    assert "Knowledge Engineer" in captured.out