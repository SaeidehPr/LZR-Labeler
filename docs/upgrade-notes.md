# Upgrade notes: 0.2.0

## Implemented

- Moved application imports under `lzr_labeler` and added a module/GUI entry point.
- Added package metadata, optional AI dependencies, tests, and a CI build matrix.
- Replaced direct JSON writes with temporary-file writes and atomic replacement.
- Included the image extension in annotation filenames; retained unambiguous legacy reads.
- Validated shapes and rejected unsupported schema versions and malformed files.
- Guarded annotation loading against autosave and made failed loads read-only.
- Made failed saves block image navigation and closing.
- Introduced general-purpose startup and an optional PCB preset.
- Moved custom label configuration outside the installed package.
- Moved AI execution into a Qt worker thread and rejected results for a different image.
- Avoided importing PyTorch during cleanup when it was never loaded.
- Fixed custom QProxyStyle instances sharing ownership of a widget's base style.
- Kept image-loading worker references valid while replacing a pending request.

## Local verification

21 pytest cases passed on Windows with Python 3.13.1 and PySide6 6.10.1.
The application opened, rendered a synthetic annotation example, and closed
cleanly in Qt offscreen mode. Wheel and source distribution builds succeeded.
The AI worker test verifies thread dispatch without downloading or running a model.

## Design decisions to understand

Atomic replacement preserves the last valid annotation if writing the new version
fails. It does not provide multi-user editing or eliminate every power-loss scenario.

Legacy annotation files contain image stems rather than full filenames. When more
than one image has that stem, refusing to choose prevents accidental misassignment.

Loading is a state transition: the canvas may be temporarily empty or incomplete.
Autosave is suppressed until that transition has completed.

Qt worker signals keep model computation out of the GUI event loop. GUI widgets
are updated only in the main thread. The application refuses to close during an
active AI operation; cancellation is a future improvement.

## Remaining work

- Benchmark supported detector checkpoints and validate their metadata documentation.
- Add cancellation and progress details for long-running inference.
- Expand interaction tests for drawing, editing, zoom, and undo/redo across images.
- Test large-image loading and rapid navigation thoroughly.
- Add an explicitly chosen interchange export format.
- Review third-party assets, institutional branding, source ownership, and licensing.
- Configure standalone application releases after platform testing.

This upgrade does not imply that these remaining items have been completed.
