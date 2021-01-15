from machine import Pin, I2C, freq
from utime import sleep_ms
from lcd import LCD16X1
from esp import osdebug
from gc import collect
import _thread
import network
try:
    import usocket as socket
except:
    import socket

osdebug(None)
collect()

freq(240000000)

wifiName = 'esp32'
wifiPassword = 'Th3@Professional'
pins = {
    'reset': Pin(36, Pin.IN),
    'increment': Pin(34, Pin.IN),
    'decrement': Pin(35, Pin.IN),
    'internalLed': Pin(2, Pin.OUT)
}
currentNumber = 0
data = dict()
serverSocket = None
i2c = I2C(scl=Pin(22), sda=Pin(21), freq=int(240E6))
lcd = LCD16X1(i2c, 39)


def webPage():
    html = """
        <html>
            <head> 
                <title>Th3 Professional Cod3r Server</title> 
                <meta name="viewport" content="width=device-width, initial-scale=1"/>
                <style>
                    html{font-family: Helvetica; display:inline-block; margin: 0px auto; text-align: center;}
                    h1{color: #0F3376; padding: 2vh;}p{font-size: 1.5rem;}.button{display: inline-block; background-color: #e7bd3b; border: none; 
                       border-radius: 4px; color: white; padding: 16px 40px; text-decoration: none; font-size: 30px; margin: 2px; cursor: pointer;}
                    .button2{background-color: #4286f4;}
                </style>
            </head>
            <body> 
                <h1>Th3 Professional Cod3r WebServer</h1> 
                <p>Current Number: <strong id="CN">""" + str(currentNumber) + """</strong></p>
                <p><a href="/?cmd=inc"><button class="button button2">increment</button></a></p>
                <p><a href="/?cmd=dec"><button class="button button2">decrement</button></a></p>
                <p><a href="/?cmd=reset"><button class="button">reset</button></a></p>
            </body>
            <script>
                var currentNumber = 0;
                var xhttp = new XMLHttpRequest();
                function updateNumber(){
                    var newNumber = 0;
                    xhttp.onreadystatechange = function() {
                        if (this.readyState == 4 && this.status == 200) {
                            newNumber = xhttp.responseText;
                            if (newNumber != currentNumber){
                                document.getElementById("CN").innerHTML = newNumber;
                                currentNumber = newNumber;
                            }
                        }
                    };
                    xhttp.open("GET", "?cmd=currentNumber", true);
                    xhttp.send();
                    setTimeout(updateNumber, 500);
                }
                updateNumber();
            </script>
            </html>
            """
    return html


def generateAp():
    global serverSocket
    pins['internalLed'].value(1)
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=wifiName, password=wifiPassword, authmode=network.AUTH_WPA2_PSK, max_clients=16)
    while not ap.active():
        pass
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.bind(('', 80))
    serverSocket.listen(5)
    pins['internalLed'].value(0)


def createServer():
    global serverSocket, currentNumber
    while True:
        conn, addr = serverSocket.accept()
        request = conn.recv(1024)
        request = str(request)

        inc = request.find('/?cmd=inc')
        dec = request.find('/?cmd=dec')
        reset = request.find('/?cmd=reset')
        currentNumberPage = request.find('/?cmd=currentNumber')

        if inc == 6:
            currentNumber += 1
        if dec == 6:
            currentNumber -= 1
        if reset == 6:
            currentNumber = 0

        if currentNumberPage == 6:
            conn.send('HTTP/1.1 200 OK\n')
            conn.send('Content-Type: text/html\n')
            conn.send('Connection: close\n\n')
            conn.sendall('%s' % currentNumber)
            conn.close()
            continue

        if any((inc == 6, dec == 6, reset == 6)):
            lcd.writeString('current Num:' + str(currentNumber))

        response = webPage()
        conn.send('HTTP/1.1 200 OK\n')
        conn.send('Content-Type: text/html\n')
        conn.send('Connection: close\n\n')
        conn.sendall(response)
        conn.close()


def loop():
    while True:
        global data, currentNumber
        data = dict((name, value.value()) for (name, value) in pins.items())
        if data['reset'] == 0:
            currentNumber = 0
            lcd.writeString('current Num:' + str(currentNumber))
            sleep_ms(200)
            continue
        addition = (not data['increment']) - (not data['decrement'])
        currentNumber += addition
        if addition:
            lcd.writeString('current Num:' + str(currentNumber))
        sleep_ms(300)


lcd.writeString('Creating AP....')
generateAp()
serverThread = _thread.start_new_thread(createServer, tuple())
lcd.writeString('current Num:' + str(currentNumber))
loop()
