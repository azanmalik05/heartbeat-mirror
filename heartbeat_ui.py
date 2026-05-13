import tkinter as tk
import serial
import threading
import time
import subprocess
import cv2
from PIL import Image, ImageTk

SERIAL_PORT = "/dev/cu.usbmodem0740D12FA0C01"
BAUD_RATE = 115200

CALM_VIDEO = "videos/calm.mp4"
EXERCISE_VIDEO = "videos/exercise.mp4"
ELEVATED_HEARTBEAT_THRESHOLD = 95
SLIDER_MIN_BPM = 40
SLIDER_MAX_BPM = 140

guess_bpm = "--"
avg_bpm = "--"
difference = "--"

last_video = None
last_video_time = 0
VIDEO_COOLDOWN = 10

root = tk.Tk()
root.title("Heartbeat Mirror")
root.attributes("-fullscreen", True)

COLORS = {
    "bg": "#07111f",
    "panel": "#101c31",
    "panel_2": "#142642",
    "panel_3": "#193253",
    "border": "#28496f",
    "coral": "#ff6b7a",
    "yellow": "#ffd166",
    "mint": "#5ff0c8",
    "sky": "#5cc8ff",
    "purple": "#b18cff",
    "white": "#ffffff",
    "soft": "#d8ecff",
    "muted": "#91abc8",
    "deep": "#020817",
}
root.configure(bg=COLORS["bg"])

TITLE_FONT = ("Avenir Next", 48, "bold")
SUBTITLE_FONT = ("Avenir Next", 19)
KICKER_FONT = ("Avenir Next", 13, "bold")
LABEL_FONT = ("Avenir Next", 13, "bold")
VALUE_FONT = ("Avenir Next", 34, "bold")
SMALL_FONT = ("Avenir Next", 14)
STATUS_FONT = ("Avenir Next", 18, "bold")

main = tk.Frame(root, bg=COLORS["bg"])
main.pack(fill="both", expand=True, padx=36, pady=28)

top_bar = tk.Frame(main, bg=COLORS["bg"])
top_bar.pack(fill="x", pady=(0, 22))

brand = tk.Frame(top_bar, bg=COLORS["bg"])
brand.pack(side="left", anchor="w")

kicker = tk.Label(
    brand,
    text="INTERACTIVE HEARTBEAT CHALLENGE",
    font=KICKER_FONT,
    fg=COLORS["mint"],
    bg=COLORS["bg"],
)
kicker.pack(anchor="w")

title = tk.Label(
    brand,
    text="Heartbeat Mirror",
    font=TITLE_FONT,
    fg=COLORS["white"],
    bg=COLORS["bg"],
)
title.pack(anchor="w", pady=(2, 0))

subtitle = tk.Label(
    brand,
    text="Guess your pulse, check the sensor, and watch the screen react in real time.",
    font=SUBTITLE_FONT,
    fg=COLORS["soft"],
    bg=COLORS["bg"],
)
subtitle.pack(anchor="w", pady=(2, 0))

threshold_badge = tk.Frame(
    top_bar,
    bg=COLORS["panel_2"],
    highlightbackground=COLORS["border"],
    highlightthickness=2,
)
threshold_badge.pack(side="right", anchor="ne", pady=(10, 0))

tk.Label(
    threshold_badge,
    text="LIVE MONITOR",
    font=KICKER_FONT,
    fg=COLORS["muted"],
    bg=COLORS["panel_2"],
).pack(padx=24, pady=(14, 0))

tk.Label(
    threshold_badge,
    text="RESPONDING",
    font=("Avenir Next", 30, "bold"),
    fg=COLORS["yellow"],
    bg=COLORS["panel_2"],
).pack(padx=24, pady=(0, 14))

content = tk.Frame(main, bg=COLORS["bg"])
content.pack(fill="both", expand=True)

left_panel = tk.Frame(content, bg=COLORS["bg"], width=420)
left_panel.pack(side="left", fill="y", padx=(0, 24))
left_panel.pack_propagate(False)

right_panel = tk.Frame(content, bg=COLORS["panel"], highlightbackground=COLORS["border"], highlightthickness=2)
right_panel.pack(side="left", fill="both", expand=True)

prompt_card = tk.Frame(left_panel, bg=COLORS["panel"], highlightbackground=COLORS["border"], highlightthickness=2)
prompt_card.pack(fill="x", pady=(0, 16))

tk.Label(
    prompt_card,
    text="How To Play",
    font=("Avenir Next", 22, "bold"),
    fg=COLORS["white"],
    bg=COLORS["panel"],
).pack(anchor="w", padx=22, pady=(18, 4))

tk.Label(
    prompt_card,
    text="Move the slider to make your guess. Then place your finger on the sensor and compare your answer.",
    font=SMALL_FONT,
    fg=COLORS["soft"],
    bg=COLORS["panel"],
    justify="left",
    wraplength=350,
).pack(anchor="w", padx=22, pady=(0, 20))

readout_area = tk.Frame(left_panel, bg=COLORS["bg"])
readout_area.pack(fill="both", expand=True)

slider_card = tk.Frame(
    readout_area,
    bg=COLORS["panel"],
    width=132,
    highlightbackground=COLORS["sky"],
    highlightthickness=3,
)
slider_card.pack(side="left", fill="y", padx=(0, 12))
slider_card.pack_propagate(False)

tk.Label(
    slider_card,
    text="LIVE\nSLIDER",
    font=("Avenir Next", 15, "bold"),
    fg=COLORS["white"],
    bg=COLORS["panel"],
    justify="center",
).pack(pady=(16, 6))

slider_value_label = tk.Label(
    slider_card,
    text="--\nBPM",
    font=("Avenir Next", 24, "bold"),
    fg=COLORS["sky"],
    bg=COLORS["panel"],
    justify="center",
)
slider_value_label.pack(pady=(0, 6))

slider_canvas = tk.Canvas(slider_card, width=108, bg=COLORS["panel"], highlightthickness=0)
slider_canvas.pack(fill="both", expand=True, padx=10, pady=(0, 16))

right_stack = tk.Frame(readout_area, bg=COLORS["bg"])
right_stack.pack(side="left", fill="both", expand=True)

stats_frame = tk.Frame(right_stack, bg=COLORS["bg"])
stats_frame.pack(fill="x")

headers = ["YOUR GUESS", "MEASURED", "DIFFERENCE"]
stat_colors = [COLORS["sky"], COLORS["mint"], COLORS["purple"]]
stat_labels = []
for i, h in enumerate(headers):
    card = tk.Frame(
        stats_frame,
        bg=COLORS["panel_2"],
        height=112,
        highlightbackground=stat_colors[i],
        highlightthickness=3,
    )
    card.pack(fill="x", pady=(0, 12))
    card.pack_propagate(False)

    tk.Label(card, text=h, font=LABEL_FONT, fg=COLORS["muted"], bg=COLORS["panel_2"]).pack(anchor="w", padx=20, pady=(16, 0))
    value_label = tk.Label(card, text="-- BPM", font=VALUE_FONT, fg=stat_colors[i], bg=COLORS["panel_2"])
    value_label.pack(anchor="w", padx=20)
    stat_labels.append(value_label)

guess_label, measured_label, difference_label = stat_labels

message_card = tk.Frame(right_stack, bg=COLORS["panel_3"], highlightbackground=COLORS["yellow"], highlightthickness=3)
message_card.pack(fill="x", pady=(4, 0))

result_label = tk.Label(
    message_card,
    text="Ready when you are!",
    font=STATUS_FONT,
    fg=COLORS["white"],
    bg=COLORS["panel_3"],
    wraplength=220,
)
result_label.pack(anchor="w", padx=22, pady=(18, 6))

status_label = tk.Label(
    message_card,
    text="Connecting to sensor...",
    font=SMALL_FONT,
    fg=COLORS["soft"],
    bg=COLORS["panel_3"],
    justify="left",
    wraplength=220,
)
status_label.pack(anchor="w", padx=22, pady=(0, 18))

video_header = tk.Frame(right_panel, bg=COLORS["panel"])
video_header.pack(fill="x", padx=24, pady=(22, 12))

tk.Label(
    video_header,
    text="Live Heartbeat Monitor",
    font=("Avenir Next", 26, "bold"),
    fg=COLORS["white"],
    bg=COLORS["panel"],
).pack(side="left", anchor="w")

video_pill = tk.Label(
    video_header,
    text="WAITING FOR SENSOR",
    font=KICKER_FONT,
    fg=COLORS["deep"],
    bg=COLORS["yellow"],
)
video_pill.pack(side="right", anchor="e", ipadx=16, ipady=7)

video_frame = tk.Frame(
    right_panel,
    bg=COLORS["deep"],
    highlightbackground=COLORS["sky"],
    highlightthickness=3,
)
video_frame.pack(fill="both", expand=True, padx=24, pady=(0, 14))
video_frame.pack_propagate(False)

video_label = tk.Label(video_frame, bg=COLORS["deep"])
video_label.pack(fill="both", expand=True)

video_status_label = tk.Label(
    right_panel,
    text="The monitor responds live as your heartbeat changes.",
    font=SMALL_FONT,
    fg=COLORS["muted"],
    bg=COLORS["panel"],
)
video_status_label.pack(anchor="w", padx=24, pady=(0, 20))

# Video playback is rendered directly into Tkinter to avoid VLC native-window crashes on macOS.
video_capture = None
video_after_id = None
video_photo = None
video_playback_token = 0
current_video_path = None
audio_process = None


def play_video(path):
    global last_video_time, video_capture, video_after_id, video_playback_token, current_video_path

    if video_after_id is not None:
        root.after_cancel(video_after_id)
        video_after_id = None

    if video_capture is not None:
        video_capture.release()

    video_capture = cv2.VideoCapture(path)
    current_video_path = path
    last_video_time = time.time()

    if not video_capture.isOpened():
        video_status_label.config(text=f"Could not open monitor media: {path}", fg=COLORS["coral"])
        return

    start_audio(path)
    video_playback_token += 1
    render_video_frame(video_playback_token)


def start_audio(path):
    global audio_process

    stop_audio()

    try:
        audio_process = subprocess.Popen(
            ["afplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        audio_process = None
        video_status_label.config(text="Monitor is running, but audio could not start.", fg=COLORS["yellow"])


def stop_audio():
    global audio_process

    if audio_process is not None and audio_process.poll() is None:
        audio_process.terminate()

    audio_process = None


def render_video_frame(token):
    global video_after_id, video_photo

    if token != video_playback_token or video_capture is None:
        return

    try:
        success, frame = video_capture.read()

        if not success:
            video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            if current_video_path is not None:
                start_audio(current_video_path)
            success, frame = video_capture.read()

        if success:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_image = Image.fromarray(frame)

            frame_width = max(video_frame.winfo_width(), 1)
            frame_height = max(video_frame.winfo_height(), 1)
            frame_image.thumbnail((frame_width, frame_height), Image.Resampling.LANCZOS)

            canvas = Image.new("RGB", (frame_width, frame_height), COLORS["deep"])
            x = (frame_width - frame_image.width) // 2
            y = (frame_height - frame_image.height) // 2
            canvas.paste(frame_image, (x, y))

            video_photo = ImageTk.PhotoImage(canvas)
            video_label.config(image=video_photo)

        fps = video_capture.get(cv2.CAP_PROP_FPS)
        delay = int(1000 / fps) if fps and fps > 1 else 33
        video_after_id = root.after(delay, lambda: render_video_frame(token))
    except Exception:
        video_status_label.config(text="Monitor playback paused. Try converting the media to H.264 MP4.", fg=COLORS["coral"])


def auto_video(measured):
    global last_video, last_video_time

    now = time.time()

    if now - last_video_time < VIDEO_COOLDOWN:
        return

    if measured >= ELEVATED_HEARTBEAT_THRESHOLD and last_video != "exercise":
        last_video = "exercise"
        play_video(EXERCISE_VIDEO)
        status_label.config(text="Your heartbeat is powered up!")
        video_status_label.config(text="Monitor mode: energy challenge", fg=COLORS["coral"])
        video_pill.config(text="ENERGY MODE", bg=COLORS["coral"], fg=COLORS["white"])

    elif measured < ELEVATED_HEARTBEAT_THRESHOLD and last_video != "calm":
        last_video = "calm"
        play_video(CALM_VIDEO)
        status_label.config(text="Nice and steady. Keep breathing calmly.")
        video_status_label.config(text="Monitor mode: calm heartbeat", fg=COLORS["mint"])
        video_pill.config(text="CALM MODE", bg=COLORS["mint"], fg=COLORS["deep"])


def update_guess_only():
    guess_label.config(text=f"{guess_bpm} BPM")
    update_slider_indicator(guess_bpm)


def extract_field_value(line, field_name):
    if field_name not in line:
        return None

    value = line.split(field_name, 1)[1].strip()
    return value.split("|", 1)[0].strip()


def update_slider_indicator(value):
    try:
        bpm = int(value)
    except (TypeError, ValueError):
        slider_value_label.config(text="--\nBPM")
        slider_canvas.delete("all")
        return

    bpm = max(SLIDER_MIN_BPM, min(SLIDER_MAX_BPM, bpm))
    percent = (bpm - SLIDER_MIN_BPM) / (SLIDER_MAX_BPM - SLIDER_MIN_BPM)

    slider_value_label.config(text=f"{bpm}\nBPM")
    slider_canvas.delete("all")

    width = max(slider_canvas.winfo_width(), 108)
    height = max(slider_canvas.winfo_height(), 260)
    track_x = width // 2 + 14
    track_top = 22
    track_bottom = height - 28
    marker_y = track_bottom - percent * (track_bottom - track_top)

    slider_canvas.create_line(
        track_x,
        track_top,
        track_x,
        track_bottom,
        fill=COLORS["border"],
        width=14,
        capstyle="round",
    )
    slider_canvas.create_line(
        track_x,
        marker_y,
        track_x,
        track_bottom,
        fill=COLORS["sky"],
        width=14,
        capstyle="round",
    )

    for tick in range(SLIDER_MIN_BPM, SLIDER_MAX_BPM + 1, 10):
        tick_percent = (tick - SLIDER_MIN_BPM) / (SLIDER_MAX_BPM - SLIDER_MIN_BPM)
        tick_y = track_bottom - tick_percent * (track_bottom - track_top)
        tick_length = 20 if tick % 20 == 0 else 12
        slider_canvas.create_line(
            track_x - tick_length,
            tick_y,
            track_x - 4,
            tick_y,
            fill=COLORS["soft"] if tick % 20 == 0 else COLORS["muted"],
            width=2 if tick % 20 == 0 else 1,
        )

        if tick % 20 == 0:
            slider_canvas.create_text(
                track_x - tick_length - 8,
                tick_y,
                text=str(tick),
                fill=COLORS["muted"],
                font=("Avenir Next", 10, "bold"),
                anchor="e",
            )

    slider_canvas.create_polygon(
        track_x + 32,
        marker_y,
        track_x + 8,
        marker_y - 14,
        track_x + 8,
        marker_y + 14,
        fill=COLORS["yellow"],
        outline=COLORS["white"],
    )
    slider_canvas.create_oval(
        track_x - 12,
        marker_y - 12,
        track_x + 12,
        marker_y + 12,
        fill=COLORS["sky"],
        outline=COLORS["white"],
        width=2,
    )


def update_full_ui():
    guess_label.config(text=f"{guess_bpm} BPM")
    measured_label.config(text=f"{avg_bpm} BPM")
    difference_label.config(text=f"{difference} BPM")
    update_slider_indicator(guess_bpm)

    try:
        diff = int(difference)
        measured = int(avg_bpm)

        if diff <= 5:
            result_label.config(text="Amazing guess!", fg=COLORS["mint"])
        elif diff <= 15:
            result_label.config(text="So close!", fg=COLORS["yellow"])
        else:
            result_label.config(text="Try another guess!", fg=COLORS["coral"])

        auto_video(measured)

    except:
        result_label.config(text="Move the slider to guess.", fg=COLORS["white"])


def read_serial():
    global guess_bpm, avg_bpm, difference

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    except Exception as e:
        root.after(0, lambda: status_label.config(text=f"Serial error: {e}"))
        return

    root.after(0, lambda: status_label.config(text="Connected. Move the slider, then place your finger."))

    while True:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()

            if not line:
                continue

            print(line)

            latest_guess = extract_field_value(line, "Guess BPM:") or extract_field_value(line, "Guess:")
            if latest_guess is not None and latest_guess != guess_bpm:
                guess_bpm = latest_guess
                root.after(0, update_guess_only)

            if "Guess:" in line and "Avg BPM:" in line:
                parts = line.split("|")

                guess_bpm = parts[0].replace("Guess:", "").strip()
                avg_bpm = parts[2].replace("Avg BPM:", "").strip()
                difference = parts[3].replace("Difference:", "").strip()

                root.after(0, update_full_ui)

            elif "No finger" in line:
                root.after(0, lambda: status_label.config(text="Place your finger on the sensor."))

        except Exception as e:
            root.after(0, lambda: status_label.config(text=f"Read error: {e}"))


def close_app():
    if video_after_id is not None:
        root.after_cancel(video_after_id)

    if video_capture is not None:
        video_capture.release()

    stop_audio()
    root.destroy()


root.bind("<Escape>", lambda event: close_app())
root.protocol("WM_DELETE_WINDOW", close_app)

threading.Thread(target=read_serial, daemon=True).start()

root.mainloop()