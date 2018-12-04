# coding=utf-8

from conans.client.outputers.base_outputer import BaseOutputer
from conans.client.outputers.formats import OutputerFormats
from conans.client.printer import Printer


@OutputerFormats.register("cli")
class CLIOutputer(BaseOutputer):

    def search_recipes(self, info, all_remotes_search, out, query, raw, *args, **kwargs):
        printer = Printer(out)
        printer.print_search_recipes(search_info=info["results"], pattern=query,
                                     raw=raw, all_remotes_search=all_remotes_search)

    def search_packages(self, info, out, query, packages_query, outdated, *args, **kwargs):
        printer = Printer(out)
        printer.print_search_packages(search_info=info['results'], reference=query,
                                      packages_query=packages_query, outdated=outdated)
