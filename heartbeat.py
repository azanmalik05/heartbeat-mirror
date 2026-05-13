import serial
import time

PORT = "/dev/cu.usbmodem1301"
BAUD = 9600

ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2)

print("Heartbeat Mirror Interface Running")
print("----------------------------------")

while True:
    line = ser.readline().decode(errors="ignore").strip()

    if line:
        print(line)

        if line.startswith("GUESS:"):
            parts = line.split(",")

            guess = int(parts[0].split(":")[1])
            bpm = int(parts[1].split(":")[1])

            if bpm == 0:
                print("Place finger on sensor...")
            else:
                diff = abs(guess - bpm)
                print(f"Guess: {guess} BPM | Actual: {bpm} BPM | Difference: {diff}")