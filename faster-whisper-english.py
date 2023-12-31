import hashlib
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Question:
    script_index: int
    script: str
    transcript: str
    wav_dir_path: Path

    @property
    def file_id(self):
        return hashlib.md5((self.script + str(self.script_index)).encode()).hexdigest()

    @property
    def output_wav_name(self):
        return f"{self.file_id}.wav"

    @property
    def wav_file_path(self):
        return self.wav_dir_path / self.output_wav_name

    @property
    def record_info(self):
        return {"script": self.script, "file_name": self.output_wav_name}


import queue

import pydub
import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer
import logging
import os

class WebRTCRecord:
    def __init__(self):
        st_webrtc_logger = logging.getLogger("streamlit_webrtc")
        #st_webrtc_logger.setLevel(logging.WARNING)
        #st_webrtc_logger.setLevel(logging.DEBUG)
        #print("set webtrc_logger to DEBUG.")
        self.webrtc_ctx = webrtc_streamer(
            key="sendonly-audio",
            mode=WebRtcMode.SENDONLY,
            #audio_receiver_size=256,
            audio_receiver_size=512,
            rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
            media_stream_constraints={
                "audio": True,
            },
        )
        #self.webrtc_ctx = webrtc_streamer(
        #    key="sendonly-audio",
        #    mode=WebRtcMode.SENDONLY,
        #    #audio_receiver_size=256,
        #    audio_receiver_size=512,
        #    media_stream_constraints={
        #        "audio": True,
        #    }
        #)

        if "audio_buffer" not in st.session_state:
            st.session_state["audio_buffer"] = pydub.AudioSegment.empty()

    def recording(self, question):
        #print("recording IN.")
        status_box = st.empty()

        while True:
            #print("recording start...")
            if self.webrtc_ctx.audio_receiver:
                try:
                    #print("Try get_frames...")
                    #status_box.info("Try get_frames...")
                    audio_frames = self.webrtc_ctx.audio_receiver.get_frames(timeout=1)
                except queue.Empty:
                    status_box.warning("No frame arrived.")
                    print("No frame arrived.")
                    continue

                status_box.info("Now Recording...")
                #print("Now Recording...")

                sound_chunk = pydub.AudioSegment.empty()
                for audio_frame in audio_frames:
                    sound = pydub.AudioSegment(
                        data=audio_frame.to_ndarray().tobytes(),
                        sample_width=audio_frame.format.bytes,
                        frame_rate=audio_frame.sample_rate,
                        channels=len(audio_frame.layout.channels),
                    )
                    sound_chunk += sound

                if len(sound_chunk) > 0:
                    st.session_state["audio_buffer"] += sound_chunk
            else:
                break

        audio_buffer = st.session_state["audio_buffer"]

        if not self.webrtc_ctx.state.playing and len(audio_buffer) > 0:
            status_box.success("Finish Recording")
            try:
                audio_buffer.export(str(question.wav_file_path), format="wav")
            except BaseException:
                st.error("Error while Writing wav to disk")

            # Reset
            st.session_state["audio_buffer"] = pydub.AudioSegment.empty()

            # ここで変換してみる
            model = st.session_state["ASR_MODEL"]
            transcript = transcribe(question.wav_file_path, model)
            file_size = os.path.getsize(question.wav_file_path)
            st.write(f"File：{question.wav_file_path} ({file_size} Byte)")
            st.write(f"聞き取り：{transcript}")

        #print("recording OUT.")


import threading
#import whisper
from faster_whisper import WhisperModel
import streamlit as st

def format_string(s):
    s = s.replace(',', '')
    s = s.replace('.', '')
    s = s.strip()
    return s

def transcribe(file_path, model):
    #result = model.transcribe(str(file_path), verbose=True)
    print(f"{file_path} transcribe...")
    st.write(f"{file_path} transcribe...")

    # https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/vad.py#L14
    # vad_parameters=dict(min_silence_duration_ms=500)
    #vad_parameters = 
    #  threshold: float = 0.5
    #  min_speech_duration_ms: int = 250
    #  max_speech_duration_s: float = float("inf")
    #  min_silence_duration_ms: int = 2000
    #  window_size_samples: int = 1024
    #  speech_pad_ms: int = 400
    #segments, info = model.transcribe(
    # str(file_path),
    # beam_size=5,
    # vad_filter=True,
    # vad_parameters=vad_parameters,
    # without_timestamps=True,)

    segments, info = model.transcribe(
    	str(file_path),
    	beam_size=5,)
    print(f"lang:({info.language}) prob:({info.language_probability}) duration:({info.duration})")
    st.write(f"lang:({info.language}) prob:({info.language_probability}) duration:({info.duration})")

    text = ""
    for segment in segments:
        print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))
        st.write(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
        text += segment.text

    #return format_string(result["text"])
    return text

import time
def async_transcribe(question, model):
    start = time.perf_counter()
    transcript = transcribe(question.wav_file_path, model)
    end = time.perf_counter()
    print(f"経過時間： {end - start}")
    question.transcript = transcript
    print(f" #### transcript: {transcript}")

def start_transcription_thread(question):
    model = st.session_state["ASR_MODEL"]
    x = threading.Thread(target=async_transcribe, args=(question, model))
    x.start()



import streamlit as st
from pathlib import Path
#from question import Question
import json

def main():

    logging.basicConfig()
    logging.getLogger("faster_whisper").setLevel(logging.DEBUG)

    print("main#0")
    # 録音ファイルの保存先の設定
    RECORD_DIR = Path("./records")
    RECORD_DIR.mkdir(exist_ok=True)

    # セッション状態の管理
    #if 'current_question_index' not in st.session_state:
    #    st.session_state['current_question_index'] = 0
    st.session_state['current_question_index'] = 0

    # whisper model
    #print(whisper.__path__)
    #model_str = "tiny"
    #model_str = "base"
    model_str = "small"
    #model_str = "medium" # Streamlit Cloud ではメモリ足りない
    #model_str = "large"
    #model_str = "large-v3"
    #st.session_state["ASR_MODEL"] = whisper.load_model(model_str)
    st.session_state["ASR_MODEL"] = WhisperModel(model_str, device="cpu", compute_type="int8")

    # 問題文を読み込む
    script_file_path = Path('scripts/en.json')

    #scripts = load_scripts(script_file_path)
    #json_open = open(script_file_path, 'r')
    #json_load = json.load(json_open)
    json_load = {
      "scripts": [
        "The cat sat on the mat.",
        "I like to eat apples and bananas.",
        "My friend is very kind."
      ]
    }
    scripts = json_load['scripts']
    for i, script in enumerate(scripts):
        print(script)

    # 問題リストの初期化
    if 'questions' not in st.session_state:
        st.session_state['questions'] = [
            Question(script_index=i, script=script, transcript="", wav_dir_path=RECORD_DIR)
            for i, script in enumerate(scripts)
        ]

    #print(f"st.session_state['current_question_index']: {st.session_state['current_question_index']}")
    #print(f"st.session_state['questions']: {st.session_state['questions']}")

    # 現在の問題を取得
    question = Question(
        script_index = st.session_state["current_question_index"],
        script = scripts[st.session_state['current_question_index']],
        transcript = "",
        wav_dir_path = RECORD_DIR,
    )

    #print("main#1")
    # 読み上げ文を表示
    st.markdown(f"# {question.script}")

    # Record
    webrtc_record = WebRTCRecord()
    webrtc_record.recording(question)

    #print("main#10")

    # 次の問題へ
    if st.button("Next >") and question.wav_file_path.exists(): # 音声ファイルがない場合 次へ行く
        current_question = st.session_state['questions'][st.session_state['current_question_index']]
        # トランスクリプションをバックグラウンドで開始
        #start_transcription_thread(current_question)
        # 次の問題へ移動
        st.session_state["current_question_index"] += 1


    # 結果表示画面
    if st.session_state['current_question_index'] >= len(scripts):
        score = 0

        st.title("結果発表")
        for question in st.session_state['questions']:
            if question.script == question.transcript:
                score += 1

            if question.transcript:
                st.markdown(f"### 問題 {question.script_index}")
                st.write(f"原稿：{question.script}")
                st.write(f"結果：{question.transcript}")
            else:
                st.markdown(f"### 問題 {question.script_index}")
                st.write(f"原稿：{question.script}")
                st.write(f"結果：処理中...")

        st.markdown(f"# あなたのスコアは... {score} 点！")

        # スレッドが完了した後にボタンを表示
        if st.button("画面を更新"):
            st.rerun()

    print("main#100")

if __name__ == "__main__":
    main()

