import shutil

import streamlit as st

#import ui.main as ui_main
#import ui.sidebar as ui_sidebar
#from config import TojiSettings
#from record import Record, RecordStrage
#from util import Counter
#from webrtc import WebRTCRecord

###############################
# ui_main
###############################
class UI_Main:
    def __init__(self):
        pass

    def previous_next_button(self) -> None:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("< Previous"):
                st.session_state["counter"].previous()
        with col2:
            if st.button("Next >"):
                st.session_state["counter"].next()


    def manuscript_view(self, target_text):
        st.markdown(f"# {target_text}", unsafe_allow_html=True)
        print(f"manuscript_view:{target_text}")


    def audio_player_if_exists(self, output_file_path):
        print(f"UI_Main:audio_player_if_exists ({output_file_path.exists()})")
        if output_file_path.exists():
            with output_file_path.open("rb") as f:
                audio_bytes = f.read()

            st.audio(audio_bytes)

ui_main = UI_Main()


###############################
# ui_sidebar
###############################
class UI_Sidebar:
    def __init__(self):
        pass

    def title(self) -> None:
        st.sidebar.title("Voice Recorder")


    def manuscripts_text_area(self) -> None:
        st.sidebar.text_area("input texts", "", key="manuscripts")


    def progress_bar_and_stats(self) -> None:
        st.sidebar.subheader("Progress")
        progress_percent = st.session_state["counter"].progress_percent if st.session_state["counter"].total else 0.0
        st.sidebar.progress(progress_percent)

        # Stats like `2/10`
        current_num = st.session_state["counter"].index + 1
        total_num = st.session_state["counter"].total if st.session_state["counter"].total else 0
        st.sidebar.write(f"{current_num} / {total_num}")


    def has_at_least_one_wav_file(self):
        return st.session_state["counter"].total


    def proceed_to_download(self, settings):
        if st.sidebar.button("Proceed to download"):
            st.session_state["records"].export_record_info_as_json(settings.record_info_path)
            st.session_state["records"].export_unrecorded_texts_as_json(settings.unrecorded_texts_path)
            st.session_state["records"].compress_wav_files_into_zip(settings.archive_filename, settings.wav_dir_path)
            num_wav_files = st.session_state["records"].num_wav_files

            st.sidebar.write("Archive Stats:")
            st.sidebar.write(f"- Num. of wav files {num_wav_files}")
            with open(settings.archive_filename, "rb") as fp:
                st.sidebar.download_button(
                    label="Download", data=fp, file_name=settings.archive_filename, mime="application/zip"
                )

ui_sidebar = UI_Sidebar()

###############################
# config
###############################
from pathlib import Path
from pydantic import BaseSettings

class TojiSettings(BaseSettings):
    wav_dir_path: Path = Path("data/")
    record_info_path: Path = wav_dir_path / "meta.json"
    unrecorded_texts_path: Path = wav_dir_path / "unrecorded.txt"
    archive_filename: str = "toji_wav_archive.zip"

    class Config:
        env_prefix = "toji_"
        case_sensitive = True

settings = TojiSettings()


###############################
# record
###############################
import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

@dataclass
class Record:
    manuscript_index: int
    text: str
    wav_dir_path: Path

    @property
    def file_id(self):
        return hashlib.md5((self.text + str(self.manuscript_index)).encode()).hexdigest()

    @property
    def output_wav_name(self):
        return f"{self.file_id}.wav"

    @property
    def wav_file_path(self):
        return self.wav_dir_path / self.output_wav_name

    @property
    def record_info(self):
        return {"text": self.text, "file_name": self.output_wav_name}

@dataclass
class RecordStrage:
    all_manuscripts: List[str] = field(default_factory=list)
    id2record: Dict[int, Record] = field(default_factory=dict)

    @property
    def num_wav_files(self):
        return len(self.id2record)

    def export_record_info_as_json(self, record_info_path) -> None:
        with record_info_path.open("w") as f:
            json.dump(
                [record.record_info for _, record in self.id2record.items()],
                f,
                ensure_ascii=False,
                indent=4,
            )

    def export_unrecorded_texts_as_json(self, unrecorded_textx_path) -> None:
        if unrecorded_textx_path.exists():
            unrecorded_textx_path.unlink()

        recorded_indexes = set([record.manuscript_index for _, record in self.id2record.items()])
        results = []
        for i, text in enumerate(self.all_manuscripts):
            if i not in recorded_indexes:
                results.append(text)

        if results:
            with unrecorded_textx_path.open("w") as f:
                for text in results:
                    f.write(text + "\n")

    def compress_wav_files_into_zip(self, archive_filename, wav_dir_path):
        with zipfile.ZipFile(archive_filename, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for file_path in wav_dir_path.rglob("*"):
                archive.write(file_path, arcname=file_path.relative_to(wav_dir_path))

###############################
# util
###############################
from typing import Optional

class Counter:
    def __init__(self) -> None:
        self.index: int = 0
        self.total: Optional[int] = None

    def set_total(self, n):
        self.total = n
        print(f"Counter:{self.total}")

    def next(self):
        if self.total and self.index != self.total - 1:
            self.index += 1

    def previous(self):
        if self.index != 0:
            self.index -= 1

    @property
    def progress_percent(self) -> float:
        # include current item
        if self.total:
            return (self.index + 1) / self.total
        else:
            return 0.0

###############################
# webrtc
###############################
import queue

import pydub
import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

class WebRTCRecord:
    def __init__(self):
        # https://zenn.dev/whitphx/articles/streamlit-realtime-cv-app
        # rtc_configuration={  # この設定を足す
        #        "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
        #    }
        # サーバがローカルにない場合、映像・音声伝送の通信を確立するためにこちらの設定が必要です。
        # streamlit_webrtcによる動画・音声の伝送にはWebRTCが使われています。
        # そして、本稿では詳細は省きますが、 リモートの（正確にはNAT越しの）のpeer同士でWebRTC接続するには、
        # グローバルネットワークにあるSTUNサーバへの問い合わせが必要になります。
        # 上記サンプルでは、Googleが公開していてフリーで利用できるSTUNサーバを利用するよう設定しました。
        # 有効なSTUNサーバであればこれ以外を設定しても大丈夫です
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
            print("WebRTCRecord:init set audio_buffer")

    def recording(self, record):
        status_box = st.empty()

        print("WebRTCRecord:recording")
        while True:
            if self.webrtc_ctx.audio_receiver:
                print("Recording Try get_frames...")
                try:
                    audio_frames = self.webrtc_ctx.audio_receiver.get_frames(timeout=1)
                except queue.Empty:
                    status_box.warning("No frame arrived.")
                    print("No frame arrived.")
                    continue

                status_box.info("Now Recording...")
                print("Now Recording.....")

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
            print("Finish Recording")
            try:
                st.session_state["records"].id2record[record.output_wav_name] = record
                audio_buffer.export(str(record.wav_file_path), format="wav")
            except BaseException:
                st.error("Error while Writing wav to disk")

            # Reset
            st.session_state["audio_buffer"] = pydub.AudioSegment.empty()


###############################
# Main
###############################

def initialize_startup():
    # Initialize
    if "counter" not in st.session_state:
        st.session_state["counter"] = Counter()
    if "records" not in st.session_state:
        st.session_state["records"] = RecordStrage()

        # initialize wav dir
        if settings.wav_dir_path.exists():
            shutil.rmtree(settings.wav_dir_path)
        settings.wav_dir_path.mkdir()


def main():
    initialize_startup()

    # To redraw the entire window, this should be declared first.
    ui_main.previous_next_button()

    # Siebar
    ui_sidebar.title()
    ui_sidebar.manuscripts_text_area()
    if ui_sidebar.has_at_least_one_wav_file():
        ui_sidebar.progress_bar_and_stats()
        ui_sidebar.proceed_to_download(settings)

    # Main Window (only visible when manuscript is in the text area)
    if st.session_state["manuscripts"]:
        texts = [t for t in st.session_state["manuscripts"].split("\n") if t]
        st.session_state["records"].all_manuscripts = texts

        if st.session_state["counter"].total is None:
            st.session_state["counter"].set_total(len(texts))

        record = Record(
            manuscript_index=st.session_state["counter"].index,
            text=texts[st.session_state["counter"].index],
            wav_dir_path=settings.wav_dir_path,
        )

        ui_main.manuscript_view(record.text)

        webrtc_record = WebRTCRecord()
        print(f"record_text: {record.text}")
        print(f"record_wav_file_path: {record.wav_file_path}")
        webrtc_record.recording(record)

        ui_main.audio_player_if_exists(record.wav_file_path)


if __name__ == "__main__":
    main()

