import argparse
import socket
import time

from nipyapi import config, versioning


def get_host_ip():
    host_name = ''
    while host_name == '':
        host_name = socket.gethostname()
        time.sleep(.5)
    return host_name


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('registry_name')
    parser.add_argument('registry_api_url')
    args = parser.parse_args()

    if args.registry_name and args.registry_api_url:
        config.nifi_config.host = 'http://{}:8080/nifi-api'.format(get_host_ip())
        description = 'Registry added from skinifi'
        versioning.create_registry_client(args.registry_name, args.registry_api_url, description)
