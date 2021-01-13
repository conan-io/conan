# coding=utf-8

import os
import textwrap

from conans.client.tools import environment_append


class TestWorkflow(object):
    """ This class implements a conan package with some tests (local and remote workflow)"""

    path_to_conanfile = None
    path_from_conanfile_to_root = None
    scm_subfolder = ""

    conanfile_base = textwrap.dedent("""\
        import os
        from conans import ConanFile, tools

        {extra_header}

        class Pkg(ConanFile):
            scm = {{"type": "{type}",
                   "url": {url},
                   "revision": "auto",
                   "subfolder": "{scm_subfolder}" }}

            def source(self):
                self.output.info(self.source_folder)
                content = tools.load(os.path.join(self.source_folder, "{scm_subfolder}", "file.txt"))
                self.output.info(">>>> I'm {{}}/{{}}@{{}}/{{}}".format(self.name, self.version,
                                                                       self.user, self.channel))
                self.output.info(">>>> content: {{}} ".format(content))
        """)

    def get_files(self, subfolder, conanfile, lib_ref):
        return {os.path.join(subfolder, self.path_to_conanfile, 'conanfile.py'): conanfile,
                os.path.join(subfolder, 'file.txt'): lib_ref}

    def run(self, *args, **kwargs):
        # path_to_conanfile and path_from_conanfile_to_root must be opposite ones.
        self.assertEqual(os.path.normpath(os.path.join(self.path_to_conanfile,
                                                       self.path_from_conanfile_to_root)),
                         '.')

        with environment_append({'CONAN_USERNAME': "user", "CONAN_CHANNEL": "channel"}):
            super(TestWorkflow, self).run(*args, **kwargs)

    def _run_local_test(self, t, working_dir, path_to_conanfile):
        old_wd = t.current_folder
        try:
            path_to_conanfile = path_to_conanfile.replace('\\', '/')
            t.current_folder = working_dir
            t.run("install {} -if tmp".format(path_to_conanfile))
            t.run("source {} -if tmp -sf src".format(path_to_conanfile))
            self.assertIn(">>>> I'm None/None@user/channel".format(self.lib1_ref), t.out)
            self.assertIn(">>>> content: {}".format(self.lib1_ref), t.out)
        finally:
            t.current_folder = old_wd

    def _run_remote_test(self, t, working_dir, path_to_conanfile):
        old_wd = t.current_folder
        try:
            path_to_conanfile = path_to_conanfile.replace('\\', '/')
            t.current_folder = working_dir
            t.run("create {} {}".format(path_to_conanfile, self.lib1_ref))
            self.assertIn(">>>> I'm {}".format(self.lib1_ref), t.out)
            self.assertIn(">>>> content: {}".format(self.lib1_ref), t.out)
        finally:
            t.current_folder = old_wd
