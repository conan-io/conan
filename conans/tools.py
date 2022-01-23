"""
    Conan tools: classes and function in this module are intended to be used out of the box
    with the Conan configuration already currified into them. This configuration refers
    mainly to two items:
     - requester: on network calls, this will include proxy definition.
     - output: the output configuration

    Here in this module there should be no logic, all functions and classes must be implemented
    elsewhere (mainly in conans.util or conans.client.tools) and ready to be used without
    the currification.
"""

# Tools from conans.client.tools
from conans.client.tools import files as tools_files

from conans.client.tools.scm import *  # pylint: disable=unused-import
from conans.client.tools.settings import *  # pylint: disable=unused-import
from conans.client.tools.apple import *
# Tools form conans.util
from conans.util.files import _generic_algorithm_sum, load, md5, md5sum, mkdir, rmdir, save as files_save, save_append, sha1sum, sha256sum, to_file_bytes, touch


"""
From here onwards only currification is expected, no logic
"""


def save(path, content, append=False):
    # TODO: All this three functions: save, save_append and this one should be merged into one.
    if append:
        save_append(path=path, content=content)
    else:
        files_save(path=path, content=content, only_if_modified=False)


# from conans.client.tools.files
chdir = tools_files.chdir
untargz = tools_files.untargz
check_with_algorithm_sum = tools_files.check_with_algorithm_sum
check_sha1 = tools_files.check_sha1
check_md5 = tools_files.check_md5
check_sha256 = tools_files.check_sha256
replace_prefix_in_pc_file = tools_files.replace_prefix_in_pc_file
collect_libs = tools_files.collect_libs
which = tools_files.which
remove_files_by_mask = tools_files.remove_files_by_mask


def unzip(*args, **kwargs):
    return tools_files.unzip(*args, **kwargs)


def replace_in_file(*args, **kwargs):
    return tools_files.replace_in_file(*args, **kwargs)


def replace_path_in_file(*args, **kwargs):
    return tools_files.replace_path_in_file(*args, **kwargs)
