# CCCARE Exercise Tracker

ECE 198 — Personalized Exercise Tracking System

Project Overview

This project aims to help CCCARE simplify personalized exercise tracking using an Arduino hardware interface and a Python software system.

Hardware Components

- Arduino UNO R4 Minima
- SSD1306 OLED Display
- Four pushbuttons
- Potentiometer

Current Features

- Select from three exercises using a potentiometer
- Display target repetitions and target exercise time
- Start, pause, resume, and reset an exercise timer
- Record actual repetitions (1–100)
- Display exercise completion results
- Send exercise records through USB Serial

Arduino Pin Configuration

| Component | Pin |
- Start Button | D3 |
- Stop Button | D4 |
- Select / Confirm Button | D5 |
- Back / Reset Button | D6 |
- Potentiometer | A0 |
- OLED | SDA / SCL |

Required Libraries

- Adafruit GFX Library
- Adafruit SSD1306

Future Development

- Python Serial communication
- SQLite database integration
- Doctor's website for managing exercise prescriptions
- Patient progress tracking
