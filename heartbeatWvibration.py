import time
import board
import busio
import digitalio

i2c = busio.I2C(board.SCL, board.SDA)
ADDR = 0x57

motor = digitalio.DigitalInOut(board.A1)
motor.direction = digitalio.Direction.OUTPUT
motor.value = False

RATE_SIZE = 5
rates = []

last_beat = 0
last_ir = 0
going_up = False

def write_reg(reg, val):
    while not i2c.try_lock():
        pass
    i2c.writeto(ADDR, bytes([reg, val]))
    i2c.unlock()

def read_reg(reg, n):
    while not i2c.try_lock():
        pass
    i2c.writeto(ADDR, bytes([reg]))
    data = bytearray(n)
    i2c.readfrom_into(ADDR, data)
    i2c.unlock()
    return data

def vibrate_heartbeat():
    # stronger-feeling triple pulse
    for i in range(3):
        motor.value = True
        time.sleep(0.045)
        motor.value = False
        time.sleep(0.025)

    # final heavier thump
    motor.value = True
    time.sleep(0.12)
    motor.value = False

print("Setting up MAX30102...")

write_reg(0x09, 0x40)
time.sleep(0.5)

write_reg(0x09, 0x03)
write_reg(0x0A, 0x27)

write_reg(0x0C, 0x3F)
write_reg(0x0D, 0x3F)

print("Place finger on sensor.")

while True:
    data = read_reg(0x07, 6)

    red = ((data[0] << 16) | (data[1] << 8) | data[2]) & 0x3FFFF
    ir = ((data[3] << 16) | (data[4] << 8) | data[5]) & 0x3FFFF

    now = time.monotonic()

    if ir < 10000:
        print("No finger | IR:", ir)

        motor.value = False
        rates = []
        last_beat = 0
        last_ir = ir
        going_up = False

        time.sleep(0.1)
        continue

    if ir > last_ir:
        going_up = True

    if going_up and ir < last_ir:
        going_up = False

        if last_beat != 0:
            delta = now - last_beat
            bpm = 60 / delta

            if 45 < bpm < 120:
                rates.append(bpm)

                if len(rates) > RATE_SIZE:
                    rates.pop(0)

                avg_bpm = sum(rates) / len(rates)

                print("BPM:", int(bpm), "| Avg BPM:", int(avg_bpm), "| IR:", ir)

                vibrate_heartbeat()

        last_beat = now

    last_ir = ir
    time.sleep(0.03)