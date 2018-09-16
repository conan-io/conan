
from conans.client.recorder.action_recorder import ActionRecorder
from conans.client.output import ScopedOutput
import time
from conans.client.loader import ProcessedProfile
from _collections import defaultdict
from conans.model.env_info import EnvValues
from conans.model.info import RequirementsList, ConanInfo, RequirementsInfo,\
    RequirementInfo
from conans.model.settings import Settings, SettingsItem
from conans.model.options import OptionsValues, PackageOptions, PackageOption,\
    PackageOptionValues, PackageOptionValue, Options
from conans.model.values import Values
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.requires import Requirement, Requirements
from conans.model.conan_file import ConanFile
from conans.client.graph.graph import BINARY_BUILD


def serial_option_values(self):
    result = {}
    result["package_values"] = serial_package_option_values(self._package_values)
    result["reqs_options"] = {k: serial_package_option_values(v)
                              for k, v in self._reqs_options.items()}
    return result


def unserial_option_values(data):
    result = OptionsValues()
    result._package_values = unserial_package_option_values(data["package_values"])
    result._reqs_options = {k: unserial_package_option_values(v)
                            for k, v in data["reqs_options"].items()}
    return result


def serial_package_option(self):
    result = {"name": self._name,
              "value": self._value,
              "possible_values": self._possible_values}
    return result


def unserial_package_option(data):
    result = PackageOption(data["possible_values"], data["name"])
    result._value = data["value"]
    return result


def serial_package_options(self):
    result = {k: serial_package_option(v) for k, v in self._data.items()}
    return result


def unserial_package_options(data):
    result = PackageOptions(None)
    result._data = {k: unserial_package_option(v) for k, v in data.items()}
    return result


def serial_package_option_values(self):
    result = {k: str(v)
              for k, v in self._dict.items()}
    return result


def serial_requirement(self):
    result = {}
    result["conan"] = serial_ref(self.conan_reference)
    result["range"] = serial_ref(self.range_reference)
    result["override"] = self.override
    result["private"] = self.private
    return result


def serial_values(self):
    return self.as_list()


def unserial_values(data):
    return Values.from_list(data)


def unserial_requirement(data):
    result = Requirement(unserial_ref(data["conan"]),
                         data["private"], data["override"])
    result.range_reference = unserial_ref(data["range"])
    return result


def serial_requirements(self):
    result = [serial_requirement(v) for v in self.values()]
    return result


def unserial_requirements(data):
    result = Requirements()
    for d in data:
        d = unserial_requirement(d)
        result[d.conan_reference.name] = d
    return result


def unserial_package_option_values(data):
    result = PackageOptionValues()
    result._dict = {k: PackageOptionValue(v) for k, v in data.items()}
    return result


def serial_options(self):
    result = {}
    result["package_options"] = serial_package_options(self._package_options)
    result["deps_package_values"] = {k: serial_package_option_values(v)
                                     for k, v in self._deps_package_values.items()}
    return result


def unserial_options(data):
    result = Options(unserial_package_options(data["package_options"]))
    result._deps_package_values = {k: unserial_package_option_values(v)
                                   for k, v in data["deps_package_values"].items()}
    return result


def serial_env_values(env_values):
    result = {}
    for package_name, d in env_values._data.items():
        result[package_name] = d
    return result


def unserial_env_values(data):
    result = EnvValues()
    result._data = defaultdict(dict)
    for k, v in data.items():
        result._data[k] = v
    return result


def serial_conanfile(conanfile):
    result = {}
    result["info"] = serial_conan_info(conanfile.info)
    result["settings"] = serial_settings(conanfile.settings)
    result["options"] = serial_options(conanfile.options)
    result["requires"] = serial_requirements(conanfile.requires)
    return result


def unserial_conanfile(conanfile, data, env):
    conanfile.info = unserial_conan_info(data["info"])
    conanfile.settings = unserial_settings(data["settings"])
    conanfile.options = unserial_options(data["options"])
    conanfile.requires = unserial_requirements(data["requires"])
    conanfile._env_values = env.copy()  # user specified -e


def serial_remote(remote):
    result = {}
    result["name"] = remote.name
    result["url"] = remote.url
    result["verify_ssl"] = remote.verify_ssl
    return result


def unserial_remote(data):
    if data is None:
        return None
    from conans.client.remote_registry import Remote
    return Remote(data["name"], data["url"], data["verify_ssl"])


_conanfile_time = 0
_unserial_time = 0


def serial_ref(conan_reference):
    return repr(conan_reference)


def unserial_ref(data):
    if data is None:
        return None
    return ConanFileReference.loads(data)


def serial_edge(edge):
    result = {}
    result["src"] = str(id(edge.src))
    result["dst"] = str(id(edge.dst))
    result["private"] = edge.private
    return result


def serial_node(node):
    result = {}
    result["path"] = getattr(node, "path", None)
    result["conan_ref"] = serial_ref(node.conan_ref) if node.conan_ref else None
    result["conanfile"] = serial_conanfile(node.conanfile)
    result["binary"] = node.binary
    result["recipe"] = node.recipe
    result["remote"] = serial_remote(node.remote) if node.remote else None
    result["binary_remote"] = serial_remote(node.binary_remote) if node.binary_remote else None
    result["build_require"] = node.build_require
    return result


def unserial_node(data, env, conanfile_path, output, proxy, loader, update=False,
                  scoped_output=None):
    path = data["path"]
    conan_ref = unserial_ref(data["conan_ref"])
    # Remotes needs to be decoupled
    remote = unserial_remote(data["remote"])
    remote_name = remote.name if remote else None
    t1 = time.time()
    if not path and not conan_ref:
        conanfile = ConanFile(None, loader._runner, Values())
    else:
        if path:
            conanfile_path = conanfile_path
            output = scoped_output
        else:
            result = proxy.get_recipe(conan_ref, check_updates=False, update=update,
                                      remote_name=remote_name, recorder=ActionRecorder())
            conanfile_path, recipe_status, remote, _ = result
            output = ScopedOutput(str(conan_ref or "Project"), output)
        if conanfile_path.endswith(".txt"):
            # FIXME: remove this ugly ProcessedProfile
            conanfile = loader.load_conanfile_txt(conanfile_path, output, ProcessedProfile())
        else:
            conanfile = loader.load_basic(conanfile_path, output, conan_ref)
    from conans.client.graph.graph import Node
    t1 = time.time()
    unserial_conanfile(conanfile, data["conanfile"], env)

    result = Node(conan_ref, conanfile)
    result.binary = None # data["binary"]
    result.recipe = data["recipe"]
    result.remote = remote
    result.binary_remote = unserial_remote(data["binary_remote"])
    result.build_require = data["build_require"]
    return result


def serial_settings_item(settings_item):
    result = {}
    result["name"] = settings_item._name
    result["value"] = settings_item._value
    if isinstance(settings_item._definition, dict):
        subdict = {}
        for k, v in settings_item._definition.items():
            subdict[k] = serial_settings(v)
        result["definition"] = subdict
    elif settings_item._definition == "ANY":
        result["definition"] = "ANY"
    else:
        result["definition"] = settings_item._definition
    return result


def unserial_settings_item(data):
    result = SettingsItem([], data["name"])
    result._value = data["value"]
    definition = data["definition"]
    if isinstance(definition, dict):
        subdict = {}
        for k, v in definition.items():
            subdict[k] = unserial_settings(v)
        result._definition = subdict
    elif definition == "ANY":
        result._definition = "ANY"
    else:
        result._definition = definition
    return result


def serial_settings(settings):
    result = {}
    result["name"] = settings._name
    result["parent_value"] = settings._parent_value
    result["data"] = {k: serial_settings_item(v) for k, v in settings._data.items()}
    return result


def unserial_settings(data):
    result = Settings()
    result._name = data["name"]
    result._parent_value = data["parent_value"]
    result._data = {k: unserial_settings_item(v) for k, v in data["data"].items()}
    return result


def serial_graph(graph):
    result = {}
    result["nodes"] = {str(id(n)): serial_node(n) for n in graph.nodes}
    result["edges"] = [serial_edge(e) for n in graph.nodes for e in n.dependencies]
    result["root"] = str(id(graph.root))
    build_order = graph.build_order_ids("ALL")
    result["build_order"] = build_order
    return result


def unserial_graph(data, env, conanfile_path, output, proxy, loader, scoped_output=None, id_=None):
    from conans.client.graph.graph import Node, DepsGraph
    result = DepsGraph()
    nodes_dict = {id_: unserial_node(n, env, conanfile_path, output, proxy, loader,
                                     scoped_output=scoped_output)
                  for id_, n in data["nodes"].items()}
    result.nodes = set(nodes_dict.values())
    result.root = nodes_dict[data["root"]]
    for edge in data["edges"]:
        result.add_edge(nodes_dict[edge["src"]], nodes_dict[edge["dst"]], edge["private"])
    if id_:
        node = nodes_dict[id_]
        result.prune_subgraph(node)
        virtual = Node(None, ConanFile(None, loader._runner, Values()))
        result.add_node(virtual)
        result.add_edge(virtual, node)
        result.root = virtual

    return result


def serial_requirement_info(self):
    return {"name": self.name,
            "version": self.version,
            "user": self.user,
            "channel": self.channel,
            "package_id": self.package_id}


def unserial_requirement_info(data):
    result = RequirementInfo("pkg/0.1@user/testing:id")
    result.name = data["name"]
    result.version = data["version"]
    result.channel = data["channel"]
    result.user = data["user"]
    result.package_id = data["package_id"]
    return result


def serial_requirements_info(requirements_info):
    return {str(k): serial_requirement_info(v) for k, v in requirements_info._data.items()}


def unserial_requirements_info(data):
    result = RequirementsInfo([])
    result._data = {PackageReference.loads(k): unserial_requirement_info(v)
                    for k, v in data.items()}
    return result


def serial_requirements_list(self):
    return self.serialize()


def unserial_requirements_list(data):
    return RequirementsList.deserialize(data)


def serial_conan_info(conan_info):
    result = {}
    result["settings"] = serial_values(conan_info.settings)
    result["full_settings"] = serial_values(conan_info.full_settings)
    result["full_requires"] = serial_requirements_list(conan_info.full_requires)
    result["full_options"] = serial_option_values(conan_info.full_options)
    result["options"] = serial_option_values(conan_info.options)
    result["requires"] = serial_requirements_info(conan_info.requires)
    result["env_values"] = serial_env_values(conan_info.env_values)
    return result


def unserial_conan_info(data):
    result = ConanInfo()
    result.settings = unserial_values(data["settings"])
    result.full_settings = unserial_values(data["full_settings"])
    result.full_requires = unserial_requirements_list(data["full_requires"])
    result.full_options = unserial_option_values(data["full_options"])
    result.options = unserial_option_values(data["options"])
    result.requires = unserial_requirements_info(data["requires"])
    result.env_values = unserial_env_values(data["env_values"])
    return result
