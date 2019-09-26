import argparse
import glob
import json
import xml.etree.ElementTree as et
from os import listdir, remove, mkdir
from os.path import exists
from shutil import copyfile, rmtree, move
from zipfile import ZipFile

from docker import from_env

from nipyapi import registry as nifi_registry

# TODO: substitute hardcoded nifi version numbers with variable
# nar files essential to nifi running
ESSENTIAL_NARS = [
    'nifi-standard-nar-1.9.2.nar',
    'nifi-standard-services-api-nar-1.9.2.nar',
    'nifi-framework-nar-1.9.2.nar',
    'nifi-provenance-repository-nar-1.9.2.nar',
    'nifi-websocket-processors-nar-1.9.2.nar',
    'nifi-websocket-services-api-nar-1.9.2.nar',
    'nifi-websocket-services-jetty-nar-1.9.2.nar',
    'nifi-jetty-bundle-1.9.2.nar'
]

_IMAGE_DIR = 'skinifi-image/'
_CUSTOM_NAR_DIR = 'custom-processors/'

_skinny_nifi_zip_path = _IMAGE_DIR + 'skinny-nifi-1.9.2-bin.zip'
_generic_nars_path = _IMAGE_DIR + 'generic-nars.zip'


def _get_nars_from_templates():
    """
    @return list of nars used in template
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


# Recursively search for bundles in the flow's json
def _get_nars_from_json(d):
    if not isinstance(d, dict):
        return

    bundle = "bundle"
    nars = []
    for k, v in d.items():
        if k == bundle:
            name = v['artifact'] + '-' + v['version']
            nars.append(name + '.nar')
        elif isinstance(v, dict):
            nars.extend(_get_nars_from_json(v))
        elif isinstance(v, list):
            for i in list(filter(lambda i: isinstance(i, dict), v)):
                nars.extend(_get_nars_from_json(i))

    return nars


def _get_nars_from_registries():
    """
    @return list of nars used in nifi registries
    """
    registry_nars = []

    with open('registries.json', 'r') as f:
        registries_json = json.load(f)['registries']

        for index, registry in enumerate(registries_json):
            registry_name = registry['name'] or 'registry {}'.format(index + 1)
            base_url = registry['baseUrl']
            registry_api_url = base_url + "/nifi-registry-api"
            client = nifi_registry.api_client.ApiClient()

            for bucket in registry['buckets']:
                bucket_id = bucket['bucketId']
                for flow in bucket['flows']:
                    flow_id = flow['flowId']
                    versions = flow.get('versions', ['latest'])

                    for version in versions:
                        response = client.request('GET', '{}/buckets/{}/flows/{}/versions/{}'.format(
                            registry_api_url, bucket_id, flow_id, version))
                        flow_json = json.loads(response.data)

                        for nar in _get_nars_from_json(flow_json):
                            if nar not in registry_nars:
                                registry_nars.append(nar)

    return registry_nars


def build_skinifi_instance():
    """
    Create a zip of nifi with reduced artifacts to skinifi-image/skinny-nifi-1.9.2-bin.zip
    :return:
    """
    # find nars and delete duplicates
    required_nars = ESSENTIAL_NARS + _get_nars_from_templates() + _get_nars_from_registries()
    required_nars = list(dict.fromkeys(required_nars))

    copyfile(_IMAGE_DIR + '.skinny-nifi-1.9.2-bin.zip', _skinny_nifi_zip_path)

    generic_nars_zip = ZipFile(_generic_nars_path, mode='r')
    skinny_nifi_zip = ZipFile(_skinny_nifi_zip_path, mode='a')

    # path to lib within skinny nifi zipped folder
    skinny_nifi_lib_path = 'skinny-nifi-1.9.2/lib/'

    # a temporary directory for decompressed generic nars
    tmp_path = '.tmp/'

    for nar_filename in required_nars:
        # add nar file to skinny nifi instance
        if nar_filename in listdir(_CUSTOM_NAR_DIR):
            skinny_nifi_zip.write(_CUSTOM_NAR_DIR + nar_filename, skinny_nifi_lib_path + nar_filename)
        elif nar_filename in generic_nars_zip.namelist():
            generic_nars_zip.extract(nar_filename, path=tmp_path)
            skinny_nifi_zip.write(tmp_path + nar_filename, skinny_nifi_lib_path + nar_filename)
        else:
            print('nar file not found: {}'.format(nar_filename))

    if exists(tmp_path):
        rmtree(tmp_path)

    skinny_nifi_zip.close()
    generic_nars_zip.close()


def build_docker_image(tag='skinifi', target=False):
    """
    Create a skinifi docker image
    @param tag: the tag of the docker image (default is 'skinifi')
    @param target: create a target directory for the nifi instance and the docker image
    """
    build_skinifi_instance()
    print('Skinny nifi instance created\nCreating docker image...')

    # create docker image
    client = from_env()
    client.images.build(path=_IMAGE_DIR,  tag=tag)

    if target:
        target_path = 'target/'
        if exists(target_path):
            rmtree(target_path)
        mkdir(target_path)
        move(_skinny_nifi_zip_path, target_path)

    else:
        remove(_skinny_nifi_zip_path)


if __name__ == '__main__':
    # tag = 'skinifi'
    # target = False

    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--target',
                        help='keep created nifi instance in target/', action='store_true', default=False)
    parser.add_argument('-t', '--tag', type=str,
                        help='specify a tag for the docker image. Default is \'skinifi\'', default='skinifi')
    args = parser.parse_args()

    build_docker_image(tag=args.tag, target=args.target)
