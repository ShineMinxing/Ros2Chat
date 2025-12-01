# Ros2Chat 🐾

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Ros2Chat** 是在 **ROS 2 Humble / Ubuntu 22.04** 上运行的 **语音 × 大模型交互仓库**，主要负责

用 **麦克风输入 → 离线 ASR (Vosk) → OpenAI Chat → 语音合成** 的完整闭环，与四足 / 双足机器人自然对话并下发运动指令。

---

## ✨ 语音交互特性

| 类别              | 说明                                                     |
| --------------- | ------------------------------------------------------ |
| **离线中文 ASR**    | 使用 Vosk 0.22 模型，完全本地推理，不耗流量                            |
| **在线 / 离线 TTS** | 长文本调用 **CosyVoice2** 云端，高音质；短文本 fallback 到本地 `pyttsx3` |
| **大模型思考**       | 默认接入 DeepSeek‑V2.5，可自定义 `BASE_URL / MODEL_CHAT`        |
| **任务 / 闲聊分流**   | 根据 `ROBOT_SETTING` Prompt 判断是否下发运动任务，或仅闲聊              |
| **手柄触发 + 唤醒词**  | 手柄 `LT + Start` 开 / 关录音；或呼叫 **“来福”** 直接唤醒              |

---

## 🏗️ 生态仓库详细信息参见

[https://github.com/ShineMinxing/Ros2Go2Estimator](https://github.com/ShineMinxing/Ros2Go2Estimator)

---

## 📂 本仓库结构

```
Ros2Chat/
├── voice_chat/                    # 源码包（ROS2 节点）
│   ├── launch/
│   └── voice_chat_node.py         # 主节点（Python）
├── other/                         # Vosk CN 模型
├── local_file/                    # 录音 / TTS 缓存
├── config.yaml                    # 运行参数（见下）
└── Readme.md                      # ← 你正在看
```

---

## ⚙️ 参数一览 `config.yaml`

| 参数                   | 默认值                                           | 说明                        |
| -------------------- | --------------------------------------------- | ------------------------- |
| `API_KEY`            | `sk-***`                                      | OpenAI / DeepSeek API Key |
| `BASE_URL`           | `https://api.siliconflow.cn/v1`               | 兼容 OpenAI 协议的私有代理         |
| `MODEL_CHAT`         | `deepseek-ai/DeepSeek‑V2.5`                   | 对话模型                      |
| `MODEL_VOICE`        | `FunAudioLLM/CosyVoice2-0.5B`                 | 云端语音模型                    |
| `VOICE_NAME`         | `FunAudioLLM/CosyVoice2-0.5B:david`           | 语音人声                      |
| `ROBOT_NAME`         | `来福`                                          | 唤醒词                       |
| `ROBOT_SETTING`      | *多行 Prompt*                                   | 人设与任务判断模板                 |
| `LOCAL_FILE_PATH`    | `src/Ros2Chat/local_file`                     | 录音 & 合成缓存目录               |
| `VOSK_MODEL_PATH`    | `src/Ros2Chat/other/vosk-model-small-cn-0.22` | 离线 ASR 模型路径               |
| `JOYSTICK_CMD_TOPIC` | `SMX/SportCmd`                                | 手柄字符串指令主题                 |
| `MOTION_CMD_TOPIC`   | `SMX/SportCmd`                                | 运动指令发布主题                  |

---

## ⚙️ 安装与编译

```bash
# 1. 依赖
sudo apt update && sudo apt install -y \
  portaudio19-dev ffmpeg libasound-dev python3-pip
pip3 install --user pyaudio pydub pygame vosk pyttsx3 "openai>=1.0"

# 2. clone & build
cd ~/ros2_ws/LeggedRobot/src
git clone https://github.com/ShineMinxing/Ros2Chat.git
# 把 Ros2Chat/config.yaml中的api_key改为自己的
cd .. && colcon build --packages-select voice_chat
source install/setup.bash

# 3. 运行
ros2 run voice_chat voice_chat_node
```

> 🗝️ **首次使用** 请在 `config.yaml` 填入您自己的 `API_KEY`，否则在线 TTS / Chat 无法使用。

---

## 📑 节点接口

```text
/voice_chat_node (rclpy)
├─ 发布
│   • SMX/SportCmd      std_msgs/Float64MultiArray   # 运动 / 任务指令
├─ 订阅
│   • SMX/SportCmd      std_msgs/Float64MultiArray   # LT+Start 开/停录音
└─ 外部依赖
    • 麦克风             pyaudio                     # 实时语音流
```

---

## 🧠 流程概览

1. **实时监听** — Vosk ASR 检测麦克风流，当听到唤醒词「来福」或手柄触发时开始录音。
2. **离线识别** — 静默 1 s 自动结束录音，Vosk 输出中文文本。短指令直接映射为运动指令。
3. **大模型回复** — 交给 DeepSeek Chat 判断任务/闲聊，生成回复。
4. **语音合成** — 长文本调用 CosyVoice2 云 TTS，短文本本地 pyttsx3。
5. **任务下发** — 检测到“任务：去××”，通过 `SMX/SportCmd` 发布导航 / 行为指令。

---

## 📄 深入阅读

* 技术原理笔记：[https://www.notion.so/Ros2Go2-1e3a3ea29e778044a4c9c35df4c27b22](https://www.notion.so/Ros2Go2-1e3a3ea29e778044a4c9c35df4c27b22)
* ROS1 版本参考：[https://github.com/ShineMinxing/FusionEstimation](https://github.com/ShineMinxing/FusionEstimation)

---

## 📨 联系我们

| 邮箱                                          | 单位           |
| ------------------------------------------- | ------------ |
| [401435318@qq.com](mailto:401435318@qq.com) | 中国科学院光电技术研究所 |

> 📌 **本仓库仍在持续开发中** — 欢迎 Issue / PR 交流、贡献！