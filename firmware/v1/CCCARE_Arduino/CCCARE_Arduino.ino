
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

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

// =============================
// EXERCISES
// =============================
const int EXERCISE_COUNT = 3;

const char* exercises[EXERCISE_COUNT] = {
  "Arm Curl",
  "Leg Raise",
  "Sit to Stand"
};

// Temporary prescriptions for testing.
// Later, these will come from the Python website.
int targetReps[EXERCISE_COUNT] = {
  15, 12, 20
};

int targetSeconds[EXERCISE_COUNT] = {
  60, 45, 120
};

// =============================
// MENU STATES
// =============================
enum MenuState {
  SELECT_EXERCISE,
  DOCTOR_DOSAGE,
  EXERCISE_TIMER,
  ENTER_REPS,
  COMPLETED
};

MenuState currentMenu = SELECT_EXERCISE;

int selectedExercise = 0;
int actualReps = 0;

// =============================
// TIMER VARIABLES
// =============================
bool timerRunning = false;
bool timerStarted = false;

unsigned long timerStartMs = 0;
unsigned long accumulatedMs = 0;

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
// TIMER FUNCTIONS
// =============================
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

void resetTimer() {
  timerRunning = false;
  timerStarted = false;

  timerStartMs = 0;
  accumulatedMs = 0;
  actualReps = 0;
}

// =============================
// OLED HELPER FUNCTIONS
// =============================
void printTime(unsigned long totalSeconds) {
  unsigned long minutes = totalSeconds / 60;
  unsigned long seconds = totalSeconds % 60;

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
// MENU 1: SELECT EXERCISE
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

    display.println(exercises[i]);
  }

  display.setCursor(0, 55);
  display.println("Knob | B3: Select");
}

// =============================
// MENU 2: DOCTOR'S DOSAGE
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
// MENU 3: EXERCISE TIMER
// =============================
void drawExerciseTimer() {
  drawHeader("EXERCISE TIMER");

  display.setTextSize(2);
  display.setCursor(30, 19);
  printTime(getElapsedMs() / 1000);

  display.setTextSize(1);
  display.setCursor(0, 44);

  if (!timerStarted) {
    display.println("Press B1 to Start");
  }
  else if (timerRunning) {
    display.println("Timer running...");
    display.println("B2: Stop");
  }
  else {
    display.println("Did you finish?");
    display.println("B1:Go B3:Yes B4:Reset");
  }
}

// =============================
// ENTER ACTUAL REPS
// =============================
void drawEnterReps() {
  drawHeader("ENTER ACTUAL REPS");

  display.setTextSize(2);
  display.setCursor(45, 23);
  display.print(actualReps);

  display.setTextSize(1);
  display.setCursor(0, 55);
  display.println("Knob | B3: Save");
}

// =============================
// MENU 4: COMPLETED
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

    case ENTER_REPS:
      drawEnterReps();
      break;

    case COMPLETED:
      drawCompleted();
      break;
  }

  display.display();
}

// =============================
// SEND DATA TO PYTHON
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

  // ---------------------------
  // MENU 1: SELECT EXERCISE
  // ---------------------------
  if (currentMenu == SELECT_EXERCISE) {

    int potValue = analogRead(POT_PIN);

    int newSelection = constrain(
      (potValue * 3L) / 1024,
      0,
      2
    );

    selectedExercise = newSelection;

    if (b3) {
      currentMenu = DOCTOR_DOSAGE;
    }
  }

  // ---------------------------
  // MENU 2: DOCTOR'S DOSAGE
  // ---------------------------
  else if (currentMenu == DOCTOR_DOSAGE) {

    if (b3) {
      resetTimer();
      currentMenu = EXERCISE_TIMER;
    }
    else if (b4) {
      currentMenu = SELECT_EXERCISE;
    }
  }

  // ---------------------------
  // MENU 3: EXERCISE TIMER
  // ---------------------------
  else if (currentMenu == EXERCISE_TIMER) {

    if (b4) {
      resetTimer();
    }
    else if (b1 && !timerRunning) {
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
      currentMenu = ENTER_REPS;
    }
  }

  // ---------------------------
  // ENTER ACTUAL REPS
  // ---------------------------
  else if (currentMenu == ENTER_REPS) {

    actualReps = map(
      analogRead(POT_PIN),
      0, 1023,
      0, 104
    );

    if (b3) {
      sendExerciseRecord();
      currentMenu = COMPLETED;
    }
    else if (b4) {
      currentMenu = EXERCISE_TIMER;
    }
  }

  // ---------------------------
  // MENU 4: COMPLETED
  // ---------------------------
  else if (currentMenu == COMPLETED) {

    if (b4) {
      resetTimer();
      currentMenu = SELECT_EXERCISE;
    }
  }

  // Refresh OLED every 100 ms
  static unsigned long lastDraw = 0;

  if (millis() - lastDraw >= 100) {
    lastDraw = millis();
    drawScreen();
  }
}





