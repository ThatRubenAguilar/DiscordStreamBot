from collections import deque
import asyncio
import discord
import logging
import traceback
import threading

class MessagePump:
    def __init__(self, discord_client):
        self.__queue = deque()
        self.__discord_client = discord_client
        self.__is_closed = False
        self.__run_sem = threading.Semaphore()
        self.__future = None

    def start_pump(self):
        self.__is_closed = False
        with self.__run_sem:
            self.__queue.clear()
            loop = self.__discord_client.loop
            self.__future = asyncio.run_coroutine_threadsafe(self.__start_pump_async(loop), loop=loop)

    def stop_pump(self):
        self.__is_closed = True
        with self.__run_sem:
            self.__future.result()

    def add_message(self, channel, message):
        self.__queue.append((channel, message))

    async def __start_pump_async(self, loop):
        try:
            while not self.__is_closed:
                print("checking pump")
                if len(self.__queue) is 0:
                    print("pump sleep")
                    await asyncio.sleep(5, loop=loop)
                else:
                    while len(self.__queue) > 0:
                        print("pump msg")
                        channel, message = self.__queue.popleft()
                        await self.__discord_client.send_message(channel, message)
        except Exception as e:
            tb = traceback.format_exc()
            logging.error("messagepump ended due to {0} \n at {1}".format(e if len(e.args) == 0 else e.args[0], tb))
            pass
