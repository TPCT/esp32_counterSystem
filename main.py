from machine import Pin, I2C
from utime import sleep_ms
from lcd import LCD16X1
from gc import collect

import _thread
import network
import socket

collect()

wifiName = 'esp32'
wifiPassword = 'Th3@Professional'
pins = {
    'reset': Pin(36, Pin.IN),
    'increment': Pin(34, Pin.IN),
    'decrement': Pin(35, Pin.IN),
    'internalLed': Pin(2, Pin.OUT)
}
currentNumber = 0
oldNumber = -1
data = dict()
serverSocket: socket.socket = None

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
    serverSocket.listen(2)
    pins['internalLed'].value(0)


def createServer():
    global serverSocket, currentNumber

    while True:
        socketConnection, clientAddress = serverSocket.accept()
        request = socketConnection.recv(1024).decode()
        headers = request.split('\n')
        fileName = headers[0].split()[1]

        if fileName == '/?cmd=inc':
            currentNumber += 1
        elif fileName == '/?cmd=dec':
            currentNumber -= 1
        elif fileName == '/?cmd=reset':
            currentNumber = 0
        elif fileName == '/?cmd=currentNumber':
            try:
                socketConnection.send('HTTP/1.1 200 OK\n')
                socketConnection.send('Content-Type: text/html\n')
                socketConnection.send('Connection: close\n\n')
                socketConnection.send(str(currentNumber))
            except OSError:
                print('internal error occurred at line 120')
            finally:
                socketConnection.close()
                continue
        elif fileName == '/':
            pass
        else:
            try:
                socketConnection.send('HTTP/1.1 404 OK\n')
                socketConnection.send('Content-Type: text/html\n')
                socketConnection.send('Connection: close\n\n')
                socketConnection.send('404 not found')
            except OSError:
                print('internal error occurred at line 129')
            finally:
                socketConnection.close()
                pass
            continue

        response = webPage()
        try:
            socketConnection.send('HTTP/1.1 200 OK\n')
            socketConnection.send('Content-Type: text/html\n')
            socketConnection.send('Connection: close\n\n')
            socketConnection.sendall(response)
        except OSError:
            print('internal error occurred at line 134')
        finally:
            socketConnection.close()


def loop():
    while True:
        global data, currentNumber, oldNumber
        data = dict((name, value.value()) for (name, value) in pins.items())
        if data['reset'] == 0:
            currentNumber = 0

        addition = (not data['increment']) - (not data['decrement'])
        currentNumber += addition

        if currentNumber != oldNumber:
            oldNumber = currentNumber
            lcd.writeString('current Num:' + str(currentNumber))

        sleep_ms(250)


lcd.writeString('Creating AP....')
generateAp()
loopThread = _thread.start_new_thread(loop, ())
serverThread = _thread.start_new_thread(createServer, ())
