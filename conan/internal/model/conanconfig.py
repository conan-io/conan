import json
import os

import yaml

from conan.api.model import RecipeReference
from conan.errors import ConanException
from conan.internal.util.files import load, save


def loadconanconfig(filename):
    try:
        contents = json.loads(load(filename))
        config_versions = contents["config_version"]
        config_versions = [RecipeReference.loads(r) for r in config_versions]
    except Exception as e:
        raise ConanException(f"Error while loading config file {filename}: {str(e)}")
    return config_versions


def loadconanconfig_yml(filename):
    try:
        contents = yaml.safe_load(load(filename))
        config_versions = contents["packages"]
        config_versions = [RecipeReference.loads(r) for r in config_versions]
        urls = contents.get("urls")
    except Exception as e:
        raise ConanException(f"Error while loading config file {filename}: {str(e)}")
    return config_versions, urls


def saveconanconfig(filename, config_versions):
    """Save config versions to file atomically.

    Uses atomic file replacement to avoid corruption if interrupted.
    """
    try:
        config_versions = [r.repr_notime() for r in config_versions]
        tmp_file = filename + ".tmp"
        save(tmp_file, json.dumps({"config_version": config_versions}, indent=4))
        os.replace(tmp_file, filename)
    except Exception as e:
        raise ConanException(f"Error while saving config file {filename}: {str(e)}")
