import serial
import time

PORT = "COM5"
BAUDRATE = 9600  # যদি কাজ না করে, পরে 9600 ট্রাই করব

ser = serial.Serial(
    port="COM5",
    baudrate=9600,
    bytesize=8,
    parity="N",
    stopbits=1,
    timeout=2,
    xonxoff=False,
    rtscts=False,
    dsrdtr=False,
)
time.sleep(2)


def send(command: str):
    print(f">>> {command}")
    ser.write((command + "\r").encode())
    time.sleep(1)

    while ser.in_waiting:
        print(ser.readline().decode(errors="ignore").rstrip())


commands = [
    "AT",
    "ATI",
    "AT+CPIN?",
    "AT+CSQ",
    "AT+CREG?",
]

for cmd in commands:
    send(cmd)

ser.close()