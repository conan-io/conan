import os
import shutil

from conans.util.files import save
from conans.model.manifest import FileTreeManifest
from conans.paths import BUILD_INFO_DEPLOY
from conans.util.dates import timestamp_now
from conans.util.files import mkdir, md5sum


FILTERED_FILES = ["conaninfo.txt", "conanmanifest.txt"]


class DeployGenerator:
    def __init__(self, conanfile):
        self._conanfile = conanfile
        # TODO: check if we want to output to another folder
        self._output_folder = self._conanfile.generators_folder

    def manifest_content(self, copied_files):
        date = timestamp_now()
        file_dict = {}
        for f in copied_files:
            abs_path = os.path.join(self._output_folder, f)
            file_dict[f] = md5sum(abs_path)
        manifest = FileTreeManifest(date, file_dict)
        return repr(manifest)

    @property
    def manifest_path(self):
        return os.path.join(self._output_folder, BUILD_INFO_DEPLOY)

    def generate(self):
        copied_files = []

        for transitive in self._conanfile.dependencies.host.values():

            rootpath = transitive.folders.package_folder
            for root, dirs, files in os.walk(os.path.normpath(rootpath)):
                files += [d for d in dirs if os.path.islink(os.path.join(root, d))]
                for f in files:
                    if f in FILTERED_FILES:
                        continue
                    src = os.path.normpath(os.path.join(root, f))
                    dst = os.path.join(self._output_folder, transitive.ref.name,
                                       os.path.relpath(root, rootpath), f)
                    dst = os.path.normpath(dst)
                    mkdir(os.path.dirname(dst))
                    if os.path.islink(src):
                        link_target = os.readlink(src)
                        if not os.path.isabs(link_target):
                            link_target = os.path.join(os.path.dirname(src), link_target)
                        linkto = os.path.relpath(link_target, os.path.dirname(src))
                        if os.path.isfile(dst) or os.path.islink(dst):
                            os.unlink(dst)
                        os.symlink(linkto, dst)
                    else:
                        shutil.copy(src, dst)
                    if f not in dirs:
                        copied_files.append(dst)

        save(self.manifest_path, self.manifest_content(copied_files))
