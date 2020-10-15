import os
import stat
import textwrap

from jinja2 import Template

from conans.client.envvars.environment import BAT_FLAVOR, SH_FLAVOR, env_files
from conans.client.run_environment import RunEnvironment
from conans.util.files import save_files

cmd_template = textwrap.dedent("""\
    @echo off
    call "{{ activate_path }}"
    pushd "{{ exe_path_dirname }}"
    call "{{ exe_path }}" %*
    popd
    call "{{ deactivate_path }}"
    """)

sh_template = textwrap.dedent("""\
    #!/bin/bash
    source "{{ activate_path }}"
    pushd "{{ exe_path_dirname }}" > /dev/null
    "{{ exe_path }}" "$@"
    popd > /dev/null
    source "{{ deactivate_path }}"
    """)


def _generate_shim(name, conanfile, settings_os, output_path):
    # Use the environment generators we already have
    suffix = "_{}".format(name)
    environment = RunEnvironment(conanfile).vars
    for k, v in conanfile.env_info.vars.items():
        environment[k] = v  # TODO: Append to known variables

    flavor = BAT_FLAVOR if settings_os == 'Windows' else SH_FLAVOR
    shimfiles = env_files(environment, [], flavor, output_path, suffix, name)

    # Create the wrapper for the given OS
    bin_folder = conanfile.cpp_info.bin_paths[0]  # TODO: More than one bin_path?
    executable = os.path.join(bin_folder, name)
    context = {
        'name': name,
        'activate_path': os.path.join(output_path, "activate{}.{}".format(suffix, flavor)),
        'exe_path_dirname': os.path.dirname(executable),
        'exe_path': executable,
        'deactivate_path': os.path.join(output_path, "deactivate{}.{}".format(suffix, flavor))
    }
    template = cmd_template if settings_os == 'Windows' else sh_template
    content = Template(template).render(**context)
    extension = '.cmd' if settings_os == 'Windows' else ""
    shimfiles.update({'{}{}'.format(name, extension): content})
    return shimfiles


def write_shims(conanfile, settings_os, output_path):
    for name in conanfile.cpp_info.exes:
        files = _generate_shim(name, conanfile, settings_os, output_path)
        save_files(output_path, files)
        exe_filename = "{}{}".format(name, ".cmd" if settings_os == 'Windows' else '')
        exe_filepath = os.path.join(output_path, exe_filename)
        st = os.stat(exe_filepath)
        os.chmod(exe_filepath, st.st_mode | stat.S_IEXEC)
