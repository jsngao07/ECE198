# ECE198 — CCCARE Exercise Tracking Prototype

CCCARE combines an Arduino exercise interface with a Flask and SQLite web app for exercise plans and progress logging.

## Current Progress

| Area | Current status |
| --- | --- |
| Arduino | V2 shows exercise targets, times the session, counts repetitions automatically, displays the live count, and prints the confirmed record over USB Serial. |
| Potentiometer | V2 uses the potentiometer for exercise selection. V1 also used it for manual repetition entry. |
| Accelerometer | V2 uses three-axis accelerometer readings for automatic counting. Thresholds still need validation on hardware. The standalone sketch is available for raw readings. |
| Web app | Source includes account roles, exercise plans, manual progress logging, and appointment workflows. |
| Device integration | Receiving Arduino records in Python, saving them automatically, and sending personalized targets back to the device are planned. |

## Repository Layout

- [V2 Arduino sketch — automatic repetition counting](firmware/v2/CCCARE_Arduino/CCCARE_Arduino.ino)
- [V1 Arduino sketch — manual repetition entry](firmware/v1/CCCARE_Arduino/CCCARE_Arduino.ino)
- [Hardware testing and design update](docs/Hardware_Testing.md)
- [Firmware notes](docs/Firmware_Testing)
- [Accelerometer test](tests/Accelerometer_Test/Accelerometer_Test.ino)
- [OLED test](tests/OLED_Test/OLED_Test.ino)
- [Potentiometer test](tests/Potentiometer_Test/Potentiometer_Test.ino)
- [Flask app and database code](Web%20%26%20Database/)

## Arduino Setup

The documented board is the Arduino UNO R4 Minima. The main sketch uses a 128 × 64 I²C OLED at address 0x3C and the Adafruit GFX and Adafruit SSD1306 libraries. Buttons connect to D3 (Start or Resume), D4 (Stop), D5 (Confirm), and D6 (Back or Reset).

| Sketch | Analog inputs | Serial Monitor |
| --- | --- | --- |
| V2 Arduino sketch | Potentiometer on A0, accelerometer X on A1, Y on A2, Z on A3 | 115200 baud |
| Accelerometer test | X on A1, Y on A2, Z on A3 | 9600 baud |

Open each test from its matching folder in Arduino IDE. Open the V2 sketch from its CCCARE_Arduino folder. Check the accelerometer model and supply requirements before wiring. The test uses 10-bit readings and a 500 ms delay. The potentiometer uses A0, separate from the three accelerometer inputs.

### Using automatic counting in V2

Select an exercise and press Start. During the initial calibration prompt, hold the sensor still in the exercise starting position. The OLED shows the live count while the timer runs. Press Stop, then Confirm to review the result. Press Confirm again to send the exercise record over USB Serial.

## Web App Setup

From the repository root, change into the Web & Database folder. In a Python virtual environment, run the following commands:

    python -m pip install -r requirements.txt
    python app.py

Open the local URL printed by Flask. The app creates its SQLite database under Web & Database/instance/ on startup. Use sample data for the local demo.

## Next Steps

1. Document and check sensor placement for each exercise.
2. Compare V2 counts with manually observed repetitions at different speeds, including pauses and partial movements, then tune the thresholds.
3. Agree on shared exercise identifiers and implement serial transfer between Arduino and the web app.
