import json
import urequests
import time
import math
import random
from neopixel import *
from machine import Pin

config = json.load(open('config.json'))
metars = {}
data_refreshed_at = None
map_stale = True
visited = []
map_mode = 'flight_category'

led_pin = Pin(config['led_data_pin'])
leds = NeoPixel(led_pin, config['num_of_leds'])

flight_category_button = Pin(config['button_pins']['flight_category'], Pin.IN, Pin.PULL_UP)
temperature_button = Pin(config['button_pins']['temperature'], Pin.IN, Pin.PULL_UP)
visited_button = Pin(config['button_pins']['visited'], Pin.IN, Pin.PULL_UP)
party_button = Pin(config['button_pins']['party'], Pin.IN, Pin.PULL_UP)

def button_pressed(button):
    buttons = {'flight_category': flight_category_button, 'temperature': temperature_button, 'visited': visited_button, 'party': party_button}

    for mode, btn in buttons.items():
        if btn == button:
            button.irq(handler=None)
            time.sleep(0.2) # debounce
            button.irq(handler=button_pressed, trigger=Pin.IRQ_RISING)
            set_map_mode(mode)


flight_category_button.irq(trigger=Pin.IRQ_RISING, handler=button_pressed)
temperature_button.irq(trigger=Pin.IRQ_RISING, handler=button_pressed)
visited_button.irq(trigger=Pin.IRQ_RISING, handler=button_pressed)
party_button.irq(trigger=Pin.IRQ_RISING, handler=button_pressed)

def loop():
    setup()
    while True:
        update_map()

def setup():
    set_legend_leds()
    set_map_mode('flight_category')

def cleanup():
    for i in range(leds.__len__()):
        set_led(i, config['colors']['off'])
    leds.write()

def expire_data():
    global map_stale, data_refreshed_at

    map_stale = True
    data_refreshed_at = None

def set_legend_leds():
    for index, color in config['legend_leds'].items():
        set_led(config[index], config['colors'][color])
    leds.write()

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
    leds.write()

def set_led(index, color):
    leds[index] = [int(config['led_brightness'] * i) for i in color]

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
    global map_stale

    if map_stale:
        if mode in ['flight_category', 'temperature']:
            for icao in metars:
                if metars[icao]:
                    if mode == 'flight_category':
                        set_led(config['icao_leds'][icao], color_from_category(metars[icao][mode]))
                    else:
                        set_led(config['icao_leds'][icao], color_from_temp(metars[icao]['temp_c']))
                else:
                    continue

            for icao in config['icao_leds'].keys():
                if not icao in metars.keys():
                    set_led(config['icao_leds'][icao], config['colors']['white'])

        elif mode == 'visited':
            for icao, index in config['icao_leds'].items():
                if icao in visited:
                    set_led(index, config['colors']['green'])
                else:
                    set_led(index, config['colors']['red'])

        leds.write()
        map_stale = False


def check_metars():
    global metars, data_refreshed_at, map_stale

    if data_stale():
        try:
            response = urequests.get(config['metars_api_url'])
            metars = response.json()
            data_refreshed_at = time.time()
            map_stale = True
        except:
            pass

def check_visited():
    global visited, data_refreshed_at, map_stale

    if data_stale():
        try:
            response = urequests.get(config['visited_api_url'])
            visited = response.json()
            data_refreshed_at = time.time()
            map_stale = True
        except:
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
        leds.write()
        data_refreshed_at = time.time()

def data_stale():
    if map_stale:
        return True

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
    print(e)
finally:
    cleanup()