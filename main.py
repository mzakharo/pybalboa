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


def get_state(spa): 
    temp = spa.curtemp
    pump = sum(spa.pump_status)
    set_temp = spa.get_settemp()

    heat = int(spa.get_heatstate() == 1) #merge HEAT_WAITING and IDLE
    light = sum(spa.light_status)
    soak = spa.get_soak_type()
    if soak == 2: #microsilk
        pump += 3
    soak = int(soak == 1) #filter out microsilk
    
    d = {'state' : 'heat'}
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
    #await spa.read_one_message()
    await spa.change_light(0, state)
    light = -1
    while True:
        msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_STATUS_UPDATE):
            await spa.parse_status_update(msg)
            return get_state(spa) 
    
async def set_temp(spa, temp):
    await spa.send_config_req()
    await spa.listen_until_configured()
    await spa.send_temp_change(temp)
    while True:
        msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_STATUS_UPDATE):
            await spa.parse_status_update(msg)
            return get_state(spa)  
    
async def read_spa(spa):

    await spa.send_config_req()
    await spa.listen_until_configured()

    temp = None
    pump = None
    heat = None
    light = None
    soak = None
    set_temp = None

    while True:
        msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_STATUS_UPDATE):
            await spa.parse_status_update(msg)
            print("New data as of {0}".format(spa.lastupd))
            print("Current Temp: {0}".format(spa.curtemp))
            print("Tempscale: {0}".format(spa.get_tempscale(text=True)))
            print("Set Temp: {0}".format(spa.get_settemp()))
            print("Heat Mode: {0}".format(spa.get_heatmode(True)))
            print("Heat State: {0}".format(spa.get_heatstate(True)))
            print("Temp Range: {0}".format(spa.get_temprange(True)))
            print("Pump Status: {0}".format(str(spa.pump_status)))
            print("Light Status: {0}".format(str(spa.light_status)))
            print("Soak type: {0}".format(str(spa.get_soak_type())))
            print("Spa Time: {0:02d}:{1:02d} {2}".format(
                spa.time_hour,
                spa.time_minute,
                spa.get_timescale(True)
            ))
            print("Filter Mode: {0}".format(spa.get_filtermode(True)))
            


            cur = time.localtime()
            cur_min = cur.tm_hour * 60 + cur.tm_min
            #filter out midnight transition
            exclude = [23*60+59, 0, 1]
            spa_min = spa.time_hour*60 + spa.time_minute
            print('spa_min', spa_min , 'cur_min', cur_min)
            if cur_min not in exclude and abs(spa_min  - cur_min) > 2:
                print("Setting time")
                print("--------------------------")
                await spa.set_time(cur)                
            return get_state(spa)
            break
   


    if d:
        return d


async def connect_and_set_temp(spa_host, timeout, temp):
    """ Connect to the spa and try some commands. """
    spa = balboa.BalboaSpaWifi(spa_host)
    try:
        await asyncio.wait_for(spa.connect(), timeout=timeout)
    except asyncio.TimeoutError:
        print("timeout connect")
        return
    val = None
    try:
        val = await asyncio.wait_for(set_temp(spa, temp), timeout=timeout)
    except asyncio.TimeoutError:
        print("timeout read")
    try:
        await asyncio.wait_for(spa.disconnect(), timeout=timeout)
    except asyncio.TimeoutError:
        print("timeout disconnect")
    return val
    

async def connect_and_set_light(spa_host, timeout, state):
    """ Connect to the spa and try some commands. """
    spa = balboa.BalboaSpaWifi(spa_host)
    try:
        await asyncio.wait_for(spa.connect(), timeout=timeout)
    except asyncio.TimeoutError:
        print("timeout connect")
        return
    val = None
    try:
        val = await asyncio.wait_for(change_light(spa, state), timeout=timeout)
    except asyncio.TimeoutError:
        print("timeout read")
    try:
        await asyncio.wait_for(spa.disconnect(), timeout=timeout)
    except asyncio.TimeoutError:
        print("timeout disconnect")
    return val
    

async def connect_and_listen(spa_host, timeout):
    """ Connect to the spa and try some commands. """
    spa = balboa.BalboaSpaWifi(spa_host)
    try:
        await asyncio.wait_for(spa.connect(), timeout=timeout)
    except asyncio.TimeoutError:
        print("timeout connect")
        return
    val = None
    try:
        val = await asyncio.wait_for(read_spa(spa), timeout=timeout)
    except asyncio.TimeoutError:
        print("timeout read")
    try:
        await asyncio.wait_for(spa.disconnect(), timeout=timeout)
    except asyncio.TimeoutError:
        print("timeout disconnect")
    return val
    
    
def on_connect( client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe("balboa/command/+")
    
def on_message(client, userdata, msg):
    parts = msg.topic.split('/')    
    print(parts, msg.payload)
    if len(parts) == 3:
        cmd = parts[2]
        if cmd == 'light':
            with lock:
                val = asyncio.run(connect_and_set_light(spa_host, timeout=5, state=int(msg.payload)))
            print(cmd, val)
            if val is not None:
                client.publish("balboa/status", json.dumps(val))
        elif cmd == 'temp':
            with lock:
                val = asyncio.run(connect_and_set_temp(spa_host, timeout=5, temp=float(msg.payload)))
            print(cmd , val)
            if val is not None:
                client.publish("balboa/status", json.dumps(val))
                
                
if __name__ == "__main__":
    client = paho.Client()
    client.connect(broker)
    client.on_connect = on_connect
    client.on_message = on_message
    client.loop_start()
    #val = asyncio.run(connect_and_set_temp(spa_host, timeout=5, temp=40.0))
    #print('status', val)
    #sys.exit(1)
    while True:
        start = time.monotonic()
        with lock:
            val = asyncio.run(connect_and_listen(spa_host, timeout=5))
        print('status', val)
        if val is not None:
            ret= client.publish("balboa/status",json.dumps(val))
        elapsed = time.monotonic() - start
        print('elapsed', elapsed)
        diff = 60  - elapsed
        if diff > 0:
            time.sleep(diff)
