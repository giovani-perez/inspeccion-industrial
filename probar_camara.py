import cv2

cap = cv2.VideoCapture("http://192.168.100.19:4747/video")  # pon tu IP real de DroidCam
ok, frame = cap.read()
print("¿Llegó imagen?", ok, frame.shape if ok else None)
cap.release()