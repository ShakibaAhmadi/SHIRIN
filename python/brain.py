# complete with mood manager, logging, idle exploration, investigation,
# interaction will, session memory, and eye/camera priority control

from email.mime import message
import sys
import os
import time
import json
import random
from collections import deque
from mood_manager import MoodManager
from reaction_center import ReactionCenter

def clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))

def now_string():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def make_eye_cmd(pan_angle, tilt_angle, speed=8):
    """
    Eye/camera command format.

    Assumption based on your previous commands:
        E:pan,speed,tilt,speed

    If your ESP parser uses another format, only change this function.
    """
    pan_angle = int(round(pan_angle))
    tilt_angle = int(round(tilt_angle))
    speed = int(round(speed))

    return f"E:{pan_angle},{speed},{tilt_angle},{speed}"


def push_to_blackboard(action_dict, shared_state):
    """This is the bridge: Pushes the dictionary data to the Blackboard keys your motors watch."""
    if action_dict:
        shared_state['mouth_cmd'] = action_dict.get('mouth', '')
        shared_state['eye_cmd'] = action_dict.get('eyes', '')
        shared_state['curtain_cmd'] = action_dict.get('curtain', '')
        shared_state['bar_cmd'] = action_dict.get('bars', '')
        shared_state['robot_emotion'] = action_dict.get('target_level', 'NEUTRAL')

        print(
            f"[BRAIN] Pushed to Motors: "
            f"{shared_state['robot_emotion']}"
        )


def load_personality_traits(personality_name, personality_file="personality.json"):
    """
    Load personality values for interaction_will.

    Expected values are 0.0 to 1.0.
    If your json uses 0 to 100, this function converts it.

    Supported keys:
        extraversion / extroversion
        agreeableness
        openness
        neuroticism
        conscientiousness
    """
    defaults = {
        "extraversion": 0.60,
        "agreeableness": 0.60,
        "openness": 0.60,
        "neuroticism": 0.40,
        "conscientiousness": 0.50,
    }

    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_paths = [
        os.path.join(base_dir, personality_file),
        personality_file,
    ]

    data = None
    for path in candidate_paths:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                break
        except Exception:
            data = None

    if not isinstance(data, dict):
        return defaults

    raw_profile = None
    name_upper = str(personality_name).upper()

    # Common format: {"BUBBLY": {...}}
    for key, value in data.items():
        if str(key).upper() == name_upper and isinstance(value, dict):
            raw_profile = value
            break

    # Alternative format: direct dict of traits
    if raw_profile is None:
        raw_profile = data

    def read_trait(*names):
        for name in names:
            for key, value in raw_profile.items():
                if str(key).lower() == name.lower():
                    v = safe_float(value, None)
                    if v is None:
                        return None
                    if v > 1.0:
                        v = v / 100.0
                    return clamp(v, 0.0, 1.0)
        return None

    traits = dict(defaults)
    traits["extraversion"] = read_trait("extraversion", "extroversion") or traits["extraversion"]
    traits["agreeableness"] = read_trait("agreeableness") or traits["agreeableness"]
    traits["openness"] = read_trait("openness") or traits["openness"]
    traits["neuroticism"] = read_trait("neuroticism") or traits["neuroticism"]
    traits["conscientiousness"] = read_trait("conscientiousness") or traits["conscientiousness"]

    return traits


# =========================================================
# IDLE BEHAVIOR
# =========================================================

class IdleBehavior:
    """
    IDLE means alive exploration, not standing still.

    It produces:
        - small base exploration chunks
        - low-priority eye scanning
        - small mouth movement
        - rare sound commands

    The APF part reuses the old PATROL idea:
        exploration target + sonar repulsion + smoothing outside this class.
    """
    robot_trust_count = 0
    robot_distrust_count= 0
    

    def __init__(self):
        now = time.time()
        self.base_actions = ["VERY_SLOW_FORWARD"]
        self.base_action = "PAUSE"
        self.base_action_end_time = now

        self.next_eye_time = now + random.uniform(2.0, 5.0)
        self.next_move_time = now + random.uniform(2.0, 3.0)
        self.next_mouth_time = now + random.uniform(3.0, 6.0)
        self.next_sound_time = now + random.uniform(4.0, 5.0)
        self.speaker_reset_time = 0.0

        

        self.eye_actions = [
            (-20, 0),
            (20, 0),
            (0, 10),
            (0, -10),
            (-12, 5),
            (12, -5),
            (-40, 10),
            (40, 10),
            (0, 0),
        ]

        self.mouth_actions = [
            "M:0,10,0,10,0,10",
            "M:10,15,-10,15,5,15",
            "M:-13,15,0,15,-5,15",
            "M:-12,15,12,15,0,15",
            "M:0,15,-13,15,-5,15",
        ]

        self.sound_actions = [
            "ROBOT_BREATH",
            "ROBOT_HUM",
        ]
        #self.base_actions = ["VERY_SLOW_FORWARD"]
    
    def base_motion_from_action(self, action, base_speed):
                    
                    if action == "SLOW_ROTATE_LEFT":
                        return 0.0, 0.0, 0.2
            
                    if action == "SLOW_ROTATE_RIGHT":
                        return 0.0, 0.0, -0.01
                    
                    if action == "PAUSE":
                        return 0.0, 0.0, 0.0
                    
                    if action == "ROTATE_LEFT":
                        return 0.0, 0.0, 0.2
                   
                    if action == "ROTATE_RIGHT":
                        return 0.0, 0.0, -0.2
                   
                    if action == "SLOW_FORWARD":
                        return base_speed * 0.5, 0.0, 0.0

                    if action == "VERY_SLOW_FORWARD":
                        return base_speed * 0.3, 0.0, 0.0
               
                    if action == "ARC_LEFT":
                        return base_speed * 0.5, 0.0, 0.2
                   
                    if action == "ARC_RIGHT":
                        return base_speed * 0.5, 0.0, -0.2

                    if action == "BACKWARD":
                        return -base_speed*0.4, 0.0, 0.0
            
                    if action == "SIDE_LEFT":
                        return 0.0, base_speed * 0.5, 0.0
                   
                    if action == "SIDE_RIGHT": 
                        return 0.0, -base_speed * 0.5, 0.0

                    #defining escape speed
                    escape_speed = base_speed * 1.2
                    
                    if action == "FAST_ESCAPE_LEFT":
                        return 0.0, escape_speed, 0.01
                 
                    if action == "FAST_ESCAPE_RIGHT":
                        return 0.0, -escape_speed, -0.01
                   
                    #if action == "ESCAPE_BACKWARD":
                        #return -escape_speed * 0.7, 0.0, 0.0
                    
                    return 0.0, 0.0, 0.0
                
    def choose_base_action(self, fc, fl, fr, b, safe_dist):
                    front_clear = fc > safe_dist
                    left_clear = fl > safe_dist * 0.75
                    right_clear = fr > safe_dist * 0.75
            
                    self.base_actions = [
                        
                        "SLOW_ROTATE_LEFT",
                        "SLOW_ROTATE_RIGHT",
                        "VERY_SLOW_FORWARD",
                    ]
            
                    if front_clear:
                        self.base_actions.extend([
                            "SLOW_FORWARD",
                            "ARC_LEFT",
                            "ARC_RIGHT",
                        ])
            
                    if left_clear:
                        self.base_actions.append("SIDE_LEFT")
            
                    if right_clear:
                        self.base_actions.append("SIDE_RIGHT")
            
                    # If the front is not clear, prefer looking/turning instead of pushing forward.
                    if not front_clear:
                        if fr >= fl:
                            self.base_actions.extend(["ROTATE_RIGHT", "SIDE_RIGHT"])
                        else:
                            self.base_actions.extend(["ROTATE_LEFT", "SIDE_LEFT"])
            
                    return self.base_actions
            
        
    
    


    def apply_apf_repulsion(
        self,
        target_vx,
        target_vy,
        target_vz,
        fc,
        fl,
        fr,
        safe_dist,
        force_multiplier,
        allow_backward=False,
    ):
        """
        Reuses the old PATROL APF idea.

        The signs are kept close to the older working version to avoid
        changing your physical direction mapping unexpectedly.
        """
        
        repel_x = 0.0
        repel_y = 0.0

        if fc < safe_dist:
            repel_x -= (safe_dist - fc) * force_multiplier
            repel_y += (safe_dist - fc) * (force_multiplier * 0.8)

        if fl < safe_dist:
            repel_y += (safe_dist - fl) * force_multiplier
            target_vz -= 0.05

        if fr < safe_dist:
            repel_y -= (safe_dist - fr) * force_multiplier
            target_vz += 0.05

        target_vx += repel_x
        target_vy += repel_y

        if not allow_backward and target_vx < 0.0:
            target_vx = 0.0

        """target_vx = clamp(target_vx, -0.25, 0.25)
        target_vy = clamp(target_vy, -0.25, 0.25)
        target_vz = clamp(target_vz, -0.25, 0.25)"""

        #print(f"[IDLE] APF Repulsion Applied: vx={target_vx:.2f}, vy={target_vy:.2f}, vz={target_vz:.2f}")

        return target_vx, target_vy, target_vz

    def update(
        self,
        shared_state,
        fc,
        fl,
        fr,
        b,
        base_speed,
        safe_dist,
        force_multiplier,
    ):
        now = time.time()

        if self.speaker_reset_time > 0.0 and now >= self.speaker_reset_time:
            shared_state["speaker_cmd"] = "NONE"
            self.speaker_reset_time = 0.0

        if now >= self.base_action_end_time:
            self.base_action = self.choose_base_action(
                fc,
                fl,
                fr,
                b,
                safe_dist,
            )

            self.base_action_end_time = now + random.uniform(2.0, 3.0)

        target_vx, target_vy, target_vz = self.base_motion_from_action(
            self.base_action,
            base_speed,
        )
        print(f"[IDLE] Base Action: {self.base_action} | vx={target_vx:.2f}, vy={target_vy:.2f}, vz={target_vz:.2f}")

        target_vx, target_vy, target_vz = self.apply_apf_repulsion(
            target_vx,
            target_vy,
            target_vz,
            fc,
            fl,
            fr,
            safe_dist,
            force_multiplier,
            allow_backward=False,
        )

        idle_eye_cmd = None

        if now >= self.next_eye_time:
            pan, tilt = random.choice(self.eye_actions)
            idle_eye_cmd = make_eye_cmd(pan, tilt, speed=8)
            self.next_eye_time = now + random.uniform(2.0, 5.0)

        if now >= self.next_mouth_time:
            shared_state["mouth_cmd"] = random.choice(self.mouth_actions)
            self.next_mouth_time = now + random.uniform(3.0, 6.0)

        if now >= self.next_sound_time:
            shared_state["speaker_cmd"] = random.choice(self.sound_actions)
            self.speaker_reset_time = now + 1
            self.next_sound_time = now + random.uniform(4.0, 10.0)
        #jadid
        if now>= self.next_move_time: 
            self.base_action = random.choice(self.base_actions)
            if self.base_action == "SIDE_LEFT" or self.base_action == "SIDE_RIGHT":
                self.base_action_end_time = now + random.uniform(0.5, 1.5)
            self.next_move_time = now + random.uniform(3.0, 5.0)

        #print(f"[IDLE] Final Velocities: vx={target_vx:.2f}, vy={target_vy:.2f}, vz={target_vz:.2f}")
        return target_vx, target_vy, target_vz, idle_eye_cmd


# =========================================================
# MAIN BRAIN PROCESS
# =========================================================

def brain_process(shared_state, personality_name="BUBBLY", initial_mood='HAPPY', shutdown_event=None):
    print("====== [MASTER BRAIN] ONLINE ======")
    def write_runtime_log(message):
        timestamp = now_string()

        with open(
            log_file_path,
            "a",
            encoding="utf-8"
        ) as log_file:
            log_file.write(
                f"[{timestamp}] {message}\n"
            )

    base_dir = os.path.dirname(os.path.abspath(__file__))

    log_file_path = os.path.join(
        base_dir,
        "robot_runtime_log.txt"
    )

    event_memory_path = os.path.join(
        base_dir,
        "session_events.jsonl"
    )

    memory_state_path = os.path.join(
        base_dir,
        "memory_state.json"
    )
    
    with open(
        log_file_path,
        "w",
        encoding="utf-8"
    ) as log_file:
        log_file.write(
            "ROBOT RUNTIME LOG\n"
            "=================\n"
        )
    
    # Session event memory resets every run.
    with open(
        event_memory_path,
        "w",
        encoding="utf-8"
    ) as event_file:
        event_file.write("")


    def write_event_memory(event_type, data=None):
        if data is None:
            data = {}

        event = {
            "time": now_string(),
            "type": event_type,
            **data,
        }

        try:
            with open(
                event_memory_path,
                "a",
                encoding="utf-8"
            ) as event_file:
                event_file.write(
                    json.dumps(event, ensure_ascii=False)
                    + "\n"
                )
        except Exception as e:
            print(f"[MEMORY ERROR] Could not write event: {e}")

    def format_log_value(value):
        try:
            return f"{float(value):.1f}"
        except (TypeError, ValueError):
            return str(value)

    print(
        f"[BRAIN LOG] Writing runtime log to: "
        f"{log_file_path}"
    )

    write_runtime_log(
        f"START | personality={personality_name}"
    )

    write_event_memory(
        "SESSION_STARTED",
        {
            "personality": personality_name,
        }
    )

    if initial_mood is None:
        initial_mood = {
            "valence": 0.0,
            "arousal": 0.0,
            "dominance": 0.0
        }

    mood_manager = MoodManager(
        personality_name=personality_name,
        initial_mood=initial_mood,
        personality_file="personality.json"
    )

    reactions = ReactionCenter(
        personality=personality_name
    )

    personality_traits = load_personality_traits(
        personality_name=personality_name,
        personality_file="personality.json"
    )

    extraversion = personality_traits["extraversion"]
    agreeableness = personality_traits["agreeableness"]
    openness = personality_traits["openness"]
    neuroticism = personality_traits["neuroticism"]
    conscientiousness = personality_traits["conscientiousness"]

    write_runtime_log(
        "PERSONALITY_TRAITS | "
        f"E={extraversion:.2f} | "
        f"A={agreeableness:.2f} | "
        f"O={openness:.2f} | "
        f"N={neuroticism:.2f} | "
        f"C={conscientiousness:.2f}"
    )

    # =====================================================
    # COMPACT MEMORY STATE
    # =====================================================
    relationship_memory = 0.0
    last_interaction_time = time.time()
    total_interactions = 0
    positive_interactions = 0
    negative_interactions = 0
    social_fatigue = 0.0
    last_escape_time = 0.0
    HAPPY_COUNTER = 2
    ANGRY_COUNTER = 0
    try:
        if os.path.exists(memory_state_path):
            with open(memory_state_path, "r", encoding="utf-8") as f:
                memory_state = json.load(f)

            relationship_memory = safe_float(
                memory_state.get("relationship_memory"),
                0.0,
            )

            last_interaction_time = safe_float(
                memory_state.get("last_interaction_time"),
                time.time(),
            )

            total_interactions = int(
                safe_float(memory_state.get("total_interactions"), 0)
            )

            positive_interactions = int(
                safe_float(memory_state.get("positive_interactions"), 0)
            )

            negative_interactions = int(
                safe_float(memory_state.get("negative_interactions"), 0)
            )

            social_fatigue = safe_float(
                memory_state.get("social_fatigue"),
                0.0,
            )

            last_escape_time = safe_float(
                memory_state.get("last_escape_time"),
                0.0,
            )

    except Exception as e:
        print(f"[MEMORY WARNING] Could not load memory_state.json: {e}")

    def save_memory_state():
        memory_state = {
            "relationship_memory": relationship_memory,
            "last_interaction_time": last_interaction_time,
            "total_interactions": total_interactions,
            "positive_interactions": positive_interactions,
            "negative_interactions": negative_interactions,
            "social_fatigue": social_fatigue,
            "last_escape_time": last_escape_time,
        }

        try:
            with open(memory_state_path, "w", encoding="utf-8") as f:
                json.dump(
                    memory_state,
                    f,
                    indent=4,
                    ensure_ascii=False,
                )
        except Exception as e:
            print(f"[MEMORY ERROR] Could not save memory_state.json: {e}")

    def update_relationship_memory(delta, reason):
        nonlocal relationship_memory

        old_value = relationship_memory
        relationship_memory = clamp(
            relationship_memory + delta,
            -1.0,
            1.0,
        )

        if abs(relationship_memory - old_value) >= 0.02:
            write_event_memory(
                "RELATIONSHIP_MEMORY_UPDATED",
                {
                    "reason": reason,
                    "delta": round(delta, 3),
                    "relationship_memory": round(relationship_memory, 3),
                }
            )

            save_memory_state()

    # =====================================================
    # STATE TRACKING VARIABLES
    # =====================================================
    last_action_time = 0.0
    ACTION_COOLDOWN = 3.0
    approach_start_time = 0.0
    last_dist = 400.0
    happy_history = 0
    angry_history = 0

    # Navigation Tuning
    BASE_SPEED = 0.7
    IDLE_BASE_SPEED = 0.8
    APPROACH_SPEED = 0.6
    safe_dist = 60.0
    NEAR_DIST = 30.0
    FORCE_MULTIPLIER = 0.005
    TURN_SPEED = 0.2
    SMOOTHING_FACTOR = 0.0

    smooth_vx, smooth_vy, smooth_vz = 0.0, 0.0, 0.0

    stop_timer = 0.0
    investigate_timer = 0.0
    turn_timer = 0.0
    escape_timer = 0.0

    recently_investigated = False
    recently_investigated_back = False

    # Interaction will thresholds
    START_INTERACTION_THRESHOLD = 0.55
    STOP_INTERACTION_THRESHOLD = 0.35
    REENGAGE_COOLDOWN = 1.0
    reengage_block_until = 0.0

    interaction_will = 0.5
    last_logged_interaction_will = 0.6
    last_interaction_will_zone = "MID"

    # Interaction ending criteria
    PERSON_LOST_TIMEOUT = 5.0
    FACE_LOST_DURING_INTERACTION_TIMEOUT = 4.0
    INTERACTION_IDLE_TIMEOUT = 20.0
    TRACKING_FAILED_TIMEOUT = 10.0
    MOVING_AWAY_TIMEOUT = 10.0
    MAX_FRAME_LOSS_COUNT = 20
    MAX_INTERACTION_DISTANCE = 180.0

    interaction_start_time = 0.0
    last_person_seen_time = time.time()
    last_face_seen_time = time.time()
    person_lost_start_time = 0.0
    face_lost_start_time = 0.0
    tracking_failure_start_time = 0.0
    moving_away_start_time = 0.0
    last_meaningful_interaction_event_time = time.time()
    person_lost_count = 0
    negative_human_reaction_count = 0
    interaction_positive_events = 0
    interaction_negative_events = 0
    interaction_robot_reactions = []
    closest_interaction_distance = 400.0

    # Eye/camera control
    PAN_RIGHT = -90.0
    PAN_FRONT = 0.0
    PAN_LEFT = 90.0
    PAN_MIN = -90.0
    PAN_MAX = 90.0
    TILT_MIN = -90.0
    TILT_MAX = 20.0
    CAMERA_STEP_INTERVAL = 0.05
    CAMERA_STEP_SIZE = 5.0
    TRACKING_STEP = 2.0
    CENTER_TOLERANCE = 0.10
    FACE_CONFIRM_TIME = 0.7
    CAMERA_SETTLE_TIME = 0.5
    INVESTIGATE_TIMEOUT = 15

    camera_pan_angle = 0.0
    camera_tilt_angle = 0.0
    camera_target_pan = 0.0
    camera_target_tilt = 0.0
    scan_min_angle = -90.0
    scan_max_angle = 90.0
    scan_direction = 1
    last_camera_step_time = 0.0
    face_centered_start_time = 0.0
    face_seen_start_time = 0.0
    investigate_phase = "IDLE"
    investigate_direction = "FRONT"
    anticipation_stage = 0
    anticipation_start_time = 0

    idle_behavior = IdleBehavior()

    emo_map = {
        "HAPPY": "HAPPY",
        "SAD": "SAD",
        "ANGRY": "FEAR",
        "ANGRY2": "ANGER",
        "FEAR": "SAD",
        "DISGUST": "DISGUST",
        "SURPRISE": "CAUTIOUS",
        "SURPRISE2": "SURPRISE",
        "HAPPY2": "TRUST",
        "ANGRY3": "DISTRUST",
    }
    REENGAGE_COOLDOWN = clamp(REENGAGE_COOLDOWN+ extraversion * 2.0 + agreeableness * 1.5, 0.0, 2.0)
    # Current discrete expression sent to ReactionCenter.
    # None makes the robot send the initial neutral posture once at startup.
    last_written_emotion = None

    # Emotion selected by your existing state machine.
    target_emotion = "NEUTRAL"

    # Prevent one state from restarting the same emotion on every
    # 0.1-second brain iteration.
    last_triggered_emotion = None
    last_triggered_time = 0.0

    # Camera emotions are treated as one-time events.
    CAMERA_NEUTRAL_VALUES = {
        "NEUTRAL",
        "NONE",
        ""
    }

    last_processed_camera_emotion = "NEUTRAL"
    camera_emotion_armed = True
    last_camera_emotion_for_memory = "NEUTRAL"

    # Used for continuous emotion decay.
    last_mood_update_time = time.time()

    # Controls the once-per-second camera and sonar log.
    last_sensor_log_time = 0.0

    # Obstacle zone memory for event memory, not long-term obstacle memory.
    last_obstacle_zone = "CLEAR"

    # Make the default state IDLE if main.py did not set it.
    if 'current_state' not in shared_state:
        shared_state['current_state'] = 'IDLE'

    # =====================================================
    # NESTED STATE / DECISION HELPERS
    # =====================================================

    def set_state(new_state, reason=""):
        old_state = shared_state.get('current_state', 'IDLE')

        if old_state != new_state:
            write_runtime_log(
                f"STATE_CHANGE | {old_state} -> {new_state} | reason={reason}"
            )

            write_event_memory(
                "STATE_CHANGED",
                {
                    "from": old_state,
                    "to": new_state,
                    "reason": reason,
                }
            )

        shared_state['current_state'] = new_state

    def get_front_distance(fc, fl, fr):
        return min(fc, fl, fr)

    def get_obstacle_zone(fc, fl, fr, b, near, far):
        front_dist = min(fc, fl, fr)

        if near or front_dist < NEAR_DIST:
            return "NEAR_OBSTACLE"

        if far or front_dist < safe_dist or b < safe_dist:
            return "FAR_OBJECT"

        return "CLEAR"

    def get_investigation_direction(fc, fl, fr, b, explicit_direction=None):
        if explicit_direction:
            explicit_direction = str(explicit_direction).upper()

            if explicit_direction in ["FRONT", "FRONT_CENTER", "CENTER"]:
                return "FRONT"

            if explicit_direction in ["LEFT", "FRONT_LEFT"]:
                return "LEFT"

            if explicit_direction in ["RIGHT", "FRONT_RIGHT"]:
                return "RIGHT"

            if explicit_direction == "BACK":
                return "BACK"

        distances = {
            "FRONT": fc,
            "LEFT": fl,
            "RIGHT": fr,
            "BACK": b,
        }

        return min(distances, key=distances.get)

    def get_direction_for_camera_scan(direction):
        if direction == "RIGHT":
            return PAN_RIGHT, -90.0, -30.0

        if direction == "LEFT":
            return PAN_LEFT, 90.0,-30.0

        if direction == "BACK":
            # The camera cannot see behind without turning the body.
            # We point front and let TURN_AROUND / body motion handle it.
            #jadid
            set_state("TURN_AROUND", "investigate_back")
            return PAN_FRONT, 0.0, 20.0
            
        return PAN_FRONT, 0.0, 20.0

    def start_investigation(direction, reason=""):
        nonlocal investigate_timer
        nonlocal investigate_phase
        nonlocal investigate_direction
        nonlocal camera_target_pan
        nonlocal scan_min_angle
        nonlocal scan_max_angle
        nonlocal scan_direction
        nonlocal face_centered_start_time
        nonlocal face_seen_start_time

        investigate_direction = direction
        investigate_timer = time.time()
        investigate_phase = "POINT_CAMERA"
        face_centered_start_time = 0.0
        face_seen_start_time = 0.0

        camera_target_pan, scan_min_angle, scan_max_angle = get_direction_for_camera_scan(
            direction
        )

        scan_direction = 1

        shared_state["investigation_active"] = True
        shared_state["investigation_direction"] = direction
        shared_state["investigation_result"] = "UNKNOWN"
        shared_state["confirmed_human"] = False
        shared_state["confirmed_human_direction"] = "NONE"

        set_state("INVESTIGATE", reason)
        
        
        write_runtime_log(
            f"INVESTIGATION_STARTED | direction={direction} | reason={reason}"
        )

        write_event_memory(
            "INVESTIGATION_STARTED",
            {
                "direction": direction,
                "reason": reason,
            }
        )

    def finish_investigation_as_obstacle(reason="no_person_confirmed"):
        shared_state["investigation_active"] = False
        shared_state["investigation_result"] = "OBSTACLE"
        shared_state["confirmed_human"] = False
        shared_state["confirmed_human_direction"] = "NONE"

        write_runtime_log(
            f"INVESTIGATION_FINISHED | result=OBSTACLE | reason={reason}"
        )

        write_event_memory(
            "INVESTIGATION_FINISHED",
            {
                "result": "OBSTACLE",
                "reason": reason,
                "direction": investigate_direction,
            }
        )

    def finish_investigation_as_person(distance_cm, interaction_will_value):
        shared_state["investigation_active"] = False
        shared_state["investigation_result"] = "PERSON"
        shared_state["confirmed_human"] = True
        shared_state["confirmed_human_direction"] = investigate_direction
        shared_state["confirmed_human_distance"] = distance_cm

        write_runtime_log(
            "INVESTIGATION_FINISHED | "
            f"result=PERSON | direction={investigate_direction} | "
            f"distance={distance_cm:.1f} | will={interaction_will_value:.2f}"
        )

        write_event_memory(
            "INVESTIGATION_FINISHED",
            {
                "result": "PERSON",
                "direction": investigate_direction,
                "distance_cm": round(distance_cm, 1),
                "interaction_will": round(interaction_will_value, 3),
            }
        )

    def start_interaction(reason=""):
        nonlocal interaction_start_time
        nonlocal last_meaningful_interaction_event_time
        nonlocal last_person_seen_time
        nonlocal last_face_seen_time
        nonlocal person_lost_start_time
        nonlocal face_lost_start_time
        nonlocal tracking_failure_start_time
        nonlocal moving_away_start_time
        nonlocal person_lost_count
        nonlocal negative_human_reaction_count
        nonlocal interaction_positive_events
        nonlocal interaction_negative_events
        nonlocal interaction_robot_reactions
        nonlocal closest_interaction_distance

        now = time.time()
        interaction_start_time = now
        last_meaningful_interaction_event_time = now
        last_person_seen_time = now
        last_face_seen_time = now
        person_lost_start_time = 0.0
        face_lost_start_time = 0.0
        tracking_failure_start_time = 0.0
        moving_away_start_time = 0.0
        person_lost_count = 0
        negative_human_reaction_count = 0
        interaction_positive_events = 0
        interaction_negative_events = 0
        interaction_robot_reactions = []
        closest_interaction_distance = 400.0

        shared_state["interaction_active"] = True
        shared_state["interaction_end_reason"] = "NONE"

        set_state("INTERACT", reason)

        write_event_memory(
            "INTERACTION_STARTED",
            {
                "reason": reason,
                "interaction_will": round(interaction_will, 3),
                "relationship_memory": round(relationship_memory, 3),
            }
        )

    def end_interaction(reason, next_state):
        nonlocal last_interaction_time
        nonlocal total_interactions
        nonlocal positive_interactions
        nonlocal negative_interactions
        nonlocal social_fatigue
        nonlocal reengage_block_until
        nonlocal last_escape_time

        now = time.time()
        duration = 0.0

        if interaction_start_time > 0.0:
            duration = now - interaction_start_time

        total_interactions += 1
        last_interaction_time = now

        if interaction_positive_events >= interaction_negative_events:
            positive_interactions += 1
            if reason in ["PERSON_LOST", "HUMAN_DISENGAGED", "NO_MEANINGFUL_EVENT", "PERSON_MOVED_AWAY"]:
                update_relationship_memory(0.1, f"interaction_ended_{reason}")
        else:
            negative_interactions += 1
            update_relationship_memory(-0.15, f"interaction_ended_{reason}")

        if next_state == "ESCAPE":
            reengage_block_until = now + REENGAGE_COOLDOWN
            last_escape_time = now
            update_relationship_memory(-0.2, f"escape_after_{reason}")

        # Social fatigue rises with long or intense interactions.
        social_fatigue = clamp(
            social_fatigue + min(0.20, duration / 300.0),
            0.0,
            1.0,
        )

        shared_state["interaction_active"] = False
        shared_state["interaction_end_reason"] = reason

        write_runtime_log(
            "INTERACTION_ENDED | "
            f"reason={reason} | next_state={next_state} | "
            f"duration={duration:.1f} | "
            f"positive_events={interaction_positive_events} | "
            f"negative_events={interaction_negative_events} | "
            f"will={interaction_will:.2f}"
        )

        write_event_memory(
            "INTERACTION_ENDED",
            {
                "reason": reason,
                "next_state": next_state,
                "duration": round(duration, 1),
                "positive_events": interaction_positive_events,
                "negative_events": interaction_negative_events,
                "robot_reactions": interaction_robot_reactions,
                "interaction_will": round(interaction_will, 3),
                "relationship_memory": round(relationship_memory, 3),
            }
        )

        save_memory_state()
        set_state(next_state, reason)

    def calculate_interaction_will(
        mood_status,
        person_in_frame,
        cam_emotion,
        fc,
        fl,
        fr,
        near,
    ):
        now = time.time()

        valence = safe_float(mood_status.get("mood_valence"), 0.0)
        arousal = safe_float(mood_status.get("mood_arousal"), 0.0)
        dominance = safe_float(mood_status.get("mood_dominance"), 0.0)

        # Personality baseline.
        will_value = (
            0.20
            + 0.25 * extraversion
            + 0.10 * agreeableness
            + 0.08 * openness
            - 0.12 * neuroticism
        )

        # Mood component: positive confident mood increases will;
        # negative/high-arousal mood lowers will.
        if valence >= 0.0:
            mood_component = (
                0.18 * valence
                + 0.06 * arousal
                + 0.08 * dominance
            )
        else:
            mood_component = (
                0.22 * valence
                - 0.08 * max(arousal, 0.0)
                + 0.08 * dominance
            )

        will_value += mood_component

        # Short-term relationship/session memory.
        will_value += 0.35 * relationship_memory

        # Time without interaction = social need.
        time_without_interaction = max(
            0.0,
            now - last_interaction_time,
        )

        social_need = min(
            1.0,
            time_without_interaction / 120.0,
        )

        social_need_component = (
            0.05
            + 0.20 * extraversion
        ) * social_need

        will_value += social_need_component

        # Distance component with optimal distance.
        front_distance = get_front_distance(fc, fl, fr)
        preferred_distance = (
            75.0
            + 35.0 * (1.0 - extraversion)
            + 25.0 * neuroticism
        )

        if front_distance < 300.0:
            distance_error = abs(front_distance - preferred_distance)
            distance_component = max(
                0.0,
                0.22 * (1.0 - distance_error / 140.0)
            )
        else:
            # Camera-only person: still interesting, but weaker.
            distance_component = 0.08 if person_in_frame else 0.0

        will_value += distance_component

        # Human emotion as social information.
        human_emotion_component = 0.0

        if cam_emotion == "HAPPY":
            human_emotion_component = (
                0.10
                + 0.15 * extraversion
                + 0.10 * agreeableness
            )

        elif cam_emotion == "SAD":
            human_emotion_component = (
                0.05
                + 0.12 * agreeableness
            )

        elif cam_emotion in ["ANGRY", "DISGUST"]:
            human_emotion_component = (
                -0.15
                - 0.20 * neuroticism
            )

        elif cam_emotion == "FEAR":
            human_emotion_component = (
                -0.08
                - 0.12 * neuroticism
            )

        elif cam_emotion == "NEUTRAL":
            human_emotion_component = 0.02

        will_value += human_emotion_component

        # Safety / personal-space penalty.
        safety_penalty = 0.0

        if near or front_distance < 35.0:
            safety_penalty = 0.60
        elif front_distance < 50.0:
            safety_penalty = 0.30

        will_value -= safety_penalty

        # Re-engagement cooldown after an avoidance/escape
        #reengage_block_until = now + REENGAGE_COOLDOWN
        if now < reengage_block_until:
            will_value -= 0.40

        # Social fatigue lowers the will slowly.
        will_value -= 0.25 * social_fatigue

        return clamp(will_value, 0.0, 1.0)

    def smooth_interaction_will(target_will):
        nonlocal interaction_will

        update_rate = (
            0.04
            + 0.08 * extraversion
            + 0.05 * neuroticism
        )

        update_rate *= (
            1.0
            - 0.4 * conscientiousness
        )

        update_rate = clamp(update_rate, 0.03, 0.18)

        interaction_will += (
            target_will
            - interaction_will
        ) * update_rate

        interaction_will = clamp(interaction_will, 0.0, 1.0)

    def log_interaction_will_if_needed(target_will):
        nonlocal last_logged_interaction_will
        nonlocal last_interaction_will_zone

        if interaction_will >= START_INTERACTION_THRESHOLD:
            zone = "HIGH"
        elif interaction_will <= STOP_INTERACTION_THRESHOLD:
            zone = "LOW"
        else:
            zone = "MID"

        if zone != last_interaction_will_zone:
            write_event_memory(
                "INTERACTION_WILL_ZONE_CHANGED",
                {
                    "from": last_interaction_will_zone,
                    "to": zone,
                    "interaction_will": round(interaction_will, 3),
                    "target_interaction_will": round(target_will, 3),
                }
            )

            write_runtime_log(
                "INTERACTION_WILL_ZONE_CHANGED | "
                f"{last_interaction_will_zone} -> {zone} | "
                f"will={interaction_will:.2f} | target={target_will:.2f}"
            )

            last_interaction_will_zone = zone
            last_logged_interaction_will = interaction_will

        elif abs(interaction_will - last_logged_interaction_will) >= 0.15:
            write_event_memory(
                "INTERACTION_WILL_CHANGED",
                {
                    "interaction_will": round(interaction_will, 3),
                    "target_interaction_will": round(target_will, 3),
                }
            )

            last_logged_interaction_will = interaction_will

    def move_camera_toward_target(now):
        nonlocal camera_pan_angle
        nonlocal camera_tilt_angle
        nonlocal last_camera_step_time

        if now - last_camera_step_time < CAMERA_STEP_INTERVAL:
            return make_eye_cmd(camera_pan_angle, camera_tilt_angle, speed=8)

        pan_error = camera_target_pan - camera_pan_angle
        tilt_error = camera_target_tilt - camera_tilt_angle

        if abs(pan_error) <= CAMERA_STEP_SIZE:
            camera_pan_angle = camera_target_pan
        else:
            camera_pan_angle += CAMERA_STEP_SIZE if pan_error > 0.0 else -CAMERA_STEP_SIZE

        if abs(tilt_error) <= CAMERA_STEP_SIZE:
            camera_tilt_angle = camera_target_tilt
        else:
            camera_tilt_angle += CAMERA_STEP_SIZE if tilt_error > 0.0 else -CAMERA_STEP_SIZE

        camera_pan_angle = clamp(camera_pan_angle, PAN_MIN, PAN_MAX)
        camera_tilt_angle = clamp(camera_tilt_angle, TILT_MIN, TILT_MAX)
        last_camera_step_time = now

        return make_eye_cmd(camera_pan_angle, camera_tilt_angle, speed=8)

    def scan_camera(now):
        nonlocal camera_pan_angle
        nonlocal scan_direction
        nonlocal last_camera_step_time

        if now - last_camera_step_time >= CAMERA_STEP_INTERVAL:
            camera_pan_angle += CAMERA_STEP_SIZE * scan_direction

            if camera_pan_angle >= scan_max_angle:
                camera_pan_angle = scan_max_angle
                scan_direction = -1

            elif camera_pan_angle <= scan_min_angle:
                camera_pan_angle = scan_min_angle
                scan_direction = 1

            camera_pan_angle = clamp(camera_pan_angle, PAN_MIN, PAN_MAX)
            last_camera_step_time = now

        return make_eye_cmd(camera_pan_angle, camera_tilt_angle, speed=8)

    def update_face_tracking(now, face_x, face_y, face_in_frame):
        nonlocal camera_pan_angle
        nonlocal camera_tilt_angle
        nonlocal last_camera_step_time
        nonlocal face_centered_start_time

        if not face_in_frame:
            face_centered_start_time = 0.0
            return make_eye_cmd(camera_pan_angle, camera_tilt_angle, speed=8), False

        face_x = clamp(safe_float(face_x, 0.5), 0.0, 1.0)
        face_y = clamp(safe_float(face_y, 0.5), 0.0, 1.0)

        x_error = face_x - 0.5
        y_error = face_y - 0.5

        centered = (
            abs(x_error) <= CENTER_TOLERANCE
            and abs(y_error) <= CENTER_TOLERANCE
        )

        if centered:
            if face_centered_start_time == 0.0:
                face_centered_start_time = now
        else:
            face_centered_start_time = 0.0

        if now - last_camera_step_time >= CAMERA_STEP_INTERVAL:
            # If signs are reversed physically, swap these + and - signs.
            if x_error > CENTER_TOLERANCE:
                camera_pan_angle -= TRACKING_STEP
            elif x_error < -CENTER_TOLERANCE:
                camera_pan_angle += TRACKING_STEP

            if y_error > CENTER_TOLERANCE:
                camera_tilt_angle -= TRACKING_STEP
            elif y_error < -CENTER_TOLERANCE:
                camera_tilt_angle += TRACKING_STEP

            camera_pan_angle = clamp(camera_pan_angle, PAN_MIN, PAN_MAX)
            camera_tilt_angle = clamp(camera_tilt_angle, TILT_MIN, TILT_MAX)
            last_camera_step_time = now

        return make_eye_cmd(camera_pan_angle, camera_tilt_angle, speed=8), centered

    def reacquire_face_scan(now):
        nonlocal camera_pan_angle
        nonlocal scan_direction
        nonlocal scan_min_angle
        nonlocal scan_max_angle

        # Small scan around the last known pan position.
        center = camera_pan_angle
        scan_min_angle = clamp(center - 15.0, PAN_MIN, PAN_MAX)
        scan_max_angle = clamp(center + 15.0, PAN_MIN, PAN_MAX)

        if scan_min_angle == scan_max_angle:
            scan_min_angle = clamp(center - 10.0, PAN_MIN, PAN_MAX)
            scan_max_angle = clamp(center + 10.0, PAN_MIN, PAN_MAX)

        return scan_camera(now)

    def calculate_escape_action(fc, fl, fr, b, near):

    # 1. If the front is safe, we are done escaping.
        if fc > safe_dist and near is False:
            return "PATH_CLEAR", 0.0
            #eturn "SLOW_FORWARD", 0.0  #in case we want to go forwrd after escape

    # Calculate severity based on how close the front obstacle is
        min_front_dist = min(fc, fl, fr)
        #severity = clamp(1.0 - (min_front_dist / 40.0), 0.5, 1.0) if min_front_dist < 40.0 else 0.5
        
        
    # 2. Check sides for an immediate strafe escape
        if fr >= fl and fr > 40.0:
            return "FAST_ESCAPE_RIGHT"

        elif fl > fr and fl > 40.0:
            return "FAST_ESCAPE_LEFT"

    # 3. Check the back! If the back has room, spin around to face it.
        elif b > 40.0:
            return "TURN_AROUND"

    # 4. Boxed in completely (Front, Left, Right, AND Back are blocked)
        

    # =====================================================
    # MAIN LOOP
    # =====================================================
    while not shutdown_event.is_set():
        try:
            # =====================================================
            # CONTINUOUS TIME UPDATE
            # =====================================================
            loop_now = time.time()

            delta_time = (
                loop_now
                - last_mood_update_time
            )

            last_mood_update_time = loop_now

            # =====================================================
            # 1. READ SENSORS / BLACKBOARD
            # =====================================================
            state = shared_state.get(
                'current_state',
                'IDLE'
            )

            # Deprecated old state. Keep this alias so old code does not crash.
            if state == 'PATROL':
                set_state('IDLE', 'deprecated_patrol_redirect')
                state = 'IDLE'

            fc = safe_float(
                shared_state.get(
                    'sonar_front_center',
                    400.0
                ),
                400.0,
            )

            fl = safe_float(
                shared_state.get(
                    'sonar_front_left',
                    400.0
                ),
                400.0,
            )

            fr = safe_float(
                shared_state.get(
                    'sonar_front_right',
                    400.0
                ),
                400.0,
            )

            b = safe_float(
                shared_state.get(
                    'sonar_back',
                    400.0
                ),
                400.0,
            )

            near = shared_state.get(
                'near_obstacle',
                False
            )

            far = shared_state.get(
                'far_obstacle',
                False
            )

            obstacle_direction = shared_state.get(
                'obstacle_direction',
                ''
            )

            person_in_frame = shared_state.get(
                'person_in_frame',
                False
            )

            # If camera.py does not yet provide face_in_frame, use person_in_frame as fallback.
            face_in_frame = shared_state.get(
                'face_in_frame',
                person_in_frame
            )

            face_center_x_norm = shared_state.get(
                'face_center_x_norm',
                0.5
            )

            face_center_y_norm = shared_state.get(
                'face_center_y_norm',
                0.5
            )

            cam_emotion = str(
                shared_state.get(
                    'person_emotion',
                    'NEUTRAL'
                )
            ).upper()

            # Rearm camera emotion detection after neutral/no face.
            if (
                not person_in_frame
                or cam_emotion in CAMERA_NEUTRAL_VALUES
            ):
                camera_emotion_armed = True

            sound_detected = shared_state.get('sound_detected',False)

            is_speaking = shared_state.get('is_speaking', False)
            
            front_distance = get_front_distance(fc, fl, fr)
            closest_dist = min(fc, fl, fr, b)

            # =====================================================
            # EVENT MEMORY FOR CAMERA / OBSTACLE ZONE CHANGES
            # =====================================================
            if cam_emotion != last_camera_emotion_for_memory:
                write_event_memory(
                    "CAMERA_EMOTION_CHANGED",
                    {
                        "from": last_camera_emotion_for_memory,
                        "to": cam_emotion,
                        "person_in_frame": bool(person_in_frame),
                    }
                )

                last_camera_emotion_for_memory = cam_emotion

            current_obstacle_zone = get_obstacle_zone(
                fc,
                fl,
                fr,
                b,
                near,
                far,
            )

            if current_obstacle_zone != last_obstacle_zone:
                write_event_memory(
                    "OBSTACLE_ZONE_CHANGED",
                    {
                        "from": last_obstacle_zone,
                        "to": current_obstacle_zone,
                        "front_left": round(fl, 1),
                        "front_center": round(fc, 1),
                        "front_right": round(fr, 1),
                        "back": round(b, 1),
                    }
                )

                last_obstacle_zone = current_obstacle_zone

            # Log camera and sonar results once every second.
            if (
                loop_now
                - last_sensor_log_time
                >= 1.0
            ):
                write_runtime_log(
                    "CAMERA | "
                    f"person_in_frame={person_in_frame} | "
                    f"face_in_frame={face_in_frame} | "
                    f"emotion={cam_emotion} | "
                    f"face_x={face_center_x_norm} | "
                    f"face_y={face_center_y_norm}"
                )

                write_runtime_log(
                    "SONAR | "
                    f"front_left={format_log_value(fl)} cm | "
                    f"front_center={format_log_value(fc)} cm | "
                    f"front_right={format_log_value(fr)} cm | "
                    f"back={format_log_value(b)} cm | "
                    f"near={near} | "
                    f"far={far}"
                )

                last_sensor_log_time = loop_now

            """target_vx = 0.0
            target_vy = 0.0
            target_vz = 0.0"""
            attention_eye_cmd = None

            # Begin each loop without a new emotional event.
            target_emotion = "NEUTRAL"

            # Mood returns weakly toward initial mood only when
            # there is no person in frame for a prolonged period.
            mood_manager.update(
                delta_time,
                inactive=(
                    not person_in_frame
                )
            )

            mood_status = mood_manager.get_status()
            current_arousal = mood_status['mood_arousal']
            # --- TOP OF THE LOOP ---
        
        # 1. Map the -1.0 to 1.0 range directly into a 0.0 to 1.0 range
        # Example: Arousal -1.0 -> Multiplier 0.0
        # Example: Arousal  0.0 -> Multiplier 0.5
        # Example: Arousal  1.0 -> Multiplier 1.0
            speed_multiplier = (current_arousal + 1.0) / 2.0
        
        # 2. Safety Clamp (Highly Recommended!)
        # We clamp the bottom at 0.2 instead of 0.0. 
        # If it reaches true 0.0, a "sad" robot will completely freeze and look broken.
        # 0.2 ensures it still creeps along slowly to show life.
            speed_multiplier = clamp(speed_multiplier, 0.2, 1.0)
    # 3. Map Arousal to a Speed Multiplier
    # If Arousal is -1.0 (Very Sad/Tired), multiplier becomes 0.5 (Half speed)
    # If Arousal is 0.0 (Neutral), multiplier becomes 1.0 (Normal speed)
    # If Arousal is 1.0 (Angry/Excited), multiplier becomes 1.5 (Fast speed)
   
    # Ensure it never goes dangerously fast or totally stops
           
            # Memory decay. This is intentionally slow.
            relationship_memory *= 0.9
            social_fatigue = clamp(
                social_fatigue - delta_time * 0.05,
                0.0,
                1.0,
            )

            # Calculate and smooth interaction will every loop.
            target_interaction_will = calculate_interaction_will(
                mood_status,
                person_in_frame,
                cam_emotion,
                fc,
                fl,
                fr,
                near,
            )

            smooth_interaction_will(target_interaction_will)
            log_interaction_will_if_needed(target_interaction_will)

            shared_state["interaction_will"] = interaction_will
            shared_state["relationship_memory"] = relationship_memory
            shared_state["social_fatigue"] = social_fatigue

            # =====================================================
            # 2. STATES
            # =====================================================
            if sound_detected and not is_speaking:
                # 1. Clear the sensor flag immediately
                shared_state['sound_detected'] = False
                if shared_state['sound_event'] == 'APPLAUSE':
                    write_event_memory(
                        "SOUND_DETECTED",
                        {
                            "state": state,
                            "sound_event": "APPLAUSE",
                        }
                    )
                    shared_state['speaker_cmd'] = "ROBOT_GRATEFUL"
                    target_emotion = "HAPPY_2"
                    start_turn = 0
                    
                    while (time.time() - start_turn) <3.0:
                        target_vx, target_vy, target_vz = idle_behavior.base_motion_from_action(
                            "TURN_AROUND", 
                            BASE_SPEED, 
                            0.5
                        )

                    
                       
                # 2. Set the emotional/facial reaction
                target_emotion = "SURPRISE_2"
                
                # 3. Tell the speaker process to play an audio track 
                # (matches keys in your speaker_process audio_map)
                shared_state['speaker_cmd'] = "ROBOT_CAUTIOUS" 
                
                print("[BRAIN] Sound detected! Triggering surprise reaction and audio.")

            elif sound_detected and is_speaking:
                # If the microphone hears the robot's own speaker, discard it safely
                shared_state['sound_detected'] = False

                write_event_memory(
                    "SOUND_DETECTED",
                    {
                        "state": state,
                    }
                )

                last_meaningful_interaction_event_time = loop_now

            elif (
                near
                and state not in [
                    'STOP',
                    'TURN_AROUND',
                    'ESCAPE'
                ]
            ):
                set_state('STOP', 'near_obstacle')
                print
                stop_timer = time.time()
                target_emotion = "SURPRISE_3"

            elif state == 'STOP':
                # Keep STOP behavior mostly the same, but return to IDLE instead of old PATROL.
                smooth_vx = smooth_vx * 1
                smooth_vy = smooth_vy * 1
                smooth_vz = smooth_vz * 1
                
                target_emotion = "SURPRISE_3"
                target_vx, target_vy, target_vz = idle_behavior.base_motion_from_action(
                                        "PAUSE", 
                                        BASE_SPEED, 
                                        
                                    )
                if near:
                    target_vx, target_vy, target_vz = idle_behavior.base_motion_from_action(
                                                            "BACKWARD", 
                                                            BASE_SPEED, 
                                                            
                                                        )
                    time.sleep(0.5)
                    target_vx, target_vy, target_vz = idle_behavior.base_motion_from_action(
                                                            "PAUSE", 
                                                            BASE_SPEED, 
                                                            
                                                        )
                if (
                                        person_in_frame
                                        and interaction_will >= START_INTERACTION_THRESHOLD
                                        and loop_now >= reengage_block_until
                                    ):
                                        start_interaction('stop_person_confirmed')
                else:
                                        set_state('IDLE', 'interaction not possible')
                

                
                    
                        

            elif state == 'ESCAPE':
                target_emotion = "NEUTRAL"

                # 1. Get the new Keyword and Severity
                escape_action = calculate_escape_action(
                    fc,
                    fl,
                    fr,
                    b,
                    near,
                )

                # 2. Handle the "All Clear" keyword
                if escape_action == "PATH_CLEAR":
                    set_state('IDLE', 'escape_path_clear')
                    recently_investigated = True
                    #target_vx, target_vy, target_vz = 0.0, 0.0, 0.0 # Stop for 1 frame
                    target_vx, target_vy, target_vz, idle_eye_cmd = idle_behavior.update(
                                            shared_state,
                                            fc,
                                            fl,
                                            fr,
                                            b,
                                            IDLE_BASE_SPEED,
                                            safe_dist,
                                            FORCE_MULTIPLIER,
                                        )
                    """ose_base_action(self, fc, fl, fr, b, safe_dist)
                    self.base_action = random.choice(self.base_actions)
                    current_choice = self.base_action
                    target_vx, target_vy, target_vz = idle_behavior.base_motion_from_action(
                                                                current_choice,
                                                                BASE_SPEED, 
                                                                severity
                                                            )"""
                    write_event_memory(
                        "ESCAPE_FINISHED",
                        {
                            "reason": "path_clear",
                        }
                    )

                # 3. Handle the "Spin" keyword
                elif escape_action == "TURN_AROUND":
                    set_state('TURN_AROUND', 'escape_boxed_in')
                    time.sleep(1.0)
                    #target_vx, target_vy, target_vz = 0.0, 0.0, 0.0 # Stop moving to prepare for spin
                    
                    #set_state('STOP', 'turn_around_timeout')
                    #time.sleep(0.02)
                    set_state('IDLE', 'TURN TIMEOUT')
                    target_vx, target_vy, target_vz, idle_eye_cmd = idle_behavior.update(
                                                                shared_state,
                                                                fc,
                                                                fl,
                                                                fr,
                                                                b,
                                                                IDLE_BASE_SPEED,
                                                                safe_dist,
                                                                FORCE_MULTIPLIER,
                                                            )
                # 4. Handle all the actual movement keywords (FAST_ESCAPE_LEFT, PAUSE, etc.)
                else:
                    target_vx, target_vy, target_vz = idle_behavior.base_motion_from_action(
                        escape_action, 
                        BASE_SPEED, 
                    
                    )

            elif state == 'TURN_AROUND':
                target_emotion = "NEUTRAL"
                now = time.time()
                # 1. Start spinning
                #jadid
                if time.time()/2 == 0:
                    target_vx, target_vy, target_vz = idle_behavior.base_motion_from_action(
                    "ROTATE_RIGHT", 
                    BASE_SPEED
                )
                else:
                    target_vx, target_vy, target_vz = idle_behavior.base_motion_from_action(
                    "ROTATE_LEFT", 
                    BASE_SPEED
                )

                # 2. THE ESCAPE HATCH (Spin UNTIL front is clear)
                if fc > safe_dist and not near:
                    set_state('IDLE', 'turn_around_clear')
                    recently_investigated = True
                    #target_vx, target_vy, target_vz = 0.0, 0.0, 0.0
                    target_vx, target_vy, target_vz, idle_eye_cmd = idle_behavior.update(
                                            shared_state,
                                            fc,
                                            fl,
                                            fr,
                                            b,
                                            IDLE_BASE_SPEED,
                                            safe_dist,
                                            FORCE_MULTIPLIER,
                                        )
                    """ose_base_action(self, fc, fl, fr, b, safe_dist)
                    self.base_action = random.choice(self.base_actions)
                    current_choice = self.base_action
                    target_vx, target_vy, target_vz = idle_behavior.base_motion_from_action(
                                                                                    current_choice,
                                                                                    BASE_SPEED, 
                                                                                    severity
                                                                                )"""

                elif time.time() - turn_timer > 2:
                    set_state('IDLE', 'turn_around_timeout')
                    recently_investigated = True
                    #target_vx, target_vy, target_vz = 0.0, 0.0, 0.0

            elif state == 'IDLE':
                target_emotion = "NEUTRAL"

                shared_state["interaction_active"] = False
                shared_state["eye_control_mode"] = "IDLE_SCAN"
                #jadid
                #reengage_block_until = time.time() + REENGAGE_COOLDOWN
                # Camera sees a person even if sonar does not.
                if (
                    person_in_frame
                    and interaction_will >= START_INTERACTION_THRESHOLD
                    and loop_now >= reengage_block_until
                ):
                    write_runtime_log(
                        "IDLE_PERSON_FOUND | "
                        f"will={interaction_will:.2f} | "
                        f"front_distance={front_distance:.1f}"
                    )

                    start_interaction('idle_camera_person_will_high')

                elif far and not recently_investigated:
                    direction = get_investigation_direction(
                        fc,
                        fl,
                        fr,
                        b,
                        obstacle_direction,
                    )

                    start_investigation(direction, 'idle_far_object')
                    recently_investigated = True

                elif b < safe_dist and not recently_investigated_back:
                    # Back sonar detection. Camera cannot directly see back, but we remember direction.
                    start_investigation('BACK', 'idle_back_object')
                    recently_investigated_back = True

                else:
                    if not far and not near:
                        recently_investigated = False

                    if b > safe_dist + 20.0:
                        recently_investigated_back = False

                    target_vx, target_vy, target_vz, idle_eye_cmd = idle_behavior.update(
                        shared_state,
                        fc,
                        fl,
                        fr,
                        b,
                        IDLE_BASE_SPEED,
                        safe_dist,
                        FORCE_MULTIPLIER,
                    )

                    attention_eye_cmd = idle_eye_cmd

            elif state == 'INVESTIGATE':
                target_vx, target_vy, target_vz = idle_behavior.base_motion_from_action(
                                                                "PAUSE",
                                                                BASE_SPEED, 
                                                                
                                                            )
                target_emotion = "CAUTIOUS_1"
                if investigate_direction == "BACK":
                                    # If object is behind, body orientation is more useful than camera pan.
                                    target_vx, target_vy, target_vz = idle_behavior.base_motion_from_action(
                                                                                "ROTATE_RIGHT",
                                                                                BASE_SPEED, 
                                                                                
                                                                            )
                shared_state["eye_control_mode"] = "INVESTIGATE"

                

                if investigate_phase == "POINT_CAMERA":
                    attention_eye_cmd = move_camera_toward_target(loop_now)

                    if (
                        abs(camera_pan_angle - camera_target_pan) <= 1.0
                        and loop_now - investigate_timer >= CAMERA_SETTLE_TIME
                    ):
                        investigate_phase = "SCAN_CAMERA"
                        write_runtime_log(
                            f"INVESTIGATE_PHASE | SCAN_CAMERA | direction={investigate_direction}"
                        )

                elif investigate_phase == "SCAN_CAMERA":
                    attention_eye_cmd = scan_camera(loop_now)

                    if person_in_frame and face_in_frame:
                        investigate_phase = "CENTER_FACE"
                        face_seen_start_time = loop_now
                        face_centered_start_time = 0.0

                        write_runtime_log(
                            "INVESTIGATE_PHASE | CENTER_FACE | person_found=True"
                        )

                    elif loop_now - investigate_timer > INVESTIGATE_TIMEOUT:
                        finish_investigation_as_obstacle('investigate_timeout_no_person')
                        set_state('ESCAPE', 'investigate_obstacle')
                        escape_timer = time.time()

                elif investigate_phase == "CENTER_FACE":
                    attention_eye_cmd, face_centered = update_face_tracking(
                        loop_now,
                        face_center_x_norm,
                        face_center_y_norm,
                        face_in_frame,
                    )

                    if not person_in_frame:
                        # Person/object was not stable; keep scanning until timeout.
                        investigate_phase = "SCAN_CAMERA"

                    elif (
                        face_centered
                        and face_centered_start_time > 0.0
                        and loop_now - face_centered_start_time >= FACE_CONFIRM_TIME
                    ):  
                        print("investigation finished as person with centered face")
                        finish_investigation_as_person(
                                                    front_distance,
                                                    interaction_will,
                                                )
                                                #reengage_block_until = time.time() + REENGAGE_COOLDOWN
                        if (
                                                    interaction_will >= START_INTERACTION_THRESHOLD
                                                    and loop_now >= reengage_block_until
                                                ):
                                                    start_interaction('investigate_person_will_high')
                        
                        else:
                                                    set_state('IDLE', 'investigate_person_will_low')
                                                    escape_timer = time.time()

                    else:
                        print("investigation finished as person without centered face")
                        finish_investigation_as_person(
                                                    front_distance,
                                                    interaction_will,
                                                )
                                                #reengage_block_until = time.time() + REENGAGE_COOLDOWN
                        if (
                                                    interaction_will >= START_INTERACTION_THRESHOLD
                                                    and loop_now >= reengage_block_until
                                                ):
                                                    start_interaction('investigate_person_will_high')
                        
                        else:
                                                    set_state('IDLE', 'investigate_person_will_low')
                                                    escape_timer = time.time()

                    
                    
                elif loop_now - investigate_timer > INVESTIGATE_TIMEOUT:
                        # If the camera reports person but centering failed, still classify as person.
                        if person_in_frame:
                            finish_investigation_as_person(
                                front_distance,
                                interaction_will,
                            )

                            if interaction_will >= START_INTERACTION_THRESHOLD:
                                start_interaction('investigate_person_not_centered_but_detected')
                                set_state('INTERACT', 'investigate_person_not_centered_but_detected')   
                            else:
                                set_state('IDLE', 'investigate_person_will_low')
                                escape_timer = time.time()
                        else:
                            finish_investigation_as_obstacle('center_face_timeout_no_person')
                            set_state('ESCAPE', 'investigate_obstacle')
                            escape_timer = time.time()

            elif state == 'INTERACT':
                shared_state["eye_control_mode"] = "FACE_TRACK"

                # By default, interaction base is still. It can approach slowly if person is far.
                target_vx, target_vy, target_vz = idle_behavior.base_motion_from_action(
                                                                "PAUSE",
                                                                BASE_SPEED, 
                                                                
                                                            )

                # Continuous face tracking has priority over emotional eye movement.
                if face_in_frame:
                    attention_eye_cmd, face_centered = update_face_tracking(
                        loop_now,
                        face_center_x_norm,
                        face_center_y_norm,
                        True,
                    )

                    last_face_seen_time = loop_now
                    face_lost_start_time = 0.0
                    tracking_failure_start_time = 0.0

                    if face_centered:
                        last_meaningful_interaction_event_time = loop_now

                elif person_in_frame:
                    attention_eye_cmd = reacquire_face_scan(loop_now)
                    shared_state["eye_control_mode"] = "REACQUIRE_FACE"

                    if face_lost_start_time == 0.0:
                        face_lost_start_time = loop_now

                    if loop_now - face_lost_start_time > FACE_LOST_DURING_INTERACTION_TIMEOUT:
                        end_interaction('HUMAN_ATTENTION_LOST', 'IDLE')

                else:
                    attention_eye_cmd = reacquire_face_scan(loop_now)
                    shared_state["eye_control_mode"] = "REACQUIRE_FACE"

                    if person_lost_start_time == 0.0:
                        person_lost_start_time = loop_now
                        person_lost_count += 1

                    if loop_now - person_lost_start_time > PERSON_LOST_TIMEOUT:
                        end_interaction('PERSON_LOST', 'IDLE')

                    elif person_lost_count >= MAX_FRAME_LOSS_COUNT:
                        end_interaction('REPEATED_FRAME_LOSS', 'IDLE')

                if person_in_frame:
                    last_person_seen_time = loop_now
                    person_lost_start_time = 0.0

                # Move toward camera-only / far person if interaction will is high and path is safe.
                if (
                    person_in_frame
                    and interaction_will >= START_INTERACTION_THRESHOLD
                    and not near
                    and front_distance > 120.0
                ):
                    target_vx, target_vy, target_vz = idle_behavior.base_motion_from_action(
                        "SLOW_FORWARD",
                        APPROACH_SPEED,
                        
                    )

                # Apply light APF even while approaching.
                if target_vx > 0.0:
                    target_vx, target_vy, target_vz = idle_behavior.apply_apf_repulsion(
                        target_vx,
                        target_vy,
                        target_vz,
                        fc,
                        fl,
                        fr,
                        safe_dist,
                        FORCE_MULTIPLIER,
                        allow_backward=False,
                    )

                # Track moving away using sonar if available.
                if person_in_frame and front_distance < 350.0:
                    closest_interaction_distance = min(
                        closest_interaction_distance,
                        front_distance,
                    )

                    if (
                        front_distance > MAX_INTERACTION_DISTANCE
                        and front_distance > closest_interaction_distance + 50.0
                    ):
                        if moving_away_start_time == 0.0:
                            moving_away_start_time = loop_now

                        elif loop_now - moving_away_start_time > MOVING_AWAY_TIMEOUT:
                            end_interaction('PERSON_MOVED_AWAY', 'IDLE')
                    else:
                        moving_away_start_time = 0.0

                # Interaction will low means the robot wants to end it.
                if interaction_will < STOP_INTERACTION_THRESHOLD:
                    end_interaction('INTERACTION_WILL_LOW', 'ESCAPE')
                    escape_timer = time.time()

                # No meaningful social activity for a long time.
                elif (
                    loop_now
                    - last_meaningful_interaction_event_time
                    > INTERACTION_IDLE_TIMEOUT
                ):
                    end_interaction('NO_MEANINGFUL_EVENT', 'IDLE')

                # Tracking failure: face/person exists but cannot be kept useful.
                elif (
                    face_in_frame
                    and tracking_failure_start_time > 0.0
                    and loop_now - tracking_failure_start_time > TRACKING_FAILED_TIMEOUT
                ):
                    end_interaction('TRACKING_FAILED', 'IDLE')

                # Existing emotional reaction logic, preserved but connected to memory/will.
                if shared_state.get('current_state') == 'INTERACT' and person_in_frame:
                    if (
                        time.time() - last_action_time
                        >= ACTION_COOLDOWN
                    ):
                        now = time.time()

                        # 1. Calculate Intensity from distance.
                        # Use front sensors only, not back sonar.
                        dist_val = min(
                            max(
                                front_distance,
                                10.0
                            ),
                            100.0
                        )

                        if dist_val <= 60.0:
                            intensity = 3
                        elif dist_val <= 80.0:
                            intensity = 2
                        else:
                            intensity = 1

                        target_emotion = "NEUTRAL"

                        # A camera emotion is a new event only if:
                        # - it is non-neutral; and
                        # - the camera was rearmed; or
                        # - the emotion changed directly.
                        new_camera_emotion = (
                            cam_emotion
                            not in CAMERA_NEUTRAL_VALUES
                            and (
                                camera_emotion_armed
                                or cam_emotion
                                != last_processed_camera_emotion
                            )
                        )
                        
                        # 2. Anticipation Trigger: person approaching.
                        if dist_val < last_dist - 5 and not near:   
                            if approach_start_time == 0:
                                approach_start_time = time.time()
                            if time.time() - approach_start_time > 3.0:

                                if anticipation_stage == 0:
                                    target_emotion = "ANTICIPATION_1"
                                    anticipation_stage = 1
                                    time.sleep(0.01)

                                elif anticipation_stage == 1 :
                                    target_emotion = "ANTICIPATION_2"
                                    anticipation_stage = 2
                                    time.sleep(0.01)

                                elif anticipation_stage == 2 :
                                    target_emotion = "ANTICIPATION_3"
                                    anticipation_stage = 3
                                    time.sleep(0.01)
                                elif anticipation_stage == 3 :
                                                                    target_emotion = "ANTICIPATION_1"
                                                                    anticipation_stage = 0
                                                                    time.sleep(0.01)
                                elif anticipation_stage == 0:
                                                                    target_emotion = "ANTICIPATION_2"
                                                                    anticipation_stage = 1
                                                                    time.sleep(0.01)
                                                    

                            """if (
                                now - approach_start_time
                                > 3.0
                            ):
                                target_emotion = (
                                    "ANTICIPATION_3"
                                )

                                last_meaningful_interaction_event_time = loop_now """

                        else:
                            approach_start_time = 0

                            # Process a detected facial emotion only once,
                            # rather than once every cooldown.
                            if new_camera_emotion:
                                last_meaningful_interaction_event_time = loop_now

                                # 3. Trust Logic
                                if cam_emotion == "HAPPY":
                                    happy_history += 1
                                    interaction_positive_events += 1
                                    base = emo_map.get(
                                        cam_emotion,
                                        "HAPPY"
                                        )
                                    HAPPY_COUNTER +=1                                   
                                    target_emotion = (
                                        f"{base}_{intensity}"
                                    )
                                    shared_state["speaker_cmd"] = "ROBOT_HAPPY"
                                    if intensity == 3:
                                        update_relationship_memory(0.3*openness, "ROBOT_HAPPY")
                                    elif intensity == 2:
                                        update_relationship_memory(0.2*openness, "ROBOT_HAPPY")
                                    elif intensity == 1:
                                        update_relationship_memory(0.1*openness, "ROBOT_HAPPY")

                            
                                elif cam_emotion == "ANGRY":
                                                                    angry_history += 1
                                                                    interaction_negative_events += 1
                                                                    
                                                                    if "neuroticism" > 0.5:
                                                                        cam_emotion = "ANGER2"
                                                                        base = emo_map.get(
                                                                            cam_emotion,
                                                                            "ANGER"
                                                                        )
                                                                    if "neuroticism" < 0.5:
                                                                        base = emo_map.get(
                                                                            cam_emotion,
                                                                            "FEAR"
                                                                        )
                                                                    
                                                                    
                                                                    target_emotion = (
                                                                        f"{base}_{intensity}"
                                                                    )
                                                                    ANGRY_COUNTER +=1
                                                                    shared_state["speaker_cmd"] = "ROBOT_ANGRY"
                                
                                                                    if intensity == 3:
                                                                        update_relationship_memory(-0.3*openness, "ROBOT_ANGRY")
                                                                    elif intensity == 2:
                                                                        update_relationship_memory(-0.2*openness, "ROBOT_ANGRY")
                                                                    elif intensity == 1:
                                                                        update_relationship_memory(-0.1*openness, "ROBOT_ANGRY")
                                elif cam_emotion == "SURPRISE":
                                    angry_history += 1
                                    interaction_negative_events += 1
                                    
                                    if traits["neuroticism"] > 0.5:
                                        cam_emotion = "SURPRISE2"
                                        base = emo_map.get(
                                            cam_emotion,
                                            "SURPRISE"
                                        )
                                        shared_state["speaker_cmd"] = "ROBOT_SURPRISED"
                                    if traits["neuroticism"] < 0.5:
                                        base = emo_map.get(
                                            cam_emotion,
                                            "CAUTIOUS"
                                        )
                                        shared_state["speaker_cmd"] = "ROBOT_CAUTIOUS"
                                    
                                    target_emotion = (
                                        f"{base}_{intensity}"
                                    )

                                    shared_state["speaker_cmd"] = "ROBOT_SURPRISED"

                                    if intensity == 3:
                                        update_relationship_memory(-0.3*openness, "ROBOT_SURPRISED")
                                    elif intensity == 2:
                                        update_relationship_memory(-0.2*openness, "ROBOT_SURPRISED")
                                    elif intensity == 1:
                                        update_relationship_memory(-0.1*openness, "ROBOT_SURPRISED")

                                

                                elif cam_emotion in ["DISGUST", "FEAR"]:
                                    negative_human_reaction_count += 1
                                    interaction_negative_events += 1
                                    
                                    base = emo_map.get(
                                        cam_emotion,
                                        "CAUTIOUS"
                                    )

                                    target_emotion = (
                                        f"{base}_{intensity}"
                                    )
                                    
                                    if intensity == 3:
                                        update_relationship_memory(-0.3*openness, f"ROBOT_{cam_emotion.upper()}")                                   
                                    elif intensity == 2:
                                        update_relationship_memory(-0.2*openness, f"ROBOT_{cam_emotion.upper()}")
                                    elif intensity == 1:
                                        update_relationship_memory(-0.1*openness, f"ROBOT_{cam_emotion.upper()}")

                                elif cam_emotion == "SAD":
                                    interaction_positive_events += 1 if agreeableness > 0.5 else 0
                                    

                                    base = emo_map.get(
                                        cam_emotion,
                                        "SAD"
                                    )
                                    
                                    target_emotion = (
                                        f"{base}_{intensity}"
                                    )

                                    shared_state["speaker_cmd"] = "ROBOT_SAD"
                                    if intensity == 3:
                                        update_relationship_memory(-0.3*openness, "ROBOT_SAD")
                                    elif intensity == 2:
                                        update_relationship_memory(-0.2*openness, "ROBOT_SAD")
                                    elif intensity == 1:
                                        update_relationship_memory(-0.1*openness, "ROBOT_SAD")

                                else:
                                    # 4. Basic Emotion Mapping
                                    base = emo_map.get(
                                        cam_emotion,
                                        "NEUTRAL"
                                    )

                                    target_emotion = (
                                        f"{base}_{intensity}"
                                    )

                                last_processed_camera_emotion = (
                                    cam_emotion
                                )

                                camera_emotion_armed = False

                        if (relationship_memory > 0.5 or HAPPY_COUNTER > 3) and target_emotion != "TRUST3":
                            base = emo_map.get(
                                                                    cam_emotion,
                                                                    "HAPPY2"
                                                                )
                            intensity = 3
                            target_emotion = (
                                 f"{base}_{intensity}"
                            )
                            
                        elif (relationship_memory > 0.2 or HAPPY_COUNTER > 2) and relationship_memory <= 0.5 and target_emotion != "TRUST2":
                            base = emo_map.get(
                                                                    cam_emotion,
                                                                    "HAPPY2"
                                                                )
                            base = "TRUST"
                            intensity = 2
                            target_emotion = (
                                 f"{base}_{intensity}"
                            )

                        if (relationship_memory < -0.5 or ANGRY_COUNTER > 3) and target_emotion != "DISTRUST3":
                            base = emo_map.get(
                                                                    cam_emotion,
                                                                    "ANGRY3"
                                                                )
                            intensity = 3
                            target_emotion = (
                                 f"{base}_{intensity}"
                            )

                            shared_state["speaker_cmd"] = "ROBOT_DISAPPOINTED"
                        elif (relationship_memory < -0.2 or ANGRY_COUNTER > 2) and relationship_memory >= -0.5 and target_emotion != "DISTRUST2":
                            base = emo_map.get(
                                                                    cam_emotion,
                                                                    "ANGRY3"
                                                                )
                            intensity = 2
                            target_emotion = (
                                 f"{base}_{intensity}"
                            )



                        

                        last_action_time = time.time()
                        last_dist = dist_val

            else:
                # Unknown state recovery.
                write_runtime_log(
                    f"UNKNOWN_STATE | state={state} | recovering_to_IDLE"
                )
                set_state('IDLE', 'unknown_state_recovery')

            # =====================================================
            # 3. EXECUTE OUTPUTS
            # =====================================================

            # Write Movement
            current_state_after_logic = shared_state.get('current_state', state)

            if current_state_after_logic != 'STOP':
                # Apply the emotional speed multiplier globally before smoothing
                if current_state_after_logic != 'PAUSE':  # not in ['AUDIO_REFLEX']:
                    """ target_vx *= speed_multiplier
                     target_vy *= speed_multiplier
                     target_vz *= speed_multiplier """

                smooth_vx = (
                    smooth_vx * (1.0 - SMOOTHING_FACTOR)
                ) + (
                    target_vx * SMOOTHING_FACTOR
                )

                smooth_vy = (
                    smooth_vy * (1.0 - SMOOTHING_FACTOR)
                ) + (
                    target_vy * SMOOTHING_FACTOR
                )

                smooth_vz = (
                    smooth_vz * (1.0 - SMOOTHING_FACTOR)
                ) + (
                    target_vz * SMOOTHING_FACTOR
                )

            shared_state['motor_cmd_x'] = target_vx
            shared_state['motor_cmd_y'] = target_vy
            shared_state['motor_cmd_z'] = target_vz
            #print(f"[IDLE] Motor Commands: x={shared_state['motor_cmd_x']:.2f}, y={shared_state['motor_cmd_y']:.2f}, z={shared_state['motor_cmd_z']:.2f}")

            # =====================================================
            # GRADUAL EMOTION AND MOOD OUTPUT
            # =====================================================
            now = time.time()

            # Your original mapping can create NEUTRAL_1.
            # Convert it to the true neutral key.
            if target_emotion.startswith(
                "NEUTRAL_"
            ):
                target_emotion = "NEUTRAL"

            # A non-neutral state becomes an emotional event.
            if (
                target_emotion != "NEUTRAL"
                and target_emotion in reactions.EMOTIONS
            ):
                should_trigger = (
                    target_emotion
                    != last_triggered_emotion
                    or (
                        now
                        - last_triggered_time
                        >= ACTION_COOLDOWN
                    )
                )

                if should_trigger:
                    # Record every actual emotional trigger together
                    # with the camera and sonar values at that exact
                    # moment.
                    write_runtime_log(
                        "TRIGGER | "
                        f"emotion={target_emotion} | "
                        f"state={state} | "
                        f"person_in_frame={person_in_frame} | "
                        f"face_in_frame={face_in_frame} | "
                        f"camera_emotion={cam_emotion} | "
                        f"interaction_will={interaction_will:.2f} | "
                        f"front_left={format_log_value(fl)} cm | "
                        f"front_center={format_log_value(fc)} cm | "
                        f"front_right={format_log_value(fr)} cm | "
                        f"back={format_log_value(b)} cm | "
                        f"near={near} | "
                        f"far={far}"
                    )

                    write_event_memory(
                        "EMOTION_TRIGGERED",
                        {
                            "emotion": target_emotion,
                            "state": state,
                            "person_in_frame": bool(person_in_frame),
                            "face_in_frame": bool(face_in_frame),
                            "camera_emotion": cam_emotion,
                            "interaction_will": round(interaction_will, 3),
                            "mood_valence": round(mood_status['mood_valence'], 3),
                            "mood_arousal": round(mood_status['mood_arousal'], 3),
                            "mood_dominance": round(mood_status['mood_dominance'], 3),
                        }
                    )

                    mood_manager.receive_emotion(
                        target_emotion
                    )

                    interaction_robot_reactions.append(target_emotion)

                    last_triggered_emotion = (
                        target_emotion
                    )

                    last_triggered_time = now

            else:
                # Allows the same emotion to be triggered again
                # later as a separate event.
                last_triggered_emotion = None

            # MoodManager now decides which expression should be
            # visible as the emotion continuously decays.
            effective_emotion = (
                mood_manager.get_expression()
            )

            mood_status = (
                mood_manager.get_status()
            )

            # Make current mood available to other processes.
            shared_state['mood_valence'] = (
                mood_status['mood_valence']
            )

            shared_state['mood_arousal'] = (
                mood_status['mood_arousal']
            )

            shared_state['mood_dominance'] = (
                mood_status['mood_dominance']
            )

            shared_state['transient_emotion'] = (
                mood_status['transient_emotion']
            )

            shared_state['transient_strength'] = (
                mood_status['transient_strength']
            )

            # Only process valid emotions.
            if effective_emotion in reactions.EMOTIONS:

                # Only send commands when the discrete expression
                # changes.
                if (
                    effective_emotion
                    != last_written_emotion
                ):
                    cmd = reactions.get_reaction(
                        effective_emotion
                    )

                    # Mouth/body expression always belongs to emotion.
                    shared_state['mouth_cmd'] = cmd.get(
                        'mouth',
                        ''
                    )

                    shared_state['curtain_cmd'] = cmd.get(
                        'curtain',
                        ''
                    )

                    shared_state['bar_cmd'] = cmd.get(
                        'bars',
                        ''
                    )

                    shared_state['robot_emotion'] = (
                        effective_emotion
                    )

                    # Eye expression is stored as a request.
                    # Final eye_cmd is decided by attention priority below.
                    shared_state['emotion_eye_request'] = cmd.get(
                        'eyes',
                        ''
                    )

                    # Emotion can directly control eye only when there is
                    # no active attention task.
                    if attention_eye_cmd is None:
                        shared_state['eye_cmd'] = cmd.get(
                            'eyes',
                            ''
                        )

                        shared_state["camera_control_active"] = False
                    else:
                        shared_state["camera_control_active"] = True

                    print(
                        "[BRAIN] Expression changed to: "
                        f"{effective_emotion} | "
                        f"Mood VAD: "
                        f"V="
                        f"{mood_status['mood_valence']:.2f}, "
                        f"A="
                        f"{mood_status['mood_arousal']:.2f}, "
                        f"D="
                        f"{mood_status['mood_dominance']:.2f} | "
                        f"Transient="
                        f"{mood_status['transient_emotion']} "
                        f"("
                        f"{mood_status['transient_strength']:.2f}"
                        f") | "
                        f"InteractionWill={interaction_will:.2f}"
                    )

                    last_written_emotion = (
                        effective_emotion
                    )

            # Attention/camera command has final priority over emotional eye command.
            if attention_eye_cmd is not None:
                shared_state['eye_cmd'] = attention_eye_cmd
                shared_state["camera_control_active"] = True

            # Save compact memory occasionally when values drift.
            if random.random() < 0.01:
                save_memory_state()

        except Exception as e:
            print(
                f"[BRAIN ERROR] {e}"
            )

            write_runtime_log(
                f"BRAIN_ERROR | "
                f"{type(e).__name__}: {e}"
            )
        except KeyboardInterrupt:
            print("\n[BRAIN] Ctrl+C caught! Shutting down brain process...")
            shutdown_event.set()
            shared_state["motor_cmd_x"]=0
            shared_state["motor_cmd_y"]=0
            shared_state["motor_cmd_z"]=0
            break
        time.sleep(0.1)
