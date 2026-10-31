# ESP32-S3 hardware uploader

This module records mono 16-bit PCM WAV audio to a microSD card and uploads
each completed recording to Pocket Recorder through `POST /upload`.

The firmware is intentionally configurable because ESP32-S3 boards and I2S
microphone modules use different pins. Set the pins and credentials in
`pocket_recorder_esp32_s3.ino` before flashing.

## Required hardware

- ESP32-S3 development board with Wi-Fi
- I2S microphone, such as an INMP441-compatible module
- MicroSD card module or board-integrated microSD
- Momentary record button
- Optional battery ADC connection

The example assumes:

- I2S microphone input
- SD library support for the selected board
- Button connected between `RECORD_BUTTON_PIN` and GND
- A computer and the ESP32 on the same Wi-Fi network

## Configure

Edit these values in the sketch:

- `WIFI_SSID` and `WIFI_PASSWORD`
- `SERVER_HOST`, using the computer's LAN IP, not `localhost`
- `DEVICE_ID`
- I2S pins
- SD chip-select pin
- optional battery ADC pin

Start the backend so it listens on the LAN:

```powershell
cd D:\VyohmAI\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Find the computer's IPv4 address with:

```powershell
ipconfig
```

For example:

```cpp
const char* UPLOAD_URL = "http://192.168.1.25:8000/upload";
```

Allow inbound TCP port `8000` in Windows Firewall if the ESP32 cannot connect.

## Device workflow

1. Press the button to start recording.
2. Press it again to stop recording.
3. The WAV is closed and uploaded over Wi-Fi.
4. A successful response removes the local file.
5. A failed upload keeps the file on the SD card for the next retry.
6. The backend deduplicates retries using device ID, timestamp, and audio bytes.

The sketch uses UTC time from NTP and sends an ISO-8601 timestamp with a
timezone offset. Do not treat a device upload as verified until the recording
appears in `GET /recordings` and the dashboard.

## Important limitation

This is a board-level integration template, not a claim that every ESP32-S3
board uses these exact pins. Test the I2S pin map, SD wiring, microphone level,
power supply, and battery ADC on the actual hardware before deployment.
