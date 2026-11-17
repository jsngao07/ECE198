# ECE198 — CCCARE Exercise Tracking Prototype

CCCARE combines an Arduino exercise interface with a Flask and SQLite web app for exercise plans and progress logging.

## Current Progress

| Area | Current status |
| --- | --- |
| Arduino | Lets users select an exercise, view hard-coded targets, time a session, enter repetitions manually, and print a record over USB Serial. |
| Potentiometer | The main firmware uses it for exercise selection and manual repetition input. The team found its readings insufficiently accurate in the current setup. |
| Accelerometer | A standalone test prints raw X/Y/Z readings. The team chose the accelerometer for automatic repetition counting, which is pending implementation and validation. |
| Web app | Source includes account roles, exercise plans, manual progress logging, and appointment workflows. |
| Device integration | Receiving Arduino records in Python, saving them automatically, and sending personalized targets back to the device are planned. |

## Repository Layout

- [Main Arduino sketch](CCCARE_Arduino.ino)
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
| Main Arduino sketch | Potentiometer on A0 | 115200 baud |
| Accelerometer test | X on A0, Y on A1, Z on A2 | 9600 baud |

Open each test from its matching folder in Arduino IDE. Open the main sketch from a folder named CCCARE_Arduino. Check the accelerometer model and supply requirements before wiring. The test uses 10-bit readings and a 500 ms delay. Assign separate inputs before combining the two sketches because both currently use A0.

## Web App Setup

From the repository root, change into the Web & Database folder. In a Python virtual environment, run the following commands:

    python -m pip install -r requirements.txt
    python app.py

Open the local URL printed by Flask. The app creates its SQLite database under Web & Database/instance/ on startup. Use sample data for the local demo.

## Next Steps

1. Confirm accelerometer wiring and mounting, then collect readings during representative movements.
2. Develop the counter and compare it with manually observed repetitions at different speeds, including pauses and partial movements.
3. Integrate the validated counter with the timer and OLED.
4. Agree on shared exercise identifiers and implement serial transfer between Arduino and the web app.
