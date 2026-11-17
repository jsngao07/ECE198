# Hardware Testing

## Components
- Arduino UNO R4 Minima
- OLED display (128 x 64)
- Potentiometer
- Push buttons (D3-D6)
- Analog three-axis accelerometer (added for evaluation)

## Earlier Test Results
- **OLED display:** Previously reported as passed.
- **Push buttons:** Previously reported as passed after correcting breadboard connections.
- **Potentiometer:** Basic operation previously passed, but subsequent testing identified insufficient measurement accuracy in the current setup. It should not be treated as validated for reliable repetition input.

## Issues Encountered
The potentiometer and buttons initially did not work properly because some breadboard holes did not provide reliable connections. Moving the wires restored basic operation. This earlier wiring fix did not establish the potentiometer's measurement accuracy.

## Design Update — November 17, 2026
The team reported that the potentiometer readings were not accurate enough for the intended use and decided to add an accelerometer for automatic exercise repetition counting. The goal is to reduce dependence on manual repetition entry through the potentiometer.

An initial accelerometer test sketch is available at [Accelerometer_Test.ino](../tests/Accelerometer_Test/Accelerometer_Test.ino). It reads raw X, Y, and Z values from A1, A2, and A3 using 10-bit resolution and prints them at 9600 baud every 500 ms. It does not yet detect movements or count repetitions. Counting accuracy has not yet been validated.

## Integration Checks and Next Steps
- Confirm and document the accelerometer model, supply voltage, wiring, and mounting position.
- Keep the potentiometer on A0 and connect accelerometer X, Y, and Z to A1, A2, and A3 respectively.
- Record stationary and movement readings, select a suitable sampling interval, and evaluate filtering and counting thresholds.
- Compare automatic counts with manually observed repetitions, including pauses and unintended movements.
- Retest the complete system after integrating the sensor.

## Current Status
Basic OLED/button operation was previously reported as working. Potentiometer accuracy remains a limitation, and accelerometer-based automatic counting is the next development step rather than a completed feature.
