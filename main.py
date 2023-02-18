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
    await spa.change_light(0, state)
    while True:
        msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_STATUS_UPDATE):
            await spa.parse_status_update(msg)
            return get_state(spa)
        await asyncio.sleep(0)
        
async def set_temp(spa, state):
    await spa.send_config_req()
    await spa.listen_until_configured()
    await spa.send_temp_change(state)
    while True:
        msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_STATUS_UPDATE):
            await spa.parse_status_update(msg)
            return get_state(spa)
        await asyncio.sleep(0)
        
async def change_soak(spa, state):
    await spa.send_config_req()
    await spa.listen_until_configured()
    await spa.change_soak(state)
    while True:
        msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_STATUS_UPDATE):
            await spa.parse_status_update(msg)
            return get_state(spa)
        await asyncio.sleep(0)
    
async def set_mode(spa, state):
    await spa.send_config_req()
    await spa.listen_until_configured()
    await spa.change_heatmode(state)
    while True:
        msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_STATUS_UPDATE):
            await spa.parse_status_update(msg)
            return get_state(spa)
        await asyncio.sleep(0)

async def set_pump(spa, state):
    await spa.send_config_req()
    await spa.listen_until_configured()
    while True:
        await spa.send_panel_req(4, 0)
        msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_STATUS_UPDATE):
            await spa.parse_status_update(msg)
            break
        await asyncio.sleep(0)

    await spa.change_pump(0, pump_modes.index(str(state)))
    while True:
        await spa.send_panel_req(4, 0)
        msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_STATUS_UPDATE):
            await spa.parse_status_update(msg)
            return get_state(spa)
        await asyncio.sleep(0)

async def read_spa(spa, state=None):
    await spa.send_config_req()
    await spa.listen_until_configured()
        
    # while True:
        # print("Asking for setup parameters")
        # await spa.send_panel_req(4, 0)
        # msg = await spa.read_one_message()
        # if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_SETUP_PARAMS_RESP):
            # spa.parse_setup_parameters(msg)
            # print("Min Temps: {0}".format(spa.tmin))
            # print("Max Temps: {0}".format(spa.tmax))
            # print("Nr of pumps: {0}".format(spa.nr_of_pumps))
            # break
        # await asyncio.sleep(0)    
            
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
        await asyncio.sleep(0)
        
      
async def connect_and_func(spa_host, func,  timeout=5, state=None):
    spa = balboa.BalboaSpaWifi(spa_host)
    try:
        success = await asyncio.wait_for(spa.connect(), timeout=timeout)
        if success:
            return await asyncio.wait_for(func(spa, state=state), timeout=timeout)
    except asyncio.TimeoutError:
        print("timeout")
    finally:
        await asyncio.wait_for(spa.disconnect(), timeout=timeout)
    
    
def on_connect( client, userdata, flags, rc):
    print("MQTT connected with result code "+str(rc))
    client.subscribe("balboa/command/+")
    
def on_message(client, userdata, msg):
    parts = msg.topic.split('/')    
    print(parts, msg.payload)
    if len(parts) == 3:
        cmd = parts[2]
        if cmd == 'light':
            func = change_light
            state = int(msg.payload)           
        elif cmd == 'soak':
            func = change_soak
            state = int(msg.payload)
        elif cmd == 'temp':
            func = set_temp
            state = float(msg.payload)
        elif cmd == 'mode':
            func = set_mode
            state = 0 if msg.payload == b'heat' else 1           
        else:
            func = read_spa
            state = None
        with lock:        
            for _ in range(5):
                val = asyncio.run(connect_and_func(spa_host, func=func, state=state))
                if val is not None:
                    break            
            print(cmd, val)
            if val is not None:
                client.publish("balboa/status", json.dumps(val))
                
                
if __name__ == "__main__":
    client = paho.Client()
    client.connect(broker)
    client.on_connect = on_connect
    client.on_message = on_message
    client.loop_start()
    #val = asyncio.run(connect_and_set_pump(spa_host, timeout=5, mode='low'))
    #print('status', val)
    #sys.exit(1)
    while True:
        start = time.monotonic()
        with lock:
            for _ in range(5):
                val = asyncio.run(connect_and_func(spa_host, func=read_spa))
                if val is not None:
                    break
        print('status', val)
        if val is not None:
            ret= client.publish("balboa/status",json.dumps(val))
            if 'temp' in val: 
                client.publish("balboa/temp", str(val['temp']), retain=True)
        elapsed = time.monotonic() - start
        print('elapsed', elapsed)
        diff = 60  - elapsed
        if diff > 0:
            time.sleep(diff)
