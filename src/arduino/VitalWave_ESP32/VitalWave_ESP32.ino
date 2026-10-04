#include <Arduino.h>
#include "Seeed_Arduino_mmWave.h"
#include <NimBLEDevice.h>

// ============================================================
// MR60BHA2 UART
// ============================================================

#ifdef ESP32
#include <HardwareSerial.h>
HardwareSerial mmWaveSerial(0);
#else
#define mmWaveSerial Serial1
#endif

SEEED_MR60BHA2 mmWave;


// ============================================================
// BLE configuration
// Nordic UART Service compatible UUIDs
// ============================================================

#define BLE_DEVICE_NAME "MR60BHA2-Radar"
#define SERVICE_UUID "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define TX_CHARACTERISTIC_UUID "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"


NimBLECharacteristic* txCharacteristic = nullptr;

bool bleConnected = false;


// ============================================================
// BLE connection callbacks
// ============================================================

class ServerCallbacks : public NimBLEServerCallbacks {
  void onConnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo) override {
    bleConnected = true;

    Serial.println();
    Serial.println("BLE client connected.");
  }

  void onDisconnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo, int reason) override {
    bleConnected = false;

    Serial.println();
    Serial.println("BLE client disconnected.");
  }
};


ServerCallbacks serverCallbacks;

void sendBLEValue(const char* name, float value) {
  char buffer[24];
  snprintf(buffer, sizeof(buffer), "%s=%.2f\n", name, value);

  // Send to USB Serial Monitor too
  // Serial.print(buffer);

  // Send over Bluetooth
  if (bleConnected && txCharacteristic != nullptr) {
    txCharacteristic->setValue(buffer);
    txCharacteristic->notify();
  }
}


// ============================================================
// Setup
// ============================================================

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("MR60BHA2 + BLE starting...");

  // Start radar
  mmWave.begin(&mmWaveSerial);
  Serial.println("Radar initialized.");


  // Start Bluetooth
  NimBLEDevice::init(BLE_DEVICE_NAME);
  NimBLEServer* server = NimBLEDevice::createServer();
  server->setCallbacks(&serverCallbacks);

  // Automatically advertise again after PC disconnects
  server->advertiseOnDisconnect(true);

  // Create BLE service
  NimBLEService* service = server->createService(SERVICE_UUID);

  // Create TX characteristic
  txCharacteristic =
      service->createCharacteristic(
          TX_CHARACTERISTIC_UUID,
          NIMBLE_PROPERTY::READ |
          NIMBLE_PROPERTY::NOTIFY
      );

  txCharacteristic->setValue("Radar ready\n");
  service->start();


  // Start advertising
  NimBLEAdvertising* advertising = NimBLEDevice::getAdvertising();
  advertising->addServiceUUID(SERVICE_UUID);
  advertising->setName(BLE_DEVICE_NAME);
  advertising->start();

  Serial.println("BLE advertising started.");
  Serial.print("BLE address: ");
  Serial.println(NimBLEDevice::getAddress().toString().c_str());
  Serial.println("Device name: " BLE_DEVICE_NAME);
  Serial.println();
}


// ============================================================
// Main loop
// ============================================================

void loop() {
  if (mmWave.update(100)) {
    float total_phase, breath_phase, heart_phase;
    if (mmWave.getHeartBreathPhases(total_phase, breath_phase, heart_phase)) {
      sendBLEValue("TP", total_phase);
      sendBLEValue("BP", breath_phase);
      sendBLEValue("HP", heart_phase);
    }

    float breath_rate;
    if (mmWave.getBreathRate(breath_rate)) {
      sendBLEValue("BR", breath_rate);
    }

    float heart_rate;
    if (mmWave.getHeartRate(heart_rate)) {
      sendBLEValue("HR", heart_rate);
    }

    float distance;
    if (mmWave.getDistance(distance)) {
      sendBLEValue("D", distance);
    }
  }
}
