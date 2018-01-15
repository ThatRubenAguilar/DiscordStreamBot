import discord
import asyncio
import dropletapi
import time
from config import Config
import digitalocean as digio
from dropletapi import DropletApi
from exception import LockedDropletException,MissingFirewallException,MissingSnapshotException, \
    MissingDropletException, UnauthorizedUserException, DropletBootFailedException

request_counter = 0
request_spam_threshold = 5
request_spam_reset_sec = 5.0
request_spam_reset_base_time = time.perf_counter()
timer_rollover_detection = -1000000000  # maxint / 2 ~
client = discord.Client()
config = Config("streambot.config")


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
    elif message.content.startswith('!stream help'):
        await stream_help(message)


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


def message_progress_callback(message):
    async def text_progress_callback(text):
        await client.send_message(message.channel, text)
    return text_progress_callback


async def turn_on_stream(message):
    request_received()
    if not await request_counter_overflow(message):
        try:
            if not check_user_role_authorized(message):
                raise UnauthorizedUserException("I'm sorry {}, I'm afraid I can't allow you to do that.".format(message.author.name))

            manager = digio.Manager(token=config.digital_ocean_api_key())
            callback = message_progress_callback(message)
            droplet = await DropletApi.create_or_get_single_droplet_from_snapshot(manager,
                                                                  config.default_tag_name(),
                                                                  config.default_snapshot_name(),
                                                                  config.default_firewall_name(),
                                                                  callback)

            await client.send_message(message.channel,
                                      "droplet {0} turned on, exists at ip {1}, \n" \
                                      "don't forget to turn it off when you're finished (!turn off stream) \n" \
                                      "stream publish url is rtmp://{1}:1935/publish/{{stream key}}?publish_key={{publish key}}\n" \
                                      "stream play url is rtmp://{1}:1935/live/{{stream key}}?play_key={2}"
                                      .format(droplet.name, droplet.ip_address, config.stream_play_key()))

        except UnauthorizedUserException as e:
            await client.send_message(message.channel, e.args[0])
        except LockedDropletException as e:
            await client.send_message(message.channel, e.args[0])
        except DropletBootFailedException as e:
            await client.send_message(message.channel, e.args[0])
        except MissingDropletException as e:
            await client.send_message(message.channel, e.args[0])
        except MissingSnapshotException as e:
            await client.send_message(message.channel, e.args[0])
        except MissingFirewallException as e:
            await client.send_message(message.channel, e.args[0])
        except Exception as e:
            await client.send_message(message.channel, "Unexcepted error: {}".format(e.args[0]))


async def turn_off_stream(message):
    request_received()
    if not await request_counter_overflow(message):
        try:
            if not check_user_role_authorized(message):
                raise UnauthorizedUserException("I'm sorry {}, I'm afraid I can't allow you to do that.".format(message.author.name))

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
                
        except UnauthorizedUserException as e:
            await client.send_message(message.channel, e.args[0])
        except Exception as e:
            await client.send_message(message.channel, "Unexcepted error: {}".format(e.args[0]))


async def stream_status(message):
    request_received()
    if not await request_counter_overflow(message):
        try:
            manager = digio.Manager(token=config.digital_ocean_api_key())
            droplet, statuses = DropletApi.check_single_droplet_status(manager, config.default_tag_name())
            status_names = ",".join([s.status for s in statuses])
            await client.send_message(message.channel,
                                      "droplet {0} exists at ip {1}, \n" \
                                      "stream publish url is rtmp://{1}:1935/publish/{{stream key}}?publish_key={{publish key}}\n" \
                                      "stream play url is rtmp://{1}:1935/live/{{stream key}}?play_key={3}\n" \
                                      "droplet's last status(es) are {2}"
                                      .format(droplet.name, droplet.ip_address, status_names, config.stream_play_key()))
        except MissingDropletException:
            await client.send_message(message.channel, "Stream is currently off, turn it on first! (!turn on stream)")
        except Exception as e:
            await client.send_message(message.channel, "Unexcepted error: {}".format(e.args[0]))


async def stream_help(message):
    request_received()
    if not await request_counter_overflow(message):
        try:
            await client.send_message(message.channel,
                                      "possible commands are: \n" \
                                      "!turn on stream \n" \
                                      "!turn off stream \n" \
                                      "!stream status")
        except Exception as e:
            await client.send_message(message.channel, "Unexcepted error: {}".format(e.args[0]))


if __name__ == '__main__':
    DropletApi.track_single_droplets()
    client.run(config.discord_api_key())
