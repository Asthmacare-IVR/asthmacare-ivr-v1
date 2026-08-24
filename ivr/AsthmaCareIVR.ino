/**
 * AsthmaCareIVR - DFPlayer FIXED
 * CORRECTED VERSION - Only One Track Issue Fixed
 */

#include <Arduino.h>

#define DFPLAYER_TX_PIN   26
#define DFPLAYER_RX_PIN   25
#define DFPLAYER_BAUDRATE 9600

HardwareSerial dfSerial(2);

bool dfPlayerReady = false;
String serialBuffer = "";
unsigned long lastCharTime = 0;

uint8_t dfpRxBuf[10];
uint8_t dfpRxIndex = 0;

// ============================================================
// YOUR WORKING CHECKSUM METHOD (DO NOT CHANGE)
// ============================================================

void dfPlayerSendCommand(uint8_t cmd, uint16_t data) {
  uint8_t packet[10];
  packet[0] = 0x7E;
  packet[1] = 0xFF;
  packet[2] = 0x06;
  packet[3] = cmd;
  packet[4] = 0x00;
  packet[5] = (data >> 8) & 0xFF;
  packet[6] = data & 0xFF;

  uint16_t checksum = 0;
  for (int i = 1; i <= 6; i++) {
    checksum += packet[i];
  }
  checksum = 0 - checksum;

  packet[7] = (checksum >> 8) & 0xFF;
  packet[8] = checksum & 0xFF;
  packet[9] = 0xEF;

  dfSerial.write(packet, 10);
  dfSerial.flush();
}

// ============================================================
// DFPlayer Control Functions - CORRECTED
// ============================================================

void dfPlayerReset() {
  Serial.println("[DFP] Resetting...");
  dfPlayerSendCommand(0x0C, 0x00);
  delay(2000);
}

void dfPlayerSelectDevice(uint8_t device) {
  Serial.println("[DFP] Selecting device...");
  dfPlayerSendCommand(0x09, device);
  delay(500);  // ← Increased delay
}

void dfPlayerVolume(int vol) {
  if (vol < 0) vol = 0;
  if (vol > 30) vol = 30;
  Serial.print("[DFP] Volume: ");
  Serial.println(vol);
  dfPlayerSendCommand(0x06, vol);
  delay(100);
}

// ============================================================
// FIXED: playFolder (Command 0x0F)
// ============================================================

void dfPlayerPlay(int track) {
  if (!dfPlayerReady) {
    Serial.println("[DFP] ERROR: Not ready");
    return;
  }
  if (track < 1 || track > 99) {
    Serial.println("[DFP] ERROR: Track must be 1-99");
    return;
  }

  Serial.print("[DFP] STOP current track...");
  dfPlayerSendCommand(0x16, 0);  // ← STOP first!
  delay(300);                     // ← Wait for stop

  Serial.print("[DFP] Playing track ");
  Serial.print(track);
  Serial.println(" from folder /01/");

  // Command 0x0F = playFolder
  // High byte = folder (1-15), Low byte = track (1-255)
  uint16_t folderTrack = (1 << 8) | track;  // folder=1, track=n
  
  dfPlayerSendCommand(0x0F, folderTrack);
  delay(500);  // ← Increased delay after play
}

// ============================================================
// FIXED: playMp3Folder (Command 0x12)
// ============================================================

void dfPlayerPlayMp3(int track) {
  if (!dfPlayerReady) {
    Serial.println("[DFP] ERROR: Not ready");
    return;
  }
  if (track < 1 || track > 2999) {
    Serial.println("[DFP] ERROR: Track must be 1-2999");
    return;
  }

  Serial.print("[DFP] STOP current track...");
  dfPlayerSendCommand(0x16, 0);  // ← STOP first!
  delay(300);

  Serial.print("[DFP] Playing MP3 folder track ");
  Serial.println(track);

  dfPlayerSendCommand(0x12, track);  // 0x12 = playMp3Folder
  delay(500);
}

void dfPlayerStop() {
  Serial.println("[DFP] Stopping...");
  dfPlayerSendCommand(0x16, 0);
  delay(100);
}

void dfPlayerPause() {
  Serial.println("[DFP] Pausing...");
  dfPlayerSendCommand(0x0E, 0);
  delay(100);
}

// ============================================================
// Response Decoder
// ============================================================

void parseDFPlayerPacket(uint8_t *p) {
  uint8_t command = p[3];
  uint16_t data = (p[5] << 8) | p[6];
  
  Serial.print("[DFP RX] ");
  switch (command) {
    case 0x3D: 
      Serial.print("Finished track "); 
      Serial.println(data); 
      break;
    case 0x3F: 
      Serial.print("Online, device="); 
      Serial.println(data); 
      break;
    case 0x40: 
      Serial.print("ERROR code "); 
      Serial.println(data); 
      break;
    case 0x41: 
      Serial.println("ACK - command received"); 
      break;
    case 0x3A: 
      Serial.println("TF card inserted"); 
      break;
    case 0x3B: 
      Serial.println("TF card removed"); 
      break;
    default:
      Serial.print("cmd=0x"); 
      Serial.print(command, HEX);
      Serial.print(" data="); 
      Serial.println(data);
  }
}

// ============================================================
// Serial Command Parser
// ============================================================

void processCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  Serial.print("[CMD] ");
  Serial.println(cmd);

  String upper = cmd;
  upper.toUpperCase();

  if (upper.length() == 1) {
    char c = upper.charAt(0);
    switch (c) {
      case 'P': dfPlayerPlay(1); return;
      case 'S': dfPlayerStop(); return;
      case 'R':
        dfPlayerReset();
        dfPlayerSelectDevice(0x02);
        dfPlayerReady = true;
        return;
      case 'V': dfPlayerVolume(30); return;
      case 'D':
        Serial.println("[DEBUG] DFPlayer Status");
        Serial.print("  Ready: ");
        Serial.println(dfPlayerReady ? "YES" : "NO");
        Serial.println("  SD: /01/001.mp3 - /01/010.mp3");
        return;
      default:
        Serial.println("[CMD] Unknown command");
        return;
    }
  }

  if (upper.startsWith("PLAY ")) {
    int track = upper.substring(5).toInt();
    if (track > 0) dfPlayerPlay(track);
    return;
  }

  if (upper.startsWith("MP3 ")) {
    int track = upper.substring(4).toInt();
    if (track > 0) dfPlayerPlayMp3(track);
    return;
  }

  if (upper == "STOP") {
    dfPlayerStop();
    return;
  }

  if (upper == "PAUSE") {
    dfPlayerPause();
    return;
  }

  if (upper == "RESET") {
    dfPlayerReset();
    dfPlayerSelectDevice(0x02);
    dfPlayerReady = true;
    return;
  }

  if (upper.startsWith("VOLUME ")) {
    int vol = upper.substring(7).toInt();
    dfPlayerVolume(vol);
    return;
  }

  // Quick test: PLAY 1, 2, 3 in sequence
  if (upper == "TEST") {
    Serial.println("[TEST] Playing tracks 1, 2, 3...");
    for (int i = 1; i <= 3; i++) {
      dfPlayerPlay(i);
      delay(4000);  // Wait 4 seconds between tracks
    }
    Serial.println("[TEST] Done!");
    return;
  }

  Serial.println("[CMD] Available: PLAY <n>, MP3 <n>, STOP, PAUSE, RESET, VOLUME <n>, TEST");
}

// ============================================================
// SETUP
// ============================================================

void setup() {
  Serial.begin(9600);
  delay(2000);

  Serial.println();
  Serial.println("========================================");
  Serial.println("   ASTHMACARE IVR - DFPLAYER FIXED");
  Serial.println("========================================");

  dfSerial.begin(DFPLAYER_BAUDRATE, SERIAL_8N1, DFPLAYER_RX_PIN, DFPLAYER_TX_PIN);
  Serial.println("[DFP] UART2: RX=D25, TX=D26");

  // Initialize DFPlayer
  dfPlayerReset();
  dfPlayerSelectDevice(0x02);  // TF card
  dfPlayerVolume(25);
  dfPlayerReady = true;

  Serial.println();
  Serial.println("READY! Send commands:");
  Serial.println("  PLAY 1  - Play /01/001.mp3");
  Serial.println("  PLAY 2  - Play /01/002.mp3");
  Serial.println("  PLAY 3  - Play /01/003.mp3");
  Serial.println("  STOP    - Stop playback");
  Serial.println("  TEST    - Play tracks 1,2,3");
  Serial.println("========================================");
  Serial.println();
}

// ============================================================
// LOOP
// ============================================================

void loop() {
  // Read DFPlayer responses
  while (dfSerial.available()) {
    uint8_t b = dfSerial.read();
    if (b == 0x7E) { 
      dfpRxIndex = 0; 
    }
    if (dfpRxIndex < 10) {
      dfpRxBuf[dfpRxIndex++] = b;
    }
    if (b == 0xEF && dfpRxIndex == 10) {
      parseDFPlayerPacket(dfpRxBuf);
      dfpRxIndex = 0;
    }
    if (dfpRxIndex >= 10) dfpRxIndex = 0;
  }

  // Read Serial commands
  while (Serial.available()) {
    char c = Serial.read();
    lastCharTime = millis();

    if (c == '\n' || c == '\r') {
      if (serialBuffer.length() > 0) {
        processCommand(serialBuffer);
        serialBuffer = "";
      }
    } else {
      serialBuffer += c;
    }
  }

  if (serialBuffer.length() > 0 && (millis() - lastCharTime) > 100) {
    processCommand(serialBuffer);
    serialBuffer = "";
  }

  delay(5);
}
