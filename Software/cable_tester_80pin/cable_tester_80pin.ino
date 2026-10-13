/*
  RIBBON CABLE 80-PIN TESTER - FIRMWARE DIEU KHIEN QUA UART
  - 10x 74HC595 (U1..U10) mo rong 80 chan ngo ra
  - 10x 74HC165 (U11..U20) gom 80 chan ngo vao ve 1 chan SO
  - Arduino Nano giao tiep voi phan mem PC qua Serial (115200 baud)

  GIAO THUC UART:
  PC -> Board:  "T:<20 ky tu hex>\n"
                20 hex = 80 bit active-mask (bit=1 nghia la chan do THUC SU
                dang duoc dung boi profile cap hien tai, can quet; bit=0 la
                chan board du ra, khong noi cap nao, BO QUA khong quet).
                Vi du full 80 pin: "T:FFFFFFFFFFFFFFFFFFFF\n"

  Board -> PC:  1 dong JSON duy nhat sau khi quet xong:
                {"open":[7,15],"short":[[1,2],[40,41]]}
                (chi so PIN o day la 1-based, tuc Pin1..Pin80)

  Van giu lenh 'r' (khong mask) de test nhanh toan bo 80 pin qua Serial Monitor.

  Quy uoc chi so noi bo (0-based): idx 0 = Pin1 ... idx 79 = Pin80.
*/

#define NUM_CHIPS   10
#define TOTAL_PINS  80
#define MASK_BYTES  10 // 80 bit = 10 byte

// ---------------- PIN ASSIGNMENT (dieu chinh theo mach that) ----------------
const int PIN_DS    = 11;
const int PIN_SH_CP = 12;
const int PIN_ST_CP = 10;
const int PIN_MR    = 9;
const int PIN_OE    = 8;
const int PIN_SHLD  = 7;
const int PIN_SO    = 6;
// ------------------------------------------------------------------------------

byte activeMask[MASK_BYTES]; // mask cac pin dang thuc su duoc dung (theo profile)

bool openPin[TOTAL_PINS];
bool shortWithNext[TOTAL_PINS - 1];

String serialLine = "";

void setup() {
  Serial.begin(115200);

  pinMode(PIN_DS, OUTPUT);
  pinMode(PIN_SH_CP, OUTPUT);
  pinMode(PIN_ST_CP, OUTPUT);
  pinMode(PIN_MR, OUTPUT);
  pinMode(PIN_OE, OUTPUT);
  pinMode(PIN_SHLD, OUTPUT);
  pinMode(PIN_SO, INPUT);

  digitalWrite(PIN_MR, HIGH);
  digitalWrite(PIN_OE, LOW);
  digitalWrite(PIN_SHLD, HIGH);
  digitalWrite(PIN_ST_CP, LOW);
  digitalWrite(PIN_SH_CP, LOW);

  // Mac dinh: toan bo 80 pin active, de co the test nhanh bang lenh 'r'
  // khi chua co phan mem PC gui mask xuong.
  for (int i = 0; i < MASK_BYTES; i++) activeMask[i] = 0xFF;

  delay(200);
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      processLine(serialLine);
      serialLine = "";
    } else if (c != '\r') {
      serialLine += c;
    }
  }
}

void processLine(String line) {
  line.trim();
  if (line.length() == 0) return;

  if (line == "PING" || line == "ping" || line == "P") {
    Serial.println(F("PONG"));
    return;
  }

  if (line.startsWith("T:")) {
    String hexPart = line.substring(2);
    if (hexPart.length() != MASK_BYTES * 2) {
      Serial.println(F("{\"error\":\"mask phai du 20 ky tu hex\"}"));
      return;
    }
    if (!parseHexMask(hexPart, activeMask)) {
      Serial.println(F("{\"error\":\"mask khong hop le\"}"));
      return;
    }
    runTest(activeMask);
  } else if (line == "r" || line == "R") {
    runTest(activeMask); // dung mask hien tai (mac dinh full 80 neu chua tung nhan T:)
  }
}

bool parseHexMask(const String &hexStr, byte *out) {
  for (int i = 0; i < MASK_BYTES; i++) {
    int hi = hexCharToNibble(hexStr[i * 2]);
    int lo = hexCharToNibble(hexStr[i * 2 + 1]);
    if (hi < 0 || lo < 0) return false;
    out[i] = (byte)((hi << 4) | lo);
  }
  return true;
}

int hexCharToNibble(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return -1;
}

// ---------------- Helper doc/ghi bit tren mang byte 10 phan tu ----------------
void setBitArr(byte *arr, int idx, bool val) {
  int chip = idx / 8;
  int bit = idx % 8;
  if (val) arr[chip] |= (1 << bit);
  else arr[chip] &= ~(1 << bit);
}

bool getBitArr(const byte *arr, int idx) {
  int chip = idx / 8;
  int bit = idx % 8;
  return (arr[chip] >> bit) & 1;
}

// ---------------- 74HC595 - ghi 80 bit (10 byte) ----------------
void writeSR(const byte *pattern) {
  digitalWrite(PIN_ST_CP, LOW);
  // gui chip xa nhat (U10, pattern[9]) truoc, chip gan nhat (U1, pattern[0]) sau cung
  for (int chip = NUM_CHIPS - 1; chip >= 0; chip--) {
    shiftOut(PIN_DS, PIN_SH_CP, MSBFIRST, pattern[chip]);
  }
  digitalWrite(PIN_ST_CP, HIGH);
}

// ---------------- 74HC165 - doc 80 bit (10 byte) ----------------
byte shiftIn165(int dataPin, int clockPin) {
  byte value = 0;
  for (int i = 7; i >= 0; i--) {
    if (digitalRead(dataPin)) value |= (1 << i);
    digitalWrite(clockPin, HIGH);
    digitalWrite(clockPin, LOW);
  }
  return value;
}

void readSR(byte *outArr) {
  digitalWrite(PIN_SHLD, LOW);
  delayMicroseconds(5);
  digitalWrite(PIN_SHLD, HIGH);
  delayMicroseconds(5);

  for (int i = 0; i < NUM_CHIPS; i++) {
    byte b = shiftIn165(PIN_SO, PIN_SH_CP);
    int chipIndex = (NUM_CHIPS - 1) - i;
    outArr[chipIndex] = b;
  }
}

// ---------------- Thuat toan quet (chi quet cac pin co active-mask = 1) ----------------
void runTest(const byte *mask) {
  bool candidateOpen[TOTAL_PINS];
  for (int i = 0; i < TOTAL_PINS; i++) {
    openPin[i] = false;
    candidateOpen[i] = false;
  }
  for (int i = 0; i < TOTAL_PINS - 1; i++) shortWithNext[i] = false;

  byte pattern[MASK_BYTES];
  byte received[MASK_BYTES];

  // Buoc 1: walking-1, chi tren cac pin active
  for (int i = 0; i < TOTAL_PINS; i++) {
    if (!getBitArr(mask, i)) continue; // bo qua pin khong dung toi (khong thuoc profile)

    for (int b = 0; b < MASK_BYTES; b++) pattern[b] = 0;
    setBitArr(pattern, i, true);
    writeSR(pattern);
    delayMicroseconds(100);
    readSR(received);
    candidateOpen[i] = !getBitArr(received, i);
  }

  // Buoc 2: xu ly tung chuoi pin active+candidateOpen LIEN TIEP NHAU
  int i = 0;
  while (i < TOTAL_PINS) {
    if (!getBitArr(mask, i) || !candidateOpen[i]) { i++; continue; }

    int start = i;
    int end = i;
    while (end + 1 < TOTAL_PINS && getBitArr(mask, end + 1) && candidateOpen[end + 1]) {
      end++;
    }

    if (start == end) {
      openPin[start] = true;
    } else {
      for (int b = 0; b < MASK_BYTES; b++) pattern[b] = 0;
      for (int k = start; k <= end; k++) setBitArr(pattern, k, true);
      writeSR(pattern);
      delayMicroseconds(100);
      readSR(received);

      for (int k = start; k <= end; k++) {
        if (!getBitArr(received, k)) openPin[k] = true;
      }
      for (int k = start; k < end; k++) {
        if (getBitArr(received, k) && getBitArr(received, k + 1)) {
          shortWithNext[k] = true;
        }
      }
    }

    i = end + 1;
  }

  printResultJson();
}

void printResultJson() {
  Serial.print(F("{\"open\":["));
  bool first = true;
  for (int i = 0; i < TOTAL_PINS; i++) {
    if (openPin[i]) {
      if (!first) Serial.print(',');
      Serial.print(i + 1);
      first = false;
    }
  }
  Serial.print(F("],\"short\":["));
  first = true;
  for (int i = 0; i < TOTAL_PINS - 1; i++) {
    if (shortWithNext[i]) {
      if (!first) Serial.print(',');
      Serial.print('[');
      Serial.print(i + 1);
      Serial.print(',');
      Serial.print(i + 2);
      Serial.print(']');
      first = false;
    }
  }
  Serial.println(F("]}"));
}
