import math
import os
import platform
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from tkinter import messagebox
import tkinter as tk

import serial
from serial.tools import list_ports

BAUD = 9600
READ_INTERVAL_MS = 100
BPM_LINE_RE = re.compile(
    r"BPM:\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*Avg BPM:\s*([0-9]+)"
    r"(?:\s*\|\s*Guess:\s*([0-9]+))?(?:\s*\|\s*Confidence:\s*([0-9]+)/([0-9]+))?"
)
NO_FINGER_RE = re.compile(r"No finger detected(?:\s*\|\s*Guess:\s*([0-9]+))?")
CALIBRATING_RE = re.compile(
    r"Calibrating(?:\s*\|\s*Guess:\s*([0-9]+))?(?:\s*\|\s*Confidence:\s*([0-9]+)/([0-9]+))?"
)
MISSING_HEART_RE = re.compile(
    r"(?:MAX30102 not found\. Check wiring\.|I2C bus stuck low\. Check SDA and SCL wiring\.)"
    r"(?:\s*\|\s*Guess:\s*([0-9]+))?"
    r"(?:\s*\|\s*NeoSlider:\s*(found|not found))?"
)
SLIDER_STATUS_RE = re.compile(r".*\|\s*NeoSlider:\s*(found|not found)")

LOW_BPM = 60
HIGH_BPM = 100
MIN_GUESS_BPM = 45
MAX_GUESS_BPM = 190
NO_FINGER_TIMEOUT_MS = 3500
SERIAL_SILENCE_TIMEOUT_MS = 6500

APP_DIR = Path(__file__).resolve().parent
MEDIA_DIR = APP_DIR / "media"

STATE_CONFIG = {
    "waiting": {
        "title": "Touch the sensor",
        "subtitle": "Move the slider to guess, then put one finger on the glowing sensor.",
        "emoji": "♡",
        "color": "#64748b",
        "bg": "#f8fafc",
        "sound": None,
        "gif": "waiting.gif",
    },
    "busy": {
        "title": "Sensor is busy",
        "subtitle": "Close Serial Monitor, then press reconnect.",
        "emoji": "!",
        "color": "#d97706",
        "bg": "#fffbeb",
        "sound": None,
        "gif": "waiting.gif",
    },
    "missing": {
        "title": "Check the wires",
        "subtitle": "The Arduino is connected, but the heart sensor is not responding.",
        "emoji": "!",
        "color": "#d97706",
        "bg": "#fffbeb",
        "sound": None,
        "gif": "waiting.gif",
    },
    "low": {
        "title": "Slow heartbeat",
        "subtitle": "Your heart is beating gently.",
        "emoji": "♥",
        "color": "#2563eb",
        "bg": "#eff6ff",
        "sound": "low.wav",
        "gif": "low.gif",
    },
    "steady": {
        "title": "Steady heartbeat",
        "subtitle": "Your heart is keeping a regular rhythm.",
        "emoji": "♥",
        "color": "#16a34a",
        "bg": "#f0fdf4",
        "sound": "steady.wav",
        "gif": "steady.gif",
    },
    "high": {
        "title": "Fast heartbeat",
        "subtitle": "Your heart is beating quickly.",
        "emoji": "♥",
        "color": "#dc2626",
        "bg": "#fef2f2",
        "sound": "high.wav",
        "gif": "high.gif",
    },
}


class GifPlayer:
    def __init__(self, label: tk.Label):
        self.label = label
        self.frames = []
        self.index = 0
        self.after_id = None

    def load(self, path: Path) -> bool:
        self.stop()
        self.frames = []
        self.index = 0

        if not path.exists():
            self.label.config(image="")
            return False

        frame_index = 0
        while True:
            try:
                frame = tk.PhotoImage(file=path, format=f"gif -index {frame_index}")
                self.frames.append(frame)
                frame_index += 1
            except tk.TclError:
                break

        if not self.frames:
            self.label.config(image="")
            return False

        self.label.config(image=self.frames[0])
        if len(self.frames) > 1:
            self.after_id = self.label.after(110, self._advance)
        return True

    def _advance(self):
        if not self.frames:
            return

        self.index = (self.index + 1) % len(self.frames)
        self.label.config(image=self.frames[self.index])
        self.after_id = self.label.after(110, self._advance)

    def stop(self):
        if self.after_id:
            self.label.after_cancel(self.after_id)
            self.after_id = None


class HeartSound:
    def __init__(self):
        self.generated_dir = Path(tempfile.gettempdir()) / "heartbeat_mirror_sounds"
        self.generated_dir.mkdir(exist_ok=True)
        self.generated_files = {
            "low": self._make_tone("low.wav", frequency=95, duration=0.13, volume=0.45),
            "steady": self._make_tone("steady.wav", frequency=125, duration=0.11, volume=0.5),
            "high": self._make_tone("high.wav", frequency=165, duration=0.09, volume=0.55),
        }
        self.player = self._find_player()
        self.enabled = True

    def play(self, state: str):
        if not self.enabled or state not in self.generated_files:
            return

        custom_path = MEDIA_DIR / "sounds" / STATE_CONFIG[state]["sound"]
        sound_path = custom_path if custom_path.exists() else self.generated_files[state]

        try:
            if self.player == "winsound":
                import winsound

                winsound.PlaySound(str(sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif self.player:
                subprocess.Popen(
                    [self.player, str(sound_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception:
            self.enabled = False

    def _find_player(self):
        if platform.system() == "Windows":
            return "winsound"

        candidates = ["afplay", "paplay", "aplay"]
        for candidate in candidates:
            for folder in os.environ.get("PATH", "").split(os.pathsep):
                if (Path(folder) / candidate).exists():
                    return candidate
        return None

    def _make_tone(self, filename: str, frequency: int, duration: float, volume: float) -> Path:
        path = self.generated_dir / filename
        if path.exists():
            return path

        sample_rate = 44100
        total_samples = int(sample_rate * duration)
        max_amp = int(32767 * volume)

        with wave.open(str(path), "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            for i in range(total_samples):
                t = i / sample_rate
                envelope = max(0.0, 1.0 - (i / total_samples))
                sample = int(max_amp * envelope * math.sin(2 * math.pi * frequency * t))
                wav.writeframesraw(sample.to_bytes(2, byteorder="little", signed=True))

        return path


class HeartRateApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Heartbeat Mirror")
        self.root.geometry("760x650")
        self.root.minsize(620, 590)

        self.ser = None
        self.current_state = None
        self.last_bpm = None
        self.last_guess = None
        self.connected_at = None
        self.last_serial_at = None
        self.last_serial_line = None
        self.last_read_at = None
        self.last_beat_at = 0
        self.pulse_size = 1.0
        self.sound = HeartSound()

        self.root.configure(bg=STATE_CONFIG["waiting"]["bg"])

        self.status_label = tk.Label(
            root,
            text="Connecting...",
            font=("Arial", 15, "bold"),
            fg="#334155",
            bg=STATE_CONFIG["waiting"]["bg"],
            wraplength=700,
        )
        self.status_label.pack(pady=(18, 8))

        self.stage = tk.Frame(root, bg=STATE_CONFIG["waiting"]["bg"])
        self.stage.pack(fill="both", expand=True, padx=24)

        self.media_label = tk.Label(self.stage, bg=STATE_CONFIG["waiting"]["bg"])
        self.media_label.place(relx=0.5, rely=0.46, anchor="center")
        self.gif_player = GifPlayer(self.media_label)

        self.canvas = tk.Canvas(
            self.stage,
            width=360,
            height=245,
            highlightthickness=0,
            bg=STATE_CONFIG["waiting"]["bg"],
        )
        self.canvas.place(relx=0.5, rely=0.46, anchor="center")

        self.title_label = tk.Label(
            root,
            text=STATE_CONFIG["waiting"]["title"],
            font=("Arial", 34, "bold"),
            fg=STATE_CONFIG["waiting"]["color"],
            bg=STATE_CONFIG["waiting"]["bg"],
        )
        self.title_label.pack(pady=(4, 0))

        self.subtitle_label = tk.Label(
            root,
            text=STATE_CONFIG["waiting"]["subtitle"],
            font=("Arial", 19),
            fg="#334155",
            bg=STATE_CONFIG["waiting"]["bg"],
        )
        self.subtitle_label.pack(pady=(4, 10))

        self.bpm_label = tk.Label(
            root,
            text="-- BPM",
            font=("Arial", 34, "bold"),
            fg="#0f172a",
            bg=STATE_CONFIG["waiting"]["bg"],
        )
        self.bpm_label.pack()

        self.guess_frame = tk.Frame(root, bg=STATE_CONFIG["waiting"]["bg"])
        self.guess_frame.pack(fill="x", padx=52, pady=(14, 6))

        self.guess_title = tk.Label(
            self.guess_frame,
            text="Guess the heartbeat first",
            font=("Arial", 16, "bold"),
            fg="#334155",
            bg=STATE_CONFIG["waiting"]["bg"],
        )
        self.guess_title.pack(anchor="w")

        self.guess_var = tk.IntVar(value=90)
        self.guess_scale = tk.Scale(
            self.guess_frame,
            from_=MIN_GUESS_BPM,
            to=MAX_GUESS_BPM,
            orient="horizontal",
            variable=self.guess_var,
            showvalue=False,
            length=560,
            state="disabled",
            bg=STATE_CONFIG["waiting"]["bg"],
            troughcolor="#e2e8f0",
            highlightthickness=0,
        )
        self.guess_scale.pack(fill="x")

        self.guess_label = tk.Label(
            self.guess_frame,
            text="Guess: 90 BPM",
            font=("Arial", 15),
            fg="#475569",
            bg=STATE_CONFIG["waiting"]["bg"],
        )
        self.guess_label.pack(anchor="w")

        self.compare_label = tk.Label(
            root,
            text="",
            font=("Arial", 17, "bold"),
            fg="#0f172a",
            bg=STATE_CONFIG["waiting"]["bg"],
        )
        self.compare_label.pack(pady=(2, 0))

        controls = tk.Frame(root, bg=STATE_CONFIG["waiting"]["bg"])
        controls.pack(pady=(12, 16))

        self.sound_var = tk.BooleanVar(value=True)
        self.sound_btn = tk.Checkbutton(
            controls,
            text="Heartbeat sound",
            variable=self.sound_var,
            command=self.toggle_sound,
            font=("Arial", 13),
            bg=STATE_CONFIG["waiting"]["bg"],
            activebackground=STATE_CONFIG["waiting"]["bg"],
        )
        self.sound_btn.pack(side="left", padx=8)

        self.reconnect_btn = tk.Button(
            controls,
            text="Reconnect sensor",
            command=self.reconnect,
            font=("Arial", 13),
            padx=12,
            pady=6,
        )
        self.reconnect_btn.pack(side="left", padx=8)

        self.reconnect()
        self.set_state("waiting")
        self.root.after(READ_INTERVAL_MS, self.read_loop)
        self.root.after(35, self.animation_loop)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def find_arduino_port(self):
        ports = list(list_ports.comports())
        if not ports:
            return None

        preferred_tokens = ["usbmodem", "usbserial", "wchusbserial", "arduino"]
        for p in ports:
            desc = (p.description or "").lower()
            dev = (p.device or "").lower()
            if any(token in desc or token in dev for token in preferred_tokens):
                return p.device

        return ports[0].device

    def reconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

        port = self.find_arduino_port()
        if not port:
            self.ser = None
            self.status_label.config(text="Sensor not connected")
            self.set_state("waiting")
            return

        try:
            self.ser = serial.Serial(port, BAUD, timeout=0.1)
            self.connected_at = self._now_ms()
            self.last_serial_at = None
            self.status_label.config(text=f"Sensor connected: {port}")
            self.set_state("waiting")
            self.root.after(1200, self.request_arduino_start)
        except Exception as e:
            self.ser = None
            if getattr(e, "errno", None) == 16 or "Resource busy" in str(e):
                self.status_label.config(text="Sensor is already open in another program")
                self.set_state("busy")
            else:
                self.status_label.config(text=f"Could not connect to sensor: {e}")
                self.set_state("waiting")

    def request_arduino_start(self):
        if not self.ser or not self.ser.is_open:
            return

        try:
            self.ser.write(b"S\n")
        except Exception:
            self.status_label.config(text="Could not start Arduino hardware check")

    def read_loop(self):
        if self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
                if line:
                    self.last_serial_at = self._now_ms()
                    self.last_serial_line = line

                no_finger = NO_FINGER_RE.match(line)
                if no_finger:
                    self.update_guess(no_finger.group(1))
                    self.update_slider_status(line)
                    self.last_bpm = None
                    self.last_read_at = None
                    self.status_label.config(text="Make your guess, then touch the sensor")
                    self.set_state("waiting")
                    self.bpm_label.config(text="-- BPM")
                    self.compare_label.config(text="")
                else:
                    missing_heart = MISSING_HEART_RE.match(line)
                    if missing_heart:
                        self.update_guess(missing_heart.group(1))
                        self.update_slider_status(line)
                        self.last_bpm = None
                        self.last_read_at = None
                        slider_message = self.slider_status_message(line)
                        self.status_label.config(text=f"Heart sensor not found{slider_message}")
                        self.bpm_label.config(text="-- BPM")
                        self.compare_label.config(text="")
                        self.set_state("missing")
                        self.root.after(READ_INTERVAL_MS, self.read_loop)
                        return

                    calibrating = CALIBRATING_RE.match(line)
                    if calibrating:
                        self.update_guess(calibrating.group(1))
                        self.update_slider_status(line)
                        self.last_bpm = None
                        self.last_read_at = self._now_ms()
                        confidence = self._confidence_text(calibrating.group(2), calibrating.group(3))
                        self.status_label.config(text=f"Finding your heartbeat{confidence}")
                        self.bpm_label.config(text="-- BPM")
                        self.compare_label.config(text="")
                        self.set_state("waiting")
                        self.root.after(READ_INTERVAL_MS, self.read_loop)
                        return

                    m = BPM_LINE_RE.match(line)
                    if m:
                        bpm = int(float(m.group(1)))
                        avg = int(m.group(2))
                        self.update_guess(m.group(3))
                        self.update_slider_status(line)
                        display_bpm = avg if avg > 0 else bpm
                        self.last_bpm = display_bpm
                        self.last_read_at = self._now_ms()
                        confidence = self._confidence_text(m.group(4), m.group(5))
                        self.status_label.config(text=f"Reading your heartbeat{confidence}")
                        self.bpm_label.config(text=f"{display_bpm} BPM")
                        self.update_comparison(display_bpm)
                        self.set_state(self.state_for_bpm(display_bpm))
                    elif line:
                        self.show_raw_arduino_line(line)
            except Exception:
                self.status_label.config(text="Read error. Try reconnecting.")

        if (
            self.ser
            and self.ser.is_open
            and self.connected_at
            and not self.last_serial_at
            and self._now_ms() - self.connected_at > SERIAL_SILENCE_TIMEOUT_MS
        ):
            self.set_state("missing")
            self.status_label.config(text="Arduino USB found, but no sketch data is coming in")
            self.subtitle_label.config(text="Upload heart_monitor.ino, close Serial Monitor, then press reconnect.")

        if (
            self.ser
            and self.ser.is_open
            and self.last_serial_at
            and not self.last_read_at
            and self._now_ms() - self.last_serial_at > SERIAL_SILENCE_TIMEOUT_MS
        ):
            self.set_state("missing")
            self.status_label.config(text=f"Arduino stopped after: {self.last_serial_line[:60]}")
            self.subtitle_label.config(text="Check I2C wiring: power, ground, SDA, and SCL.")

        if self.last_read_at and self._now_ms() - self.last_read_at > NO_FINGER_TIMEOUT_MS:
            self.last_bpm = None
            self.last_read_at = None
            self.set_state("waiting")
            self.bpm_label.config(text="-- BPM")
            self.compare_label.config(text="")

        self.root.after(READ_INTERVAL_MS, self.read_loop)

    def state_for_bpm(self, bpm: int) -> str:
        if bpm < LOW_BPM:
            return "low"
        if bpm > HIGH_BPM:
            return "high"
        return "steady"

    def set_state(self, state: str):
        if state == self.current_state:
            return

        self.current_state = state
        config = STATE_CONFIG[state]
        bg = config["bg"]

        self.root.configure(bg=bg)
        for widget in [
            self.status_label,
            self.stage,
            self.media_label,
            self.canvas,
            self.title_label,
            self.subtitle_label,
            self.bpm_label,
            self.guess_frame,
            self.guess_title,
            self.guess_scale,
            self.guess_label,
            self.compare_label,
            self.sound_btn.master,
            self.sound_btn,
        ]:
            widget.configure(bg=bg)

        self.title_label.config(text=config["title"], fg=config["color"])
        self.subtitle_label.config(text=config["subtitle"])

        loaded_gif = self.gif_player.load(MEDIA_DIR / config["gif"])
        if loaded_gif:
            self.canvas.place_forget()
            self.media_label.place(relx=0.5, rely=0.46, anchor="center")
        else:
            self.media_label.place_forget()
            self.canvas.place(relx=0.5, rely=0.46, anchor="center")

    def update_guess(self, value):
        if value is None:
            return

        self.last_guess = int(value)
        self.guess_var.set(self.last_guess)
        self.guess_label.config(text=f"Guess: {self.last_guess} BPM")

    def update_comparison(self, bpm: int):
        if self.last_guess is None:
            self.compare_label.config(text="")
            return

        difference = abs(self.last_guess - bpm)
        if difference == 0:
            message = "Perfect guess"
        elif difference <= 5:
            message = f"Only {difference} BPM away"
        else:
            message = f"{difference} BPM away from the guess"
        self.compare_label.config(text=message)

    def update_slider_status(self, line: str):
        slider_status = SLIDER_STATUS_RE.match(line)
        if slider_status and slider_status.group(1) == "not found":
            self.guess_label.config(text=f"{self.guess_label.cget('text')} - slider not found")

    def slider_status_message(self, line: str) -> str:
        slider_status = SLIDER_STATUS_RE.match(line)
        if slider_status and slider_status.group(1) == "not found":
            return "; NeoSlider not found"
        return ""

    def show_raw_arduino_line(self, line: str):
        if line.startswith("I2C MAX30102") or line.startswith("I2C NeoSlider"):
            self.status_label.config(text=line)
            return

        if line == "Heartbeat Mirror starting.":
            self.status_label.config(text="Arduino sketch started")
            return

        self.status_label.config(text=f"Arduino says: {line[:80]}")

    def _confidence_text(self, count, total):
        if not count or not total:
            return ""

        count = int(count)
        total = int(total)
        if count < total:
            return f" - calibrating {count}/{total}"
        return " - calibrated"

    def animation_loop(self):
        bpm = self.last_bpm or 54
        beat_interval_ms = max(280, min(1300, int(60000 / bpm)))
        now = self._now_ms()

        if self.current_state not in {"waiting", "busy", "missing"} and now - self.last_beat_at >= beat_interval_ms:
            self.last_beat_at = now
            self.pulse_size = 1.2
            self.sound.play(self.current_state)

        self.pulse_size += (1.0 - self.pulse_size) * 0.16
        self.draw_heart()
        self.root.after(35, self.animation_loop)

    def draw_heart(self):
        config = STATE_CONFIG[self.current_state]
        self.canvas.delete("all")
        self.canvas.configure(bg=config["bg"])

        color = config["color"]
        scale = self.pulse_size
        cx = 180
        cy = 105
        size = 92 * scale

        self.canvas.create_text(
            cx,
            cy,
            text=config["emoji"],
            font=("Arial", int(size), "bold"),
            fill=color,
        )

        if self.current_state == "waiting":
            self.canvas.create_oval(105, 64, 255, 214, outline=color, width=5)
            self.canvas.create_line(180, 31, 180, 67, fill=color, width=6, capstyle="round")
            self.canvas.create_text(
                cx,
                224,
                text="Try the sensor",
                font=("Arial", 18, "bold"),
                fill="#334155",
            )
            return

        if self.current_state in {"busy", "missing"}:
            self.canvas.create_oval(105, 64, 255, 214, outline=color, width=5)
            self.canvas.create_text(
                cx,
                137,
                text="!",
                font=("Arial", 96, "bold"),
                fill=color,
            )
            self.canvas.create_text(
                cx,
                224,
                text="Check SDA SCL power ground" if self.current_state == "missing" else "Close Serial Monitor",
                font=("Arial", 18, "bold"),
                fill="#334155",
            )
            return

        line_y = 214
        self.canvas.create_line(30, line_y, 108, line_y, fill=color, width=6, capstyle="round")
        self.canvas.create_line(108, line_y, 130, line_y - 40, fill=color, width=6, capstyle="round")
        self.canvas.create_line(130, line_y - 40, 157, line_y + 34, fill=color, width=6, capstyle="round")
        self.canvas.create_line(157, line_y + 34, 184, line_y - 18, fill=color, width=6, capstyle="round")
        self.canvas.create_line(184, line_y - 18, 213, line_y, fill=color, width=6, capstyle="round")
        self.canvas.create_line(213, line_y, 330, line_y, fill=color, width=6, capstyle="round")

    def toggle_sound(self):
        self.sound.enabled = self.sound_var.get()

    def _now_ms(self):
        return int(self.root.tk.call("clock", "milliseconds"))

    def on_close(self):
        try:
            self.gif_player.stop()
            if self.ser and self.ser.is_open:
                self.ser.close()
        finally:
            self.root.destroy()


def main():
    root = tk.Tk()
    HeartRateApp(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except ModuleNotFoundError:
        messagebox.showerror(
            "Missing dependency",
            "Install pyserial first:\n\npython3 -m pip install pyserial",
        )
        sys.exit(1)
