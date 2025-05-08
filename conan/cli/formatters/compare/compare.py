import os

from jinja2 import Template

from conan.api.output import cli_out_write
from conan.cli.formatters.compare.compare_html import compare_html


def _render_diff(diff_text, template, template_folder, **kwargs):
    from conan import __version__
    template = Template(template, autoescape=True)
    def _safe_filename(filename):
        # Create a hash of the filename
        # TODO: This is done to avoid broken links,
        #  but it should be done in a better way, sha256 is overkill
        import hashlib
        return hashlib.sha256(filename.encode("utf-8")).hexdigest()

    def _replace_path_with_ref(cache_path, ref, line):
        # Replace the cache path with the reference
        return line.replace(cache_path, f"({ref.repr_notime()})")


    return template.render(diff_text=diff_text,
                           base_template_path=template_folder, version=__version__,
                           safe_filename=_safe_filename,
                           replace_path_with_ref=_replace_path_with_ref,
                           **kwargs)

def format_compare_html(result):
    conan_api = result["conan_api"]
    diff_text = result["diff"]

    template_folder = os.path.join(conan_api.cache_folder, "templates")
    user_template = os.path.join(template_folder, "compare.html")
    template = compare_html
    if os.path.isfile(user_template):
        with open(user_template, 'r', encoding="utf-8", newline="") as handle:
            template = handle.read()

    file_names = [line.split()[2][1:] for line in diff_text.splitlines() if
                  line.startswith("diff --git")]


    cli_out_write(_render_diff(diff_text, template, template_folder,
                               old_reference=result["old_export_ref"],
                               new_reference=result["new_export_ref"],
                               old_cache_path=result["old_cache_path"],
                               new_cache_path=result["new_cache_path"],
                               file_names=file_names,))


def format_compare_txt(result):
    diff_text = result["diff"]
    cli_out_write(diff_text)
