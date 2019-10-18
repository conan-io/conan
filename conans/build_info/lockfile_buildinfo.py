import datetime
import json
import os
import re
import sys
from collections import defaultdict, namedtuple
from urllib.parse import urlparse

from rtpy import Rtpy

from conans.client.cache.cache import ClientCache
from conans.model.ref import ConanFileReference
from conans.paths import get_conan_user_home
from conans.client.output import ConanOutput

output = ConanOutput(sys.stdout, sys.stderr, True)

pref_pattern = re.compile(r"(?P<name>[^\/@#:]+)\/"
                          r"(?P<version>[^\/@#:]+)"
                          r"@"
                          r"(?P<user>[^\/@#:]+)\/"
                          r"(?P<channel>[^\/@#:]+)"
                          r"#(?P<rrev>[^\/@#:]+)"
                          r":(?P<pid>[^\/@#:]+)"
                          r"#(?P<prev>[^\/@#:]+)")


class Artifact(namedtuple('Artifact', ["sha1", "md5", "name", "id"])):
    def __hash__(self):
        return hash(self.sha1)


def parse_pref(pref):
    return pref_pattern.match(pref).groupdict()


def _get_reference(pref):
    r = parse_pref(pref)
    return "{name}/{version}@{user}/{channel}".format(**r)


def _get_package_reference(pref):
    r = parse_pref(pref)
    return "{reference}:{pid}".format(reference=_get_reference(pref), **r)


def _parse_profile(contents):
    import configparser

    config = configparser.ConfigParser()
    config.read_string(contents)

    for section, values in config._sections.items():
        for key, value in values.items():
            yield "{}.{}".format(section, key), value


def _parse_options(contents):
    for line in contents.splitlines():
        key, value = line.split("=")
        yield "options.{}".format(key), value


def _get_artifacts(path, remote, use_id=False, name_format="{name}"):
    art_query = 'items.find({{"path": "{path}"}}).include("repo", "name", "path", "actual_md5", "actual_sha1")'
    url = art_query.format(path=path)
    ret = {}
    r = remote.searches.artifactory_query_language(url)
    if r:
        for result in r["results"]:
            if result["name"] in [".timestamp"]:
                continue
            name_or_id = name_format.format(**result)
            ret[result["actual_sha1"]] = {"md5": result["actual_md5"],
                                          "name": name_or_id if not use_id else None,
                                          "id": name_or_id if use_id else None}
    return set([Artifact(k, **v) for k, v in ret.items()])


def _get_recipe_artifacts(pref, add_prefix, use_id):
    r = parse_pref(pref)
    ref = "{name}/{version}@{user}/{channel}#{rrev}".format(**r)
    paths = ClientCache(os.path.join(get_conan_user_home(), ".conan"), output)
    reference = ConanFileReference.loads(ref)
    package_layout = paths.package_layout(reference)
    metadata = package_layout.load_metadata()
    # get remote from metadata
    remote_name = metadata.recipe.remote
    remotes = paths.registry.load_remotes()
    remote_url = remotes[remote_name].url
    parsed_uri = urlparse(remote_url)
    artifactory_url = '{uri.scheme}://{uri.netloc}/artifactory'.format(uri=parsed_uri)
    artifactory = Rtpy(
        {"af_url": artifactory_url, "username": "admin", "password": "password"})
    url = "{user}/{name}/{version}/{channel}/{rrev}/export".format(**r)
    name_format = "{} :: {{name}}".format(_get_reference(pref)) if add_prefix else "{name}"
    return _get_artifacts(path=url, remote=artifactory, use_id=use_id, name_format=name_format)


def _get_package_artifacts(pref, add_prefix, use_id):
    r = parse_pref(pref)
    ref = "{name}/{version}@{user}/{channel}#{rrev}".format(**r)
    paths = ClientCache(os.path.join(get_conan_user_home(), ".conan"), output)
    reference = ConanFileReference.loads(ref)
    package_layout = paths.package_layout(reference)
    metadata = package_layout.load_metadata()
    # get remote from metadata
    remote_name = metadata.packages[r["pid"]].remote
    remotes = paths.registry.load_remotes()
    remote_url = remotes[remote_name].url
    parsed_uri = urlparse(remote_url)
    artifactory_url = '{uri.scheme}://{uri.netloc}/artifactory'.format(uri=parsed_uri)
    artifactory = Rtpy(
        {"af_url": artifactory_url, "username": "admin", "password": "password"})
    url = "{user}/{name}/{version}/{channel}/{rrev}/package/{pid}/{prev}".format(**r)
    name_format = "{} :: {{name}}".format(_get_package_reference(pref)) if add_prefix else "{name}"
    arts = _get_artifacts(path=url, remote=artifactory, use_id=use_id, name_format=name_format)
    return arts


def process_lockfile(lockfile, multi_module):
    modules = defaultdict(lambda: {"id": None, "properties": {},
                                   "artifacts": set(), "dependencies": set()})

    def _gather_deps(node_uid, contents, func):
        node_content = contents["graph_lock"]["nodes"].get(node_uid)
        artifacts = func(node_content["pref"], add_prefix=True, use_id=True)
        for _, id_node in node_content.get("requires", {}).items():
            artifacts.update(_gather_deps(id_node, contents, func))
        return artifacts

    with open(lockfile) as json_data:
        data = json.load(json_data)
    profile = dict(_parse_profile(data["profile"]))

    # Gather modules, their artifacts and recursively all required artifacts
    for _, node in data["graph_lock"]["nodes"].items():
        pref = node["pref"]
        if node.get("modified"):  # Work only on generated nodes
            # Create module for the recipe reference
            recipe_key = _get_reference(pref)
            modules[recipe_key]["id"] = recipe_key
            modules[recipe_key]["artifacts"].update(_get_recipe_artifacts(pref, add_prefix=not multi_module, use_id=False))
            # TODO: what about `python_requires`?
            # TODO: can we associate any properties to the recipe? Profile/options may be different per lockfile

            # Create module for the package_id
            package_key = _get_package_reference(pref) if multi_module else recipe_key
            modules[package_key]["id"] = package_key
            modules[package_key]["artifacts"].update(
                _get_package_artifacts(pref, add_prefix=not multi_module, use_id=False))
            if multi_module:  # Only for multi_module, see TODO above
                modules[package_key]["properties"].update(profile)
                modules[package_key]["properties"].update(_parse_options(node.get("options")))

            # Recurse requires
            for _, node_id in node["requires"].items():
                modules[recipe_key]["dependencies"].update(
                    _gather_deps(node_id, data, _get_recipe_artifacts))
                modules[package_key]["dependencies"].update(
                    _gather_deps(node_id, data, _get_package_artifacts))

            # TODO: Is the recipe a 'dependency' of the package

    return modules


def create_build_info(build_info_file, lockfile, multi_module=True, skip_env=True):
    paths = ClientCache(os.path.join(get_conan_user_home(), ".conan"), output)
    properties = paths.read_put_headers()
    modules = process_lockfile(lockfile, multi_module)
    # Add extra information
    ret = {"version": "1.0.1",
           "name": properties["artifact_property_build.name"],
           "number": properties["artifact_property_build.number"],
           "type": "GENERIC",
           "started": datetime.datetime.utcnow().isoformat().split(".")[0] + ".000Z",
           "buildAgent": {"name": "Conan Client", "version": "1.X"},
           "modules": list(modules.values())}

    if not skip_env:
        excluded = ["secret", "key", "password"]
        environment = {"buildInfo.env.{}".format(k): v for k, v in os.environ.items() if
                       k not in excluded}
        ret["properties"] = environment

    def dump_custom_types(obj):
        if isinstance(obj, set):
            artifacts = [{k: v for k, v in o._asdict().items() if v is not None} for o in obj]
            return sorted(artifacts, key=lambda u: u.get("name") or u.get("id"))
        raise TypeError

    with open(build_info_file, "w") as f:
        f.write(json.dumps(ret, indent=4, default=dump_custom_types))
