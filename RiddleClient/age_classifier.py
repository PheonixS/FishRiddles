import signal
import sys
import uuid
import cv2
import numpy as np
import face_recognition
from picamera2 import Picamera2
import time
import json
import os
from enum import Enum


class AgeClassifierStates(Enum):
    NO_FACE_DETECTED = 0x30


class NumpyArrayEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(NumpyArrayEncoder, self).default(obj)


class NumpyArrayDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        # Call the parent constructor
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):
        # Check if the object is a list and convert it back to a NumPy array
        if isinstance(obj, list):
            try:
                return np.array(obj)
            except:
                pass  # Let it fall through if it's not convertible
        return obj

class AgeClassifier:
    def __init__(self, queue, face_model_path: str, face_proto_path: str,
                 age_model_path: str, age_proto_path: str,
                 json_path: str = 'recognized_faces.json',
                 frame_width: int = 320, frame_height: int = 240,
                 process_interval: int = 5, timeout_duration: int = 10):
        """
        Initializes the class responsible for processing video frames and performing face detection and age classification.

        Args:
            queue : A queue for communication between processes.
            face_model_path (str): Path to the pre-trained model file for face detection.
            face_proto_path (str): Path to the protocol buffer file for face detection architecture.
            age_model_path (str): Path to the pre-trained model file for age classification.
            age_proto_path (str): Path to the protocol buffer file for age classification architecture.
            json_path (str, optional): Path to the JSON file where recognized faces are stored. Default is 'recognized_faces.json'.
            frame_width (int, optional): The width of the video frames to process. Default is 320 pixels.
            frame_height (int, optional): The height of the video frames to process. Default is 240 pixels.
            process_interval (int, optional): The number of frames to skip between processing steps to optimize performance. Default is 5.
            timeout_duration (int, optional): Timeout duration in seconds before the process consider person leaving the camera zone. Default is 10 seconds.
        """
        self.queue = queue
        # Load the age categories
        self.AGE_BUCKETS = ['(0-2)', '(4-6)', '(8-12)', '(15-20)',
                            '(25-32)', '(38-43)', '(48-53)', '(60-100)']

        # Load the models
        self.face_net = cv2.dnn.readNetFromCaffe(
            face_proto_path, face_model_path)
        self.age_net = cv2.dnn.readNetFromCaffe(age_proto_path, age_model_path)

        # Initialize picamera2
        self.picam2 = Picamera2()
        config = self.picam2.create_preview_configuration(
            main={"format": 'RGB888', "size": (frame_width, frame_height)})
        self.picam2.configure(config)
        self.picam2.start()

        # Frame processing variables
        self.process_interval = process_interval
        self.frame_count = 0

        # For checking if it's the same person
        # Adjust as needed for stricter/looser matching
        self.face_similarity_threshold = 0.6

        # Path for saving recognized data
        self.json_path = json_path

        self.timeout_duration = timeout_duration

        # Load previously saved faces (if any)
        self.recognized_faces = self.load_recognized_faces()

        self.last_detection_time = time.time()
        self.exiting = False

        def handle_sigterm(signum, frame):
            print("AgeClassifier: Received SIGTERM or SIGINT. Shutting down gracefully...")
            self.exiting = True

        signal.signal(signal.SIGTERM, handle_sigterm)
        signal.signal(signal.SIGINT, handle_sigterm)


    def send_state(self, state: AgeClassifierStates):
        self.queue.put({'state': state})

    def send_detected_metadata(self, data: dict, new: bool):
        ret = {
            "age": str(data['age']),
            "confidence": float(data['confidence']),
            "id": str(data['id']),
            "flag_new": bool(new),
        }
        self.queue.put(ret)

    def classify(self):
        try:
            while not self.exiting:
                # Capture frame-by-frame
                frame = self.picam2.capture_array()
                if frame is None:
                    print("Can't receive frame (stream end?). Exiting ...")
                    break

                self.frame_count += 1
                if self.frame_count % self.process_interval != 0:
                    continue  # Skip this frame

                # Prepare the frame for face detection
                h, w = frame.shape[:2]
                blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)),
                                             1.0, (300, 300), (104.0, 177.0, 123.0))

                # Detect faces
                self.face_net.setInput(blob)
                detections = self.face_net.forward()

                face_detected = False
                for i in range(detections.shape[2]):
                    confidence = detections[0, 0, i, 2]
                    if confidence > 0.7:  # Confidence threshold for face detection
                        face_detected = True
                        self.last_detection_time = time.time()
                        # Get face coordinates
                        box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                        (startX, startY, endX, endY) = box.astype("int")
                        face = frame[startY:endY, startX:endX]

                        # Check if face ROI is valid
                        if face.size == 0:
                            continue

                        # Convert face to RGB (required for face_recognition)
                        rgb_face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)

                        # Get face encoding
                        current_face_encodings = face_recognition.face_encodings(
                            rgb_face)
                        if current_face_encodings:
                            current_face_encoding = current_face_encodings[0]

                            # If previous face encoding exists, compare
                            if self.recognized_faces is not None:
                                matches = face_recognition.compare_faces(
                                    [i['encoding'] for i in self.recognized_faces], current_face_encoding, self.face_similarity_threshold)
                                if any(matches):
                                    previousPerson = self.recognized_faces[matches.index(
                                        True)]
                                    self.send_detected_metadata(
                                        previousPerson, False)
                                    # print(
                                    #     f"Same person detected: {previousPerson['id']}, {previousPerson['age']}, {previousPerson['confidence']}")
                                else:
                                    print("Different person detected")

                                    # Prepare the face ROI for age estimation
                                    face_blob = cv2.dnn.blobFromImage(face, 1.0, (227, 227),
                                                                      (78.4263377603, 87.7689143744,
                                                                       114.895847746),
                                                                      swapRB=False)

                                    # Predict the age
                                    self.age_net.setInput(face_blob)
                                    age_preds = self.age_net.forward()
                                    age_index = age_preds[0].argmax()
                                    age = self.AGE_BUCKETS[age_index]
                                    age_confidence = age_preds[0][age_index]

                                    print(
                                        f"Current age confidence: {age_confidence}")
                                    if age_confidence > 0.7:
                                        # Save the face encoding and age data
                                        id = str(uuid.uuid4())
                                        self.save_recognized_face(
                                            current_face_encoding, age, age_confidence, id)
                                        self.send_detected_metadata(
                                            {'age': age, 'confidence': confidence, 'id': id}, True)
                                        # FIXME: Hack which translates base64 back to NumPy
                                        self.recognized_faces = self.load_recognized_faces()

                                        # Prepare label text
                                        label_text = f"Age: {age} ({age_confidence * 100:.1f}%)"

                                        # Log the result
                                        print(label_text)
                                        break

                # Check if the timeout duration has been reached without detecting a face
                if not face_detected and (time.time() - self.last_detection_time) > self.timeout_duration:
                    print(
                        f"No face detected for {self.timeout_duration} seconds.")
                    self.send_state(AgeClassifierStates.NO_FACE_DETECTED)
                    self.last_detection_time = time.time()

                time.sleep(0.5)
        finally:
            # Release resources
            self.picam2.stop()

    def save_recognized_face(self, face_encoding, age, confidence, id):
        """Save the face encoding, age, and confidence to JSON."""
        # Add the new face encoding and its details
        self.recognized_faces.append({
            "encoding": face_encoding,
            "age": str(age),  # Convert age to string (if needed)
            # Ensure confidence is a native Python float
            "confidence": float(confidence),
            "id": id,
        })

        # Save the updated recognized faces to the JSON file
        with open(self.json_path, 'w') as f:
            json.dump(self.recognized_faces, f,
                      indent=4, cls=NumpyArrayEncoder)

    def load_recognized_faces(self) -> list:
        """Load the face encodings and associated data from JSON."""
        if os.path.exists(self.json_path):
            with open(self.json_path, 'r') as f:
                try:
                    return json.load(f, cls=NumpyArrayDecoder)
                except json.JSONDecodeError:
                    return list()
        return list()
