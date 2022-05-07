import pybalboa as balboa
import asyncio
import sys
import time
import json
import paho.mqtt.client as paho


broker="nas.local"
port=1883
spa_host = '192.168.50.201'

async def read_spa(spa):

    await spa.send_config_req()
    await spa.listen_until_configured()

    temp = None
    pump = None

    for i in range(0, 4):
        print("Reading panel update")
        msg = await spa.read_one_message()
        if(msg is None or spa.find_balboa_mtype(msg) != balboa.BMTR_STATUS_UPDATE):
            msg = await spa.read_one_message()
        if(msg is not None and spa.find_balboa_mtype(msg) == balboa.BMTR_STATUS_UPDATE):
            print("Got msg: {0}".format(msg.hex()))
            await spa.parse_status_update(msg)
            print("New data as of {0}".format(spa.lastupd))
            print("Current Temp: {0}".format(spa.curtemp))
            print("Tempscale: {0}".format(spa.get_tempscale(text=True)))
            print("Set Temp: {0}".format(spa.get_settemp()))
            print("Heat Mode: {0}".format(spa.get_heatmode(True)))
            print("Heat State: {0}".format(spa.get_heatstate(True)))
            print("Temp Range: {0}".format(spa.get_temprange(True)))
            print("Pump Status: {0}".format(str(spa.pump_status)))
            print("Circulation Pump: {0}".format(spa.get_circ_pump(True)))
            print("Light Status: {0}".format(str(spa.light_status)))
            print("Mister Status: {0}".format(spa.get_mister(True)))
            print("Aux Status: {0}".format(str(spa.aux_status)))
            print("Blower Status: {0}".format(spa.get_blower(True)))
            print("Spa Time: {0:02d}:{1:02d} {2}".format(
                spa.time_hour,
                spa.time_minute,
                spa.get_timescale(True)
            ))
            print("Filter Mode: {0}".format(spa.get_filtermode(True)))

            temp = spa.curtemp
            pump = sum(spa.pump_status)


            cur = time.localtime()
            cur_min = cur.tm_hour * 60 + cur.tm_min

            spa_min = spa.time_hour*60 + spa.time_minute

            print('spa_min', spa_min , 'cur_min', cur_min)

            if abs(spa_min  - cur_min) > 2:
                print("Setting time")
                print("--------------------------")
                await spa.set_time(cur)

            break
    d = {}
    if temp is not None and temp != 0.0:
        d['temp'] = temp
    if pump is not None:
        d['pmp'] =pump
    if d:
        return d



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


if __name__ == "__main__":
    client = paho.Client()
    client.connect(broker)
    client.loop_start()
    while True:
        start = time.monotonic()
        val = asyncio.run(connect_and_listen(spa_host, timeout=30))
        print('status', val)
        if val is not None:
            ret= client.publish("balboa/status",json.dumps(val))
        elapsed = time.monotonic() - start
        print('elapsed', elapsed)
        diff = 60  - elapsed
        if diff > 0:
            time.sleep(diff)
