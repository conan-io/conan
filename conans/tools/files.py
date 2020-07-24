from conans.client.tools import files as tools_files


chdir = tools_files.chdir
human_size = tools_files.human_size
untargz = tools_files.untargz
check_with_algorithm_sum = tools_files.check_with_algorithm_sum
check_sha1 = tools_files.check_sha1
check_md5 = tools_files.check_md5
check_sha256 = tools_files.check_sha256
patch = tools_files.patch
replace_prefix_in_pc_file = tools_files.replace_prefix_in_pc_file
collect_libs = tools_files.collect_libs
which = tools_files.which
unix2dos = tools_files.unix2dos
dos2unix = tools_files.dos2unix
fix_symlinks = tools_files.fix_symlinks

def save(path, content, append=False):
    # TODO: All this three functions: save, save_append and this one should be merged into one.
    from conans.util import files
    if append:
        files.save_append(path=path, content=content)
    else:
        files.save(path=path, content=content, only_if_modified=False)


def unzip(conanfile, *args, **kwargs):
    return tools_files.unzip(output=conanfile.conanfile, *args, **kwargs)


def replace_in_file(conanfile, *args, **kwargs):
    return tools_files.replace_in_file(output=conanfile.output, *args, **kwargs)


def replace_path_in_file(conanfile, *args, **kwargs):
    return tools_files.replace_path_in_file(output=conanfile.output, *args, **kwargs)

