# Face detection model

| | |
| --- | --- |
| File | `face_detection_yunet_2023mar.onnx` |
| Model | YuNet (face detector), release `2023mar`, fixed-input variant |
| Source | [opencv/opencv_zoo, `models/face_detection_yunet`](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) |
| Direct file | https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx |
| SHA-256 | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` |
| License | MIT (copyright Shiqi Yu); full text in `LICENSE-yunet` |
| Runtime | `cv2.FaceDetectorYN` from `opencv-python==4.12.0.88` |

The model is committed so the app runs offline with no downloads. The SHA-256 is stored in
every detection cache file, so replacing this file automatically invalidates old caches.

This is the release verified to load and run with the pinned OpenCV. If the model or OpenCV
version changes, re-run the tests and the debug script before trusting the new combination.
