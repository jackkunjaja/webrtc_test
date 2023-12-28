import streamlit as st
from streamlit_webrtc import webrtc_streamer
#import cv2
#import av #strealing video library
#import logging

st.title('Streamlit App Test')
st.write('Hello world')

#st_webrtc_logger = logging.getLogger("streamlit_webrtc")
#st_webrtc_logger.setLevel(logging.WARNING)
#st_webrtc_logger.setLevel(logging.INFO)

#webrtc_streamer(key='example')
webrtc_streamer(
            key='example',
            rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
          )
