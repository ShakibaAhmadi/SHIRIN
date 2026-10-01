import time
import subprocess

def speaker_process(shared_state, shutdown_event):
    print("[SPEAKER] Process Started.")
    #connection_status["SPEAKER"] = True

    # Your manual path definition
    SOUND_DIR = "/media/jetson/sd/beedel/bidel/sound/"
    AUDIO_DEVICE = "hw:0,0"

    # Track the last command so we don't spam the audio repeatedly
    last_played_cmd = None

    shared_state['is_speaking'] = False
    current_process = None

    while not shutdown_event.is_set():
        try:
            # 1. Read the command from the "Blackboard"
            cmd = shared_state.get('speaker_cmd', 'NONE')
            print(f"[SPEAKER DEBUG] speaker_cmd = {cmd}")
            if current_process is not None:
                if current_process.poll() is not None:
                    shared_state['is_speaking'] = False
                    current_process = None
                    print("[SPEAKER] Audio playback finished. Microphone re-enabled.")

            # 2. Only play if it's a new command and not 'NONE'
            if cmd != 'NONE' and cmd != last_played_cmd:
                
                print(f"[SPEAKER] Playing audio for: {cmd}")

                # Update map to match your actual file names
                audio_map = {
                    'CAUTIOUS': 'ROBOT_CAUTIOUS.mp3',
                    'APPLAUSE': 'ROBOT_GRATEFUL.mp3',
                    'LOUD_SOUND': 'SURPRISE.mp3',
                    'ROBOT_HAPPY': 'ROBOT_HAPPY.mp3',
                    'ROBOT_SAD': 'ROBOT_SAD.mp3',
                    'ROBOT_ANGRY': 'ROBOT_ANGRY.mp3',
                    'ROBOT_DISAPPOINTED': 'ROBOT_DISAPPOINTED.mp3',
                }

                if cmd in audio_map:
                    # Extract just the filename from the map
                    file_name = audio_map[cmd].split('/')[-1]

                    # Combine your SOUND_DIR and the file_name
                    full_path = SOUND_DIR + file_name
                    print(f"[SPEAKER] Attempting to play: {full_path}")

                    current_process = subprocess.Popen([
                        "mpg123",
                        "-q",
                        "-o", "alsa",
                        "-a", AUDIO_DEVICE,
                        full_path
                    ])

                    shared_state['is_speaking'] = True

                # Mark as played so we don't loop the sound
                last_played_cmd = cmd

            # 3. Reset trigger if Brain sends 'NONE'
            if cmd == 'NONE':
                last_played_cmd = None

        except KeyboardInterrupt:
            print("\n[SPEAKER] Ctrl+C caught! Shutting down speaker process...")
            speaker_cmd = "NONE"
            #connection_status["SPEAKER"] = False
            print("[speaker] Shutting down")
            time.sleep(0.1)
            #connection_status["SPEAKER"] = False
            break

        """except (BrokenPipeError, EOFError, FileNotFoundError) as e:
            print(
                "[SPEAKER] Main process or Manager stopped. "
                f"Stopping speaker process: {e}",
                flush=True
            )
            break

        except Exception as e:
            print(
                f"[SPEAKER ERROR]: {e}",
                flush=True
            )"""

        time.sleep(0.1) 

"""import time
import subprocess

def speaker_process(shared_state, shutdown_event):
    print("[SPEAKER] Process Started.")
    #connection_status["SPEAKER"] = True
    
    # Your manual path definition
    SOUND_DIR = "/media/jetson/sd/beedel/bidel/sound/"
    AUDIO_DEVICE = "hw:CARD=Device,DEV=0"
    # Track the last command so we don't spam the audio repeatedly
    last_played_cmd = None 
    shared_state['is_speaking'] = False
    current_process = None
   
    while not shutdown_event.is_set():
        try:
            # 1. Read the command from the "Blackboard"
            cmd = shared_state.get('speaker_cmd', 'NONE')
            if current_process is not None:
                if current_process.poll() is not None:
                        shared_state['is_speaking'] = False
                        current_process = None
                        print("[SPEAKER] Audio playback finished. Microphone re-enabled.")

            # 2. Only play if it's a new command and not 'NONE'
            if cmd != 'NONE' and cmd != last_played_cmd:
                print(f"[SPEAKER] Playing audio for: {cmd}")
                shared_state['is_speaking'] = True
                # Update map to match your actual file names
                audio_map = {
                    'CAUTIOUS': 'ROBOT_CAUTIOUS.mp3',
                    'APPLAUSE': 'ROBOT_GRATEFUL.mp3',  
                    'LOUD_SOUND': 'SURPRISE.mp3',
                    'ROBOT_HAPPY': 'ROBOT_HAPPY.mp3',
                    'ROBOT_SAD': 'ROBOT_SAD.mp3',
                    'ROBOT_ANGRY': 'ROBOT_ANGRY.mp3',
                    'ROBOT_DISAPPOINTED': 'ROBOT_DISAPPOINTED.mp3',
                }
                
                if cmd in audio_map:
                    # Extract just the filename from the map (e.g., 'swanlake.mp3')
                    file_name = audio_map[cmd].split('/')[-1]
                    
                    # Combine your SOUND_DIR and the file_name
                    full_path = SOUND_DIR + file_name
                    print(f"[SPEAKER] Attempting to play: {full_path}")
                    
                    # subprocess.Popen runs this in the background, 
                    # so your robot doesn't freeze while the sound plays.
                    # -o alsa: Bypasses JACK (prevents crash)
                    # -a hw:0,0: Forces it to your confirmed hardware address
                    subprocess.Popen([
                        "mpg123", 
                        "-q",
                        "-o", "alsa", 
                        "-a", AUDIO_DEVICE, 
                        full_path
                    ])  
                    shared_state['is_speaking'] = True
                # Mark as played so we don't loop the sound
                last_played_cmd = cmd
                
            # 3. Reset trigger if Brain sends 'NONE'
            if cmd == 'NONE':
                last_played_cmd = None
        except KeyboardInterrupt:
                    print("\n[SPEAKER] Ctrl+C caught! Shutting down speaker process...")
                    speaker_cmd="NONE"
                    print("[speaker] Shutting down")   
                    time.sleep(0.1)
                    #connection_status["SPEAKER"] = False
                    break
        
         # Check the blackboard 10 times a second.
        
        except (BrokenPipeError, EOFError, FileNotFoundError) as e:
            print(
                "[SPEAKER] Main process or Manager stopped. "
                f"Stopping speaker process: {e}",
                flush=True
            )
            break

        except Exception as e:
            print(
                f"[SPEAKER ERROR]: {e}",
                flush=True
            )   
        """