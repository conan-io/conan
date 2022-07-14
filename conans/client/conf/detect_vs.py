import json
import os
from shutil import which

from conan.tools.build import cmd_args_to_string
from conan.api.output import ConanOutput
from conans.errors import ConanException
from conans.model.version import Version
from conans.util.env import get_env


def _visual_compiler(version):
    """"version have to be 8.0, or 9.0 or... anything .0"""
    if Version(version) >= "15":
        vs_path = os.getenv('vs%s0comntools' % version)
        path = vs_path or vs_installation_path(version)
        if path:
            ConanOutput().success("Found msvc %s" % version)
            return version
    return None


def latest_visual_studio_version_installed():
    msvc_sersions = "17", "16", "15"
    for version in msvc_sersions:
        vs = _visual_compiler(version)
        if vs:
            return {"17": "193", "16": "192", "15": "191"}.get(vs)
    return None


def vs_installation_path(version):
    # TODO: Preference hardcoded, [conf] must be defined
    preference = ["Enterprise", "Professional", "Community", "BuildTools"]

    # Try with vswhere()
    try:
        legacy_products = vswhere(legacy=True)
        all_products = vswhere(products=["*"])
        products = legacy_products + all_products
    except ConanException:
        products = None

    vs_paths = []

    if products:
        # remove repeated products
        seen_products = []
        for product in products:
            if product not in seen_products:
                seen_products.append(product)

        # Append products with "productId" by order of preference
        for product_type in preference:
            for product in seen_products:
                product = dict(product)
                if (product["installationVersion"].startswith(("%d." % int(version)))
                        and "productId" in product):
                    if product_type in product["productId"]:
                        vs_paths.append(product["installationPath"])

        # Append products without "productId" (Legacy installations)
        for product in seen_products:
            product = dict(product)
            if (product["installationVersion"].startswith(("%d." % int(version)))
                    and "productId" not in product):
                vs_paths.append(product["installationPath"])

    # If vswhere does not find anything or not available, try with vs_comntools
    if not vs_paths:
        env_var = "vs%s0comntools" % version
        vs_path = os.getenv(env_var)

        if vs_path:
            sub_path_to_remove = os.path.join("", "Common7", "Tools", "")
            # Remove '\\Common7\\Tools\\' to get same output as vswhere
            if vs_path.endswith(sub_path_to_remove):
                vs_path = vs_path[:-(len(sub_path_to_remove)+1)]

        result_vs_installation_path = vs_path
    else:
        result_vs_installation_path = vs_paths[0]

    return result_vs_installation_path


def vswhere(all_=False, prerelease=False, products=None, requires=None, version="", latest=False,
            legacy=False, property_="", nologo=True):

    # 'version' option only works if Visual Studio 2017 is installed:
    # https://github.com/Microsoft/vswhere/issues/91

    products = list() if products is None else products
    requires = list() if requires is None else requires

    if legacy and (products or requires):
        raise ConanException("The 'legacy' parameter cannot be specified with either the "
                             "'products' or 'requires' parameter")

    installer_path = None
    program_files = get_env("ProgramFiles(x86)") or get_env("ProgramFiles")
    if program_files:
        expected_path = os.path.join(program_files, "Microsoft Visual Studio", "Installer",
                                     "vswhere.exe")
        if os.path.isfile(expected_path):
            installer_path = expected_path
    vswhere_path = installer_path or which("vswhere")

    if not vswhere_path:
        raise ConanException("Cannot locate vswhere in 'Program Files'/'Program Files (x86)' "
                             "directory nor in PATH")

    arguments = list()
    arguments.append(vswhere_path)

    # Output json format
    arguments.append("-format")
    arguments.append("json")

    if all_:
        arguments.append("-all")

    if prerelease:
        arguments.append("-prerelease")

    if products:
        arguments.append("-products")
        arguments.extend(products)

    if requires:
        arguments.append("-requires")
        arguments.extend(requires)

    if len(version) != 0:
        arguments.append("-version")
        arguments.append(version)

    if latest:
        arguments.append("-latest")

    if legacy:
        arguments.append("-legacy")

    if len(property_) != 0:
        arguments.append("-property")
        arguments.append(property_)

    if nologo:
        arguments.append("-nologo")

    try:
        from conans.util.runners import check_output_runner
        cmd = cmd_args_to_string(arguments)
        output = check_output_runner(cmd).strip()
        # Ignore the "description" field, that even decoded contains non valid charsets for json
        # (ignored ones)
        output = "\n".join([line for line in output.splitlines()
                            if not line.strip().startswith('"description"')])

    except (ValueError, UnicodeDecodeError) as e:
        raise ConanException("vswhere error: %s" % str(e))

    return json.loads(output)
