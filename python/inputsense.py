import time
import serial
import subprocess

from sonar import sonar_process

from mic import mic_process

def launch_camera():

    print("[INPUT HUB] Launching standalone camera.py in the background...")
    return subprocess.Popen(["python3", "camera.py"])

"""def sonar_process(shared_state):
    print("[SONAR] Process Started.")
    
    # 1. SETUP SERIAL (Adjust '/dev/ttyUSB0' and baud rate to match your Arduino)
    try:
        ser_sonar = serial.Serial('/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0', 115200, timeout=1)
        ser_sonar.setDTR(False) 
        ser_sonar.setRTS(False)
        time.sleep(2) # Wait for Arduino to reboot
        ser_sonar.reset_input_buffer()
        #ser_sonar.open()
        print("[SONAR] Serial connection established.")
    except Exception as e:
        print(f"[SONAR ERROR] Could not open Serial: {e}")
        return # Exit if no Arduino is found

    while True:
        try:
            if ser_sonar.in_waiting > 0:
                # 2. READ DATA FROM ARDUINO
                line = ser_sonar.readline().decode('utf-8', errors='ignore').strip()
                print(f"[SONAR RAW] Received: {line}") 
                
                data = line.split(',')
                # Expecting format from Arduino: "FL_dist,FC_dist,FR_dist,B_dist" (e.g. "120,80,200,150")
                data = line.split(',')
                if len(data) == 4:
                    fl = int(data[0]) # Front Left
                    fc = int(data[1]) # Front Center
                    fr = int(data[2]) # Front Right
                    b  = int(data[3]) # Back

                    # 3. WRITE RAW DATA TO SHARED MEMORY
                    shared_state['sonar_front_left'] = fl
                    shared_state['sonar_front_center'] = fc
                    shared_state['sonar_front_right'] = fr
                    shared_state['sonar_back'] = b

                    # 4. ALGORITHM LOGIC: Find the closest obstacle
                    distances = {'FRONT_LEFT': fl, 'FRONT_CENTER': fc, 'FRONT_RIGHT': fr, 'BACK': b}
                    closest_dir = min(distances, key=distances.get)
                    min_dist = distances[closest_dir]

                    # Update direction of closest object
                    shared_state['obstacle_direction'] = closest_dir
                    shared_state['obstacle_detected'] = True 

                    # 5. ALGORITHM LOGIC: Check Thresholds
                    # Threshold 1: Near (Emergency / Interaction distance) < 100cm
                    if min_dist < 5:
                        shared_state['near_obstacle'] = True
                        shared_state['far_obstacle'] = True
                    
                    # Threshold 2: Far (Attention distance) < 200cm
                    elif min_dist < 30:
                        shared_state['near_obstacle'] = False
                        shared_state['far_obstacle'] = True
                    
                    # Clear path
                    else:
                        shared_state['near_obstacle'] = False
                        shared_state['far_obstacle'] = False
                        shared_state['obstacle_direction'] = 'NONE'

        except Exception as e:
            # Catch parsing errors so the process doesn't crash if Arduino sends garbage text
            print(f"[SONAR ERROR inside loop] {e}")
            #pass
            
        time.sleep(0.05) # Run at 20Hz
    def mic_process(shared_state):
    print("[MIC] Process Started.")
    while True:
        # (Your Microphone code will go here later)
        time.sleep(0.1)

    def camera_process(shared_state):
    print("[CAMERA] Process Started.")
    while True:
        # (Your Camera/DeepFace code will go here later)
        time.sleep(0.1)"""
