import configparser
import time
import datetime


class Config:
    def __init__(self, file_path=None, config_refresh_time_sec=None):
        self.__parser = None
        self.__parser_file_path=file_path
        self.__config_refresh_time_threshold=config_refresh_time_sec
        self.__config_refresh_base_time=None
        self.__default_tag_name=None
        self.__default_snapshot_name=None
        self.__default_firewall_name=None
        self.__digital_ocean_api_key=None
        self.__discord_api_key=None
        self.__stream_play_key=None
        self.__default_stream_key=None
        self.__droplet_inactivity_delta_sec=None
        self.__droplet_inactivity_poll_sec=None

        if file_path is not None:
            self.__config_refresh_base_time=time.perf_counter()
            self.__parser = configparser.ConfigParser()
            self.__populate_from_parser()

    def __populate_from_parser(self):
        parser = self.__parser
        file_path = self.__parser_file_path
        parser.read(file_path)
        self.__default_tag_name=parser.get("Droplet", "DefaultTagName", fallback=None)
        self.__default_snapshot_name=parser.get("Droplet", "DefaultSnapshotName", fallback=None)
        self.__default_firewall_name=parser.get("Droplet", "DefaultFirewallName", fallback=None)
        self.__digital_ocean_api_key=parser.get("ApiKey", "DigitalOceanApiKey", fallback=None)
        self.__discord_api_key=parser.get("ApiKey", "DiscordApiKey", fallback=None)
        self.__stream_play_key=parser.get("StreamPlayKey", "PlayKey", fallback="{play key}")
        self.__default_stream_key=parser.get("StreamPlayKey", "DefaultStreamKey", fallback="{stream key}")
        self.__droplet_inactivity_delta_sec=parser.get("Droplet", "DropletInactivityDelta", fallback=None)
        self.__droplet_inactivity_poll_sec=parser.get("Droplet", "DropletInactivityPollDelaySec", fallback=None)

    def __check_for_config_refresh(self):
        if self.__config_refresh_time_threshold is not None and \
                self.__parser is not None and \
                self.__config_refresh_base_time - time.perf_counter() > self.__config_refresh_time_threshold:
            self.__config_refresh_base_time = time.perf_counter()
            self.__populate_from_parser()

    def default_tag_name(self):
        self.__check_for_config_refresh()
        return self.__default_tag_name

    def default_snapshot_name(self):
        self.__check_for_config_refresh()
        return self.__default_snapshot_name

    def default_firewall_name(self):
        self.__check_for_config_refresh()
        return self.__default_firewall_name

    def digital_ocean_api_key(self):
        self.__check_for_config_refresh()
        return self.__digital_ocean_api_key

    def discord_api_key(self):
        self.__check_for_config_refresh()
        return self.__discord_api_key

    def stream_play_key(self):
        self.__check_for_config_refresh()
        return self.__stream_play_key

    def default_stream_key(self):
        self.__check_for_config_refresh()
        return self.__default_stream_key

    def droplet_inactivity_delta(self):
        self.__check_for_config_refresh()
        if self.__droplet_inactivity_delta_sec is None:
            return self.__droplet_inactivity_delta_sec
        return datetime.timedelta(seconds=float(self.__droplet_inactivity_delta_sec))

    def droplet_inactivity_poll_sec(self):
        self.__check_for_config_refresh()
        if self.__droplet_inactivity_poll_sec is None:
            return self.__droplet_inactivity_poll_sec
        return float(self.__droplet_inactivity_poll_sec)
