import os
import stat
import textwrap

from jinja2 import Template

from conans.client.envvars.environment import BAT_FLAVOR, SH_FLAVOR, env_files
from conans.util.files import save_files

cmd_template = textwrap.dedent("""\
    echo Calling {{ name }} wrapper
    call "{{ activate_path }}"
    pushd "{{ exe_path_dirname }}"
    call "{{ exe_path }}" %*
    popd
    call "{{ deactivate_path }}"
    """)

sh_template = textwrap.dedent("""\
    #!/bin/bash
    echo Calling {{ name }} wrapper
    source "{{ activate_path }}"
    pushd "{{ exe_path_dirname }}" > /dev/null
    "{{ exe_path }}" "$@"
    popd > /dev/null
    source "{{ deactivate_path }}"
    """)


def _envvariables(deps_cpp_info):
    # TODO: Refactor, this code is duplicated
    # TODO: Other environment variables should be considered too
    lib_paths = deps_cpp_info.lib_paths
    bin_paths = deps_cpp_info.bin_paths
    framework_paths = deps_cpp_info.framework_paths
    ret = {"DYLD_LIBRARY_PATH": lib_paths,
           "LD_LIBRARY_PATH": lib_paths,
           "PATH": bin_paths}
    if framework_paths:
        ret["DYLD_FRAMEWORK_PATH"] = framework_paths
    return ret


def _generate_shim(name, deps_cpp_info, settings_os, output_path):
    # Use the environment generators we already have
    suffix = "_{}".format(name)
    environment = _envvariables(deps_cpp_info)
    flavor = BAT_FLAVOR if settings_os == 'Windows' else SH_FLAVOR
    shimfiles = env_files(environment, [], flavor, os.path.join(output_path, '.shims'), suffix, name)
    shimfiles = {os.path.join('.shims', k): v for k, v in shimfiles.items()}

    # Create the wrapper for the given OS
    executable = os.path.join(deps_cpp_info.bin_paths[0], name)  # TODO: More than one bin_path?
    context = {
        'name': name,
        'activate_path': os.path.join(output_path, '.shims', "activate{}.{}".format(suffix, flavor)),
        'exe_path_dirname': os.path.dirname(executable),
        'exe_path': executable,
        'deactivate_path': os.path.join(output_path, '.shims',
                                        "deactivate{}.{}".format(suffix, flavor))
    }
    template = cmd_template if settings_os == 'Windows' else sh_template
    content = Template(template).render(**context)
    extension = '.cmd' if settings_os == 'Windows' else ""
    shimfiles.update({'{}{}'.format(name, extension): content})
    return shimfiles


def write_shim(name, deps_cpp_info, settings_os, output_path):
    files = _generate_shim(name, deps_cpp_info, settings_os, output_path)
    save_files(output_path, files)
    exe_filename = "{}{}".format(name, ".cmd" if settings_os == 'Windows' else '')
    exe_filepath = os.path.join(output_path, exe_filename)
    st = os.stat(exe_filepath)
    os.chmod(exe_filepath, st.st_mode | stat.S_IEXEC)
