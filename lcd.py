class LCD16X1:
    from utime import sleep_ms, sleep_us

    def __init__(self, i2CProtocol: I2C, address: int):
        self.i2CProtocol = i2CProtocol
        self.address = address
        self.dataByte = bytearray(1)
        self.RS = 0x00
        self.BK = 0x08
        self.lcdInit()

    def lcdInit(self):
        self.sleep_ms(20)
        self.lcdSendCMD(0x33)
        self.lcdSendCMD(0x32)   # 0x33, 0x32 is for 4 bit mode lcd initializing
        self.lcdSendCMD(0x28)   # 0x28 2 line, 5*7 matrix character
        self.lcdSendCMD(0x0C)   # 0x0C making the underline cursor off
        self.lcdSendCMD(0x06)   # 0x06 auto-increment for the cursor (shift to right)
        self.lcdSendCMD(0x01)   # 0x01 clear display

    def lcdSendCMD(self, CMD):
        self.RS = 0x00
        self.lcdMakePacket(CMD)
        self.lcdMakePacket(CMD << 0x04)

    def lcdSendData(self, data):
        self.RS = 0x01
        self.lcdMakePacket(data)
        self.lcdMakePacket(data << 0x04)

    def lcdMakePacket(self, data):
        data = (data & 0xF0) | self.BK | self.RS
        self.lcdSendByte(data | 0x04)
        self.sleep_us(1)
        self.lcdSendByte(data)
        self.sleep_ms(5)

    def lcdSendByte(self, data):
        self.dataByte[0] = data
        self.i2CProtocol.writeto(self.address, self.dataByte)
        self.sleep_ms(1)

    def writeChar(self, char: chr, xPos=0):
        if xPos <= 16:
            self.lcdSendCMD(0x80 + xPos if 0 <= xPos < 8 else 0) if xPos < 0x08 else self.lcdSendCMD(0xC0 + xPos - 0x08)
            self.lcdSendData(ord(char))

    def writeString(self, string: str):
        self.lcdSendCMD(0x01)
        for i in enumerate(string):
            if i[1] == '\n':
                self.lcdSendCMD(0x01)
                continue
            self.writeChar(i[1], i[0])
