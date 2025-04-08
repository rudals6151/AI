"""
실행 코드
python chat.py --output_file results/result1.json --persona_type persona_20s_friend --chat_id chat101 --user_id user1234
"""
import json
from pathlib import Path
from agents.client_agent import ClientAgent
from agents.counselor_agent import CounselorAgent
from agents.evaluator_agent import EvaluatorAgent
from agents.sub_llm import SubLLMAgent
from config import get_config, set_openai_api_key
from cbt.cbt_mappings import emotion_strategies, cognitive_distortion_strategies
from DB import get_chat_log, save_chat_log, save_user_info, get_user_info
from clova_tts import generate_clova_tts

import whisper
import sounddevice as sd
import numpy as np
import wave
import keyboard
import time

# OpenAI API 키 설정
set_openai_api_key()

def record_audio_keypress(filename="input.wav", fs=16000):
    print("⏺️ Enter 키를 누르면 녹음 시작, 다시 누르면 종료 (2초 이상 누르면 챗봇 종료)")
    while True:
        if keyboard.read_key() == "enter":
            print("🎙️ 녹음 중... 다시 Enter 누르면 종료")
            break

    recording = []
    stream = sd.InputStream(samplerate=fs, channels=1, dtype='int16')
    stream.start()

    while True:
        if keyboard.is_pressed("enter"):
            start_time = time.time()
            while keyboard.is_pressed("enter"):
                time.sleep(0.1)
                if time.time() - start_time >= 2.0:
                    print("🛑 Enter 키를 2초 이상 눌러 챗봇을 종료합니다.")
                    stream.stop()
                    stream.close()
                    return "exit"
            print("⏹️ 녹음 종료")
            break

        data, _ = stream.read(1024)
        recording.append(data)

    stream.stop()
    stream.close()

    if len(recording) == 0:
        print("❌ 녹음된 데이터가 없습니다.")
        return "no_data"

    audio_data = np.concatenate(recording)
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes(audio_data.tobytes())

    print("✅ 저장 완료:", filename)
    return "ok"

def whisper_transcribe(filename="input.wav"):
    model = whisper.load_model("base")
    result = model.transcribe(filename, language='ko')
    return result["text"]

class TherapySimulation:
    def __init__(self, persona_type: str, chat_id: str, user_id: str, max_turns: int = 20):
        self.persona_type = persona_type
        self.chat_id = chat_id
        self.user_id = user_id
        self.max_turns = max_turns
        self.history = []

        user_info = get_user_info(self.user_id)
        if user_info:
            self.name = user_info["name"]
            self.age = user_info["age"]
            self.gender = user_info["gender"]
        else:
            print(f"{self.user_id}는 새로운 사용자입니다. 사용자 정보를 입력해주세요.")
            self.name = input("이름을 입력해주세요: ")
            self.age = int(input("나이를 입력해주세요: "))
            self.gender = input("성별을 입력해주세요: ")
            save_user_info(self.user_id, self.name, self.age, self.gender)

        chat_log = get_chat_log(self.chat_id)
        if chat_log:
            self.history = chat_log
        else:
            self.history.append({"role": "client", "message": f"{self.name}님, 안녕하세요. 어떤 문제가 있으신가요?"})

        self.subllm_agent = SubLLMAgent()
        self.evaluator_agent = EvaluatorAgent(criteria_list=["general_1", "general_2", "general_3", "cbt_1", "cbt_2", "cbt_3"])
        self.counselor_agent = CounselorAgent(
            client_info=f"{self.name}, {self.age}세, {self.gender}",
            total_strategy="",
            persona_type=persona_type,
            emotion="",
            distortion=""
        )

    def run(self):
        mode = input("모드를 선택하세요 (text/voice): ").strip().lower()
        if mode not in ["text", "voice"]:
            mode = "text"

        for turn in range(self.max_turns):
            print(f"\n--- Turn {turn + 1} ({mode.upper()} MODE) ---")

            counselor_msg = self.counselor_agent.generate_response(self.history)
            self.history.append({"role": "counselor", "message": counselor_msg})
            print("Counselor:", counselor_msg)

            # TTS 출력은 voice 모드에서만
            if mode == "voice":
                emotion = self.counselor_agent.emotion or "neutral"
                generate_clova_tts(text=counselor_msg, emotion=emotion, persona_type=self.persona_type)

            if mode == "voice":
                result = record_audio_keypress("input.wav")
                if result == "exit": break
                client_msg = whisper_transcribe("input.wav").strip()
                print(f"{self.name}: {client_msg}")
            else:
                client_msg = input(f"{self.name}: ").strip()

            if any(k in client_msg.lower() for k in ["종료", "끝내자", "그만할래"]):
                print("🛑 종료 명령어 감지됨. 대화를 종료합니다.")
                self.history.append({"role": "client", "message": client_msg})
                break

            self.history.append({"role": "client", "message": client_msg})

            analysis_result = self.subllm_agent.analyze(client_msg)
            emotion = analysis_result.get("감정", "")
            distortion = analysis_result.get("인지왜곡", "")
            total_strategy = analysis_result.get("총합_CBT전략", "")

            print(f"Emotion: {emotion} | Distortion: {distortion} | Strategy: {total_strategy}\n")

            self.counselor_agent = CounselorAgent(
                client_info=f"{self.name}, {self.age}세, {self.gender}성",
                total_strategy=total_strategy,
                persona_type=self.persona_type,
                emotion=emotion,
                distortion=distortion
            )

            save_chat_log(self.user_id, self.chat_id, client_msg, counselor_msg)

        evaluation_result = self.evaluator_agent.evaluate_all(self.history)
        return {
            "persona": self.persona_type,
            "cbt_strategy": total_strategy,
            "cognitive_distortion": distortion,
            "emotion": emotion,
            "history": self.history,
            "evaluation": evaluation_result
        }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_file", required=True)
    parser.add_argument("--persona_type", required=True)
    parser.add_argument("--chat_id", required=True)
    parser.add_argument("--user_id", required=True)
    args = parser.parse_args()

    sim = TherapySimulation(
        persona_type=args.persona_type,
        chat_id=args.chat_id,
        user_id=args.user_id
    )
    result = sim.run()

    Path(args.output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
