import os
import sys
import re
import subprocess
from io import BytesIO
from datetime import datetime
from pathlib import Path

import fitz
import cv2
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, QRectF, Signal, QSize, QSizeF, QTimer
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QIcon, QPageSize, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QListWidget, QListWidgetItem, QComboBox, QCheckBox,
    QMessageBox, QSplitter, QScrollArea, QFrame, QProgressBar, QGraphicsDropShadowEffect
)

from PySide6.QtPrintSupport import QPrinter, QPrintDialog

STYLE = """
QMainWindow, QWidget { background: #100d18; color: #eae4f5; font-family: 'Segoe UI', 'Arial'; font-size: 13px; }
QLabel { background: transparent; color: #cfc4e0; }
QPushButton { background: #2a213b; color: #f4edff; border: 1px solid #443358; border-radius: 10px; padding: 10px 16px; min-height: 22px; font-weight: 600; }
QPushButton:hover { background: #3b2c54; border-color: #a978ed; }
QPushButton:pressed { background: #4b346a; }
QPushButton:disabled { background: #211b2b; color: #655b70; border-color: #30273c; }
QPushButton#accentButton { background: #8e55df; border: 1px solid #a977f5; color: #ffffff; }
QPushButton#accentButton:hover { background: #a36bf3; }
QPushButton#accentButton:disabled { background: #3b2c52; color: #827495; border-color: #49385d; }
QComboBox { background: #261e35; color: #f0eaff; border: 1px solid #46365c; border-radius: 9px; padding: 10px 14px; min-height: 22px; }
QComboBox:hover { border-color: #9b68e3; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #261e35; color: #f4edff; selection-background-color: #7043ad; border: 1px solid #49335f; }
QListWidget#fileList { background: #1b1627; border: 1px solid #342943; border-radius: 13px; padding: 8px; outline: none; }
QListWidget::item { padding: 13px 10px; border-radius: 8px; }
QListWidget::item:selected { background: #493168; color: white; }
QListWidget::item:hover { background: #332542; }
QCheckBox { color: #cfc3e1; spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QCheckBox::indicator:checked { image: url(checkbox_checked.png); background: #a16bea; border: 1px solid #bd96ff; border-radius: 4px; }
QCheckBox::indicator:unchecked { background: #21192f; border: 1px solid #6b567e; border-radius: 5px; }
QSplitter::handle { background: #100d18; }
QMessageBox { background: #1b1527; }
"""

DPI = 300
LABEL_W_IN = 4
LABEL_H_IN = 6


def pixmap_from_rgb(rgb):
    h, w, ch = rgb.shape
    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


def render_page(page, scale=2.0):
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2RGB)
    elif pix.n == 1:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
    return arr


def detect_label_crop(rgb):
    """
    Best-effort automatic label detection. Finds large rectangular regions using
    edge/contour analysis. Returns (x, y, w, h) in image pixels or None.
    """
    h, w = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    # Try multiple thresholds because PDFs vary in contrast/background.
    candidates = []
    for mode in (0, 1):
        if mode == 0:
            edges = cv2.Canny(gray, 35, 110)
            edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
        else:
            _, bw = cv2.threshold(gray, 225, 255, cv2.THRESH_BINARY_INV)
            edges = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            area = cw * ch
            if area < w * h * 0.08 or cw < w * 0.18 or ch < h * 0.12:
                continue
            ratio = cw / max(ch, 1)
            # Shipping labels are commonly portrait 4x6 or landscape 6x4.
            ratio_score = min(abs(ratio - 2/3), abs(ratio - 1.5))
            area_score = area / (w * h)
            # Prefer large, label-like rectangles, with a little tolerance for margins.
            score = area_score - ratio_score * 0.12
            candidates.append((score, (x, y, cw, ch)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    x, y, cw, ch = candidates[0][1]
    # Slight inset avoids capturing a surrounding box border.
    inset = max(2, int(min(cw, ch) * 0.004))
    x += inset
    y += inset
    cw = max(1, cw - inset * 2)
    ch = max(1, ch - inset * 2)
    return (x, y, cw, ch)


def crop_to_4x6(rgb, rect=None, fit_mode="fill", rotation=0):
    h, w = rgb.shape[:2]
    if rect is not None:
        x, y, cw, ch = rect
        rgb = rgb[max(0,y):min(h,y+ch), max(0,x):min(w,x+cw)]
    if rgb.size == 0:
        raise ValueError("The selected crop is empty.")
    # Turn landscape labels upright, without stretching barcode proportions.
    if rgb.shape[1] > rgb.shape[0]:
        rgb = cv2.rotate(rgb, cv2.ROTATE_90_CLOCKWISE)
    image = Image.fromarray(rgb).convert("RGB")
    tw, th = LABEL_W_IN * DPI, LABEL_H_IN * DPI
    if fit_mode == "stretch":
        # Preserve every pixel of the selected rectangle and use all of the 4x6 page.
        # Non-2:3 selections will change aspect ratio.
        image = image.resize((tw, th), Image.Resampling.LANCZOS)
        return image.rotate(-rotation, expand=False)
    if fit_mode == "contain":
        # Manual selections keep every pixel, even when the selection isn't 2:3.
        image.thumbnail((tw, th), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (tw, th), "white")
        canvas.paste(image, ((tw-image.width)//2, (th-image.height)//2))
        return canvas.rotate(-rotation, expand=False)
    # Automatic labels: fill page with centered crop, without distortion.
    w, h = image.size
    if w / h > tw / th:
        nw = round(h * tw / th)
        left = (w-nw)//2
        image = image.crop((left, 0, left+nw, h))
    else:
        nh = round(w * th / tw)
        top = (h-nh)//2
        image = image.crop((0, top, w, top+nh))
    return image.resize((tw, th), Image.Resampling.LANCZOS).rotate(-rotation, expand=False)


def apply_rounded_mask(widget, radius=14):
    """Clip the actual widget, including its children and pixmap, to rounded corners."""
    if widget.width() < 2 or widget.height() < 2:
        return
    path = QPainterPath()
    path.addRoundedRect(QRectF(widget.rect()), radius, radius)
    widget.setMask(QRegion(path.toFillPolygon().toPolygon()))


class RoundedActionsPanel(QFrame):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        apply_rounded_mask(self, 15)


class PdfPreview(QLabel):
    cropSelected = Signal(tuple)

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(420, 500)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("background:#171222;border:1px solid #372b4c;border-radius:14px;")
        self.original_pixmap = None
        self.image_size = (1, 1)
        self.drag_start = None
        self.drag_end = None
        self.manual_mode = False
        self.setMouseTracking(True)

    def set_image(self, rgb):
        self.image_size = (rgb.shape[1], rgb.shape[0])
        self.original_pixmap = pixmap_from_rgb(rgb)
        self.drag_start = self.drag_end = None
        self._refresh()

    def _display_rect(self):
        if not self.original_pixmap:
            return QRectF()
        pw, ph = self.original_pixmap.width(), self.original_pixmap.height()
        area = self.contentsRect()
        scale = min(area.width() / pw, area.height() / ph)
        dw, dh = pw * scale, ph * scale
        return QRectF(area.x() + (area.width()-dw)/2, area.y() + (area.height()-dh)/2, dw, dh)

    def _refresh(self):
        if not self.original_pixmap:
            return
        rect = self._display_rect()
        scaled = self.original_pixmap.scaled(int(rect.width()), int(rect.height()), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        canvas = QPixmap(self.size())
        canvas.fill(QColor("#171222"))
        painter = QPainter(canvas)
        painter.drawPixmap(int(rect.x()), int(rect.y()), scaled)
        if self.drag_start and self.drag_end:
            selection = QRectF(self.drag_start, self.drag_end).normalized()
            painter.setPen(QPen(QColor("#bb86fc"), 2, Qt.SolidLine))
            painter.setBrush(QColor(169, 108, 255, 60))
            painter.drawRect(selection)
            # Crosshair guide lines
            painter.drawLine(int(selection.center().x()), int(rect.y()), int(selection.center().x()), int(rect.bottom()))
            painter.drawLine(int(rect.x()), int(selection.center().y()), int(rect.right()), int(selection.center().y()))
        painter.end()
        self.setPixmap(canvas)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        apply_rounded_mask(self, 14)
        self._refresh()

    def mousePressEvent(self, event):
        if self.manual_mode and event.button() == Qt.LeftButton and self.original_pixmap:
            self.drag_start = event.position().toPoint()
            self.drag_end = self.drag_start
            self._refresh()

    def mouseMoveEvent(self, event):
        if self.manual_mode and self.drag_start:
            self.drag_end = event.position().toPoint()
            self._refresh()

    def mouseReleaseEvent(self, event):
        if self.manual_mode and self.drag_start and event.button() == Qt.LeftButton:
            self.drag_end = event.position().toPoint()
            disp = self._display_rect()
            a = self.drag_start
            b = self.drag_end
            x1, x2 = sorted((a.x(), b.x()))
            y1, y2 = sorted((a.y(), b.y()))
            left = max(disp.left(), x1)
            top = max(disp.top(), y1)
            right = min(disp.right(), x2)
            bottom = min(disp.bottom(), y2)
            if right-left > 5 and bottom-top > 5:
                iw, ih = self.image_size
                sx, sy = iw/disp.width(), ih/disp.height()
                crop = (int((left-disp.left())*sx), int((top-disp.top())*sy),
                        int((right-left)*sx), int((bottom-top)*sy))
                self.cropSelected.emit(crop)
            self.drag_start = self.drag_end = None
            self._refresh()


class PdfDropList(QListWidget):
    """File list with PDF drag-and-drop and a centered empty-state hint."""
    pdfsDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DropOnly)
        self.setDefaultDropAction(Qt.CopyAction)
        self.hint = QWidget(self.viewport())
        self.hint.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hint.setObjectName("pdfDropHint")
        self.hint.setStyleSheet("""
            QWidget#pdfDropHint {
                background: transparent;
                border: 2px dashed #79529f;
                border-radius: 15px;
            }
            QLabel {background: transparent; border: none;}
        """)
        hint_layout = QVBoxLayout(self.hint)
        hint_layout.setContentsMargins(12, 16, 12, 16)
        hint_layout.setSpacing(8)
        hint_layout.setAlignment(Qt.AlignCenter)
        icon = QLabel()
        icon.setAlignment(Qt.AlignCenter)
        icon_path = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "drop_pdf_icon.png"
        if icon_path.exists():
            icon.setPixmap(QPixmap(str(icon_path)).scaled(
                36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        hint_layout.addWidget(icon)
        heading = QLabel('Drag and drop PDFs here or click "Add PDFs" at the top.')
        heading.setAlignment(Qt.AlignCenter)
        heading.setWordWrap(True)
        heading.setStyleSheet("color:#ead7ff;font-size:13px;font-weight:600;")
        hint_layout.addWidget(heading)
        self.model().rowsInserted.connect(self.refresh_hint)
        self.model().rowsRemoved.connect(self.refresh_hint)
        self.refresh_hint()

    def refresh_hint(self, *args):
        self.hint.setVisible(self.count() == 0)
        self.position_hint()

    def position_hint(self):
        area = self.viewport().rect()
        width = min(max(120, area.width() - 24), 225)
        height = 190
        self.hint.setGeometry((area.width()-width)//2,
                              (area.height()-height)//2, width, height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.position_hint()

    @staticmethod
    def pdf_paths(event):
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        urls = mime.urls()
        if not urls or any(not u.isLocalFile() or
                           Path(u.toLocalFile()).suffix.lower() != ".pdf"
                           for u in urls):
            return []
        return [u.toLocalFile() for u in urls]

    def dragEnterEvent(self, event):
        if self.pdf_paths(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self.pdf_paths(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = self.pdf_paths(event)
        if paths:
            self.pdfsDropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Labelizer4x6")
        self.resize(1250, 810)
        self.setMinimumSize(980, 650)
        self.files = []
        self.current_rgb = None
        self.current_pdf = None
        self.current_page = 0
        self.current_crop = None
        self.preview_mode = "auto"
        self.rotation = 0
        self._build_ui()
        icon_path = Path(__file__).with_name("labelizer.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(24, 22, 24, 20)
        main.setSpacing(16)

        title = QLabel("Labelizer4x6")
        title.setObjectName("brandTitle")
        title.setStyleSheet("font-size:29px;font-weight:750;color:#f5efff;")
        subtitle = QLabel("Extract a shipping label from a PDF, format it to 4 × 6 inches, and open it for printing.")
        subtitle.setStyleSheet("color:#a99cbd;font-size:13px;")
        main.addWidget(title)
        main.addWidget(subtitle)

        top = QHBoxLayout()
        self.add_btn = QPushButton("+  Add PDFs")
        self.add_btn.setObjectName("accentButton")
        self.remove_btn = QPushButton("Remove PDF")
        self.mode = QComboBox()
        self.mode.addItems(["Auto-find label", "Manual crosshair crop"])
        self.mode.currentIndexChanged.connect(self.change_mode)
        self.page_combo = QComboBox()
        self.page_combo.currentIndexChanged.connect(self.change_page)
        self.undo_btn = QPushButton("↶  Undo crop")
        self.undo_btn.setEnabled(False)
        self.save_btn = QPushButton("Save 4×6 Label PDF")
        self.save_btn.setObjectName("accentButton")
        self.save_btn.setEnabled(False)
        self.open_after = QCheckBox("Open PDF after saving")
        self.open_after.setChecked(False)
        self.open_after.setToolTip("Open the saved label in your default PDF application. Off by default.")
        top.addWidget(self.add_btn)
        top.addWidget(self.remove_btn)
        top.addSpacing(12)
        top.addWidget(QLabel("Page:"))
        top.addWidget(self.page_combo)
        top.addWidget(QLabel("Mode:"))
        top.addWidget(self.mode)
        top.addWidget(QLabel("Sizing:"))
        self.sizing = QComboBox()
        self.sizing.addItems(["Stretch selection to 4×6", "Fill page (crop edges)", "Fit entire selection (margins)"])
        self.sizing.setToolTip("Stretch fits all selected content edge-to-edge but may distort proportions. Fit preserves proportions with margins.")
        self.sizing.currentIndexChanged.connect(self.update_final_preview)
        top.addWidget(self.sizing)
        top.addStretch()
        self.rotate_left = QPushButton("↶  90°")
        self.rotate_right = QPushButton("↷  90°")
        self.rotate_left.setToolTip("Rotate the finished label 90° counterclockwise")
        self.rotate_right.setToolTip("Rotate the finished label 90° clockwise")
        self.print_btn = QPushButton("Print 4×6 Label")
        self.print_btn.setEnabled(False)
        main.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.file_list = PdfDropList()
        self.file_list.setMinimumWidth(255)
        self.file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.file_list.setTextElideMode(Qt.ElideRight)
        self.file_list.setObjectName("fileList")
        self.preview = PdfPreview()
        self.preview.setObjectName("pdfPreview")
        self.preview.cropSelected.connect(self.set_manual_crop)
        self.preview.set_manual_mode = lambda value: setattr(self.preview, "manual_mode", value)
        splitter.addWidget(self.file_list)
        splitter.addWidget(self.preview)

        actions = RoundedActionsPanel()
        actions.setObjectName("actionsPanel")
        actions.setMinimumWidth(235)
        actions.setMaximumWidth(310)
        actions.setStyleSheet("""
            QFrame#actionsPanel {background:#21192e;border:1px solid #403052;border-radius:15px;}
            QLabel#sectionTitle {color:#eee1ff;font-size:15px;font-weight:700;border:0;}
            QCheckBox {background:transparent;border:0;}
        """)
        side = QVBoxLayout(actions)
        side.setContentsMargins(16, 19, 16, 19)
        side.setSpacing(13)
        rotate_title = QLabel("Rotate label")
        rotate_title.setObjectName("sectionTitle")
        side.addWidget(rotate_title)
        rotate_buttons = QHBoxLayout()
        rotate_buttons.addWidget(self.rotate_left)
        rotate_buttons.addWidget(self.rotate_right)
        side.addLayout(rotate_buttons)
        note = QLabel("Rotation updates the preview, saved PDF, and print output.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#a99cbd;font-size:12px;border:0;")
        side.addWidget(note)
        side.addSpacing(8)
        crop_title = QLabel("Selection")
        crop_title.setObjectName("sectionTitle")
        side.addWidget(crop_title)
        side.addWidget(self.undo_btn)
        side.addStretch(1)
        output_title = QLabel("Output")
        output_title.setObjectName("sectionTitle")
        side.addWidget(output_title)
        self.print_btn.setObjectName("accentButton")
        side.addWidget(self.print_btn)
        side.addWidget(self.open_after)
        side.addWidget(self.save_btn)
        splitter.addWidget(actions)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setHandleWidth(12)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setCollapsible(2, False)
        self.main_splitter = splitter
        main.addWidget(splitter, 1)
        # Keep the file list at its normal width initially, but allow expansion.
        QTimer.singleShot(0, lambda: splitter.setSizes([
            255, max(420, splitter.width() - 255 - 275 - 24), 275
        ]))

        bottom = QHBoxLayout()
        self.status = QLabel("Add one or more PDF files to begin.")
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximumWidth(180)
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.progress)
        credit = QLabel("Labelizer4x6 by Carson")
        credit.setStyleSheet("color:#9284a7;font-size:12px;background:transparent;")
        credit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bottom.addWidget(credit)
        main.addLayout(bottom)

        self.add_btn.clicked.connect(self.add_pdfs)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.file_list.currentRowChanged.connect(self.load_selected)
        self.file_list.pdfsDropped.connect(self.add_pdf_paths)
        self.save_btn.clicked.connect(self.save_current)
        self.undo_btn.clicked.connect(self.undo_crop)
        self.rotate_left.clicked.connect(lambda: self.rotate_preview(-90))
        self.rotate_right.clicked.connect(lambda: self.rotate_preview(90))
        self.print_btn.clicked.connect(self.print_current)
        self.setStyleSheet(STYLE)

    def add_pdfs(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select PDF files", "", "PDF documents (*.pdf)")
        self.add_pdf_paths(paths)

    def add_pdf_paths(self, paths):
        if not paths:
            return
        existing = {os.path.normcase(os.path.abspath(p)) for p in self.files}
        for p in paths:
            key = os.path.normcase(os.path.abspath(p))
            if Path(p).suffix.lower() == ".pdf" and os.path.isfile(p) and key not in existing:
                self.files.append(p)
                self.add_file_row(p)
                existing.add(key)
        if self.file_list.count() and self.file_list.currentRow() < 0:
            self.file_list.setCurrentRow(0)
        self.file_list.refresh_hint()
        if paths:
            self.status.setText(f"{len(self.files)} PDF(s) in the list.")

    def add_file_row(self, path):
        item = QListWidgetItem()
        item.setSizeHint(QSize(230, 52))
        self.file_list.addItem(item)
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 2, 6, 2)
        layout.setSpacing(4)
        name = QPushButton(Path(path).name)
        name.setToolTip(path)
        name.setStyleSheet("QPushButton {background:transparent; border:0; text-align:left; color:#f0e9fa; padding:4px; min-height:0;} QPushButton:hover {color:#d3a7ff;}")
        name.clicked.connect(lambda checked=False, entry=item: self.file_list.setCurrentItem(entry))
        layout.addWidget(name, 1)
        close = QPushButton("×")
        close.setFixedSize(29, 29)
        close.setToolTip("Remove this PDF from the list")
        close.setStyleSheet(
            "QPushButton {background:transparent;border:0;color:#c9a6f7;"
            "font-size:20px;padding:0;border-radius:7px;min-height:0;}"
            "QPushButton:hover {background:#5a336e;color:white;}"
        )
        close.clicked.connect(lambda checked=False, entry=item: self.remove_file_item(entry))
        layout.addWidget(close)
        self.file_list.setItemWidget(item, row)
        self.file_list.refresh_hint()

    def remove_file_item(self, item):
        row = self.file_list.row(item)
        if row < 0:
            return
        was_current = row == self.file_list.currentRow()
        self.files.pop(row)
        self.file_list.takeItem(row)
        self.file_list.refresh_hint()
        if not self.files:
            self.current_pdf = None
            self.current_rgb = None
            self.current_crop = None
            self.preview.clear()
            self.save_btn.setEnabled(False)
            self.print_btn.setEnabled(False)
            self.page_combo.clear()
            self.status.setText("Add one or more PDF files to begin.")
        elif was_current:
            next_row = min(row, len(self.files)-1)
            self.file_list.setCurrentRow(next_row)
            self.load_selected(next_row)

    def remove_selected(self):
        row = self.file_list.currentRow()
        if row >= 0:
            self.remove_file_item(self.file_list.item(row))

    def load_selected(self, row):
        if row < 0 or row >= len(self.files):
            return
        self.current_pdf = self.files[row]
        try:
            with fitz.open(self.current_pdf) as doc:
                self.page_combo.blockSignals(True)
                self.page_combo.clear()
                for i in range(len(doc)):
                    self.page_combo.addItem(f"Page {i+1}", i)
                self.page_combo.blockSignals(False)
                self.current_page = 0
                self._render_current_page()
        except Exception as e:
            QMessageBox.critical(self, "Could not open PDF", str(e))

    def change_page(self, idx):
        if idx < 0 or not self.current_pdf:
            return
        self.current_page = self.page_combo.itemData(idx)
        self._render_current_page()

    def _render_current_page(self):
        try:
            with fitz.open(self.current_pdf) as doc:
                self.current_rgb = render_page(doc[self.current_page], 2.2)
            self.current_crop = None
            self.rotation = 0
            self.preview.manual_mode = (self.preview_mode == "manual")
            self.preview.set_image(self.current_rgb)
            self.undo_btn.setEnabled(False)
            if self.preview_mode == "auto":
                rect = detect_label_crop(self.current_rgb)
                self.current_crop = rect
                if rect:
                    self.status.setText("Label detected. Preview shows your print-ready 4 × 6 output.")
                    self.update_final_preview()
                else:
                    self.status.setText("No label detected. Use Manual crosshair crop to select one.")
            else:
                self.status.setText("Drag a purple rectangle around the content to crop.")
            self.save_btn.setEnabled(True)
            self.print_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Could not render PDF page", str(e))

    def change_mode(self, idx):
        self.rotation = 0
        self.preview_mode = "auto" if idx == 0 else "manual"
        self.sizing.blockSignals(True)
        self.sizing.setCurrentIndex(1 if idx == 0 else 0)
        self.sizing.blockSignals(False)
        self.preview.manual_mode = (self.preview_mode == "manual")
        if self.current_rgb is not None:
            self._render_current_page()

    def set_manual_crop(self, crop):
        self.current_crop = crop
        # Show the exact final PDF page rather than the full original document.
        self.undo_btn.setEnabled(True)
        self.update_final_preview()
        self.status.setText("Print-ready 4 × 6 preview. Change sizing, undo, or save.")

    def update_final_preview(self):
        if self.current_rgb is None or self.current_crop is None:
            return
        fit_mode = ("stretch", "fill", "contain")[self.sizing.currentIndex()]
        final_image = crop_to_4x6(self.current_rgb, self.current_crop, fit_mode=fit_mode, rotation=self.rotation)
        self.preview.manual_mode = False
        self.preview.set_image(np.asarray(final_image).copy())

    def rotate_preview(self, degrees):
        if self.current_crop is None:
            self.status.setText("Select a label first, then rotate the preview.")
            return
        self.rotation = (self.rotation + degrees) % 360
        self.update_final_preview()
        self.status.setText(f"Rotation: {self.rotation}°. Preview and export match.")

    def current_label(self):
        if self.current_rgb is None or self.current_crop is None:
            raise ValueError("Select a label before printing or saving.")
        return crop_to_4x6(
            self.current_rgb, self.current_crop,
            fit_mode=("stretch", "fill", "contain")[self.sizing.currentIndex()],
            rotation=self.rotation
        )

    def print_current(self):
        try:
            label = self.current_label()
            printer = QPrinter(QPrinter.HighResolution)
            printer.setPageSize(QPageSize(QSizeF(4.0, 6.0), QPageSize.Inch))
            printer.setFullPage(True)
            printer.setColorMode(QPrinter.GrayScale)
            dialog = QPrintDialog(printer, self)
            dialog.setWindowTitle("Print 4 × 6 label")
            if dialog.exec() != QPrintDialog.Accepted:
                return
            # Respect printer choice, but enforce the actual 4x6 label stock.
            printer.setPageSize(QPageSize(QSizeF(4.0, 6.0), QPageSize.Inch))
            printer.setFullPage(True)
            painter = QPainter()
            if not painter.begin(printer):
                raise RuntimeError("Could not start the printer.")
            try:
                buffer = BytesIO()
                label.save(buffer, format="PNG")
                qimg = QImage.fromData(buffer.getvalue(), "PNG")
                painter.drawImage(printer.pageRect(QPrinter.DevicePixel), qimg)
            finally:
                painter.end()
            self.status.setText("Print job sent to the selected printer.")
        except Exception as exc:
            QMessageBox.critical(self, "Printing failed", str(exc))

    def undo_crop(self):
        if self.current_rgb is None:
            return
        self.current_crop = None
        self.preview.manual_mode = (self.preview_mode == "manual")
        self.preview.set_image(self.current_rgb)
        self.undo_btn.setEnabled(False)
        self.status.setText("Crop undone. Drag around the label to select again.")

    def save_current(self):
        if not self.current_pdf or self.current_rgb is None:
            return
        if self.preview_mode == "manual" and not self.current_crop:
            QMessageBox.information(self, "Select the label", "Switch to manual crop and drag a rectangle around the label first.")
            return
        if self.preview_mode == "auto" and not self.current_crop:
            choice = QMessageBox.question(
                self, "No label detected",
                "Automatic detection did not find a confident label boundary. Switch to manual crop?",
                QMessageBox.Yes | QMessageBox.No
            )
            if choice == QMessageBox.Yes:
                self.mode.setCurrentIndex(1)
            return
        self._save_pdf(self.current_pdf, self.current_page, self.current_rgb, self.current_crop)

    def _save_pdf(self, source_path, page_no, rgb, crop):
        try:
            label = self.current_label()
            out_dir = str(Path(source_path).parent)
            stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            stem = re.sub(r'[<>:"/\\\\|?*]', "_", Path(source_path).stem)
            out_path = os.path.join(out_dir, f"{stem}_{stamp}_4x6.pdf")
            # Create a true 4x6 inch PDF page, with the rendered label image at 300 DPI.
            doc = fitz.open()
            page = doc.new_page(width=LABEL_W_IN*72, height=LABEL_H_IN*72)
            image_buffer = BytesIO()
            label.save(image_buffer, format="PNG")
            page.insert_image(page.rect, stream=image_buffer.getvalue())
            # Avoid silently overwriting if multiple exports occur within one second.
            counter = 2
            while os.path.exists(out_path):
                out_path = os.path.join(out_dir, f"{stem}_{stamp}_4x6_{counter}.pdf")
                counter += 1
            doc.save(out_path)
            doc.close()
            self.status.setText(f"Saved: {out_path}")
            if self.open_after.isChecked():
                try:
                    if sys.platform.startswith("win"):
                        os.startfile(out_path)
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", out_path])
                    else:
                        subprocess.Popen(["xdg-open", out_path])
                except Exception as e:
                    QMessageBox.warning(self, "Saved, but could not open", f"The PDF was saved here:\n{out_path}\n\nCould not open the default PDF viewer:\n{e}")
            else:
                QMessageBox.information(self, "Label saved", f"Saved 4×6 PDF:\n{out_path}")
        except Exception as e:
            QMessageBox.critical(self, "Could not save label", str(e))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()