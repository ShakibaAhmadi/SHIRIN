#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// Initialize PCA9685
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);

// ---------------- SAFETY & CALIBRATION CONFIG ----------------
const int STOP_DEADBAND = 5;                // Treat any speed from -5 to +5 as exactly 0
const bool DISABLE_CHANNEL_ON_STOP = false; // Keep sending the active neutral pulse

// Symmetrical continuous-servo range around neutral
const int SPEED_RANGE_US = 200;

// Positional Limits (Mouth / Eyes)
#define SERVOMIN 100
#define SERVOMAX 700

#define SWITCH_CH8 16
#define SWITCH_CH9 17
#define SWITCH_CH10 18
#define SWITCH_CH11 19

bool sent_limit_8  = false;
bool sent_limit_9  = false;
bool sent_limit_10 = false;
bool sent_limit_11 = false;

// Continuous-servo neutral pulses
int stopPulses[16] = {
  1500, 1500, 1500, 1500,
  1500, 1500, 1500, 1500,
  1400, 1400, 1400, 1400,
  1500, 1500, 1500, 1500
};

String input = "";

// Timers for Continuous motor auto-stops
unsigned long contStopTimes[16] = {0};

struct ServoTracker {
  bool isActive;
  float targetExp;
  float currentExp;
  unsigned long lastMoveTime;
  int speedDelay; // ms delay per 1% movement
};

ServoTracker posTrackers[16];

// ---------------- MATH & CONVERSIONS ----------------
int expressionToAngle(float value) {
  value = constrain(value, -100, 100);
  return map(value, -100, 100, 15, 165);
}

void moveExpression(float expValue, int channel) {
  int angle = expressionToAngle(expValue);
  int pulse = map(angle, 0, 180, SERVOMIN, SERVOMAX);
  pwm.setPWM(channel, 0, pulse);
}

void setContinuousUS(uint8_t channel, int speed) {
  int neutral = stopPulses[channel];

  speed = constrain(speed, -100, 100);

  if (speed == 0) {
    int pulse = (neutral * 4096L) / 20000L;
    pwm.setPWM(channel, 0, pulse);
    return;
  }

  const int POSITIVE_START_OFFSET_US = 105;
  const int NEGATIVE_START_OFFSET_US = 10;
  const int MAX_OFFSET_US = 200;

  int magnitude = abs(speed);
  int offset;
  int microseconds;

  if (speed > 0) {
    offset = map(
      magnitude,
      1,
      100,
      POSITIVE_START_OFFSET_US,
      MAX_OFFSET_US
    );

    microseconds = neutral + offset;

  } else {
    offset = map(
      magnitude,
      1,
      100,
      NEGATIVE_START_OFFSET_US,
      MAX_OFFSET_US
    );

    microseconds = neutral - offset;
  }

  int pulse = (microseconds * 4096L) / 20000L;
  pwm.setPWM(channel, 0, pulse);

  Serial.print("CH: ");
  Serial.print(channel);
  Serial.print(" speed: ");
  Serial.print(speed);
  Serial.print(" pulse: ");
  Serial.println(microseconds);
}

// ---------------- I2C DIAGNOSTIC SCANNER ----------------
void scanI2CBus() {
  Serial.println("\n--- [I2C DIAGNOSTIC SCAN] ---");

  byte error;
  byte address;
  int nDevices = 0;

  for (address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();

    if (error == 0) {
      Serial.print(
        "[I2C SUCCESS] Found device at address 0x"
      );

      if (address < 16) {
        Serial.print("0");
      }

      Serial.println(address, HEX);
      nDevices++;

    } else if (error == 4) {
      Serial.print(
        "[I2C ERROR] Unknown error at address 0x"
      );

      if (address < 16) {
        Serial.print("0");
      }

      Serial.println(address, HEX);
    }
  }

  if (nDevices == 0) {
    Serial.println(
      "[I2C FAILURE] No I2C devices detected! "
      "Check SDA/SCL and GND."
    );
  } else {
    Serial.println(
      "[I2C SUCCESS] Scan completed successfully."
    );
  }

  Serial.println("-----------------------------\n");
}

// ---------------- SERIAL PARSER ----------------
void processInput(String msg) {

  // 1. POSITIONAL COMMANDS
  // U:ch,pos,spd,ch,pos,spd...
  if (msg.startsWith("U:")) {
    msg.remove(0, 2);

    int lastPos = 0;

    while (lastPos < msg.length()) {
      int p1 = msg.indexOf(',', lastPos);

      if (p1 == -1) {
        break;
      }

      int p2 = msg.indexOf(',', p1 + 1);

      if (p2 == -1) {
        break;
      }

      int p3 = msg.indexOf(',', p2 + 1);
      int endPos = (p3 == -1) ? msg.length() : p3;

      int ch = msg.substring(lastPos, p1).toInt();
      float pos = msg.substring(p1 + 1, p2).toFloat();
      int spd = msg.substring(p2 + 1, endPos).toInt();

      if (ch >= 0 && ch < 16) {
        posTrackers[ch].isActive = true;
        posTrackers[ch].targetExp = pos;
        posTrackers[ch].speedDelay = spd;

        Serial.print("[DEBUG] POS U -> CH:");
        Serial.print(ch);
        Serial.print(" Target:");
        Serial.print(pos);
        Serial.print(" Spd:");
        Serial.println(spd);
      }

      lastPos = (
        p3 == -1
      ) ? msg.length() : p3 + 1;
    }
  }

  // 2. CONTINUOUS COMMANDS
  // D:ch,spd,time,ch,spd,time...
  else if (msg.startsWith("D:")) {
    msg.remove(0, 2);

    int lastPos = 0;

    while (lastPos < msg.length()) {
      int p1 = msg.indexOf(',', lastPos);

      if (p1 == -1) {
        break;
      }

      int p2 = msg.indexOf(',', p1 + 1);

      if (p2 == -1) {
        break;
      }

      int p3 = msg.indexOf(',', p2 + 1);
      int endPos = (p3 == -1) ? msg.length() : p3;

      int ch = msg.substring(lastPos, p1).toInt();
      int spd = msg.substring(p1 + 1, p2).toInt();
      int dur = msg.substring(p2 + 1, endPos).toInt();

      if (ch >= 0 && ch < 16) {
        // Write speed to the motor
        setContinuousUS(ch, spd);

        // Set the automatic stop timer in the future
        contStopTimes[ch] = (
          dur > 0
        ) ? millis() + dur : 0;

        Serial.print("[DEBUG] CONT D -> CH:");
        Serial.print(ch);
        Serial.print(" Spd:");
        Serial.print(spd);
        Serial.print(" Time:");
        Serial.println(dur);
      }

      lastPos = (
        p3 == -1
      ) ? msg.length() : p3 + 1;
    }
  }
}

// ---------------- SETUP ----------------
void setup() {
  pinMode(SWITCH_CH8, INPUT_PULLUP);
  pinMode(SWITCH_CH9, INPUT_PULLUP);
  pinMode(SWITCH_CH10, INPUT_PULLUP);
  pinMode(SWITCH_CH11, INPUT_PULLUP);
  //SWITCH_CH8 = HIGH

  Serial.begin(115200);

  Wire.begin(4, 5); // SDA, SCL for ESP32

  pwm.begin();
  pwm.setPWMFreq(50);

  // Initialize tracking array
  for (int i = 0; i < 16; i++) {
    posTrackers[i].isActive = false;
    posTrackers[i].currentExp = 0;
    posTrackers[i].targetExp = 0;
  }

  // Pre-stop all continuous channels
  int startChannels[] = {7, 8, 9, 10, 11};

  for (int i = 0; i < 5; i++) {
    setContinuousUS(startChannels[i], 0);
  }

  delay(500);

  scanI2CBus();

  Serial.println(
    "[DEBUG] Unified PCA9685 Expressive System Ready!"
  );
}

// ---------------- LOOP (NON-BLOCKING) ----------------
void loop() {

  // 1. Read incoming Serial from Jetson/Laptop
  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n') {
      processInput(input);
      input = "";
    } else {
      input += c;
    }
  }

  unsigned long currentMillis = millis();

  // If pressed LOW, immediately stop the motor
  // and clear its software timer

  // --- CHANNEL 8 ---
  if (digitalRead(SWITCH_CH8) == LOW) {
    setContinuousUS(8, 0);
    contStopTimes[8] = 0;

    if (!sent_limit_8) {
      Serial.println("LIMIT_HIT:8");
      sent_limit_8 = true;
    }
  } else {
    sent_limit_8 = false;
  }

  // --- CHANNEL 9 ---
  if (digitalRead(SWITCH_CH9) == LOW) {
    setContinuousUS(9, 0);
    contStopTimes[9] = 0;

    if (!sent_limit_9) {
      Serial.println("LIMIT_HIT:9");
      sent_limit_9 = true;
    }
  } else {
    sent_limit_9 = false;
  }

  // --- CHANNEL 10 ---
  if (digitalRead(SWITCH_CH10) == LOW) {
    setContinuousUS(10, 0);
    contStopTimes[10] = 0;

    if (!sent_limit_10) {
      Serial.println("LIMIT_HIT:10");
      sent_limit_10 = true;
    }
  } else {
    sent_limit_10 = false;
  }

  // --- CHANNEL 11 ---
  if (digitalRead(SWITCH_CH11) == LOW) {
    setContinuousUS(11, 0);
    contStopTimes[11] = 0;

    if (!sent_limit_11) {
      Serial.println("LIMIT_HIT:11");
      sent_limit_11 = true;
    }
  } else {
    sent_limit_11 = false;
  }

  // 2. Handle Continuous Auto-Stops
  for (int i = 0; i < 16; i++) {
    if (
      contStopTimes[i] > 0
      && currentMillis >= contStopTimes[i]
    ) {
      setContinuousUS(i, 0);
      contStopTimes[i] = 0;

      Serial.print("[DEBUG] CH:");
      Serial.print(i);
      Serial.println(" auto-stopped.");
    }
  }

  // 3. Handle Positional Smooth Sweeps
  for (int i = 0; i < 16; i++) {
    if (posTrackers[i].isActive) {
      if (
        posTrackers[i].currentExp
        != posTrackers[i].targetExp
      ) {

        if (posTrackers[i].speedDelay <= 0) {
          // Instant Snap
          posTrackers[i].currentExp =
              posTrackers[i].targetExp;

          moveExpression(
            posTrackers[i].currentExp,
            i
          );

        } else {
          // Smooth Step over Time
          if (
            currentMillis
            - posTrackers[i].lastMoveTime
            >= posTrackers[i].speedDelay
          ) {

            if (
              posTrackers[i].currentExp
              < posTrackers[i].targetExp
            ) {
              posTrackers[i].currentExp += 1.0;

              if (
                posTrackers[i].currentExp
                > posTrackers[i].targetExp
              ) {
                posTrackers[i].currentExp =
                    posTrackers[i].targetExp;
              }

            } else {
              posTrackers[i].currentExp -= 1.0;

              if (
                posTrackers[i].currentExp
                < posTrackers[i].targetExp
              ) {
                posTrackers[i].currentExp =
                    posTrackers[i].targetExp;
              }
            }

            moveExpression(
              posTrackers[i].currentExp,
              i
            );

            posTrackers[i].lastMoveTime =
                currentMillis;
          }
        }
      }
    }
  }
}