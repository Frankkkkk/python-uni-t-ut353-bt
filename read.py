#!/usr/bin/env python3
# -*- coding: utf-8 -*-
## Frank@Villaro-Dixon.eu - DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE, etc.

import pexpect
import time
import os
import statistics
import requests
import re
import sys
from functools import reduce


def get_minute_measure(child, trigger_char):
    end_time = time.time()+10
    measures = []
    trigger_line = f"char-write-cmd 0x{trigger_char[0]:x} 5e"
    while time.time() < end_time:
        child.sendline(trigger_line)
        # we get 40 samples in 10s with 200ms sleep, which is ideal for sat sampling at 250ms
        time.sleep(.2) 

        child.expect("Notification handle.*", timeout=10)
        result = child.after.split(b'\r')[0]

        value = result.decode('ascii').split('value: ')[1]
        condensed = value.replace(' ', '')
        bytemsg = bytes.fromhex(condensed)

        # For more information, look at the file
        # p004cn/com/unitrend/ienv/android/domain/service/BluetoothLeService.java
        # From the decompiled cn-com-unitrend-ienv APK application
        assert(bytemsg[4] == 0x3b)  # Uni-T UT353BT noise meter
        assert(bytemsg[14] == 0x3d)  # dB(A) units

        value = bytemsg[5:]
        value = value.split(b'=')[0]
        assert(b'dBA' in value)
        raw_value = value.split(b'dBA')[0]

        dba_noise = float(raw_value.decode('ascii'))
        # print(dba_noise)
        measures.append(dba_noise)

    return {
#        'length': len(measures),
        'min': min(measures),
        'max': max(measures),
        'median': statistics.median(measures),
        'mean': statistics.mean(measures),
    }


def send_stats(stats):
    print(stats)
    now = int(time.time())
    for key, value in stats.items():
        pt = {
            "metric": "noise.outside",
            "timestamp": now,
            "value": value,
            "tags": {
               "type": key,
            }
        }
        OPEN_TSDB_HOST = os.environ.get('OPEN_TSDB_HOST')
        if OPEN_TSDB_HOST:
            url = f'http://{OPEN_TSDB_HOST}/api/put'
            print(url)
            r = requests.post(url, json=pt)

if len(sys.argv) == 2:
  DEVICE_MAC = sys.argv[1]
elif os.environ.get('DEVICE_MAC'):
  DEVICE_MAC = os.environ.get('DEVICE_MAC')
else:
  DEVICE_MAC = "90:E2:02:8F:76:7D"

print('Launching gatttool -I')
child = pexpect.spawn("gatttool -I")

print(f'Connecting to {DEVICE_MAC}')
child.sendline(f'connect {DEVICE_MAC}')
child.expect("Connection successful", timeout=5)
print('Connected, Hell yeah ! !')

child.sendline("char-desc");
char_desc = []
def line_reducer(arr, line):
    #x = re.search(".*handle: [0-f]*, uuid: [0-9\-]*", str(line))
    x = re.search(".*handle: (0x[0-f]*), uuid: ([-0-f]*).*", line.decode("utf-8"))
    if x:
      arr.append((int(x[1], 16), x[2]))
    return arr

while True:
    try:
        child.expect("handle: .*", timeout=2)
        lines = child.after.split(b'\n')
        chars = reduce(line_reducer, child.after.split(b'\n'), [])
        char_desc += chars
    except pexpect.exceptions.TIMEOUT as e:
        break

# print(char_desc)
TriggerUUID = '0000ff01-0000-1000-8000-00805f9b34fb'
NoiseUUID = '0000ff02-0000-1000-8000-00805f9b34fb'
ClientCharacteristicConfigurationUUID = '00002902-0000-1000-8000-00805f9b34fb'

trigger_char = list(filter(lambda t: t[1] == TriggerUUID, char_desc))[0] # should be length == 1, could use next()
noise_char = list(filter(lambda t: t[1] == NoiseUUID, char_desc))[0] # should be length == 1, could use next()

# enable notification, on ClientCharacteristicConfigurationUUID for NoiseUUID, just noise_handle+1
child.sendline(f"char-write-cmd 0x{noise_char[0]+1:x} 01")

# TODO: someone to figure out the bitlevel logic behind these commands?
CMD_SWITCH_HOLD = 'aabb04304201db'
CMD_CLEAR_HOLD = 'aabb04304501de'
CMD_SWITCH_MAX = 'aabb04303f01d8'
CMD_SWITCH_MIN = 'aabb04304001d9'
CMD_MODE_SLOW = 'aabb04304401dd'
CMD_MODE_FAST = 'aabb04304301dc'
# sent from app, appears to do nothing
CMD_UNKNOWN_1 = 'aabb04304601df'
CMD_UNKNOWN_2 = 'aabb04303d01d6'


try:
    while True:
        try:
            stats = get_minute_measure(child, trigger_char)
        except Exception as e:
            print("Sleep - Error 1")
            time.sleep(5)
            continue
        try:
            send_stats(stats)
        except Exception as e:
            print("Sleep - Error 2")
            time.sleep(5)
finally:
    child.sendline('disconnect')

# vim: set ts=4 sw=4 et:

