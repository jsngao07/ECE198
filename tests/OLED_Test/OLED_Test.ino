
#include <Wire.h>

void setup() {
  Serial.begin(9600);
  Wire.begin();

  delay(2000);
  Serial.println("Starting I2C Scanner...");
}

void loop() {
  byte error;
  int devices = 0;

  Serial.println("Scanning...");

  for (byte address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("Device found at 0x");

      if (address < 16) {
        Serial.print("0");
      }

      Serial.println(address, HEX);
      devices++;
    }
  }

  if (devices == 0) {
    Serial.println("No I2C devices found!");
  }

  delay(3000);
}

