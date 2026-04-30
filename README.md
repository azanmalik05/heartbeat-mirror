# Heartbeat Mirror

This project is an interactive heartbeat mirror that measures a user's heart rate and provides real-time feedback through a simple interface.

## Overview
We use a MAX30102 heart rate sensor connected to an Arduino MKR Zero to detect BPM (beats per minute). The data is sent to a Python interface on a computer, where it is displayed and used to generate sound based on the user’s heart rate.

## Components
- Arduino MKR Zero
- MAX30102 Heart Rate Sensor
- Breadboard and jumper wires
- Python (for interface)

## How It Works
1. The user places their finger on the sensor.
2. The Arduino reads the heart rate and calculates BPM.
3. BPM is sent over serial to the computer.
4. The Python interface displays BPM and plays sound based on heart rate.

## Running the Project

### Arduino
- Upload the `heartbeat.ino` file to the Arduino.
- Make sure it prints data in this format:


### Python
Install dependencies: pip3 install pyserial