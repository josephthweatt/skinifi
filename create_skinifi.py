import argparse
import glob
import json
import requests
import validators
import xml.etree.ElementTree as et
from os import remove, mkdir
from os.path import exists
from shutil import copyfile, rmtree, move
from zipfile import ZipFile

from docker import from_env

from nipyapi import registry as nifi_registry

NIFI_VERSION = '1.9.2'

# TODO: substitute hardcoded nifi version numbers with variable
# nar files essential to nifi running
ESSENTIAL_NARS = [
    'nifi-standard-nar-{}.nar'.format(NIFI_VERSION),
    'nifi-standard-services-api-nar-{}.nar'.format(NIFI_VERSION),
    'nifi-framework-nar-{}.nar'.format(NIFI_VERSION),
    'nifi-provenance-repository-nar-{}.nar'.format(NIFI_VERSION),
    'nifi-websocket-processors-nar-{}.nar'.format(NIFI_VERSION),
    'nifi-websocket-services-api-nar-{}.nar'.format(NIFI_VERSION),
    'nifi-websocket-services-jetty-nar-{}.nar'.format(NIFI_VERSION),
    'nifi-jetty-bundle-{}.nar'.format(NIFI_VERSION)
]

DEFAULT_GENERIC_URL = 'https://nifi-default-artifacts.s3.amazonaws.com/'

_IMAGE_DIR = 'skinifi-image/'
_CUSTOM_NAR_DIR = 'custom-processors/'
_SAVED_GENERIC_NAR_PATH = _IMAGE_DIR + 'generic-nars/'
_SKINNY_NIFI_ZIP_PATH = _IMAGE_DIR + 'skinny-nifi-1.9.2-bin.zip'


def _get_nars_from_templates():
    """
    :return: list of nars used in template
    """
    template_nars = []

    for filepath in glob.glob('templates/*.xml'):
        print('adding nars from {}'.format(filepath))

        tree = et.parse(filepath)
        root = tree.getroot()
        for bundle in root.iter('bundle'):
            nar = bundle.find('artifact').text

            version = bundle.find('version')
            if version is not None:
                nar += '-' + version.text
            nar += '.nar'

            if nar not in template_nars:
                template_nars.append(nar)

    return template_nars


class Nar:

    def __init__(self, artifact, group, version, api_url=None, bucket_name=None):
        self.artifact = artifact
        self.group = group
        self.version = version
        self.api_url = api_url
        self.bucket_name = bucket_name

    def get_filename(self):
        return self.artifact + '-' + self.version + '.nar'

    def set_bundle_info(self, api_url, bucket_name):
        self.api_url = api_url
        self.bucket_name = bucket_name

    def has_bundle_info(self):
        return bool(self.api_url and self.bucket_name)


def _get_nars_from_json(d):
    """
    Recursively search for bundles in the flow's json
    :param d: dict containing json
    :return: list of nar objects
    """
    if not isinstance(d, dict):
        return

    bundle = "bundle"
    nars = []
    for k, v in d.items():
        if k == bundle:
            nar = Nar(v['artifact'], v['group'], v['version'])
            nars.append(nar)
        elif isinstance(v, dict):
            nars.extend(_get_nars_from_json(v))
        elif isinstance(v, list):
            for i in list(filter(lambda i: isinstance(i, dict), v)):
                nars.extend(_get_nars_from_json(i))

    return nars


def _get_nars_from_registries():
    """
    :return: list of Nars used in nifi registries.
    """
    registry_nars = {}

    with open('registries.json', 'r') as f:
        registries_json = json.load(f)['registries']

        for index, registry in enumerate(registries_json):
            base_url = registry['baseUrl']
            reg_api_url = base_url + "/nifi-registry-api"
            client = nifi_registry.api_client.ApiClient()
            use_bundles = registry['useBundles']

            for bucket in registry['buckets']:
                bucket_id = bucket['bucketId']
                for flow in bucket['flows']:
                    flow_id = flow['flowId']
                    versions = flow.get('versions', ['latest'])

                    for version in versions:
                        response = client.request('GET', '{}/buckets/{}/flows/{}/versions/{}'.format(
                            reg_api_url, bucket_id, flow_id, version))
                        flow_json = json.loads(response.data)
                        bucket_name = flow_json['bucket']['name']

                        for nar in _get_nars_from_json(flow_json):
                            nar_filename = nar.get_filename()
                            if nar_filename not in registry_nars:
                                if use_bundles:
                                    nar.set_bundle_info(reg_api_url, bucket_name)
                                registry_nars[nar_filename] = nar

    return registry_nars.values()


def build_skinifi_instance(generic_nars_path=DEFAULT_GENERIC_URL, custom_nars_path=_CUSTOM_NAR_DIR):
    """
    Create a zip of nifi with reduced artifacts to skinifi-image/skinny-nifi-1.9.2-bin.zip
    :param generic_nars_path: str - url or path to copy generic nars
    :param custom_nars_path: str - url or path to copy custom nars
    :return:
    """
    generic_nars_path += '/' if not generic_nars_path.endswith('/') else ''
    custom_nars_path += '/' if not custom_nars_path.endswith('/') else ''

    # path to lib within skinny nifi zipped folder
    skinny_nifi_lib_path = 'skinny-nifi-1.9.2/lib/'

    if not exists(_SAVED_GENERIC_NAR_PATH):
        mkdir(_SAVED_GENERIC_NAR_PATH)

    # a temporary directory for downloaded custom nars
    tmp_path = '.tmp/'
    if not exists(tmp_path):
        mkdir(tmp_path)

    # find nars and delete duplicates
    nars_from_registry = _get_nars_from_registries()
    bundled_nars = list(filter(lambda n: n.has_bundle_info(), nars_from_registry))
    unbundled_nars = list(filter(lambda n: n.get_filename() if not n.has_bundle_info() else None, nars_from_registry))
    unbundled_nars += ESSENTIAL_NARS + _get_nars_from_templates()
    unbundled_nars = list(dict.fromkeys(unbundled_nars))

    copyfile(_IMAGE_DIR + '.skinny-nifi-1.9.2-bin.zip', _SKINNY_NIFI_ZIP_PATH)
    skinny_nifi_zip = ZipFile(_SKINNY_NIFI_ZIP_PATH, mode='a')

    # add nar files from nifi registry to skinifi instance
    for nar in bundled_nars:
        nar_filename = nar.get_filename()
        print("getting {}".format(nar_filename))

        bundle_content_endpoint = '{}/extension-repository/{}/{}/{}/{}/content'\
            .format(nar.api_url, nar.bucket_name, nar.group, nar.artifact, nar.version)
        r = requests.get(bundle_content_endpoint, allow_redirects=True)
        if r.status_code == 200:
            tmp_nar_filepath = tmp_path + nar_filename
            open(tmp_nar_filepath, 'wb').write(r.content)
            skinny_nifi_zip.write(tmp_nar_filepath, skinny_nifi_lib_path + nar_filename)

    # add nar files to skinifi instance
    for nar_filename in unbundled_nars:
        custom_nar_filepath = custom_nars_path + nar_filename
        saved_generic_nar_filepath = _SAVED_GENERIC_NAR_PATH + nar_filename
        generic_nar_filepath = generic_nars_path + nar_filename
        target_filepath = skinny_nifi_lib_path + nar_filename

        if target_filepath in skinny_nifi_zip.namelist():
            continue

        if exists(custom_nar_filepath):
            skinny_nifi_zip.write(custom_nar_filepath, target_filepath)

        elif exists(saved_generic_nar_filepath):
            skinny_nifi_zip.write(saved_generic_nar_filepath, target_filepath)

        elif validators.url(custom_nar_filepath):
            r = requests.get(custom_nar_filepath, allow_redirects=True)
            if r.status_code == 200:
                tmp_nar_filepath = tmp_path + nar_filename
                open(tmp_nar_filepath, 'wb').write(r.content)
                skinny_nifi_zip.write(tmp_nar_filepath, target_filepath)

        elif validators.url(generic_nar_filepath):
            r = requests.get(generic_nar_filepath, allow_redirects=True)
            if r.status_code == 200:
                # download and save nars into a directory to avoid re-downloading
                open(saved_generic_nar_filepath, 'wb').write(r.content)
                skinny_nifi_zip.write(saved_generic_nar_filepath, target_filepath)

        else:
            print('nar file not found: {}'.format(nar_filename))

    if exists(tmp_path):
        rmtree(tmp_path)

    skinny_nifi_zip.close()


def build_docker_image(generic_nar_path=DEFAULT_GENERIC_URL, custom_nar_path=_CUSTOM_NAR_DIR, tag='skinifi', target=False):
    """
    Create a skinifi docker image
    :param generic_nar_path: str - a directory to include generic nars from. Can be a url or a filepath
    :param custom_nar_path: str - a directory to include custom nars from. Can be a url or a filepath
    :param tag: str - the tag of the docker image (default is 'skinifi')
    :param target: bool - create a target directory for the nifi instance and the docker image
    """

    if custom_nar_path:
        build_skinifi_instance(generic_nar_path, custom_nar_path)
    else:
        build_skinifi_instance(generic_nar_path)

    print('Skinny nifi instance created\nCreating docker image...')

    # create docker image
    client = from_env()
    client.images.build(path=_IMAGE_DIR,  tag=tag)

    if target:
        target_path = 'target/'
        if exists(target_path):
            rmtree(target_path)
        mkdir(target_path)
        move(_SKINNY_NIFI_ZIP_PATH, target_path)

    else:
        remove(_SKINNY_NIFI_ZIP_PATH)


if __name__ == '__main__':
    # tag = 'skinifi'
    # target = False

    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--target',
                        help='Keep created nifi instance in target/', action='store_true', default=False)
    parser.add_argument('-t', '--tag', type=str,
                        help='Specify a tag for the docker image. Default is \'skinifi\'', default='skinifi')
    parser.add_argument('-gd', '--generic-nar-directory', type=str,
                        help='Specify a directory to include generic nars from. Can be a url or a path, by default '
                             'nars will be downloaded from an existing repo and saved to {}'
                        .format(_SAVED_GENERIC_NAR_PATH),
                        default=DEFAULT_GENERIC_URL)
    parser.add_argument('-cd', '--custom-nar-directory', type=str,
                        help='Specify a directory to include custom nars from. Can be a url or a path, by default {} '
                             'will be searched for custom nars'
                        .format(_CUSTOM_NAR_DIR),
                        default=_CUSTOM_NAR_DIR)

    args = parser.parse_args()

    bad_args = False

    # Validate arguments
    if not validators.url(args.custom_nar_directory) and not exists(args.custom_nar_directory):
        print('ERROR: Invalid custom nar directory')
        bad_args = True

    if not validators.url(args.generic_nar_directory) and not exists(args.generic_nar_directory):
        print('ERROR: Invalid generic nar directory')
        bad_args = True

    if bad_args:
        exit()

    build_docker_image(tag=args.tag, generic_nar_path=args.generic_nar_directory,
                       custom_nar_path=args.custom_nar_directory, target=args.target)
