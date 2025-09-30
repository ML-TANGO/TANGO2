"""Functions using docker registry REST APIs"""
import requests
import traceback
import sys
from utils import settings
from utils.settings import *

import utils.common as common
from utils.exceptions import *

#  InsecureRequestWarning 에러 처리
import urllib3
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
urllib3.disable_warnings()

CATALOG_PATH = '/v2/_catalog'
TAG_LIST_PATH_SKEL = '/v2/{repository}/tags/list'
MANIFEST_BYTAG_PATH_SKEL = '/v2/{repository}/manifests/{tag}'
MANIFEST_BYDIGEST_PATH_SKEL = '/v2/{repository}/manifests/{digest}'

DOCKER_REGISTRY_CONTAINER = 'JFB-Docker-REGISTRY'
DOCKER_REGISTRY_DIR = '/var/lib/registry/docker/registry/v2/repositories'



# TODO address -> pod config REGISTRY_SVC_DNS:PORT 변경필요

def _regularize_address(address):
    """
    input : 192.168.x.x:5000
    return : https://192.168.x.x:5000
    """
    if address.endswith('/'):
        address = address[:-1] #remove trailing slashs

    if address.startswith(DOCKER_REGISTRY_PROTOCOL):
        return address

    address = DOCKER_REGISTRY_PROTOCOL + address
    return address

def _parse_real_name_to_registry_arg(real_name):
    """
    input : 192.168.x.x:5000/jfb/by...-.../k4Z3uD
    return
        {
            "address" : 192.168.x.x:5000
            "repository" : jfb/by...-...
            "tag" : k4Z3uD
        }
    """
    try:
        address = real_name.split("/")[0]
        tag = real_name.split(":")[-1]
        repository = real_name.replace(address, "").replace(tag, "")[1:-1] # 맨 앞(/), 맨 뒤(:) 제거
        return {"address" : address, "repository" : repository, "tag" : tag}
    except:
        traceback.print_exc()

# curl -s -X GET http://127.0.0.1:5000/v2/_catalog | jq .repositories
# curl -s -X GET https://127.0.0.1:5000/v2/_catalog --insecure
def get_registry_repositories(address):
    """Get a list of installed repositories in docker registry.

    :param address: url of scheme, ip, port

    Example:
    address = 'http://192.168.1.13:5000'
    repositories = get_registry_repositories(address)
    return : list
    """

    address = _regularize_address(address)

    repositories = None
    catalog_address = address + CATALOG_PATH

    res = requests.get(catalog_address, verify=False, timeout=15)
    if res.ok:
        try:
            repositories = res.json()['repositories']
        except ValueError as e:
            traceback.print_exc()
            sys.stderr.write('GET {} returned "{}"\n'.format(catalog_address, res.text))
        except KeyError as e:
            traceback.print_exc()
        except:
            traceback.print_exc()
    else:
        status_code = res.status_code
        sys.stderr.write('GET {} returned {}\n'.format(catalog_address, status_code))

    return repositories


# curl -s -X GET http://127.0.0.1:5000/v2/jfb/bybuild-workspace1-mytest01/tags/list | jq .tags
# curl -s -X GET https://127.0.0.1:5000/v2/{repository}/tags/list --insecure
def get_registry_repository_tags(address, repository):
    """Get a list of tags of a repository in docker registry.

    :param address: url of scheme, ip, port
    :param repository: image name without ip, port, tag.

    Example:
    address = 'http://192.168.1.13:5000'
    repository = 'jfb/bybuild-workspace1-mytest01'
    tags = get_registry_repository_tags(address, repository)
    """
    address = _regularize_address(address)

    tags = None
    tag_list_address = address + TAG_LIST_PATH_SKEL.format(repository=repository)
    res = requests.get(tag_list_address, verify=False, timeout=15)

    if res.ok:
        try:
            tags = res.json()['tags']
        except ValueError as e:
            traceback.print_exc()
            # sys.stderr.write('GET {} returned "{}"\n'.format(tag_list_address, res.text))
            return False
        except KeyError as e:
            traceback.print_exc()
            return False
        except:
            traceback.print_exc()
            return False
    else:
        # status_code = res.status_code
        # sys.stderr.write('GET {} returned {}\n'.format(tag_list_address, status_code))
        return False

    return tags

# curl -H "Accept: application/vnd.docker.distribution.manifest.v2+json" https://192.168.1.11:5000/v2/{repository}/manifests/{tag} --insecure
def get_registry_image_size(address=None, repository=None, tag=None, real_name=None):
    """
    :param address: url of registry server.           Ex) http://192.168.1.13:5000
    :param repository: image name with ip, port, tag  Ex) jfb/bybuild-workspace1-mytest01
    :param tag: tag of image.                         Ex) eT2TfzP15I4sFLeL

    return byte
    """
    # check the address
    if real_name:
        arg = _parse_real_name_to_registry_arg(real_name=real_name)
        address = arg["address"]
        repository = arg["repository"]
        tag = arg["tag"]
    address = _regularize_address(address)

    # Get manifest.
    manifest_bytag_address = address+MANIFEST_BYTAG_PATH_SKEL.format(repository=repository, tag=tag)
    headers = {'Accept': 'application/vnd.docker.distribution.manifest.v2+json'}
    get_data = requests.get(manifest_bytag_address, headers=headers, verify=False, timeout=15).json()

    # parsing size
    size = 0
    for data in get_data:
        if data == "config":
            size += int(get_data[data]["size"])

        elif data == "layers":
            for i in get_data["layers"]:
                # print(i)
                size += int(i["size"])
    return size

# digets (v 옵션 필요, -> Docker-Content-Digest 확인)
# curl -X GET -v -H "Accept: application/vnd.docker.distribution.manifest.v2+json" https://127.0.0.1:5000/v2/{repository}/manifests/{tag} --insecure
# curl -X DELETE https://127.0.0.1:5000/v2/{repository}/manifests/{digest(sha부터)} --insecure
def delete_registry_repository_tag(address=None, repository=None, tag=None, real_name=None):
    """Delete image from registry server and run garbage collection.
    repository의 tag만 삭제 (경로 : /var/lib/registry/docker/registry/v2/repositories/jfb/{...}/_manifests/tags)

    :param address: url of registry server.           Ex) http://192.168.1.13:5000
    :param repository: image name with ip, port, tag  Ex) jfb/bybuild-workspace1-mytest01
    :param tag: tag of image.                         Ex) eT2TfzP15I4sFLeL
    """
    # check the address
    if real_name:
        arg = _parse_real_name_to_registry_arg(real_name=real_name)
        address = arg["address"]
        repository = arg["repository"]
        tag = arg["tag"]
    address = _regularize_address(address)

    # Check existance of the tag
    before_tags = get_registry_repository_tags(address, repository)
    if not before_tags or tag not in before_tags:
        return True #already removed

    # Get digest for reference.
    manifest_bytag_address = address+MANIFEST_BYTAG_PATH_SKEL.format(repository=repository, tag=tag)
    headers = {'Accept': 'application/vnd.docker.distribution.manifest.v2+json'}
    try:
        digest = requests.get(manifest_bytag_address, headers=headers, verify=False, timeout=300).headers['Docker-Content-Digest']
    except:
        traceback.print_exc()
        return False #failed

    # Delete the image by digest. DELETE /v2/<name>/manifests/<reference>
    manifest_bydigest_address = address+MANIFEST_BYDIGEST_PATH_SKEL.format(repository=repository, digest=digest)
    try:
        requests.delete(manifest_bydigest_address, headers=headers, verify=False, timeout=300)
    except:
        traceback.print_exc()

    # Delete the repository, if image is jfb image.
    if not get_registry_repository_tags(address, repository):
        common.launch_on_host("""docker exec {} rm -r {}/{}""".format(DOCKER_REGISTRY_CONTAINER, DOCKER_REGISTRY_DIR, repository))

    # Garbage Collection
    # Just doing with cron without leaving REGISTRY_DOCKER_NAME in settings would be ok.
    if 'REGISTRY_DOCKER_NAME' in dir(settings):
        try:
            common.launch_on_host('docker exec {} bin/registry garbage-collect /etc/docker/registry/config.yml'.format(settings.REGISTRY_DOCKER_NAME))
        except RemoteError as e:
            print (e)
        except:
            traceback.print_exc()

    # Check existance of the tag
    after_tags = get_registry_repository_tags(address, repository) # jfb 이미지는 태그가 랜덤한 고유값이므로 삭제된 경우 None 이어야 정상
    if after_tags and tag in after_tags:
        return False #failed

    return True #success