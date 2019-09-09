import glob
import xml.etree.ElementTree as ET
from os import listdir, remove, mkdir
from os.path import exists
from shutil import copyfile, rmtree, move
import sys, getopt
from zipfile import ZipFile

from docker import from_env

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
    '''
    @return list of nars used in template
    '''
    required_nars = ESSENTIAL_NARS

    for filepath in glob.glob('templates/*.xml'):
        print('adding nars from {}'.format(filepath))

        tree = ET.parse(filepath)
        root = tree.getroot()
        for bundle in root.iter('bundle'):
            nar = bundle.find('artifact').text

            version = bundle.find('version')
            if version is not None:
                nar += '-' + version.text + '.nar'

            if nar not in required_nars:
                required_nars.append(nar)

    return required_nars


def _cleanup_nifi_instance_creation(tmp_path, skinny_nifi_zip, generic_nars_zip):
    if exists(tmp_path):
        rmtree(tmp_path)

    skinny_nifi_zip.close()
    generic_nars_zip.close()


def build_skinny_nifi_instance():
    required_nars = _get_nars_from_templates()
    copyfile(_IMAGE_DIR + '.skinny-nifi-1.9.2-bin.zip', _skinny_nifi_zip_path)

    generic_nars_zip = ZipFile(_generic_nars_path, mode='r')
    skinny_nifi_zip = ZipFile(_skinny_nifi_zip_path, mode='a')

    # path to lib within skinny nifi zipped folder
    _skinny_nifi_lib_path = 'skinny-nifi-1.9.2/lib/'

    # a temporary directory for decompressed generic nars
    tmp_path = '.tmp/'

    for nar_filename in required_nars:
        # add nar file to skinny nifi instance
        if nar_filename in listdir(_CUSTOM_NAR_DIR):
            skinny_nifi_zip.write(_CUSTOM_NAR_DIR + nar_filename, _skinny_nifi_lib_path + nar_filename)
        elif nar_filename in generic_nars_zip.namelist():
            generic_nars_zip.extract(nar_filename, path=tmp_path)
            skinny_nifi_zip.write(tmp_path + nar_filename, _skinny_nifi_lib_path + nar_filename)
        else:
            print('nar file not found: {}'.format(nar_filename))
            _cleanup_nifi_instance_creation(tmp_path, skinny_nifi_zip, generic_nars_zip)
            exit()

    _cleanup_nifi_instance_creation(tmp_path, skinny_nifi_zip, generic_nars_zip)


def build_docker_image(tag='skinifi', target=False):
    '''
    Create a skinifi docker image
    @param tag: the tag of the docker image (default is 'skinifi')
    @param target: create a target directory for the nifi instance and the docker image
    '''
    build_skinny_nifi_instance()
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


def main(argv):
    tag = 'skinifi'
    target = False
    try:
        opts, args = getopt.getopt(argv, 'hot:', ['help', 'target', 'tag='])
    except getopt.GetoptError:
        print('Invalid arguments: create_skinifi.py -o -t <tag_name>')
        sys.exit(2)

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print('create_skinifi.py --target --tag=my_skinifi')
        elif opt in ('-o', '--target'):
            target = arg
        elif opt in ('-t', '--tag'):
            tag = arg

    build_docker_image(tag=tag, target=target)


if __name__ == '__main__':
   main(sys.argv[1:])
