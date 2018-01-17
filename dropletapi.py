import digitalocean as digio
from digitalocean.baseapi import NotFoundError
import threading
from config import Config
from exception import LockedDropletException, MissingFirewallException, MissingSnapshotException, \
    MissingDropletException, DropletBootFailedException
import asyncio


class DropletApi:
    __droplet_sem = threading.Semaphore()
    __existing_droplets = None

    @staticmethod
    def track_single_droplets():
        DropletApi.__existing_droplets = {}

    @staticmethod
    def check_existing_droplet(manager, tag_name):
        droplets = manager.get_all_droplets(tag_name=tag_name)
        if len(droplets) is 0:
            return None

        return droplets[0]

    @staticmethod
    def get_droplet_snapshot(manager, snapshot_name):
        snapshots = manager.get_all_snapshots()
        snapshot = [s for s in snapshots if s.name == snapshot_name]
        if len(snapshot) is 0:
            return None

        return snapshot[0]

    @staticmethod
    def get_droplet_firewall(manager, firewall_name):
        firewalls = manager.get_all_firewalls()
        firewall = [f for f in firewalls if f.name == firewall_name]
        if len(firewall) is 0:
            return None

        return firewall[0]

    @staticmethod
    def destroy_tagged_droplets(manager, tag_name):
        droplets = manager.get_all_droplets(tag_name=tag_name)

        for droplet in droplets:
            droplet.destroy()
            if DropletApi.__existing_droplets is not None and droplet.name in DropletApi.__existing_droplets:
                DropletApi.__existing_droplets.pop(droplet.name)

        return droplets

    @staticmethod
    def create_or_get_tag(manager, tag_name):
        tag = digio.Tag(token=manager.token, name=tag_name)
        try:
            tag.load()
        except NotFoundError:
            tag.create()

        print(manager.get_all_tags())
        print(tag.name)
        return tag

    @staticmethod
    def check_single_droplet_status(manager, tag_name):
        droplet = DropletApi.check_existing_droplet(manager, tag_name)
        if droplet is None:
            raise MissingDropletException("there are no droplets tagged with {}".format(tag_name))

        actions = droplet.get_actions()
        for action in actions:
            action.load()

        return droplet, actions

    @staticmethod
    async def __poll_existing_droplet_or_timeout(manager, tag_name, max_attempts=10, attempt_delay_sec=1):
        attempts = 0
        while attempts < max_attempts:
            await asyncio.sleep(attempt_delay_sec)
            droplet = DropletApi.check_existing_droplet(manager, tag_name)
            if droplet is not None:
                return droplet
            attempts += 1
        return None

    @staticmethod
    async def create_or_get_single_droplet_from_snapshot(manager, tag_name, snapshot_name, firewall_name=None,
                                                         progress_callback=None):
        droplet_name = "{}-{}".format(snapshot_name, tag_name)

        if not DropletApi.__droplet_sem.acquire(blocking=False):
            raise LockedDropletException("droplet {} is already being created.".format(droplet_name))
        try:
            droplet = DropletApi.check_existing_droplet(manager, tag_name)
            if droplet is not None:
                return droplet

            if DropletApi.__existing_droplets is not None and droplet_name in DropletApi.__existing_droplets:
                droplet = await DropletApi.__poll_existing_droplet_or_timeout(manager, tag_name)
                if droplet is not None:
                    return droplet
                raise MissingDropletException("droplet {} could not be located".format(droplet_name))

            snapshot = DropletApi.get_droplet_snapshot(manager, snapshot_name)
            if snapshot is None:
                raise MissingSnapshotException("snapshot {} is missing".format(snapshot_name))

            ssh_keys = manager.get_all_sshkeys()

            region_name = snapshot.regions[0]

            droplet = digio.Droplet(
                token=manager.token,
                name=droplet_name,
                region=region_name,
                image=snapshot.id,
                ssh_keys=ssh_keys,
                size_slug='2gb',
                tags=[tag_name]
            )

            if progress_callback is not None:
                await progress_callback("preparing to turn on droplet {}".format(droplet_name))

            if DropletApi.__existing_droplets is not None and droplet.name not in DropletApi.__existing_droplets:
                DropletApi.__existing_droplets[droplet.name] = droplet.name

            droplet.create()

            # tag = create_or_get_tag(tag_name)
            # if tag is None:
            #     return None #exception

            # tag.add_droplets([droplet.id])

            if firewall_name is not None:
                firewall = DropletApi.get_droplet_firewall(manager, firewall_name)
                if firewall is None:
                    raise MissingFirewallException("firewall {} is missing".format(firewall_name))
                firewall.add_droplets([droplet.id])

            actions = droplet.get_actions()
            complete = False
            final_status = "no-status"
            while not complete:
                for action in actions:
                    action.load()
                    # Once it shows complete, droplet is up and running
                    if action.status is not 'in-progress':
                        complete = True
                        final_status = action.status
                await asyncio.sleep(1)

            if final_status is "errored":
                raise DropletBootFailedException("droplet {} failed to turn on".format(droplet_name))

            droplet.load()

            return droplet

        finally:
            DropletApi.__droplet_sem.release()


if __name__ == '__main__':
    config = Config("streambot.config")
    manager = digio.Manager(token=config.digital_ocean_api_key())
    loop = asyncio.get_event_loop()
    created_droplet = loop.run_until_complete(
        DropletApi.create_or_get_single_droplet_from_snapshot(manager,
                                                              config.default_tag_name(),
                                                              config.default_snapshot_name(),
                                                              config.default_firewall_name()))
    print(created_droplet)
    pending = asyncio.Task.all_tasks()
    loop.run_until_complete(asyncio.gather(*pending))
    loop.close()
    # DropletApi.destroy_tagged_droplets(manager, config.default_tag_name())
