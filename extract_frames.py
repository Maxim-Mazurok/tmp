import cv2
import os
import glob

SKIP_SECONDS = 15

videos = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "*.mp4")))

for video_path in videos:
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    output_dir = os.path.join(os.path.dirname(video_path), video_name)
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps

    start_frame = int(SKIP_SECONDS * fps)
    end_frame = int((duration - SKIP_SECONDS) * fps)

    print(f"Processing: {video_name}")
    print(f"  FPS: {fps}, Total frames: {total_frames}, Duration: {duration:.1f}s")
    print(f"  Extracting frames {start_frame} to {end_frame} ({end_frame - start_frame} frames)")

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frame_num = start_frame
    saved = 0

    while frame_num < end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        out_path = os.path.join(output_dir, f"{frame_num:06d}.png")
        cv2.imwrite(out_path, frame, [cv2.IMWRITE_PNG_COMPRESSION, 0])
        saved += 1
        if saved % 100 == 0:
            print(f"  Saved {saved} frames...")
        frame_num += 1

    cap.release()
    print(f"  Done: {saved} frames saved to {output_dir}")
