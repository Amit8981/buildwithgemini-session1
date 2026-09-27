import os
import cv2
from PIL import Image

def convert_webm_to_gif(webm_path, gif_path, max_width=800, fps=8):
    cap = cv2.VideoCapture(webm_path)
    if not cap.isOpened():
        print(f"Error opening video file: {webm_path}")
        return

    frames = []
    original_fps = cap.get(cv2.CAP_PROP_FPS) or 25
    frame_interval = max(1, int(original_fps / fps))
    frame_count = 0

    print(f"Reading frames from {webm_path}...")
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_interval == 0:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)

            if max_width and pil_img.width > max_width:
                aspect = pil_img.height / pil_img.width
                new_height = int(max_width * aspect)
                pil_img = pil_img.resize((max_width, new_height), Image.Resampling.LANCZOS)

            pil_img = pil_img.convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
            frames.append(pil_img)

        frame_count += 1

    cap.release()

    if frames:
        duration = int(1000 / fps)
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            optimize=True,
            duration=duration,
            loop=0
        )
        print(f"Successfully created optimized GIF: {gif_path} ({len(frames)} frames, size: {os.path.getsize(gif_path)} bytes)")
    else:
        print("No frames extracted.")

if __name__ == "__main__":
    src = "/config/Desktop/Session1/agent_demo.webm"
    if not os.path.exists(src):
        src = "/config/Desktop/Session1/demo-agent/agent_demo.webm"
    dst = "/config/Desktop/Session1/demo-agent/demo.gif"
    convert_webm_to_gif(src, dst)
