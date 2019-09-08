import glob
import xml.etree.ElementTree as ET
from os import listdir, remove, mkdir
from os.path import exists
from shutil import copyfile, rmtree, move
import sys
from zipfile import ZipFile

from docker import from_env

# TODO: substitute hardcoded nifi version numbers with variable
# nar files essential to nifi running
essential_nars = [
    'nifi-standard-nar-1.9.2',
    'nifi-standard-services-api-nar-1.9.2',
    'nifi-framework-nar-1.9.2',
    'nifi-provenance-repository-nar-1.9.2',
    'nifi-websocket-processors-nar-1.9.2',
    'nifi-websocket-services-api-nar-1.9.2',
    'nifi-websocket-services-jetty-nar-1.9.2',
    'nifi-jetty-bundle-1.9.2'
]

_IMAGE_DIR = 'skinifi-image/'
_CUSTOM_NAR_DIR = "custom-processors/"

_whitelist_path = "./nar-whitelist.config"
_skinny_nifi_zip_path = _IMAGE_DIR + 'skinny-nifi-1.9.2-bin.zip'
_generic_nars_path = _IMAGE_DIR + "generic-nars.zip"

_skinny_nifi_lib_path = "skinny-nifi-1.9.2/lib/"

def _get_nars_from_templates():
    '''
    @return set of nars used in template
    '''
    whitelist = set(essential_nars)  # set to prevent duplicates

    for filepath in glob.glob('templates/*.xml'):
        print('adding nars from {}'.format(filepath))

        tree = ET.parse(filepath)
        root = tree.getroot()
        for bundle in root.iter('bundle'):
            nar = bundle.find('artifact').text

            version = bundle.find('version')
            if version is not None:
                nar += '-' + version.text

            if nar not in whitelist:
                whitelist.add(nar)

    return whitelist


def create_whitelist():
    '''
    Creates a .config file of nars needed for nifi
    '''
    # overwrite existing whitelist
    copyfile(".nar-whitelist.config", _whitelist_path)
    whitelist_file = open(_whitelist_path, "w")
    whitelist = _get_nars_from_templates()

    for nar in whitelist:
        whitelist_file.write(nar + '.nar\n')

    whitelist_file.close()


def _cleanup_nifi_instance_creation(tmp_path, skinny_nifi_zip, generic_nars_zip):
    if exists(tmp_path):
        rmtree(tmp_path)

    skinny_nifi_zip.close()
    generic_nars_zip.close()


def build_skinny_nifi_instance():
    whitelist = open(_whitelist_path, "r")
    copyfile(_IMAGE_DIR + ".skinny-nifi-1.9.2-bin.zip", _skinny_nifi_zip_path)

    generic_nars_zip = ZipFile(_generic_nars_path, mode='r')
    skinny_nifi_zip = ZipFile(_skinny_nifi_zip_path, mode='a')

    # path to lib within skinny nifi zipped folder
    _skinny_nifi_lib_path = "skinny-nifi-1.9.2/lib/"

    # a temporary directory for decompressed generic nars
    tmp_path = '.tmp/'

    for line in whitelist:
        nar_filename = line.strip()

        if len(nar_filename) > 0 and not nar_filename.startswith('#'):
            # add nar file to skinny nifi instance
            if nar_filename in listdir(_CUSTOM_NAR_DIR):
                skinny_nifi_zip.write(_CUSTOM_NAR_DIR + nar_filename, _skinny_nifi_lib_path + nar_filename)
            elif nar_filename in generic_nars_zip.namelist():
                generic_nars_zip.extract(nar_filename, path=tmp_path)
                skinny_nifi_zip.write(tmp_path + nar_filename, _skinny_nifi_lib_path + nar_filename)
            else:
                print("nar file not found: {}".format(nar_filename))
                _cleanup_nifi_instance_creation(tmp_path, skinny_nifi_zip, generic_nars_zip)
                exit()

    _cleanup_nifi_instance_creation(tmp_path, skinny_nifi_zip, generic_nars_zip)


def build_docker_image(tag='skinifi', target=False):
    '''
    Create a skinifi docker image
    @param tag: the tag of the docker image (default is 'skinifi')
    @param target: create a target directory for the nifi instance and the docker image
    '''

    create_whitelist()
    print('Created whitelist\nAdding nar files to skinny nifi instance...')
    build_skinny_nifi_instance()
    print('Skinny nifi instance created')

    # create docker image
    client = from_env()
    client.images.build(path=_IMAGE_DIR,  tag=tag)

    if target:
        remove(_skinny_nifi_zip_path)
        remove(_whitelist_path)
    else:
        target_path = 'target/'
        if exists(target_path):
            rmtree(target_path)
        mkdir(target_path)
        move(_skinny_nifi_zip_path, target_path)
        move(_whitelist_path, target_path)


tag = sys.argv[1] if sys.argv[1] else None
target = sys.argv[2] if sys.argv[2] else False
build_docker_image(tag=tag, target=target)
