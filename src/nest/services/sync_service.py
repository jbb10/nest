from pathlib import Path
import logging

from nest.services.discovery_service import DiscoveryService
from nest.services.output_service import OutputMirrorService
from nest.services.manifest_service import ManifestService
from nest.services.index_service import IndexService
from nest.core.models import ProcessingResult

logger = logging.getLogger(__name__)

class SyncService:
    """Orchestrator for the document sync process.

    Coordinates discovery, processing, manifest updates, and index generation.
    """

    def __init__(
        self,
        discovery: DiscoveryService,
        output: OutputMirrorService,
        manifest: ManifestService,
        index: IndexService,
        project_root: Path,
    ) -> None:
        """Initialize SyncService.

        Args:
            discovery: Service for file discovery.
            output: Service for document processing and output mirroring.
            manifest: Service for manifest tracking.
            index: Service for master index generation.
            project_root: Root directory of the project.
        """
        self._discovery = discovery
        self._output = output
        self._manifest = manifest
        self._index = index
        self._project_root = project_root
        
    def sync(self) -> None:
        """Execute the sync process."""
        logger.info("Starting sync process...")
        
        # 1. Discovery
        changes = self._discovery.discover_changes(self._project_root)
        files_to_process = changes.new_files + changes.modified_files
        
        if files_to_process:
            logger.info(f"Processing {len(files_to_process)} files...")
            
        # 2. Processing Loop
        raw_inbox = self._project_root / "raw_inbox"
        output_dir = self._project_root / "processed_context"
        
        for file_info in files_to_process:
            try:
                result = self._output.process_file(file_info.path, raw_inbox, output_dir)
                
                if result.status == "success":
                    if result.output_path is None:
                         # Should not happen for success
                         logger.error(f"Processing succeeded but output_path is None for {file_info.path}")
                         self._manifest.record_failure(file_info.path, file_info.checksum, "Internal error: output_path missing")
                    else:
                        self._manifest.record_success(file_info.path, file_info.checksum, result.output_path)
                else:
                    self._manifest.record_failure(file_info.path, file_info.checksum, result.error or "Unknown error")
                    
            except Exception as e:
                logger.exception(f"Unexpected error processing {file_info.path}")
                self._manifest.record_failure(file_info.path, file_info.checksum, str(e))

        # 3. Commit Manifest
        self._manifest.commit()
        
        # 4. Update Index
        current_manifest = self._manifest.load_current_manifest()
        success_files = []
        for entry in current_manifest.files.values():
            if entry.status == "success":
                success_files.append(entry.output)
        
        # We assume project name is the directory name
        project_name = self._project_root.name
        
        self._index.update_index(success_files, project_name)
        logger.info("Master index updated.")
