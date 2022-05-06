import pybalboa as balboa
import asyncio
import sys
import time
import json
import paho.mqtt.client as paho


broker="nas.local"
port=1883
spa_host = '192.168.50.201'


async def connect_and_listen(spa_host):
    """ Connect to the spa and try some commands. """
    spa = balboa.BalboaSpaWifi(spa_host)
    await spa.connect()

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

            '''
            cur = time.localtime()
            spa_time = time.localtime()
            spa_time = list(spa_time)
            spa_time[3] = spa.time_hour
            spa_time[4] = spa.time_minute
            spa_time = time.struct_time(tuple(spa_time)) 

            diff = time.mktime(cur) - time.mktime(spa_time) / 60
            print('time difference', diff)
            if diff > 10:
            '''

            print("Trying to set time")
            print("--------------------------")
            await spa.set_time(time.localtime())
            await spa.disconnect()
            break
    d = {}
    if temp is not None and temp != 0.0:
        d['temp'] = temp
    if pump is not None:
        d['pmp'] =pump
    if d:
        return d

async def connect_and_listen_timeout(spa_host, timeout):
    val = None
    try:
        val = await asyncio.wait_for(connect_and_listen(spa_host), timeout=timeout)
    except asyncio.TimeoutError:
        print("timeout")
    return val

if __name__ == "__main__":
    client = paho.Client("balboa")
    client.connect(broker)
    client.loop_start()
    while True:
        start = time.monotonic()
        val = asyncio.run(connect_and_listen_timeout(spa_host, timeout=30))
        print('status', val)
        if val is not None:
            ret= client.publish("balboa/status",json.dumps(val))
        elapsed = time.monotonic() - start
        print('elapsed', elapsed)
        diff = 60  - elapsed
        if diff > 0:
            time.sleep(diff)
