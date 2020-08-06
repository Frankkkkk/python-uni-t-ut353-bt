#!/usr/bin/env python3
# -*- coding: utf-8 -*-
## Frank@Villaro-Dixon.eu - DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE, etc.

import pexpect
import time
import os
import statistics
import requests


def get_minute_measure(child):
    end_time = time.time()+10
    measures = []
    while time.time() < end_time:
        child.sendline("char-write-cmd 0x25 5e")
        time.sleep(.1)

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
        print(dba_noise)
        measures.append(dba_noise)
    return {
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
        url = f'http://{OPEN_TSDB_HOST}/api/put'
        print(url)
        r = requests.post(url, json=pt)



DEVICE = "90:E2:02:8F:76:7D"

print('Launching gatttool -I')
child = pexpect.spawn("gatttool -I")

print(f'Connecting to {DEVICE}')
child.sendline(f'connect {DEVICE}')
child.expect("Connection successful", timeout=5)
print('Connected, Hell yeah ! !')

time.sleep(1)

try:
    while True:
        try:
            stats = get_minute_measure(child)
        except Exception as e:
            print("Sleep - Error 1")
            time.sleep(5)
        try:
            send_stats(stats)
        except Exception as e:
            print("Sleep - Error 2")
            time.sleep(5)
finally:
    child.sendline('disconnect')

# vim: set ts=4 sw=4 et:

