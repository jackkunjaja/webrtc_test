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

class WebRTCRecord:
    def __init__(self):
        self.webrtc_ctx = webrtc_streamer(
            key="sendonly-audio",
            mode=WebRtcMode.SENDONLY,
            audio_receiver_size=256,
            rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
            media_stream_constraints={
                "audio": True,
            },
        )

        if "audio_buffer" not in st.session_state:
            st.session_state["audio_buffer"] = pydub.AudioSegment.empty()

    def recording(self, question):
        status_box = st.empty()

        while True:
            if self.webrtc_ctx.audio_receiver:
                try:
                    audio_frames = self.webrtc_ctx.audio_receiver.get_frames(timeout=1)
                except queue.Empty:
                    status_box.warning("No frame arrived.")
                    continue

                status_box.info("Now Recording...")

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






import threading
import whisper
import streamlit as st

def format_string(s):
    s = s.replace(',', '')
    s = s.replace('.', '')
    s = s.strip()
    return s

def transcribe(file_path, model):
    result = model.transcribe(str(file_path), verbose=True)
    return format_string(result["text"])

def async_transcribe(question, model):
    transcript = transcribe(question.wav_file_path, model)
    question.transcript = transcript

def start_transcription_thread(question):
    model = st.session_state["ASR_MODEL"]
    x = threading.Thread(target=async_transcribe, args=(question, model))
    x.start()



import streamlit as st
from pathlib import Path
#from question import Question
import json

def main():

    # 録音ファイルの保存先の設定
    RECORD_DIR = Path("./records")
    RECORD_DIR.mkdir(exist_ok=True)

    # whisper model
    print(whisper.__path__)
    st.session_state["ASR_MODEL"] = whisper.load_model("base")

    # セッション状態の管理
    if 'current_question_index' not in st.session_state:
        st.session_state['current_question_index'] = 0

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

    print(f"st.session_state['current_question_index']: {st.session_state['current_question_index']}")
    print(f"st.session_state['questions']: {st.session_state['questions']}")

    # 現在の問題を取得
    question = Question(
        script_index = st.session_state["current_question_index"],
        script = scripts[st.session_state['current_question_index']],
        transcript = "",
        wav_dir_path = RECORD_DIR,
    )

    # 読み上げ文を表示
    st.markdown(f"# {question.script}")

    # Record
    webrtc_record = WebRTCRecord()
    webrtc_record.recording(question)


    # 次の問題へ
    if st.button("Next >") and question.wav_file_path.exists(): # 音声ファイルがない場合 次へ行く
        current_question = st.session_state['questions'][st.session_state['current_question_index']]
        # トランスクリプションをバックグラウンドで開始
        start_transcription_thread(current_question)
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


if __name__ == "__main__":
    main()

