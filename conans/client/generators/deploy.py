import calendar
import os
import shutil
import time

from conans.model import Generator
from conans.model.manifest import FileTreeManifest
from conans.paths import BUILD_INFO_DEPLOY
from conans.util.files import mkdir, md5sum


FILTERED_FILES = ["conaninfo.txt", "conanmanifest.txt"]


class DeployGenerator(Generator):

    def deploy_manifest_content(self, copied_files):
        date = calendar.timegm(time.gmtime())
        file_dict = {}
        for f in copied_files:
            abs_path = os.path.join(self.output_path, f)
            file_dict[f] = md5sum(abs_path)
        manifest = FileTreeManifest(date, file_dict)
        return repr(manifest)

    @property
    def filename(self):
        return BUILD_INFO_DEPLOY

    @property
    def content(self):
        copied_files = []

        for dep_name in self.conanfile.deps_cpp_info.deps:
            rootpath = self.conanfile.deps_cpp_info[dep_name].rootpath
            for root, dirs, files in os.walk(os.path.normpath(rootpath)):
                files += [d for d in dirs if os.path.islink(os.path.join(root, d))]
                for f in files:
                    if f in FILTERED_FILES:
                        continue
                    src = os.path.normpath(os.path.join(root, f))
                    dst = os.path.join(self.output_path, dep_name,
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
        return self.deploy_manifest_content(copied_files)
