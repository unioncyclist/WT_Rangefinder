# 黄标测距

启动后实时检测视频源（默认 OBS Virtual Camera）右下角 445x445 区域，识别两个可替换目标&一个临时目标的中心点并在终端输出像素距离。

## 1. 安装依赖

```bash
pip install -r requirements.txt
```

## 2. 准备模板（有默认配置）

把目标裁成小图，例如：

- `templates/warning.png`：黄标/小队标
- `templates/arrow.png`：玩家位置箭头
- `templates/apoint.png` & `templates/apointRed.png`：A点,测距参照物；网页里可切换当前使用的参考图像

建议使用 PNG

## 3. 运行示例

### 实时检测（视频右下区域）

双击运行`shape_distance.py`即可，啥都没发生的话我也不会，程序AI写的

启动后会打印两条地址：

- 本机访问：`http://127.0.0.1:<端口>`
- 局域网访问：`http://<你的局域网IP>:<端口>`

其中端口默认使用 `9973`，如果该端口被占用会自动切换到空闲端口。

若你环境里的 OpenCV 不支持按名称打开 OBS 虚拟摄像头，可改用：

```bash
python shape_distance.py --camera-index 0
```

## 4. 参数说明

- `--scale-min/--scale-max/--scale-step`：模板多尺度匹配区间
- `--min-score`：最低匹配分数，各个识别项默认值不同
- `--interval-ms`：每帧检测间隔（毫秒）
- `--report-ms`：终端输出间隔（毫秒）
- `--web-host`：网页服务监听地址，默认 `0.0.0.0`
- `--web-port`：网页服务端口，默认 `9973`（冲突时自动切换）
- `--camera-index`：摄像头索引，OBS 虚拟摄像头不可用时可手动指定

## 5. 输出

终端会周期输出：

- 中心距离（像素，格式 `distance=xx.xxpx`）
- 匹配失败时输出 `distance=nan`
- `--debug` 时附带中心点与匹配分数

按 `Ctrl+C` 退出。

## 6. 调试建议

- 先加 `--debug` 查看实时分数与距离输出。
- 默认使用 `OBS Virtual Camera` 作为输入源，先在 OBS 里点击 `Start Virtual Camera`。
- 默认仅尝试 `OBS Virtual Camera`；若 OpenCV 按名称打开失败，会自动通过设备列表定位 `OBS Virtual Camera` 并按索引打开。
- 若 OBS 未启动或系统设备列表中不存在 OBS 虚拟摄像头，程序会报错退出。
- 如需改用其它相机，可用 `--camera-index` 手动指定。
- ROI 固定为输入源右下角 `445x445`，如果目标不在该区域内会持续提示低分数。
- Windows 下如果路径含中文，优先在项目目录里用相对路径运行（如 `templates/warning.png`）。

  
# Referenced Projects in this project:

NumPy: https://github.com/numpy/numpy

OpenCV: https://github.com/opencv/opencv

mss: https://github.com/BoboTiG/python-mss

pygrabber: https://pypi.org/project/pygrabber

I would like to thank the authors and maintainers of these projects.
