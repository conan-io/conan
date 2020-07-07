import datetime
import json
import os
from collections import defaultdict, namedtuple

import requests
from six.moves.urllib.parse import urlparse, urljoin

from conans.client.cache.cache import ClientCache
from conans.client.rest import response_to_str
from conans.errors import AuthenticationException, RequestErrorException, ConanException
from conans.model.graph_lock import LOCKFILE_VERSION
from conans.model.ref import ConanFileReference
from conans.paths import ARTIFACTS_PROPERTIES_PUT_PREFIX
from conans.paths import get_conan_user_home
from conans.util.files import save


class Artifact(namedtuple('Artifact', ["sha1", "md5", "name", "id"])):
    def __hash__(self):
        return hash(self.sha1)


def _parse_options(contents):
    for line in contents.splitlines():
        key, value = line.split("=")
        yield "options.{}".format(key), value


def _parse_profile(contents):
    import configparser

    config = configparser.ConfigParser()
    config.read_string(contents)

    for section, values in config._sections.items():
        for key, value in values.items():
            yield "{}.{}".format(section, key), value


class BuildInfoCreator(object):
    def __init__(self, output, build_info_file, lockfile, user=None, password=None, apikey=None):
        self._build_info_file = build_info_file
        self._lockfile = lockfile
        self._user = user
        self._password = password
        self._apikey = apikey
        self._output = output
        self._conan_cache = ClientCache(os.path.join(get_conan_user_home(), ".conan"), output)

    def parse_ref(self, ref):
        ref = ConanFileReference.loads(ref, validate=False)
        rrev = ref.revision
        return {
            "name": ref.name,
            "version": ref.version,
            "user": ref.user,
            "channel": ref.channel,
            "rrev": rrev,
        }

    def _get_reference(self, ref):
        r = self.parse_ref(ref)
        if r.get("user") and r.get("channel"):
            return "{name}/{version}@{user}/{channel}".format(**r)
        else:
            return "{name}/{version}".format(**r)

    def _get_package_reference(self, ref, pid):
        r = self.parse_ref(ref)
        return "{reference}:{pid}".format(reference=self._get_reference(ref), pid=pid)

    def _get_metadata_artifacts(self, metadata, request_path, use_id=False, name_format="{}",
                                package_id=None):
        ret = {}
        need_sources = False
        if package_id:
            data = metadata.packages[package_id].checksums
        else:
            data = metadata.recipe.checksums
            need_sources = not ("conan_sources.tgz" in data)

        for name, value in data.items():
            name_or_id = name_format.format(name)
            ret[value["sha1"]] = {"md5": value["md5"],
                                  "name": name_or_id if not use_id else None,
                                  "id": name_or_id if use_id else None}
        if need_sources:
            remote_name = metadata.recipe.remote
            remotes = self._conan_cache.registry.load_remotes()
            remote_url = remotes[remote_name].url
            parsed_uri = urlparse(remote_url)
            base_url = "{uri.scheme}://{uri.netloc}/artifactory/api/storage/conan/".format(
                uri=parsed_uri)
            request_url = urljoin(base_url, "{}/conan_sources.tgz".format(request_path))
            if self._user and self._password:
                response = requests.get(request_url, auth=(self._user, self._password))
            elif self._apikey:
                response = requests.get(request_url, headers={"X-JFrog-Art-Api": self._apikey})
            else:
                response = requests.get(request_url)

            if response.status_code == 200:
                data = response.json()
                ret[data["checksums"]["sha1"]] = {"md5": data["checksums"]["md5"],
                                                  "name": "conan_sources.tgz" if not use_id else None,
                                                  "id": "conan_sources.tgz" if use_id else None}
        return set([Artifact(k, **v) for k, v in ret.items()])

    def _get_recipe_artifacts(self, ref, is_dependency):
        r = self.parse_ref(ref)
        if r.get("user") and r.get("channel"):
            ref = "{name}/{version}@{user}/{channel}#{rrev}".format(**r)
        else:
            ref = "{name}/{version}#{rrev}".format(**r)
        reference = ConanFileReference.loads(ref)
        package_layout = self._conan_cache.package_layout(reference)
        metadata = package_layout.load_metadata()
        name_format = "{} :: {{}}".format(self._get_reference(ref)) if is_dependency else "{}"
        if r.get("user") and r.get("channel"):
            url = "{user}/{name}/{version}/{channel}/{rrev}/export".format(**r)
        else:
            url = "_/{name}/{version}/_/{rrev}/export".format(**r)

        return self._get_metadata_artifacts(metadata, url, name_format=name_format,
                                            use_id=is_dependency)

    def _get_package_artifacts(self, ref, pid, prev, is_dependency):
        r = self.parse_ref(ref)
        if r.get("user") and r.get("channel"):
            ref = "{name}/{version}@{user}/{channel}#{rrev}".format(**r)
        else:
            ref = "{name}/{version}#{rrev}".format(**r)
        reference = ConanFileReference.loads(ref)
        package_layout = self._conan_cache.package_layout(reference)
        metadata = package_layout.load_metadata()
        if is_dependency:
            name_format = "{} :: {{}}".format(self._get_package_reference(ref, pid))
        else:
            name_format = "{}"
        if r.get("user") and r.get("channel"):
            url = "{user}/{name}/{version}/{channel}/{rrev}/package/{pid}/{prev}"
        else:
            url = "_/{name}/{version}/_/{rrev}/package/{pid}/{prev}"
        url = url.format(pid=pid, prev=prev, **r)
        arts = self._get_metadata_artifacts(metadata, url, name_format=name_format,
                                            use_id=is_dependency, package_id=pid)
        return arts

    def process_lockfile(self):
        modules = defaultdict(lambda: {"id": None, "artifacts": set(), "dependencies": set()})

        def _gather_transitive_recipes(nid, contents):
            n = contents["graph_lock"]["nodes"][nid]
            artifacts = self._get_recipe_artifacts(n["ref"], is_dependency=True)
            for id_node in n.get("requires", []):
                artifacts.update(_gather_transitive_recipes(id_node, contents))
            for id_node in n.get("build_requires", []):
                artifacts.update(_gather_transitive_recipes(id_node, contents))
            return artifacts

        def _gather_transitive_packages(nid, contents):
            n = contents["graph_lock"]["nodes"][nid]
            artifacts = self._get_package_artifacts(n["ref"], n["package_id"], n["prev"],
                                                    is_dependency=True)
            for id_node in n.get("requires", []):
                artifacts.update(_gather_transitive_packages(id_node, contents))
            for id_node in n.get("build_requires", []):
                artifacts.update(_gather_transitive_packages(id_node, contents))
            return artifacts

        with open(self._lockfile) as json_data:
            data = json.load(json_data)

        version = data["version"]
        if version != LOCKFILE_VERSION:
            raise ConanException("This lockfile was created with an incompatible version "
                                 "of Conan. Please update all your Conan clients")

        # Gather modules, their artifacts and recursively all required artifacts
        for _, node in data["graph_lock"]["nodes"].items():
            ref = node["ref"]
            pid = node.get("package_id")
            prev = node.get("prev")
            if node.get("modified"):  # Work only on generated nodes
                # Create module for the recipe reference
                recipe_key = self._get_reference(ref)
                modules[recipe_key]["id"] = recipe_key
                modules[recipe_key]["artifacts"].update(
                    self._get_recipe_artifacts(ref, is_dependency=False))
                # TODO: what about `python_requires`?
                # TODO: can we associate any properties to the recipe? Profile/options may
                # TODO: be different per lockfile

                # Create module for the package_id
                package_key = self._get_package_reference(ref, pid)
                modules[package_key]["id"] = package_key
                modules[package_key]["artifacts"].update(
                    self._get_package_artifacts(ref, pid, prev, is_dependency=False))

                # Recurse requires
                node_ids = node.get("requires", []) + node.get("build_requires", [])
                for node_id in node_ids:
                    modules[recipe_key]["dependencies"].update(_gather_transitive_recipes(node_id,
                                                                                          data))
                    modules[package_key]["dependencies"].update(_gather_transitive_packages(node_id,
                                                                                            data))

                # TODO: Is the recipe a 'dependency' of the package

        return modules

    def create(self):
        properties = self._conan_cache.read_artifacts_properties()
        modules = self.process_lockfile()
        # Add extra information
        ret = {"version": "1.0.1",
               "name": properties[ARTIFACTS_PROPERTIES_PUT_PREFIX + "build.name"],
               "number": properties[ARTIFACTS_PROPERTIES_PUT_PREFIX + "build.number"],
               "type": "GENERIC",
               "started": datetime.datetime.utcnow().isoformat().split(".")[0] + ".000Z",
               "buildAgent": {"name": "Conan Client", "version": "1.X"},
               "modules": list(modules.values())}

        def dump_custom_types(obj):
            if isinstance(obj, set):
                artifacts = [{k: v for k, v in o._asdict().items() if v is not None} for o in obj]
                return sorted(artifacts, key=lambda u: u.get("name") or u.get("id"))
            raise TypeError

        save(self._build_info_file, json.dumps(ret, indent=4, default=dump_custom_types))


def create_build_info(output, build_info_file, lockfile, user, password, apikey):
    bi = BuildInfoCreator(output, build_info_file, lockfile, user, password, apikey)
    bi.create()


def start_build_info(output, build_name, build_number):
    paths = ClientCache(os.path.join(get_conan_user_home(), ".conan"), output)
    content = ARTIFACTS_PROPERTIES_PUT_PREFIX + "build.name={}\n".format(build_name) + \
              ARTIFACTS_PROPERTIES_PUT_PREFIX + "build.number={}\n".format(build_number)
    artifact_properties_file = paths.artifacts_properties_path
    try:
        save(artifact_properties_file, content)
    except Exception:
        raise ConanException("Can't write properties file in %s" % artifact_properties_file)


def stop_build_info(output):
    paths = ClientCache(os.path.join(get_conan_user_home(), ".conan"), output)
    artifact_properties_file = paths.artifacts_properties_path
    try:
        save(artifact_properties_file, "")
    except Exception:
        raise ConanException("Can't write properties file in %s" % artifact_properties_file)


def publish_build_info(build_info_file, url, user, password, apikey):
    with open(build_info_file) as json_data:
        parsed_uri = urlparse(url)
        request_url = "{uri.scheme}://{uri.netloc}/artifactory/api/build".format(uri=parsed_uri)
        if user and password:
            response = requests.put(request_url, headers={"Content-Type": "application/json"},
                                    data=json_data, auth=(user, password))
        elif apikey:
            response = requests.put(request_url, headers={"Content-Type": "application/json",
                                                          "X-JFrog-Art-Api": apikey},
                                    data=json_data)
        else:
            response = requests.put(request_url)

        if response.status_code == 401:
            raise AuthenticationException(response_to_str(response))
        elif response.status_code != 204:
            raise RequestErrorException(response_to_str(response))


def find_module(build_info, module_id):
    for it in build_info["modules"]:
        if it["id"] == module_id:
            return it
    new_module = {"id": module_id, "artifacts": [], "dependencies": []}
    build_info["modules"].append(new_module)
    return new_module


def merge_artifacts(lhs, rhs, key, cmp_key):
    ret = {it[cmp_key]: it for it in lhs[key]}
    for art in rhs[key]:
        art_cmp_key = art[cmp_key]
        if art_cmp_key in ret:
            assert art[cmp_key] == ret[art_cmp_key][cmp_key], \
                "({}) {} != {} for sha1={}".format(cmp_key, art[cmp_key], ret[art_cmp_key][cmp_key],
                                                   art_cmp_key)
        else:
            ret[art_cmp_key] = art

    return [value for _, value in ret.items()]


def merge_buildinfo(lhs, rhs):
    if not lhs or not rhs:
        return lhs or rhs

    # Check they are compatible
    assert lhs["version"] == rhs["version"]
    assert lhs["name"] == rhs["name"]
    assert lhs["number"] == rhs["number"]

    for rhs_module in rhs["modules"]:
        lhs_module = find_module(lhs, rhs_module["id"])
        lhs_module["artifacts"] = merge_artifacts(lhs_module, rhs_module, key="artifacts",
                                                  cmp_key="name")
        lhs_module["dependencies"] = merge_artifacts(lhs_module, rhs_module, key="dependencies",
                                                     cmp_key="id")
    return lhs


def update_build_info(buildinfo, output_file):
    build_info = {}
    for it in buildinfo:
        with open(it) as json_data:
            data = json.load(json_data)
        build_info = merge_buildinfo(build_info, data)

    save(output_file, json.dumps(build_info, indent=4))
