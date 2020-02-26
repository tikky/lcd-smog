import ujson
import urequests as requests
import sys #to check the board type

from cet import cettime #for proper timezone
from ntptime import settime
from time import sleep, sleep_ms, ticks_ms, mktime

from machine import I2C, Pin, Timer, reset
from esp8266_i2c_lcd import I2cLcd

import micropython
import gc
gc.enable()

settime()

#load variables from config file
import ujson
json_file = open('config.json')
cfg = ujson.load(json_file)

#set variables
WIFI_SSID = cfg['WIFI_SSID']
WIFI_PASS = cfg['WIFI_PASS']
DEFAULT_I2C_ADDR = int(cfg['DEFAULT_I2C_ADDR']) #0x27
DEFAULT_SCL_PIN = int(cfg['DEFAULT_SCL_PIN']) #wemos 5 esp32 #22
DEFAULT_SLA_PIN = int(cfg['DEFAULT_SLA_PIN']) #wemos 4 esp32 #21
LCD_LINES = int(cfg['LCD_LINES']) #2 4
LCD_CHARS = int(cfg['LCD_CHARS']) #16 20
REFRESH_DATA = int(cfg['REFRESH_DATA']) #30 #how often to get data from api [s]
URL = cfg['URL'] #"https://192.168.6.11/smog/pomiary/api"
CHIP = sys.platform #cfg['CHIP']


## Hardware WDT for ESP32
if CHIP == "esp32":
    from machine import WDT
    wdt = WDT(timeout=(REFRESH_DATA*2*1000)) #watchdog timeout [ms]
## END Hardware WDT


## Simple software WDT implementation for ESP8266
#wdt_counter = 0

#def wdt_callback():
#    global wdt_counter
#    wdt_counter += 1
#    if (wdt_counter >= 90):
#        print("watchdog reset")
#        reset()

#def wdt_feed():
#    global wdt_counter
#    wdt_counter = 0
## END Simple software WDT implementation

i2c = I2C(scl=Pin(DEFAULT_SCL_PIN), sda=Pin(DEFAULT_SLA_PIN), freq=400000) 
lcd = I2cLcd(i2c, DEFAULT_I2C_ADDR, LCD_LINES, LCD_CHARS)

lcd.clear()

#test
happy_face = bytearray([0x00,0x0A,0x00,0x04,0x00,0x11,0x0E,0x00])
sad_face = bytearray([0x00,0x0A,0x00,0x04,0x00,0x0E,0x11,0x00])
celsius = bytearray([0x18,0x18,0x06,0x09,0x08,0x09,0x06,0x00])
#celsius = bytearray([0x10,0x06,0x09,0x08,0x08,0x08,0x09,0x06])
lcd.custom_char(0, happy_face)
lcd.custom_char(1, sad_face)
lcd.custom_char(2, celsius)

lcd.putstr("STERIO AirMonitor\nSMOG 0.15")
sleep_ms(2000)
lcd.clear()

def do_connect():
    import network
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('connecting to network..')
        lcd.move_to(0, 0)
        lcd.putstr("connecting WiFI")
        lcd.move_to(0, 1)
        lcd.putstr(WIFI_SSID)
        wlan.connect(WIFI_SSID, WIFI_PASS)
        while not wlan.isconnected():
            print(".", end="")
            sleep_ms(1000)
            
    print('network config:', wlan.ifconfig())

def zfill(s, width):
    return '{:0>{w}}'.format(s, w=width)

def get_from_api(URL):
    print ('get_from_api')
    #lcd.move_to(LCD_CHARS-6, 0)
    #lcd.putstr("  updt")
    sleep_ms(200)
    print ('... Checking WiFI WiFI')
    do_connect()
    print ('... Starting TRY')
    try:
        response = requests.get(URL, headers = {
            "Accept": "application/json"
        })
        dane = ujson.loads(response.content)
        print ('... Parsing JSON')
        dekodowane_dane = response.json()
        print ('... closing response')
        response.close()
        print ('... END TRY')
    except:
        print("Error")
        return None
    
    #if CHIP == "ESP8266":
    #    wdt_feed() #feed the dog #wemos
    if CHIP == "esp32":
        wdt.feed() #feed the dog #esp32
    
    print ('After the loop')
    lcd.move_to(LCD_CHARS-6, 0)
    lcd.putstr("update")
    sleep_ms(200)
    return dekodowane_dane

dane = None

def update_lcd(_):
    now = cettime()
    hour = zfill(str(now[3]),2)
    minu  = zfill(str(now[4]),2)
    secs  = zfill(str(now[5]),2)
    czas = hour + ":" + minu + ":" + secs
    
    #also convert current time in tuple to epoch
    now_epoch = mktime(now)

    if dane != None:
        if int(dane["pm10_norm"]) > 100:
            pass
        
        last_update = dane["date"]  #"2019-12-17 14:36:09"
        #convert last_update from Y-m-d H:i:s to epoch
        last_update_epoch = mktime(tuple(int(x) for x in last_update.replace(' ','-').replace(':','-').split('-')) + (0,0))
        
        lcd.move_to(0, 0)
        lcd.putstr(czas)
        
        #if data from sensor are older then 5 min
        if (now_epoch - last_update_epoch) > 900:
            lcd.move_to(0, 1)
            lcd.putstr('{0:<{x}}'.format('Brak akt odczytu', x=LCD_CHARS)) #16 letters
            lcd.move_to(0, 2)
            lcd.putstr('{:<20}'.format(""))
            lcd.move_to(0, 3)
            lcd.putstr('{:<20}'.format(""))
        else:    
            #chr(223) - degree symbol
            #lcd.putstr(czas+"\nPM10: "+dane["pm10_norm"]+"% "+dane["temp"]+chr(2))
            lcd.move_to(0, 1)
            lcd.putstr('{:<20}'.format("PM10: "+dane["pm10_norm"]+"% "))
            lcd.move_to(LCD_CHARS-6, 1)
            lcd.putstr('{:>5}'.format(dane["temp"])+chr(2))
            
            if LCD_CHARS >= 20:
                lcd.move_to(0, 2)
                lcd.putstr("Wilg: "+dane["hum"]+" %")
                
                lcd.move_to(0, 3)
                lcd.putstr("Cisn: "+dane["pressure"]+" mmHg")
            
        lcd.move_to(LCD_CHARS-6, 0)
        #lcd.putstr(last_update[11:16])
        lcd.putstr('{:>6}'.format(last_update[11:16]))


def schedule_update_display(_):
    micropython.schedule(update_lcd, 0)
    #if CHIP == "ESP8266":
    #    wdt_callback() # start software watchdog

timer = Timer(-1)
timer.init(period=1000, mode=Timer.PERIODIC, callback=schedule_update_display)

while True:
    try:
        settime() # just for a case set time once again
        do_connect()
        dane = get_from_api(URL) #refresh data from api
        sleep(REFRESH_DATA)
    except (KeyboardInterrupt, SystemExit):
        timer.deinit()
        print('stopped')
        

