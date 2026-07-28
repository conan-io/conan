from collections import Counter
from unittest import mock
import os
import platform
import pytest

from conan.errors import ConanException
from conan.tools.files import copy
from conan.test.utils.test_files import temp_folder
from conan.internal.util.files import load, save, mkdir, save_files, chdir


def _folders_opened_by_copy(pattern, src, dst):
    """ The folders of ``src`` (relative names) that copy() opens looking for matches, one entry
    per open. It counts os.scandir() calls, because that is what scanning a tree costs and
    because os.walk() opens each folder with exactly one scandir() in every Python version
    """
    opened = []
    real_scandir = os.scandir

    def counting_scandir(path, *args, **kwargs):
        opened.append(os.path.relpath(path, src))
        return real_scandir(path, *args, **kwargs)

    with mock.patch("os.scandir", counting_scandir):
        copy(None, pattern, src, dst)
    return opened


class TestToolCopy:

    def test_basic(self):
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "subdir1")
        sub2 = os.path.join(folder1, "subdir2")
        save(os.path.join(sub1, "file1.txt"), "hello1")
        save(os.path.join(sub1, "file2.c"), "Hello2")
        save(os.path.join(sub1, "sub1/file1.txt"), "Hello1 sub")
        save(os.path.join(sub1, "sub1/file2.c"), "Hello2 sub")
        save(os.path.join(sub2, "file1.txt"), "2 Hello1")
        save(os.path.join(sub2, "file2.c"), "2 Hello2")

        folder2 = temp_folder()
        copy(None, "*.txt", folder1, os.path.join(folder2, "texts"))
        assert "hello1" == load(os.path.join(folder2, "texts/subdir1/file1.txt"))
        assert "Hello1 sub" == load(os.path.join(folder2, "texts/subdir1/sub1/file1.txt"))
        assert "2 Hello1" == load(os.path.join(folder2, "texts/subdir2/file1.txt"))
        assert ['file1.txt'] == os.listdir(os.path.join(folder2, "texts/subdir2"))

        folder2 = temp_folder()
        copy(None, "*.txt", os.path.join(folder1, "subdir1"), os.path.join(folder2, "texts"))
        assert "hello1" == load(os.path.join(folder2, "texts/file1.txt"))
        assert "Hello1 sub" == load(os.path.join(folder2, "texts/sub1/file1.txt"))
        assert "subdir2" not in os.listdir(os.path.join(folder2, "texts"))

    @pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
    def test_symlinks_folder_behavior(self):
        """
        https://github.com/conan-io/conan/issues/11150

        test.h
        inc/test2.h
        gen/test.bin
        sym/ => gen
        """

        build_folder = temp_folder()
        test = os.path.join(build_folder, "test.h")
        save(test, "")
        inc_folder = os.path.join(build_folder, "inc")
        mkdir(inc_folder)
        test2 = os.path.join(inc_folder, "test2.h")
        save(test2, "")
        gen_folder = os.path.join(build_folder, "gen")
        mkdir(gen_folder)
        binfile = os.path.join(gen_folder, "test.bin")
        save(binfile, "")
        sym_folder = os.path.join(build_folder, "sym")
        os.symlink(gen_folder, sym_folder)

        package_folder = temp_folder()
        # Pattern with the sym/*.bin won't work, "sym" is a file (symlink to folder), not a folder
        copy(None, "sym/*.bin", build_folder, package_folder)
        assert not os.path.exists(os.path.join(package_folder, "sym"))

        # Pattern searches in the "inc/" subfolder, "sym/" shouldn't be copied
        copy(None, "inc/*.h", build_folder, package_folder)
        assert not os.path.exists(os.path.join(package_folder, "sym")), \
            "The sym file shouldn't exist in package_folder"

        # Even if there is a test.bin "inside" the "sym/" (gen/), the "sym" file shouldn't be copied
        # because it is a file, the pattern has to match the file
        copy(None, "*.bin", build_folder, package_folder)
        assert not os.path.exists(os.path.join(package_folder, "sym")), \
            "The sym file shouldn't exist in package_folder"

        # If the pattern matches the "sym" file, it will be copied (as a symlink)
        copy(None, "s*", build_folder, package_folder)
        assert os.path.exists(os.path.join(package_folder, "sym"))
        assert os.path.islink(os.path.join(package_folder, "sym"))

    @pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
    def test_linked_relative(self):
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "foo/other/file")
        save(os.path.join(sub1, "file.txt"), "Hello")
        sub2 = os.path.join(folder1, "foo/symlink")
        os.symlink("other/file", sub2)  # @UndefinedVariable

        folder2 = temp_folder()
        copy(None, "*", folder1, folder2)
        symlink = os.path.join(folder2, "foo", "symlink")
        assert os.path.islink(symlink)
        assert load(os.path.join(symlink, "file.txt")) == "Hello"

    @pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
    def test_linked_folder_nested(self):
        # https://github.com/conan-io/conan/issues/2959
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "lib/icu/60.2")
        sub2 = os.path.join(folder1, "lib/icu/current")
        os.makedirs(sub1)
        os.symlink("60.2", sub2)  # @UndefinedVariable

        folder2 = temp_folder()
        copied = copy(None, "*.cpp", folder1, folder2)
        assert copied == []

    @pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
    def test_linked_folder_copy_from_linked_folder(self):
        # https://github.com/conan-io/conan/issues/5114
        folder1 = temp_folder(path_with_spaces=False)
        sub_src = os.path.join(folder1, "sub/src")

        src = os.path.join(folder1, "src")
        src_dir = os.path.join(folder1, "src/dir")
        src_dir_link = os.path.join(folder1, "src/dir_link")
        src_dir_file = os.path.join(src_dir, "file.txt")

        dst = os.path.join(folder1, "dst")
        dst_dir = os.path.join(folder1, "dst/dir")
        dst_dir_link = os.path.join(folder1, "dst/dir_link")
        dst_dir_file = os.path.join(dst_dir, "file.txt")

        os.makedirs(dst)
        os.makedirs(sub_src)
        # input src folder should be a symlink
        os.symlink(sub_src, src)
        # folder, file and folder link to copy
        os.mkdir(src_dir)
        save(src_dir_file, "file")
        os.symlink(src_dir, src_dir_link)

        copied = copy(None, "dir/*", src, dst)

        # The pattern "dir/*" doesn't match to the symlink file "dir_link" so it is not copied
        assert copied == [dst_dir_file]
        assert not os.path.exists(dst_dir_link)

        # This pattern "dir*" match both the symlink "dir_link" and the folder "dir/"
        copied = copy(None, "dir*", src, dst)

        assert copied == [dst_dir_file, dst_dir_link]
        assert sorted(os.listdir(dst)) == sorted(os.listdir(src))
        assert os.path.islink(dst_dir_link)

    def test_excludes(self):
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "subdir1")
        save(os.path.join(sub1, "file1.txt"), "hello1")
        save(os.path.join(sub1, "file2.c"), "Hello2")

        folder2 = temp_folder()
        copy(None, "*.*", folder1, os.path.join(folder2, "texts"), excludes="*.c")
        assert ['file1.txt'] == os.listdir(os.path.join(folder2, "texts/subdir1"))

        folder1 = temp_folder()
        save(os.path.join(folder1, "MyLib.txt"), "")
        save(os.path.join(folder1, "MyLibImpl.txt"), "")
        save(os.path.join(folder1, "MyLibTests.txt"), "")

        folder2 = temp_folder()
        copy(None, "*.txt", folder1, folder2, excludes="*Test*.txt")
        assert {'MyLib.txt', 'MyLibImpl.txt'} == set(os.listdir(folder2))

        folder2 = temp_folder()
        copy(None, "*.txt", folder1, folder2, excludes=("*Test*.txt", "*Impl*"))
        assert ['MyLib.txt'] == os.listdir(folder2)

        folder1 = temp_folder()
        src_dir = os.path.join(folder1, "src_dir")
        dst_dir = os.path.join(folder1, "dst_dir")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)
        save(os.path.join(src_dir, "file"), "nothing")
        save(os.path.join(dst_dir, "file"), "nothing")
        copy(None, "*_dir*", folder1, folder2, excludes=["dst_dir", ])
        assert os.path.exists(os.path.join(folder2, "src_dir"))
        assert not os.path.exists(os.path.join(folder2, "dst_dir"))

    def test_excludes_hidden_files(self):
        folder1 = temp_folder()
        save_files(folder1, {
            "file1.txt": "",
            ".hiddenfile": "",
            "foo/file2.txt": "",
            "foo/.hiddenfile2": "",
            ".hiddenfolder/file3.txt": "",
            "foo/bar/file4.txt": ""
        })

        folder2 = temp_folder()
        copy(None, "*", folder1, folder2, excludes=(".*", "*/.*"))
        assert set(os.listdir(folder2)) == {'file1.txt', 'foo'}
        assert set(os.listdir(os.path.join(folder2, "foo"))) == {'file2.txt', 'bar'}
        assert not os.path.exists(os.path.join(folder2, ".hiddenfolder"))
        assert os.listdir(os.path.join(folder2, "foo", "bar")) == ['file4.txt']

    def test_excludes_camelcase_folder(self):
        # https://github.com/conan-io/conan/issues/8153
        folder1 = temp_folder()
        save(os.path.join(folder1, "UPPER.txt"), "")
        save(os.path.join(folder1, "lower.txt"), "")
        sub2 = os.path.join(folder1, "CamelCaseIgnore")
        save(os.path.join(sub2, "file3.txt"), "")

        folder2 = temp_folder()
        copy(None, "*", folder1, folder2, excludes=["CamelCaseIgnore", "UPPER.txt"])
        assert not os.path.exists(os.path.join(folder2, "CamelCaseIgnore"))
        assert not os.path.exists(os.path.join(folder2, "UPPER.txt"))
        assert os.path.exists(os.path.join(folder2, "lower.txt"))

        folder2 = temp_folder()
        copy(None, "*", folder1, folder2)
        assert os.path.exists(os.path.join(folder2, "CamelCaseIgnore"))
        assert os.path.exists(os.path.join(folder2, "UPPER.txt"))
        assert os.path.exists(os.path.join(folder2, "lower.txt"))

    @pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
    def test_excludes_symlink_folder(self):
        # https://github.com/conan-io/conan/issues/18296
        root_folder = temp_folder(path_with_spaces=False)
        target_folder = os.path.join(root_folder, "target_folder")
        src_dir = os.path.join(root_folder, "src_dir")
        os.makedirs(src_dir)
        save(os.path.join(src_dir, "file"), "nothing")
        os.symlink(src_dir, os.path.join(root_folder, "link_dir"))

        copied = copy(None, "*_dir*", root_folder, target_folder, excludes=["link_dir",])

        assert os.path.exists(target_folder) and os.path.isdir(target_folder)
        assert os.path.exists(os.path.join(target_folder, "src_dir", "file"))
        assert not os.path.exists(os.path.join(target_folder, "link_dir"))
        assert sorted(copied) == [os.path.join(target_folder, "src_dir", "file"),]

    @pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
    def test_excludes_symlink_file(self):
        # https://github.com/conan-io/conan/issues/18296
        root_folder = temp_folder(path_with_spaces=False)
        target_folder = os.path.join(root_folder, "target_folder")
        save(os.path.join(root_folder, "src_file"), "nothing")
        os.symlink(os.path.join(root_folder, "src_file"), os.path.join(root_folder, "link_file"))

        copied = copy(None, "*_file", root_folder, target_folder, excludes=["link_file", ])

        assert os.path.exists(target_folder) and os.path.isdir(target_folder)
        assert os.path.exists(os.path.join(target_folder, "src_file"))
        assert not os.path.exists(os.path.join(target_folder, "link_file"))
        assert copied == [os.path.join(target_folder, "src_file"),]

    def test_multifolder(self):
        src_folder1 = temp_folder()
        src_folder2 = temp_folder()
        save(os.path.join(src_folder1, "file1.txt"), "hello1")
        save(os.path.join(src_folder2, "file2.txt"), "Hello2")

        dst_folder = temp_folder()
        copy(None, "*", src_folder1, dst_folder)
        copy(None, "*", src_folder2, dst_folder)
        assert ['file1.txt', 'file2.txt'] == sorted(os.listdir(dst_folder))

    def test_multiple_patterns(self):
        src_folder = temp_folder()
        save(os.path.join(src_folder, "hello.h"), "h")
        save(os.path.join(src_folder, "src/lib.cpp"), "cpp")
        save(os.path.join(src_folder, "src/util.cpp"), "cpp")
        save(os.path.join(src_folder, "docs/readme.md"), "md")
        save(os.path.join(src_folder, "docs/private.md"), "secret")
        save(os.path.join(src_folder, "unmatched.txt"), "nope")

        dst_folder = temp_folder()
        copied = copy(None, ["*.h", "src/*.cpp", "docs/*.md"], src_folder, dst_folder,
                      excludes=["*/private.md"])
        rels = sorted(os.path.relpath(f, dst_folder).replace(os.sep, "/") for f in copied)
        assert rels == ["docs/readme.md", "hello.h", "src/lib.cpp", "src/util.cpp"]

    @mock.patch('shutil.copy2')
    def test_multiple_patterns_dedup(self, copy2_mock):
        """ A file matched by several patterns is still copied (and reported) only once """
        src_folder = temp_folder()
        save(os.path.join(src_folder, "a.h"), "x")   # matches both patterns below
        save(os.path.join(src_folder, "b.h"), "x")   # matches only "*.h"
        dst_folder = temp_folder()

        copied = copy(None, ["*.h", "a.*"], src_folder, dst_folder)
        assert sorted(os.path.basename(f) for f in copied) == ["a.h", "b.h"], \
            f"copy() reported {len(copied)} files: a.h is handled once per matching pattern"
        assert copy2_mock.call_count == 2, \
            f"2 files, {copy2_mock.call_count} copies: a.h is being copied once per pattern"

    def test_pattern_list_opens_every_src_folder_once(self):
        """ Passing the whole pattern list to a single copy() costs one scan of the src tree, the
        same as a single pattern would, instead of one scan per pattern like a loop of copy()
        calls did. This is the point of accepting a list of patterns, see #18981
        """
        src_folder = temp_folder()
        for i in range(5):
            save(os.path.join(src_folder, f"dir{i}/file.h"), "h")
            save(os.path.join(src_folder, f"dir{i}/file.cpp"), "cpp")
        patterns = [f"dir{i}/*.h" for i in range(5)] + [f"dir{i}/*.cpp" for i in range(5)]

        opens = Counter(_folders_opened_by_copy(patterns, src_folder, temp_folder()))
        assert opens == {".": 1, "dir0": 1, "dir1": 1, "dir2": 1, "dir3": 1, "dir4": 1}, \
            f"copy() with {len(patterns)} patterns must open each folder of src exactly once: " \
            f"a folder opened more than once means the tree is scanned once per pattern again"

    @pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
    def test_multiple_patterns_symlinked_folder(self):
        # A symlink to a folder is copied when ANY of the patterns matches it, not just the first
        src_folder = temp_folder()
        target_folder = os.path.join(src_folder, "target")
        mkdir(target_folder)
        os.symlink(target_folder, os.path.join(src_folder, "alink"))
        os.symlink(target_folder, os.path.join(src_folder, "blink"))

        dst_folder = temp_folder()
        copied = copy(None, ["a*", "b*"], src_folder, dst_folder)

        # both symlinks are copied: "alink" only matches the 1st pattern, "blink" only the 2nd
        assert sorted(os.path.relpath(f, dst_folder) for f in copied) == ["alink", "blink"]
        assert os.path.islink(os.path.join(dst_folder, "alink"))
        assert os.path.islink(os.path.join(dst_folder, "blink"))

    def test_multiple_patterns_ignore_case(self):
        # Every pattern of the list is matched, not only the first one, and ignore_case
        # case-folds all of them. The first pattern never matches, so if any assert below
        # sees a file it can only be because the *second* pattern was honoured.
        src_folder = temp_folder()
        save(os.path.join(src_folder, "FooBar.txt"), "x")

        # ignore_case=True: the trailing pattern is case-folded too (POSIX only: on Windows
        # fnmatch() normcases the pattern by itself, so the mixed case is already irrelevant)
        dst_folder = temp_folder()
        copy(None, ["*.zzz", "FOOBAR.TXT"], src_folder, dst_folder)
        assert os.listdir(dst_folder) == ["FooBar.txt"]

        # ignore_case=False: the trailing pattern is still matched, but case-sensitively
        dst_folder = temp_folder()
        copy(None, ["*.zzz", "FooBar.txt"], src_folder, dst_folder, ignore_case=False)
        assert os.listdir(dst_folder) == ["FooBar.txt"]

        dst_folder = temp_folder()
        copy(None, ["*.zzz", "FOOBAR.TXT"], src_folder, dst_folder, ignore_case=False)
        assert os.listdir(dst_folder) == []

    def test_multiple_patterns_accepts_tuple_and_validates_every_pattern(self):
        src_folder = temp_folder()
        save(os.path.join(src_folder, "hello.h"), "h")
        dst_folder = temp_folder()

        # Any collection works, not only a list: recipes do copy(self, ("*.h", "*.cpp"), ...)
        copied = copy(None, ("*.h", "*.cpp"), src_folder, dst_folder)
        assert [os.path.basename(f) for f in copied] == ["hello.h"]
        # An empty collection copies nothing instead of failing, so callers building the
        # pattern list dynamically (like the export of conanfile.exports) don't have to guard it
        assert copy(None, [], src_folder, dst_folder) == []
        # Every pattern of the collection is validated, not only the first one
        with pytest.raises(ConanException) as exc:
            copy(None, ["*.h", "../*.cpp"], src_folder, dst_folder)
        assert "not possible to use relative patterns" in str(exc.value)

    @mock.patch('shutil.copy2')
    def test_avoid_repeat_copies(self, copy2_mock):
        src_folders = [temp_folder() for _ in range(2)]
        for index, src_folder in enumerate(src_folders):
            save(os.path.join(src_folder, "sub", "file%d.txt" % index),
                 "Hello%d" % index)

        dst_folder = temp_folder()

        for src_folder in src_folders:
            copy(None, "*", os.path.join(src_folder, "sub"), dst_folder)

        assert copy2_mock.call_count == len(src_folders)

    def test_ignore_case(self):
        src_folder = temp_folder()
        save(os.path.join(src_folder, "FooBar.txt"), "Hello")

        dst_folder = temp_folder()
        copy(None, "foobar.txt", src_folder, dst_folder, ignore_case=False)
        assert [] == os.listdir(dst_folder)

        dst_folder = temp_folder()
        copy(None, "FooBar.txt", src_folder, dst_folder, ignore_case=False)
        assert ["FooBar.txt"] == os.listdir(dst_folder)

        dst_folder = temp_folder()
        copy(None, "foobar.txt", src_folder, dst_folder, ignore_case=True)
        assert ["FooBar.txt"] == os.listdir(dst_folder)

    def test_ignore_case_excludes(self):
        src_folder = temp_folder()
        save(os.path.join(src_folder, "file.h"), "")
        save(os.path.join(src_folder, "AttributeStorage.h"), "")
        save(os.path.join(src_folder, "sub/file.h"), "")
        save(os.path.join(src_folder, "sub/AttributeStorage.h"), "")

        dst_folder = temp_folder()
        # Exclude pattern will match AttributeStorage
        copy(None, "*.h", src_folder, os.path.join(dst_folder, "include"),
             excludes="*Test*")
        assert ["include"] == os.listdir(dst_folder)
        assert sorted(["file.h", "sub"]) == sorted(os.listdir(os.path.join(dst_folder, "include")))
        assert ["file.h"] == os.listdir(os.path.join(dst_folder, "include", "sub"))

        dst_folder = temp_folder()
        # Exclude pattern will not match AttributeStorage if ignore_case=False
        copy(None, "*.h", src_folder, os.path.join(dst_folder, "include"), excludes="*Test*",
             ignore_case=False)
        assert ["include"] == os.listdir(dst_folder)
        assert sorted(["AttributeStorage.h", "file.h", "sub"]) == sorted(os.listdir(os.path.join(dst_folder, "include")))
        assert sorted(["AttributeStorage.h", "file.h"]) == sorted(os.listdir(os.path.join(dst_folder, "include", "sub")))

    def test_empty_parent_folder_makedirs(self):
        src_folder = temp_folder()
        save(os.path.join(src_folder, "file.h"), "")
        sources = os.path.join(src_folder, "src")
        os.makedirs(sources)
        with chdir(sources):
            copy(None, "*", "..", dst=".")  # This used to crash
            assert "file.h" in os.listdir(sources)

    def test_keep_path_false(self):
        folder1 = temp_folder()
        save(os.path.join(folder1, "file1.txt"), "file1")
        save(os.path.join(folder1, "sub1", "file2.txt"), "file2")
        save(os.path.join(folder1, "sub1", "file3.txt"), "file3")
        save(os.path.join(folder1, "sub1", "sub12", "file4.txt"), "file4")
        save(os.path.join(folder1, "sub2", "file5.txt"), "file5")
        save(os.path.join(folder1, "sub2", "sub22", "file6.txt"), "file6")
        save(os.path.join(folder1, "sub2", "sub22", "sub23", "file7.txt"), "file7")

        folder2 = temp_folder()
        copy(None, "*.txt", folder1, folder2, keep_path=False)
        for file_number in range(1, 8):
            assert load(os.path.join(folder2, f"file{file_number}.txt")) == f"file{file_number}"
