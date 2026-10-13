const int PIN_DATA_OUT = 11;
const int PIN_CLOCK    = 12;
const int PIN_LATCH    = 10;
const int PIN_MR       = 9;
const int PIN_OE       = 8;

const int PIN_DATA_IN  = 7;
const int PIN_LOAD     = 6;

void setup()
{
    Serial.begin(115200);

    pinMode(PIN_DATA_OUT, OUTPUT);
    pinMode(PIN_CLOCK, OUTPUT);
    pinMode(PIN_LATCH, OUTPUT);
    pinMode(PIN_MR, OUTPUT);
    pinMode(PIN_OE, OUTPUT);

    pinMode(PIN_DATA_IN, INPUT);
    pinMode(PIN_LOAD, OUTPUT);

    digitalWrite(PIN_MR, HIGH);
    digitalWrite(PIN_OE, LOW);
    digitalWrite(PIN_CLOCK, LOW);
    digitalWrite(PIN_LATCH, HIGH);
    digitalWrite(PIN_LOAD, HIGH);

    set595(0);

    Serial.println("64 PIN CABLE TESTER");
}

void loop()
{
    uint64_t inputData;

    set595(0x0000000000000001ULL);
    delayMicroseconds(100);

    inputData = read165();

    print64(inputData);

    delay(1000);
}

void set595(uint64_t data)
{
    digitalWrite(PIN_LATCH, LOW);

    for (int i = 7; i >= 0; i--)
    {
        byte value = (data >> (i * 8)) & 0xFF;

        for (int bit = 7; bit >= 0; bit--)
        {
            digitalWrite(PIN_DATA_OUT, (value >> bit) & 1);

            digitalWrite(PIN_CLOCK, HIGH);
            digitalWrite(PIN_CLOCK, LOW);
        }
    }

    digitalWrite(PIN_LATCH, HIGH);
}

uint64_t read165()
{
    uint64_t data = 0;

    digitalWrite(PIN_LOAD, LOW);
    delayMicroseconds(2);
    digitalWrite(PIN_LOAD, HIGH);

    for (int i = 0; i < 64; i++)
    {
        data <<= 1;

        digitalWrite(PIN_CLOCK, HIGH);

        if (digitalRead(PIN_DATA_IN))
            data |= 1;

        digitalWrite(PIN_CLOCK, LOW);
    }

    return data;
}

void print64(uint64_t data)
{
    Serial.print("0x");

    for (int i = 15; i >= 0; i--)
    {
        byte nibble = (data >> (i * 4)) & 0x0F;

        if (nibble < 10)
            Serial.print(nibble);
        else
            Serial.print(char('A' + nibble - 10));
    }

    Serial.println();

    for (int i = 63; i >= 0; i--)
    {
        Serial.print((data >> i) & 1);

        if (i % 8 == 0)
            Serial.print(" ");
    }

    Serial.println();
}