import serial
import time

# =================================================================
# PHYSICAL CHANNEL CONFIGURATION
# =================================================================
MOUTH_CHANNELS = [0, 1, 2]     
EYE_CHANNELS = [3, 4]          
CURTAIN_CHANNEL = 7            
BAR_CHANNELS = [8, 9, 10, 11]  

PORT = '/dev/ttyUSB2'
#PORT = '/dev/serial/by-path/platform-3610000.xhci-usb-0:4.1:1.0-port0' # <-- Make sure this is your active port! serial/by-path/platform-3610000.xhci-usb-0:4.2.3:1.0-port0
BAUD_RATE = 115200

def face_motor_process(shared_state, shutdown_event, connection_status):
    print("[EXPRESSIVE MOTOR PROCESS] Thread Started.")
    
    ser_face = None
    last_u_values = {}  
    last_d_values = {}  

    def connect_serial():
        nonlocal ser_face
        while True:
            try:
                print(f"[EXPRESSIVE MOTOR] Connecting to ESP32 on {PORT}...")
                ser_face = serial.Serial(PORT, BAUD_RATE, timeout=0.1)
                time.sleep(2) 
                ser_face.reset_input_buffer()
                ser_face.reset_output_buffer()
                print("FACE OK")
                connection_status["FACE"] = True
                return True
            except Exception as e:
                print(f"[ERROR] Port connection failed: {e}. Retrying in 3s...")
                time.sleep(3)

    # Initial Connection
    connect_serial()

    # ---> THE NEW 2-SECOND TIMER <---
    last_sent_time = 0.0 

    while not shutdown_event.is_set():
        try:
            # 1. ALWAYS READ ESP32 LOGS (To prevent buffer overflow)
            while ser_face.in_waiting > 0:
                line = ser_face.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(f"  [ESP32] {line}")

            # 2. ONLY READ AND SEND COMMANDS IF 2 SECONDS HAVE PASSED
            if time.time() - last_sent_time >= 0.5:
                
                mouth_cmd = shared_state.get('mouth_cmd', '')
                eye_cmd = shared_state.get('eye_cmd', '')
                curtain_cmd = shared_state.get('curtain_cmd', '')
                bar_cmd = shared_state.get('bar_cmd', '')

                u_packet_parts = []
                d_commands_list = []

                # --- PARSE MOUTH (With Integer Fix) ---
                if mouth_cmd:
                    try:
                        mouth_vals = [int(float(x)) for x in mouth_cmd.replace("M:", "").split(',')]
                        for idx in range(0, len(mouth_vals) - 1, 2):
                            motor_idx = idx // 2
                            if motor_idx < len(MOUTH_CHANNELS):
                                ch = MOUTH_CHANNELS[motor_idx]
                                pos = mouth_vals[idx]
                                spd = mouth_vals[idx + 1]
                                
                                if last_u_values.get(ch) != (pos, spd):
                                    u_packet_parts.append(f"{ch},{pos},{spd}")
                                    last_u_values[ch] = (pos, spd)
                    except ValueError: pass

                # --- PARSE EYES (With Integer Fix) ---
                if eye_cmd:
                    try:
                        eye_vals = [int(float(x)) for x in eye_cmd.replace("E:", "").split(',')]
                        for idx in range(0, len(eye_vals) - 1, 2):
                            motor_idx = idx // 2
                            if motor_idx < len(EYE_CHANNELS):
                                ch = EYE_CHANNELS[motor_idx]
                                pos = eye_vals[idx]
                                spd = eye_vals[idx + 1]
                                
                                if last_u_values.get(ch) != (pos, spd):
                                    u_packet_parts.append(f"{ch},{pos},{spd}")
                                    last_u_values[ch] = (pos, spd)
                    except ValueError: pass

                # --- PARSE CURTAIN & BARS ---
                if curtain_cmd:
                    try:
                        curtain_vals = [int(float(x)) for x in curtain_cmd.replace("C:", "").split(',')]
                        if len(curtain_vals) >= 2:
                            spd, dur = curtain_vals[0], curtain_vals[1]
                            if last_d_values.get(CURTAIN_CHANNEL) != (spd, dur):
                                d_commands_list.append(f"{CURTAIN_CHANNEL},{spd},{dur}")
                                last_d_values[CURTAIN_CHANNEL] = (spd, dur)
                    except ValueError: pass

                if bar_cmd:
                    try:
                        bar_vals = [int(float(x)) for x in bar_cmd.replace("B:", "").split(',')]
                        for idx in range(0, len(bar_vals) - 1, 2):
                            motor_idx = idx // 2
                            if motor_idx < len(BAR_CHANNELS):
                                ch = BAR_CHANNELS[motor_idx]
                                spd, dur = bar_vals[idx], bar_vals[idx + 1]
                                if last_d_values.get(ch) != (spd, dur):
                                    d_commands_list.append(f"{ch},{spd},{dur}")
                                    last_d_values[ch] = (spd, dur)
                    except ValueError: pass

                # --- SEND THE PACKETS AND RESET THE 2-SECOND TIMER ---
                sent_anything = False

                if u_packet_parts:
                    u_command = "U:" + ",".join(u_packet_parts) + "\n"
                    print(f"[IRONCLAD WRITE] {u_command.strip()}")
                    ser_face.write(u_command.encode('utf-8'))
                    ser_face.flush()
                    sent_anything = True

                if d_commands_list:
                    d_command = "D:" + ",".join(d_commands_list) + "\n"
                    print(f"[IRONCLAD WRITE] {d_command.strip()}")
                    ser_face.write(d_command.encode('utf-8'))
                    ser_face.flush()
                    sent_anything = True

                # If we actually sent a command to the ESP32, restart the stopwatch!
                if sent_anything:
                    last_sent_time = time.time()

        except KeyboardInterrupt:
            print("\n[EXPRESSIVE MOTOR] Ctrl+C caught! Shutting down motor process...")
            connection_status["FACE"] = False
            shutdown_event.set()
            break
        except (serial.SerialException, OSError) as se:
            print(f"[MOTOR FAILURE] Connection lost: {se}. Reconnecting...")
            connect_serial()
        except Exception as e:
            print(f"[MOTOR LOOP ERROR] {e}")


            print("\n[EXPRESSIVE MOTOR] Ctrl+C caught! Shutting down motor process...")
            shutdown_event.set()
            break
        

    print("[FACE] Shutting down")

    time.sleep(0.05)




"""import serial
import time

# =================================================================
# PHYSICAL CHANNEL CONFIGURATION
# =================================================================
# Map your physical PCA9685 row pins here!
MOUTH_CHANNELS = [0, 1, 2]     # Row 0, Row 1, Row 2 for Mouth Positional Servos
EYE_CHANNELS = [3, 4]          # Row 3, Row 4 for Eye Positional Servos
CURTAIN_CHANNEL = 7            # Row 7 for Curtain Continuous Servo
BAR_CHANNELS = [8, 9, 10, 11]  # Rows 8, 9, 10, 11 for Bar Continuous Servos

# =================================================================
# PERMANENT PORT CONFIGURATION
# =================================================================
#PORT = 'dev/ttyUSB0'
PORT = '/dev/serial/by-path/platform-3610000.xhci-usb-0:4.2:1.0-port0'
BAUD_RATE = 115200


def face_motor_process(shared_state):

    #Acts as the Actuator Daemon for your expressive system.
    #Runs continuously, polls the blackboard, and pushes commands to the ESP32.

    print("[EXPRESSIVE MOTOR PROCESS] Thread Started.")
    
    ser = None
    last_u_values = {}  # Cache to prevent spamming positional commands: { channel: (pos, spd) }
    last_d_values = {}  # Cache to prevent spamming continuous commands: { channel: (spd, dur) }

    def connect_serial():
        nonlocal ser
        while True:
            try:
                print(f"[EXPRESSIVE MOTOR] Connecting to ESP32 on permanent port {PORT}...")
                ser = serial.Serial(PORT, BAUD_RATE, timeout=0.1)
                time.sleep(2) # Give ESP32 time to reboot
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                print("[EXPRESSIVE MOTOR] Serial connection established!")
                return True
            except Exception as e:
                print(f"[EXPRESSIVE MOTOR ERROR] Port connection failed: {e}. Retrying in 3s...")
                time.sleep(3)

    # Initial Connection
    connect_serial()
    last_sent_time = 0.0
    while True:
        try:
            # 1. READ BLACKBOARD COMMANDS FROM DECISION CENTER
            mouth_cmd = shared_state.get('mouth_cmd', '')
            eye_cmd = shared_state.get('eye_cmd', '')
            curtain_cmd = shared_state.get('curtain_cmd', '')
            bar_cmd = shared_state.get('bar_cmd', '')

            # ==========================================
            # A. PARSE & PACKAGE POSITIONAL COMMANDS (U:)
            # ==========================================
            u_packet_parts = []

            # Parse Mouth Positional (Pairs of: pos, spd_delay)
            if mouth_cmd:
                try:
                    mouth_vals = [float(x) for x in mouth_cmd.replace("M:", "").split(',')]
                    # Step by 2 to extract (position, speed_delay) for each mouth motor
                    for idx in range(0, len(mouth_vals) - 1, 2):
                        motor_idx = idx // 2
                        if motor_idx < len(MOUTH_CHANNELS):
                            ch = MOUTH_CHANNELS[motor_idx]
                            pos = mouth_vals[idx]
                            spd = int(mouth_vals[idx + 1])
                            
                            # Cache Check: Only log and add to serial packet if position or speed changed
                            if last_u_values.get(ch) != (pos, spd):
                                print(f"[MOTOR] Mouth channel {ch} position change -> pos: {pos}, speed delay: {spd}")
                                u_packet_parts.append(f"{ch},{pos},{spd}")
                                last_u_values[ch] = (pos, spd)
                except ValueError:
                    pass

            # Parse Eye Positional (Pairs of: pos, spd_delay)
            if eye_cmd:
                try:
                    eye_vals = [float(x) for x in eye_cmd.replace("E:", "").split(',')]
                    # Step by 2 to extract (position, speed_delay) for each eye motor
                    for idx in range(0, len(eye_vals) - 1, 2):
                        motor_idx = idx // 2
                        if motor_idx < len(EYE_CHANNELS):
                            ch = EYE_CHANNELS[motor_idx]
                            pos = eye_vals[idx]
                            spd = int(eye_vals[idx + 1])
                            
                            # Cache Check: Only log and add to serial packet if position or speed changed
                            if last_u_values.get(ch) != (pos, spd):
                                print(f"[MOTOR] Eye channel {ch} position change -> pos: {pos}, speed delay: {spd}")
                                u_packet_parts.append(f"{ch},{pos},{spd}")
                                last_u_values[ch] = (pos, spd)
                except ValueError:
                    pass

            # Send aggregated positional packet if changes were found
            if u_packet_parts:
                u_command = "U:" + ",".join(u_packet_parts) + "\n"
                print(f"[EXPRESSIVE MOTOR WRITE] {u_command.strip()}")
                ser.write(u_command.encode('utf-8'))
                ser.flush()

            # ==========================================
            # B. PARSE & PACKAGE CONTINUOUS COMMANDS (D:)
            # ==========================================
            d_commands_list = []

            # Parse Curtain Continuous (Pairs of: speed, duration)
            if curtain_cmd:
                try:
                    curtain_vals = [int(x) for x in curtain_cmd.replace("C:", "").split(',')]
                    if len(curtain_vals) >= 2:
                        spd = curtain_vals[0]
                        dur = curtain_vals[1]
                        
                        # Cache Check: Only log and add to serial packet if values changed
                        if last_d_values.get(CURTAIN_CHANNEL) != (spd, dur):
                            print(f"[MOTOR] Curtain channel {CURTAIN_CHANNEL} speed change -> speed: {spd}, duration: {dur}ms")
                            d_commands_list.append(f"{CURTAIN_CHANNEL},{spd},{dur}")
                            last_d_values[CURTAIN_CHANNEL] = (spd, dur)
                except ValueError:
                    pass

            # Parse Bar Continuous (Pairs of: speed, duration)
            if bar_cmd:
                try:
                    bar_vals = [int(x) for x in bar_cmd.replace("B:", "").split(',')]
                    # Step by 2 to extract (speed, duration) for each bar motor
                    for idx in range(0, len(bar_vals) - 1, 2):
                        motor_idx = idx // 2
                        if motor_idx < len(BAR_CHANNELS):
                            ch = BAR_CHANNELS[motor_idx]
                            spd = bar_vals[idx]
                            dur = bar_vals[idx + 1]
                            
                            # Cache Check: Only log and add to serial packet if values changed
                            if last_d_values.get(ch) != (spd, dur):
                                print(f"[MOTOR] Bar channel {ch} speed change -> speed: {spd}, duration: {dur}ms")
                                d_commands_list.append(f"{ch},{spd},{dur}")
                                last_d_values[ch] = (spd, dur)
                except ValueError:
                    pass

            # Send aggregated continuous packet if changes were found
            if d_commands_list:
                d_command = "D:" + ",".join(d_commands_list) + "\n"
                print(f"[EXPRESSIVE MOTOR WRITE] {d_command.strip()}")
                ser.write(d_command.encode('utf-8'))
                ser.flush()

            # 2. READ SERIAL LOGS FROM ESP32 TO PREVENT BUFFER OVERFLOW
            while ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith("LIMIT_HIT:"):
                 channel = line.split(":")[1]
                 print(f"[WARNING] Motor {channel} reached its physical limit!")
                    # Update your Shared Blackboard here so the Decision Center knows!
                 #shared_state[f'limit_{channel}'] = True
                if line:
                    print(f"  [ESP32] {line}")


        except (serial.SerialException, OSError) as se:
            print(f"[EXPRESSIVE MOTOR FAILURE] Connection lost: {se}. Reconnecting...")
            connect_serial()
        except Exception as e:
            print(f"[EXPRESSIVE MOTOR LOOP ERROR] {e}")
            
        time.sleep(0.05) 
        """ 