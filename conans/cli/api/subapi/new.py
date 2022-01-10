import fnmatch
import os

from jinja2 import Template

from conans.cli.api.subapi import api_method
from conans.util.files import load
from conans import __version__


class NewAPI:

    _NOT_TEMPLATES = "not_templates"  # Filename containing filenames of files not to be rendered

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def get_builtin_template(self, template_name):
        from conans.cli.api.helpers.new.alias_new import alias_file
        from conans.cli.api.helpers.new.cmake_exe import cmake_exe_files
        from conans.cli.api.helpers.new.cmake_lib import cmake_lib_files
        new_templates = {"cmake_lib": cmake_lib_files,
                         "cmake_exe": cmake_exe_files,
                         "alias": alias_file}
        template_files = new_templates.get(template_name)
        return template_files

    @api_method
    def get_template(self, template_name):
        """ Load a template from a user absolute folder
        """
        if os.path.isdir(template_name):
            return self._read_files(template_name)

    @api_method
    def get_home_template(self, template_name):
        """ load a template from the Conan home templates/command/new folder
        """
        folder_template = os.path.join(self.conan_api.home_folder, "templates", "command/new",
                                       template_name)
        if os.path.isdir(folder_template):
            return self._read_files(folder_template)

    def _read_files(self, folder_template):
        template_files, non_template_files = {}, {}
        excluded = os.path.join(folder_template, self._NOT_TEMPLATES)
        if os.path.exists(excluded):
            excluded = load(excluded)
            excluded = [] if not excluded else [s.strip() for s in excluded.splitlines() if
                                                s.strip()]
        else:
            excluded = []

        for d, _, fs in os.walk(folder_template):
            for f in fs:
                if f == self._NOT_TEMPLATES:
                    continue
                rel_d = os.path.relpath(d, folder_template) if d != folder_template else ""
                rel_f = os.path.join(rel_d, f)
                path = os.path.join(d, f)
                if not any(fnmatch.fnmatch(rel_f, exclude) for exclude in excluded):
                    template_files[rel_f] = load(path)
                else:
                    non_template_files[rel_f] = path

        return template_files, non_template_files

    @staticmethod
    def render(template_files, definitions):
        result = {}
        definitions["conan_version"] = __version__
        for k, v in template_files.items():
            k = Template(k, keep_trailing_newline=True).render(**definitions)
            v = Template(v, keep_trailing_newline=True).render(**definitions)
            if v:
                result[k] = v
        return result
