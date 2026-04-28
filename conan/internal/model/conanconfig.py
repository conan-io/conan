import json

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
        urls_raw = contents.get("urls")
        urls = None
        if urls_raw is not None:
            urls = []
            for u in urls_raw:
                if isinstance(u, str):
                    urls.append((u, True))
                else:
                    urls.append((u["url"], u.get("verify_ssl", True)))
    except Exception as e:
        raise ConanException(f"Error while loading config file {filename}: {str(e)}")
    return config_versions, urls


def saveconanconfig(filename, config_versions):
    try:
        config_versions = [r.repr_notime() for r in config_versions]
        save(filename, json.dumps({"config_version": config_versions}, indent=4))
    except Exception as e:
        raise ConanException(f"Error while saving config file {filename}: {str(e)}")
