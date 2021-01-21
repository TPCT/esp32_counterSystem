from machine import Pin, I2C
from utime import sleep_ms

from lcd import LCD16X1
from ultrasonic import ultraSonic
from gc import collect

import _thread
import network
import socket

collect()

wifiName = 'esp32'
wifiPassword = 'Th3@Professional'
activeApp = ''

pins = {
    'reset': Pin(36, Pin.IN),
    'increment': Pin(34, Pin.IN),
    'decrement': Pin(35, Pin.IN),
    'internalLed': Pin(2, Pin.OUT)
}
data = dict()

serverSocket: socket.socket = None
mainAppHtml: str = None
doorAppHtml: str = None
indexHtml: str = None
settingsHtml: str = None

i2c = I2C(scl=Pin(22), sda=Pin(21), freq=int(240E6))
lcd = LCD16X1(i2c, 39)
uSonic1 = ultraSonic(18, 19)
currentNumber = 0
oldNumber = -1

currentDistanceUSonic1 = 100
doorStates = ('idle', 'request', 'rejected')
doorRequest = 0x00  # 0x00 to close the door, 0x01 to open the door, 0x02 stop accepting
lastDoorRequest = 0x03
clientsNumber = 0
maxClientsNumber = 3


with open('mainAppIndex.html', 'r') as mainAppReader, open('index.html', 'r') as indexHtmlReader, \
        open('doorAppIndex.html', 'r') as doorAppReader, open('settings.html', 'r') as settingsHtmlReader:
    globals()['mainAppHtml'] = mainAppReader.read()
    globals()['indexHtml'] = indexHtmlReader.read()
    globals()['doorAppHtml'] = doorAppReader.read()
    globals()['settingsHtml'] = settingsHtmlReader.read()


def generateAp(essid, password, authMode=network.AUTH_WPA2_PSK, maxClients=1):
    global serverSocket
    pins['internalLed'].value(1)
    ap = network.WLAN(network.AP_IF)
    ap.config(essid=essid, password=password, authmode=authMode, max_clients=maxClients)
    ap.active(True)

    while not ap.active():
        pass

    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.bind(('', 80))
    serverSocket.listen(5)

    pins['internalLed'].value(0)


def createServer():
    global serverSocket, currentNumber, activeApp, \
           doorRequest, clientsNumber, currentDistanceUSonic1, \
           maxClientsNumber

    while True:
        socketConnection, clientAddress = serverSocket.accept()
        request = socketConnection.recv(4096).decode()
        headers = request.split('\n')
        requestType, fileName, *http = headers[0].split()
        fileName = str(fileName).rstrip('/ \t\n')
        postData = dict(tuple(post_data.split('=')[:2])
                        if '=' in post_data else (post_data, '')
                        for post_data in headers[headers.index('\r'):])

        if fileName == '' or fileName == 'index.html':
            activeApp = ''
            sendResponse(socketConnection, webPage())
            continue

        if fileName == '/mainApp/currentNumber':
            sendResponse(socketConnection, currentNumber)
            continue

        if fileName == '/mainApp' or fileName == '/mainApp/index.html':
            activeApp = 'mainApp'
            if requestType == 'POST':
                choice = postData.get('choice')
                if choice == 'increment':
                    currentNumber += 1
                elif choice == 'decrement':
                    currentNumber -= 1
                elif choice == 'reset':
                    currentNumber = 0
            sendResponse(socketConnection, webPage('mainApp').replace('%%Current Number%%', str(currentNumber)))
            continue

        if fileName == '/doorApp/request':
            sendResponse(socketConnection, doorStates[doorRequest] + "_%s" % clientsNumber)
            continue

        if fileName == '/doorApp' or fileName == '/doorApp/index.html':
            activeApp = 'doorApp'
            currentDistanceUSonic1 = 100
            choice = postData.get('choice')
            number = postData.get('number')
            if requestType == 'POST':
                if choice == 'enter':
                    if clientsNumber < maxClientsNumber:
                        doorRequest = 0x00
                        clientsNumber += 1
                    else:
                        doorRequest = 0x02
                elif choice == 'exit':
                    if clientsNumber > 0:
                        doorRequest = 0x00
                        clientsNumber -= 1
                elif choice == 'reset':
                    doorRequest = 0x00
                    clientsNumber = 0
                elif number:
                    clientsNumber = 0
                    maxClientsNumber = int(number) if number and number >= 0 else 0
                    doorRequest = 0x00
                    currentDistanceUSonic1 = 100

            sendResponse(socketConnection,
                         webPage('doorApp').replace('%%Current Number%%', str(clientsNumber))
                         .replace("%%Current Request%%", doorStates[doorRequest]))
            continue

        if fileName == '/doorApp/settings' or fileName == '/doorApp/settings/index.html':
            sendResponse(socketConnection, settingsHtml)
            continue

        sendResponse(socketConnection, 'Page not found', 404, 'NOT FOUND')


def webPage(selector='index'):
    if selector == 'mainApp':
        return mainAppHtml
    elif selector == 'doorApp':
        return doorAppHtml
    elif selector == 'index':
        return indexHtml


def sendResponse(socketConnection, response, statusCode=200, statusMsg='OK'):
    try:
        socketConnection.send('HTTP/1.1 %s %s\n' % (statusCode, statusMsg))
        socketConnection.send('Content-Type: text/html\n')
        socketConnection.send('Connection: close\n\n')
        socketConnection.sendall(str(response))
    except OSError:
        pass
    finally:
        socketConnection.close()


def mainApp():
    global data, currentNumber, oldNumber
    data = dict((name, value.value()) for (name, value) in pins.items())
    if data['reset'] == 0:
        currentNumber = 0
        data['increment'] = 0
        data['decrement'] = 0

    addition = (not data['increment']) - (not data['decrement'])
    currentNumber += addition

    if currentNumber != oldNumber and activeApp == 'mainApp':
        oldNumber = currentNumber
        lcd.writeString('current Num:' + str(currentNumber))

    sleep_ms(250)


def doorApp():
    global currentDistanceUSonic1, doorRequest, lastDoorRequest
    currentDistanceUSonic1 = int(uSonic1.readDistance())

    if doorRequest != 0x02:
        if currentDistanceUSonic1 < 16:
            doorRequest = 0x01
        else:
            doorRequest = 0x00

    if lastDoorRequest != doorRequest and activeApp == 'doorApp':
        lcd.writeString(doorStates[doorRequest])
        lastDoorRequest = doorRequest

    sleep_ms(250)


def loop():
    while True:
        if activeApp == 'mainApp':
            mainApp()
        elif activeApp == 'doorApp':
            doorApp()
        else:
            lcd.writeString('waiting...')
            sleep_ms(250)


if __name__ == '__main__':
    lcd.writeString('Creating AP....')
    generateAp(wifiName, wifiPassword)
    serverThread = _thread.start_new_thread(createServer, ())
    loopThread = _thread.start_new_thread(loop(), ())
