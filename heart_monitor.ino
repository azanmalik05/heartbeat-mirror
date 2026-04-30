#include <Wire.h>
#include "MAX30105.h"
#include "heartRate.h"

MAX30105 particleSensor;

const byte RATE_SIZE = 4;
byte rates[RATE_SIZE] = {0};
byte rateSpot = 0;

long lastBeat = 0;
float beatsPerMinute = 0;
int beatAvg = 0;

unsigned long lastPrint = 0;

void setup() {
  Serial.begin(9600);
  while (!Serial);

  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("MAX30102 not found. Check wiring.");
    while (1);
  }

  particleSensor.setup();
  particleSensor.setPulseAmplitudeRed(0x0A);
  particleSensor.setPulseAmplitudeGreen(0);

  Serial.println("Place your finger on the sensor.");
}

void loop() {
  long irValue = particleSensor.getIR();

  if (checkForBeat(irValue)) {
    long delta = millis() - lastBeat;
    lastBeat = millis();

    if (delta > 0) {
      beatsPerMinute = 60.0 / (delta / 1000.0);
    }

    if (beatsPerMinute > 40 && beatsPerMinute < 180) {
      rates[rateSpot++] = (byte)beatsPerMinute;
      rateSpot %= RATE_SIZE;

      int sum = 0;
      for (byte x = 0; x < RATE_SIZE; x++) {
        sum += rates[x];
      }
      beatAvg = sum / RATE_SIZE;
    }
  }

  if (millis() - lastPrint >= 1000) {
    lastPrint = millis();

    if (irValue < 50000) {
      Serial.println("No finger detected");
    } else {
      Serial.print("BPM: ");
      Serial.print(beatsPerMinute);
      Serial.print(" | Avg BPM: ");
      Serial.println(beatAvg);
    }
  }
}
