# 视频转高清GIF工具 - 微信公众号专用

一个简洁易用的视频转GIF工具，专为微信公众号优化，确保生成的GIF符合微信公众号的要求（不超过10MB，不超过300帧）。支持Windows和macOS系统。

![应用截图](https://github.com/yourusername/video2gif_for_wechat/raw/main/screenshots/app_screenshot.png)

## 功能特点

- 🎨 简洁优雅的现代用户界面
- 📱 对微信公众号GIF格式限制进行优化
- 🖱️ 支持拖放上传视频文件
- ⚙️ 自定义参数控制（帧率、质量、尺寸等）
- 🔍 自动检测并提示是否符合微信公众号规范
- 🔄 使用ffmpeg高质量转换
- 📋 详细转换日志实时显示
- 🌐 跨平台支持：Windows和macOS
- 💾 自动保存用户设置和偏好
- 🗂️ 智能文件命名和输出目录管理

## 使用方法

### 方式一：下载预编译版本（推荐）

1. 从[Releases](https://github.com/yourusername/video2gif_for_wechat/releases)页面下载最新版本
2. 解压缩文件
3. 运行`Video2Gif微信版.exe`（Windows）或`Video2Gif微信版.app`（macOS）

### 方式二：从源码运行

#### 前提条件

- Python 3.9 或以上版本
- 已安装 pip

#### 安装步骤

1. 克隆或下载本仓库
   ```bash
   git clone https://github.com/yourusername/video2gif_for_wechat.git
   cd video2gif_for_wechat
   ```

2. 安装依赖包
   ```bash
   pip install -r requirements.txt
   ```

3. 下载 FFmpeg 可执行文件
   > **注意**: 由于 FFmpeg 文件较大，它们没有包含在 Git 仓库中。您需要手动下载并放置到正确的位置。

   - **Windows**:
     1. 下载 [FFmpeg for Windows](https://www.ffmpeg.org/download.html#build-windows) (静态构建版本)
     2. 解压并找到 `ffmpeg.exe` 和 `ffprobe.exe` 文件
     3. 将这两个文件放置在项目的 `lib/windows/` 目录中

   - **macOS**:
     1. 下载 [FFmpeg for macOS](https://www.ffmpeg.org/download.html#build-mac)
     2. 解压并找到 `ffmpeg` 和 `ffprobe` 可执行文件
     3. 将这两个文件放置在项目的 `lib/mac/` 目录中
     4. 通过以下命令授予执行权限:
        ```bash
        chmod +x lib/mac/ffmpeg lib/mac/ffprobe
        ```

4. 运行程序
   ```bash
   python main.py
   ```

## 详细使用说明

1. **上传视频文件**：通过拖放文件到指定区域或点击选择文件

2. **设置转换参数**：
   - **开始时间**：从视频的哪个时间点开始截取
   - **持续时间**：截取多长时间的视频内容
   - **帧率**：每秒显示多少帧（影响文件大小和流畅度）
   - **质量**：输出GIF的质量（影响文件大小和清晰度）
   - **宽度**：输出GIF的宽度（影响文件大小和清晰度）
   - **高级设置**：抖动算法和调色板颜色数

3. **设置输出选项**：点击"设置"按钮可以：
   - 更改默认输出目录
   - 选择是否每次询问保存位置
   - 所有设置会自动保存到配置文件，下次启动时自动加载

4. **开始转换**：点击"开始转换"按钮启动转换过程
   - 文件将自动使用原视频文件名（更改扩展名为.gif）
   - 如果文件已存在，会自动添加序号避免覆盖

5. **查看结果**：转换完成后，可以查看：
   - 生成的GIF文件大小和帧数
   - 是否符合微信公众号标准
   - 可以一键打开文件所在位置

## 注意事项

- 微信公众号对GIF的限制：文件大小不超过10MB，帧数不超过300帧
- 如果生成的GIF超出限制，程序会给出提示并让您选择是否继续
- 降低帧率、质量或时长可以减小文件大小
- 避免选择过长时间的视频片段转换

## 为开发者

### 源码结构

- `main.py`: 主程序入口
- `lib/`: FFmpeg工具目录（按操作系统区分）
- `res/icons/`: 图标资源文件
- `config.json`: 用户配置文件（自动生成）

### 打包应用

请参考仓库中的[打包说明](打包说明.md)了解如何将应用打包为可分发的可执行文件。

## 鸣谢

- 本工具使用 [FFmpeg](https://ffmpeg.org/) 进行视频处理
- 界面基于 [PyQt5](https://www.riverbankcomputing.com/software/pyqt/)
- 图标来自 [Material Design Icons](https://materialdesignicons.com/)

## 许可证

[MIT License](LICENSE)

## 贡献

欢迎提交问题、功能请求和贡献代码！请参阅[贡献指南](CONTRIBUTING.md)了解更多信息。 