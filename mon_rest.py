from sonic_platform_base.sonic_xcvr.codes.public.cmis import CmisCodes
from sonic_platform_base.sonic_xcvr.api.public.cmis import CmisApi
from sonic_platform_base.sonic_xcvr.api.public.c_cmis import CCmisApi
from sonic_platform_base.sonic_xcvr.mem_maps.public.cmis import CmisMemMap
from sonic_platform_base.sonic_xcvr.api.public.cmisVDM import CmisVdmApi

from sonic_platform_base.sonic_xcvr.codes.public.sff8436 import Sff8436Codes
from sonic_platform_base.sonic_xcvr.api.public.sff8436 import Sff8436Api
from sonic_platform_base.sonic_xcvr.mem_maps.public.sff8436 import Sff8436MemMap

from sonic_platform_base.sonic_xcvr.codes.public.sff8636 import Sff8636Codes
from sonic_platform_base.sonic_xcvr.api.public.sff8636 import Sff8636Api
from sonic_platform_base.sonic_xcvr.mem_maps.public.sff8636 import Sff8636MemMap

from sonic_platform_base.sonic_xcvr.codes.public.sff8472 import Sff8472Codes
from sonic_platform_base.sonic_xcvr.api.public.sff8472 import Sff8472Api
from sonic_platform_base.sonic_xcvr.mem_maps.public.sff8472 import Sff8472MemMap

from sonic_platform_base.sonic_xcvr.xcvr_eeprom import XcvrEeprom
from sonic_platform_base.sonic_xcvr.api.xcvr_api import XcvrApi

import sonic_platform.platform
import sonic_platform_base.sonic_sfp.sfputilhelper
import time
import redis
from flask import Flask
from flask_restplus import Resource, Api
from threading import Thread
from threading import Event
from TelemetryAdaptor import TelemetryAdaptor
import json

TRANSCEIVER_DOM_SENSOR_TABLE = 'TRANSCEIVER_DOM_SENSOR'

interface = "Ethernet48"
pport= 7


portx = 3106

# Flask and Flask-RestPlus configuration
app = Flask(__name__)
api = Api(app, version='1.0', title='Sonic API',
          description='Rest API to get data from pluggables. \nAuthor: Andrea Sgambelluri')
monitoring = api.namespace('Monitoring', description='Sonic APIs')

events = {}
threads = {}
jobs = {}
thread_id = 1
config_file = "config.json"
config = None


def telemetry_task(event, thread_idx, port, interface, mode):
    global config
    telemetry_adaptor = TelemetryAdaptor(config["redis"])  # configuration for the telemetry adaptor
    sleep_time = config["sleep_time"]  # telemetry period
    header = config["header"]  # header to attach to the telemetry sample
    header["tags"]["interface"] = "{}/{}".format(interface, port)
    print('Telemetry job {} starting...'.format(thread_idx))

    while True:
        data_body = {}
        pport = port
        platform_chassis = sonic_platform.platform.Platform().get_chassis()
        sfp = platform_chassis.get_sfp(int(pport))
        apix = sfp.get_xcvr_api()
        r = redis.Redis(host='localhost', port=6379, db=6)
        d1 = r.hgetall(TRANSCEIVER_DOM_SENSOR_TABLE + '|' + interface)
        d = {k.decode('utf8'): v.decode('utf8') for k, v in d1.items()}
        rx = round(float(d['rx1power']), 2)
        vals = CmisApi.get_vdm(apix)
        ber = round(float(vals['Pre-FEC BER Current Value Media Input'][1][0]), 6)
        osnr = round(float(vals['OSNR [dB]'][1][0]), 2)
        esnr = round(float(vals['eSNR [dB]'][1][0]),2)

        data_body["rx-power"] = rx
        data_body["BER"] = ber
        data_body["osnr"] = osnr
        data_body["esnr"] = esnr
        msg = "Telemetry thread {} --> {}".format(thread_idx, data_body)
        print(msg)
        if mode > 0:
            try:
                data_json = {"header": header, "body": data_body}
                data = json.dumps(data_json)
                telemetry_adaptor.write_to_redis(data)
            except:
                print("Error connecting to Redis, server is unreachable!")
            # check for stop

        if event.is_set():
            break
        time.sleep(sleep_time)
    print('Telemetry thread {} closing down'.format(thread_idx))


'''
def telemetry_task(event, thread_idx, port, interface, mode):
    global config
    telemetry_adaptor = TelemetryAdaptor(config["redis"])  # configuration for the telemetry adaptor
    sleep_time = config["sleep_time"]  # telemetry period
    header = config["header"]  # header to attach to the telemetry sample

    # execute a task in a loop
    print('Telemetry thread {} starting...'.format(thread_idx))
    while True:
        pport = port
        platform_chassis = sonic_platform.platform.Platform().get_chassis()
        sfp = platform_chassis.get_sfp(int(pport))
        apix = sfp.get_xcvr_api()
        r = redis.Redis(host='localhost', port=6379, db=6)        
        d1 = r.hgetall(TRANSCEIVER_DOM_SENSOR_TABLE + '|' + interface)
        d = {k.decode('utf8'): v.decode('utf8') for k, v in d1.items()}
        rx = round(float(d['rx1power']), 2)
        vals = CmisApi.get_vdm(apix)
        ber = round(float(vals['Pre-FEC BER Current Value Media Input'][1][0]),6)
        osnr = round(float(vals['OSNR [dB]'][1][0]), 2)
        esnr = round(float(vals['eSNR [dB]'][1][0]), 2)
        line = "{},{},{},{}".format(rx, ber, osnr, esnr)
        msg = "Telemetry thead {} --> {}".format(thread_idx, line)
        print(msg)
        if mode > 0:
            try:
                data_json = {"header": header, "body": line}
                data = json.dumps(data_json)
                telemetry_adaptor.write_to_redis(data)
            except:
                print("Error connecting to Redis, server is unreachable!")
            # check for stop
        if event.is_set():
            break
        # report a message 
        time.sleep(sleep_time)
    print('Telemetry thread {} closing down'.format(thread_idx))
'''


@monitoring.route('/get-data/<int:port>/<string:interface>/<int:mode>')
@monitoring.response(200, 'Success')
@monitoring.response(404, 'Error, not found')
class _getData(Resource):
    @staticmethod
    def get(port, interface, mode):
       lines = []
       pport = port
       platform_chassis = sonic_platform.platform.Platform().get_chassis()
       platform_sfputil = sonic_platform_base.sonic_sfp.sfputilhelper.SfpUtilHelper()
       sfp = platform_chassis.get_sfp(int(pport))
       apix = sfp.get_xcvr_api()
       r = redis.Redis(host='localhost', port=6379, db=6)
       for i in range (0, mode):
           d1 = r.hgetall(TRANSCEIVER_DOM_SENSOR_TABLE + '|' + interface)
           d = {k.decode('utf8'): v.decode('utf8') for k, v in d1.items()}
           rx = round(float(d['rx1power']), 2)
           vals = CmisApi.get_vdm(apix)
           ber = round(float(vals['Pre-FEC BER Current Value Media Input'][1][0]),6)
           osnr = round(float(vals['OSNR [dB]'][1][0]), 2)
           esnr = round(float(vals['eSNR [dB]'][1][0]),2)
           #line = "RX={}\tBER={}\tOSNR={}\teSNR={}".format(rx, ber, osnr, esnr)
           line = "{},{},{},{}".format(rx, ber, osnr, esnr)
           lines.append(line)
           print(line)
       return lines, 200


@monitoring.route('/startTelemetry/<int:port>/<string:interface>/<int:mode>')
@monitoring.response(200, 'Success')
@monitoring.response(404, 'Error, not found')
class _startTelemetry(Resource):
    @monitoring.doc(description="start telemetry")
    @staticmethod
    def put(port, interface, mode):
        global threads
        global thread_id
        global jobs

        event = Event()

        thread = Thread(target=telemetry_task, args=(event, thread_id, port, interface, mode))
        thread.start()

        threads[thread_id] = {}
        jobs[thread_id] = {}
        threads[thread_id]["event"] = event
        threads[thread_id]["thread"] = thread
        threads[thread_id]["active"] = True
        jobs[thread_id]["data"] = [port, interface, mode]
        jobs[thread_id]["active"] = True
        thread_id = thread_id + 1
        return thread_id - 1, 200

@monitoring.route('/stopTelemetry/<int:job_id>')
@monitoring.response(200, 'Success')
@monitoring.response(404, 'Error, not found')
class _stopTelemetryData(Resource):
    @monitoring.doc(description="stop telemetry")
    @staticmethod
    def delete(job_id):
        global threads
        global thread_id
        global jobs
        if threads[job_id]["active"]: 
            event = threads[job_id]["event"]
            thread = threads[job_id]["thread"]
            event.set()
            # wait for the new thread to finish
            thread.join()
            threads[job_id]["active"] = False
            jobs[job_id]["active"] = False
            return job_id , 200
        return thread_id , 404


@monitoring.route('/getTelemetryJobs')
@monitoring.response(200, 'Success')
@monitoring.response(404, 'Error, not found')
class _getTelemetry(Resource):
    @staticmethod
    def get():
        global jobs
        return jobs, 200


if __name__ == '__main__':
    c_file = open(config_file)
    config = json.load(c_file)
    print(config)
    app.run(host='0.0.0.0', port=portx)


