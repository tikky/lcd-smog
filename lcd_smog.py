import ujson
import urequests as requests

from cet import cettime #for proper timezone

from ntptime import settime
import utime

from time import sleep, sleep_ms, ticks_ms
from machine import I2C, Pin, Timer, reset
from esp8266_i2c_lcd import I2cLcd

import micropython
import utime
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
url = cfg['URL'] #"https://192.168.6.11/smog/pomiary/api"
CHIP = cfg['CHIP'] #ESP32


## Hardware WDT for ESP32
if CHIP == "ESP32":
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

lcd.putstr("SIGNATI\nSMOG 0.12a")
sleep_ms(2000)
lcd.clear()

def do_connect():
    import network #, time
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

def get_from_api(url):
    print ('Wchodze do petli')
    #lcd.move_to(LCD_CHARS-6, 0)
    #lcd.putstr("  updt")
    sleep_ms(200)
    print ('Sprawdzam WiFI')
    do_connect()
    print ('Wchodze w TRY')
    try:
        response = requests.get(url, headers = {
            "Accept": "application/json"
        })
        dane = ujson.loads(response.content)
        print ('Parsuje JSON..')
        dekodowane_dane = response.json()
        print ('Zamykam respoonse..')
        response.close()
        print ('END TRY')
    except:
        print("Nieznany blad")
        return None
    
    #if CHIP == "ESP8266":
    #    wdt_feed() #feed the dog #wemos
    if CHIP == "ESP32":
        wdt.feed() #feed the dog #esp32
    
    print ('jestem za pêtl¹')
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

    if dane != None:
        if int(dane["pm10_norm"]) > 100:
            pass

        lcd.move_to(0, 0)
        # chr(223)
        #lcd.putstr(czas+"\nPM10: "+dane["pm10_norm"]+"% "+dane["temp"]+chr(2))
        lcd.putstr(czas+"\nPM10: "+dane["pm10_norm"]+"% ")
        lcd.move_to(LCD_CHARS-6, 1)
        lcd.putstr('{:>5}'.format(dane["temp"])+chr(2))
        last_update = dane["date"]  #"2019-12-17 14:36:09"
        
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
        dane = get_from_api(url) #refresh data from api
        sleep(REFRESH_DATA)
    except (KeyboardInterrupt, SystemExit):
        timer.deinit()
        print('stopped')
        

