from machine import Pin, I2C
from utime import sleep_ms

from lcd import LCD16X1
from ultrasonic import ultraSonic
from gc import collect, enable

import _thread
import network  
import socket

enable()        # to enable the automatic garbage collection
collect()       # to collect the 0 reference variables (free up ram)

wifiName = 'esp32'  # the esp access point name
wifiPassword = 'Th3@Professional'   # the esp access point password
activeApp = ''  # used to save the current working app, allowed values ('mainApp', 'doorApp')

pins = {
    'increment': Pin(34, Pin.IN, Pin.PULL_UP),
    'decrement': Pin(35, Pin.IN, Pin.PULL_UP),
    'reset': Pin(36, Pin.IN, Pin.PULL_UP),
    'internalLed': Pin(2, Pin.OUT, value=1)
}   # used to save the GPIO pins and set if they are input (in pull up mode){34, 35, 36} or output (with value = 1){2}
data = dict()   # used to save the value will be read from GPIO input pins

serverSocket: socket.socket = None  # used to save the web socket
mainAppHtml: str = ''   # used to save the read html text from mainAppIndex.html
doorAppHtml: str = ''   # used to save the read html text from doorAppIndex.html
indexHtml: str = ''     # used to save the read html text from index.html
settingsHtml: str = ''  # used to save the read html text from settings.html
styleSheet: str = ''    # used to save the read css text from styleSheet.css

lcd = None
try:
    i2c = I2C(-1, scl=Pin(22), sda=Pin(21), freq=int(240E6))  # activating i2c serial protocol at pins(21, 22) with freq 240 MH
    lcd = LCD16X1(i2c, 0x27)  # used to bind with lcd using i2c having slave address 0x27 (39d)
except Exception as e:
    pass

currentNumber = 0   # used to save the current number value
oldNumber = -1      # used to save the last current number value (they are not equal to make lcd print the value at first run)

uSonic1 = ultraSonic(18, 19)    # used to bind with ultrasonic at pins 18, 19
currentDistanceUSonic1 = 100    # used to save the distance read from ultrasonic
doorStates = ('idle', 'request', 'rejected')    # used to send status for the front-end by indexing
doorRequest = 0x00  # 0x00 to close the door, 0x01 to open the door, 0x02 stop accepting
lastDoorRequest = 0x03      # used to save the last door request (they are not equal to make lcd print the status at first run)
clientsNumber = 0   # used to save the current clients number
maxClientsNumber = 3    # used to save the max clients allowed to enter the place

# the context manager will define readers that will read html file and will close file descriptors after exiting from context
# open(filename, open_option) used to make file descriptor to r/w specific file
with open('mainAppIndex.html', 'r') as mainAppReader, open('index.html', 'r') as indexHtmlReader, \
        open('doorAppIndex.html', 'r') as doorAppReader, open('settings.html', 'r') as settingsHtmlReader, \
        open('styleSheet.css', 'r') as styleSheetReader:
    mainAppHtml = mainAppReader.read()     # reading 'mainAppIndex.html' and saving it mainAppHtml
    indexHtml = indexHtmlReader.read()
    doorAppHtml = doorAppReader.read()
    settingsHtml = settingsHtmlReader.read()
    styleSheet = styleSheetReader.read()


def generateAp(essid: str, password: str, authMode=network.AUTH_WPA2_PSK, maxClients: int = 1):
    """
    =------------------------------------------------------------------------------------------------------------------=
                                            *specifications and requirements*
        setting and configuring the wifi interface of mcu
        activating the AP
        turning off the led after activating the AP.
    =------------------------------------------------------------------------------------------------------------------=
        :var pins:         global variable, used to set, read value of GPIO pins used in project 1 (main app)
        :var ap:           local variable, used to save wireless interface class to configure access point
        :param essid:       the access point name
        :param password:    the access point password
        :param authMode:    the access point auth mode common auth modes {OPEN, WEP, WPA_WPA2_PSK, WPA2_PSK}
        :param maxClients:  the max number of clients can be connected to the interface at the same time
        :return: None
    """

    global serverSocket           # declaring the global variable so it can be set inside the function

    ap = network.WLAN(network.AP_IF)  # setting the wlan interface to be access point (AP_IF)
    ap.config(essid=essid,
              password=password,
              authmode=authMode,
              max_clients=maxClients)  # configuring access point parameters (name, password, auth, clients no.)
    ap.active(True)  # activating the wireless interface of esp32

    while not ap.active():  # empty loop to hang the system up until the access point starts
        pass
    
    pins['internalLed'].value(0)    # setting GPIO 2 to low after setting the server and access point


def createServer():
    """
        =--------------------------------------------------------------------------------------------------------------=
                                            *specifications and requirements*
        hanging up until a request is caught
                if the request no. <= 5 then it will be accepted [listen(5)] else it will be rejected and closed
        reading the received request from the client
        parsing the received request (request type, requested path, post data, get data)
        parsing the url sent by the client.
        creating the infrastructure of the web server for handling and parsing the requests.
        =--------------------------------------------------------------------------------------------------------------=
                                                    *allowed formats*
        accepting (post, get) requests
        accepted urls ('/', '/index.html', 'mainApp/', 'mainApp/index.html', 'doorApp/', 'doorApp/index.html',
                       'doorApp/request', 'mainApp/currentNumber', 'stylesheet.css')
        paths => '/', '/index.html' the main page of web server (localhost) to redirect you to one app
              => 'mainApp', 'mainApp/index.html' the main page of main app (counting system)
              => 'mainApp/currentNumber' returns the value of current number of the system to be used by js.
              => 'doorApp', 'doorApp/index.html' the main page of door app (corona system)
              => 'doorApp/request' returns the current door status and current clients number(close, enter[exit], reject)
                 to be used by js.
              => 'stylesheet.css' the css stylesheet of all pages
        =--------------------------------------------------------------------------------------------------------------=

        :var serverSocket:  global variable, socket (used to access the created socket)
        :var currentNumber: global variable, used to save the value of current number in project 1 (main app)
        :var activeApp:     global variable, used to set, read the current active app (main app, door app, '')
        :var doorRequest:   global variable, used to set, read the door request value (close, request, rejected)
        :var clientsNumber: global variable, used to set, read the number of clients in place (door app)
        :var currentDistanceUSonic1: global variable, used to set, read the ultrasonic sensor object distance (door app)
        :var maxClientsNumber: global variable, used to set, read the max clients in place (door app)
        :var socketConnection: local variable, used to save the socket connection to receive and send data
        :var clientAddress: local variable, used to save the ip address of client that sent the request
        :var request: local variable, used to save the received request from the client to be parsed
        :var headers: local variable, used to read the headers in request (to know more about request)
        :var requestType: local variable, used to read the type of the received request (GET, POST, HEAD, ...etc)
        :var fileName: local variable, used to read the requested path (localhost/filename, then fileName = /filename)
        :var postData: local variable, used to read the request data send by post request (requestType == POST)
        :var choice: local variable, used to read the current post request at the two apps {(inc., dec., reset),
                                                                                            (enter, exit)}
        :var number: local variable, used to read the max no. of clients send by settings page

        :return: None
    """
    global serverSocket, currentNumber, activeApp, \
        doorRequest, clientsNumber, currentDistanceUSonic1, \
        maxClientsNumber
    
    serverSocket = socket.socket(socket.AF_INET,
                                 socket.SOCK_STREAM)  # creating web socket (address family ipv4, socket protocol TCP)
    serverSocket.bind(('', 80))     # binding the web socket at mcu local ip address at port 80 (web surfing port)
    serverSocket.listen(5)          # listening for incoming requests at max of 5 in queue before rejection
    
    while True:
        socketConnection, clientAddress = serverSocket.accept()     # hanging up until a request is received
        request = socketConnection.recv(4096).decode('utf-8', 'ignore')  # reading the request data (4 bytes at once)
        headers = request.split('\n')    # splitting request line by line to get headers
        requestType, fileName, *http = headers[0].split()   # splitting first header using spaces to parse request (request type, path, http type)
        fileName = str(fileName).strip('/\t\n').lower()   # removing trailing (spaces, /, tabs, new lines) parse req. path (ex: /filename/ => filename)
        getData = dict(tuple(get_data.split("=")[:2]
                       if "=" in get_data else (get_data, '')
                       for get_data in fileName.split("?")[-1].split("&")))     # reading the get data from the request url (ex: /?cmd=inc => getData[cmd] = inc)

        postData = dict(tuple(post_data.split('=')[:2])
                        if '=' in post_data else (post_data, '')
                        for post_data in headers[headers.index('\r'):])     # reading the post data from the request (the data sent by post request)

        print(activeApp, fileName)
        if fileName == 'stylesheet.css':    # accessing the stylesheet
            sendResponse(socketConnection, webPage('styleSheet'), contentType='text/css')
            continue

        if fileName == '' or fileName == 'index.html':  # accessing the main web page of local host ('' === '/')
            activeApp = ''  # setting the current active app to empty string.
            sendResponse(socketConnection, webPage())   # return response to the client and close the connection
            continue    # jump to the loop control

        if fileName == 'mainapp/currentnumber' and activeApp == 'mainApp':
            sendResponse(socketConnection, currentNumber)   # returning the current number as response and close the connection
            continue

        if fileName == 'mainapp' or fileName == 'mainapp/index.html':
            activeApp = 'mainApp'
            if requestType == 'POST':   # checking if the data is sent using post request
                choice = postData.get('choice')     # get the value of choice if exists else it will return none
                if choice == 'increment':
                    # if the user clicked increment button in front-end
                    # checking if the number of max 9999 because free space in lcd is 4 digits
                    currentNumber = (currentNumber + 1) if currentNumber < 9999 else -999
                elif choice == 'decrement':
                    # if the user clicked decrement button in front-end
                    # checking if the number is greater than -999 because free space in lcd is 4 digits
                    currentNumber = (currentNumber - 1) if currentNumber > -999 else 9999
                elif choice == 'reset':
                    # if the user clicked reset button in front-end
                    # setting the current number to 0
                    currentNumber = 0
            # returning the mainAppIndex.html page to the client with current number and closing the connection
            sendResponse(socketConnection, webPage('mainApp') % dict(current_number=currentNumber))
            continue

        if fileName == 'doorapp/request' and activeApp == 'doorApp':
            # returning door state and the current clients number to the request's client and closing the connection
            sendResponse(socketConnection, doorStates[doorRequest] + "_%s" % clientsNumber)
            continue

        if fileName == 'doorapp' or fileName == 'doorapp/index.html':
            activeApp = 'doorApp'   # setting the current active app to be door application
            # settings door status to close (initial condition) to give idle state
            doorRequest = 0x00
            currentDistanceUSonic1 = 100    # resetting the initial values of ultrasonic
            choice = postData.get('choice')     # getting choice from the request if exists else None
            number = postData.get('number')     # getting number from the request if exists else None
            if requestType == 'POST':
                if choice == 'enter':
                    # if the user clicked enter button in front-end
                    # it will check if clients number < max number else will set the state to be rejected
                    if clientsNumber < maxClientsNumber:
                        clientsNumber += 1
                    else:
                        doorRequest = 0x02
                elif choice == 'exit':
                    # if the user clicked exit button in front-end
                    # it will check if clients number > 0 else it will do nothing
                    if clientsNumber > 0:
                        clientsNumber -= 1
                    else:
                        doorRequest = 0x02
                elif choice == 'reset':
                    # if the user clicked reset button in front-end then it resets the system
                    clientsNumber = 0
                elif number:
                    # if the number is set then it's redirected from settings.html
                    # setting clientsNumber to 0
                    # setting maxClients to number if sent data is numeric and greater than 0
                    clientsNumber = 0
                    maxClientsNumber = max(0, int(number)) if number.isdigit() else 0

            # returning back to the client doorAppIndex.html with current clients number and door state
            sendResponse(socketConnection,
                         webPage('doorApp') % dict(clients_number=clientsNumber,
                                                   door_state=doorStates[doorRequest]))
            continue

        if (fileName == 'doorapp/settings' or fileName == 'doorapp/settings/index.html') and activeApp == 'doorApp':
            # returning back to the client settings.html and close the connection
            sendResponse(socketConnection, webPage('settings'))
            continue

        # returning back to the client page not found request with http status code 404
        sendResponse(socketConnection, 'Page not found', 404, 'NOT FOUND')


def webPage(selector: str = 'index'):
    """
    =------------------------------------------------------------------------------------------------------------------=
                                            *specifications and requirements*
    this function used to return the required html webpage to be sent to the client
    =------------------------------------------------------------------------------------------------------------------=
    :param selector: to select between (index, mainApp, doorApp, settings)
    :return: str
    """
    if selector == 'mainApp':
        return mainAppHtml
    elif selector == 'doorApp':
        return doorAppHtml
    elif selector == 'index':
        return indexHtml
    elif selector == 'settings':
        return settingsHtml
    elif selector == 'styleSheet':
        return styleSheet
    else:
        return None


def sendResponse(socketConnection, response, statusCode: int = 200, statusMsg: str = 'OK',
                 contentType: str = 'text/html'):
    """
    =------------------------------------------------------------------------------------------------------------------=
                                            *specifications and requirements*
    this function sends the response back to the client.
    sending http type to the client with status code (200 for nice response) with status message (OK for nice resp.)
    sending the content type for the client to make the client detect the type of returned data
    sending connection type (close or keep-alive)
    sending the response passed to it as parameter to the client after encoding it to bytes
    then closing the connection with the client either there's a problem with send or not
    =------------------------------------------------------------------------------------------------------------------=
    :param socketConnection: the socket connection handler
    :param response: the response which will be send to the client
    :param statusCode: the http status code (200 ok, 404 not found, 301/302 redirection, 500 server error, ...etc)
    :param statusMsg:  the http status msg (ok, not found, redirection, internal server error, ...etc)
    :param contentType:  the http response type
    :return: None
    """
    try:
        socketConnection.send('HTTP/1.1 %s %s\n' % (statusCode, statusMsg))
        socketConnection.send('Content-Type: %s\n' % contentType)
        socketConnection.send('Connection: close\n\n')
        # using send all here because send takes amount of the data until the buffer is filled only
        socketConnection.sendall((response if isinstance(response, str) else str(response)).encode('utf-8', 'ignore'))
    except OSError:
        pass
    finally:
        socketConnection.close()


def mainApp():
    """
    =------------------------------------------------------------------------------------------------------------------=
                                            *specifications and requirements*
    this function runs the main app handler
    reading the data from mcu GPIO pin (push buttons)
    checking if reset button if pressed (highest priority), so if it's pressed then current number must become 0
    but what if reset button is pressed with other button then due to the highest priority the other 2 buttons must be
    set to 1 so if they are not set.
    the variable addition is used to save increment, and decrement value and to handle if both are pressed at same time.
        if increment and decrement pressed then (not 0 - not 0) = 1 - 1 => so no increments or decrements will occur
        if increment pressed and decrement is not then (not 0 - not 1) = 1 - 0 => so increment will occur
        if increment is not pressed and decrement is pressed then (not 1 - not 0) = 0 - 1 => so decrement will occur
        if both are not pressed then (not 1 - not 1) = 0 - 0 => so no increments or decrements will occur
    we compare the last captured number and the current number if they are not equal this should give output to lcd
    and set the last captured number to the current captured number, so the lcd doesn't keep printing the msg.
    then the function will sleep for 250 milli-seconds so we remove bouncing effect + high increment in one press
    =------------------------------------------------------------------------------------------------------------------=
    :var data: global variable, used to save the values read from the pins of mcu
    :var currentNumber: global variable, used to record the current number
    :var oldNumber: global variable, used to record the last record of current number
    :var addition:  local variable, used to save the value of (inc, dec) push buttons
    :return: None
    """
    global data, currentNumber, oldNumber
    data = dict((name, value.value()) for (name, value) in pins.items())
    if data['reset'] == 0x00:
        currentNumber = 0x00
        data['increment'] = 0x01
        data['decrement'] = 0x01
    addition = (not data['increment']) - (not data['decrement'])
    currentNumber += addition
    currentNumber = -999 if currentNumber > 9999 else currentNumber
    currentNumber = 9999 if currentNumber < -999 else currentNumber

    if currentNumber != oldNumber:
        oldNumber = currentNumber
        lcd.writeString('current Num:' + str(currentNumber)) if lcd else None
    sleep_ms(250)
    

def doorApp():
    """
    =------------------------------------------------------------------------------------------------------------------=
                                        *specifications and requirements*
    this function run the door app handler
    reading the ultrasonic distance and saving it
    checking if the number of clients < max clients number (door request to enter is not rejected [code: 0x02])
    if door status is not rejected then it measures the distance from ultra sonic as ultra sonic reads distance up to 4m
    so we need to detect if there's a real client or not; so we made the max distance between ultrasonic and the client
    should be less than 16 cms.
    then comparing the last captured door request by the current captured door request
    if they are not equal then we need to write this to the lcd, this to not to make the lcd keep writing the values
    then settings the last captured door request to the current captured door request.
    then sleeping 250 millis-seconds to remove errors like a bee has moved in-front of ultrasonic
    =------------------------------------------------------------------------------------------------------------------=
    :var currentDistanceUSonic1: the distance measured by the ultrasonic
    :var doorRequest: the current door request
    :var lastDoorRequest: the last read door request
    :return: None
    """
    global currentDistanceUSonic1, doorRequest, lastDoorRequest
    currentDistanceUSonic1 = int(uSonic1.readDistance())

    if currentDistanceUSonic1 < 16:
        doorRequest = 0x01
    else:
        doorRequest = 0x00

    if lastDoorRequest != doorRequest:
        lcd.writeString(doorStates[doorRequest]) if lcd else None
        lastDoorRequest = doorRequest

    sleep_ms(250)


def loop():
    """
    =------------------------------------------------------------------------------------------------------------------=
                                        *specifications and requirements*
    this function runs the main loop to make the system handling all hardware changes for the two apps.
    the 250 millis-seconds sleep in this function is for making (waiting...) appears for the user
    =------------------------------------------------------------------------------------------------------------------=
    :return: None
    """
    while True:
        if activeApp == 'mainApp':
            mainApp()
        elif activeApp == 'doorApp':
            doorApp()
        else:
            lcd.writeString('waiting...') if lcd else None
            sleep_ms(250)


if __name__ == '__main__':  # checking if the app is running or imported
    lcd.writeString('Creating AP....') if lcd else None
    generateAp(wifiName, wifiPassword, maxClients=16)
    loopThread = _thread.start_new_thread(loop, ())     # creating a thread so we don't use interrupt
    serverThread = _thread.start_new_thread(createServer, ())   # creating a thread so we don't use interrupt

