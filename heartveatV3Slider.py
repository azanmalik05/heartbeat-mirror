import time
import board
import busio
import digitalio

from adafruit_seesaw.seesaw import Seesaw
from adafruit_seesaw.analoginput import AnalogInput
from adafruit_seesaw.neopixel import NeoPixel

i2c = busio.I2C(board.SCL, board.SDA)

# Scan I2C devices
while not i2c.try_lock():
    pass

print("I2C devices found:", [hex(x) for x in i2c.scan()])
i2c.unlock()

# MAX30102
ADDR = 0x57

# Vibration motor
motor = digitalio.DigitalInOut(board.A1)
motor.direction = digitalio.Direction.OUTPUT
motor.value = False

# NeoSlider
neoslider = Seesaw(i2c, addr=0x30)
slider = AnalogInput(neoslider, 18)
pixels = NeoPixel(neoslider, 14, 4)
pixels.brightness = 0.3

RATE_SIZE = 5
rates = []

last_beat = 0
last_ir = 0
going_up = False
peak_ir = 0
last_no_finger_print = 0

# -----------------------------
# MAX30102 FUNCTIONS
# -----------------------------

def write_reg(reg, val):
    while not i2c.try_lock():
        pass

    try:
        i2c.writeto(ADDR, bytes([reg, val]))
    except Exception as e:
        print("I2C Write Error:", e)

    i2c.unlock()

def read_reg(reg, n):
    data = bytearray(n)

    while not i2c.try_lock():
        pass

    try:
        i2c.writeto_then_readfrom(
            ADDR,
            bytes([reg]),
            data
        )
    except Exception as e:
        print("I2C Read Error:", e)
        i2c.unlock()
        return bytearray(n)

    i2c.unlock()
    return data

# -----------------------------
# MOTOR
# -----------------------------

def vibrate_heartbeat():
    motor.value = True
    time.sleep(0.15)
    motor.value = False

# -----------------------------
# NEOSLIDER BPM GUESS
# -----------------------------

def get_guess_bpm():
    raw = slider.value

    # adjust if needed after testing
    SLIDER_MIN = 50
    SLIDER_MAX = 1000

    if raw < SLIDER_MIN:
        raw = SLIDER_MIN

    if raw > SLIDER_MAX:
        raw = SLIDER_MAX

    percent = (raw - SLIDER_MIN) / (SLIDER_MAX - SLIDER_MIN)

    guess = 40 + percent * (180 - 40)

    return int(guess)

def show_guess_feedback(difference):
    if difference <= 5:
        pixels.fill((0, 255, 0))

    elif difference <= 15:
        pixels.fill((255, 150, 0))

    else:
        pixels.fill((255, 0, 0))

# -----------------------------
# TESTS
# -----------------------------

print("Testing motor...")
motor.value = True
time.sleep(1)
motor.value = False
print("Motor test done.")

print("Testing NeoSlider...")
pixels.fill((0, 0, 255))
time.sleep(1)
pixels.fill((0, 0, 0))
print("NeoSlider test done.")

# -----------------------------
# SENSOR SETUP
# -----------------------------

print("Setting up MAX30102...")

write_reg(0x09, 0x40)
time.sleep(0.5)

write_reg(0x09, 0x03)
write_reg(0x0A, 0x27)

write_reg(0x0C, 0x3F)
write_reg(0x0D, 0x3F)

print("Place finger on sensor.")

# -----------------------------
# MAIN LOOP
# -----------------------------

while True:

    data = read_reg(0x07, 6)

    red = ((data[0] << 16) | (data[1] << 8) | data[2]) & 0x3FFFF
    ir = ((data[3] << 16) | (data[4] << 8) | data[5]) & 0x3FFFF

    now = time.monotonic()

    guess_bpm = get_guess_bpm()

    # DEBUG SLIDER
    print("RAW SLIDER:", slider.value, "| Guess:", guess_bpm)

    # -----------------------------
    # NO FINGER
    # -----------------------------

    if ir < 10000:

        if now - last_no_finger_print > 2:
            print("No finger | Guess:", guess_bpm, "| IR:", ir)
            last_no_finger_print = now

        pixels.fill((0, 0, 80))

        motor.value = False
        rates = []

        last_beat = 0
        last_ir = ir
        going_up = False
        peak_ir = 0

        time.sleep(0.1)
        continue

    # -----------------------------
    # PEAK DETECTION
    # -----------------------------

    if ir > last_ir:
        going_up = True
        peak_ir = ir

    if going_up and ir < last_ir:

        drop = peak_ir - ir

        if drop > 200:

            going_up = False

            if last_beat != 0:

                delta = now - last_beat
                bpm = 60 / delta

                if 45 < bpm < 150:

                    rates.append(bpm)

                    if len(rates) > RATE_SIZE:
                        rates.pop(0)

                    avg_bpm = sum(rates) / len(rates)

                    difference = abs(int(avg_bpm) - guess_bpm)

                    print(
                        "Guess:", guess_bpm,
                        "| BPM:", int(bpm),
                        "| Avg BPM:", int(avg_bpm),
                        "| Difference:", difference,
                        "| IR:", ir
                    )

                    show_guess_feedback(difference)

                    vibrate_heartbeat()

            last_beat = now

    last_ir = ir

    time.sleep(0.05)