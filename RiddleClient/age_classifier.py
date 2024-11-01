import signal
import sys
import uuid
import cv2
import numpy as np
import face_recognition
from picamera2 import Picamera2
import time
import json
from enum import Enum

from pydantic import ValidationError

from models.history import *
from models.profile import *
from models.responses import *


class AgeClassifierStates(Enum):
    NO_FACE_DETECTED = 0x30

class AgeClassifier:
    def __init__(self, queue, face_model_path: str, face_proto_path: str,
                 age_model_path: str, age_proto_path: str,
                 json_path: str = 'RiddleClient/recognized_faces.json',
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
        self.data = self.load()

        self.last_detection_time = time.time()
        self.exiting = False

        def handle_sigterm(signum, frame):
            print(
                "AgeClassifier: Received SIGTERM or SIGINT. Shutting down gracefully...")
            self.exiting = True

        signal.signal(signal.SIGTERM, handle_sigterm)
        signal.signal(signal.SIGINT, handle_sigterm)

    def process_new_person(self, face, confidence, current_face_encoding):
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

        print(f"Current age confidence: {age_confidence}")
        if age_confidence > 0.6:
            player_profile = UserProfile(
                id=uuid.uuid4(),
                age=age,
                confidence=confidence,
                encoding=current_face_encoding,
                flag_new=True,
            )
            self.save(player_profile)
            self.queue.put(player_profile.model_dump())
        else:
            print(f"not enough confidence to process user yet")

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
                    if confidence > 0.6:  # Confidence threshold for face detection
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

                            # no data saved yet, recognize new person
                            if len(self.data.root) == 0:
                                print("Nothing in the registry yet - assuming it's new person")
                                self.process_new_person(face, confidence, current_face_encoding)
                            elif len(self.data.root) > 0:
                                matches = face_recognition.compare_faces(
                                    [i.encoding for i in self.data.root],
                                    current_face_encoding,
                                    self.face_similarity_threshold)
                                # if match - send old information
                                if any(matches):
                                    previousPerson = self.data.root[matches.index(
                                        True)]
                                    profile = UserProfile(
                                        id=previousPerson.id,
                                        age=previousPerson.age,
                                        confidence=previousPerson.confidence,
                                        flag_new=False,
                                        encoding=current_face_encoding,
                                    )
                                    print(f"same person detected: {previousPerson.id}")
                                    self.queue.put(profile.model_dump())
                                else:
                                    print("New person detected")
                                    self.process_new_person(face, confidence, current_face_encoding)
                                    break

                # Check if the timeout duration has been reached without detecting a face
                if not face_detected and (time.time() - self.last_detection_time) > self.timeout_duration:
                    self.queue.put(
                        {'state': AgeClassifierStates.NO_FACE_DETECTED})
                    self.last_detection_time = time.time()

                time.sleep(0.5)
        finally:
            # Release resources
            self.picam2.stop()

    def save(self, profile: UserProfile):
        """Save user profile to JSON"""

        self.data.root.append(profile)

        with open(self.json_path, 'w') as f:
            f.write(self.data.model_dump_json(indent=4, exclude={'flag_new'}))

    def load(self) -> UserProfiles:
        try:
            with open(self.json_path, 'r') as f:
                data = f.read()
            return UserProfiles.model_validate_json(data)
        except (FileNotFoundError, ValidationError):
            print("UserProfiles does not exists or corrupted, initializing empty.")
            return UserProfiles(root=[])
