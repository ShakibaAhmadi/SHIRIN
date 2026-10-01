import serial
import serial.tools.list_ports
import time

""" find_esp_port(target_id):
    #cans all available serial ports looking for the matching handshake ID.
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if "USB" in p.device or "ACM" in p.device:
            try:
                # Open the port temporarily
                ser = serial.Serial(p.device, 115200, timeout=1.5)
                time.sleep(0.5) # Wait for ESP32 auto-reset wakeup
                
                # Read the first line coming out of the port
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                ser.close()
                
                # Check if it matches our target greeting
                if target_id in line:
                    print(f"[FOUND] {target_id} located on {p.device}")
                    return p.device
            except Exception:
                pass
    return None

# Automatically find the Sonar ESP dynamically
sonar_port_path = find_esp_port("ID:SONAR_ESP")

if not sonar_port_path:
    raise ConnectionError("Could not find the Sonar ESP32! Check wiring/power.")

# Open the connection using the dynamically discovered port
ser_sonar = serial.Serial(sonar_port_path, 115200, timeout=1)"""

def sonar_process(shared_state, shutdown_event, connection_status):
    print("[SONAR] Process Started.")
    shared_state['near_obstacle'] = False
    shared_state['far_obstacle'] = False
    shared_state['obstacle_detected'] = False

    shared_state['obstacle_direction'] = 'NONE'
    # 1. SETUP SERIAL (Adjust '/dev/ttyUSB0' and baud rate to match your Arduino)
    try:
        ser_sonar = serial.Serial('/dev/ttyUSB1', 115200, timeout=1)
        #ser_sonar = serial.Serial('/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0', 115200, timeout=1)
        #ser_sonar = serial.Serial('/dev/serial/by-path/platform-3610000.xhci-usb-0:4.2.4:1.0-port0', 115200, timeout=1) # "/dev/serial/by-id'/usb-1a86_USB_Serial-if00-port0"  platform-3610000.xhci-usb-0:4.2.2:1.0-port0
        ser_sonar.setDTR(False) 
        ser_sonar.setRTS(False)
        time.sleep(1) # Wait for Arduino to reboot
        ser_sonar.reset_input_buffer()
        ser_sonar.reset_output_buffer()
        #ser_sonar.open()
        print("SONAR OK")
        connection_status["SONAR"] = True
    except Exception as e:
        print(f"[SONAR ERROR] Could not open Serial: {e}")
        return # Exit if no Arduino is found

    try:
        while not shutdown_event.is_set():
            try:
                if ser_sonar.in_waiting > 0:
                # 2. READ DATA FROM ARDUINO
                #rint("start reading from arduino!!!!!!!!!!!!!!!!!!")
                    line = ser_sonar.readline().decode('utf-8', errors='ignore').strip()
                #print(f"[SONAR RAW] Received: {line}") 
                
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
                        if min_dist < 30:
                            shared_state['near_obstacle'] = True
                            shared_state['far_obstacle'] = True
                    
                    # Threshold 2: Far (Attention distance) < 200cm
                        elif min_dist < 150:
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
            
    except KeyboardInterrupt:
        print("\n[SONAR] Ctrl+C caught! Shutting down sonar process...")
        connection_status["SONAR"] = False                
    finally:
        print("[SONAR] Shutting down...")
        connection_status["SONAR"] = False
        if ser_sonar.is_open:
            ser_sonar.flush()
            ser_sonar.close()

    print("[SONAR] Port closed safely.")            # Graceful shutdown
    time.sleep(0.05) # Run at 20Hz
