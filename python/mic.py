import time
import subprocess
import sounddevice as sd
import numpy as np
import threading


# =================================================================
# MICROPHONE PROCESS (With Applause Logic)
# =================================================================
def mic_process(shared_state, shutdown_event):
    print("[MIC] Process Started.")
    #connection_status["MIC"] = True
    SAMPLE_RATE = 48000 
    BLOCK_DURATION = 0.1
    THRESHOLD = 0.01
    block_size = int(SAMPLE_RATE * BLOCK_DURATION)
    
    # State tracking variables
    noise_start_time = 0
    is_noise_active = False
    loud_triggered = False
    applause_triggered = False

    def callback(indata, frames, time_info, status):
        nonlocal is_noise_active, noise_start_time
        audio = indata[:, 0]
        rms = np.sqrt(np.mean(audio ** 2))
        
        if rms > THRESHOLD:
            if not is_noise_active:
                noise_start_time = time.time()
                is_noise_active = True
        else:
            is_noise_active = False

    stream = sd.InputStream(
        device='USB Audio Device',
        channels=1,
        samplerate=SAMPLE_RATE,
        blocksize=block_size,
        callback=callback
    )
    
    with stream:
        while not shutdown_event.is_set():

                if shared_state.get('is_speaking', False):
                    # Ignore sounds while the robot is speaking
                    shared_state['sound_detected'] = False
                    shared_state['sound_event'] = 'NONE'
                    loud_triggered = False
                    applause_triggered = False
                    is_noise_active = False
                    time.sleep(0.1)
                    continue
                    time.sleep(0.1)
                    continue
                
                current_time = time.time()
            
                if is_noise_active:
                    duration = current_time - noise_start_time
                
                # Logic for Applause (> 3 seconds)
                    if duration > 3.0 and not applause_triggered:
                        print("\n[MIC] 👏 APPLAUSE DETECTED!")
                        shared_state['sound_event'] = 'APPLAUSE'
                    
                        shared_state['sound_detected'] = True  # Reset flag
                        applause_triggered = True
                        loud_triggered = True # Mark loud as triggered so we don't trigger it twice
                
                # Logic for normal Loud Sound (First trigger)
                    elif not loud_triggered:
                        print("\n[MIC] 🔥 LOUD NOISE DETECTED!")
                        shared_state['sound_detected'] = True  
                        shared_state['sound_event'] = 'LOUD_SOUND'
                    
                        loud_triggered = True
            
                else:
                # Reset when silence detected
                    if loud_triggered or applause_triggered:
                        print("[MIC] Silence. Resetting.")
                        shared_state['sound_event'] = 'NONE'
                        loud_triggered = False
                        applause_triggered = False
                        shared_state['sound_detected'] = False  

            
            time.sleep(0.1)

            """if KeyboardInterrupt:
                                print("\n[MIC] Ctrl+C caught! Shutting down microphone process...")
                                #connection_status["MIC"] = False
                                print("[MIC] Shutting down")   
                                time.sleep(0.1)
                                #connection_status["MIC"] = False
                                break"""

    #connection_status["MIC"] = False