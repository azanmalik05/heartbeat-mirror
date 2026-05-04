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
BPM_LINE_RE = re.compile(r"BPM:\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*Avg BPM:\s*([0-9]+)")

LOW_BPM = 60
HIGH_BPM = 100
NO_FINGER_TIMEOUT_MS = 3500

APP_DIR = Path(__file__).resolve().parent
MEDIA_DIR = APP_DIR / "media"

STATE_CONFIG = {
    "waiting": {
        "title": "Touch the sensor",
        "subtitle": "Put one finger on the glowing sensor.",
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
        self.root.geometry("760x560")
        self.root.minsize(620, 500)

        self.ser = None
        self.current_state = None
        self.last_bpm = None
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
            self.status_label.config(text=f"Sensor connected: {port}")
            self.set_state("waiting")
        except Exception as e:
            self.ser = None
            if getattr(e, "errno", None) == 16 or "Resource busy" in str(e):
                self.status_label.config(text="Sensor is already open in another program")
                self.set_state("busy")
            else:
                self.status_label.config(text=f"Could not connect to sensor: {e}")
                self.set_state("waiting")

    def read_loop(self):
        if self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
                if line == "No finger detected":
                    self.last_bpm = None
                    self.last_read_at = None
                    self.status_label.config(text="Waiting for a finger")
                    self.set_state("waiting")
                    self.bpm_label.config(text="-- BPM")
                else:
                    m = BPM_LINE_RE.match(line)
                    if m:
                        bpm = int(float(m.group(1)))
                        avg = int(m.group(2))
                        display_bpm = avg if avg > 0 else bpm
                        self.last_bpm = display_bpm
                        self.last_read_at = self._now_ms()
                        self.status_label.config(text="Reading your heartbeat")
                        self.bpm_label.config(text=f"{display_bpm} BPM")
                        self.set_state(self.state_for_bpm(display_bpm))
            except Exception:
                self.status_label.config(text="Read error. Try reconnecting.")

        if self.last_read_at and self._now_ms() - self.last_read_at > NO_FINGER_TIMEOUT_MS:
            self.last_bpm = None
            self.last_read_at = None
            self.set_state("waiting")
            self.bpm_label.config(text="-- BPM")

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

    def animation_loop(self):
        bpm = self.last_bpm or 54
        beat_interval_ms = max(280, min(1300, int(60000 / bpm)))
        now = self._now_ms()

        if self.current_state not in {"waiting", "busy"} and now - self.last_beat_at >= beat_interval_ms:
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

        if self.current_state == "busy":
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
                text="Close Serial Monitor",
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
