from flask import Flask, request, jsonify
import cv2
import numpy as np
from deepface import DeepFace

app = Flask(__name__)

@app.route("/predict", methods=["POST"])
def predict():

    file = request.files["image"]
    npimg = np.frombuffer(file.read(), np.uint8)
    frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

    result = DeepFace.analyze(
    frame,
    actions=['emotion'],
    detector_backend='skip',
    #detector_backend='retinaface',  # or 'mtcnn'
    enforce_detection=False
    )

    emotion = result[0]['dominant_emotion']

    return jsonify({"emotion": emotion})

app.run(host="0.0.0.0", port=5000)
