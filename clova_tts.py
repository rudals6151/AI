import requests
import uuid
import os
from config import load_config

# Clova TTS API 키 및 URL 설정
config = load_config()
CLOVA_API_URL = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"
CLOVA_API_KEY = config.get("clova", {}).get("api_id", "")
CLOVA_API_SECRET = config.get("clova", {}).get("api_secret", "")


# TTS 출력 함수
def generate_clova_tts(text: str, emotion: str, persona_type: str = "persona_20s_friend", filename: str = "output.wav"):
    # 페르소나에 따른 화자 설정
    persona_to_speaker = {
        "persona_20s_friend": "vgoeun",
        "persona_30s_rational": "vdaeseong",
        "persona_50s_mentor": "vyuna"
    }
    speaker = persona_to_speaker.get(persona_type, "vgoeun")  # 기본은 고은

    # 기본 파라미터
    data = {
        "speaker": speaker,
        "text": text,
        "volume": "0",
        "speed": "0",
        "pitch": "0",
        "format": "wav"
    }

    # 감정별 설정
    emotion_map = {
        "기쁨":     {"emotion": "2", "emotion_strength": "2", "pitch": "-5"},
        "기대":     {"emotion": "2", "emotion_strength": "2", "pitch": "-5"},
        "슬픔":     {"emotion": "1", "emotion_strength": "2", "pitch": "5"},
        "공포":     {"emotion": "1", "emotion_strength": "2", "pitch": "5"},
        "분노":     {"emotion": "3", "emotion_strength": "2", "pitch": "3"},
        "혐오":     {"emotion": "3", "emotion_strength": "2", "pitch": "3"},
        "놀람":     {"pitch": "-2"},
        "신뢰":     {"pitch": "-1"},
        "없음":     {},  # neutral
        "중립":     {}
    }

    if emotion in emotion_map:
        data.update(emotion_map[emotion])

    headers = {
        "X-NCP-APIGW-API-KEY-ID": CLOVA_API_KEY,
        "X-NCP-APIGW-API-KEY": CLOVA_API_SECRET
    }

    # 요청
    response = requests.post(CLOVA_API_URL, headers=headers, data=data)

    # 결과 처리
    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)
        print(f"[🔊 Clova TTS 저장 완료] {filename} (화자: {speaker}, 감정: {emotion})")
    else:
        print(f"[❌ TTS 실패] 상태코드 {response.status_code}: {response.text}")
