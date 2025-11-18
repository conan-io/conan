import json

from conan.api.model import RecipeReference
from conan.errors import ConanException
from conan.internal.util.files import load


def loadconanconfig(filename):
    try:
        config_versions = json.loads(load(filename))
        config_versions = config_versions["config_version"]
        config_versions = [RecipeReference.loads(r) for r in config_versions]
    except Exception as e:
        raise ConanException(f"Error while loading config file {filename}: {str(e)}")
    return config_versions
