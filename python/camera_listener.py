import time
import socket
import json
import sys

import cv2
# Force line-buffering so logs appear in the parent terminal immediately
sys.stdout.reconfigure(line_buffering=True)
def camera_listener_process(shared_state, shutdown_event, connection_status):
    print("====== [CAMERA SYNC] Listening for DeepFace on Port 5005 ======")
    
    UDP_IP = "10.0.0.114"
    UDP_PORT = 5005
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((UDP_IP, UDP_PORT))
    
    # Timeout is crucial! If the camera stops seeing a face for 1 second,
    # the socket times out and we assume the person left.
    sock.settimeout(10.0) 
    connection_status["CAMERA"] = True
    print("CAMERA OK")
    while not shutdown_event.is_set():
        try:
            # Listen for the message from your other Python script
            data, addr = sock.recvfrom(1024) 
            message = json.loads(data.decode('utf-8'))
            
            # Instantly update the Blackboard!
            shared_state['person_in_frame'] = message.get("person_in_frame", False)
            shared_state['person_emotion'] = message.get("person_emotion", "Neutral")
            
        except socket.timeout:
            # If 1 second passes with no messages, the person must be gone.
            # Reset the blackboard so the Brain knows to go back to PATROL.
            shared_state['person_in_frame'] = False
            shared_state['person_emotion'] = "Neutral"
            
        except Exception as e:
            print(f"[CAMERA SYNC ERROR]: {e}")
            time.sleep(0.5)

        except KeyboardInterrupt:
            print("\n[CAMERA SYNC] Ctrl+C received. Exiting...")
            
            shutdown_event.set()
            break
    connection_status["CAMERA"] = False
   