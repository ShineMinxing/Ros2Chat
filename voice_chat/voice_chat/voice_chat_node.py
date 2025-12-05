import os
import sys
import threading
import queue
import wave
import datetime
from pathlib import Path
import time
import socket
import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray

import httpx
import pyaudio
from openai import OpenAI
from pydub import AudioSegment
import pygame
from vosk import Model, KaldiRecognizer
import pyttsx3

import yaml

# =============== 1. 配置信息 ===============
# 读取 YAML 配置文件
config_file = Path("/home/unitree/ros2_ws/LeggedRobot/src/Ros2Chat/config.yaml")
if not config_file.exists():
    raise FileNotFoundError(f"配置文件不存在: {config_file}")
with open(config_file, "r", encoding="utf-8") as file:
    config = yaml.safe_load(file)

# Extract settings from YAML
API_KEY             = config.get("API_KEY",             "obtain from https://cloud.siliconflow.cn/i/5kSHnwpA")
BASE_URL            = config.get("BASE_URL",            "https://api.siliconflow.cn/v1")
MODEL_CHAT          = config.get("MODEL_CHAT",          "deepseek-ai/DeepSeek-V2.5")
MODEL_VOICE         = config.get("MODEL_VOICE",         "FunAudioLLM/CosyVoice2-0.5B")
VOICE_NAME          = config.get("VOICE_NAME",          "FunAudioLLM/CosyVoice2-0.5B:david")
ROBOT_NAME          = config.get("ROBOT_NAME",          "来福")
# 多行字符串默认值
ROBOT_SETTING       = config.get("ROBOT_SETTING",       (
    "你是光电所的四足机器狗，名字叫做来福。\n"
    "你用中文回答问题，有趣又调皮，回答很简短，喜欢汪汪叫。\n"
    "当你收到一段话，首先你会判断是想让你执行任务还是与你聊天。\n"
    "可能的任务有4个，分别是“去办公室”，“去会议室”，“去厕所”，“去仓库”。\n"
    "如果是在给你任务，你只需要回复“任务：去办公室”等，不要回复任何多余的文字。\n"
    "如果是在与你聊天，你就按照你的性格正常回复。"
))
MAX_CONTEXT_NUMBER  = config.get("MAX_CONTEXT_NUMBER",  5)
LOCAL_FILE_PATH     = config.get("LOCAL_FILE_PATH",     "src/Ros2Chat/local_file")
VOSK_MODEL_PATH     = config.get("VOSK_MODEL_PATH",     "src/Ros2Chat/other/vosk-model-small-cn-0.22")
JOYSTICK_CMD_TOPIC  = config.get("JOYSTICK_CMD_TOPIC",  "NoYamlRead/JoyStringCmd")
MOTION_CMD_TOPIC    = config.get("MOTION_CMD_TOPIC",    "NoYamlRead/SportCmd")

# =============== 1.1 从本地文件覆盖 API_KEY（如果存在） ===============
# 优先从 /home/unitree/ros2_ws/LeggedRobot/src/Ros2Chat/local_file/API_KEY 读取
api_key_file = Path(LOCAL_FILE_PATH) / "API_KEY"

if api_key_file.exists():
    with open(api_key_file, "r", encoding="utf-8") as f:
        file_key = f.read().strip()
    if file_key:
        API_KEY = file_key
        print(f"[VoiceChatNode] 从 {api_key_file} 读取 API_KEY 并覆盖 YAML 中的设置")

# 初始化 OpenAI 客户端（如果你需要代理，可在此配置）
http_client = httpx.Client(trust_env=False, timeout=httpx.Timeout(120.0))
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
    http_client=http_client
)

# 录音相关配置
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # 16kHz

# 确保存音频的文件夹存在
RECORD_FOLDER = Path(LOCAL_FILE_PATH)
if not RECORD_FOLDER.exists():
    RECORD_FOLDER.mkdir(parents=True, exist_ok=True)

# 文本转语音程序初始化
engine = pyttsx3.init()
engine.setProperty('voice', 'cmn')


# =============== 额外：Vosk 中文语音库加载 ===============
if not Path(VOSK_MODEL_PATH).is_dir():
    raise RuntimeError(f"Vosk 模型路径不存在: {VOSK_MODEL_PATH}")
print(f"Loading Vosk model from: {VOSK_MODEL_PATH}")
vosk_model = Model(str(VOSK_MODEL_PATH))
print("Vosk model loaded.")


# =============== 2. 录音数据转文字（使用 Vosk） ===============
def speech_to_text(frames, sample_width):
    """
    用 Vosk 对录音数据进行离线识别（中文）。
    frames：音频帧列表；sample_width：每个采样字节数（paInt16 为 2）
    """
    audio_data = b"".join(frames)
    recognizer = KaldiRecognizer(vosk_model, RATE)
    recognizer.AcceptWaveform(audio_data)
    final_result = recognizer.FinalResult()
    result_dict = json.loads(final_result)
    text = result_dict.get("text", "")
    return text.strip()


# =============== 3. 保存用户语音为 MP3 ===============
def save_input_audio(frames, sample_width) -> Path:
    """
    将录下的 frames 转为临时 WAV，再转换成 MP3 文件，并返回 MP3 文件路径。
    文件名带时间戳，保存在 mp3_record 目录中。
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    wav_path = RECORD_FOLDER / f"temp_input_{timestamp}.wav"
    with wave.open(str(wav_path), 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(sample_width)
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

    mp3_path = RECORD_FOLDER / f"input_{timestamp}.mp3"
    audio_seg = AudioSegment.from_wav(wav_path)
    audio_seg.export(mp3_path, format="mp3")

    if wav_path.exists():
        wav_path.unlink()
    return mp3_path

conversation_history = []
# =============== 4. 调用大语言模型，获取回复 ===============
def get_model_response(user_text: str):
    global conversation_history

    conversation_history.append({
        "role": "user",
        "content": user_text
    })

    history_to_send = conversation_history[-MAX_CONTEXT_NUMBER*2:]  # 不足时自动取全部

    input_message = [{"role": "system", "content": ROBOT_SETTING}] + history_to_send

    try:
        response = client.chat.completions.create(
            model=MODEL_CHAT,
            messages=input_message,
            temperature=0.5,
            max_tokens=1024,
            stream=False
        )
        if response and hasattr(response, 'choices'):
            conversation_history.append({
                "role": "assistant",
                "content": response.choices[0].message.content
            })
            reasoning = getattr(response.choices[0].message, "reasoning_content", None)
            usage = getattr(response, "usage", None)
            if reasoning:
                print("===== reasoning_content =====")
                print(reasoning)
                print("===== end of reasoning =====")
            if usage is not None:
                total_tokens = getattr(usage, "total_tokens", None)
                if total_tokens is not None:
                    print(f"total tokens={total_tokens}")
            return response.choices[0].message.content
        else:
            return "对不起，模型没有返回有效结果。"
    except Exception as e:
        return f"调用模型接口出现错误: {str(e)}"


# =============== 5. 文字转语音 ===============
def speak_text_siliconcloud(text: str):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_mp3 = RECORD_FOLDER / f"output_{timestamp}.mp3"
    try:
        with client.audio.speech.with_streaming_response.create(
            model=MODEL_VOICE,
            voice=VOICE_NAME,
            input=text,
            response_format="mp3"
        ) as response:
            response.stream_to_file(output_mp3)

        pygame.mixer.init()
        pygame.mixer.music.load(str(output_mp3))
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    except Exception as e:
        print(f"调用 SiliconCloud 语音合成失败: {str(e)}")

def speak_text_pyttsx3(text: str):
    engine.say(text)
    engine.runAndWait()


# =============== 6. ROS2 节点：语音对话 ===============
class VoiceChatNode(Node):
    def __init__(self):
        super().__init__('voice_chat_node')
        self.subscription = self.create_subscription(
            Float64MultiArray,
            JOYSTICK_CMD_TOPIC,
            self.control_callback,
            10
        )
        self.publisher = self.create_publisher(
            Float64MultiArray,
            MOTION_CMD_TOPIC,
            10
        )

        self.get_logger().info("VoiceChatNode 已启动")

        self.recording = False
        self.frames_queue = queue.Queue()
        self.sample_width = 2  # 对于 paInt16，每个样本2字节
        self.stop_event = threading.Event()
        self.restart_listener = False
        self.startrecording = True

        # 启动一个后台线程，用于持续录音 + 实时识别
        self.listener_thread = SpeechListener(self)
        self.listener_thread.start()

    def control_callback(self, msg: Float64MultiArray):
        """
        处理外部 ROS Topic 命令
        """
        if msg.data[0] == 22170000:
            if not self.recording:
                self.start_recording()
            else:
                self.stop_recording()
            
    def start_recording(self):
        if not self.recording:
            speak_text_pyttsx3("汪。。。")
            time.sleep(0.3)
            self.get_logger().info("开始录音")
            self.frames_queue = queue.Queue()
            self.recording = True
            self.startrecording = True
        else:
            self.get_logger().warn("当前已在录音状态")

    def stop_recording(self):
        if self.recording:
            self.recording = False

            speak_text_pyttsx3("汪。。。")
            self.get_logger().info("停止录音")

            # 从队列中把录下的帧取出来
            frames = []
            while not self.frames_queue.empty():
                frames.append(self.frames_queue.get())

            # 保存 MP3
            input_mp3_path = save_input_audio(frames, self.sample_width)
            self.get_logger().info(f"保存用户语音: {input_mp3_path}")

            # 进行离线识别
            text = speech_to_text(frames, self.sample_width)
            self.get_logger().info(f"识别结果: {text}")

            # 如果识别到的内容较短，可能是简单命令（坐、趴、站）
            if len(text) < 10:
                if any(word in text for word in ["坐", "座"]):
                    self.get_logger().info("检测到命令: 坐")
                    self.publish_sport_cmd(22110000, 0, 0, 0, 0)
                    return
                elif any(word in text for word in ["趴"]):
                    self.get_logger().info("检测到命令: 趴")
                    self.publish_sport_cmd(25110000, 0, 0, 0, 0)
                    return
                elif any(word in text for word in ["站"]):
                    self.get_logger().info("检测到命令: 站")
                    self.publish_sport_cmd(25100000, 0, 0, 0, 0)
                    return
                elif "跟踪" in text:
                    self.get_logger().info("检测到命令: 转动跟踪")
                    self.publish_sport_cmd(22110000, 0, 0, 0, 0)
                    return
                elif "跟随" in text:
                    self.get_logger().info("检测到命令: 运动跟踪")
                    self.publish_sport_cmd(22120000, 0, 0, 0, 0)
                    return
                elif "开始" in text:
                    self.get_logger().info("检测到命令: 开始工作")
                    self.publish_sport_cmd(22100000, 0, 0, 0, 0)
                    return

            # 调用大语言模型
            response_text = get_model_response(text)
            self.get_logger().info(f"模型回复: {response_text}")

            # 先检查是否包含连续"任务"
            if "任务" in response_text:
                idx = response_text.find("任务")
                response_text_part = response_text[idx+2 : idx+2+8]
                # 任务相关的场所判断
                if "办公室" in response_text_part:
                    self.get_logger().info("执行任务: 去办公室")
                    self.publish_sport_cmd(22270000, -1, 0, 0, 0)
                elif "会议室" in response_text_part:
                    self.get_logger().info("执行任务: 去会议室")
                    self.publish_sport_cmd(22260000, 1, 0, 0, 0)
                elif "厕所" in response_text_part:
                    self.get_logger().info("执行任务: 去厕所")
                    self.publish_sport_cmd(22270000, 1, 0, 0, 0)
                elif "仓库" in response_text_part:
                    self.get_logger().info("执行任务: 去仓库")
                    self.publish_sport_cmd(22260000, -1, 0, 0, 0)

            # 最终合成语音
            # speak_text_pyttsx3(response_text)
            speak_text_siliconcloud(response_text)
            self.restart_listener = True
        else:
            self.get_logger().warn("当前未在录音状态")

    def publish_sport_cmd(self, Action, Value1, Value2, Value3, Value4):
        msg = Float64MultiArray()
        msg.data = [float(Action), float(Value1), float(Value2), float(Value3), float(Value4)]
        self.publisher.publish(msg)
        self.get_logger().info(f"发布Motion CMD消息: {msg.data}")
        self.restart_listener = True


# =============== 7. 后台线程：实时录音 & 实时识别 ===============
class SpeechListener(threading.Thread):
    """
    持续从麦克风读取音频，使用 Vosk KaldiRecognizer 做实时识别：
    1. 打印部分识别结果（partial result）。
    2. 如果未录音且出现‘ROBOT_NAME’则自动start。
    3. 如果已录音且检测到长时间静音（认为语音结束）则自动stop。
    """

    def __init__(self, node: VoiceChatNode):
        super().__init__()
        self.daemon = True
        self.node = node
        self.p = pyaudio.PyAudio()

        # 打开一个单独的流持续读音频
        self.stream = self.p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        self.stream.start_stream()

        # 用完整词汇模式识别（不是只含‘ROBOT_NAME’）
        self.recognizer = KaldiRecognizer(vosk_model, RATE)
        self.last_speech_time = time.time()

        # 若在录音时，会把音频数据放进 node.frames_queue
        # 这里设一个超时时间（秒），如果超时没有新的语音，就判断结束
        self.SILENCE_TIMEOUT = 1.0

    def run(self):
        while True:
            data = self.stream.read(CHUNK)

            if self.node.restart_listener:
                self.node.restart_listener = False
                while not self.node.frames_queue.empty():
                    self.node.frames_queue.get_nowait()
                while True:
                    available_frames = self.stream.get_read_available()
                    if available_frames <= 0:
                        break
                    frames_to_read = min(available_frames, CHUNK)
                    _ = self.stream.read(frames_to_read, exception_on_overflow=False)

                self.node.frames_queue.put(data) #舍弃这段录音
                self.recognizer = KaldiRecognizer(vosk_model, RATE)
                self.last_speech_time = time.time()
                continue

            # 如果正在录音，把原始音频先存起来
            if self.node.recording and self.node.startrecording:
                self.node.startrecording = False
                self.last_speech_time = time.time() + 3
            if self.node.recording:
                self.node.frames_queue.put(data)

            # 实时送入 Vosk，获取部分识别结果
            if self.recognizer.AcceptWaveform(data):
                # 完整的一句话识别完成
                result = json.loads(self.recognizer.Result())
                text = result.get("text", "")
                if text:
                    print(f"[Final] {text}")  # 打印最终文本
                    self.last_speech_time = time.time()

                    # 如果没在录音且识别里出现‘ROBOT_NAME’，则自动start
                    if (not self.node.recording) and (ROBOT_NAME in text):
                        self.node.get_logger().info("full_result检测到唤醒词：‘ROBOT_NAME’")
                        self.node.control_callback(Float64MultiArray(data=[22170000.0]))

            else:
                # 正在识别中的部分结果
                partial_result = self.recognizer.PartialResult()
                partial_text = json.loads(partial_result).get("partial", "")
                if partial_text:
                    # print(f"[Partial] {partial_text}")
                    # 如果没在录音且出现‘ROBOT_NAME’，也可以在partial里判断
                    if (not self.node.recording) and (ROBOT_NAME in partial_text):
                        self.node.get_logger().info("partial_result检测到唤醒词：‘ROBOT_NAME’ (partial)")
                        self.recognizer = KaldiRecognizer(vosk_model, RATE)
                        self.node.control_callback(Float64MultiArray(data=[22170000.0]))
                    # 如果正在录音，就更新 last_speech_time
                    if self.node.recording:
                        self.last_speech_time = time.time()

            # 如果正在录音，且已超过 SILENCE_TIMEOUT 秒无新的语音，则自动 stop
            if self.node.recording:
                time_since_speech = time.time() - self.last_speech_time
                if time_since_speech > self.SILENCE_TIMEOUT:
                    self.node.get_logger().info("检测到静音结束，自动停止录音")
                    self.node.control_callback(Float64MultiArray(data=[22170000.0]))
                    self.recognizer = KaldiRecognizer(vosk_model, RATE)
                    self.last_speech_time = time.time()


# =============== 8. main ===============
def main():
    rclpy.init()
    node = VoiceChatNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
