import digitalocean as digio
from digitalocean.baseapi import NotFoundError
import threading
from config import Config
from exception import LockedDropletException, MissingFirewallException, MissingSnapshotException, MissingDropletException


class DropletApi:
    __droplet_sem = threading.Semaphore()

    @staticmethod
    def check_existing_droplet(manager, tag_name):
        droplets = manager.get_all_droplets(tag_name=tag_name)
        if len(droplets) is 0:
            return None

        print(droplets)
        return droplets[0]

    @staticmethod
    def get_droplet_snapshot(manager, snapshot_name):
        snapshots = manager.get_all_snapshots()
        snapshot = [s for s in snapshots if s.name == snapshot_name]
        if len(snapshot) is 0:
            return None

        print(snapshots)
        return snapshot[0]

    @staticmethod
    def get_droplet_firewall(manager, firewall_name):
        firewalls = manager.get_all_firewalls()
        firewall = [f for f in firewalls if f.name == firewall_name]
        if len(firewall) is 0:
            return None

        print(firewalls)
        return firewall[0]

    @staticmethod
    def destroy_tagged_droplets(manager, tag_name):
        droplets = manager.get_all_droplets(tag_name)
        print(droplets)
        for droplet in droplets:
            droplet.destroy()

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
    def create_or_get_single_droplet_from_snapshot(manager, tag_name, snapshot_name, firewall_name=None):
        droplet_name = "{}-{}".format(snapshot_name, tag_name)
        if not DropletApi.__droplet_sem.acquire(blocking=False):
            raise LockedDropletException("droplet {} is already being created.".format(droplet_name))
        try:
            droplet = DropletApi.check_existing_droplet(manager, tag_name)
            if droplet is not None:
                return droplet

            snapshot = DropletApi.get_droplet_snapshot(manager, snapshot_name)
            if snapshot is None:
                raise MissingSnapshotException("snapshot {} is missing".format(snapshot_name))

            ssh_keys = manager.get_all_sshkeys()
            print(ssh_keys)

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

            print(droplet)
            droplet.create()

            print(droplet)

            # tag = create_or_get_tag(tag_name)
            # if tag is None:
            #     return None #exception

            # tag.add_droplets([droplet.id])

            if firewall_name is not None:
                firewall = DropletApi.get_droplet_firewall(manager, firewall_name)
                if firewall is None:
                    raise MissingFirewallException("firewall {} is missing".format(firewall_name))
                firewall.add_droplets([droplet.id])

            # make async and send note only if there's trouble
            # actions = droplet.get_actions()
            # complete = False
            # while not complete:
            #     for action in actions:
            #         action.load()
            #         # Once it shows complete, droplet is up and running
            #         print(action.status)
            #         if action.status == 'completed':
            #             complete = True

            return droplet

        finally:
            DropletApi.__droplet_sem.release()


if __name__ == '__main__':
    config = Config("streambot.config")
    manager = digio.Manager(token=config.digital_ocean_api_key())
    manager.token
    # created_droplet = create_or_get_single_droplet_from_snapshot(manager,
    #     config.default_tag_name(), config.default_snapshot_name(), config.default_firewall_name())
    # print(created_droplet)
    DropletApi.destroy_tagged_droplets(manager, None)
