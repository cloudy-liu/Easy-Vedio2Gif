import io
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QIcon, QDragEnterEvent, QDropEvent, QPixmap
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QProgressBar, QMessageBox, QGroupBox,
                             QFormLayout, QDoubleSpinBox,
                             QComboBox, QTextEdit, QFrame,
                             QCheckBox, QDialog, QDialogButtonBox)

# Get operating system type
SYSTEM = platform.system()

# Configure ffmpeg paths for different platforms
BASE_DIR = Path(__file__).parent.absolute()
if SYSTEM == 'Windows':
    FFMPEG_PATH = str(BASE_DIR / 'lib' / 'windows' / 'ffmpeg.exe')
    FFPROBE_PATH = str(BASE_DIR / 'lib' / 'windows' / 'ffprobe.exe')
    # No window flag for Windows
    SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW
elif SYSTEM == 'Darwin':  # macOS
    FFMPEG_PATH = str(BASE_DIR / 'lib' / 'mac' / 'ffmpeg')
    FFPROBE_PATH = str(BASE_DIR / 'lib' / 'mac' / 'ffprobe')
    SUBPROCESS_FLAGS = 0
else:  # Linux or other systems
    FFMPEG_PATH = 'ffmpeg'
    FFPROBE_PATH = 'ffprobe'
    SUBPROCESS_FLAGS = 0

# Ensure executable permissions (on Unix systems)
if SYSTEM != 'Windows':
    ffmpeg_path = Path(FFMPEG_PATH)
    ffprobe_path = Path(FFPROBE_PATH)
    if ffmpeg_path.exists():
        os.chmod(FFMPEG_PATH, 0o755)
    if ffprobe_path.exists():
        os.chmod(FFPROBE_PATH, 0o755)

ICONS_DIR = BASE_DIR / 'res' / 'icons'


class Icons:
    @staticmethod
    def get_icon(name):
        """Get icon path"""
        icon_path = ICONS_DIR / f"{name}.ico"
        if icon_path.exists():
            return QIcon(str(icon_path))
        return None


class LogStream(io.StringIO):
    def __init__(self, log_signal):
        super().__init__()
        self.log_signal = log_signal

    def write(self, text):
        super().write(text)
        self.log_signal.emit(text)

    def flush(self):
        pass


def run_command(cmd, **kwargs):
    """Runs a command with subprocess.run and handles platform-specific flags.

    Args:
        cmd: List of command arguments to execute.
        **kwargs: Additional keyword arguments passed to subprocess.run.

    Returns:
        A subprocess.CompletedProcess object.
    """
    if SYSTEM == 'Windows':
        return subprocess.run(cmd, creationflags=SUBPROCESS_FLAGS, **kwargs)
    return subprocess.run(cmd, **kwargs)


def start_command_process(cmd, **kwargs):
    """Creates a subprocess.Popen object with platform-specific flags.

    Args:
        cmd: List of command arguments to execute.
        **kwargs: Additional keyword arguments passed to subprocess.Popen.

    Returns:
        A subprocess.Popen object.
    """
    if SYSTEM == 'Windows':
        return subprocess.Popen(cmd, creationflags=SUBPROCESS_FLAGS, **kwargs)
    return subprocess.Popen(cmd, **kwargs)


class ConversionThread(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    # Add warning signal, passing warning message and warning type
    warning_signal = pyqtSignal(str, int)

    def __init__(
            self,
            input_file,
            output_file,
            start_time,
            duration,
            fps,
            quality,
            width,
            dither_method='bayer',
            colors=256,
            ignore_limits=False
    ):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.start_time = start_time
        self.duration = duration
        self.fps = fps
        self.quality = quality
        self.width = width
        self.dither_method = dither_method
        self.colors = colors
        self.ignore_limits = ignore_limits  # Flag to ignore limits

    def log(self, message):
        """Helper method to emit log messages"""
        self.log_signal.emit(message)

    def get_video_duration(self):
        """Get video duration using ffprobe if duration is not specified"""
        if self.duration <= 0:
            cmd = [
                FFPROBE_PATH,
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                self.input_file
            ]
            result = run_command(cmd, capture_output=True, text=True)
            total_duration = float(result.stdout.strip())
            self.duration = total_duration - self.start_time

        return self.duration

    def validate_frame_count(self):
        """Validate total frames against WeChat limit"""
        total_frames = int(self.fps * self.duration)

        # Check frame limit, but don't stop directly
        if total_frames > 300 and not self.ignore_limits:
            self.warning_signal.emit(
                f"当前设置将生成 {total_frames} 帧，超过微信公众号的300帧限制。", 1)
            return False

        return True

    def log_conversion_parameters(self):
        """Log all conversion parameters"""
        self.log(f"开始生成调色板...\n")
        self.log(f"视频: {self.input_file}\n")
        self.log(f"开始时间: {self.start_time}秒, 持续时间: {self.duration}秒\n")
        self.log(f"帧率: {self.fps}fps, 宽度: {self.width}px, 质量级别: {self.quality}\n")
        self.log(f"抖动方法: {self.dither_method}, 调色板颜色数: {self.colors}\n")

    def generate_palette(self, palette_file):
        """Generate a palette for better GIF quality"""
        # Build palette generation command
        palette_cmd = [
            FFMPEG_PATH, '-y',
            '-ss', str(self.start_time),
            '-t', str(self.duration),
            '-i', self.input_file,
            '-vf',
            f'fps={self.fps},scale={self.width}:-1:flags=lanczos,palettegen=max_colors={self.colors}:stats_mode=full',
            palette_file
        ]

        self.log(f"调色板命令: {' '.join(palette_cmd)}\n")
        self.progress_signal.emit(25)

        # Execute palette generation
        process = start_command_process(
            palette_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )

        # Read and log output
        for line in process.stderr:
            self.log(line)

        process.wait()
        if process.returncode != 0:
            raise Exception("调色板生成失败")

        self.log(f"调色板生成成功，开始转换GIF...\n")
        return True

    def convert_to_gif(self, palette_file):
        """Convert video to GIF using the generated palette"""
        # Build GIF conversion command
        gif_cmd = [
            FFMPEG_PATH, '-y',
            '-ss', str(self.start_time),
            '-t', str(self.duration),
            '-i', self.input_file,
            '-i', palette_file,
            '-lavfi',
            f'fps={self.fps},scale={self.width}:-1:flags=lanczos [x]; [x][1:v] paletteuse=dither={self.dither_method}:bayer_scale={6 - self.quality}',
            self.output_file
        ]

        self.log(f"GIF转换命令: {' '.join(gif_cmd)}\n")
        self.progress_signal.emit(50)

        # Execute GIF conversion
        process = start_command_process(
            gif_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )

        # Read and log output
        for line in process.stderr:
            self.log(line)

        process.wait()
        if process.returncode != 0:
            raise Exception("GIF转换失败")

        return True

    def check_output_size(self):
        """Check output file size and emit warning if needed"""
        # Calculate total frames
        total_frames = int(self.fps * self.duration)

        # Check file size
        output_path = Path(self.output_file)
        file_size = output_path.stat().st_size / (1024 * 1024)  # Size in MB

        self.log(
            f"转换完成！文件: {self.output_file}, GIF大小: {file_size:.2f}MB, "
            f"总帧数: {total_frames}\n"
        )
        self.progress_signal.emit(100)

        # Warn about file size exceeding limit, but don't stop
        if file_size > 10 and not self.ignore_limits:
            self.warning_signal.emit(
                f"生成的GIF大小为 {file_size:.2f}MB，超过微信公众号的10MB限制。", 2)
        else:
            self.finished_signal.emit(
                f"转换成功！GIF大小: {file_size:.2f}MB, 总帧数: {total_frames}")

        return file_size, total_frames

    def run(self):
        """Main execution method of the thread"""
        try:
            # Create temp directory for palette
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                palette_file = str(temp_dir_path / "palette.png")

                # Get and validate video duration
                self.get_video_duration()

                # Validate frame count
                if not self.validate_frame_count():
                    return  # Pause execution, wait for user response

                # Log all parameters
                self.log_conversion_parameters()

                # Generate palette
                self.generate_palette(palette_file)

                # Convert video to GIF
                self.convert_to_gif(palette_file)

                # Check output size and emit completion signal
                self.check_output_size()

        except Exception as e:
            self.log(f"错误: {str(e)}\n")
            self.error_signal.emit(f"转换失败: {str(e)}")


class DropArea(QWidget):
    file_dropped = pyqtSignal(str)
    file_select_clicked = pyqtSignal()  # New click signal

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        layout = QVBoxLayout()

        # Create label with icon
        self.label = QLabel("拖放视频文件到这里\n或点击选择文件")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            "background-color: #f5f5f7; border-radius: 8px; padding: 15px;")
        self.label.setMinimumHeight(120)
        self.label.setMaximumHeight(120)

        # Add upload icon to drop area
        upload_icon = Icons.get_icon("upload")
        if upload_icon:
            self.label.setPixmap(upload_icon.pixmap(48, 48))
            self.label.setAlignment(Qt.AlignCenter)
            # Add extra line breaks for icon space
            self.label.setText("\n\n拖放视频文件到这里\n或点击选择文件")

        layout.addWidget(self.label)
        self.setLayout(layout)

        # Set mouse cursor style to indicate clickable
        self.setCursor(Qt.PointingHandCursor)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.label.setStyleSheet(
                "background-color: #e0e0e0; border-radius: 8px; padding: 15px; border: 2px dashed #0071e3;")
            # Ensure icon doesn't disappear during drag operation
            upload_icon = Icons.get_icon("upload")
            if upload_icon:
                self.label.setPixmap(upload_icon.pixmap(48, 48))
                self.label.setText("\n\n拖放至此完成上传")

    def dragLeaveEvent(self, event):
        self.label.setStyleSheet(
            "background-color: #f5f5f7; border-radius: 8px; padding: 15px;")
        # Restore original icon and text
        upload_icon = Icons.get_icon("upload")
        if upload_icon:
            self.label.setPixmap(upload_icon.pixmap(48, 48))
            self.label.setText("\n\n拖放视频文件到这里\n或点击选择文件")

    def dropEvent(self, event: QDropEvent):
        self.label.setStyleSheet(
            "background-color: #f5f5f7; border-radius: 8px; padding: 15px;")
        # Restore original icon and text
        upload_icon = Icons.get_icon("upload")
        if upload_icon:
            self.label.setPixmap(upload_icon.pixmap(48, 48))
            self.label.setText("\n\n拖放视频文件到这里\n或点击选择文件")

        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(('.mp4', '.avi', '.mov', '.wmv', '.mkv', '.flv')):
                self.file_dropped.emit(file_path)
                return

        QMessageBox.warning(self, "不支持的文件", "请选择有效的视频文件。")

    def mousePressEvent(self, event):
        # Emit signal on click
        self.file_select_clicked.emit()


# Settings dialog class
class SettingsDialog(QDialog):
    def __init__(self, parent=None, output_dir="", ask_save_location=False):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)
        self.output_dir = output_dir
        self.ask_save_location = ask_save_location

        # Dialog layout
        layout = QVBoxLayout()

        # Output directory settings
        output_dir_group = QGroupBox("输出设置")
        output_dir_layout = QVBoxLayout()

        # Output directory selection
        dir_layout = QHBoxLayout()
        self.output_dir_label = QLabel(f"输出目录: {self.output_dir}")
        self.change_dir_btn = QPushButton("浏览...")
        self.change_dir_btn.clicked.connect(self.change_output_dir)
        dir_layout.addWidget(self.output_dir_label, 1)
        dir_layout.addWidget(self.change_dir_btn, 0)

        # Ask save location checkbox
        self.ask_location_checkbox = QCheckBox("每次询问保存位置")
        self.ask_location_checkbox.setChecked(self.ask_save_location)

        output_dir_layout.addLayout(dir_layout)
        output_dir_layout.addWidget(self.ask_location_checkbox)
        output_dir_group.setLayout(output_dir_layout)

        # Add to main layout
        layout.addWidget(output_dir_group)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # Style the OK button
        ok_button = button_box.button(QDialogButtonBox.Ok)
        ok_button.setStyleSheet("""
            background-color: #0071e3;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
        """)

        layout.addWidget(button_box)
        self.setLayout(layout)

    def change_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择输出目录", self.output_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if dir_path:
            self.output_dir = dir_path
            self.output_dir_label.setText(f"输出目录: {self.output_dir}")

    def get_settings(self):
        return {
            "output_dir": self.output_dir,
            "ask_save_location": self.ask_location_checkbox.isChecked()
        }


class Video2GifApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.input_file = ""
        self.video_duration = 0
        self.video_width = 0
        self.video_height = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_output_estimate)
        self.timer.setInterval(100)  # Update every 100ms when settings change

        # Set default values
        self.default_output_dir = str(
            Path.home() / "Downloads")  # Set default output directory to the user's Downloads folder
        self.ask_save_location = False

        # Load configuration file
        self.config_file = Path(BASE_DIR) / "config.json"
        self.log_text = None  # Initialize as None

        self.initUI()

        # Load configuration after initializing the UI
        self.load_config()

    def initUI(self):
        self.setWindowTitle("微信公众号：视频转 Gif")
        self.setMinimumSize(1000, 800)  # Adjust window size

        # Set application icon
        app_icon = Icons.get_icon("app")
        if app_icon:
            self.setWindowIcon(app_icon)

        # Main layout container
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # ===== Top area: File selection =====
        file_selection_group = QGroupBox("文件选择")
        file_selection_layout = QVBoxLayout()

        # Drop area (clickable for file selection)
        self.drop_area = DropArea()
        self.drop_area.file_dropped.connect(self.set_input_file)
        self.drop_area.file_select_clicked.connect(
            self.open_file_dialog)  # Connect click signal
        file_selection_layout.addWidget(self.drop_area)

        # File info label
        self.file_info_label = QLabel("请选择一个视频文件")
        self.file_info_label.setAlignment(Qt.AlignCenter)
        file_selection_layout.addWidget(self.file_info_label)

        file_selection_group.setLayout(file_selection_layout)

        middle_widget = QWidget()
        middle_layout = QHBoxLayout()

        settings_group = QGroupBox("设置区")
        settings_form_layout = QFormLayout()
        settings_form_layout.setSpacing(10)

        # Basic settings
        # Start time
        self.start_time_spin = QDoubleSpinBox()
        self.start_time_spin.setRange(0, 1000)
        self.start_time_spin.setSuffix(" 秒")
        self.start_time_spin.setDecimals(1)
        self.start_time_spin.setSingleStep(1.0)
        self.start_time_spin.valueChanged.connect(
            self.start_estimate_update_timer)
        settings_form_layout.addRow("开始时间:", self.start_time_spin)

        # Duration
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.1, 60)
        self.duration_spin.setValue(5)
        self.duration_spin.setSuffix(" 秒")
        self.duration_spin.setDecimals(1)
        self.duration_spin.setSingleStep(1.0)
        self.duration_spin.valueChanged.connect(
            self.start_estimate_update_timer)
        settings_form_layout.addRow("持续时间:", self.duration_spin)

        # FPS
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(
            ["10 (节省空间)", "15 (推荐)", "20 (较流畅)", "25 (非常流畅)"])
        self.fps_combo.setCurrentIndex(3)  # Default to 25fps
        self.fps_combo.currentIndexChanged.connect(
            self.start_estimate_update_timer)
        settings_form_layout.addRow("帧率:", self.fps_combo)

        # Quality
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(
            ["低 (节省空间)", "中 (平衡)", "高 (高清)", "超高 (极致高清)"])
        self.quality_combo.setCurrentIndex(2)  # Default to high quality
        self.quality_combo.currentIndexChanged.connect(
            self.start_estimate_update_timer)
        settings_form_layout.addRow("质量:", self.quality_combo)

        # Width
        self.width_combo = QComboBox()
        self.width_combo.addItems(
            ["320 (小尺寸)", "480 (中等)", "640 (较大)", "800 (大尺寸)", "1024 (高清)",
             "1280 (超清)", "1920 (全高清)"])
        self.width_combo.setCurrentIndex(3)  # Default to 800px width
        self.width_combo.currentIndexChanged.connect(
            self.start_estimate_update_timer)
        settings_form_layout.addRow("宽度:", self.width_combo)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        settings_form_layout.addRow(separator)

        # Advanced settings label
        adv_label = QLabel("高级设置")
        settings_form_layout.addRow(adv_label)

        # Dither method
        self.dither_combo = QComboBox()
        self.dither_combo.addItems(
            ["默认 (bayer)", "抖动较少 (floyd_steinberg)", "高质量 (sierra2_4a)"])
        self.dither_combo.setCurrentIndex(0)
        self.dither_combo.currentIndexChanged.connect(
            self.start_estimate_update_timer)
        settings_form_layout.addRow("抖动算法:", self.dither_combo)

        # Color count
        self.colors_combo = QComboBox()
        self.colors_combo.addItems(["128色 (节省空间)", "192色 (中等)", "256色 (最高质量)"])
        self.colors_combo.setCurrentIndex(2)  # Default to 256 colors
        self.colors_combo.currentIndexChanged.connect(
            self.start_estimate_update_timer)
        settings_form_layout.addRow("调色板色彩:", self.colors_combo)

        settings_group.setLayout(settings_form_layout)

        # ------ Right side: Output estimate ------
        estimate_group = QGroupBox("输出预估")

        estimate_layout = QVBoxLayout()

        # Estimate label
        self.estimate_label = QLabel("请先选择视频文件进行预估")
        self.estimate_label.setStyleSheet("""
            background-color: #f5f5f7;
            border-radius: 6px;
            padding: 10px;
        """)
        self.estimate_label.setAlignment(Qt.AlignCenter)
        self.estimate_label.setWordWrap(True)
        estimate_layout.addWidget(self.estimate_label)

        # WeChat tip label
        self.wechat_tip_label = QLabel("")
        self.wechat_tip_label.setStyleSheet("""
            color: #777;
            font-style: italic;
        """)
        self.wechat_tip_label.setAlignment(Qt.AlignCenter)
        estimate_layout.addWidget(self.wechat_tip_label)

        # Add buttons row
        buttons_layout = QHBoxLayout()

        # Settings button
        self.settings_btn = QPushButton("设置")
        self.settings_btn.setMinimumHeight(40)
        self.settings_btn.setMinimumWidth(80)
        self.settings_btn.clicked.connect(self.open_settings_dialog)

        # Convert button
        self.convert_btn = QPushButton("start")
        self.convert_btn.setMinimumHeight(40)
        self.convert_btn.setMinimumWidth(120)
        self.convert_btn.setEnabled(False)

        # Add start icon
        start_icon = Icons.get_icon("start")
        if start_icon:
            self.convert_btn.setIcon(start_icon)
            self.convert_btn.setText("开始转换")
            self.convert_btn.setIconSize(QSize(20, 20))

        self.convert_btn.clicked.connect(self.convert_to_gif)

        # Add buttons to layout
        buttons_layout.addWidget(self.settings_btn, alignment=Qt.AlignLeft)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.convert_btn, alignment=Qt.AlignRight)

        # Set up progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(12)
        self.progress_bar.setMaximumHeight(12)
        self.progress_bar.setTextVisible(False)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)

        # Add these widgets to vertical layout
        convert_layout = QVBoxLayout()
        convert_layout.addWidget(self.progress_bar)
        convert_layout.addWidget(self.status_label)
        convert_layout.addLayout(buttons_layout)
        estimate_layout.addLayout(convert_layout)

        estimate_group.setLayout(estimate_layout)

        # Add settings and estimate areas to middle layout
        middle_layout.addWidget(settings_group, 3)  # Ratio 3
        middle_layout.addWidget(estimate_group, 2)  # Ratio 2
        middle_widget.setLayout(middle_layout)

        # ===== Bottom area: Log =====
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout()

        # Log title
        log_label = QLabel("转换日志")
        bottom_layout.addWidget(log_label)

        # Log text box
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        bottom_layout.addWidget(self.log_text)

        # Log clear button
        self.clear_log_btn = QPushButton("清除日志")
        self.clear_log_btn.setMinimumHeight(40)
        self.clear_log_btn.setMinimumWidth(100)

        self.clear_log_btn.clicked.connect(self.clear_log)
        bottom_layout.addWidget(self.clear_log_btn, alignment=Qt.AlignRight)

        bottom_widget.setLayout(bottom_layout)

        # Add all areas to main layout
        # File selection area ratio 1
        main_layout.addWidget(file_selection_group, 1)
        # Middle settings area ratio 3
        main_layout.addWidget(middle_widget, 3)
        # Bottom log area ratio 3
        main_layout.addWidget(bottom_widget, 3)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # Apply styles
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #ffffff;
                color: #333333;
            }
            QPushButton {
                background-color: #0071e3;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #0077ED;
            }
            QPushButton:pressed {
                background-color: #005BBB;
            }
            QPushButton:disabled {
                background-color: #E1E1E6;
                color: #999999;
            }
            QGroupBox {
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                margin-top: 1.5ex;
                padding-top: 15px;
                padding-bottom: 8px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
                color: #333333;
            }
            QProgressBar {
                border: none;
                background-color: #f5f5f7;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background-color: #34C759;
                border-radius: 6px;
            }
            QComboBox, QDoubleSpinBox {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 5px;
                background-color: #ffffff;
                selection-background-color: #0071e3;
            }
            QComboBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #0071e3;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QLabel {
                color: #333333;
            }
            QSplitter::handle {
                background-color: #e0e0e0;
            }
            QScrollBar:vertical {
                border: none;
                background: #f5f5f7;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #c1c1c1;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def start_estimate_update_timer(self):
        """Start the estimate update timer"""
        self.timer.start()

    def update_output_estimate(self):
        """Update the estimated output file size and frame count"""
        self.timer.stop()

        if not self.input_file:
            self.estimate_label.setText("请先选择视频文件进行预估")
            self.wechat_tip_label.setText("")
            return

        # Get current settings
        duration = self.duration_spin.value()

        fps_map = {0: 10, 1: 15, 2: 20, 3: 25}
        fps = fps_map[self.fps_combo.currentIndex()]

        width_map = {0: 320, 1: 480, 2: 640, 3: 800, 4: 1024, 5: 1280, 6: 1920}
        width = width_map[self.width_combo.currentIndex()]

        colors_map = {0: 128, 1: 192, 2: 256}
        colors = colors_map[self.colors_combo.currentIndex()]

        # Quality factor (higher is better)
        quality_map = {0: 1, 1: 2, 2: 3, 3: 4}
        quality_factor = quality_map[self.quality_combo.currentIndex()]

        # Calculate frame count
        total_frames = int(fps * duration)

        # Estimate output height (maintain aspect ratio)
        if self.video_width > 0 and self.video_height > 0:
            height = int(self.video_height * (width / self.video_width))
        else:
            height = width * 9 // 16  # Assume 16:9 ratio

        # Estimate file size (based on empirical formula)
        # File size estimation formula: frames * width * height * color depth factor * quality
        # factor / compression factor
        color_depth_factor = colors / 256.0
        compression_factor = 30000.0  # Adjust this value to match actual results

        estimated_size_bytes = (total_frames * width * height *
                                color_depth_factor * quality_factor) / compression_factor
        estimated_size_mb = estimated_size_bytes / (1024 * 1024)

        # Update estimate label - remove font settings but keep format
        self.estimate_label.setText(
            f"<b>预估GIF参数:</b><br><br>"
            f"• <b>总帧数:</b> {total_frames} 帧<br>"
            f"• <b>分辨率:</b> {width}x{height} 像素<br>"
            f"• <b>预估大小:</b> {estimated_size_mb:.2f} MB"
        )

        # Add WeChat tips
        warnings = []

        if total_frames > 300:
            warnings.append(f"帧数 ({total_frames}) 超过微信建议的300帧限制")

        if estimated_size_mb > 10:
            warnings.append(f"文件大小 ({estimated_size_mb:.1f}MB) 超过微信的10MB限制")

        if warnings:
            self.wechat_tip_label.setText("⚠️ " + " 和 ".join(warnings))
            self.wechat_tip_label.setStyleSheet("""
                color: #FF6B00;
                font-style: italic;
            """)
        else:
            self.wechat_tip_label.setText("✅ 预估参数符合微信公众号标准")
            self.wechat_tip_label.setStyleSheet("""
                color: #34C759;
                font-style: italic;
            """)

    def log_message(self, message):
        # Ensure that log_text is initialized
        if hasattr(self, 'log_text') and self.log_text is not None:
            self.log_text.append(message)
            # Auto-scroll to the bottom
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )
        else:
            # If log_text is not initialized, print to the console
            print(f"Log: {message}")

    def clear_log(self):
        self.log_text.clear()

    def open_file_dialog(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.avi *.mov *.wmv *.mkv *.flv);;所有文件 (*)",
            options=options
        )

        if file_path:
            self.set_input_file(file_path)

    def set_input_file(self, file_path):
        self.input_file = file_path
        file_path_obj = Path(file_path)
        filename = file_path_obj.name

        self.log_message(f"已选择文件: {file_path}")

        # Display the selected file name in the drop area
        self.drop_area.label.setPixmap(QPixmap())  # Clear the icon
        self.drop_area.label.setText(f"已选择: {filename}")  # Show the file name in the drop area
        self.drop_area.label.setStyleSheet(
            "background-color: #e6f7ff; border-radius: 8px; padding: 15px; border: 1px solid #0071e3;")

        # Get video duration and resolution
        try:
            cmd = [
                FFPROBE_PATH,
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                file_path
            ]
            result = run_command(cmd, capture_output=True, text=True)
            self.video_duration = float(result.stdout.strip())

            # Update the maximum value of the duration spinbox
            self.duration_spin.setRange(0.1, self.video_duration)

            # Use the full video duration by default
            self.duration_spin.setValue(self.video_duration)

            # Get resolution
            cmd = [
                FFPROBE_PATH,
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'csv=s=x:p=0',
                file_path
            ]
            result = run_command(cmd, capture_output=True, text=True)
            resolution = result.stdout.strip()

            # Parse width and height for estimation
            if "x" in resolution:
                width_str, height_str = resolution.split("x")
                self.video_width = int(width_str)
                self.video_height = int(height_str)

            self.log_message(
                f"视频信息: 时长={self.video_duration:.1f}秒, 分辨率={resolution}")

            # Display duration and resolution information in the label below without repeating the file name
            self.file_info_label.setText(
                f"时长: {self.video_duration:.1f}秒, 分辨率: {resolution}")
            self.convert_btn.setEnabled(True)

            # Update the output estimate
            self.update_output_estimate()
        except Exception as e:
            error_msg = f"无法读取视频信息: {str(e)}"
            self.log_message(f"错误: {error_msg}")
            QMessageBox.warning(self, "错误", error_msg)
            self.file_info_label.setText(f"无法读取视频信息: {str(e)}")

    def load_config(self):
        """Load settings from config file if it exists"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.default_output_dir = config.get(
                        'output_dir', self.default_output_dir)
                    self.ask_save_location = config.get(
                        'ask_save_location', False)
                    self.log_message(f"已加载配置文件: {self.config_file}")
        except Exception as e:
            # If failed to load, use default values
            self.log_message(f"加载配置文件失败: {str(e)}")

    def save_config(self):
        """Save settings to config file"""
        try:
            config = {
                'output_dir': self.default_output_dir,
                'ask_save_location': self.ask_save_location
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            self.log_message(f"已保存配置到: {self.config_file}")
        except Exception as e:
            self.log_message(f"保存配置文件失败: {str(e)}")

    def open_settings_dialog(self):
        """Open settings dialog"""
        dialog = SettingsDialog(
            self,
            output_dir=self.default_output_dir,
            ask_save_location=self.ask_save_location
        )

        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            self.default_output_dir = settings['output_dir']
            self.ask_save_location = settings['ask_save_location']
            self.log_message(
                f"已更新设置: 输出目录={self.default_output_dir}, 询问保存位置={self.ask_save_location}")
            # Save settings to config file
            self.save_config()

    def convert_to_gif(self):
        if not self.input_file:
            QMessageBox.warning(self, "错误", "请先选择一个视频文件")
            return

        # Automatically determine the output file name based on the input file
        input_path = Path(self.input_file)
        default_output_filename = input_path.stem + ".gif"
        default_output_path = Path(
            self.default_output_dir) / default_output_filename

        # Determine whether to show the file dialog based on whether to ask for save location
        if self.ask_save_location:
            self.output_file, _ = QFileDialog.getSaveFileName(
                self, "保存GIF文件", str(
                    default_output_path), "GIF文件 (*.gif);;所有文件 (*)"
            )

            if not self.output_file:  # User canceled the save dialog
                return
        else:
            # Use the default path directly
            self.output_file = str(default_output_path)

            # Check if the file already exists, and if so, add a number
            output_path = Path(self.output_file)
            counter = 1
            while output_path.exists():
                new_filename = f"{input_path.stem}_{counter}.gif"
                output_path = Path(self.default_output_dir) / new_filename
                counter += 1

            self.output_file = str(output_path)

        if not self.output_file.lower().endswith('.gif'):
            self.output_file += '.gif'

        self.log_message(f"输出文件: {self.output_file}")

        # Get parameters
        start_time = self.start_time_spin.value()
        duration = self.duration_spin.value()

        fps_map = {0: 10, 1: 15, 2: 20, 3: 25}
        fps = fps_map[self.fps_combo.currentIndex()]

        quality_map = {0: 1, 1: 3, 2: 5, 3: 6}  # Higher is better quality
        quality = quality_map[self.quality_combo.currentIndex()]

        width_map = {0: 320, 1: 480, 2: 640, 3: 800, 4: 1024, 5: 1280, 6: 1920}
        width = width_map[self.width_combo.currentIndex()]

        # Get advanced parameters
        dither_method_map = {0: 'bayer', 1: 'floyd_steinberg', 2: 'sierra2_4a'}
        dither_method = dither_method_map[self.dither_combo.currentIndex()]

        colors_map = {0: 128, 1: 192, 2: 256}
        colors = colors_map[self.colors_combo.currentIndex()]

        # Disable UI during conversion
        self.convert_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText("正在转换...")

        # Start conversion thread
        self.start_conversion(start_time, duration, fps,
                              quality, width, dither_method, colors, False)

    def start_conversion(self, start_time, duration, fps, quality, width, dither_method, colors,
                         ignore_limits=False):
        """Start conversion thread with option to ignore limits."""
        self.conversion_thread = ConversionThread(
            self.input_file, self.output_file, start_time, duration, fps, quality, width,
            dither_method, colors, ignore_limits
        )
        self.conversion_thread.progress_signal.connect(self.update_progress)
        self.conversion_thread.finished_signal.connect(
            self.conversion_finished)
        self.conversion_thread.error_signal.connect(self.conversion_error)
        self.conversion_thread.log_signal.connect(self.log_message)
        self.conversion_thread.warning_signal.connect(self.handle_warning)
        self.conversion_thread.start()

    def handle_warning(self, message, warning_type):
        """Handle warning signals and display dialog asking user whether to continue."""
        # Restore UI state
        self.progress_bar.setVisible(False)
        self.convert_btn.setEnabled(True)

        # Use Apple-style warning dialog
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("注意")
        msg_box.setText(message)
        msg_box.setInformativeText("是否仍然继续转换？\n(可能在某些平台上无法正常使用)")
        msg_box.setIcon(QMessageBox.Warning)

        # 自定义按钮
        continue_btn = msg_box.addButton("继续转换", QMessageBox.AcceptRole)
        continue_btn.setStyleSheet("""
            background-color: #0071e3;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
        """)

        cancel_btn = msg_box.addButton("取消", QMessageBox.RejectRole)
        cancel_btn.setStyleSheet("""
            background-color: #f5f5f7;
            color: #333333;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
        """)

        msg_box.setDefaultButton(cancel_btn)

        # Show dialog
        msg_box.exec_()
        clicked_button = msg_box.clickedButton()

        if clicked_button == continue_btn:
            self.log_message("用户选择忽略限制，继续转换...\n")
            self.progress_bar.setVisible(True)
            self.convert_btn.setEnabled(False)
            self.status_label.setText("正在转换...")

            # Get current parameters
            start_time = self.start_time_spin.value()
            duration = self.duration_spin.value()

            fps_map = {0: 10, 1: 15, 2: 20, 3: 25}
            fps = fps_map[self.fps_combo.currentIndex()]

            quality_map = {0: 1, 1: 3, 2: 5, 3: 6}
            quality = quality_map[self.quality_combo.currentIndex()]

            width_map = {0: 320, 1: 480, 2: 640,
                         3: 800, 4: 1024, 5: 1280, 6: 1920}
            width = width_map[self.width_combo.currentIndex()]

            dither_method_map = {0: 'bayer',
                                 1: 'floyd_steinberg', 2: 'sierra2_4a'}
            dither_method = dither_method_map[self.dither_combo.currentIndex()]

            colors_map = {0: 128, 1: 192, 2: 256}
            colors = colors_map[self.colors_combo.currentIndex()]

            # Start new conversion thread, ignoring limits
            self.start_conversion(start_time, duration, fps,
                                  quality, width, dither_method, colors, True)
        else:
            self.log_message("用户取消了转换操作\n")
            self.status_label.setText("转换已取消")

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def conversion_finished(self, message):
        self.status_label.setText(message)
        self.progress_bar.setValue(100)
        self.convert_btn.setEnabled(True)

        # Use Apple-style success dialog
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("转换完成")
        msg_box.setText("GIF转换已成功完成")
        msg_box.setInformativeText(message)
        msg_box.setIcon(QMessageBox.Information)

        # success button
        ok_btn = msg_box.addButton("确定", QMessageBox.AcceptRole)
        ok_btn.setStyleSheet("""
            background-color: #0071e3;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
        """)

        open_folder_btn = msg_box.addButton("打开文件位置", QMessageBox.ActionRole)
        open_folder_btn.setStyleSheet("""
            background-color: #f5f5f7;
            color: #333333;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
        """)

        msg_box.setDefaultButton(ok_btn)
        msg_box.exec_()

        # If user clicked "Open Location"
        if msg_box.clickedButton() == open_folder_btn:
            output_path = Path(self.output_file)
            folder_path = str(output_path.parent.absolute())
            # Open folder using OS default method
            if sys.platform == 'win32':
                os.startfile(folder_path)
            elif sys.platform == 'darwin':  # macOS
                run_command(['open', folder_path])
            else:  # Linux
                run_command(['xdg-open', folder_path])

    def conversion_error(self, error_message):
        self.status_label.setText(f"错误: {error_message}")
        self.progress_bar.setVisible(False)
        self.convert_btn.setEnabled(True)

        # Use Apple-style error dialog
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("转换错误")
        msg_box.setText("GIF转换过程中发生错误")
        msg_box.setInformativeText(error_message)
        msg_box.setDetailedText("请检查日志获取更多详细信息。")
        msg_box.setIcon(QMessageBox.Critical)

        ok_btn = msg_box.addButton("确定", QMessageBox.AcceptRole)
        ok_btn.setStyleSheet("""
            background-color: #0071e3;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
        """)

        msg_box.setDefaultButton(ok_btn)
        msg_box.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Video2GifApp()
    window.show()
    sys.exit(app.exec_())
