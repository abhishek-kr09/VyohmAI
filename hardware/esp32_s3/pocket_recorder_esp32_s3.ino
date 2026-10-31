#include <Arduino.h>
#include <FS.h>
#include <SD.h>
#include <SPI.h>
#include <WiFi.h>
#include <time.h>
#include "driver/i2s.h"

const char* WIFI_SSID = "replace-with-wifi";
const char* WIFI_PASSWORD = "replace-with-password";
const char* SERVER_HOST = "192.168.1.25";
constexpr uint16_t SERVER_PORT = 8000;
const char* SERVER_PATH = "/upload";
const char* DEVICE_ID = "esp32-s3-001";

constexpr int RECORD_BUTTON_PIN = 0;
constexpr int SD_CS_PIN = 10;
constexpr int BATTERY_ADC_PIN = -1;
constexpr i2s_port_t I2S_PORT = I2S_NUM_0;
constexpr int I2S_BCLK_PIN = 4;
constexpr int I2S_LRCLK_PIN = 5;
constexpr int I2S_DATA_PIN = 6;
constexpr uint32_t SAMPLE_RATE = 16000;
constexpr uint16_t CHANNELS = 1;
constexpr uint16_t BITS_PER_SAMPLE = 16;
constexpr size_t AUDIO_BUFFER_SAMPLES = 512;

bool recording = false;
File audioFile;
uint32_t audioBytes = 0;
uint32_t recordingStarted = 0;
String pendingPath;
String pendingTimestamp;
uint32_t pendingDurationMs = 0;
int pendingBattery = -1;
uint32_t nextRetryAt = 0;

void writeLittleEndian(File& file, uint32_t value, uint8_t bytes) {
  for (uint8_t index = 0; index < bytes; ++index) {
    file.write(static_cast<uint8_t>(value >> (index * 8)));
  }
}

void writeWavHeader(File& file, uint32_t dataLength) {
  file.seek(0);
  file.write(reinterpret_cast<const uint8_t*>("RIFF"), 4);
  writeLittleEndian(file, 36 + dataLength, 4);
  file.write(reinterpret_cast<const uint8_t*>("WAVEfmt "), 8);
  writeLittleEndian(file, 16, 4);
  writeLittleEndian(file, 1, 2);
  writeLittleEndian(file, CHANNELS, 2);
  writeLittleEndian(file, SAMPLE_RATE, 4);
  writeLittleEndian(file, SAMPLE_RATE * CHANNELS * BITS_PER_SAMPLE / 8, 4);
  writeLittleEndian(file, CHANNELS * BITS_PER_SAMPLE / 8, 2);
  writeLittleEndian(file, BITS_PER_SAMPLE, 2);
  file.write(reinterpret_cast<const uint8_t*>("data"), 4);
  writeLittleEndian(file, dataLength, 4);
}

String timestampNow() {
  struct tm timeInfo;
  if (!getLocalTime(&timeInfo, 1000)) {
    return "";
  }
  char value[32];
  strftime(value, sizeof(value), "%Y-%m-%dT%H:%M:%S+00:00", &timeInfo);
  return String(value);
}

int batteryPercent() {
  if (BATTERY_ADC_PIN < 0) {
    return -1;
  }
  return constrain(map(analogRead(BATTERY_ADC_PIN), 0, 4095, 0, 100), 0, 100);
}

bool connectWifi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t deadline = millis() + 20000;
  while (WiFi.status() != WL_CONNECTED && millis() < deadline) {
    delay(250);
  }
  return WiFi.status() == WL_CONNECTED;
}

void configureI2s() {
  i2s_config_t config = {};
  config.mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_RX);
  config.sample_rate = SAMPLE_RATE;
  config.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;
  config.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  config.communication_format = I2S_COMM_FORMAT_I2S;
  config.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  config.dma_buf_count = 8;
  config.dma_buf_len = AUDIO_BUFFER_SAMPLES;
  config.use_apll = false;
  config.tx_desc_auto_clear = false;
  config.fixed_mclk = 0;
  i2s_pin_config_t pins = {};
  pins.bck_io_num = I2S_BCLK_PIN;
  pins.ws_io_num = I2S_LRCLK_PIN;
  pins.data_out_num = I2S_PIN_NO_CHANGE;
  pins.data_in_num = I2S_DATA_PIN;
  i2s_driver_install(I2S_PORT, &config, 0, nullptr);
  i2s_set_pin(I2S_PORT, &pins);
}

void startRecording() {
  String path = "/recording-" + String(millis()) + ".wav";
  audioFile = SD.open(path, FILE_WRITE);
  if (!audioFile) {
    return;
  }
  for (int index = 0; index < 44; ++index) {
    audioFile.write(static_cast<uint8_t>(0));
  }
  audioBytes = 0;
  recordingStarted = millis();
  recording = true;
}

void captureAudio() {
  int32_t samples[AUDIO_BUFFER_SAMPLES];
  size_t bytesRead = 0;
  i2s_read(I2S_PORT, samples, sizeof(samples), &bytesRead, 0);
  const size_t sampleCount = bytesRead / sizeof(int32_t);
  for (size_t index = 0; index < sampleCount; ++index) {
    int16_t sample = static_cast<int16_t>(samples[index] >> 14);
    audioFile.write(reinterpret_cast<uint8_t*>(&sample), sizeof(sample));
    audioBytes += sizeof(sample);
  }
}

String multipartValue(const String& boundary, const String& name, const String& value) {
  return "--" + boundary + "\r\nContent-Disposition: form-data; name=\"" + name +
         "\"\r\n\r\n" + value + "\r\n";
}

bool uploadRecording(const String& path, const String& recordedAt, uint32_t durationMs, int battery) {
  if (WiFi.status() != WL_CONNECTED && !connectWifi()) {
    return false;
  }
  File file = SD.open(path, FILE_READ);
  if (!file) {
    return false;
  }
  const String boundary = "PocketRecorderBoundary";
  WiFiClient client;
  if (!client.connect(SERVER_HOST, SERVER_PORT)) {
    file.close();
    return false;
  }
  String prefix = multipartValue(boundary, "device_id", DEVICE_ID);
  prefix += multipartValue(boundary, "recorded_at", recordedAt);
  prefix += multipartValue(boundary, "duration_ms", String(durationMs));
  if (battery >= 0) {
    prefix += multipartValue(boundary, "battery_pct", String(battery));
  }
  prefix += "--" + boundary + "\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"" +
            path.substring(1) + "\"\r\nContent-Type: audio/wav\r\n\r\n";
  String suffix = "\r\n--" + boundary + "--\r\n";
  const size_t contentLength = prefix.length() + file.size() + suffix.length();
  client.print("POST ");
  client.print(SERVER_PATH);
  client.println(" HTTP/1.1");
  client.print("Host: ");
  client.print(SERVER_HOST);
  client.print(":");
  client.println(SERVER_PORT);
  client.println("Connection: close");
  client.println("Content-Type: multipart/form-data; boundary=" + boundary);
  client.println("Content-Length: " + String(contentLength));
  client.println();
  client.print(prefix);
  uint8_t buffer[1024];
  while (file.available()) {
    size_t count = file.read(buffer, sizeof(buffer));
    if (client.write(buffer, count) != count) {
      file.close();
      client.stop();
      return false;
    }
  }
  client.print(suffix);
  file.close();
  uint32_t deadline = millis() + 15000;
  while (!client.available() && millis() < deadline) {
    delay(10);
  }
  String statusLine = client.readStringUntil('\n');
  client.stop();
  return statusLine.startsWith("HTTP/1.1 2") || statusLine.startsWith("HTTP/1.0 2");
}

void stopRecording() {
  recording = false;
  const String path = audioFile.name();
  const uint32_t durationMs = millis() - recordingStarted;
  writeWavHeader(audioFile, audioBytes);
  audioFile.close();
  pendingPath = path;
  pendingTimestamp = timestampNow();
  pendingDurationMs = durationMs;
  pendingBattery = batteryPercent();
  const bool uploaded = uploadRecording(
      pendingPath, pendingTimestamp, pendingDurationMs, pendingBattery);
  if (uploaded) {
    SD.remove(pendingPath);
    pendingPath = "";
  } else {
    nextRetryAt = millis() + 30000;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(RECORD_BUTTON_PIN, INPUT_PULLUP);
  configureI2s();
  SD.begin(SD_CS_PIN);
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  connectWifi();
}

void loop() {
  static bool previousButton = HIGH;
  const bool currentButton = digitalRead(RECORD_BUTTON_PIN);
  if (previousButton == HIGH && currentButton == LOW) {
    if (recording) {
      stopRecording();
    } else {
      startRecording();
    }
    delay(250);
  }
  previousButton = currentButton;
  if (recording) {
    captureAudio();
  } else if (pendingPath.length() > 0 && millis() >= nextRetryAt) {
    if (uploadRecording(pendingPath, pendingTimestamp, pendingDurationMs, pendingBattery)) {
      SD.remove(pendingPath);
      pendingPath = "";
    } else {
      nextRetryAt = millis() + 30000;
    }
  }
}
