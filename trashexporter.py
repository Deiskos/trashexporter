from datetime import datetime as dt
from datetime import date, time, timedelta, tzinfo
import calendar
import os
from aiohttp import web
import requests
import json
import logging

logging.basicConfig(level=logging.INFO)

class TWTZ(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=8)
    def dst(self, dt):
        return timedelta(0)
    def tzname(self, dt):
        return "+08:00"
twtz = TWTZ()

pickup_time = [
    time(14, 0, 0, tzinfo=twtz),
    time(19, 0, 0, tzinfo=twtz),
]
# weekday names are zero indexed, so it's very not obvious
# what number corresponds to which day
days = dict(zip(calendar.day_name, range(7)))
pickup_days = ['Monday', 'Tuesday', 'Thursday', 'Friday', 'Saturday']
pickup_days = [days[d] for d in pickup_days]

routes = web.RouteTableDef()
@routes.get('/metrics')
async def handle(request):
    now = dt.now(tz=twtz)

    override = True if request.rel_url.query.get('override', None)=='true' else False

    if not override:
        if not now.date().weekday() in pickup_days:
            return web.Response(text="# Wrong day")
        if not any([abs(now - dt.combine(date.today(), tm)) < timedelta(minutes=10) for tm in pickup_time]):
            return web.Response(text="# Wrong time")

    url = 'https://car.hccepb.gov.tw/TMap/MapGISData.asmx/LoadObus'
    headers = {
        'Content-Type': 'application/json',
        'charset': 'UTF-8',
    }
    data = "{lat:'REDACTED', lon:'REDACTED', distance:'10000'}"
    response = requests.post(url=url, headers=headers, data=data)
    j = json.loads(json.loads(response.text)["d"])

    metrics = ''
    for car in j:
        car_no = car['car_no']
        metrics += f'trash_car_lon{{carno="{car_no}"}} {car["lon"]}\n'
        metrics += f'trash_car_lat{{carno="{car_no}"}} {car["lat"]}\n'
        metrics += f'trash_car_direction{{carno="{car_no}"}} {car["direction"]}\n'
        metrics += f'trash_car_direction{{carno="{car_no}"}} {car["direction"]}\n'
        metrics += '\n'

    return web.Response(text=metrics)

app = web.Application()
app.add_routes(routes)
web.run_app(app, host='0.0.0.0', port=8085)

# print(left < dt.now(tz=TZ()).timetz())
