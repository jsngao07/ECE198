const int xPin = A0;
const int yPin = A1;
const int zPin = A2;

void setup() {
  Serial.begin(9600);
  analogReadResolution(10);
}

void loop() {
  int x = analogRead(xPin);
  int y = analogRead(yPin);
  int z = analogRead(zPin);

  Serial.print("X: ");
  Serial.print(x);

  Serial.print(" | Y: ");
  Serial.print(y);

  Serial.print(" | Z: ");
  Serial.println(z);

  delay(500);
}
