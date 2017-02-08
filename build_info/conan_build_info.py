import json
import os
from collections import defaultdict

from build_info.model import BuildInfo, BuildInfoModule, BuildInfoModuleArtifact, BuildInfoModuleDependency
from conans.model.info import ConanInfo, PackageReference
from conans.model.ref import ConanFileReference
from conans.util.files import sha1sum, md5sum, load


def _extract_from_conan_trace(path):
    modules = defaultdict(list)  # dict of {conan_ref: [abs_path1, abs_path2]}

    with open(path, "r") as traces:
        for line in traces.readlines():
            doc = json.loads(line)
            if doc["_action"] in ("UPLOADED_RECIPE", "UPLOADED_PACKAGE"):
                module_type = "recipe" if doc["_action"] == "UPLOADED_RECIPE" else "package"
                for a_file in doc["files"].values():
                    modules[(doc["_id"], module_type)].append(a_file)
    return modules


def _get_type(file_path):
    return os.path.splitext(file_path)[1].upper()[1:]


def _get_build_info_artifact(file_path):
    the_type = _get_type(file_path)
    name = os.path.basename(file_path)
    sha1 = sha1sum(file_path)
    md5 = md5sum(file_path)

    artifact = BuildInfoModuleArtifact(the_type, sha1, md5, name)
    return artifact


def _detect_storage_path(mods):
    for (module_id, module_type), files in mods.items():
        if module_type == "recipe":
            tmp_path = os.path.sep.join(ConanFileReference.loads(module_id))
            base, rest = files[0].split(tmp_path, 1)
            if base:
                return base
    return None


def _build_modules(trace_path):
    modules = []
    mods = _extract_from_conan_trace(trace_path)
    recipe_deps = defaultdict(set)  # Reference: [Reference, Reference]
    package_deps = defaultdict(set)
    modules_files = defaultdict(set)
    storage_path = _detect_storage_path(mods)

    # Extract needed information
    for (module_id, module_type), files in mods.items():
        module_id = ConanFileReference.loads(module_id) if module_type == "recipe" \
                                                        else PackageReference.loads(module_id)
        for the_file in files:
            modules_files[(module_id, module_type)].add(the_file)
        # Store recipe and package dependencies
        if module_type == "package":
            conan_infos = filter(lambda x: True if x.endswith("conaninfo.txt") else False, files)
            if conan_infos:
                conan_info = conan_infos[0]
                info = ConanInfo.loads(load(conan_info))
                for package_reference in info.full_requires:
                    recipe_deps[module_id.conan].add(package_reference.conan)
                    package_deps[module_id].add(package_reference)

    # Add the modules
    for (module_id, module_type), files in modules_files.items():
        module = BuildInfoModule()
        module.id = str(module_id)
        # Add artifacts
        for the_file in files:
            artifact = _get_build_info_artifact(the_file)
            module.artifacts.append(artifact)
        # Add dependencies
        if module_type == "recipe":
            for recipe_dep in recipe_deps[module_id]:
                base_dep_dir = os.path.join(storage_path, os.path.sep.join(recipe_dep), "export")
                module.dependencies.extend(_get_dependencies_from_path(base_dep_dir, recipe_dep))
        elif module_type == "package":
            for package_dep in package_deps[module_id]:
                base_dep_dir = os.path.join(storage_path, os.path.sep.join(package_dep.conan), "package", package_dep.package_id)
                module.dependencies.extend(_get_dependencies_from_path(base_dep_dir, package_dep))

        modules.append(module)

    return modules


def _get_dependencies_from_path(path, module_id):
    if not os.path.exists(path):
        return []

    arts = []
    for root, _, files in os.walk(path):
        for the_file in files:

            if the_file != "conan_package.tgz":
                continue
            print(the_file)
            full_path = os.path.join(root, the_file)
            sha1 = sha1sum(full_path)
            md5 = md5sum(full_path)
            the_type = _get_type(full_path)
            the_id = str(module_id) + ":" + the_file
            bi = BuildInfoModuleDependency(the_id, the_type, sha1, md5)
            arts.append(bi)
    return arts


def get_build_info(trace_path):
    bi = BuildInfo()
    modules = _build_modules(trace_path)
    bi.modules.extend(modules)
    return bi
