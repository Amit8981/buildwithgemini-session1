import os
import time
import asyncio
import shutil
import subprocess
from playwright.async_api import async_playwright

ARTIFACT_DIR = "/config/.gemini/antigravity/brain/196f96cd-daec-46e9-8425-4005b4ed84c9"
REC_DIR = os.path.join(ARTIFACT_DIR, "recordings")
os.makedirs(REC_DIR, exist_ok=True)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=REC_DIR,
            record_video_size={"width": 1280, "height": 800}
        )
        
        page = await context.new_page()
        print("Navigating to http://localhost:8080...")
        await page.goto("http://localhost:8080")
        await page.wait_for_timeout(2000)

        # 1. First interaction: Expiring items lookup
        print("Sending prompt 1: Expiring items...")
        await page.evaluate("sendPrompt(\"What items are expiring soon in my pantry?\")")

        # Wait until the agent bubble is rendered and no longer showing '…'
        print("Waiting for response 1...")
        await page.wait_for_selector(".msg.agent .bubble", timeout=45000)
        # Wait for streaming text completion
        for _ in range(30):
            text = await page.locator(".msg.agent .bubble").last.text_content()
            if text and text != "…":
                break
            await asyncio.sleep(1)

        await page.wait_for_timeout(6000)

        # 2. Second interaction: Search recipe and generate image
        print("Sending prompt 2: Recipe search + Image generation...")
        await page.evaluate("sendPrompt(\"Search for a recipe using eggs and spinach, then generate a photo of the dish.\")")

        print("Waiting for response 2...")
        # Wait until 2 agent bubbles exist and the second is complete
        for _ in range(60):
            count = await page.locator(".msg.agent .bubble").count()
            if count >= 2:
                last_text = await page.locator(".msg.agent .bubble").last.text_content()
                if last_text and last_text != "…":
                    break
            await asyncio.sleep(1)

        # Allow full visual display of generated image/card
        await page.wait_for_timeout(12000)

        print("Demo flow finished! Closing context...")
        await page.close()
        await context.close()
        await browser.close()

        # Find latest webm recording
        video_files = [os.path.join(REC_DIR, f) for f in os.listdir(REC_DIR) if f.endswith(".webm")]
        if not video_files:
            print("Error: No video file found in recordings dir.")
            return

        latest_webm = max(video_files, key=os.path.getmtime)
        print(f"Recorded video file: {latest_webm}")

        # Mix video with upbeat lo-fi audio using ffmpeg
        audio_wav = "/config/Desktop/Session1/demo-agent/lofi_beat.wav"
        output_mp4 = os.path.join(ARTIFACT_DIR, "agent_demo_lofi.mp4")

        cmd = [
            "ffmpeg", "-y",
            "-i", latest_webm,
            "-i", audio_wav,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest",
            output_mp4
        ]
        print("Mixing video and upbeat lo-fi audio with ffmpeg...")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"Successfully created demo video with upbeat lo-fi audio: {output_mp4}")
        else:
            print(f"ffmpeg mixing error: {res.stderr}")

if __name__ == "__main__":
    asyncio.run(main())
