class LCD16X1:
    from utime import sleep_ms, sleep_us

    def __init__(self, i2CProtocol: I2C, address: int):
        # using PCF8574
        # from P0 to P7 is the output data
        # p0(0x0[0, 1])  -> register select{1: for data, 0: for command}
        # p1(0x0[0, 2])  -> read/write {0: for write, 1: read}
        # p2(0x0[0, 4])  -> enable {falling edge trail}
        # p3(0x0[0, 8])  -> enable/disable gate of transistor responsible for backlight control
        # p4, p5, p6, p7 -> command/data pins
        # enable pulse width 450 ns, trailing edge minimum of 10 ns

        self.i2CProtocol = i2CProtocol
        self.address = address
        self.dataByte = bytearray(1)
        self.RS = 0x00
        self.EN = 0x04
        self.RW = 0x02
        self.BK = 0x08
        self.lcdInit()

    def lcdInit(self):
        """
        =--------------------------------------------------------------------------------------------------------------=
                                            *specification and requirements*
        this function is used for initializing the lcd
        sleeping 20 ms to make sure the lcd loaded fully (as the voltage rise from 0 to approx. 4.5v)
        sending command (0x28) 2 line, 5*7 matrix character setting the lcd to 4 bit mode
        sending command (0x0F) to enable makes cursor on, blink on
        sending command (0x06) to enable auto increment (shifting to right)
        sending command (0x01) to clear the display
        sending command (0x02) to return to home position
        =--------------------------------------------------------------------------------------------------------------=
        :return: None
        """
        self.sleep_ms(20)
        self.lcdSendCMD(0x28)   # 0x28 2 line, 5*7 matrix character
        self.lcdSendCMD(0x0F)   # 0x0C making the underline cursor off
        self.lcdSendCMD(0x06)   # 0x06 auto-increment for the cursor (shift to right)
        self.lcdSendCMD(0x01)   # 0x01 clear display
        self.lcdSendCMD(0x02)   # 0x02 return home position

    def lcdSendCMD(self, CMD):
        """
        =--------------------------------------------------------------------------------------------------------------=
                                            *specifications and requirements*
        this function is used to send a command to lcd through 4 bit mode
        Setting Register Select To 0, W/R to LOW to send command to cgram
        send packet to lcd containing highest 4 bits of the command
        send packet to lcd containing lowest  4 bits of the command
        =--------------------------------------------------------------------------------------------------------------=
        :param CMD: 8-bit instruction you want to send to lcd
        :return: None
        """
        self.RW = 0x00                      # setting W/R to LOW (Write mode)
        self.RS = 0x00                      # setting register select to 0
        self.lcdMakePacket(CMD)             # sending the highest 4 bits
        self.lcdMakePacket(CMD << 0x04)     # to send the lowest 4 bits

    def lcdSendData(self, data):
        """
        =--------------------------------------------------------------------------------------------------------------=
                                            *specifications and requirements*
        this function is used to send data (character) to lcd through 4 bit mode
        Setting Register Select To 0, to send data to dram
        sending packet to lcd containing highest 4 bits of the data
        sending packet to lcd containing lowest  4 bits of the data
        =--------------------------------------------------------------------------------------------------------------=
        :param data: 8-bit data required to be send to the lcd using i2c
        :return: None
        """
        self.RW = 0x00                      # setting the W/R to low (writing mode)
        self.RS = 0x01                      # setting the register select to 1
        self.lcdMakePacket(data)            # sending the highest 4 bits
        self.lcdMakePacket(data << 0x04)    # sending the lowest 4 bits

    def lcdMakePacket(self, data):
        """
        =--------------------------------------------------------------------------------------------------------------=
                                            *specifications and requirements*
        this function is used to make the packet will be send to the lcd,
        by reading the datasheet we found that:
        sending the packet to lcd and to be saved we need to set data at pins firstly (highest 4 bits first)
        sending the register select pin (0 for command, 1 for data)
        sending High to Low pulse to enable pin because it captures the trailing edge
            note: the pulse width must be of min 450 ns, the trailing edge must take min of 10 ns
        :param data: 8-bit data to be send to the lcd
        :return: None
        """
        data = (data & 0xF0) | self.BK | self.RS | self.RW
        self.lcdSendByte(data | self.EN)
        self.sleep_us(1)
        self.lcdSendByte(data)
        self.sleep_ms(2)

    def lcdSendByte(self, data):
        """
        =--------------------------------------------------------------------------------------------------------------=
                                            *specifications and requirements*
        this function is used to send the bytes at specific i2c slave address
        load the data and encode it to byte
                (dataByte[0] will convert automatically the data to bytes by taking it's decimal value)
        write the data to the i2c data line, for lcd address 0x27 (39d)
        sleep 2 ms (to make sure that any command is executed fully [max time of command is 1.47 ms])
        :param data: the required data that will be packed and send to lcd
        :return: None
        """
        self.dataByte[0] = data
        self.i2CProtocol.writeto(self.address, self.dataByte)
        self.sleep_ms(1)

    def writeChar(self, char: chr, xPos=0):
        """
        =--------------------------------------------------------------------------------------------------------------=
                                        *specifications and requirements*
        this function is used to send character to lcd at specific x position
        checking if x position < 16 (16X1 LCD)
        sending the start of the line command (0x80) + (x position)
            if the x position > 8 then it will go to the next x position using row operation 0xC0 (first row)
        sending the character to lcd using send data function
        =--------------------------------------------------------------------------------------------------------------=
        :param char: the character you want to write (Ascii)
        :param xPos: the character position in x-axis
        :return: None
        """
        if xPos <= 16:
            self.lcdSendCMD(0x80 + xPos if 0 <= xPos < 8 else 0) if xPos < 0x08 else self.lcdSendCMD(0xC0 + xPos - 0x08)
            self.lcdSendData(ord(char))

    def writeString(self, string: str):
        """
        =--------------------------------------------------------------------------------------------------------------=
                                            *specifications and requirements*
        this function is used to write string (character array) to the lcd
        sending 0x01 (clear display command to lcd)
        generate (position, char) pairs using enumerate
        sending the character and it's position
        =--------------------------------------------------------------------------------------------------------------=
        :param string: the required string you want to write
        :return: None
        """
        self.lcdSendCMD(0x01)
        for i in enumerate(string):
            if i[1] == '\n':
                self.lcdSendCMD(0x01)
                continue
            self.writeChar(i[1], i[0])
