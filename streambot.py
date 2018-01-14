import discord
import asyncio
import dropletapi
import time
from config import Config
import digitalocean as digio
from dropletapi import DropletApi
from exception import LockedDropletException,MissingFirewallException,MissingSnapshotException, MissingDropletException

request_counter = 0
request_spam_threshold = 5
request_spam_reset_sec = 5.0
request_spam_reset_base_time = time.perf_counter()
timer_rollover_detection = -1000000000  # maxint / 2 ~
client = discord.Client()
config = Config("streambot.config")


def get_default_discord_bot_token():
    return ""


@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')


@client.event
async def on_message(message):
    if message.content.startswith('!turn on stream'):
        await turn_on_stream(message)
    elif message.content.startswith('!turn off stream'):
        await turn_off_stream(message)
    elif message.content.startswith('!stream status'):
        await stream_status(message)


async def request_counter_overflow(message):
    check_request_counter_reset()
    if request_counter > request_spam_threshold:
        await client.send_message(message.channel, 'Hold your horses, I''m doing stuff, but not for you... ば.. ばか!!')
        return True
    return False


def check_request_counter_reset():
    global request_spam_reset_base_time
    global request_counter
    delta_time = time.perf_counter() - request_spam_reset_base_time;
    if delta_time > request_spam_reset_sec or delta_time < timer_rollover_detection:
        request_counter = 0
        request_spam_reset_base_time = time.perf_counter()


async def turn_on_stream(message):
    if not await request_counter_overflow(message):
        try:
            manager = digio.Manager(token=config.digital_ocean_api_key())
            droplet = DropletApi.create_or_get_single_droplet_from_snapshot(manager,
                                                                  config.default_tag_name(),
                                                                  config.default_snapshot_name(),
                                                                  config.default_firewall_name())

            await client.send_message(message.channel,
                                      "droplet {0} turned on, exists at ip {1}, \n" \
                                      "don't forget to turn it off when you're finished (!turn off stream) \n" \
                                      "stream publish url is rtmp://{1}:1935/publish/{{stream key}}?publish_key={{publish key}}\n" \
                                      "stream play url is rtmp://{1}:1935/live/{{stream key}}?play_key={{play key}}"
                                      .format(droplet.name, droplet.ip_address))
        except LockedDropletException as e:
            await client.send_message(message.channel, e.args[0])
        except MissingSnapshotException as e:
            await client.send_message(message.channel, e.args[0])
        except MissingFirewallException as e:
            await client.send_message(message.channel, e.args[0])
        except Exception as e:
            await client.send_message(message.channel, "Unexcepted error: {}", e.args[0])


async def turn_off_stream(message):
    if not await request_counter_overflow(message):
        try:
            manager = digio.Manager(token=config.digital_ocean_api_key())
            droplets = DropletApi.destroy_tagged_droplets(manager, config.default_tag_name())
            droplet_names = ",".join([d.name for d in droplets])
            await client.send_message(message.channel,
                                      "droplet(s) {} turned off"
                                      .format(droplet_names))
        except Exception as e:
            await client.send_message(message.channel, "Unexcepted error: {}", e.args[0])


async def stream_status(message):
    if not await request_counter_overflow(message):
        try:
            manager = digio.Manager(token=config.digital_ocean_api_key())
            droplet, statuses = DropletApi.check_single_droplet_status(manager, config.default_tag_name())
            status_names = ",".join([s.status for s in statuses])
            await client.send_message(message.channel,
                                      "droplet {0} is turned on, exists at ip {1}, \n" \
                                      "stream publish url is rtmp://{1}:1935/publish/{{stream key}}?publish_key={{publish key}}\n" \
                                      "stream play url is rtmp://{1}:1935/live/{{stream key}}?play_key={{play key}}\n" \
                                      "droplet's last status(es) are {2}"
                                      .format(droplet.name, droplet.ip_address, status_names))
        except MissingDropletException:
            await client.send_message(message.channel, "Stream is currently off, turn it on first! (!turn on stream)")
        except Exception as e:
            await client.send_message(message.channel, "Unexcepted error: {}", e.args[0])


def async_test():
    global request_counter
    loop = asyncio.get_event_loop()
    #r = loop.run_until_complete(check_request_counter_overflow(None))
    r = request_counter_overflow(None)
    print(r)
    print(request_counter)
    print(request_spam_reset_base_time)
    request_counter = 6
    r = request_counter_overflow(None)
    print(r)
    print(request_counter)
    print(request_spam_reset_base_time)
    time.sleep(6)
    r = request_counter_overflow(None)
    print(r)
    print(request_counter)
    print(request_spam_reset_base_time)
    r = request_counter_overflow(None)
    print(r)
    print(request_counter)
    print(request_spam_reset_base_time)
    pending = asyncio.Task.all_tasks()
    loop.run_until_complete(asyncio.gather(*pending))
    loop.close()


if __name__ == '__main__':
    # client.run(get_default_discord_bot_token())
    client.close()
    async_test()
