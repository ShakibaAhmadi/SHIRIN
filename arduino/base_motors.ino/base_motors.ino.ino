#include <Encoder.h>

// ---------------- ROBOT STATE ----------------
bool alt = true;
volatile unsigned long last_valid_packet_time = 0;

typedef struct {
  float linear_x;
  float linear_y;
  float angular_z;
} Twist;

Twist twist_msg = { 0.0, 0.0, 0.0 };

float scale1 = 1.0;
float scale2 = 1.18;
float scale3 = 1.0;
// --- ENCODER PINS ---
#define _EP31 35
#define _EP32 34
#define _EP21 33
#define _EP22 32
#define _EP11 19
#define _EP12 18
#define DRIVER_ENABLE_PIN 23   // change to your actual ESP32 pin
// Encoder pointers.
// The actual encoder objects are created inside setup().
Encoder* enc1 = nullptr;
Encoder* enc2 = nullptr;
Encoder* enc3 = nullptr;

// To tune rotation with respect to translation
float ROTATION_SCALE = 1.0f;

// PID Constants
float Kp = 2.5;
float Ki = 0.05;
float Kd = 0.0;

// Keep this false during the first motor and kinematics tests.
// Change it to true after all three motors behave correctly.
const bool USE_PID = true;

float targetSpeed[3] = { 0, 0, 0 };
float integral[3] = { 0, 0, 0 };
long lastCount[3] = { 0, 0, 0 };
float lastError[3] = { 0, 0, 0 };
unsigned long lastPIDTime = 0;

// Change an individual value to -1 only if that encoder reports
// the opposite sign relative to its motor command.
const int ENCODER_SIGN[3] = {
  1,  // Motor 1
  1,  // Motor 2
  1   // Motor 3
};

const float REFERENCE_TICKS_PER_SECOND[3] = {
  14000.0f,  // Motor 1
  14000.0f,  // Motor 2
  14000.0f   // Motor 3
};


// --- MOTOR CLASS WITH ENCODER ---
class MotorWithEncoder {
private:
  int pwmChannelA;
  int pwmChannelB;
  Encoder* encoder;

public:
  MotorWithEncoder(int channelA, int channelB, Encoder* enc) {
    pwmChannelA = channelA;
    pwmChannelB = channelB;
    encoder = enc;
  }

  void setEncoder(Encoder* enc) {
    encoder = enc;
  }

  void setSpeed(int speed) {

    speed = constrain(speed, -255, 255);

    if (speed > 0) {

      ledcWrite(pwmChannelA, speed);
      ledcWrite(pwmChannelB, 0);

    } 
    else if (speed < 0) {

      ledcWrite(pwmChannelA, 0);
      ledcWrite(pwmChannelB, -speed);

    } 
    else {

      ledcWrite(pwmChannelA, 0);
      ledcWrite(pwmChannelB, 0);

    }
  }

  long getTicks() {
    if (encoder == nullptr) {
      return 0;
    }

    return encoder->read();
  }
};


// --- PIN MAPPING ---
#define M1_A 16
#define M1_B 17

#define M2_A 25
#define M2_B 26

#define M3_A 27
#define M3_B 14

#define CH1_A 0
#define CH1_B 1

#define CH2_A 2
#define CH2_B 3

#define CH3_A 4
#define CH3_B 5

MotorWithEncoder motor1(CH1_A, CH1_B, nullptr); //left
MotorWithEncoder motor2(CH2_A, CH2_B, nullptr); //right
MotorWithEncoder motor3(CH3_A, CH3_B, nullptr); //back


void runPID() {
  unsigned long now = millis();

  if (now - lastPIDTime < 20) return;

  float dt = (now - lastPIDTime) / 1000.0f;

  MotorWithEncoder* motors[3] = {
    &motor1,
    &motor2,
    &motor3
  };

  for (int i = 0; i < 3; i++) {
    long currentCount = motors[i]->getTicks();

    float currentTicksPerSecond =
      ENCODER_SIGN[i] *
      (currentCount - lastCount[i]) / dt;

    lastCount[i] = currentCount;

    // Prevent a wheel with a zero target from reacting to encoder noise.
    if (abs(targetSpeed[i]) < 0.5f) {
      integral[i] = 0.0f;
      lastError[i] = 0.0f;
      motors[i]->setSpeed(0);
      continue;
    }

    // Convert encoder speed to the normalized -255 to +255 scale.
    float currentSpeed = 0.0f;

    if (REFERENCE_TICKS_PER_SECOND[i] > 0.0f) {
      currentSpeed =
        (currentTicksPerSecond /
         REFERENCE_TICKS_PER_SECOND[i]) * 255.0f;
    }

    float error = targetSpeed[i] - currentSpeed;

    integral[i] += error * dt;

    float derivative =
      (error - lastError[i]) / dt;

    // Target speed acts as feedforward.
    // PID terms correct the remaining speed error.
    float pwmOutput =
      targetSpeed[i] +
      (Kp * error) +
      (Ki * integral[i]) +
      (Kd * derivative);

    motors[i]->setSpeed((int)pwmOutput);

    lastError[i] = error;
  }

  lastPIDTime = now;
}


void setup() {
  Serial.begin(115200);
  delay(2000);

  pinMode(DRIVER_ENABLE_PIN, OUTPUT);
  digitalWrite(DRIVER_ENABLE_PIN, HIGH);
  Serial.println("ENABLE PIN HIGH");
  // Create encoders after the ESP32 has initialized.
  enc1 = new Encoder(_EP11, _EP12);
  enc2 = new Encoder(_EP21, _EP22);
  enc3 = new Encoder(_EP31, _EP32);

  motor1.setEncoder(enc1);
  motor2.setEncoder(enc2);
  motor3.setEncoder(enc3);

  // Both control inputs of every motor are PWM outputs.
  pinMode(M1_A, OUTPUT);
  pinMode(M1_B, OUTPUT);

  pinMode(M2_A, OUTPUT);
  pinMode(M2_B, OUTPUT);

  pinMode(M3_A, OUTPUT);
  pinMode(M3_B, OUTPUT);

  // Hold all active-low motor inputs inactive before enabling PWM.
  digitalWrite(M1_A, HIGH);
  digitalWrite(M1_B, HIGH);

  digitalWrite(M2_A, HIGH);
  digitalWrite(M2_B, HIGH);

  digitalWrite(M3_A, HIGH);
  digitalWrite(M3_B, HIGH);

  ledcSetup(CH1_A, 20000, 8);
  ledcSetup(CH1_B, 20000, 8);

  ledcSetup(CH2_A, 20000, 8);
  ledcSetup(CH2_B, 20000, 8);

  ledcSetup(CH3_A, 20000, 8);
  ledcSetup(CH3_B, 20000, 8);

  // Set the inactive duty before connecting channels to the pins.
  ledcWrite(CH1_A, 255);
  ledcWrite(CH1_B, 255);

  ledcWrite(CH2_A, 255);
  ledcWrite(CH2_B, 255);

  ledcWrite(CH3_A, 255);
  ledcWrite(CH3_B, 255);

  ledcAttachPin(M1_A, CH1_A);
  ledcAttachPin(M1_B, CH1_B);

  ledcAttachPin(M2_A, CH2_A);
  ledcAttachPin(M2_B, CH2_B);

  ledcAttachPin(M3_A, CH3_A);
  ledcAttachPin(M3_B, CH3_B);

  motor1.setSpeed(0);
  motor2.setSpeed(0);
  motor3.setSpeed(0);

  Serial.println("READY");

  last_valid_packet_time = millis();
}


void loop() {
  // --- SERIAL COMMUNICATION (Unchanged) ---
  static char buffer[200];
  static int idx = 0;

  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == '\n' || c == '\r') {
      if (idx > 0) {
        buffer[idx] = '\0';

        if (strcmp(buffer, "START") == 0) {
          alt = false;
          last_valid_packet_time = millis();

          Serial.println("OK START");

        } else if (strcmp(buffer, "STOP") == 0) {
          alt = true;

          // Clear the old robot command
          twist_msg.linear_x = 0.0f;
          twist_msg.linear_y = 0.0f;
          twist_msg.angular_z = 0.0f;

          // Clear wheel-speed targets
          targetSpeed[0] = 0.0f;
          targetSpeed[1] = 0.0f;
          targetSpeed[2] = 0.0f;

          // Reset PID memory
          integral[0] = 0.0f;
          integral[1] = 0.0f;
          integral[2] = 0.0f;

          lastError[0] = 0.0f;
          lastError[1] = 0.0f;
          lastError[2] = 0.0f;

          // Synchronize encoder history with current positions
          lastCount[0] = motor1.getTicks();
          lastCount[1] = motor2.getTicks();
          lastCount[2] = motor3.getTicks();

          lastPIDTime = millis();

          // Completely disable motor output
          motor1.setSpeed(0);
          motor2.setSpeed(0);
          motor3.setSpeed(0);

          Serial.println("OK STOP");

        } else if (strncmp(buffer, "<BEGIN>", 7) == 0) {
          last_valid_packet_time = millis();

          char* dataStart = buffer + 7;
          char* endToken = strstr(dataStart, "<END>");

          if (endToken != NULL) {
            *endToken = '\0';
          }

          twist_msg.linear_x =
            atof(strtok(dataStart, ","));

          twist_msg.linear_y =
            atof(strtok(NULL, ","));

          twist_msg.angular_z =
            atof(strtok(NULL, ","));

          Serial.println("READY_FOR_NEXT");
        }

        idx = 0;
      }

    } else if (idx < 199) {
      buffer[idx++] = c;
    }
  }

  // --- HEARTBEAT WATCHDOG ---
  if (!alt && millis() - last_valid_packet_time > 20000) {
    alt = true;

    // Clear old movement command
    twist_msg.linear_x = 0.0f;
    twist_msg.linear_y = 0.0f;
    twist_msg.angular_z = 0.0f;

    // Clear wheel targets
    targetSpeed[0] = 0.0f;
    targetSpeed[1] = 0.0f;
    targetSpeed[2] = 0.0f;

    // Reset PID memory
    integral[0] = 0.0f;
    integral[1] = 0.0f;
    integral[2] = 0.0f;

    lastError[0] = 0.0f;
    lastError[1] = 0.0f;
    lastError[2] = 0.0f;

    // Synchronize encoder measurements
    lastCount[0] = motor1.getTicks();
    lastCount[1] = motor2.getTicks();
    lastCount[2] = motor3.getTicks();

    lastPIDTime = millis();

    motor1.setSpeed(0);
    motor2.setSpeed(0);
    motor3.setSpeed(0);

    Serial.println("WATCHDOG STOP");
  }

  // --- INTEGRATED MOVEMENT ---
  if (alt ||
      (twist_msg.linear_x == 0 &&
       twist_msg.linear_y == 0 &&
       twist_msg.angular_z == 0)) {

    targetSpeed[0] = 0.0f;
    targetSpeed[1] = 0.0f;
    targetSpeed[2] = 0.0f;

    // Reset PID memory while stopped
    integral[0] = 0.0f;
    integral[1] = 0.0f;
    integral[2] = 0.0f;

    lastError[0] = 0.0f;
    lastError[1] = 0.0f;
    lastError[2] = 0.0f;

    lastCount[0] = motor1.getTicks();
    lastCount[1] = motor2.getTicks();
    lastCount[2] = motor3.getTicks();

    lastPIDTime = millis();

    motor1.setSpeed(0);
    motor2.setSpeed(0);
    motor3.setSpeed(0);

  } else {
    // Defensive input bounding
    float vx =
      constrain(twist_msg.linear_x, -1.0f, 1.0f);

    float vy =
      constrain(twist_msg.linear_y, -1.0f, 1.0f);

    float w =
      constrain(twist_msg.angular_z, -1.0f, 1.0f);

    // Kinematics Calculation
    float m1 =
      -sin(radians(60.0)) * vx +
      cos(radians(60.0)) * vy +
      ROTATION_SCALE * w;

    float m2 =
      -sin(radians(-60.0)) * vx +
      cos(radians(-60.0)) * vy +
      ROTATION_SCALE * w;

    float m3 =
      -sin(radians(180.0)) * vx +
      cos(radians(180.0)) * vy +
      ROTATION_SCALE * w;

    float maxVal =
      max(max(abs(m1), abs(m2)), abs(m3));

    if (maxVal > 1.0) {
      m1 /= maxVal;
      m2 /= maxVal;
      m3 /= maxVal;
    }

    // Store as targets scaled to -255 to +255.
    targetSpeed[0] = m1 * 255*scale1;
    targetSpeed[1] = m2 * 255*scale2;
    targetSpeed[2] = m3 * 255*scale3;
    Serial.print("Targets: ");
    Serial.print(targetSpeed[0]);
    Serial.print(" ");
    Serial.print(targetSpeed[1]);
    Serial.print(" ");
    Serial.println(targetSpeed[2]);
  }

  if (USE_PID) {
    // Closed-loop encoder control
    runPID();

  } else {
    // Temporary direct motor test without PID feedback
    motor1.setSpeed((int)targetSpeed[0]);
    motor2.setSpeed((int)targetSpeed[1]);
    motor3.setSpeed((int)targetSpeed[2]);
  }
}