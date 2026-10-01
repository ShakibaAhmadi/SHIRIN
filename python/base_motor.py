import json
import time  
import serial 
import sys # <-- ADDED THIS to allow safe exiting

def base_motor_process(shared_state, shutdown_event, connection_status):
    print("[BASE MOTOR] Process Started.")
    
    # Change this to your exact Motor Arduino port!
    PORT = "/dev/ttyUSB0"
    #PORT = "/dev/serial/by-path/platform-3610000.xhci-usb-0:4.1:1.0-port0" # "/dev/serial/by-id/usb-Arduino__www.arduino.cc__0042_559303435363517131F0-if00" # /"dev/arduino" #
    BAUD = 115200
    
    
        
    ser_base = serial.Serial(PORT, BAUD, timeout=1.0, write_timeout=1.0, rtscts=False, dsrdtr=False, xonxoff=False)
    time.sleep(1)
    ser_base.close()
    time.sleep(0.5)
    ser_base.open()
        # The Zombie-Killer Reset (Prevents Jetson serial lockups)
    ser_base.setDTR(False)
    ser_base.setRTS(False)
    time.sleep(0.5)
    ser_base.setDTR(True)
    ser_base.setRTS(True)
    time.sleep(1) # Wait for Arduino to boot
        
    ser_base.reset_input_buffer()
    ser_base.reset_output_buffer()
    
        # Send Wake-up command
    ser_base.write(b"\nSTART\n")
    ser_base.flush()
    print("BASE OK")
    connection_status["BASE"] = True
        
    

    # ==========================================
    # 1. START THE SAFETY TRY BLOCK HERE
    # ==========================================
    try:
        print("[MOTOR] Entering main loop. Press Ctrl+C to exit.")
        while not shutdown_event.is_set():
            # 1. Read the latest desired speeds from the Blackboard
            speed_x = shared_state.get('motor_cmd_x', 0.0)
            speed_y = shared_state.get('motor_cmd_y', 0.0)
            angular_speed = shared_state.get('motor_cmd_z', 0.0)

            # print(f"MOTOR SCRIPT READS: X={vx}, Y={vy}, Z={vz}")
  
            # 2. Package and send over Serial

            line = f"<BEGIN>{speed_x},{speed_y},{angular_speed}<END>"
            ser_base.write((line + "\n").encode())
            #ser_base.write(line.encode('utf-8'))
            ser_base.flush()
            
            # 3. Read and Print incoming telemetry
            while ser_base.in_waiting > 0:
                incoming = ser_base.readline().decode('utf-8', errors='ignore').strip()
                if incoming:
                    # This will print "TEL:..." and "OK START" to your Jetson terminal
                    print(f"[ARDUINO-MOTOR] {incoming}")
            
            # Send commands every 0.2 seconds (5Hz)
            time.sleep(0.2)

    # ==========================================
    # 2. CATCH THE CTRL+C AND TRIGGER EMERGENCY STOP
    # ==========================================
    except KeyboardInterrupt:
        print("\n[EMERGENCY] Ctrl+C caught! Sending STOP to base motors...")
        connection_status["BASE"] = False
        shutdown_event.set()
    finally:
        # Graceful shutdown
        if ser_base.is_open:
            ser_base.write(b"STOP\n")
            ser_base.flush()
            time.sleep(0.2) # Give it 200ms to ensure the message travels down the USB cable
            ser_base.close()
        print("[MOTOR] Motors stopped. Port closed safely.")        
        sys.exit(0) # Kills this specific background process cleanly


"""import json
import time  
import serial 

def base_motor_process(shared_state):
    print("[BASE MOTOR] Process Started.")
    
    # Change this to your exact Motor Arduino port!
    PORT = "/dev/serial/by-id/usb-Arduino__www.arduino.cc__0042_559303435363517131F0-if00"
    BAUD = 115200
    
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1.0, write_timeout=1.0, rtscts=False, dsrdtr=False, xonxoff=False)
        time.sleep(2)
        # The Zombie-Killer Reset (Prevents Jetson serial lockups)
        ser.setDTR(False)
        ser.setRTS(False)
        time.sleep(0.5)
        ser.setDTR(True)
        ser.setRTS(True)
        time.sleep(2) # Wait for Arduino to boot
        
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Send Wake-up command
        ser.write(b"\nSTART\n")
        ser.flush()
        print("[MOTOR] Connected and START command sent.")
        
    except Exception as e:
        print(f"[MOTOR ERROR] Could not open port: {e}")
        return

    while True:
        try:
            # 1. Read the latest desired speeds from the Blackboard
            vx = shared_state.get('motor_cmd_x', 0.0)
            vy = shared_state.get('motor_cmd_y', 0.0)
            vz = shared_state.get('motor_cmd_z', 0.0)

            print(f"MOTOR SCRIPT READS: X={vx}, Y={vy}, Z={vz}")
            # 2. Package and send over Serial
            #print("sending message to motors")
            msg = {
                "speed_x": vx,
                "speed_y": vy,
                "angular_speed": vz
            }
            #print("message sent")
            line = json.dumps(msg) + "\n"
            ser.write(line.encode('utf-8'))
            ser.flush()
            
            # 3. Clear any incoming telemetry to prevent buffer overflow
            # 3. Read and Print incoming telemetry
            while ser.in_waiting > 0:
                print("reading incoming telemetry")
                incoming = ser.readline().decode('utf-8', errors='ignore').strip()
                if incoming:
                    # This will print "TEL:..." and "OK START" to your Jetson terminal
                    print(f"[ARDUINO-MOTOR] {incoming}")
            
            # Send commands every 0.2 seconds (5Hz)
            time.sleep(0.2) 
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            pass

    # Graceful shutdown
    if ser.is_open:
        print("[MOTOR] Shutting down...")
        ser.write(b"STOP\n")
        ser.flush()
        time.sleep(0.5)
        ser.close()"""