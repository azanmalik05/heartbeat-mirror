# Heartbeat Mirror

This project is an interactive heartbeat exhibit for kids. A MAX30102 heart rate
sensor sends BPM data from an Arduino to a Python interface. The interface shows
whether the heartbeat is slow, steady, or fast, animates a pulsing heart, and
plays a beat sound at the measured rhythm.

## What Kids See

- No finger: "Touch the sensor"
- Under 60 BPM: "Slow heartbeat"
- 60-100 BPM: "Steady heartbeat"
- Over 100 BPM: "Fast heartbeat"

These thresholds are set near the top of `heartrate.py`:

```python
LOW_BPM = 60
HIGH_BPM = 100
```

Change those numbers if you want the exhibit to classify heartbeats differently.

## Hardware

- Arduino MKR Zero
- MAX30102 heart rate sensor
- Breadboard and jumper wires
- Computer running Python

## Arduino Setup

1. Open `heart_monitor.ino` in the Arduino IDE.
2. Install the SparkFun MAX3010x library if the Arduino IDE asks for it.
3. Upload the sketch to the Arduino.
4. Keep the Arduino connected by USB.

The Arduino prints lines like:

```text
BPM: 82.4 | Avg BPM: 80
```

The Python interface reads that format.

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
