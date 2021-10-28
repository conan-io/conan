import copy
import os
import shutil

from conans import tools
from conans.client.file_copier import FileCopier


class active_conanfile:
    """ Handle variant conanfiles in scope.
        Currently just patch the shared output.
    """
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._display_name = None

    def __enter__(self):
        self._display_name = self._conanfile.output.scope
        self._conanfile.output.scope = self._conanfile.display_name

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._display_name is not None:
            self._conanfile.output.scope = self._display_name


class Variants(object):
    """ The mix-in class for all recipes with variant builds.
    MRO is different depending on class hierarchy.
    By default, we the final class inherits like this:

        class MyConanFile(ConanFile):
            def build(self):
                pass

        class MyVariants(Variants, MyConanFile):
            pass

    In this case, super() will return MyConanFile.

    A common approach is to subclass Variants, which requires overriding conanfile():

        class MyVariants(Variants):
            def conanfile(self):
                return super()

        class MyConanFile(MyVariants, ConanFile):
            def build_variant(self):
                pass

    build() is inherited from Variants so build_variant is implemented instead.

    This is the same hierarchy if pyreq is used:

        class MyConanFile(ConanFile):
            python_requires = "variants_pyreq/1.0@user/testing"
            python_requires_extend = "variants_pyreq.MyVariants"
            def build_variant(self):
                pass

    build(), package(), and test() are all defined which will override the ConanFile methods,
    except in the first case.  Either implement build_variant(), package_variant(), etc. or
    define a new method like this:

        class MyConanFile(MyVariants, ConanFile):
            def package_variant(self):
                # package one arch only
                pass
            def package(self):
                # Before individual archs
                self.package_variants()
                # After individual archs
    """

    """ name of the subfolder to build variants """
    variants_folder = "variants"
    reserved_settings = "display_name", "folder"

    def __init__(self, *args, **kwargs):
        super(Variants, self).__init__(*args, **kwargs)
        self._conanfiles = None
        self._source_variants = False

    def __iter__(self):
        """ iterate over variant conanfiles, or just self
        """
        self.create_variants()
        if not self._conanfiles:
            yield self
        else:
            for conanfile in self._conanfiles:
                with active_conanfile(conanfile):
                    yield conanfile

    def conanfile(self):
        """ Find the ConanFile class.  See Variants docstring. """
        c = super(Variants, self)
        assert hasattr(c, "build"), c
        return c

    def enable_variants(self, enabled=True, source=False):
        """ Enable variants and indicate if source folder has variant copies. """
        if enabled:
            if not self._conanfiles:
                self._conanfiles = None
            self._source_variants = source
        else:
            self._conanfiles = []

    def variants(self):
        """ Return enabled variants.  Can be overridden to check settings. """
        return self._variants

    def set_variants(self, variants):
        """ enable variants from user conanfile (str or list).
        If dict is not provided assume 'arch'.
        self.set_variants("x86_64 armv8")
        self.set_variants(self.settings.multiarch)
        self.set_variants([
            {"arch": "x86_64", "os.version": "10.13", "display_name": "Intel"},
            {"arch": "armv8", "os.version": "11.0", "display_name": "M1"},
        ])
        """
        if not variants:
            self._variants = []
            return
        elif isinstance(variants, (list, tuple)):
            if hasattr(variants[0], "items"):
                self._variants = variants
                return
            v = variants
        else:
            v = str(variants).split();
        self._variants = [{ "arch": arch, "display_name": arch } for arch in v]

    @staticmethod
    def get_variant_basename(variant):
        if "folder" in variant:
            return variant["folder"]
        return variant["display_name"]

    @staticmethod
    def get_variant_folder(basename, variant):
        folder = Variants.get_variant_basename(variant)
        if basename:
            return os.path.join(basename, Variants.variants_folder, folder)
        return basename

    def new_conanfile(self, variant):
        """ clone this instance (including ConanFile) and point folders to variant subfolders
        """
        # clone is defined on ConanFile but might be overridden.
        conanfile = self.clone()
        display_name = variant.get("display_name", None)
        if display_name:
            conanfile.display_name = "%s[%s]" % (conanfile.display_name, display_name)
        for k, v in variant.items():
            if k not in self.reserved_settings:
                conanfile.settings.update_values([(k, v)])
        if self._source_variants:
            conanfile.source_folder = self.get_variant_folder(self.source_folder, variant)
        if self.build_folder is not None:
            conanfile.build_folder = self.get_variant_folder(self.build_folder, variant)
        if self.install_folder is not None:
            conanfile.install_folder = self.get_variant_folder(self.install_folder, variant)
        if self.package_folder is not None:
            conanfile.package_folder = self.get_variant_folder(self.package_folder, variant)
        return conanfile

    def create_variants(self):
        """ Clone and cached conanfiles.  They might store local attributes so caching is required.
        """
        if self._conanfiles is not None:
            return self._conanfiles
        variants = self.variants()
        # new_conanfile calls self.clone() so set attributes last.
        self._conanfiles = [self.new_conanfile(v) for v in (variants or ())]

    def copy_sources(self, build_folder):
        """ copy source directory to variant folders
        """
        variants = self.variants()
        # Don't create the variant conanfiles yet.
        for variant in (variants or ()):
            folder = self.get_variant_folder(build_folder, variant)
            if build_folder != folder:
                def ignore_variants(path, files):
                    if path == build_folder:
                        if Variants.variants_folder in files:
                            return [Variants.variants_folder]
                    return [] # ignore nothing
                shutil.copytree(build_folder,
                                folder,
                                symlinks=True,
                                ignore=ignore_variants)
        self._source_variants = True

    def _build_variant(self):
        with tools.chdir(self.build_folder):
            self.build_variant()

    def build_variant(self):
        self.conanfile().build()

    def build_variants(self):
        for conanfile in self:
            conanfile._build_variant()

    def build(self):
        return self.build_variants()

    def _package_variant(self):
        folders = [self.source_folder, self.build_folder]
        self.copy = FileCopier(folders, self.package_folder)
        with tools.chdir(self.build_folder):
            self.output.info("packaging variant: %s" % self.display_name)
            self.package_variant()

    def package_variant(self):
        self.conanfile().package()

    def package_variants(self):
        for conanfile in self:
            if conanfile is self:
                self.package_variant()
            else:
                conanfile._package_variant()

    def package(self):
        return self.package_variants()

    def _test_variant(self):
        with tools.chdir(self.build_folder):
            self.test_variant()

    def test_variant(self):
        self.conanfile().test()

    def test_variants(self):
        for conanfile in self:
            conanfile._test_variant()

    def test(self):
        return self.test_variants()

    def package_id_variants(self):
        """ combine settings from all variants to produce new package_id """
        variants = self.variants()
        if not variants:
            return self.conanfile().package_id()
        for field in variants[0].keys():
            if field not in self.reserved_settings:
                value = ' '.join([str(v[field]) for v in variants])
                # Values currently does not have a method to set,
                # for example, "os.version"
                tokens = field.split(".")
                attr = self.info.settings
                for token in tokens[:-1]:
                    attr = getattr(attr, token)
                    if attr is None:
                        raise ConanException("%s not defined for %s\n"
                                             "Please define %s value first too"
                                             % (token, field, token))
                    setattr(attr, tokens[-1], value)
        return self.conanfile().package_id()

    def package_id(self):
        return self.package_id_variants()
