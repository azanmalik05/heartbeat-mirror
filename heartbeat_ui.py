import tkinter as tk
import serial
import threading
import time
import vlc

SERIAL_PORT = "/dev/cu.usbmodem0740D12FA0C01"
BAUD_RATE = 115200

CALM_VIDEO = "videos/calm.mp4"
EXERCISE_VIDEO = "videos/exercise.mp4"

guess_bpm = "--"
avg_bpm = "--"
difference = "--"

last_video = None
last_video_time = 0
VIDEO_COOLDOWN = 10

root = tk.Tk()
root.title("Heartbeat Mirror")
root.configure(bg="black")
root.attributes("-fullscreen", True)

title = tk.Label(root, text="HEARTBEAT MIRROR", font=("Helvetica", 48, "bold"), fg="red", bg="black")
title.pack(pady=15)

subtitle = tk.Label(root, text="Can you guess your heartbeat?", font=("Helvetica", 26), fg="white", bg="black")
subtitle.pack(pady=5)

frame = tk.Frame(root, bg="black")
frame.pack(pady=20)

headers = ["YOUR GUESS", "MEASURED", "DIFFERENCE"]
for i, h in enumerate(headers):
    tk.Label(frame, text=h, font=("Helvetica", 22), fg="white", bg="black").grid(row=0, column=i, padx=55)

guess_label = tk.Label(frame, text="-- BPM", font=("Helvetica", 38, "bold"), fg="red", bg="black")
guess_label.grid(row=1, column=0, pady=15)

measured_label = tk.Label(frame, text="-- BPM", font=("Helvetica", 38, "bold"), fg="red", bg="black")
measured_label.grid(row=1, column=1, pady=15)

difference_label = tk.Label(frame, text="-- BPM", font=("Helvetica", 38, "bold"), fg="red", bg="black")
difference_label.grid(row=1, column=2, pady=15)

result_label = tk.Label(root, text="Move the slider to guess.", font=("Helvetica", 30, "bold"), fg="white", bg="black")
result_label.pack(pady=8)

status_label = tk.Label(root, text="Connecting to sensor...", font=("Helvetica", 18), fg="gray", bg="black")
status_label.pack(pady=5)

video_frame = tk.Frame(root, bg="gray20", width=700, height=330, highlightbackground="red", highlightthickness=2)
video_frame.pack(pady=15)
video_frame.pack_propagate(False)

button_frame = tk.Frame(root, bg="black")
button_frame.pack(pady=10)

# VLC setup
vlc_instance = vlc.Instance()
player = vlc_instance.media_player_new()


def set_video_window():
    root.update()
    player.set_xwindow(video_frame.winfo_id())


def play_video(path):
    global last_video_time

    media = vlc_instance.media_new(path)
    player.set_media(media)
    set_video_window()
    player.play()
    last_video_time = time.time()


def loop_video():
    while True:
        time.sleep(1)
        try:
            state = player.get_state()
            if state == vlc.State.Ended:
                player.stop()
                player.play()
        except:
            pass


def auto_video(measured):
    global last_video, last_video_time

    now = time.time()

    if now - last_video_time < VIDEO_COOLDOWN:
        return

    if measured >= 95 and last_video != "calm":
        last_video = "calm"
        play_video(CALM_VIDEO)
        status_label.config(text="Try calming your heartbeat.")

    elif measured <= 70 and last_video != "exercise":
        last_video = "exercise"
        play_video(EXERCISE_VIDEO)
        status_label.config(text="Try raising your heartbeat.")


def update_guess_only():
    guess_label.config(text=f"{guess_bpm} BPM")


def update_full_ui():
    guess_label.config(text=f"{guess_bpm} BPM")
    measured_label.config(text=f"{avg_bpm} BPM")
    difference_label.config(text=f"{difference} BPM")

    try:
        diff = int(difference)
        measured = int(avg_bpm)

        if diff <= 5:
            result_label.config(text="Great guess!", fg="#00ff66")
        elif diff <= 15:
            result_label.config(text="Pretty close!", fg="#ffcc00")
        else:
            result_label.config(text="Try again!", fg="#ff4444")

        auto_video(measured)

    except:
        result_label.config(text="Move the slider to guess.", fg="white")


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

            if line.startswith("RAW:") and "Guess BPM:" in line:
                guess_bpm = line.split("Guess BPM:")[1].strip()
                root.after(0, update_guess_only)

            elif "Guess:" in line and "Avg BPM:" in line:
                parts = line.split("|")

                guess_bpm = parts[0].replace("Guess:", "").strip()
                avg_bpm = parts[2].replace("Avg BPM:", "").strip()
                difference = parts[3].replace("Difference:", "").strip()

                root.after(0, update_full_ui)

            elif "No finger" in line:
                root.after(0, lambda: status_label.config(text="Place your finger on the sensor."))

        except Exception as e:
            root.after(0, lambda: status_label.config(text=f"Read error: {e}"))


tk.Button(
    button_frame,
    text="Calm Breathing Video",
    font=("Helvetica", 18, "bold"),
    width=24,
    height=2,
    command=lambda: play_video(CALM_VIDEO)
).grid(row=0, column=0, padx=25)

tk.Button(
    button_frame,
    text="Exercise Challenge Video",
    font=("Helvetica", 18, "bold"),
    width=24,
    height=2,
    command=lambda: play_video(EXERCISE_VIDEO)
).grid(row=0, column=1, padx=25)

root.bind("<Escape>", lambda event: root.destroy())

threading.Thread(target=read_serial, daemon=True).start()
threading.Thread(target=loop_video, daemon=True).start()

root.mainloop()