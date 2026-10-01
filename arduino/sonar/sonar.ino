#include <NewPing.h>

// Define the digital pins connected to the sensor
const int trigPin = 26;   //3
const int echoPin = 16;

const int trigPin1 = 25;  //2
const int echoPin1 = 15;

const int trigPin2 = 22;  //1
const int echoPin2 = 12;

const int trigPin3 = 23;  //4
const int echoPin3 = 13;

int vicinity_threshold = 100;
int intimacy_threshold = 70;

#define SONAR_NUM 4 
#define MAX_DISTANCE 300

float dist[SONAR_NUM];
float cm[SONAR_NUM];
float cm_prec[SONAR_NUM];
float cm_raw[SONAR_NUM];
float cm_prec1[SONAR_NUM];
float cm_prec2[SONAR_NUM];
float cm_prec3[SONAR_NUM];
float cm_prec4[SONAR_NUM];
int numActualData;

NewPing sonar[SONAR_NUM] = {
  NewPing(trigPin2, echoPin2, MAX_DISTANCE),
  NewPing(trigPin1, echoPin1, MAX_DISTANCE),
  NewPing(trigPin, echoPin, MAX_DISTANCE),
  NewPing(trigPin3, echoPin3, MAX_DISTANCE),
};


void setup() {
  // Initialize serial communication at 9600 bits per second
  Serial.begin(115200);
  
  // Set pin modes
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(trigPin1, OUTPUT);
  pinMode(echoPin1, INPUT);
  pinMode(trigPin2, OUTPUT);
  pinMode(echoPin2, INPUT);
  pinMode(trigPin3, OUTPUT);
  pinMode(echoPin3, INPUT); 
}

void loop() {
  // Fetch data continuously

  publishSensorMsg();
  // A small delay to avoid flooding the serial buffer and to let 
  // residual ultrasonic echoes clear out before the next pulse.
  delay(60); 
}

void getSonarData() {
  for (uint8_t i = 0; i < SONAR_NUM; i++) {
    cm_prec4[i] = cm_prec3[i];
    cm_prec3[i] = cm_prec2[i];
    cm_prec2[i] = cm_prec1[i];
    cm_prec1[i] = cm_raw[i];
    cm_prec[i] = cm[i];
  }

  for (uint8_t i = 0; i < SONAR_NUM; i++) {
    cm_raw[i] = sonar[i].ping_cm();
    numActualData = 0;

    if (cm_raw[i] == 0) {
      if (cm_prec1[i] + cm_prec2[i] + cm_prec3[i] + cm_prec4[i] == 0)
        cm[i] = MAX_DISTANCE;
      else {
        if (cm_prec1[i] != 0) numActualData++;
        if (cm_prec2[i] != 0) numActualData++;
        if (cm_prec3[i] != 0) numActualData++;
        if (cm_prec4[i] != 0) numActualData++;
        cm[i] = (cm_prec1[i] + cm_prec2[i] + cm_prec3[i] + cm_prec4[i]) / numActualData;
      }
    } else {
      if (cm_prec1[i] != 0) numActualData++;
      if (cm_prec2[i] != 0) numActualData++;
      if (cm_prec3[i] != 0) numActualData++;
      if (cm_prec4[i] != 0) numActualData++;
      cm[i] = (cm_raw[i] + cm_prec1[i] + cm_prec2[i] + cm_prec3[i] + cm_prec4[i]) / (numActualData + 1);
    }
  }
}

void publishSensorMsg() {
  getSonarData();

  // Stampa i valori su seriale
  for (int i = 0; i < SONAR_NUM; i++) {
    //Serial.print((int)cm[i]);
    Serial.print((int)cm[i]);
    
    // Print a comma after every number EXCEPT the last one
    if (i < SONAR_NUM - 1) {
      Serial.print(","); 
    }
  }
  Serial.println();
  }


  