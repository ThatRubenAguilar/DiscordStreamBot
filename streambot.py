import discord
import asyncio
import dropletapi
import sys
import logging
import time
import traceback
from config import Config
import digitalocean as digio
from dropletapi import DropletApi
from exception import LockedDropletException, MissingFirewallException, MissingSnapshotException, \
    MissingDropletException, UnauthorizedUserException, DropletBootFailedException, StreamBotException
from dropletactivitymonitor import DropletActivityMonitor

request_counter = 0
request_spam_threshold = 5
request_spam_reset_sec = 5.0
request_spam_reset_base_time = time.perf_counter()
timer_rollover_detection = -1000000000  # maxint / 2 ~
client = discord.Client()
config = Config("streambot.config")
server_activity_monitor = \
    DropletActivityMonitor(config.droplet_inactivity_delta(), config.droplet_inactivity_poll_sec(), loop=client.loop)


@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')


@client.event
async def on_message(message):
    if message.content.startswith('!turn on stream'):
        await call_authorized(turn_on_stream(message), message)
    elif message.content.startswith('!turn off stream'):
        await call_authorized(turn_off_stream(message), message)
    elif message.content.startswith('!stream status'):
        await call_unauthorized(stream_status(message), message)
    elif message.content.startswith('!stream help'):
        await call_unauthorized(stream_help(message), message)


def request_received():
    global request_counter
    request_counter += 1


async def request_counter_overflow(message):
    check_request_counter_reset()
    if request_counter > request_spam_threshold:
        await client.send_message(message.channel, 'Hold your horses, I''m doing stuff, but not for you... ば.. ばか!!')
        return True
    return False


def check_request_counter_reset():
    global request_spam_reset_base_time
    global request_counter
    delta_time = time.perf_counter() - request_spam_reset_base_time

    if delta_time > request_spam_reset_sec or delta_time < timer_rollover_detection:
        request_counter = 0
        request_spam_reset_base_time = time.perf_counter()


def check_user_role_authorized(message):
    # require they have the manage server permission
    author = message.author
    if isinstance(author, discord.User):
        user = message.author
        permissions = user.permissions_in(message.channel)
        if permissions.manage_server is True:
            return True

    elif isinstance(author, discord.Member):
        member = message.author
        for role in member.roles:
            if role.permissions.manage_server is True:
                return True

    return False


async def call_authorized(coroutine, message):
    request_received()
    if not await request_counter_overflow(message):
        try:
            if not check_user_role_authorized(message):
                raise UnauthorizedUserException(
                    "I'm sorry {}, I'm afraid I can't allow you to do that.".format(message.author.name))

            await coroutine
        except StreamBotException as e:
            await client.send_message(message.channel, e if len(e.args) == 0 else e.args[0])
        except Exception as e:
            await client.send_message(message.channel,
                                      "Unexcepted error: {}".format(e if len(e.args) == 0 else e.args[0]))


async def call_unauthorized(coroutine, message):
    request_received()
    if not await request_counter_overflow(message):
        try:
            await coroutine
        except StreamBotException as e:
            await client.send_message(message.channel, e if len(e.args) == 0 else e.args[0])
        except Exception as e:
            await client.send_message(message.channel,
                                      "Unexcepted error: {}".format(e if len(e.args) == 0 else e.args[0]))


def message_progress_callback(message):
    async def text_progress_callback(text):
        if not client.is_closed:
            await client.send_message(message.channel, text)

    return text_progress_callback


async def turn_on_stream(message):
    manager = digio.Manager(token=config.digital_ocean_api_key())
    callback = message_progress_callback(message)
    droplet = await DropletApi.create_or_get_single_droplet_from_snapshot(manager,
                                                                          config.default_tag_name(),
                                                                          config.default_snapshot_name(),
                                                                          config.default_firewall_name(),
                                                                          callback, server_activity_monitor)

    default_stream_key = config.default_stream_key()
    use_stream_key_line = default_stream_key is not "{stream key}"
    stream_key_line = ""
    if use_stream_key_line:
        stream_key_line = "stream key for publishing is '{}'\n".format(default_stream_key)

    await client.send_message(message.channel,
                              "droplet {0} turned on, exists at ip {1}, \n" \
                              "don't forget to turn it off when you're finished (!turn off stream) \n" \
                              "stream publish url is rtmp://{1}:1935/publish?publish_key={{publish key}}\n" \
                              "{4}" \
                              "stream play url is rtmp://{1}:1935/live/{3}?play_key={2}"
                              .format(droplet.name, droplet.ip_address, config.stream_play_key(),
                                      default_stream_key, stream_key_line))


async def turn_off_stream(message):
    manager = digio.Manager(token=config.digital_ocean_api_key())
    droplets = DropletApi.destroy_tagged_droplets(manager, config.default_tag_name())
    if len(droplets) is 0:
        await client.send_message(message.channel,
                                  "no droplets to turn off")
    else:
        droplet_names = ",".join([d.name for d in droplets])
        await client.send_message(message.channel,
                                  "droplet(s) {} turned off"
                                  .format(droplet_names))


async def stream_status(message):
    try:
        manager = digio.Manager(token=config.digital_ocean_api_key())
        droplet, statuses = DropletApi.check_single_droplet_status(manager, config.default_tag_name())
        status_names = ",".join([s.status for s in statuses])

        default_stream_key = config.default_stream_key()
        use_stream_key_line = default_stream_key is not "{stream key}"
        stream_key_line = ""
        if use_stream_key_line:
            stream_key_line = "stream key for publishing is '{}'\n".format(default_stream_key)

        await client.send_message(message.channel,
                                  "droplet {0} exists at ip {1}, \n" \
                                  "stream publish url is rtmp://{1}:1935/publish?publish_key={{publish key}}\n" \
                                  "{5}" \
                                  "stream play url is rtmp://{1}:1935/live/{4}?play_key={3}\n" \
                                  "droplet's last status(es) are {2}"
                                  .format(droplet.name, droplet.ip_address, status_names,
                                          config.stream_play_key(), default_stream_key, stream_key_line))
    except MissingDropletException:
        await client.send_message(message.channel, "Stream is currently off, turn it on first! (!turn on stream)")
        pass


async def stream_help(message):
    await client.send_message(message.channel,
                              "possible commands are: \n" \
                              "!turn on stream \n" \
                              "!turn off stream \n" \
                              "!stream status")

def start_loop(*args, **kwargs):
    try:
        asyncio.ensure_future(client.start(*args, **kwargs), loop=client.loop)
        client.loop.run_forever()
    except KeyboardInterrupt:
        finish_pending_tasks()
        pass
    except Exception:
        finish_pending_tasks(cancel=False)
        pass
    finally:
        client.loop.close()

def finish_pending_tasks(cancel=True):
    client.loop.run_until_complete(client.logout())
    pending = asyncio.Task.all_tasks(loop=client.loop)
    gathered = asyncio.gather(*pending, loop=client.loop)
    try:
        if cancel:
            gathered.cancel()
        client.loop.run_until_complete(gathered)

        # we want to retrieve any exceptions to make sure that
        # they don't nag us about it being un-retrieved.
        gathered.exception()
    except:
        pass



if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    logging.info("Starting streambot")
    client.loop.set_debug(True)
    #logging.getLogger('backoff').addHandler(logging.StreamHandler(stream=sys.stdout))
    DropletApi.track_single_droplets()
    while True:
        try:
            #client.run(config.discord_api_key())
            start_loop(config.discord_api_key())
        except KeyboardInterrupt:
            logging.info("Ending streambot")
            pass
        except Exception as e:
            tb = traceback.format_exc()
            logging.error("Main loop exception: {0} \n at {1}".format(e if len(e.args) == 0 else e.args[0], tb))
