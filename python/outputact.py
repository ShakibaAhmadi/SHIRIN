import time
import serial 

from speaker import speaker_process
from face_motor import face_motor_process
from base_motor import base_motor_process

"""def speaker_process(shared_state):
    print("[SPEAKER] Process Started.")
    current_audio = ""
    while True:
        target_audio = shared_state['audio_cmd']
        # If the brain sends a new audio file name, play it
        if target_audio != "" and target_audio != current_audio:
            print(f"[SPEAKER] Playing: {target_audio}")
            # PASTE AUDIO PLAYING CODE HERE (e.g., os.startfile)
            
            current_audio = target_audio
            shared_state['audio_cmd'] = "" # Clear command after playing
        time.sleep(0.1)

def face_process(shared_state):
    print("[FACE] Process Started.")
    current_emotion = "Neutral"
    while True:
        target_emotion = shared_state['robot_emotion']
        if target_emotion != current_emotion:
            print(f"[FACE] Moving eyes and mouth to: {target_emotion}")
            # PASTE FACE MOVEMENT CODE HERE
            current_emotion = target_emotion
        time.sleep(0.1)

def bar_process(shared_state):
    print("[BARS] Process Started.")
    current_emotion = "Neutral"
    while True:
        target_emotion = shared_state['robot_emotion']
        if target_emotion != current_emotion:
            print(f"[BARS] Moving physical emotion bars to: {target_emotion}")
            # PASTE BAR MOVEMENT CODE HERE
            current_emotion = target_emotion
        time.sleep(0.1)"""