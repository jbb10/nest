from pathlib import Path
from unittest.mock import Mock

import pytest
from nest.adapters.protocols import FileSystemProtocol
from nest.services.index_service import IndexService

def test_generate_content_structure():
    fs = Mock(spec=FileSystemProtocol)
    service = IndexService(filesystem=fs, project_root=Path("/app"))
    
    files = [
        "contracts/beta.md",
        "reports/q3.md",
        "contracts/alpha.md"
    ]
    
    content = service.generate_content(files, project_name="Test Project")
    
    assert "# Nest Project Index: Test Project" in content
    assert "Generated:" in content
    assert "Files: 3" in content
    assert "## File Listing" in content
    assert "contracts/alpha.md" in content
    assert "contracts/beta.md" in content
    assert "reports/q3.md" in content
    
    # Check sorting
    # Find the part after ## File Listing
    parts = content.split("## File Listing")
    listing = parts[1].strip().splitlines()
    
    # Filter only file lines (ignoring empty lines)
    file_lines = [l for l in listing if l.strip()]
    assert file_lines[0] == "contracts/alpha.md"
    assert file_lines[1] == "contracts/beta.md"
    assert file_lines[2] == "reports/q3.md"

def test_update_index_writes_to_correct_file():
    fs = Mock(spec=FileSystemProtocol)
    service = IndexService(filesystem=fs, project_root=Path("/app"))
    
    files = ["doc.md"]
    service.update_index(files, project_name="TestNested")
    
    # Expect write_text call
    # Story says: write to processed_context/00_MASTER_INDEX.md
    expected_path = Path("/app") / "processed_context" / "00_MASTER_INDEX.md"
    
    fs.write_text.assert_called_once()
    args, _ = fs.write_text.call_args
    path_arg = args[0]
    content_arg = args[1]
    
    assert path_arg == expected_path
    assert "# Nest Project Index: TestNested" in content_arg
    assert "doc.md" in content_arg

def test_update_index_handles_empty_list():
    fs = Mock(spec=FileSystemProtocol)
    service = IndexService(filesystem=fs, project_root=Path("/app"))
    
    service.update_index([], project_name="Empty Project")
    
    fs.write_text.assert_called_once()
    args, _ = fs.write_text.call_args
    content_arg = args[1]
    
    assert "Files: 0" in content_arg
