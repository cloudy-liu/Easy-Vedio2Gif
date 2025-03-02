# Easy Vedio2Gif 

微信公众号文章使用的视频转 Gif 工具

![应用截图](https://github.com/Easy-Vedio2Gif/Easy-Vedio2Gif/raw/main/screenshots/app.png)


## 使用方法

### 方式一：下载预编译版本（推荐）

1. 从[Releases](https://github.com/Easy-Vedio2Gif/Easy-Vedio2Gif/releases)页面下载最新版本
2. 解压缩文件
3. 找到 `video2gif.exe` 文件，双击运行, **默认提供 windows 可执行文件**

### 方式二：从源码运行

#### 前提条件

- Python 3.9 或以上版本
- 已安装 pip

#### 安装步骤

1. 克隆或下载本仓库
   ```bash
   git clone https://github.com/cloudy-liu/Easy-Vedio2Gif.git
   cd Easy-Vedio2Gif
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

## Tips

- 微信公众号对GIF的限制：文件大小不超过10MB，帧数不超过300帧
- 如果生成的GIF超出限制，程序会给出提示并让您选择是否继续
- 降低帧率、质量或时长可以减小文件大小
- 避免选择过长时间的视频片段转换

## Software stack

- 本工具使用 [FFmpeg](https://ffmpeg.org/) 进行视频处理
- 界面基于 [PyQt5](https://www.riverbankcomputing.com/software/pyqt/)
- 图标来自 [Material Design Icons](https://materialdesignicons.com/)

## License

[MIT License](LICENSE)