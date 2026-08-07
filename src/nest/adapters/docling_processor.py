@@
-from nest.core.models import ProcessingResult
+from nest.core.models import ProcessingResult
+from nest.adapters.accelerator import resolve_accelerator
+from nest.ui.logger import logging
+import logging
@@
     def __init__(self, enable_classification: bool = False) -> None:
@@
-        self._converter = DocumentConverter(
-            allowed_formats=self.SUPPORTED_FORMATS,
-            format_options={
-                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
-            },
-        )
+        # Resolve accelerator and pass to Docling via AcceleratorOptions
+        resolved = resolve_accelerator()
+        logging.getLogger("nest").info("Resolved accelerator: %s", resolved)
+
+        try:
+            from docling.datamodel.accelerator_options import AcceleratorOptions
+
+            accel_opts = AcceleratorOptions(device=resolved)
+            self._converter = DocumentConverter(
+                allowed_formats=self.SUPPORTED_FORMATS,
+                format_options={
+                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
+                },
+                accelerator_options=accel_opts,
+            )
+        except Exception:
+            # Fallback if docling version doesn't accept accelerator_options
+            self._converter = DocumentConverter(
+                allowed_formats=self.SUPPORTED_FORMATS,
+                format_options={
+                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
+                },
+            )
@@
     def convert(self, source: Path) -> ConversionResult:
@@
         return self._converter.convert(source)
*** End Patch
