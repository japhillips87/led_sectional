# https://tutorials-raspberrypi.com/connect-control-raspberry-pi-ws2812-rgb-led-strips/
import json
import requests
import time
import math
import random
import traceback
from gpiozero import Button
from neopixel import *
from subprocess import check_call
from signal import pause

config = json.load(open('config.json'))
metars = {}
data_refreshed_at = None
map_stale = True
mfb_unreachable = False
visited = []
shutting_down = False
map_mode = 'flight_category'
leds = Adafruit_NeoPixel(config['num_of_leds'], config['led_data_pin'], brightness=config['led_brightness'])
flight_category_button = Button(config['button_pins']['flight_category'])
temperature_button = Button(config['button_pins']['temperature'])
visited_button = Button(config['button_pins']['visited'])
party_button = Button(config['button_pins']['party'], hold_time=5)

def loop():
    setup()
    while shutting_down != True:
        update_map()

def setup():
    configure_buttons()
    leds.begin()
    set_legend_leds()
    set_map_mode('flight_category')

def cleanup():
    for i in range(leds.numPixels()):
        set_led(i, config['colors']['off'])
    leds.show()

def shutdown():
    global shutting_down

    shutting_down = True
    cleanup()
    check_call(['sudo', 'poweroff'])

def configure_buttons():
    flight_category_button.when_pressed = lambda : set_map_mode('flight_category')
    temperature_button.when_pressed = lambda : set_map_mode('temperature')
    visited_button.when_pressed = lambda : set_map_mode('visited')
    party_button.when_pressed = lambda : set_map_mode('party')
    party_button.when_held = shutdown

def set_legend_leds():
    for index, color in config['legend_leds'].items():
        set_led(config[index], config['colors'][color])
    leds.show()

def set_map_mode(mode):
    global map_mode, map_stale, data_refreshed_at

    map_mode = mode
    map_stale = True
    data_refreshed_at = None

    update_legend_mode_leds()

def update_legend_mode_leds():
    for index in config['legend_mode_leds']:
        possible_index = map_mode + '_mode_led'
        if possible_index == index:
            set_led(config[possible_index], config['colors']['white'])
        else:
            set_led(config[index], config['colors']['off'])
    leds.show()

def set_led(index, color):
    leds.setPixelColor(index, Color(*color))

def update_map():
    if map_mode == 'flight_category' or map_mode == 'temperature':
        check_metars()
        set_map_from(map_mode)
    elif map_mode == 'visited':
        check_visited()
        set_map_from(map_mode)
    else:
        party()

def set_map_from(mode):
    global map_stale, mfb_unreachable

    if mode in ['flight_category', 'temperature']:
        for icao in metars:
            if metars[icao]:
                if mode == 'flight_category':
                    set_led(config['icao_leds'][icao], color_from_category(metars[icao][mode]))
                else:
                    set_led(config['icao_leds'][icao], color_from_temp(metars[icao]['temp_c']))
            else:
                continue

        for icao in metars.keys() ^ config['icao_leds'].keys():
            set_led(config['icao_leds'][icao], config['colors']['white'])

    elif mode == 'visited':
        if mfb_unreachable:
            for icao in metars.keys():
                set_led(config['icao_leds'][icao], config['colors']['white'])
        else:
            for icao, index in config['icao_leds'].items():
                if icao in visited:
                    set_led(index, config['colors']['green'])
                else:
                    set_led(index, config['colors']['red'])

    leds.show()
    map_stale = False


def check_metars():
    global metars, data_refreshed_at, map_stale

    if data_stale():
        icao_string = ','.join(config['icao_leds'].keys())
        payload = { 'icaos': icao_string }
        try:
            response = requests.get(config['metars_api_url'], params=payload)
            if response:
                metars = json.loads(response.text)
                data_refreshed_at = time.time()
                map_stale = True
        except:
            pass

def check_visited():
    global visited, data_refreshed_at, map_stale, mfb_unreachable

    if data_stale():
        try:
            response = requests.get(config['visited_api_url'])
            if response:
                visited = json.loads(response.text)
                data_refreshed_at = time.time()
                map_stale = True
                mfb_unreachable = False
        except:
            mfb_unreachable = True
            pass

def color_from_category(category):
    return config['colors'].get(category, config['colors']['white'])

def color_from_temp(temp):
    if temp == None or temp == '':
        return config['colors']['white']
    elif float(temp) <= config['min_temp']:
        return config['colors']['blue']
    elif float(temp) >= config['max_temp']:
        return config['colors']['red']
    else:
        mid_temp = (config['min_temp'] + config['max_temp']) / 2
        b = math.ceil(max((mid_temp - float(temp)) / mid_temp * 255, 0))
        r = math.ceil(max((float(temp) - mid_temp) / mid_temp * 255, 0))
        g = 255 - b - r
        return [r, g, b]

def party():
    global data_refreshed_at

    if data_stale():
        for index in config['icao_leds'].values():
            set_led(index, random.choice(config['party_colors']))
        leds.show()
        data_refreshed_at = time.time()

def data_stale():
    _time = data_refreshed_at # race condition
    if _time == None:
        return True
    elif time.time() - _time >= config['refresh_threshold'][map_mode]:
        return True
    else:
        return False

try:
    loop()
except Exception as e:
    traceback.print_exc()
    print(e)
finally:
    cleanup()