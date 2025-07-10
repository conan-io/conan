import yaml

from conan.errors import ConanException
from conan.internal.util.files import load


def loadconanconfig(filename):
    try:
        packages = yaml.safe_load(load(filename))["packages"]
    except Exception as e:
        raise ConanException(f"Error while loading config file {filename}: {str(e)}")
    return packages
