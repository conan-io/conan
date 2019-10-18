import os
import sys

from rtpy import Rtpy

from conans.build_info.lockfile_buildinfo import create_build_info
from conans.client.cache.cache import ClientCache
from conans.client.output import ConanOutput
from conans.errors import ConanException
from conans.paths import get_conan_user_home
from conans.util.files import save

output = ConanOutput(sys.stdout, sys.stderr, True)


def start(build_name, build_number):
    paths = ClientCache(os.path.join(get_conan_user_home(), ".conan"), output)
    content = "artifact_property_build.name={}\n" \
              "artifact_property_build.number={}\n".format(build_name, build_number)
    try:
        artifact_properties_file = paths.put_headers_path
        save(artifact_properties_file, content)
    except Exception:
        raise ConanException("Can't write properties file in %s" % artifact_properties_file)


def stop():
    paths = ClientCache(os.path.join(get_conan_user_home(), ".conan"), output)
    try:
        artifact_properties_file = paths.put_headers_path
        save(artifact_properties_file, "")
    except Exception:
        raise ConanException("Can't write properties file in %s" % artifact_properties_file)


def create(build_info_file, lockfile):
    create_build_info(build_info_file, lockfile)


def update(build_info_1, build_info_2):
    print(build_info_1, build_info_2)
    pass


def publish(build_info_file, url, user, password=None, apikey=None):
    if apikey:
        rtpy = Rtpy({"af_url": url, "api_key": apikey})
    elif password:
        rtpy = Rtpy({"af_url": url, "username": user, "password": password})

    with open(build_info_file) as json_data:
        rtpy.builds._request("PUT", "build", "Publish build info", kwargs={},
                             params={"Content-Type": "application/json"}, data=json_data)
