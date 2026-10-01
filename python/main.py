
#correct and comopletel main file, 30-june
import argparse
import multiprocessing
import subprocess
import time

# Import your functions from the other files!
from inputsense import sonar_process, mic_process, launch_camera
from outputact import base_motor_process, speaker_process, face_motor_process
from brain import brain_process
from camera_listener import camera_listener_process
shutdown_event = multiprocessing.Event()
# ================================================================
# INITIAL MOOD PRESETS
# ================================================================
# Each mood uses VAD values:
# valence:   -1 negative to +1 positive
# arousal:   -1 calm to +1 activated
# dominance: -1 submissive to +1 dominant

MOOD_PRESETS = {
    "NEUTRAL": {
        "valence": 0.0,
        "arousal": 0.0,
        "dominance": 0.0
    },

    "POSITIVE": {
        "valence": 0.3,
        "arousal": 0.3,
        "dominance": 0.1
    },

    "HAPPY": {
        "valence": 0.6,
        "arousal": 0.5,
        "dominance": 0.2
    },

    "CALM": {
        "valence": 0.3,
        "arousal": -0.3,
        "dominance": 0.1
    },

    "SAD": {
        "valence": -0.5,
        "arousal": -0.3,
        "dominance": -0.2
    },

    "ANXIOUS": {
        "valence": -0.4,
        "arousal": 0.6,
        "dominance": -0.4
    },

    "ANGRY": {
        "valence": -0.5,
        "arousal": 0.7,
        "dominance": 0.5
    }
}

def read_startup_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Start BIDEL with a selected personality "
            "and initial mood."
        )
    )

    parser.add_argument(
        "--personality",
        type=str,
        default="BUBBLY",
        help=(
            "Personality name exactly as written "
            "in personality.json"
        )
    )

    parser.add_argument(
        "--mood",
        type=str.upper,
        choices=MOOD_PRESETS.keys(),
        default="NEUTRAL",
        help=(
            "Initial mood name: "
            + ", ".join(MOOD_PRESETS.keys())
        )
    )

    return parser.parse_args()

if __name__ == '__main__':
    #added for mood and personality input
    args = read_startup_arguments()

    ROBOT_PERSONALITY = args.personality.upper()
    INITIAL_MOOD_NAME = args.mood

    INITIAL_MOOD = MOOD_PRESETS[
        INITIAL_MOOD_NAME
    ].copy()

    print(
        f"[MAIN] Personality: {ROBOT_PERSONALITY}"
    )

    print(
        f"[MAIN] Initial mood: {INITIAL_MOOD_NAME}"
    )

    print(
        "[MAIN] Initial VAD: "
        f"V={INITIAL_MOOD['valence']}, "
        f"A={INITIAL_MOOD['arousal']}, "
        f"D={INITIAL_MOOD['dominance']}"
    )

    def wait_for_module(connection_status,
                    module_name,
                    timeout=15):

        print(f"[MAIN] Waiting for {module_name}...")

        start_time = time.time()

        while not connection_status[module_name]:

            if time.time() - start_time > timeout:
                print(f"[MAIN] ERROR: {module_name} failed to connect.")
                return False

            time.sleep(0.1)

        print(f"[MAIN] {module_name} connected.")
        return True

    
    with multiprocessing.Manager() as manager:
        
        # 1. Create the Shared Blackboard
        shared_state = manager.dict({
            #sonar and navigation
            'sonar_front_left': 300,
            'sonar_front_center': 300,
            'sonar_front_right': 300,
            'sonar_back': 300,
            'obstacle_distance': 100,
            'near_obstacle': False,
            'far_obstacle': False,
            'obstacle_direction': 'NONE',
            'current_state': 'PATROL',
            'last_avoid_dir': 'LEFT', # For the tie-breaker
            'investigate_timer': 0.0, #

            'sound_detected': False,
            'is_speaking': False,
            'sound_type': 'LOUD_SOUND',
            'person_in_frame': False,
            'person_emotion': 'Neutral',
            'motor_cmd_x': 0.0,
            'motor_cmd_y': 0.0,
            'motor_cmd_z': 0.0,
            'robot_emotion': 'SMILE',
            #added for mood and personality
            'robot_personality': ROBOT_PERSONALITY,
            'initial_mood_name': INITIAL_MOOD_NAME,
            'mood_valence': INITIAL_MOOD['valence'],
            'mood_arousal': INITIAL_MOOD['arousal'],
            'mood_dominance': INITIAL_MOOD['dominance'],
            'transient_emotion': 'NONE',
            'transient_strength': 0.0,

            'speaker_cmd': 'NONE',
            'mouth_cmd': 'M:0,5,0,5,0,5',
            'eye_cmd': 'E:0,5,0,5',
            'curtain_cmd': 'C:0,0',
            'bar_cmd': 'B:0,0,0,0,0,0,0,0'
            
        })
        connection_status = manager.dict({
                    "SONAR": False,
                    "MIC": False,
                    "CAMERA": False,
                    "BASE": False,
                    "SPEAKER": False,
                    "FACE": False
        })
        #p_camera = multiprocessing.Process(target=camera_listener_process, args=(shared_state, shutdown_event, connection_status))
        #p_camera.start()

        # 2. Define ALL the processes
        processes = [
            multiprocessing.Process(target=sonar_process, args=(shared_state,shutdown_event, connection_status)),
            multiprocessing.Process(target=mic_process, args=(shared_state,shutdown_event)),
            multiprocessing.Process(target=camera_listener_process, args=(shared_state,shutdown_event, connection_status)),
            multiprocessing.Process(target=base_motor_process, args=(shared_state,shutdown_event, connection_status)),
            multiprocessing.Process(target=speaker_process, args=(shared_state,shutdown_event)),
            multiprocessing.Process(target=face_motor_process, args=(shared_state,shutdown_event, connection_status)),
            multiprocessing.Process(target=brain_process, args=(shared_state,ROBOT_PERSONALITY,
        INITIAL_MOOD, shutdown_event)) #added for mood and personality
            
        ]
        
        # 3. Start them all simultaneously
        print("Starting robot systems sequentially...")

        startup_order = [
            (3, "BASE"),
            (0, "SONAR"),
            (5, "FACE"),
            (2, "CAMERA"),
]

        for index, name in startup_order:
            print(f"\n[MAIN] Starting {name}...")

            processes[index].start()
            time.sleep(1)
            if not wait_for_module(connection_status, name, timeout=10):
                print(f"[MAIN] {name} failed. Shutting down.")
                shutdown_event.set()

                for p in processes:
                    if p.is_alive():
                        p.terminate()

                exit()

        print("\n[MAIN] All hardware processes connected.")
        #print("[MAIN] Starting microphone...")
        #processes[1].start()

        #time.sleep(1)

        #print("[MAIN] Starting speaker...")
        #processes[4].start()

        #time.sleep(1)
        camera_producer = subprocess.Popen(["python3", "camera_input.py"])
        # Start brain last
        print("[MAIN] Starting brain...")
        processes[6].start()

        print("[MAIN] BRAIN STARTED. ROBOT READY.")
            
        # 4. Keep main script alive
        try:
            processes[-1].join() 
        except KeyboardInterrupt:
            print("\nShutting down robot...")
            shutdown_event.set()
            """if camera_producer:
                camera_producer.terminate()
                camera_producer.wait()"""

            for p in processes:
                p.join(timeout=3)

            #for p in processes: p.terminate()
            time.sleep(10)
            print("Shutdown complete.")