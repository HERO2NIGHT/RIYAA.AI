import cv2
import mediapipe as mp
import time

mp_hands = mp.solutions.hands

def start_camera_thread(avatar_state):
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

    hands = mp_hands.Hands(
        model_complexity=0,
        max_num_hands=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    x_history = []
    last_wave_time = 0

    print("Camera watching for waves...")

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        if results.multi_hand_landmarks:
            wrist = results.multi_hand_landmarks[0].landmark[0]
            x_history.append(wrist.x)
            if len(x_history) > 15:
                x_history.pop(0)

            if len(x_history) == 15:
                reversals = 0
                direction = None
                for i in range(1, len(x_history)):
                    diff = x_history[i] - x_history[i - 1]
                    if abs(diff) < 0.008:
                        continue
                    new_direction = "right" if diff > 0 else "left"
                    if direction and new_direction != direction:
                        reversals += 1
                    direction = new_direction

                if reversals >= 3 and (time.time() - last_wave_time) > 3:
                    print("WAVE DETECTED!")   # <-- just a print for now, no avatar action yet
                    avatar_state["user_waving"] = True
                    last_wave_time = time.time()
                    x_history.clear()
        else:
            x_history.clear()

        if avatar_state.get("user_waving") and time.time() - last_wave_time > 2:
            avatar_state["user_waving"] = False

        time.sleep(0.05)
