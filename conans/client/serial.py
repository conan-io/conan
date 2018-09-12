from conans.client.remote_registry import Remote
from conans.client.recorder.action_recorder import ActionRecorder
from conans.client.output import ScopedOutput
import time
from conans.client.loader import ProcessedProfile
from conans.client.graph.graph import Node, DepsGraph
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.info import RequirementInfo, RequirementsInfo, ConanInfo


def serial_remote(remote):
    result = {}
    result["name"] = remote.name
    result["url"] = remote.url
    result["verify_ssl"] = remote.verify_ssl
    return result


def unserial_remote(data):
    if data is None:
        return None
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
    result["conanfile"] = node.conanfile.serial()
    result["binary"] = node.binary
    result["recipe"] = node.recipe
    result["remote"] = node.remote.serial() if node.remote else None
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
    Node._conanfile_time += time.time() - t1
    t1 = time.time()
    conanfile.unserial(data["conanfile"], env)

    result = Node(conan_ref, conanfile)
    result.binary = data["binary"]
    result.recipe = data["recipe"]
    result.remote = remote
    result.binary_remote = Remote.unserial(data["binary_remote"])
    result.build_require = data["build_require"]
    Node._unserial_time += time.time() - t1
    return result


def serial_graph(graph):
    result = {}
    result["nodes"] = {str(id(n)): serial_node(n) for n in graph.nodes}
    result["edges"] = [serial_edge(e) for n in graph.nodes for e in n.dependencies]
    result["root"] = str(id(graph.root))
    return result


def unserial_graph(data, env, conanfile_path, output, proxy, loader, scoped_output=None):
    result = DepsGraph()
    nodes_dict = {id_: unserial_node(n, env, conanfile_path, output, proxy, loader,
                                     scoped_output=scoped_output)
                  for id_, n in data["nodes"].items()}
    result.nodes = set(nodes_dict.values())
    result.root = nodes_dict[data["root"]]
    for edge in data["edges"]:
        result.add_edge(nodes_dict[edge["src"]], nodes_dict[edge["dst"]], edge["private"])
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
    result._data = {PackageReference.loads(k): unserial_requirements_info(v)
                    for k, v in data.items()}
    return result

    def serial(self):
        return self.serialize()

    @staticmethod
    def unserial(data):
        return RequirementsList.deserialize(data)

def serial_conan_info(conan_info):
    result = {}
    result["settings"] = conan_info.settings.serial()
    result["full_settings"] = conan_info.full_settings.serial()
    result["full_requires"] = conan_info.full_requires.serial()
    result["full_options"] = conan_info.full_options.serial()
    result["options"] = conan_info.options.serial()
    result["requires"] = conan_info.requires.serial()
    result["env_values"] = conan_info.env_values.serial()
    return result


def unserial_conan_info(data):
    result = ConanInfo()
    result.settings = Values.unserial(data["settings"])
    result.full_settings = Values.unserial(data["full_settings"])
    result.full_requires = RequirementsList.unserial(data["full_requires"])
    result.full_options = OptionsValues.unserial(data["full_options"])
    result.options = OptionsValues.unserial(data["options"])
    result.requires = RequirementsInfo.unserial(data["requires"])
    result.env_values = EnvValues.unserial(data["env_values"])
    return result
