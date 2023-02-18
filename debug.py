import pybalboa as balboa
import asyncio
import sys
import time
import json
import paho.mqtt.client as paho
from threading import Lock

broker="nas.local"
port=1883
spa_host = '192.168.50.201'
lock = Lock()

pump_modes = ['off', 'low', 'high', 'microsilk']




def get_state(spa): 
    d = {'state' : 'heat' if spa.get_heatmode() == 0 else 'off'}

    temp = spa.curtemp
    set_temp = spa.get_settemp()

    pump = sum(spa.pump_status)
    if pump <= 2:
        d['pump_mode'] = pump_modes[pump]

    heat = int(spa.get_heatstate() == 1) #merge HEAT_WAITING and IDLE
    light = sum(spa.light_status)
    soak = spa.get_soak_type()
    if soak == 2: #microsilk
        pump += 3
        d['pump_mode'] = 'microsilk'
    soak = int(soak == 1) #filter out microsilk

    action = 'idle'
    if pump:
        action = 'fan'
    if heat:
        action = 'heating'
    d['action'] = action

    if set_temp is not None:
        d['set_temp'] = set_temp
    if temp is not None and temp != 0.0:
        d['temp'] = temp
    if pump is not None:
        d['pmp'] = pump
    if heat is not None:
        d['heat'] = heat
    if light is not None:
        d['light'] = light
    if soak is not None:
        d['soak'] = soak
        
    return d

async def change_light(spa, state):
    await spa.send_config_req()
    await spa.listen_until_configured()
    print('state 0x%x' %(state))
    await spa.control(state)
    while True:
        msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_STATUS_UPDATE):
            await spa.parse_status_update(msg)
            return get_state(spa)
        await asyncio.sleep(0)





async def connect_and_check_light(spa_host, timeout, state):
    spa = balboa.BalboaSpaWifi(spa_host)
    try:
        success = await asyncio.wait_for(spa.connect(), timeout=timeout)
        if success:
            return await asyncio.wait_for(change_light(spa, state), timeout=timeout)
    except asyncio.TimeoutError:
        print("timeout")
    finally:
        await asyncio.wait_for(spa.disconnect(), timeout=timeout)    




                
if __name__ == "__main__":
    no = [
     0x04,
     0x05,
     0x06,
     0x07,
     0x08,
     0x09,
     0x11,
     0x12,
     0x0E,
     0x16,
     0x17,
     0x0C,
     0x50,
     0x51,
     ]
    val = asyncio.run(connect_and_check_light(spa_host, timeout=5, state=0x1d))
    print('status', val)
    sys.exit(0)
    for i in range(4, 0xff):
        if i in no:
            continue
        val = asyncio.run(connect_and_check_light(spa_host, timeout=5, state=i))
        print('status', val)
        time.sleep(0.5)
