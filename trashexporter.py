import logging
import yaml
import signal
import calendar
import os
from datetime import datetime as dt
from datetime import date, timedelta, tzinfo
from datetime import time as dt_time
import sched, time
import requests
import json
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

logging.basicConfig(level=logging.INFO)

def load_config(filename: str):
    logging.info('Loading config file')
    with open(filename, 'r') as f:
        try:
            return yaml.safe_load(f)['config']
        except yaml.YAMLError as e:
            print(e)
config = load_config('config.yml')

def sighup_handler(signum, frame):
    global config
    config = load_config('config.yml')
signal.signal(signal.SIGHUP, sighup_handler)

class TWTZ(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=8)
    def dst(self, dt):
        return timedelta(0)
    def tzname(self, dt):
        return "+08:00"
twtz = TWTZ()

pickup_time = [
    dt_time(14, 0, 0, tzinfo=twtz),
    dt_time(19, 0, 0, tzinfo=twtz),
]
# weekday names are zero indexed, so it's very not obvious
# what number corresponds to which day
days = dict(zip(calendar.day_name, range(7)))
pickup_days = ['Monday', 'Tuesday', 'Thursday', 'Friday', 'Saturday']
pickup_days = [days[d] for d in pickup_days]

scheduler = sched.scheduler(time.time, time.sleep)

def handle():
    logging.debug('Setting up next run in 15 seconds')
    scheduler.enter(15, 1, handle)

    now = dt.now(tz=twtz)
    if not now.date().weekday() in pickup_days:
        logging.debug('Wrong day')
        return
    if not any([abs(now - dt.combine(date.today(), tm)) < timedelta(minutes=10) for tm in pickup_time]):
        logging.debug('Wrong time of day')
        return

    logging.info('Querying trash website')

    url = 'https://car.hccepb.gov.tw/TMap/MapGISData.asmx/LoadObus'
    headers = {
        'Content-Type': 'application/json',
        'charset': 'UTF-8',
    }
    data = {
        'lat': config['lat'],
        'lon': config['lon'],
        'distance': config['distance'],
    }
    try:
        response = requests.post(
            url=url, headers=headers, data=json.dumps(data),timeout=10
        )
    except requests.Timeout as e:
        logging.error(e)
        return
    j = json.loads(json.loads(response.text)["d"])

    logging.info(f'Got {len(j)} cars.')

    for car in j:
        car_no = car['car_no']
        lat = car['lat']
        lon = car['lon']
        direction = car['direction']

        token = config.get('influxdb_token')
        org = "deiskos"
        bucket = "trashexporter"
        with InfluxDBClient(
            url="http://influxdb:8086", token=token, org=org
        ) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            point = Point("car") \
                .tag('car_no', car_no) \
                .field('lat', lat) \
                .field('lon', lon) \
                .field('direction', direction) \
                .time(now.utcnow(), WritePrecision.NS)
            write_api.write(bucket, org, point)

handle()
while True:
    scheduler.run()
    time.sleep(0.1)
