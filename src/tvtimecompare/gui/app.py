"""Desktop application for comparing TV Time and Refract exports."""

import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from tvtimecompare.services import ComparisonRun, run_comparison

_TOTAL_STAGES = 4


class ComparisonWorker(QObject):
    """Run an export comparison in a worker thread."""

    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        tvtime_export: Path,
        refract_export: Path,
        output_dir: Path,
    ) -> None:
        super().__init__()
        self._tvtime_export = tvtime_export
        self._refract_export = refract_export
        self._output_dir = output_dir

    @Slot()
    def run(self) -> None:
        """Execute the workflow and emit its result or user-facing error."""
        try:
            comparison_run = run_comparison(
                self._tvtime_export,
                self._refract_export,
                self._output_dir,
                on_progress=self.progress.emit,
            )
        except ValueError as error:
            self.failed.emit(str(error))
        except Exception as error:  # pragma: no cover - unexpected UI safeguard
            self.failed.emit(f"Unexpected error: {error}")
        else:
            self.completed.emit(comparison_run)


class MainWindow(QMainWindow):
    """Window for selecting exports, running comparisons, and opening reports."""

    def __init__(self) -> None:
        super().__init__()
        self._thread: QThread | None = None
        self._worker: ComparisonWorker | None = None
        self._comparison_run: ComparisonRun | None = None

        self.setWindowTitle("TVTimeCompare")
        self.setMinimumSize(720, 520)
        self.resize(840, 620)
        self._build_ui()

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(16)

        heading = QLabel("TV Time migration comparison")
        heading.setObjectName("heading")
        layout.addWidget(heading)
        layout.addWidget(
            QLabel("Choose the two ZIP exports and a destination for the reports.")
        )

        inputs = QGroupBox("Exports")
        input_layout = QGridLayout(inputs)
        self._tvtime_input = self._path_input()
        self._refract_input = self._path_input()
        self._output_input = self._path_input("reports")
        self._add_picker_row(
            input_layout, 0, "TV Time export", self._tvtime_input, self._choose_tvtime
        )
        self._add_picker_row(
            input_layout, 1, "Refract export", self._refract_input, self._choose_refract
        )
        self._add_picker_row(
            input_layout, 2, "Reports folder", self._output_input, self._choose_output
        )
        layout.addWidget(inputs)

        controls = QHBoxLayout()
        self._compare_button = QPushButton("Compare exports")
        self._compare_button.setDefault(True)
        self._compare_button.clicked.connect(self._start_comparison)
        controls.addWidget(self._compare_button)
        controls.addStretch()
        self._open_html_button = QPushButton("Open HTML report")
        self._open_html_button.setEnabled(False)
        self._open_html_button.clicked.connect(self._open_html_report)
        controls.addWidget(self._open_html_button)
        self._open_folder_button = QPushButton("Open reports folder")
        self._open_folder_button.setEnabled(False)
        self._open_folder_button.clicked.connect(self._open_reports_folder)
        controls.addWidget(self._open_folder_button)
        layout.addLayout(controls)

        self._status_label = QLabel("Ready to compare exports.")
        layout.addWidget(self._status_label)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, _TOTAL_STAGES)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        summary_box = QGroupBox("Summary")
        self._summary_layout = QFormLayout(summary_box)
        self._summary_layout.addRow("Status", QLabel("No comparison has run."))
        layout.addWidget(summary_box)
        layout.addStretch()
        self.setStyleSheet(
            "#heading { font-size: 22px; font-weight: 600; }"
            "QGroupBox { font-weight: 600; padding-top: 12px; }"
        )

    @staticmethod
    def _path_input(default: str = "") -> QLineEdit:
        input_field = QLineEdit(default)
        input_field.setReadOnly(True)
        input_field.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        return input_field

    @staticmethod
    def _add_picker_row(
        layout: QGridLayout,
        row: int,
        label: str,
        input_field: QLineEdit,
        handler: Callable[[], None],
    ) -> None:
        layout.addWidget(QLabel(label), row, 0)
        layout.addWidget(input_field, row, 1)
        button = QPushButton("Choose…")
        button.clicked.connect(handler)
        layout.addWidget(button, row, 2)

    @Slot()
    def _choose_tvtime(self) -> None:
        self._choose_zip(self._tvtime_input, "Choose TV Time export")

    @Slot()
    def _choose_refract(self) -> None:
        self._choose_zip(self._refract_input, "Choose Refract export")

    def _choose_zip(self, input_field: QLineEdit, caption: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, caption, filter="ZIP files (*.zip)")
        if path:
            input_field.setText(path)

    @Slot()
    def _choose_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose reports folder")
        if path:
            self._output_input.setText(path)

    @Slot()
    def _start_comparison(self) -> None:
        tvtime_export = Path(self._tvtime_input.text())
        refract_export = Path(self._refract_input.text())
        output_dir = Path(self._output_input.text() or "reports")
        error = self._validate_inputs(tvtime_export, refract_export)
        if error:
            QMessageBox.warning(self, "Cannot compare exports", error)
            return

        self._comparison_run = None
        self._compare_button.setEnabled(False)
        self._open_html_button.setEnabled(False)
        self._open_folder_button.setEnabled(False)
        self._progress_bar.setValue(0)
        self._status_label.setText("Starting comparison…")
        self._thread = QThread(self)
        self._worker = ComparisonWorker(tvtime_export, refract_export, output_dir)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._update_progress)
        self._worker.completed.connect(self._comparison_completed)
        self._worker.failed.connect(self._comparison_failed)
        self._worker.completed.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._comparison_finished)
        self._thread.start()

    @staticmethod
    def _validate_inputs(tvtime_export: Path, refract_export: Path) -> str | None:
        for label, path in (("TV Time", tvtime_export), ("Refract", refract_export)):
            if not path.is_file():
                return f"{label} export was not found: {path}"
            if path.suffix.casefold() != ".zip":
                return f"{label} export must be a .zip file: {path}"
        return None

    @Slot(int, str)
    def _update_progress(self, completed: int, description: str) -> None:
        self._progress_bar.setValue(completed)
        self._status_label.setText(description)

    @Slot(object)
    def _comparison_completed(self, comparison_run: ComparisonRun) -> None:
        self._comparison_run = comparison_run
        self._show_summary(comparison_run)
        self._open_html_button.setEnabled(True)
        self._open_folder_button.setEnabled(True)

    @Slot(str)
    def _comparison_failed(self, message: str) -> None:
        self._status_label.setText("Comparison failed.")
        QMessageBox.critical(self, "Comparison failed", message)

    @Slot()
    def _comparison_finished(self) -> None:
        self._compare_button.setEnabled(True)
        self._thread = None
        self._worker = None

    def _show_summary(self, comparison_run: ComparisonRun) -> None:
        while self._summary_layout.rowCount():
            self._summary_layout.removeRow(0)
        statistics = comparison_run.result.statistics
        rows = (
            ("Matched shows", statistics.matched_show_count),
            ("Missing shows", statistics.missing_show_count),
            ("Ambiguous matches", statistics.ambiguous_show_count),
            ("Missing episodes", statistics.missing_episode_count),
        )
        for label, value in rows:
            self._summary_layout.addRow(label, QLabel(str(value)))
        for diagnostic in comparison_run.diagnostics:
            self._summary_layout.addRow(
                f"{diagnostic.source_file} imported",
                QLabel(
                    f"{diagnostic.rows_imported} of {diagnostic.rows_read} "
                    f"({diagnostic.rows_skipped} skipped)"
                ),
            )
        self._status_label.setText(
            f"Comparison complete. Reports saved to {comparison_run.report_paths.report_html.parent}"
        )

    @Slot()
    def _open_html_report(self) -> None:
        if self._comparison_run is not None:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self._comparison_run.report_paths.report_html))
            )

    @Slot()
    def _open_reports_folder(self) -> None:
        if self._comparison_run is not None:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(
                    str(self._comparison_run.report_paths.report_html.parent)
                )
            )


def run_gui() -> int:
    """Start the TVTimeCompare desktop application and return its exit code."""
    application = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return application.exec()
