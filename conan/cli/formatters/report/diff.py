import json
import os
import base64

from jinja2 import Template

from conan.api.output import cli_out_write
from conan.cli.formatters.report.diff_html import diff_html


def _get_filenames(line, src_prefix, dst_prefix):
    """
    Extracts the source and destination filenames from a diff line.
    """
    src_index = line.find(src_prefix)
    dst_index = line.find(dst_prefix)

    if src_index == -1 or dst_index == -1:
        return None, None

    src_filename = line[src_index + len(src_prefix) - 1:dst_index - 1].strip()
    dst_filename = line[dst_index + len(dst_prefix) - 1:].strip()

    return src_filename, dst_filename

def _render_diff(diff_text, template, template_folder, **kwargs):
    from conan import __version__
    template = Template(template, autoescape=True)
    def _safe_filename(filename):
        # Calculate base64 of the filename
        return base64.b64encode(filename.encode(), altchars=b'-_').decode()

    def _replace_path_with_ref(cache_path, ref, line):
        # Replace the cache path with the reference
        return line.replace(cache_path, f"({ref.repr_notime()})")

    def _get_diff_filename(line):
        return _get_filenames(line, kwargs["src_prefix"], kwargs["dst_prefix"])[0]

    return template.render(diff_text=diff_text,
                           base_template_path=template_folder, version=__version__,
                           safe_filename=_safe_filename,
                           replace_path_with_ref=_replace_path_with_ref,
                           get_diff_filename=_get_diff_filename,
                           **kwargs)

def format_diff_html(result):
    conan_api = result["conan_api"]
    diff_text = result["diff"]
    src_prefix = result["src_prefix"]
    dst_prefix = result["dst_prefix"]

    template_folder = os.path.join(conan_api.cache_folder, "templates")
    user_template = os.path.join(template_folder, "diff.html")
    template = diff_html
    if os.path.isfile(user_template):
        with open(user_template, 'r', encoding="utf-8", newline="") as handle:
            template = handle.read()

    prefix = "diff --git "
    prefix_len = len(prefix)
    context_paths = [line[prefix_len:].strip() for line in diff_text.splitlines()
                    if line.startswith(prefix)]
    file_names = list()
    for line in context_paths:
        src_filename, dst_filename = _get_filenames(line, src_prefix, dst_prefix)

        if src_filename not in file_names:
            file_names.append(src_filename)
        if dst_filename not in file_names:
            file_names.append(dst_filename)

    cli_out_write(_render_diff(diff_text, template, template_folder,
                               old_reference=result["old_export_ref"],
                               new_reference=result["new_export_ref"],
                               old_cache_path=result["old_cache_path"],
                               new_cache_path=result["new_cache_path"],
                               src_prefix=src_prefix,
                               dst_prefix=dst_prefix,
                               file_names=list(file_names)))


def format_diff_txt(result):
    diff_text = result["diff"]
    cli_out_write(diff_text)


def format_diff_json(result):
    '''
        Example of how the diff appears for each file::
        -----------------------------------------

        diff --git a/path with spaces/.conan2/p/pkg1/e/conanfile.py b/path with spaces/.conan2/p/pkg2/e/conanfile.py
        index aabbccdd..eeffgghh 123456
        --- a/path with spaces/.conan2/p/pkg1/e/conanfile.py
        +++ b/path with spaces/.conan2/p/pkg2/e/conanfile.py
        @@ -3,5 +3,5 @@ class HelloConan(ConanFile):
             name = 'pkg'
             ...

        diff --git a/old/foo.txt b/new/buzz.txt
        similarity index 100%
        rename from old/foo.txt
        rename to new/buzz.txt
    '''
    diff_text = result["diff"]
    result = {}
    filename = None
    skip_lines = True
    diff_splited_lines = diff_text.splitlines()
    buffer = []
    for i, line in enumerate(diff_splited_lines):
        if line.startswith("--- a") or (line.startswith("+++ b") and skip_lines):
            filename = line[len("--- a"):].strip()
            result.setdefault(filename, {})["new_name"] = line[len("+++ b"):].strip() \
                if line.startswith("+++ b") else diff_splited_lines[i+1][len("+++ b"):].strip()
            skip_lines = False
            result[filename].setdefault("diff", []).extend(buffer)
            buffer = []
        elif line.startswith("diff --git") or skip_lines:
            skip_lines = True
            buffer.append(line)
        else:
            result[filename].setdefault("diff", []).append(line)

    cli_out_write(json.dumps(result, indent=2))
