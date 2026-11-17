
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <math.h>

// =============================
// OLED SETTINGS
// =============================
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define OLED_ADDRESS 0x3C

Adafruit_SSD1306 display(
  SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET
);

// =============================
// HARDWARE PINS
// =============================
const int BTN_START = 3;
const int BTN_STOP = 4;
const int BTN_CONFIRM = 5;
const int BTN_BACK = 6;

const int POT_PIN = A0;

// Analog accelerometer
const int ACC_X = A1;
const int ACC_Y = A2;
const int ACC_Z = A3;

// =============================
// EXERCISES
// =============================
const int EXERCISE_COUNT = 3;

const char* exercises[EXERCISE_COUNT] = {
  "Arm Curl",
  "Front Arm Raise",
  "Lateral Arm Raise"
};

// Temporary testing prescriptions
int targetReps[EXERCISE_COUNT] = {
  15, 12, 12
};

int targetSeconds[EXERCISE_COUNT] = {
  60, 60, 60
};

// =============================
// MENU STATES
// =============================
enum MenuState {
  SELECT_EXERCISE,
  DOCTOR_DOSAGE,
  EXERCISE_TIMER,
  CONFIRM_REPS,
  COMPLETED
};

MenuState currentMenu = SELECT_EXERCISE;

int selectedExercise = 0;
int actualReps = 0;

// =============================
// TIMER
// =============================
bool timerRunning = false;
bool timerStarted = false;

unsigned long timerStartMs = 0;
unsigned long accumulatedMs = 0;

unsigned long getElapsedMs() {
  if (timerRunning) {
    return accumulatedMs + millis() - timerStartMs;
  }
  return accumulatedMs;
}

void startTimer() {
  if (!timerRunning) {
    timerStartMs = millis();
    timerRunning = true;
    timerStarted = true;
  }
}

void stopTimer() {
  if (timerRunning) {
    accumulatedMs = getElapsedMs();
    timerRunning = false;
  }
}

// =============================
// ACCELEROMETER VARIABLES
// =============================

// Reference vector at starting position
float baseX = 0;
float baseY = 0;
float baseZ = 0;

// Filtered sensor readings
float filteredX = 0;
float filteredY = 0;
float filteredZ = 0;

bool sensorCalibrated = false;

// True after arm reaches raised position
bool armRaised = false;

// Measured angle from starting position
float movementAngle = 0;

// Starting thresholds for testing.
// Tune separately for each exercise.
float upperThreshold[EXERCISE_COUNT] = {
  55.0, 55.0, 55.0
};

float lowerThreshold[EXERCISE_COUNT] = {
  25.0, 25.0, 25.0
};

// Minimum time a position must be held
const unsigned long POSITION_HOLD_MS = 180;

// Avoid counting unusually fast cycles
const unsigned long MIN_REP_INTERVAL_MS = 450;

// Sensor sampling
const unsigned long SAMPLE_INTERVAL_MS = 20;

unsigned long lastSampleMs = 0;
unsigned long phaseStartMs = 0;
unsigned long lastRepMs = 0;

bool upperCandidate = false;
bool lowerCandidate = false;

// =============================
// BUTTON DEBOUNCE
// =============================
const int buttonPins[4] = {
  BTN_START,
  BTN_STOP,
  BTN_CONFIRM,
  BTN_BACK
};

bool lastRaw[4] = {
  HIGH, HIGH, HIGH, HIGH
};

bool stableState[4] = {
  HIGH, HIGH, HIGH, HIGH
};

unsigned long lastChange[4] = {
  0, 0, 0, 0
};

bool buttonPressed(int index) {
  bool reading = digitalRead(buttonPins[index]);

  if (reading != lastRaw[index]) {
    lastChange[index] = millis();
    lastRaw[index] = reading;
  }

  if (millis() - lastChange[index] >= 35) {
    if (reading != stableState[index]) {
      stableState[index] = reading;

      if (reading == LOW) {
        return true;
      }
    }
  }

  return false;
}

// =============================
// SENSOR FUNCTIONS
// =============================

void readAccelerometer(
  float &x, float &y, float &z
) {
  x = analogRead(ACC_X);
  y = analogRead(ACC_Y);
  z = analogRead(ACC_Z);
}

// Measure the starting position.
// Keep arm still and lowered.
void calibrateAccelerometer() {
  const int samples = 50;

  float sumX = 0;
  float sumY = 0;
  float sumZ = 0;

  for (int i = 0; i < samples; i++) {
    float x, y, z;
    readAccelerometer(x, y, z);

    sumX += x;
    sumY += y;
    sumZ += z;

    delay(10);
  }

  baseX = sumX / samples;
  baseY = sumY / samples;
  baseZ = sumZ / samples;

  filteredX = baseX;
  filteredY = baseY;
  filteredZ = baseZ;

  movementAngle = 0;
  armRaised = false;
  upperCandidate = false;
  lowerCandidate = false;

  lastRepMs = 0;
  lastSampleMs = millis();

  sensorCalibrated = true;

  Serial.println("ACCELEROMETER CALIBRATED");
}

// Estimate movement from the initial
// gravity vector.
//
// This assumes an analog accelerometer
// with gravity-sensitive output.
//
// Raw ADC values must be converted to
// acceleration by subtracting the
// sensor's zero-g offsets.
//
// For an initial prototype, use the
// change in the calibrated raw vector.
// See calibration notes below.
void updateAccelerometer() {
  if (!timerRunning || !sensorCalibrated) {
    return;
  }

  unsigned long now = millis();

  if (now - lastSampleMs < SAMPLE_INTERVAL_MS) {
    return;
  }

  lastSampleMs = now;

  float x, y, z;
  readAccelerometer(x, y, z);

  // Low-pass filtering
  const float alpha = 0.15;

  filteredX += alpha * (x - filteredX);
  filteredY += alpha * (y - filteredY);
  filteredZ += alpha * (z - filteredZ);

  // Difference from starting position.
  // This is an ADC-change metric,
  // NOT a physical angle in degrees.
  float dx = filteredX - baseX;
  float dy = filteredY - baseY;
  float dz = filteredZ - baseZ;

  movementAngle = sqrt(
    dx * dx +
    dy * dy +
    dz * dz
  );

  // These are initial ADC thresholds.
  // Adjust using real sensor data.
  float upper = upperThreshold[selectedExercise];
  float lower = lowerThreshold[selectedExercise];

  // Detect raised position
  if (!armRaised) {
    if (movementAngle >= upper) {
      if (!upperCandidate) {
        upperCandidate = true;
        phaseStartMs = now;
      }

      if (now - phaseStartMs >= POSITION_HOLD_MS) {
        armRaised = true;
        upperCandidate = false;
        lowerCandidate = false;
      }
    } else {
      upperCandidate = false;
    }
  }

  // Detect return to starting position
  else {
    if (movementAngle <= lower) {
      if (!lowerCandidate) {
        lowerCandidate = true;
        phaseStartMs = now;
      }

      if (now - phaseStartMs >= POSITION_HOLD_MS) {
        armRaised = false;
        lowerCandidate = false;
        upperCandidate = false;

        if (
          lastRepMs == 0 ||
          now - lastRepMs >= MIN_REP_INTERVAL_MS
        ) {
          actualReps++;
          lastRepMs = now;

          Serial.print("REP_COUNT,");
          Serial.println(actualReps);
        }
      }
    } else {
      lowerCandidate = false;
    }
  }

  // Debug data for Serial Plotter
  // Uncomment while tuning:
  /*
  Serial.print("Movement:");
  Serial.print(movementAngle);
  Serial.print(",Upper:");
  Serial.print(upper);
  Serial.print(",Lower:");
  Serial.println(lower);
  */
}

// =============================
// RESET
// =============================
void resetTimer() {
  timerRunning = false;
  timerStarted = false;

  timerStartMs = 0;
  accumulatedMs = 0;

  actualReps = 0;

  sensorCalibrated = false;
  armRaised = false;
  upperCandidate = false;
  lowerCandidate = false;

  movementAngle = 0;
  lastRepMs = 0;
}

// =============================
// OLED HELPERS
// =============================
void printTime(unsigned long totalSeconds) {
  unsigned long minutes = totalSeconds / 60;
  unsigned long seconds = totalSeconds % 60;

  if (minutes < 10) display.print("0");
  display.print(minutes);
  display.print(":");
  if (seconds < 10) display.print("0");
  display.print(seconds);
}

void drawHeader(const char* title) {
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  display.setCursor(0, 0);
  display.println(title);

  display.drawLine(
    0, 11, 127, 11, SSD1306_WHITE
  );
}

// =============================
// MENU 1
// =============================
void drawSelectExercise() {
  drawHeader("SELECT EXERCISE");

  for (int i = 0; i < EXERCISE_COUNT; i++) {
    display.setCursor(0, 16 + i * 12);

    display.print(
      i == selectedExercise ? "> " : "  "
    );

    display.println(exercises[i]);
  }

  display.setCursor(0, 55);
  display.println("Knob | B3: Select");
}

// =============================
// MENU 2
// =============================
void drawDoctorDosage() {
  drawHeader("DOCTOR'S DOSAGE");

  display.setCursor(0, 17);
  display.println(exercises[selectedExercise]);

  display.setCursor(0, 30);
  display.print("Target reps: ");
  display.println(targetReps[selectedExercise]);

  display.setCursor(0, 41);
  display.print("Target time: ");
  display.print(targetSeconds[selectedExercise]);
  display.println("s");

  display.setCursor(0, 55);
  display.println("B3:Next  B4:Back");
}

// =============================
// MENU 3
// =============================
void drawExerciseTimer() {
  drawHeader("AUTO REP COUNTER");

  display.setTextSize(2);
  display.setCursor(0, 16);
  display.print("Reps:");
  display.println(actualReps);

  display.setTextSize(1);
  display.setCursor(0, 37);

  printTime(getElapsedMs() / 1000);

  display.setCursor(0, 53);

  if (!timerStarted) {
    display.println("Arm down | B1:Start");
  }
  else if (timerRunning) {
    display.println("B2:Pause");
  }
  else {
    display.println("B1:Go B3:Done B4:Rst");
  }
}

// =============================
// MENU 4
// =============================
void drawConfirmReps() {
  drawHeader("CONFIRM REPS");

  display.setCursor(0, 19);
  display.println("Automatically counted:");

  display.setTextSize(2);
  display.setCursor(45, 32);
  display.println(actualReps);

  display.setTextSize(1);
  display.setCursor(0, 55);
  display.println("B3:Save  B4:Back");
}

// =============================
// MENU 5
// =============================
void drawCompleted() {
  drawHeader("GOOD JOB!");

  display.setCursor(0, 18);
  display.println("Exercise completed!");

  display.setCursor(0, 31);
  display.print("Actual reps: ");
  display.println(actualReps);

  display.setCursor(0, 43);
  display.print("Actual time: ");
  printTime(getElapsedMs() / 1000);

  display.setCursor(0, 55);
  display.println("B4: New Exercise");
}

// =============================
// SCREEN RENDERING
// =============================
void drawScreen() {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  switch (currentMenu) {
    case SELECT_EXERCISE:
      drawSelectExercise();
      break;

    case DOCTOR_DOSAGE:
      drawDoctorDosage();
      break;

    case EXERCISE_TIMER:
      drawExerciseTimer();
      break;

    case CONFIRM_REPS:
      drawConfirmReps();
      break;

    case COMPLETED:
      drawCompleted();
      break;
  }

  display.display();
}

// =============================
// SERIAL DATA
// =============================
void sendExerciseRecord() {
  Serial.print("EXERCISE,");
  Serial.print(exercises[selectedExercise]);

  Serial.print(",TARGET_REPS,");
  Serial.print(targetReps[selectedExercise]);

  Serial.print(",ACTUAL_REPS,");
  Serial.print(actualReps);

  Serial.print(",TARGET_SECONDS,");
  Serial.print(targetSeconds[selectedExercise]);

  Serial.print(",ACTUAL_SECONDS,");
  Serial.println(getElapsedMs() / 1000);
}

// =============================
// SETUP
// =============================
void setup() {
  Serial.begin(115200);

  analogReadResolution(10);

  for (int i = 0; i < 4; i++) {
    pinMode(buttonPins[i], INPUT_PULLUP);
  }

  if (!display.begin(
    SSD1306_SWITCHCAPVCC,
    OLED_ADDRESS
  )) {
    Serial.println("OLED FAILED");
    while (true) {}
  }

  Serial.println("OLED SUCCESS");
  Serial.println("CCCARE SYSTEM READY");

  drawScreen();
}

// =============================
// MAIN LOOP
// =============================
void loop() {
  bool b1 = buttonPressed(0);
  bool b2 = buttonPressed(1);
  bool b3 = buttonPressed(2);
  bool b4 = buttonPressed(3);

  // MENU 1
  if (currentMenu == SELECT_EXERCISE) {
    int potValue = analogRead(POT_PIN);

    selectedExercise = constrain(
      (potValue * 3L) / 1024,
      0, 2
    );

    if (b3) {
      currentMenu = DOCTOR_DOSAGE;
    }
  }

  // MENU 2
  else if (currentMenu == DOCTOR_DOSAGE) {
    if (b3) {
      resetTimer();
      currentMenu = EXERCISE_TIMER;
    }
    else if (b4) {
      currentMenu = SELECT_EXERCISE;
    }
  }

  // MENU 3
  else if (currentMenu == EXERCISE_TIMER) {
    if (b4) {
      resetTimer();
    }
    else if (b1 && !timerRunning) {
      if (!sensorCalibrated) {
        display.clearDisplay();
        drawHeader("CALIBRATING...");
        display.setCursor(0, 25);
        display.println("Keep arm lowered");
        display.display();

        calibrateAccelerometer();
      }

      // Avoid counting movement during
      // calibration as a repetition
      armRaised = false;
      upperCandidate = false;
      lowerCandidate = false;

      startTimer();
    }
    else if (b2 && timerRunning) {
      stopTimer();
    }
    else if (
      b3 &&
      timerStarted &&
      !timerRunning
    ) {
      currentMenu = CONFIRM_REPS;
    }

    updateAccelerometer();
  }

  // MENU 4
  else if (currentMenu == CONFIRM_REPS) {
    if (b3) {
      sendExerciseRecord();
      currentMenu = COMPLETED;
    }
    else if (b4) {
      currentMenu = EXERCISE_TIMER;
    }
  }

  // MENU 5
  else if (currentMenu == COMPLETED) {
    if (b4) {
      resetTimer();
      currentMenu = SELECT_EXERCISE;
    }
  }

  static unsigned long lastDraw = 0;

  if (millis() - lastDraw >= 100) {
    lastDraw = millis();
    drawScreen();
  }
}
