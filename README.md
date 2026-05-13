# Heartbeat Mirror

This project is an interactive heartbeat exhibit for kids. A MAX30102 heart rate
sensor sends BPM data from an Arduino to a Python interface. Kids first move a
NeoSlider to guess their heartbeat, then touch the sensor to measure it. The
interface compares the guess with the measured BPM, shows whether the heartbeat
is slow, steady, or fast, animates a pulsing heart, and plays a beat sound at
the measured rhythm.

## What Kids See

- No finger: "Touch the sensor" and a guess slider
- Under 60 BPM: "Slow heartbeat"
- 60-100 BPM: "Steady heartbeat"
- Over 100 BPM: "Fast heartbeat"
- After measuring: how close the guess was to the measured BPM

These thresholds are set near the top of `heartrate.py`:

```python
LOW_BPM = 60
HIGH_BPM = 100
```

Change those numbers if you want the exhibit to classify heartbeats differently.

## Hardware

- Arduino MKR Zero
- MAX30102 heart rate sensor
- Adafruit NeoSlider
- Vibration motor module, or a bare vibration motor plus NPN transistor/MOSFET
- Breadboard and jumper wires
- Computer running Python

## Wiring

All grounds must connect together.

### MAX30102 Heart Sensor

Connect this on the Arduino MKR Zero I2C pins:

```text
MAX30102 VIN/VCC -> MKR Zero VCC/3.3V
MAX30102 GND     -> MKR Zero GND
MAX30102 SDA     -> MKR Zero SDA
MAX30102 SCL     -> MKR Zero SCL
```

### NeoSlider

The NeoSlider is also I2C, so it shares the same SDA and SCL lines as the heart
sensor. You do not need to solder the header pads if you use the STEMMA QT /
Qwiic cable.

```text
NeoSlider black wire -> MKR Zero GND
NeoSlider red wire   -> MKR Zero 3.3V
NeoSlider blue wire  -> MKR Zero SDA
NeoSlider yellow wire -> MKR Zero SCL
```

The sketch expects the default NeoSlider I2C address, `0x30`.

### Vibration Motor

The sketch outputs motor strength on Arduino pin `D6`.

If your board is the 3-pin vibration motor module labeled `IN`, `VCC`, `GND`:

```text
Motor IN  -> MKR Zero D6
Motor VCC -> 3.3V, or 5V/VIN if the module requires it
Motor GND -> MKR Zero GND
```

If you are using a bare motor with your own NPN transistor:

```text
MKR Zero D6 -> 1k resistor -> transistor base
transistor emitter -> GND
transistor collector -> motor negative wire
motor positive wire -> 3.3V or external motor supply positive
external supply negative -> MKR Zero GND
flyback diode across motor: stripe/cathode to motor positive, anode to collector
```

Do not power a bare motor directly from an Arduino pin. The pin should only
drive the transistor.

## Arduino Setup

1. Open `heart_monitor.ino` in the Arduino IDE.
2. Install the SparkFun MAX3010x library if the Arduino IDE asks for it.
3. Install the Adafruit seesaw library and its dependencies for the NeoSlider.
4. Upload the sketch to the Arduino.
5. Keep the Arduino connected by USB.

The Arduino prints lines like:

```text
BPM: 82.4 | Avg BPM: 80 | Guess: 75 | Confidence: 8/8
```

The Python interface reads that format.

The heartbeat average uses the last 8 valid beats. While it is filling those 8
beats, the interface shows a calibrating count. For the best reading, keep the
finger still and gently covering the sensor until it says calibrated.

## Python Setup

Install Python dependency:

```bash
python3 -m pip install pyserial
```

Run the exhibit interface:

```bash
python3 heartrate.py
```

The app tries to find the Arduino automatically. If the sensor is plugged in
after the app opens, click `Reconnect sensor`.

If you see "Sensor is busy", close anything else that is using the Arduino
serial port. Common causes are:

- Arduino IDE Serial Monitor
- Arduino IDE Serial Plotter
- Another copy of `heartrate.py`

Only one program can read the Arduino serial port at a time.

## Optional Custom Sounds

The app works without downloaded sound files. It generates simple heartbeat
tones automatically.

To use your own sounds, add WAV files here:

```text
media/sounds/low.wav
media/sounds/steady.wav
media/sounds/high.wav
```

Use short files, ideally under half a second. A clean "lub-dub" heartbeat sound
works best because the app repeats it at the user's BPM.

Good search/download terms:

- "free heartbeat wav"
- "public domain heartbeat sound"
- "short heartbeat lub dub wav"

Use WAV if possible. MP3 support depends on the computer's audio player, while
WAV is the safest choice for this simple setup.

## Optional Visuals

The app works without downloaded visuals. It draws an animated heart itself.

If you want video-like visuals, convert short videos to GIFs and add:

```text
media/waiting.gif
media/low.gif
media/steady.gif
media/high.gif
```

Tkinter can display GIFs without extra Python packages. MP4 video needs extra
libraries, so GIFs are the easiest option for a reliable exhibit computer.

Good visual ideas:

- `waiting.gif`: finger touching a sensor
- `low.gif`: calm slow pulsing heart
- `steady.gif`: regular pulsing heart
- `high.gif`: faster excited pulsing heart

Keep GIFs small, around 500 pixels wide or less, so the interface stays smooth.
