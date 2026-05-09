# 黄标测距

启动后实时检测屏幕右下九分之一范围，识别两个可替换目标&一个临时目标的中心点并在终端输出像素距离。

## 1. 安装依赖

```bash
pip install -r requirements.txt
```

## 2. 准备模板（有默认配置）

把目标裁成小图，例如：

- `templates/warning.png`：黄标/小队标
- `templates/arrow.png`：玩家位置箭头
- `templates/apoint.png` & `templates/apointRed.png`：A点,测距参照物

建议使用 PNG

## 3. 运行示例

### 实时检测（右下九分之一）

双击运行`shape_distance.py`即可，啥都没发生的话我也不会，程序AI写的

启动后会打印两条地址：

- 本机访问：`http://127.0.0.1:<端口>`
- 局域网访问：`http://<你的局域网IP>:<端口>`

其中端口默认使用 `9973`，如果该端口被占用会自动切换到空闲端口。

## 4. 参数说明

- `--scale-min/--scale-max/--scale-step`：模板多尺度匹配区间
- `--min-score`：最低匹配分数，各个识别项默认值不同
- `--interval-ms`：每帧检测间隔（毫秒）
- `--report-ms`：终端输出间隔（毫秒）
- `--web-host`：网页服务监听地址，默认 `0.0.0.0`
- `--web-port`：网页服务端口，默认 `9973`（冲突时自动切换）

## 5. 输出

终端会周期输出：

- 中心距离（像素，格式 `distance=xx.xxpx`）
- 匹配失败时输出 `distance=nan`
- `--debug` 时附带中心点与匹配分数

按 `Ctrl+C` 退出。

## 6. 调试建议

- 先加 `--debug` 查看实时分数与距离输出。
- ROI 固定为右下九分之一，如果目标不在该区域内会持续提示低分数。
- Windows 下如果路径含中文，优先在项目目录里用相对路径运行（如 `templates/warning.png`）。

# Referenced Projects in this project:

NumPy: https://github.com/numpy/numpy

OpenCV: https://github.com/opencv/opencv

mss: https://github.com/BoboTiG/python-mss

I would like to thank the authors and maintainers of these projects.
