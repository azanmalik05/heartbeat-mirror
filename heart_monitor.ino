#include <Wire.h>
#include "Adafruit_seesaw.h"
#include <seesaw_neopixel.h>
#include "MAX30105.h"
#include "heartRate.h"

MAX30105 particleSensor;
Adafruit_seesaw neoSlider;
seesaw_NeoPixel sliderPixels = seesaw_NeoPixel(4, 14, NEO_GRB + NEO_KHZ800);

const byte RATE_SIZE = 8;
byte rates[RATE_SIZE] = {0};
byte rateSpot = 0;
byte rateCount = 0;

long lastBeat = 0;
float beatsPerMinute = 0;
int beatAvg = 0;
int guessBpm = 90;
bool heartSensorFound = false;
bool sliderFound = false;
bool i2cBusReady = false;
bool hardwareInitTried = false;

unsigned long lastPrint = 0;
unsigned long lastSliderRead = 0;

const byte SLIDER_ADDR = 0x30;
const byte MAX30102_ADDR = 0x57;
const byte SLIDER_ANALOG_PIN = 18;
const byte MOTOR_PIN = 6;
const int FINGER_THRESHOLD = 50000;
const int MIN_BPM = 45;
const int MAX_BPM = 190;

void setup() {
  Serial.begin(9600);

  pinMode(MOTOR_PIN, OUTPUT);
  analogWrite(MOTOR_PIN, 0);
}

void initHardware() {
  hardwareInitTried = true;
  heartSensorFound = false;
  sliderFound = false;
  i2cBusReady = false;

  resetHeartbeat();
  Serial.println("Heartbeat Mirror starting.");
  Serial.println("Checking I2C bus...");
  Serial.flush();

  pinMode(SDA, INPUT_PULLUP);
  pinMode(SCL, INPUT_PULLUP);
  delay(50);
  i2cBusReady = digitalRead(SDA) == HIGH && digitalRead(SCL) == HIGH;

  if (i2cBusReady) {
    Wire.begin();
    heartSensorFound = i2cDevicePresent(MAX30102_ADDR);
    sliderFound = i2cDevicePresent(SLIDER_ADDR);

    Serial.print("I2C MAX30102 0x57: ");
    Serial.println(heartSensorFound ? "found" : "not found");
    Serial.print("I2C NeoSlider 0x30: ");
    Serial.println(sliderFound ? "found" : "not found");

    if (heartSensorFound) {
      heartSensorFound = particleSensor.begin(Wire, I2C_SPEED_FAST);
    }

    if (heartSensorFound) {
      particleSensor.setup(60, 4, 2, 100, 411, 4096);
      particleSensor.setPulseAmplitudeRed(0x1F);
      particleSensor.setPulseAmplitudeGreen(0);
    } else {
      Serial.println("MAX30102 not found. Check wiring.");
    }

    if (sliderFound) {
      sliderFound = neoSlider.begin(SLIDER_ADDR);
      if (sliderFound) {
        sliderPixels.begin(SLIDER_ADDR);
        sliderPixels.setBrightness(20);
        sliderPixels.show();
      }
    } else {
      Serial.println("NeoSlider not found. Guess will stay at 90 BPM.");
    }
  } else {
    Serial.println("I2C bus stuck low. Check SDA and SCL wiring.");
  }

  Serial.println("Place your finger on the sensor.");
}

void loop() {
  if (!hardwareInitTried) {
    if (Serial.available()) {
      char command = Serial.read();
      if (command == 'S' || command == 's') {
        initHardware();
      }
    }

    if (millis() - lastPrint >= 1000) {
      lastPrint = millis();
      Serial.println("Arduino ready. Waiting for app start command.");
    }
    return;
  }

  readGuessSlider();

  if (!heartSensorFound) {
    setMotorStrength(0);
    if (millis() - lastPrint >= 1000) {
      lastPrint = millis();
      if (i2cBusReady) {
        Serial.print("MAX30102 not found. Check wiring. | Guess: ");
      } else {
        Serial.print("I2C bus stuck low. Check SDA and SCL wiring. | Guess: ");
      }
      Serial.print(guessBpm);
      printSliderStatus();
    }
    return;
  }

  long irValue = particleSensor.getIR();

  if (irValue < FINGER_THRESHOLD) {
    resetHeartbeat();
    setMotorStrength(0);
  } else if (checkForBeat(irValue)) {
    long delta = millis() - lastBeat;
    lastBeat = millis();

    if (delta > 0) {
      beatsPerMinute = 60.0 / (delta / 1000.0);
    }

    if (beatsPerMinute >= MIN_BPM && beatsPerMinute <= MAX_BPM) {
      rates[rateSpot++] = (byte)beatsPerMinute;
      rateSpot %= RATE_SIZE;
      if (rateCount < RATE_SIZE) {
        rateCount++;
      }

      int sum = 0;
      for (byte x = 0; x < rateCount; x++) {
        sum += rates[x];
      }
      beatAvg = sum / rateCount;
      setMotorStrength(beatAvg);
    }
  }

  if (millis() - lastPrint >= 1000) {
    lastPrint = millis();

    if (irValue < FINGER_THRESHOLD) {
      Serial.print("No finger detected | Guess: ");
      Serial.print(guessBpm);
      printSliderStatus();
    } else if (beatAvg == 0) {
      Serial.print("Calibrating | Guess: ");
      Serial.print(guessBpm);
      Serial.print(" | Confidence: ");
      Serial.print(rateCount);
      Serial.print("/");
      Serial.print(RATE_SIZE);
      printSliderStatus();
    } else {
      Serial.print("BPM: ");
      Serial.print(beatsPerMinute);
      Serial.print(" | Avg BPM: ");
      Serial.print(beatAvg);
      Serial.print(" | Guess: ");
      Serial.print(guessBpm);
      Serial.print(" | Confidence: ");
      Serial.print(rateCount);
      Serial.print("/");
      Serial.print(RATE_SIZE);
      printSliderStatus();
    }
  }
}

void readGuessSlider() {
  if (!sliderFound || millis() - lastSliderRead < 80) {
    return;
  }

  lastSliderRead = millis();
  int raw = neoSlider.analogRead(SLIDER_ANALOG_PIN);
  guessBpm = map(constrain(raw, 0, 1023), 0, 1023, MIN_BPM, MAX_BPM);
  updateSliderPixels();
}

void updateSliderPixels() {
  int litPixels = map(guessBpm, MIN_BPM, MAX_BPM, 1, 4);
  for (int i = 0; i < 4; i++) {
    if (i < litPixels) {
      int red = map(guessBpm, MIN_BPM, MAX_BPM, 20, 255);
      int blue = map(guessBpm, MIN_BPM, MAX_BPM, 180, 0);
      sliderPixels.setPixelColor(i, sliderPixels.Color(red, 40, blue));
    } else {
      sliderPixels.setPixelColor(i, 0);
    }
  }
  sliderPixels.show();
}

void setMotorStrength(int bpm) {
  if (bpm <= 0) {
    analogWrite(MOTOR_PIN, 0);
    return;
  }

  int pwm = map(constrain(bpm, MIN_BPM, MAX_BPM), MIN_BPM, MAX_BPM, 70, 255);
  analogWrite(MOTOR_PIN, pwm);
}

void resetHeartbeat() {
  beatsPerMinute = 0;
  beatAvg = 0;
  rateSpot = 0;
  rateCount = 0;
  lastBeat = 0;
  for (byte x = 0; x < RATE_SIZE; x++) {
    rates[x] = 0;
  }
}

bool i2cDevicePresent(byte address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

void printSliderStatus() {
  Serial.print(" | NeoSlider: ");
  Serial.println(sliderFound ? "found" : "not found");
}
