# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()

import network

WIFI_NETWORK='WIFI_NETWORK_HERE'
WIFI_PASSWORD='WIFI_PASSWORD_HERE'

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(WIFI_NETWORK, WIFI_PASSWORD)

print()
print("Connected to ", WIFI_NETWORK)