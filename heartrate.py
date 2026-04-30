import re
import tkinter as tk
from tkinter import messagebox

import serial
from serial.tools import list_ports

BAUD = 9600
READ_INTERVAL_MS = 200
BPM_LINE_RE = re.compile(r"BPM:\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*Avg BPM:\s*([0-9]+)")


class HeartRateApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Heart Rate Monitor")
        self.root.geometry("420x260")

        self.ser = None

        self.status_label = tk.Label(root, text="Connecting...", font=("Arial", 14))
        self.status_label.pack(pady=(20, 8))

        self.bpm_label = tk.Label(root, text="--", font=("Arial", 56, "bold"))
        self.bpm_label.pack()

        self.avg_label = tk.Label(root, text="Avg BPM: --", font=("Arial", 20))
        self.avg_label.pack(pady=8)

        self.info_label = tk.Label(root, text="", font=("Arial", 11))
        self.info_label.pack(pady=4)

        self.reconnect_btn = tk.Button(root, text="Reconnect", command=self.reconnect)
        self.reconnect_btn.pack(pady=8)

        self.reconnect()
        self.root.after(READ_INTERVAL_MS, self.read_loop)
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
            self.status_label.config(text="Arduino not found")
            self.info_label.config(text="Plug in board, then click Reconnect")
            return

        try:
            self.ser = serial.Serial(port, BAUD, timeout=0.1)
            self.status_label.config(text="Connected")
            self.info_label.config(text=f"Port: {port} @ {BAUD}")
        except Exception as e:
            self.status_label.config(text="Connection failed")
            self.info_label.config(text=str(e))

    def read_loop(self):
        if self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
                if line == "No finger detected":
                    self.status_label.config(text="No finger detected")
                else:
                    m = BPM_LINE_RE.match(line)
                    if m:
                        bpm = int(float(m.group(1)))
                        avg = int(m.group(2))
                        self.status_label.config(text="Reading")
                        self.bpm_label.config(text=str(bpm))
                        self.avg_label.config(text=f"Avg BPM: {avg}")
            except Exception:
                self.status_label.config(text="Read error")

        self.root.after(READ_INTERVAL_MS, self.read_loop)

    def on_close(self):
        try:
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
