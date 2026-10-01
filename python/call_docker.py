import cv2
import requests

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    _, img = cv2.imencode(".jpg", frame)

    response = requests.post(
        "http://localhost:5000/predict",
        files={"image": img.tobytes()}
    )

    print("STATUS:", response.status_code)

    print("TEXT:", response.text)

    try:
        print("EMOTION:", response.json()["emotion"])
    except:
        print("No JSON received")