from pathlib import Path
from unittest.mock import Mock

from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.adapters.file_discovery import FileDiscoveryAdapter
from nest.adapters.protocols import DocumentProcessorProtocol
from nest.core.models import ProcessingResult
from nest.services.discovery_service import DiscoveryService
from nest.services.index_service import IndexService
from nest.services.manifest_service import ManifestService
from nest.services.output_service import OutputMirrorService
from nest.services.sync_service import SyncService

def test_sync_generates_index_end_to_end(tmp_path: Path):
    # Setup directories (Use tmp_path directly as root to avoid nesting issues or path confusion)
    project_root = tmp_path
    raw = project_root / "raw_inbox"
    raw.mkdir()
    processed_context = project_root / "processed_context"
    # processed_context not created yet
    
    # Create a file
    (raw / "contracts").mkdir()
    (raw / "contracts" / "doc.pdf").write_bytes(b"content")

    # Wire up services
    fs_adapter = FileSystemAdapter()
    manifest_adapter = ManifestAdapter()
    discovery_adapter = FileDiscoveryAdapter()
    
    manifest_service = ManifestService(
        manifest=manifest_adapter, 
        project_root=project_root, 
        raw_inbox=raw, 
        output_dir=processed_context
    )
    
    discovery_service = DiscoveryService(
        file_discovery=discovery_adapter, 
        manifest=manifest_adapter
    ) 

    # Mock processor
    def mock_process(source: Path, output: Path) -> ProcessingResult:
        # Simulate processor logic: create output dir and file
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"Processed {source.name}")
        return ProcessingResult(
            source_path=source,
            status="success",
            output_path=output,
        )

    mock_processor = Mock(spec=DocumentProcessorProtocol)
    mock_processor.process.side_effect = mock_process
    
    output_service = OutputMirrorService(filesystem=fs_adapter, processor=mock_processor)
    
    index_service = IndexService(filesystem=fs_adapter, project_root=project_root)
    
    sync_service = SyncService(
        discovery=discovery_service,
        output=output_service,
        manifest=manifest_service,
        index=index_service,
        project_root=project_root
    )
    
    # Act
    sync_service.sync()
    
    # Assert
    index_file = processed_context / "00_MASTER_INDEX.md"
    assert index_file.exists(), "Index file was not created"
    content = index_file.read_text()
    assert f"# Nest Project Index: {project_root.name}" in content
    # Note: OutputMirrorService typically changes extension to .md.
    # contracts/doc.pdf -> contracts/doc.md
    # Path in index is relative to processed_context
    assert "contracts/doc.md" in content
