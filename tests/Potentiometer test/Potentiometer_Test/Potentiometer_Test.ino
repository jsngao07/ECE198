
const int POT_PIN = A0;

void setup() {
  Serial.begin(115200);
}

void loop() {
  int potValue = analogRead(POT_PIN);
  int exercise = constrain((potValue * 3L) / 1024, 0, 2);

  Serial.print("Potentiometer: ");
  Serial.print(potValue);
  Serial.print(" | Selected Exercise: ");
  Serial.println(exercise + 1);

  delay(300);
}

