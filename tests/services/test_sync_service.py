from pathlib import Path
from unittest.mock import Mock

import pytest
from nest.services.sync_service import SyncService
from nest.services.discovery_service import DiscoveryService
from nest.services.output_service import OutputMirrorService
from nest.services.manifest_service import ManifestService
from nest.services.index_service import IndexService
from nest.core.models import DiscoveryResult, DiscoveredFile, FileEntry, Manifest, ProcessingResult

@pytest.fixture
def mock_deps():
    return {
        "discovery": Mock(spec=DiscoveryService),
        "output": Mock(spec=OutputMirrorService),
        "manifest": Mock(spec=ManifestService),
        "index": Mock(spec=IndexService),
        "project_root": Path("/app")
    }

def test_sync_calls_index_update_with_success_files(mock_deps):
    service = SyncService(
        discovery=mock_deps["discovery"],
        output=mock_deps["output"],
        manifest=mock_deps["manifest"],
        index=mock_deps["index"],
        project_root=mock_deps["project_root"]
    )
    
    # Setup mocks
    mock_deps["discovery"].discover_changes.return_value = DiscoveryResult(
        new_files=[DiscoveredFile(path=Path("/app/raw/a.pdf"), checksum="123", status="new")],
        modified_files=[],
        unchanged_files=[]
    )
    
    # Mock processing result
    mock_deps["output"].process_file.return_value = ProcessingResult(
        source_path=Path("/app/raw/a.pdf"),
        status="success",
        output_path=Path("/app/processed_context/idx/a.md"),
        error=None
    )
    
    from datetime import datetime

    # ...
    
    final_manifest = Manifest(
        nest_version="1.0",
        project_name="Nest",
        files={
            "key_a": FileEntry(
                sha256="123",
                processed_at=datetime.now(),
                output="idx/a.md",
                status="success",
                error=None
            ),
             "key_b": FileEntry(
                sha256="456",
                processed_at=datetime.now(),
                output="",
                status="failed",
                error="boom"
            )
        }
    )

    mock_deps["manifest"].commit.return_value = None
    mock_deps["manifest"].load_current_manifest.return_value = final_manifest
    
    # Execute
    service.sync()
    
    # Verify
    mock_deps["index"].update_index.assert_called_once()
    files_arg = mock_deps["index"].update_index.call_args[0][0]
    project_name = mock_deps["index"].update_index.call_args[0][1]
    
    assert "idx/a.md" in files_arg
    assert "idx/b.md" not in files_arg
    assert len(files_arg) == 1
    assert project_name == "app" 
