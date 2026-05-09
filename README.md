# WT_Rangefinder
使用OpenCV的战争雷霆小队标记测距工具。仅供个人编程练习，游戏中使用很可能被认为违反EULA封号。

War Thunder squad marking and rangefinding tool using OpenCV. For personal programming practice only; using this in-game is likely to be considered a violation of the EULA and result in a ban.

有两个版本，	Using external video source version和Self hosted Capture Version。Self hosted Capture Version运行在运行游戏的主机上，直接截取右下角小地图区别并在本地进行识别和处理。	
Using external video source version版本使用外部视频推流作为输入，比如说OBS，在另一台电脑上进行处理。

There are two versions: the “Using external video source version” and the “Self-hosted Capture Version.” The Self-hosted Capture Version runs on the host machine running the game, directly capturing the mini-map area in the bottom-right corner and performing recognition and processing locally.	
The “Using external video source version” uses an external video stream as input—such as OBS—and processes the data on a separate computer.

两个版本都基于个人电脑2560*1440分辨率开发，没有进行其他分辨率测试
个人游戏内使用AMD滤镜，部分筛选色彩范围的识别算法在其他滤镜环境中可能无法正常识别

Both versions were developed for a PC with a 2560x1440 resolution; no testing has been conducted on other resolutions.
The program uses AMD filters for in-game use; some recognition algorithms that rely on specific color ranges may not function properly with other filter environments.

开局在网页后端先选择合适识别A点模式（如有）
检查是否正确识别地图上A点
输入游戏内看到A点的距离，程序会记忆A点的距离和输入作为参考
放小队标记，大约一秒后会在网页后端显示测距结果

At the start, select the appropriate mode for recognizing Point A (if available) in the web backend.
Verify that Point A on the map is correctly identified.
Enter the distance to Point A as seen in-game; the program will store this distance and your input as a reference.
Place a squad marker; the distance measurement result will appear in the web backend approximately one second later.


# Referenced Projects in this project:
NumPy: https://github.com/numpy/numpy
OpenCV: https://github.com/opencv/opencv
mss: https://github.com/BoboTiG/python-mss
I would like to thank the authors and maintainers of these projects.
