import cv2
import mediapipe as mp
import requests
import numpy as np
import time
import subprocess
from collections import deque, Counter
import socket
import json
import os
import re


# =================================================================
# UDP BRIDGE
# =================================================================
sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_DGRAM
)

sock.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)

UDP_IP = "10.0.0.114"
UDP_PORT = 5005


# =================================================================
# FACE QUALITY SETTINGS
# =================================================================

# Makes the crop 35% larger than the longest side of the face box.
# This should preserve the eyebrows, forehead and chin. THE LARGER, LESS STRICT
CROP_SCALE = 1.45

# Reject weak MediaPipe face detections.
MIN_DETECTION_CONFIDENCE = 0.50

# Reject faces that are too small for reliable emotion recognition. THE SMALLER, LESS STRICT
MIN_FACE_SIZE_PIXELS =90

# Head-pose and face-geometry thresholds. 
MIN_EYE_DISTANCE_RATIO = 0.10  #THE SMALLER, LESS STRICT
MAX_NOSE_OFFSET_RATIO = 0.75   #THE BIGGER LESS STRICT
#MAX_EYE_TILT_RATIO = 0.35

# Image-quality thresholds.
MIN_BLUR_SCORE = 15.0 #THE SMALLER LESS STRICT
MIN_BRIGHTNESS = 25.0
MAX_BRIGHTNESS = 245.0


# =================================================================
# DEBUG IMAGE SAVING SETTINGS
# =================================================================
SAVE_DEBUG_IMAGES = False

DEBUG_IMAGE_DIRECTORY = (
    "/media/jetson/sd/beedel/bidel/debug_faces"
)

ACCEPTED_IMAGE_DIRECTORY = os.path.join(
    DEBUG_IMAGE_DIRECTORY,
    "accepted"
)

REJECTED_IMAGE_DIRECTORY = os.path.join(
    DEBUG_IMAGE_DIRECTORY,
    "rejected"
)

# Maximum one accepted image and one rejected image per second.
DEBUG_SAVE_INTERVAL = 1.0

last_debug_save_time = {
    "accepted": 0.0,
    "rejected": 0.0
}

os.makedirs(
    ACCEPTED_IMAGE_DIRECTORY,
    exist_ok=True
)

os.makedirs(
    REJECTED_IMAGE_DIRECTORY,
    exist_ok=True
)


# =================================================================
# DOCKER SERVER STARTUP
# =================================================================
def start_docker_server(container_name, script_path):
    
    print(
        "Initiating DeepFace GPU server inside Docker..."
    )

    command = [
        "docker",
        "exec",
        "-d",
        container_name,
        "python3",
        script_path
    ]

    try:
        subprocess.run(
            command,
            check=True
        )
        
        #print("CAMERA OK")
        
        print(
            "Waiting 10 seconds for the Flask server "
            "and GPU model to load..."
        )
        
        time.sleep(10)
        #connection_status["CAMERA"] = True
    except subprocess.CalledProcessError as error:
        print(
            "Error starting the server! "
            f"Is the container running? Error: {error}"
        )


# =================================================================
# EMOTION SMOOTHING AND CONFIRMATION
# =================================================================
emotion_buffer = deque(
    maxlen=30
)

confirmed_emotion = "neutral"

candidate_history = deque()

EMOTION_CONFIRM_TIME = 1.0


# =================================================================
# DEEPFACE AND MEDIAPIPE
# =================================================================
DEEPFACE_URL = "http://localhost:5000/predict"

mp_face = mp.solutions.face_detection

face_detector = mp_face.FaceDetection(
    min_detection_confidence=0.5
)


# =================================================================
# CAMERA STARTUP
# =================================================================
start_docker_server(
    "vision",
    "/vision_server.py"
)

cap = cv2.VideoCapture(
    "/dev/v4l/by-id/"
    "usb-Jieli_Technology_USB_Composite_Device-video-index0"
)

last_sent_time = 0.0

SEND_INTERVAL = 0.05


# =================================================================
# DEBUG IMAGE FUNCTIONS
# =================================================================
def sanitize_filename(text):
    """
    Removes characters that should not be used in filenames.
    """

    text = str(text).lower()

    text = re.sub(
        r"[^a-z0-9._-]+",
        "_",
        text
    )

    return text[:80]


def save_debug_image(
    image,
    category,
    reason=""
):
    """
    Saves an accepted or rejected debug image.

    category must be:
        accepted
        rejected
    """

    if not SAVE_DEBUG_IMAGES:
        return

    if image is None or image.size == 0:
        return

    if category not in last_debug_save_time:
        return

    now = time.time()

    if (
        now - last_debug_save_time[category]
        < DEBUG_SAVE_INTERVAL
    ):
        return

    if category == "accepted":
        output_directory = (
            ACCEPTED_IMAGE_DIRECTORY
        )
    else:
        output_directory = (
            REJECTED_IMAGE_DIRECTORY
        )

    timestamp = time.strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    milliseconds = int(
        (now % 1) * 1000
    )

    safe_reason = sanitize_filename(
        reason
    )

    filename = (
        f"{timestamp}_"
        f"{milliseconds:03d}_"
        f"{safe_reason}.jpg"
    )

    full_path = os.path.join(
        output_directory,
        filename
    )

    save_success = cv2.imwrite(
        full_path,
        image
    )

    if save_success:
        last_debug_save_time[category] = now

        print(
            f"[DEBUG IMAGE] Saved: {full_path}",
            flush=True
        )

    else:
        print(
            f"[DEBUG IMAGE] Could not save: {full_path}",
            flush=True
        )


def make_rejection_preview(
    frame,
    detection,
    reason
):
    """
    Creates a copy of the complete camera frame with:
    - the face bounding rectangle;
    - the rejection reason.
    """

    preview = frame.copy()

    frame_height, frame_width = (
        preview.shape[:2]
    )

    bbox = (
        detection
        .location_data
        .relative_bounding_box
    )

    x1 = int(
        bbox.xmin * frame_width
    )

    y1 = int(
        bbox.ymin * frame_height
    )

    x2 = int(
        (bbox.xmin + bbox.width)
        * frame_width
    )

    y2 = int(
        (bbox.ymin + bbox.height)
        * frame_height
    )

    x1 = max(
        0,
        x1
    )

    y1 = max(
        0,
        y1
    )

    x2 = min(
        frame_width - 1,
        x2
    )

    y2 = min(
        frame_height - 1,
        y2
    )

    cv2.rectangle(
        preview,
        (x1, y1),
        (x2, y2),
        (0, 0, 255),
        2
    )

    display_reason = str(reason)[:70]

    text_y = max(
        25,
        y1 - 10
    )

    cv2.putText(
        preview,
        display_reason,
        (x1, text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 0, 255),
        2,
        cv2.LINE_AA
    )

    return preview


# =================================================================
# FACE VALIDATION FUNCTIONS
# =================================================================
def point_distance(
    point_1,
    point_2
):
    """
    Calculates the distance between two normalized MediaPipe points.
    """

    return np.sqrt(
        ((point_1.x - point_2.x) ** 2)
        + ((point_1.y - point_2.y) ** 2)
    )

def enhance_face_image(face_image):
    """
          Applies mild contrast enhancement and sharpening.
          This can improve slightly soft or low-contrast images,
          but cannot recover severely blurred details.
         """

    # Improve local contrast using LAB luminance.
    lab = cv2.cvtColor(
        face_image,
        cv2.COLOR_BGR2LAB
    )

    l_channel, a_channel, b_channel = cv2.split(
        lab
    )

    clahe = cv2.createCLAHE(
        clipLimit=1.5,
        tileGridSize=(8, 8)
    )

    enhanced_l = clahe.apply(
        l_channel
    )

    enhanced_lab = cv2.merge(
        (
            enhanced_l,
            a_channel,
            b_channel
        )
    )

    contrast_enhanced = cv2.cvtColor(
        enhanced_lab,
        cv2.COLOR_LAB2BGR
    )

    # Mild unsharp mask.
    blurred = cv2.GaussianBlur(
        contrast_enhanced,
        (0, 0),
        1.0
    )

    sharpened = cv2.addWeighted(
        contrast_enhanced,
        1.4,
        blurred,
        -0.4,
        0
    )

    return sharpened


def detection_priority(detection):
    """
    Prioritizes faces that are large and confidently detected.
    """

    bbox = (
        detection
        .location_data
        .relative_bounding_box
    )

    area = (
        max(0.0, bbox.width)
        * max(0.0, bbox.height)
    )

    confidence = (
        detection.score[0]
        if detection.score
        else 0.0
    )

    return area * confidence


def validate_face_view(
    detection,
    frame
):
    """
    Rejects faces that are:
    - detected with low confidence;
    - too small;
    - cut by the camera image boundary;
    - strongly turned sideways;
    - strongly tilted;
    - geometrically incomplete.

    Returns:
        valid, reason
    """

    frame_height, frame_width = (
        frame.shape[:2]
    )

    # -------------------------------------------------------------
    # Detection confidence
    # -------------------------------------------------------------
    if not detection.score:
        return (
            False,
            "missing detection confidence"
        )

    detection_confidence = float(
        detection.score[0]
    )

    if (
        detection_confidence
        < MIN_DETECTION_CONFIDENCE
    ):
        return (
            False,
            "low detection confidence "
            f"{detection_confidence:.2f}"
        )

    bbox = (
        detection
        .location_data
        .relative_bounding_box
    )

    x1 = bbox.xmin
    y1 = bbox.ymin

    x2 = (
        bbox.xmin
        + bbox.width
    )

    y2 = (
        bbox.ymin
        + bbox.height
    )

    # -------------------------------------------------------------
    # Face outside camera image
    # -------------------------------------------------------------
    if (
        x1 < -0.03
        or y1 < -0.10
        or x2 > 1.03
        or y2 > 1.04
    ):
        return (
            False,
            "face partially outside image"
        )

    face_width_pixels = (
        bbox.width
        * frame_width
    )

    face_height_pixels = (
        bbox.height
        * frame_height
    )

    # -------------------------------------------------------------
    # Face size
    # -------------------------------------------------------------
    if (
        min(
            face_width_pixels,
            face_height_pixels
        )
        < MIN_FACE_SIZE_PIXELS
    ):
        return (
            False,
            "face too small "
            f"{face_width_pixels:.0f}x"
            f"{face_height_pixels:.0f}"
        )

    # -------------------------------------------------------------
    # MediaPipe keypoints
    # -------------------------------------------------------------
    right_eye = mp_face.get_key_point(
        detection,
        mp_face.FaceKeyPoint.RIGHT_EYE
    )

    left_eye = mp_face.get_key_point(
        detection,
        mp_face.FaceKeyPoint.LEFT_EYE
    )

    nose = mp_face.get_key_point(
        detection,
        mp_face.FaceKeyPoint.NOSE_TIP
    )

    mouth = mp_face.get_key_point(
        detection,
        mp_face.FaceKeyPoint.MOUTH_CENTER
    )

    if (
        right_eye is None
        or left_eye is None
        or nose is None
        or mouth is None
    ):
        return (
            False,
            "important face keypoints missing"
        )

    eye_distance = point_distance(
        left_eye,
        right_eye
    )

    # -------------------------------------------------------------
    # Side view based on eye distance
    # -------------------------------------------------------------
    if (
        eye_distance
        < bbox.width
        * MIN_EYE_DISTANCE_RATIO
    ):
        return (
            False,
            "side view eyes too close"
        )

    eye_mid_x = (
        left_eye.x
        + right_eye.x
    ) / 2.0

    eye_mid_y = (
        left_eye.y
        + right_eye.y
    ) / 2.0

    # -------------------------------------------------------------
    # Side view based on nose position
    # -------------------------------------------------------------
    nose_horizontal_offset = (
        abs(
            nose.x
            - eye_mid_x
        )
        / max(
            eye_distance,
            0.0001
        )
    )

    if (
        nose_horizontal_offset
        > MAX_NOSE_OFFSET_RATIO
    ):
        return (
            False,
            "face turned sideways "
            f"{nose_horizontal_offset:.2f}"
        )

    # -------------------------------------------------------------
    # Head tilt
    # -------------------------------------------------------------
    """eye_vertical_difference = (
        abs(
            left_eye.y
            - right_eye.y
        )
        / max(
            eye_distance,
            0.0001
        )
    )

    if (
        eye_vertical_difference
        > MAX_EYE_TILT_RATIO
    ):
        return (
            False,
            "head too tilted "
            f"{eye_vertical_difference:.2f}"
        )"""

    # -------------------------------------------------------------
    # Eye, nose and mouth vertical order
    # -------------------------------------------------------------
    if not (
        eye_mid_y
        < nose.y
        < mouth.y
    ):
        return (
            False,
            "invalid eye nose mouth geometry"
        )

    # -------------------------------------------------------------
    # Left/right face symmetry
    # -------------------------------------------------------------
    nose_to_left_eye = point_distance(
        nose,
        left_eye
    )

    nose_to_right_eye = point_distance(
        nose,
        right_eye
    )

    symmetry_ratio = (
        nose_to_left_eye
        / max(
            nose_to_right_eye,
            0.0001
        )
    )

    if (
        symmetry_ratio < 0.15
        or symmetry_ratio > 2.80
    ):
        return (
            False,
            "face asymmetry too high "
            f"{symmetry_ratio:.2f}"
        )

    return (
        True,
        "valid"
    )


def crop_center_face(
    frame,
    bbox,
    scale=CROP_SCALE
):
    """
    Creates a square face crop.

    The crop uses the longest side of the detected face box,
    enlarges it by CROP_SCALE, and moves it slightly upward
    to preserve the eyebrows and forehead.
    """

    frame_height, frame_width = (
        frame.shape[:2]
    )

    x = (
        bbox.xmin
        * frame_width
    )

    y = (
        bbox.ymin
        * frame_height
    )

    bbox_width = (
        bbox.width
        * frame_width
    )

    bbox_height = (
        bbox.height
        * frame_height
    )

    center_x = (
        x
        + bbox_width / 2.0
    )

    center_y = (
        y
        + bbox_height / 2.0
    )

    crop_side = (
        max(
            bbox_width,
            bbox_height
        )
        * scale
    )

    # Shift crop upward slightly to preserve eyebrows and forehead.
    center_y -= (
        crop_side
        * 0.04
    )

    x1 = int(
        center_x
        - crop_side / 2.0
    )

    y1 = int(
        center_y
        - crop_side / 2.0
    )

    x2 = int(
        center_x
        + crop_side / 2.0
    )

    y2 = int(
        center_y
        + crop_side / 2.0
    )

    # Reject instead of silently clipping the face crop.
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(frame_width, x2)
    y2 = min(frame_height, y2)

    face_crop = frame[
        y1:y2,
        x1:x2
    ]

    if face_crop.size == 0:
        return None

    return face_crop


def validate_face_image(
    face_image
):
    """
    Validates:
    - cropped face size;
    - image sharpness;
    - brightness.

    Returns:
        valid, reason
    """

    if (
        face_image is None
        or face_image.size == 0
    ):
        return (
            False,
            "empty face crop"
        )

    face_height, face_width = (
        face_image.shape[:2]
    )

    if (
        min(
            face_height,
            face_width
        )
        < MIN_FACE_SIZE_PIXELS
    ):
        return (
            False,
            "cropped face too small "
            f"{face_width}x{face_height}"
        )

    gray_face = cv2.cvtColor(
        face_image,
        cv2.COLOR_BGR2GRAY
    )

    blur_score = cv2.Laplacian(
        gray_face,
        cv2.CV_64F
    ).var()

    brightness = float(
        gray_face.mean()
    )

    if blur_score < MIN_BLUR_SCORE:
        return (
            False,
            "face too blurry "
            f"{blur_score:.1f}"
        )

    if brightness < MIN_BRIGHTNESS:
        return (
            False,
            "face too dark "
            f"{brightness:.1f}"
        )

    if brightness > MAX_BRIGHTNESS:
        return (
            False,
            "face overexposed "
            f"{brightness:.1f}"
        )

    return (
        True,
        "valid "
        f"blur_{blur_score:.1f}_"
        f"brightness_{brightness:.1f}"
    )


def send_invalid_face_state(reason):
    """
    Reports that a person is visible but the current face image
    is not reliable enough for a new emotion prediction.

    The previous confirmed emotion remains active.
    """

    global last_sent_time

    now = time.time()

    print(
        f"[CAMERA] Face rejected: {reason}",
        flush=True
    )

    if (
        now - last_sent_time
        > SEND_INTERVAL
    ):
        data = {
            "person_in_frame": True,
            "person_emotion": confirmed_emotion,
            "all_emotions": {}
        }

        sock.sendto(
            json.dumps(data).encode(
                "utf-8"
            ),
            (
                UDP_IP,
                UDP_PORT
            )
        )

        last_sent_time = now


# =================================================================
# MAIN CAMERA LOOP
# =================================================================
while True:
    ret, frame = cap.read()

    if not ret:
        continue

    rgb = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    results = face_detector.process(
        rgb
    )

    if results.detections:
        face_detected = True

        # Select the largest and most confident face.
        detection = max(
            results.detections,
            key=detection_priority
        )

        # ---------------------------------------------------------
        # Validate face direction, geometry and size
        # ---------------------------------------------------------
        (
            face_is_valid,
            rejection_reason
        ) = validate_face_view(
            detection,
            frame
        )

        if not face_is_valid:
            rejection_preview = (
                make_rejection_preview(
                    frame,
                    detection,
                    rejection_reason
                )
            )

            save_debug_image(
                rejection_preview,
                "rejected",
                rejection_reason
            )

            send_invalid_face_state(
                rejection_reason
            )

            # Rejected frames do not enter smoothing/history.
            continue

        bbox = (
            detection
            .location_data
            .relative_bounding_box
        )

        # ---------------------------------------------------------
        # Create improved square face crop
        # ---------------------------------------------------------
        face_img = crop_center_face(
            frame,
            bbox
        )

        if face_img is None:
            rejection_reason = (
                "crop outside image"
            )

            rejection_preview = (
                make_rejection_preview(
                    frame,
                    detection,
                    rejection_reason
                )
            )

            save_debug_image(
                rejection_preview,
                "rejected",
                rejection_reason
            )

            send_invalid_face_state(
                rejection_reason
            )
            
            continue

        # ---------------------------------------------------------
        # Validate face crop sharpness and lighting
        # ---------------------------------------------------------
        (
            image_is_valid,
            image_reason
        ) = validate_face_image(
            face_img
        )
    
        if not image_is_valid:
            save_debug_image(
                face_img,
                "rejected",
                image_reason
            )

            send_invalid_face_state(
                image_reason
            )
            face_img = enhance_face_image(
            face_img
            )
            # Rejected frames do not enter smoothing/history.
            continue
        face_img = enhance_face_image(
          face_img)

        save_debug_image(
        face_img,
        "accepted",
        image_reason)

        now = time.time()
        # ---------------------------------------------------------
        # Save accepted face crop
        # ---------------------------------------------------------


        if (
            now - last_sent_time
            > SEND_INTERVAL
        ):
            (
                encode_success,
                img_encoded
            ) = cv2.imencode(
                ".jpg",
                face_img
            )

            if not encode_success:
                print(
                    "[CAMERA] Could not encode face crop",
                    flush=True
                )

                continue

            try:
                response = requests.post(
                    DEEPFACE_URL,
                    files={
                        "image": (
                            img_encoded
                            .tobytes()
                        )
                    },
                    timeout=20
                )

                response_data = response.json()

                emotion_data = (
                    response_data.get(
                        "emotion",
                        {}
                    )
                )

                # =================================================
                # EMOTION AMPLIFIER
                # Kept unchanged from your current code.
                # =================================================
                if isinstance(
                    emotion_data,
                    dict
                ):
                    if "neutral" in emotion_data:
                        emotion_data[
                            "neutral"
                        ] *= 0.2

                    if "happy" in emotion_data:
                        emotion_data[
                            "happy"
                        ] *= 0.3

                    if "sad" in emotion_data:
                        emotion_data[
                            "sad"
                        ] *= 6.0

                    if "disgust" in emotion_data:
                        emotion_data[
                            "disgust"
                        ] *= 8.0

                    if "fear" in emotion_data:
                        emotion_data[
                            "fear"
                        ] *= 4.0

                    if "surprise" in emotion_data:
                        emotion_data[
                            "surprise"
                        ] *= 3.5

                # =================================================
                # EMOTION SMOOTHING
                # Kept unchanged from your current code.
                # =================================================
                if isinstance(
                    emotion_data,
                    dict
                ):
                    emotion_buffer.append(
                        emotion_data
                    )

                    smoothed_emotions = {}

                    for key in emotion_data.keys():
                        smoothed_emotions[key] = round(
                            sum(
                                previous_result.get(
                                    key,
                                    0
                                )
                                for previous_result
                                in emotion_buffer
                                if isinstance(
                                    previous_result,
                                    dict
                                )
                            )
                            / len(emotion_buffer),
                            2
                        )

                    smoothed_dominant = (
                        max(
                            smoothed_emotions,
                            key=smoothed_emotions.get
                        )
                        if smoothed_emotions
                        else "none"
                    )

                else:
                    emotion_buffer.append(
                        emotion_data
                    )

                    smoothed_dominant = Counter(
                        emotion_buffer
                    ).most_common(1)[0][0]

                    smoothed_emotions = {
                        smoothed_dominant: 100.0
                    }

                # =================================================
                # ONE-SECOND LOCK WITH 90% AGREEMENT
                # Kept unchanged from your current code.
                # =================================================
                candidate_history.append(
                    (
                        now,
                        smoothed_dominant
                    )
                )

                while (
                    candidate_history
                    and (
                        now
                        - candidate_history[0][0]
                        > EMOTION_CONFIRM_TIME
                    )
                ):
                    candidate_history.popleft()

                if len(candidate_history) >= 10:
                    counts = Counter(
                        emotion
                        for _, emotion
                        in candidate_history
                    )

                    (
                        top_emotion,
                        top_count
                    ) = counts.most_common(1)[0]

                    agreement_ratio = (
                        top_count
                        / len(candidate_history)
                    )

                    if agreement_ratio >= 0.90:
                        confirmed_emotion = (
                            top_emotion
                        )

                print(
                    "[CAMERA] "
                    f"Confirmed: {confirmed_emotion} "
                    f"(Candidate: {smoothed_dominant}) "
                    f"| Crop: "
                    f"{face_img.shape[1]}x"
                    f"{face_img.shape[0]} "
                    f"| {image_reason}",
                    flush=True
                )

                data = {
                    "person_in_frame": (
                        face_detected
                    ),
                    "person_emotion": (
                        confirmed_emotion
                    ),
                    "all_emotions": (
                        smoothed_emotions
                    )
                }

                sock.sendto(
                    json.dumps(data).encode(
                        "utf-8"
                    ),
                    (
                        UDP_IP,
                        UDP_PORT
                    )
                )

                last_sent_time = now

            except Exception as error:
                print(
                    "Docker error:",
                    error
                )

    else:
        print(
            "No face detected",
            flush=True
        )

        # Clear candidate confirmations when the person leaves.
        candidate_history.clear()

        data = {
            "person_in_frame": False,
            "person_emotion": "none",
            "all_emotions": {}
        }

        sock.sendto(
            json.dumps(data).encode(
                "utf-8"
            ),
            (
                UDP_IP,
                UDP_PORT
            )
        )



"""
import cv2
import mediapipe as mp
import requests
import numpy as np
import time
import subprocess
from collections import deque, Counter
import socket
import json


# =================================================================
# UDP BRIDGE
# =================================================================
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

UDP_IP = "10.0.0.114"
UDP_PORT = 5005


# =================================================================
# FACE QUALITY SETTINGS
# =================================================================

# Makes the crop 35% larger than the longest side of the detected face.
# This should preserve the eyebrows, forehead and chin.
CROP_SCALE = 1.35

# Reject weak MediaPipe detections.
MIN_DETECTION_CONFIDENCE = 0.85

# Reject very small faces because emotion recognition becomes unreliable.
MIN_FACE_SIZE_PIXELS = 110

# Head-pose checks.
MIN_EYE_DISTANCE_RATIO = 0.18
MAX_NOSE_OFFSET_RATIO = 0.38
MAX_EYE_TILT_RATIO = 0.35

# Image-quality checks.
MIN_BLUR_SCORE = 45.0
MIN_BRIGHTNESS = 35.0
MAX_BRIGHTNESS = 225.0


# =================================================================
# DOCKER SERVER STARTUP
# =================================================================
def start_docker_server(container_name, script_path):
    print("Initiating DeepFace GPU server inside Docker...")

    command = [
        "docker",
        "exec",
        "-d",
        container_name,
        "python3",
        script_path
    ]

    try:
        subprocess.run(command, check=True)

        print("Server triggered successfully!")
        print(
            "Waiting 10 seconds for the Flask server "
            "and GPU model to load..."
        )

        time.sleep(10)

    except subprocess.CalledProcessError as e:
        print(
            "Error starting the server! "
            f"Is the container running? Error: {e}"
        )


# =================================================================
# EMOTION SMOOTHING AND CONFIRMATION
# =================================================================
emotion_buffer = deque(maxlen=30)

confirmed_emotion = "neutral"
candidate_history = deque()

EMOTION_CONFIRM_TIME = 1.0


# =================================================================
# DEEPFACE AND MEDIAPIPE
# =================================================================
DEEPFACE_URL = "http://localhost:5000/predict"

mp_face = mp.solutions.face_detection

face_detector = mp_face.FaceDetection(
    min_detection_confidence=0.8
)


# =================================================================
# CAMERA STARTUP
# =================================================================
start_docker_server(
    "vision",
    "/vision_server.py"
)

cap = cv2.VideoCapture(
    "/dev/v4l/by-id/"
    "usb-Jieli_Technology_USB_Composite_Device-video-index0"
)

last_sent_time = 0.0
SEND_INTERVAL = 0.05


# =================================================================
# FACE VALIDATION FUNCTIONS
# =================================================================
def point_distance(point_1, point_2):
   # Distance between two normalized MediaPipe points.

    return np.sqrt(
        ((point_1.x - point_2.x) ** 2)
        + ((point_1.y - point_2.y) ** 2)
    )


def detection_priority(detection):
   
    #Gives priority to a face that is both large and confidently detected.
    

    bbox = detection.location_data.relative_bounding_box

    area = (
        max(0.0, bbox.width)
        * max(0.0, bbox.height)
    )

    confidence = (
        detection.score[0]
        if detection.score
        else 0.0
    )

    return area * confidence


def validate_face_view(detection, frame):
    
    Reject faces that are:
    - detected with low confidence;
    - too small;
    - cut by the image border;
    - strongly turned sideways;
    - strongly tilted;
    - geometrically incomplete or unreliable.

    Returns:
        valid: bool
        reason: str
    

    frame_height, frame_width = frame.shape[:2]

    # -------------------------------------------------------------
    # Detection-confidence check
    # -------------------------------------------------------------
    if not detection.score:
        return False, "missing detection confidence"

    detection_confidence = float(detection.score[0])

    if detection_confidence < MIN_DETECTION_CONFIDENCE:
        return (
            False,
            "low detection confidence: "
            f"{detection_confidence:.2f}"
        )

    bbox = detection.location_data.relative_bounding_box

    x1 = bbox.xmin
    y1 = bbox.ymin
    x2 = bbox.xmin + bbox.width
    y2 = bbox.ymin + bbox.height

    # -------------------------------------------------------------
    # Image-border check
    # -------------------------------------------------------------
    if (
        x1 < 0.01
        or y1 < 0.01
        or x2 > 0.99
        or y2 > 0.99
    ):
        return False, "face is partially outside the camera image"

    face_width_pixels = bbox.width * frame_width
    face_height_pixels = bbox.height * frame_height

    # -------------------------------------------------------------
    # Face-size check
    # -------------------------------------------------------------
    if (
        min(face_width_pixels, face_height_pixels)
        < MIN_FACE_SIZE_PIXELS
    ):
        return (
            False,
            "face too small: "
            f"{face_width_pixels:.0f} x "
            f"{face_height_pixels:.0f}"
        )

    # -------------------------------------------------------------
    # Extract MediaPipe facial keypoints
    # -------------------------------------------------------------
    right_eye = mp_face.get_key_point(
        detection,
        mp_face.FaceKeyPoint.RIGHT_EYE
    )

    left_eye = mp_face.get_key_point(
        detection,
        mp_face.FaceKeyPoint.LEFT_EYE
    )

    nose = mp_face.get_key_point(
        detection,
        mp_face.FaceKeyPoint.NOSE_TIP
    )

    mouth = mp_face.get_key_point(
        detection,
        mp_face.FaceKeyPoint.MOUTH_CENTER
    )

    if (
        right_eye is None
        or left_eye is None
        or nose is None
        or mouth is None
    ):
        return False, "important facial keypoints are missing"

    eye_distance = point_distance(
        left_eye,
        right_eye
    )

    # -------------------------------------------------------------
    # Side-view check using apparent eye distance
    # -------------------------------------------------------------
    if eye_distance < bbox.width * MIN_EYE_DISTANCE_RATIO:
        return False, "probable side view: eyes appear too close"

    eye_mid_x = (
        left_eye.x + right_eye.x
    ) / 2.0

    eye_mid_y = (
        left_eye.y + right_eye.y
    ) / 2.0

    # -------------------------------------------------------------
    # Side-view check using nose displacement
    # -------------------------------------------------------------
    nose_horizontal_offset = (
        abs(nose.x - eye_mid_x)
        / max(eye_distance, 0.0001)
    )

    if nose_horizontal_offset > MAX_NOSE_OFFSET_RATIO:
        return (
            False,
            "face turned sideways: "
            f"nose offset {nose_horizontal_offset:.2f}"
        )

    # -------------------------------------------------------------
    # Head-roll check
    # -------------------------------------------------------------
    eye_vertical_difference = (
        abs(left_eye.y - right_eye.y)
        / max(eye_distance, 0.0001)
    )

    if eye_vertical_difference > MAX_EYE_TILT_RATIO:
        return (
            False,
            "head too tilted: "
            f"{eye_vertical_difference:.2f}"
        )

    # -------------------------------------------------------------
    # Basic facial-feature order
    # -------------------------------------------------------------
    if not (
        eye_mid_y < nose.y < mouth.y
    ):
        return False, "invalid eye, nose and mouth geometry"

    # -------------------------------------------------------------
    # Left/right facial symmetry check
    # -------------------------------------------------------------
    nose_to_left_eye = point_distance(
        nose,
        left_eye
    )

    nose_to_right_eye = point_distance(
        nose,
        right_eye
    )

    symmetry_ratio = (
        nose_to_left_eye
        / max(nose_to_right_eye, 0.0001)
    )

    if symmetry_ratio < 0.55 or symmetry_ratio > 1.80:
        return (
            False,
            "face asymmetry too high: "
            f"{symmetry_ratio:.2f}"
        )

    return True, "valid"


def crop_center_face(frame, bbox, scale=CROP_SCALE):

    Creates a square crop around the detected face.

    It uses the longest side of the face bounding box and enlarges it
    by CROP_SCALE. The crop is shifted slightly upward to preserve
    eyebrows and forehead.
    

    frame_height, frame_width = frame.shape[:2]

    x = bbox.xmin * frame_width
    y = bbox.ymin * frame_height

    bbox_width = bbox.width * frame_width
    bbox_height = bbox.height * frame_height

    center_x = x + (bbox_width / 2.0)
    center_y = y + (bbox_height / 2.0)

    # Use the longest side so the resulting crop is square.
    crop_side = max(
        bbox_width,
        bbox_height
    ) * scale

    # Shift slightly upward to include eyebrows and forehead.
    center_y -= crop_side * 0.04

    x1 = int(center_x - crop_side / 2.0)
    y1 = int(center_y - crop_side / 2.0)

    x2 = int(center_x + crop_side / 2.0)
    y2 = int(center_y + crop_side / 2.0)

    # Reject incomplete crops instead of silently clipping them.
    if (
        x1 < 0
        or y1 < 0
        or x2 > frame_width
        or y2 > frame_height
    ):
        return None

    face_crop = frame[
        y1:y2,
        x1:x2
    ]

    if face_crop.size == 0:
        return None

    return face_crop


def validate_face_image(face_image):
    
    Checks whether the cropped face image has acceptable:
    - resolution;
    - sharpness;
    - brightness.

    Returns:
        valid: bool
        reason: str
    

    if face_image is None or face_image.size == 0:
        return False, "empty face crop"

    face_height, face_width = face_image.shape[:2]

    if min(face_height, face_width) < MIN_FACE_SIZE_PIXELS:
        return (
            False,
            "cropped face too small: "
            f"{face_width} x {face_height}"
        )

    gray_face = cv2.cvtColor(
        face_image,
        cv2.COLOR_BGR2GRAY
    )

    # Higher values normally mean a sharper image.
    blur_score = cv2.Laplacian(
        gray_face,
        cv2.CV_64F
    ).var()

    brightness = float(
        gray_face.mean()
    )

    if blur_score < MIN_BLUR_SCORE:
        return (
            False,
            "face too blurry: "
            f"{blur_score:.1f}"
        )

    if brightness < MIN_BRIGHTNESS:
        return (
            False,
            "face too dark: "
            f"{brightness:.1f}"
        )

    if brightness > MAX_BRIGHTNESS:
        return (
            False,
            "face overexposed: "
            f"{brightness:.1f}"
        )

    return (
        True,
        "valid "
        f"(blur={blur_score:.1f}, "
        f"brightness={brightness:.1f})"
    )


def send_invalid_face_state(reason):
    
    A person is visible, but the current face image is not reliable
    enough for a new emotion prediction.

    The previously confirmed emotion is preserved.
    

    global last_sent_time

    now = time.time()

    print(
        f"[CAMERA] Face rejected: {reason}",
        flush=True
    )

    if now - last_sent_time > SEND_INTERVAL:
        data = {
            "person_in_frame": True,
            "person_emotion": confirmed_emotion,
            "all_emotions": {}
        }

        sock.sendto(
            json.dumps(data).encode("utf-8"),
            (UDP_IP, UDP_PORT)
        )

        last_sent_time = now


# =================================================================
# MAIN CAMERA LOOP
# =================================================================
while True:
    ret, frame = cap.read()

    if not ret:
        continue

    rgb = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    results = face_detector.process(rgb)

    if results.detections:
        face_detected = True

        # Choose the largest and most confident detected face.
        detection = max(
            results.detections,
            key=detection_priority
        )

        # ---------------------------------------------------------
        # Validate face direction, size and geometry
        # ---------------------------------------------------------
        face_is_valid, rejection_reason = validate_face_view(
            detection,
            frame
        )

        if not face_is_valid:
            send_invalid_face_state(
                rejection_reason
            )

            # Invalid frames must not enter smoothing/history.
            continue

        bbox = detection.location_data.relative_bounding_box

        # ---------------------------------------------------------
        # Create improved square crop
        # ---------------------------------------------------------
        face_img = crop_center_face(
            frame,
            bbox
        )

        if face_img is None:
            send_invalid_face_state(
                "crop would extend outside the image"
            )

            continue

        # ---------------------------------------------------------
        # Validate crop sharpness and lighting
        # ---------------------------------------------------------
        image_is_valid, image_reason = validate_face_image(
            face_img
        )

        if not image_is_valid:
            send_invalid_face_state(
                image_reason
            )

            # Invalid frames must not enter smoothing/history.
            continue

        now = time.time()

        if now - last_sent_time > SEND_INTERVAL:
            encode_success, img_encoded = cv2.imencode(
                ".jpg",
                face_img
            )

            if not encode_success:
                print(
                    "[CAMERA] Could not encode face crop",
                    flush=True
                )

                continue

            try:
                response = requests.post(
                    DEEPFACE_URL,
                    files={
                        "image": img_encoded.tobytes()
                    },
                    timeout=20
                )

                response_data = response.json()

                emotion_data = response_data.get(
                    "emotion",
                    {}
                )

                # =================================================
                # EMOTION AMPLIFIER
                # Kept exactly as part of your current system.
                # =================================================
                if isinstance(emotion_data, dict):

                    if "neutral" in emotion_data:
                        emotion_data["neutral"] *= 0.2

                    if "happy" in emotion_data:
                        emotion_data["happy"] *= 0.6

                    if "sad" in emotion_data:
                        emotion_data["sad"] *= 6.0

                    if "disgust" in emotion_data:
                        emotion_data["disgust"] *= 4.0

                    if "fear" in emotion_data:
                        emotion_data["fear"] *= 4.0

                    if "surprise" in emotion_data:
                        emotion_data["surprise"] *= 1.5

                # =================================================
                # EMOTION SMOOTHING
                # Kept unchanged.
                # =================================================
                if isinstance(emotion_data, dict):
                    emotion_buffer.append(
                        emotion_data
                    )

                    smoothed_emotions = {}

                    for key in emotion_data.keys():
                        smoothed_emotions[key] = round(
                            sum(
                                previous_result.get(key, 0)
                                for previous_result in emotion_buffer
                                if isinstance(
                                    previous_result,
                                    dict
                                )
                            )
                            / len(emotion_buffer),
                            2
                        )

                    smoothed_dominant = (
                        max(
                            smoothed_emotions,
                            key=smoothed_emotions.get
                        )
                        if smoothed_emotions
                        else "none"
                    )

                else:
                    emotion_buffer.append(
                        emotion_data
                    )

                    smoothed_dominant = Counter(
                        emotion_buffer
                    ).most_common(1)[0][0]

                    smoothed_emotions = {
                        smoothed_dominant: 100.0
                    }

                # =================================================
                # ONE-SECOND LOCK WITH 90% AGREEMENT
                # Kept unchanged.
                # =================================================
                candidate_history.append(
                    (
                        now,
                        smoothed_dominant
                    )
                )

                # Remove candidate results older than one second.
                while (
                    candidate_history
                    and now - candidate_history[0][0]
                    > EMOTION_CONFIRM_TIME
                ):
                    candidate_history.popleft()

                # Require at least 10 valid samples.
                if len(candidate_history) >= 10:
                    counts = Counter(
                        emotion
                        for _, emotion in candidate_history
                    )

                    top_emotion, top_count = (
                        counts.most_common(1)[0]
                    )

                    agreement_ratio = (
                        top_count
                        / len(candidate_history)
                    )

                    if agreement_ratio >= 0.90:
                        confirmed_emotion = top_emotion

                print(
                    "[CAMERA] "
                    f"Confirmed: {confirmed_emotion} "
                    f"(Candidate: {smoothed_dominant}) "
                    f"| Crop: {face_img.shape[1]}x"
                    f"{face_img.shape[0]} "
                    f"| {image_reason}",
                    flush=True
                )

                data = {
                    "person_in_frame": face_detected,
                    "person_emotion": confirmed_emotion,
                    "all_emotions": smoothed_emotions
                }

                sock.sendto(
                    json.dumps(data).encode("utf-8"),
                    (UDP_IP, UDP_PORT)
                )

                last_sent_time = now

            except Exception as e:
                print(
                    "Docker error:",
                    e
                )

    else:
        print(
            "No face detected",
            flush=True
        )

        # Reset the confirmation candidates if the person leaves.
        candidate_history.clear()

        data = {
            "person_in_frame": False,
            "person_emotion": "none",
            "all_emotions": {}
        }

        sock.sendto(
            json.dumps(data).encode("utf-8"),
            (UDP_IP, UDP_PORT)
        )



import cv2
import mediapipe as mp
import requests
import numpy as np
import time
import subprocess
from collections import deque, Counter
import socket
import json

# Setup the invisible UDP bridge
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
UDP_IP = "10.0.0.114" # Local memory IP
UDP_PORT = 5005

def start_docker_server(container_name, script_path):
    print("Initiating DeepFace GPU server inside Docker...")
    command = ["docker", "exec", "-d", container_name, "python3", script_path]
    try:
        subprocess.run(command, check=True)
        print("Server triggered successfully!")
        print("Waiting 10 seconds for the Flask server and GPU model to load...")
        time.sleep(10) 
    except subprocess.CalledProcessError as e:
        print(f"Error starting the server! Is the container running? Error: {e}")

emotion_buffer = deque(maxlen=30)

# --- NEW: 1-Second Lock Variables ---
confirmed_emotion = "neutral"  # The emotion the robot is actually acting on
candidate_history = deque()    # Tracks the history of emotions for the margin check
EMOTION_CONFIRM_TIME = 1.0     # Seconds required to lock in an emotion
# ------------------------------------

DEEPFACE_URL = "http://localhost:5000/predict"
mp_face = mp.solutions.face_detection
face_detector = mp_face.FaceDetection(min_detection_confidence=0.8)

start_docker_server("vision", "/vision_server.py")
 
cap = cv2.VideoCapture('/dev/v4l/by-id/usb-Jieli_Technology_USB_Composite_Device-video-index0')

last_sent_time = 0
SEND_INTERVAL = 0.05

def crop_center_face(frame, bbox, margin=0.4):
    h, w, _ = frame.shape
    x = int(bbox.xmin * w)
    y = int(bbox.ymin * h)
    bw = int(bbox.width * w)
    bh = int(bbox.height * h)

    mx = int(bw * margin)
    my = int(bh * margin)

    x1 = max(0, x - mx)
    y1 = max(0, y - my)
    x2 = min(w, x + bw + mx)
    y2 = min(h, y + bh + my)

    face_crop = frame[y1:y2, x1:x2]

    fh, fw, _ = face_crop.shape
    size = min(fh, fw)

    cx, cy = fw // 2, fh // 2
    face_square = face_crop[
        max(0, cy - size // 2):cy + size // 2,
        max(0, cx - size // 2):cx + size // 2
    ]
    return face_square

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_detector.process(rgb)

    if results.detections:
        face_detected = True
        detection = results.detections[0]
        bbox = detection.location_data.relative_bounding_box

        face_img = crop_center_face(frame, bbox)

        now = time.time()
        if now - last_sent_time > SEND_INTERVAL:
            _, img_encoded = cv2.imencode(".jpg", face_img)

            try:
                response = requests.post(
                    DEEPFACE_URL,
                    files={"image": img_encoded.tobytes()},
                    timeout=20
                )

                response_data = response.json()
                emotion_data = response_data.get("emotion", {})
                
                # ---- NEW: EMOTION AMPLIFIER ----
                if isinstance(emotion_data, dict):
                    # 1. Heavily penalize Neutral (Cut its score by 80%),  Boost the underrepresented emotions
                    if 'neutral' in emotion_data:
                        emotion_data['neutral'] *= 0.2
                    if 'happy' in emotion_data:
                        emotion_data['happy'] *= 0.6
                    if 'sad' in emotion_data:          
                        emotion_data['sad'] *= 6.0      
                    if 'disgust' in emotion_data:
                        emotion_data['disgust'] *= 4.0  
                    if 'fear' in emotion_data:
                        emotion_data['fear'] *= 4.0
                    if 'surprise' in emotion_data:
                        emotion_data['surprise'] *= 1.5
                # --------------------------------

                # ---- EMOTION SMOOTHING START ----
                if isinstance(emotion_data, dict):
                    emotion_buffer.append(emotion_data)
                    smoothed_emotions = {}
                    for key in emotion_data.keys():
                        smoothed_emotions[key] = round(sum(d.get(key, 0) for d in emotion_buffer if isinstance(d, dict)) / len(emotion_buffer), 2)
                    smoothed_dominant = max(smoothed_emotions, key=smoothed_emotions.get) if smoothed_emotions else "none"
                else:
                    emotion_buffer.append(emotion_data)
                    smoothed_dominant = Counter(emotion_buffer).most_common(1)[0][0]
                    smoothed_emotions = {smoothed_dominant: 100.0}
                # ---- EMOTION SMOOTHING END ----

                # ---- TIME LOCK WITH 90% MARGIN START ----
                candidate_history.append((now, smoothed_dominant))
                
                # Remove frames older than EMOTION_CONFIRM_TIME
                while candidate_history and now - candidate_history[0][0] > EMOTION_CONFIRM_TIME:
                    candidate_history.popleft()
                    
                # Ensure we have a decent sample size before checking percentages
                if len(candidate_history) >= 10:
                    counts = Counter([emo for _, emo in candidate_history])
                    top_emotion, top_count = counts.most_common(1)[0]
                    
                    # If 90% or more of the frames in the last second are the same, lock it in
                    if (top_count / len(candidate_history)) >= 0.90:
                        confirmed_emotion = top_emotion
                # ---- TIME LOCK WITH 90% MARGIN END ----

                print(f"[CAMERA] Confirmed: {confirmed_emotion} (Candidate: {smoothed_dominant})", flush=True)
                
                data = {
                    "person_in_frame": face_detected, 
                    "person_emotion": confirmed_emotion, # Send the locked emotion to the Brain
                    "all_emotions": smoothed_emotions   
                }
                
                sock.sendto(json.dumps(data).encode('utf-8'), (UDP_IP, UDP_PORT))
                last_sent_time = now

            except Exception as e:
                print("Docker error:", e)

    else:
        print("No face detected")
        
        # Reset the candidate history if they leave the camera frame
        candidate_history.clear()
        
        data = {
            "person_in_frame": False,
            "person_emotion": "none",
            "all_emotions": {}
        }
        sock.sendto(json.dumps(data).encode('utf-8'), (UDP_IP, UDP_PORT))


----------------------------------------------------------------
final code 
import cv2
import mediapipe as mp
import requests
import numpy as np
import time
import subprocess
from collections import deque, Counter
import socket
import json

# Setup the invisible UDP bridge
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
UDP_IP = "10.0.0.114" # Local memory IP
UDP_PORT = 5005

def start_docker_server(container_name, script_path):
    print("Initiating DeepFace GPU server inside Docker...")
    command = ["docker", "exec", "-d", container_name, "python3", script_path]
    try:
        subprocess.run(command, check=True)
        print("Server triggered successfully!")
        print("Waiting 10 seconds for the Flask server and GPU model to load...")
        time.sleep(10) 
    except subprocess.CalledProcessError as e:
        print(f"Error starting the server! Is the container running? Error: {e}")

emotion_buffer = deque(maxlen=30)

# --- NEW: 2-Second Lock Variables ---
confirmed_emotion = "neutral"  # The emotion the robot is actually acting on
candidate_emotion = None       # The emotion trying to prove itself
candidate_start_time = 0
EMOTION_CONFIRM_TIME = 1.0     # Seconds required to lock in an emotion
# ------------------------------------

DEEPFACE_URL = "http://localhost:5000/predict"
mp_face = mp.solutions.face_detection
face_detector = mp_face.FaceDetection(min_detection_confidence=0.8)

start_docker_server("vision", "/vision_server.py")
 
cap = cv2.VideoCapture('/dev/v4l/by-id/usb-Jieli_Technology_USB_Composite_Device-video-index0')

last_sent_time = 0
SEND_INTERVAL = 0.05

def crop_center_face(frame, bbox, margin=0.4):
    h, w, _ = frame.shape
    x = int(bbox.xmin * w)
    y = int(bbox.ymin * h)
    bw = int(bbox.width * w)
    bh = int(bbox.height * h)

    mx = int(bw * margin)
    my = int(bh * margin)

    x1 = max(0, x - mx)
    y1 = max(0, y - my)
    x2 = min(w, x + bw + mx)
    y2 = min(h, y + bh + my)

    face_crop = frame[y1:y2, x1:x2]

    fh, fw, _ = face_crop.shape
    size = min(fh, fw)

    cx, cy = fw // 2, fh // 2
    face_square = face_crop[
        max(0, cy - size // 2):cy + size // 2,
        max(0, cx - size // 2):cx + size // 2
    ]
    return face_square

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_detector.process(rgb)

    if results.detections:
        face_detected = True
        detection = results.detections[0]
        bbox = detection.location_data.relative_bounding_box

        face_img = crop_center_face(frame, bbox)

        now = time.time()
        if now - last_sent_time > SEND_INTERVAL:
            _, img_encoded = cv2.imencode(".jpg", face_img)

            try:
                response = requests.post(
                    DEEPFACE_URL,
                    files={"image": img_encoded.tobytes()},
                    timeout=20
                )

                response_data = response.json()
                emotion_data = response_data.get("emotion", {})
                
                # ---- NEW: EMOTION AMPLIFIER ----
                if isinstance(emotion_data, dict):
                    # 1. Heavily penalize Neutral (Cut its score by 80%),  Boost the underrepresented emotions
                    if 'neutral' in emotion_data:
                        emotion_data['neutral'] *= 0.2
                    if 'happy' in emotion_data:
                        emotion_data['happy'] *= 0.6
                    if 'sad' in emotion_data:          
                        emotion_data['sad'] *= 6.0      
                    if 'disgust' in emotion_data:
                        emotion_data['disgust'] *= 4.0  
                    if 'fear' in emotion_data:
                        emotion_data['fear'] *= 4.0
                    if 'surprise' in emotion_data:
                        emotion_data['surprise'] *= 1.5
                # --------------------------------

                # ---- EMOTION SMOOTHING START ----
                if isinstance(emotion_data, dict):
                    emotion_buffer.append(emotion_data)
                    smoothed_emotions = {}
                    for key in emotion_data.keys():
                        smoothed_emotions[key] = round(sum(d.get(key, 0) for d in emotion_buffer if isinstance(d, dict)) / len(emotion_buffer), 2)
                    smoothed_dominant = max(smoothed_emotions, key=smoothed_emotions.get) if smoothed_emotions else "none"
                else:
                    emotion_buffer.append(emotion_data)
                    smoothed_dominant = Counter(emotion_buffer).most_common(1)[0][0]
                    smoothed_emotions = {smoothed_dominant: 100.0}
                # ---- EMOTION SMOOTHING END ----

                # ---- 2-SECOND TIME LOCK START ----
                if smoothed_dominant == candidate_emotion:
                    # If the AI has seen this emotion consistently for 2 seconds, lock it in!
                    if now - candidate_start_time >= EMOTION_CONFIRM_TIME:
                        confirmed_emotion = candidate_emotion
                else:
                    # The emotion changed! Reset the candidate and start the timer over.
                    candidate_emotion = smoothed_dominant
                    candidate_start_time = now
                # ---- 2-SECOND TIME LOCK END ----

                print(f"[CAMERA] Confirmed: {confirmed_emotion} (Candidate: {smoothed_dominant})", flush=True)
                
                data = {
                    "person_in_frame": face_detected, 
                    "person_emotion": confirmed_emotion, # Send the locked emotion to the Brain
                    "all_emotions": smoothed_emotions   
                }
                
                sock.sendto(json.dumps(data).encode('utf-8'), (UDP_IP, UDP_PORT))
                last_sent_time = now

            except Exception as e:
                print("Docker error:", e)

    else:
        print("No face detected")
        
        # Reset the candidate timer if they leave the camera frame
        candidate_emotion = None
        
        data = {
            "person_in_frame": False,
            "person_emotion": "none",
            "all_emotions": {}
        }
        sock.sendto(json.dumps(data).encode('utf-8'), (UDP_IP, UDP_PORT))





#this code works compeletely with all 7 emotion categories 
import cv2
import mediapipe as mp
import requests
import numpy as np
import time
import subprocess
from collections import deque, Counter
import statistics
import socket
import json

# Setup the invisible UDP bridge
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
UDP_IP = "10.0.0.114" # Local memory IP
UDP_PORT = 5005

# ---- 2. ADDED DOCKER STARTUP FUNCTION ----
def start_docker_server(container_name, script_path):
    print("Initiating DeepFace GPU server inside Docker...")
    command = ["docker", "exec", "-d", container_name, "python3", script_path]
    try:
        subprocess.run(command, check=True)
        print("Server triggered successfully!")
        print("Waiting 10 seconds for the Flask server and GPU model to load...")
        time.sleep(10) 
    except subprocess.CalledProcessError as e:
        print(f"Error starting the server! Is the container running? Error: {e}")
# ------------------------------------------

emotion_buffer = deque(maxlen=7)
age_buffer = deque(maxlen=15)

DEEPFACE_URL = "http://localhost:5000/predict"

mp_face = mp.solutions.face_detection
face_detector = mp_face.FaceDetection(min_detection_confidence=0.6)

# ---- 3. TRIGGER DOCKER SERVER HERE BEFORE CAMERA OPENS ----
# IMPORTANT: Change these two strings to match your actual container name and path!
start_docker_server("vision", "/vision_server.py")
# -----------------------------------------------------------
 
cap = cv2.VideoCapture('/dev/v4l/by-id/usb-Jieli_Technology_USB_Composite_Device-video-index0')

last_sent_time = 0
SEND_INTERVAL = 0.1  # prevents flooding Docker

def crop_center_face(frame, bbox, margin=0.2):
    h, w, _ = frame.shape

    x = int(bbox.xmin * w)
    y = int(bbox.ymin * h)
    bw = int(bbox.width * w)
    bh = int(bbox.height * h)

    # add margin around face
    mx = int(bw * margin)
    my = int(bh * margin)

    x1 = max(0, x - mx)
    y1 = max(0, y - my)
    x2 = min(w, x + bw + mx)
    y2 = min(h, y + bh + my)

    face_crop = frame[y1:y2, x1:x2]

    # center crop to square (important for DeepFace stability)
    fh, fw, _ = face_crop.shape
    size = min(fh, fw)

    cx, cy = fw // 2, fh // 2
    face_square = face_crop[
        max(0, cy - size // 2):cy + size // 2,
        max(0, cx - size // 2):cx + size // 2
    ]

    return face_square

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_detector.process(rgb)

    if results.detections:
        # take strongest face
        face_detected = True
        detection = results.detections[0]
        bbox = detection.location_data.relative_bounding_box

        face_img = crop_center_face(frame, bbox)

        # avoid sending too frequently
        now = time.time()
        if now - last_sent_time > SEND_INTERVAL:

            _, img_encoded = cv2.imencode(".jpg", face_img)

            try:
                response = requests.post(
                    DEEPFACE_URL,
                    files={"image": img_encoded.tobytes()},
                    timeout=20
                )

                response_data = response.json()
                emotion_data = response_data.get("emotion", {})
                age_data = response_data.get("age", 0)

# ---- SMOOTHING START ----
                if isinstance(emotion_data, dict):
                    # Emotion Smoothing
                    emotion_buffer.append(emotion_data)
                    smoothed_emotions = {}
                    for key in emotion_data.keys():
                        smoothed_emotions[key] = round(sum(d.get(key, 0) for d in emotion_buffer if isinstance(d, dict)) / len(emotion_buffer), 2)
                    smoothed_dominant = max(smoothed_emotions, key=smoothed_emotions.get) if smoothed_emotions else "none"
                else:
                    emotion_buffer.append(emotion_data)
                    smoothed_dominant = Counter(emotion_buffer).most_common(1)[0][0]
                    smoothed_emotions = {smoothed_dominant: 100.0}

                # Age Smoothing (NEW)
                if age_data > 0:
                    age_buffer.append(age_data)
                
                # Use the median to ignore crazy outliers (like suddenly guessing 60 when you are 25)
                smoothed_age = int(statistics.median(age_buffer)) if age_buffer else 0
# ---- SMOOTHING END ----

                print(f"[CAMERA]  | Dominant: {smoothed_dominant} | All: {smoothed_emotions}", flush=True)
                
                data = {
                    "person_in_frame": face_detected, 
                    "person_emotion": smoothed_dominant, 
                    "all_emotions": smoothed_emotions,   
                    
                }
# ---- SMOOTHING END ----

               # print(f"Age: {age_data} | Dominant: {smoothed_dominant} | All Emotions: {smoothed_emotions}", flush=True)
                # print(response.json()) # (Optional) Kept hidden to keep terminal clean
                
                data = {
                    "person_in_frame": face_detected, 
                    "person_emotion": smoothed_dominant, # Keep backward compatibility for your brain process
                    "all_emotions": smoothed_emotions,   # NEW: Dictionary of all 7 emotions
                    "person_age": age_data               # NEW: Age of the person
                }
                
                # Shout the data to the robot's Blackboard
                sock.sendto(json.dumps(data).encode('utf-8'), (UDP_IP, UDP_PORT))
                last_sent_time = now
                
                current_time = time.time()

            except Exception as e:
                print("Docker error:", e)

    else:
        print("No face detected")
        data = {
            "person_in_frame": False,
            "person_emotion": "none",
            "all_emotions": {},
            "person_age": 0
        }
        sock.sendto(json.dumps(data).encode('utf-8'), (UDP_IP, UDP_PORT))"""























