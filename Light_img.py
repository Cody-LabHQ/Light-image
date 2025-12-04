import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, 
    QProgressBar, QListWidget, QListWidgetItem, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QColor, QDragEnterEvent, QDropEvent
from PIL import Image, ImageOps

# ---------------------------------------------------------
# CONSTANTS & CONFIGURATION
# ---------------------------------------------------------
GITHUB_LINK = "https://github.com/Cody-LabHQ"
SIGNATURE = "Created by Cody"
APP_TITLE = "Light image"

# Logic Configuration
MAX_DIMENSION = 1920
JPEG_QUALITY = 60
WEBP_QUALITY = 75

# ---------------------------------------------------------
# WORKER THREAD FOR PROCESSING
# ---------------------------------------------------------
class CompressorWorker(QThread):
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths

    def run(self):
        total_files = len(self.file_paths)
        for index, file_path in enumerate(self.file_paths):
            try:
                self.process_image(file_path)
            except Exception as e:
                self.log_signal.emit(f"Error processing {os.path.basename(file_path)}: {str(e)}")
            
            # Update progress
            progress = int(((index + 1) / total_files) * 100)
            self.progress_signal.emit(progress)
        
        self.finished_signal.emit()

    def process_image(self, file_path):
        directory, filename = os.path.split(file_path)
        name, ext = os.path.splitext(filename)
        new_filename = f"{name}_light{ext}"
        save_path = os.path.join(directory, new_filename)
        
        # Open Image
        with Image.open(file_path) as img:
            # Handle rotation based on EXIF data (fixes sideways phone photos)
            img = ImageOps.exif_transpose(img)
            
            original_mode = img.mode
            file_format = img.format if img.format else 'JPEG'

            # 1. RESIZING LOGIC (The key to massive size reduction)
            # If the image is larger than HD (1920px), scale it down.
            width, height = img.size
            if width > MAX_DIMENSION or height > MAX_DIMENSION:
                ratio = min(MAX_DIMENSION / width, MAX_DIMENSION / height)
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                self.log_signal.emit(f"  ↳ Resized from {width}x{height} to {new_size[0]}x{new_size[1]}")

            # 2. SAVING LOGIC
            # Strip metadata by creating a new image without the info buffer
            data_img = Image.new(img.mode, img.size)
            data_img.putdata(list(img.getdata()))
            # Copy transparency for PNG/WEBP
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                 data_img = img.copy() # Fallback for complex transparency
            
            if file_format in ['JPEG', 'JPG']:
                # Convert RGBA to RGB if necessary
                if data_img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', data_img.size, (255, 255, 255))
                    background.paste(data_img, mask=data_img.split()[-1])
                    data_img = background
                
                data_img.save(save_path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
            
            elif file_format == 'PNG':
                # For PNG, we use maximum compression and quantize colors if possible to reduce size
                # However, to maintain strictly "high quality" perception, we stick to optimize=True
                # But resizing done earlier does the heavy lifting here.
                data_img.save(save_path, "PNG", optimize=True, compress_level=9)
            
            elif file_format == 'WEBP':
                data_img.save(save_path, "WEBP", quality=WEBP_QUALITY, method=6)
                
            else:
                # Fallback
                data_img.save(save_path, optimize=True)
                
            original_size = os.path.getsize(file_path) / 1024
            new_size = os.path.getsize(save_path) / 1024
            saved_percent = 100 - (new_size / original_size * 100)
            
            self.log_signal.emit(
                f"✔ {filename}: {original_size:.1f}KB -> {new_size:.1f}KB ({saved_percent:.1f}% saved)"
            )

# ---------------------------------------------------------
# CUSTOM UI WIDGETS
# ---------------------------------------------------------
class DragDropArea(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("DRAG IMAGES HERE")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.setStyleSheet("""
            QLabel {
                border: 3px dashed #444444;
                border-radius: 15px;
                background-color: #222222;
                color: #888888;
            }
            QLabel:hover {
                border-color: #00ADB5;
                color: #EEEEEE;
                background-color: #2A2A2A;
            }
        """)
        self.setAcceptDrops(True)
        self.parent_window = parent

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        image_files = [f for f in files if self.is_image(f)]
        
        if image_files:
            self.parent_window.start_processing(image_files)
        else:
            self.parent_window.log_message("No valid images found.")

    def is_image(self, path):
        try:
            with Image.open(path) as i:
                return True
        except:
            return False

# ---------------------------------------------------------
# MAIN WINDOW
# ---------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_TITLE)
        self.resize(550, 600)
        
        self.apply_dark_theme()

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout
        self.layout = QVBoxLayout(central_widget)
        self.layout.setContentsMargins(25, 25, 25, 25)
        self.layout.setSpacing(20)

        # Title
        self.header_label = QLabel(APP_TITLE)
        self.header_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.header_label.setStyleSheet("color: #00ADB5; letter-spacing: 1px;")
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.header_label)

        # Description
        self.desc_label = QLabel("High-Efficiency Image Size Reducer")
        self.desc_label.setFont(QFont("Segoe UI", 10))
        self.desc_label.setStyleSheet("color: #aaaaaa; margin-bottom: 10px;")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.desc_label)

        # Drag & Drop Area
        self.drop_area = DragDropArea(self)
        self.drop_area.setMinimumHeight(180)
        self.layout.addWidget(self.drop_area)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #333333;
                height: 8px;
                text-align: center;
                color: transparent;
            }
            QProgressBar::chunk {
                background-color: #00ADB5;
                border-radius: 4px;
            }
        """)
        self.progress_bar.setValue(0)
        self.layout.addWidget(self.progress_bar)

        # Log List
        self.log_list = QListWidget()
        self.log_list.setStyleSheet("""
            QListWidget {
                background-color: #1a1a1a;
                border: 1px solid #333333;
                border-radius: 8px;
                color: #cfcfcf;
                font-family: Consolas, monospace;
                font-size: 11px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 2px;
            }
        """)
        self.layout.addWidget(self.log_list)

        # Footer
        footer_frame = QFrame()
        footer_layout = QVBoxLayout(footer_frame)
        footer_layout.setContentsMargins(0, 10, 0, 0)
        
        self.signature_label = QLabel(f"{SIGNATURE} | <a href='{GITHUB_LINK}' style='color: #00ADB5; text-decoration: none;'>{GITHUB_LINK}</a>")
        self.signature_label.setOpenExternalLinks(True)
        self.signature_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.signature_label.setStyleSheet("font-size: 10px; color: #666666;")
        
        footer_layout.addWidget(self.signature_label)
        self.layout.addWidget(footer_frame)

    def apply_dark_theme(self):
        self.setStyleSheet("QMainWindow { background-color: #222222; }")

    def log_message(self, message):
        item = QListWidgetItem(message)
        self.log_list.addItem(item)
        self.log_list.scrollToBottom()

    def start_processing(self, files):
        self.log_list.clear()
        self.log_message(f"Initializing optimization for {len(files)} files...")
        self.drop_area.setText("COMPRESSING...")
        self.drop_area.setStyleSheet("QLabel { border: 3px solid #00ADB5; background-color: #222222; color: #00ADB5; }")
        
        self.worker = CompressorWorker(files)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.log_signal.connect(self.log_message)
        self.worker.finished_signal.connect(self.processing_finished)
        self.worker.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def processing_finished(self):
        self.drop_area.setText("DRAG IMAGES HERE")
        self.drop_area.setStyleSheet("""
            QLabel {
                border: 3px dashed #444444;
                border-radius: 15px;
                background-color: #222222;
                color: #888888;
            }
            QLabel:hover {
                border-color: #00ADB5;
                color: #EEEEEE;
                background-color: #2A2A2A;
            }
        """)
        self.log_message("All operations completed successfully.")
        self.progress_bar.setValue(100)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
