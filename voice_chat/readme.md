# Ros2Go2Estimator 🦾
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

- 此包是 https://github.com/ShineMinxing/Ros2Go2Estimator 的子包，但能独立编译和运行
- 在config.yaml中设置参数
- 使用VOSK本地语音转文字
- 使用Deepseek APIKey联网获得文字回复（如果连不上关了VPN再试试）
- 使用pyttsx3本地短文字转语音（超难听），使用CosyVoice2 APIKey联网长文字转语音
- 信号源1-麦克风：实时监测ROBOT_NAME “来福”，开启录音，静默1s结束录音
- 信号源2-SMX/JoystickCmd：Ros2Go2Estimator手柄LT+start开启或结束录音

## 📚 补充说明
- 安装指南总体靠谱......
- LOG ALSA报一堆输出很正常，能关但很麻烦
- 如长期使用，请把api_key换成您自己的https://cloud.siliconflow.cn/i/5kSHnwpA

## 🎥 视频演示
### 最新进展(点击图片进入视频)
1. 语音控制机器狗，DeepSeek大模型语音交流
[![实验1](https://i0.hdslb.com/bfs/archive/6aaac2a8d2726fa2c7d77f20544c9692f9fb752f.jpg)](https://www.bilibili.com/video/BV1YjQVYcEdX/)

2. 语音控制机器狗，实现意图猜测和在预建地图导航。比如说“没有纸张了”，自动执行导航‘去仓库’
[![实验2](https://i2.hdslb.com/bfs/archive/5b95c6eda3b6c9c8e0ba4124c1af9f3da10f39d2.jpg)](https://www.bilibili.com/video/BV1HCQBYUEvk/)

## ⚙️ 安装指南

- Use Ubuntu 22.04, ROS2 Humble
```bash
sudo apt install portaudio19-dev ffmpeg libasound-dev python3-pyaudio python3-pip
pip3 install pyaudio pydub pygame vosk pyttsx3 "openai>=1.0" --user
mkdir -p ~/ros2_ws/LeggedRobot/src && cd ~/ros2_ws/LeggedRobot/src
git clone https://github.com/ShineMinxing/Ros2Chat.git
cd ..
colcon build
ros2 ros2 run voice_chat voice_chat_node
```

## 📄 相关文档
- 主体代码: [github](https://github.com/ShineMinxing/Ros2Go2Estimator)

## 📧 联系我们
``` 
博士团队: 401435318@qq.com  
研究所: 中国科学院光电技术研究所
```

> 📌 注意：当前为开发预览版，完整文档正在编写中
``