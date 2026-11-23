
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <math.h>
#include <stdio.h>

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

const char* exerciseNames[EXERCISE_COUNT] = {
  "Arm Curl",
  "Front Arm Raise",
  "Lateral Arm Raise"
};

// Editable by Python
int targetReps[EXERCISE_COUNT] = {
  15, 12, 12
};

int targetSeconds[EXERCISE_COUNT] = {
  60, 60, 60
};

// =============================
// MENU STATES
// =============================
enum Screen {
  SELECT_EXERCISE,
  DOCTOR_DOSAGE,
  EXERCISE_TIMER,
  CONFIRM_REPS,
  COMPLETED
};

Screen currentScreen = SELECT_EXERCISE;

int selectedExercise = 0;
int actualReps = 0;

// =============================
// BUTTON DEBOUNCE
// =============================
const int buttonPins[4] = {
  BTN_START, BTN_STOP, BTN_CONFIRM, BTN_BACK
};

bool lastRaw[4] = {
  HIGH, HIGH, HIGH, HIGH
};

bool stableButton[4] = {
  HIGH, HIGH, HIGH, HIGH
};

unsigned long lastChange[4] = {
  0, 0, 0, 0
};

bool buttonPressed(int index) {
  bool raw = digitalRead(buttonPins[index]);

  if (raw != lastRaw[index]) {
    lastChange[index] = millis();
    lastRaw[index] = raw;
  }

  if (millis() - lastChange[index] > 35) {
    if (raw != stableButton[index]) {
      stableButton[index] = raw;

      if (raw == LOW) {
        return true;
      }
    }
  }

  return false;
}

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

void pauseTimer() {
  if (timerRunning) {
    accumulatedMs = getElapsedMs();
    timerRunning = false;
  }
}

// =============================
// ACCELEROMETER
// =============================
float filteredX = 0;
float filteredY = 0;
float filteredZ = 0;

float baseX = 0;
float baseY = 0;
float baseZ = 0;

float movement = 0;

bool sensorCalibrated = false;

// Rep detection state
bool armRaised = false;
bool candidateActive = false;

unsigned long candidateStartMs = 0;
unsigned long lastRepMs = 0;
unsigned long lastSampleMs = 0;

// =============================
// REP COUNT SETTINGS
// =============================

// ADC change thresholds
// These are NOT physical angles.
const float UPPER_THRESHOLD[3] = {
  40.0, 50.0, 50.0
};

const float LOWER_THRESHOLD[3] = {
  22.0, 18.0, 18.0
};

const unsigned long SAMPLE_INTERVAL_MS = 20;
const unsigned long POSITION_HOLD_MS = 150;
const unsigned long MIN_REP_INTERVAL_MS = 600;

// Low-pass filter
const float FILTER_ALPHA = 0.15;

// =============================
// SENSOR CALIBRATION
// =============================
void calibrateSensor() {
  display.clearDisplay();

  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  display.setCursor(0, 0);
  display.println("CALIBRATING...");

  display.setCursor(0, 20);
  display.println("Keep arm DOWN");

  display.setCursor(0, 35);
  display.println("Hold sensor STILL");

  display.display();

  delay(1000);

  float sumX = 0;
  float sumY = 0;
  float sumZ = 0;

  const int samples = 100;

  for (int i = 0; i < samples; i++) {
    sumX += analogRead(ACC_X);
    sumY += analogRead(ACC_Y);
    sumZ += analogRead(ACC_Z);

    delay(10);
  }

  baseX = sumX / samples;
  baseY = sumY / samples;
  baseZ = sumZ / samples;

  filteredX = baseX;
  filteredY = baseY;
  filteredZ = baseZ;

  movement = 0;

  armRaised = false;
  candidateActive = false;

  lastSampleMs = millis();
  lastRepMs = 0;

  sensorCalibrated = true;
}

// =============================
// AUTOMATIC REP COUNTING
// =============================
void updateAccelerometer() {
  if (!timerRunning || !sensorCalibrated) {
    return;
  }

  unsigned long now = millis();

  if (now - lastSampleMs < SAMPLE_INTERVAL_MS) {
    return;
  }

  lastSampleMs = now;

  float rawX = analogRead(ACC_X);
  float rawY = analogRead(ACC_Y);
  float rawZ = analogRead(ACC_Z);

  // Smooth sensor data
  filteredX += FILTER_ALPHA * (rawX - filteredX);
  filteredY += FILTER_ALPHA * (rawY - filteredY);
  filteredZ += FILTER_ALPHA * (rawZ - filteredZ);

  // Difference from starting position
  float dx = filteredX - baseX;
  float dy = filteredY - baseY;
  float dz = filteredZ - baseZ;

  // Magnitude of ADC change
  movement = sqrt(
    dx * dx +
    dy * dy +
    dz * dz
  );

  float upper = UPPER_THRESHOLD[selectedExercise];
  float lower = LOWER_THRESHOLD[selectedExercise];

  // =============================
  // STATE 1: WAIT FOR ARM RAISED
  // =============================
  if (!armRaised) {
    if (movement >= upper) {
      if (!candidateActive) {
        candidateActive = true;
        candidateStartMs = now;
      }

      if (now - candidateStartMs >= POSITION_HOLD_MS) {
        armRaised = true;
        candidateActive = false;
      }
    } else {
      candidateActive = false;
    }
  }

  // =============================
  // STATE 2: WAIT FOR ARM LOWERED
  // =============================
  else {
    if (movement <= lower) {
      if (!candidateActive) {
        candidateActive = true;
        candidateStartMs = now;
      }

      if (now - candidateStartMs >= POSITION_HOLD_MS) {
        if (
          lastRepMs == 0 ||
          now - lastRepMs >= MIN_REP_INTERVAL_MS
        ) {
          actualReps++;
          lastRepMs = now;

          armRaised = false;
          candidateActive = false;
        }
      }
    } else {
      candidateActive = false;
    }
  }
}

// =============================
// RESET EXERCISE
// =============================
void resetExercise() {
  timerRunning = false;
  timerStarted = false;

  timerStartMs = 0;
  accumulatedMs = 0;

  actualReps = 0;

  sensorCalibrated = false;

  armRaised = false;
  candidateActive = false;

  movement = 0;

  lastRepMs = 0;
}

// =============================
// OLED HELPERS
// =============================
void drawHeader(const char* title) {
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  display.setCursor(0, 0);
  display.println(title);

  display.drawLine(
    0, 11, 127, 11, SSD1306_WHITE
  );
}

void printTime(unsigned long seconds) {
  unsigned long minutes = seconds / 60;
  seconds %= 60;

  if (minutes < 10) {
    display.print("0");
  }

  display.print(minutes);
  display.print(":");

  if (seconds < 10) {
    display.print("0");
  }

  display.print(seconds);
}

// =============================
// SCREEN 1: SELECT EXERCISE
// =============================
void drawSelectExercise() {
  drawHeader("SELECT EXERCISE");

  for (int i = 0; i < EXERCISE_COUNT; i++) {
    display.setCursor(0, 16 + i * 12);

    if (i == selectedExercise) {
      display.print("> ");
    } else {
      display.print("  ");
    }

    display.println(exerciseNames[i]);
  }

  display.setCursor(0, 55);
  display.println("Knob | B3: Select");
}

// =============================
// SCREEN 2: DOCTOR DOSAGE
// =============================
void drawDoctorDosage() {
  drawHeader("DOCTOR'S DOSAGE");

  display.setCursor(0, 17);
  display.println(exerciseNames[selectedExercise]);

  display.setCursor(0, 30);
  display.print("Target reps: ");
  display.println(targetReps[selectedExercise]);

  display.setCursor(0, 41);
  display.print("Target time: ");
  display.print(targetSeconds[selectedExercise]);
  display.println("s");

  display.setCursor(0, 55);
  display.println("B3:Next B4:Back");
}

// =============================
// SCREEN 3: EXERCISE TIMER
// =============================
void drawExerciseTimer() {
  drawHeader("EXERCISE TIMER");

  display.setCursor(0, 15);
  display.setTextSize(2);

  display.print("Reps:");
  display.println(actualReps);

  display.setTextSize(1);

  display.setCursor(0, 37);
  display.print("Move:");
  display.print(movement, 0);

  display.print(" Time:");
  printTime(getElapsedMs() / 1000);

  display.setCursor(0, 53);

  if (!timerStarted) {
    display.println("B1: Start");
  }

  else if (timerRunning) {
    display.println("B2: Pause");
  }

  else {
    display.println("B1:Go B3:Done B4:Rst");
  }
}

// =============================
// SCREEN 4: CONFIRM REPS
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
  display.println("B3:Save B4:Back");
}

// =============================
// SCREEN 5: COMPLETED
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
// DRAW CURRENT SCREEN
// =============================
void drawScreen() {
  display.clearDisplay();

  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  switch (currentScreen) {
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
// SERIAL DATA OUTPUT
// =============================
void sendExerciseRecord() {
  Serial.print("EXERCISE,");
  Serial.print(exerciseNames[selectedExercise]);

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
// NEW: RECEIVE DOCTOR PRESCRIPTION
// =============================
// Python sends: SET,exercise_id,reps,seconds
// Example: SET,0,20,90
//
// Arduino responds:
// ACK,0
// ERROR,BUSY
// ERROR,INVALID
// ERROR,FORMAT
// ERROR,TOO_LONG

void receiveDoctorPrescription() {
  static char buffer[64];
  static byte index = 0;

  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '\n') {
      buffer[index] = '\0';
      index = 0;

      int exerciseIndex;
      int reps;
      int seconds;
      char extra;

      if (sscanf(
            buffer,
            "SET,%d,%d,%d%c",
            &exerciseIndex,
            &reps,
            &seconds,
            &extra
          ) == 3) {

        if (timerStarted) {
          Serial.println("ERROR,BUSY");
        }
        else if (
          exerciseIndex >= 0 &&
          exerciseIndex < EXERCISE_COUNT &&
          reps > 0 && reps <= 1000 &&
          seconds > 0 && seconds <= 3600
        ) {
          targetReps[exerciseIndex] = reps;
          targetSeconds[exerciseIndex] = seconds;

          Serial.print("ACK,");
          Serial.println(exerciseIndex);
        }
        else {
          Serial.println("ERROR,INVALID");
        }
      }
      else {
        Serial.println("ERROR,FORMAT");
      }
    }
    else if (c != '\r') {
      if (index < sizeof(buffer) - 1) {
        buffer[index++] = c;
      }
      else {
        index = 0;
        Serial.println("ERROR,TOO_LONG");
      }
    }
  }
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
    while (true) {
      delay(1000);
    }
  }

  drawScreen();
}

// =============================
// MAIN LOOP
// =============================
void loop() {

  // NEW: Receive prescription updates from Python
  receiveDoctorPrescription();

  bool b1 = buttonPressed(0);
  bool b2 = buttonPressed(1);
  bool b3 = buttonPressed(2);
  bool b4 = buttonPressed(3);

  // =============================
  // SELECT EXERCISE
  // =============================
  if (currentScreen == SELECT_EXERCISE) {
    int pot = analogRead(POT_PIN);

    selectedExercise = constrain(
      (pot * 3L) / 1024,
      0,
      2
    );

    if (b3) {
      currentScreen = DOCTOR_DOSAGE;
    }
  }

  // =============================
  // DOCTOR DOSAGE
  // =============================
  else if (currentScreen == DOCTOR_DOSAGE) {
    if (b3) {
      resetExercise();
      currentScreen = EXERCISE_TIMER;
    }

    else if (b4) {
      currentScreen = SELECT_EXERCISE;
    }
  }

  // =============================
  // EXERCISE TIMER
  // =============================
  else if (currentScreen == EXERCISE_TIMER) {

    if (b4) {
      resetExercise();
    }

    else if (b1 && !timerRunning) {
      if (!sensorCalibrated) {
        calibrateSensor();
      }

      startTimer();
    }

    else if (b2 && timerRunning) {
      pauseTimer();
      candidateActive = false;
    }

    else if (
      b3 &&
      timerStarted &&
      !timerRunning
    ) {
      currentScreen = CONFIRM_REPS;
    }

    updateAccelerometer();
  }

  // =============================
  // CONFIRM REPS
  // =============================
  else if (currentScreen == CONFIRM_REPS) {
    if (b3) {
      sendExerciseRecord();
      currentScreen = COMPLETED;
    }

    else if (b4) {
      currentScreen = EXERCISE_TIMER;
    }
  }

  // =============================
  // COMPLETED
  // =============================
  else if (currentScreen == COMPLETED) {
    if (b4) {
      resetExercise();
      currentScreen = SELECT_EXERCISE;
    }
  }

  // =============================
  // OLED REFRESH
  // =============================
  static unsigned long lastDraw = 0;

  if (millis() - lastDraw >= 100) {
    lastDraw = millis();
    drawScreen();
  }
}
