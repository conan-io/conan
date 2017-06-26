import json
import os
from collections import defaultdict

from conans.build_info.model import BuildInfo, BuildInfoModule, BuildInfoModuleArtifact, BuildInfoModuleDependency
from conans.model.info import ConanInfo, PackageReference
from conans.model.ref import ConanFileReference
from conans.util.files import load


def _extract_uploads_from_conan_trace(path):
    modules = defaultdict(dict)  # dict of {conan_ref: [abs_path1, abs_path2]}
    try:
        with open(path, "r") as traces:
            for line in traces.readlines():
                doc = json.loads(line)
                if doc["_action"] in ("UPLOADED_RECIPE", "UPLOADED_PACKAGE"):
                    module_type = "recipe" if doc["_action"] == "UPLOADED_RECIPE" else "package"
                    modules[doc["_id"]] = {"remote": doc["remote"], "files": [], "type": module_type}
                    modules[doc["_id"]]["files"].extend(doc["files"])
    except ValueError as exc:
        raise Exception("INVALID TRACE FILE! %s" % exc)

    return modules


def _extract_downloads_from_conan_trace(path):
    downloaded_modules = defaultdict(dict)  # dict of {conan_ref: {"files": [doc_file, doc_file], "remote": remote }}

    with open(path, "r") as traces:
        for line in traces.readlines():
            doc = json.loads(line)
            if doc["_action"] in ["DOWNLOADED_PACKAGE", "DOWNLOADED_RECIPE"]:
                downloaded_modules[doc["_id"]] = {"files": doc["files"], "remote": doc["remote"]}
    return downloaded_modules


def _get_type(file_path):
    return os.path.splitext(file_path)[1].upper()[1:]


def _get_build_info_artifact(file_doc):
    the_type = _get_type(file_doc["path"])
    ret = BuildInfoModuleArtifact(the_type, file_doc["sha1"], file_doc["md5"], file_doc["name"])
    return ret


def _get_dependency(file_doc, dep_ref):
    the_type = _get_type(file_doc["path"])
    the_id = "%s:%s" % (dep_ref, file_doc["name"])
    ret = BuildInfoModuleDependency(the_id, the_type, file_doc["sha1"], file_doc["md5"])
    return ret


def _get_upload_modules_with_deps(uploaded_files, downloaded_files):
    modules = []
    deps = defaultdict(set)  # Reference: [Reference, Reference]
    # Extract needed information
    for module_id, mod_doc in uploaded_files.items():
        module_id = ConanFileReference.loads(module_id) if mod_doc["type"] == "recipe" \
            else PackageReference.loads(module_id)
        # Store recipe and package dependencies
        if mod_doc["type"] == "package":
            conan_infos = [file_doc for file_doc in mod_doc["files"]
                           if file_doc["name"] == "conaninfo.txt"]
            if conan_infos:
                conan_info = conan_infos[0]["path"]
                info = ConanInfo.loads(load(conan_info))
                for package_reference in info.full_requires:
                    deps[str(module_id.conan)].add(str(package_reference.conan))
                    deps[str(module_id)].add(str(package_reference))

    # Add the modules
    for module_id, mod_doc in uploaded_files.items():
        module = BuildInfoModule()
        module.id = str(module_id)
        # Add artifacts
        for file_doc in mod_doc["files"]:
            artifact = _get_build_info_artifact(file_doc)
            module.artifacts.append(artifact)

        # Add dependencies, for each module dep modules
        for mod_dep_id in deps[module_id]:
            if mod_dep_id in downloaded_files:
                down_module = downloaded_files[mod_dep_id]
                # Check if the remote from the uploaded package matches the remote from the downloaded dependency
                if down_module.get("remote", None) == mod_doc["remote"]:
                    for file_doc in down_module["files"]:
                        module.dependencies.append(_get_dependency(file_doc, mod_dep_id))

        modules.append(module)
    return modules


def _get_only_downloads_module(downloaded_files):
    """
    Gets a BuildInfoModule for the downloaded_files
    :param downloaded_files: {conan_ref: {"files": [doc_file, doc_file], "remote": remote }}
    :return: BuildInfoModule object
    """
    ret = BuildInfoModule()
    ret.id = "DownloadOnly"
    for _, file_docs in downloaded_files.items():
        files = file_docs["files"]
        for file_doc in files:
            the_type = _get_type(file_doc["path"])
            dep = BuildInfoModuleDependency(file_doc["name"], the_type, file_doc["sha1"],
                                            file_doc["md5"])
            ret.dependencies.append(dep)
    return ret


def _build_modules(trace_path):
    uploaded_files = _extract_uploads_from_conan_trace(trace_path)
    downloaded_files = _extract_downloads_from_conan_trace(trace_path)
    if uploaded_files:
        return _get_upload_modules_with_deps(uploaded_files, downloaded_files)
    else:
        return [_get_only_downloads_module(downloaded_files)]


def get_build_info(trace_path):
    bi = BuildInfo()
    modules = _build_modules(trace_path)
    bi.modules.extend(modules)
    return bi
