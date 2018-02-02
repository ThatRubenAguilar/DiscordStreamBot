import threading
import asyncio
import time
from datetime import datetime, timedelta
import requests
from config import Config
import digitalocean as digio
from dropletapi import DropletApi
import logging
import traceback
import concurrent.futures
import backoff

class DropletActivityMonitor:
    def __init__(self, inactive_time_delta=timedelta(seconds=300), poll_delay_sec=60, loop=None):
        if inactive_time_delta is None:
            inactive_time_delta = timedelta(seconds=300)
        if poll_delay_sec is None:
            poll_delay_sec = 60

        self.__inactive_time_delta = inactive_time_delta
        self.__poll_delay_sec = poll_delay_sec
        self.__loop=loop if loop is not None else asyncio.get_event_loop()

    def start_monitoring(self, droplet, callback):
        loop = self.__loop
        task = loop.run_in_executor(None, self.__start_monitoring,
                                    droplet, callback, loop)

        asyncio.ensure_future(task, loop=loop)

    def __start_monitoring(self, droplet, callback, loop):
        asyncio.set_event_loop(loop)
        asyncio.run_coroutine_threadsafe(self.__start_monitoring_async(droplet, callback), loop=loop)

    async def start_monitoring_async(self, droplet, callback):
        return self.__start_monitoring_async(droplet, callback)

    def start_monitoring_no_wait(self, droplet, callback):
        loop = self.__loop
        coroutine = self.__start_monitoring_async(droplet, callback)

        asyncio.ensure_future(coroutine, loop=loop)

    async def __start_monitoring_async(self, droplet, callback):
        continue_loop = True
        try:
            while True:
                last_active_utc_raw = await self.get_last_active_time(droplet.ip_address)
                if last_active_utc_raw is not None:
                    last_active_utc_time = datetime.utcfromtimestamp(last_active_utc_raw)
                    now_utc = datetime.utcfromtimestamp(time.time())
                    delta_utc = now_utc - last_active_utc_time
                    print("checking for inactivity at {0} : delta {1}".format(now_utc, delta_utc))
                    if delta_utc > self.__inactive_time_delta:
                        continue_loop = await callback(last_active_utc_time, droplet)

                if not continue_loop:
                    break

                await asyncio.sleep(self.__poll_delay_sec)
        except Exception as e:
            tb = traceback.format_exc()
            logging.info("monitoring ended for droplet {0} due to {1} \n at {2}".format(droplet.name, e if len(e.args) == 0 else e.args[0], tb))
            pass

    @backoff.on_exception(backoff.expo, Exception, max_tries=5)
    async def get_last_active_time(self, ip):
        await asyncio.sleep(0)
        url = "http://{}/last_active_time".format(ip)
        r = requests.get(url)
        r.raise_for_status()
        json_obj = r.json()
        str_time = json_obj["last_active_time"]
        if str_time is not None:
            return float(str_time)
        return str_time

