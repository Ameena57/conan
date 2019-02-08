import ast
import os
import shutil

import six

from conans.client.cmd.export_linter import conan_linter
from conans.client.file_copier import FileCopier
from conans.client.output import ScopedOutput
from conans.errors import ConanException
from conans.model.manifest import FileTreeManifest
from conans.model.scm import SCM, get_scm_data
from conans.paths import CONANFILE
from conans.search.search import search_recipes
from conans.util.files import is_dirty, load, rmdir, save, set_dirty, remove
from conans.util.log import logger


def export_alias(ref_layout, target_reference):
    conanfile = """
from conans import ConanFile

class AliasConanfile(ConanFile):
    alias = "%s"
""" % target_reference

    save(ref_layout.conanfile(), conanfile)
    digest = FileTreeManifest.create(ref_layout.export())
    digest.save(folder=ref_layout.export())


def cmd_export(conanfile_path, conanfile, ref, keep_source, output, cache, hook_manager):
    """ Export the recipe
    param conanfile_path: the original source directory of the user containing a
                       conanfile.py
    """
    hook_manager.execute("pre_export", conanfile=conanfile, conanfile_path=conanfile_path,
                         reference=ref)
    logger.debug("EXPORT: %s" % conanfile_path)

    output.highlight("Exporting package recipe")
    conan_linter(conanfile_path, output)

    # Check for casing conflict
    # Maybe a platform check could be added, but depends on disk partition
    reference = str(ref)
    refs = search_recipes(cache, reference, ignorecase=True)
    if refs and ref not in refs:
        raise ConanException("Cannot export package with same name but different case\n"
                             "You exported '%s' but already existing '%s'"
                             % (reference, " ".join(str(s) for s in refs)))

    output = conanfile.output

    # Get previous digest
    package_layout = cache.package_layout(ref, conanfile.short_paths)
    try:
        previous_digest = FileTreeManifest.load(package_layout.export())
    except IOError:
        previous_digest = None
    finally:
        _recreate_folders(package_layout.export(), package_layout.export_sources())

    # Copy sources to target folders
    with cache.conanfile_write_lock(ref):
        origin_folder = os.path.dirname(conanfile_path)
        export_recipe(conanfile, origin_folder, package_layout.export())
        export_source(conanfile, origin_folder, package_layout.export_sources())
        shutil.copy2(conanfile_path, package_layout.conanfile())

        scm_data, captured_revision = _capture_export_scm_data(conanfile,
                                                               os.path.dirname(conanfile_path),
                                                               package_layout.export(),
                                                               output, cache, ref)

        # Execute post-export hook before computing the digest
        hook_manager.execute("post_export", conanfile=conanfile, reference=ref,
                             conanfile_path=package_layout.conanfile())

        # Compute the new digest
        digest = FileTreeManifest.create(package_layout.export(), package_layout.export_sources())
        modified_recipe = not previous_digest or previous_digest != digest
        if modified_recipe:
            output.success('A new %s version was exported' % CONANFILE)
            output.info('Folder: %s' % package_layout.export())
        else:
            output.info("The stored package has not changed")
            digest = previous_digest  # Use the old one, keep old timestamp
        digest.save(package_layout.export())

    # Compute the revision for the recipe
    revision = scm_data.revision if scm_data and captured_revision else digest.summary_hash
    with package_layout.update_metadata() as metadata:
        # Note that there is no time set, the time will come from the remote
        metadata.recipe.revision = revision

    # FIXME: Conan 2.0 Clear the registry entry if the recipe has changed
    source_folder = package_layout.source()
    if os.path.exists(source_folder):
        try:
            if is_dirty(source_folder):
                output.info("Source folder is corrupted, forcing removal")
                rmdir(source_folder)
            elif modified_recipe and not keep_source:
                output.info("Package recipe modified in export, forcing source folder removal")
                output.info("Use the --keep-source, -k option to skip it")
                rmdir(source_folder)
        except BaseException as e:
            output.error("Unable to delete source folder. Will be marked as corrupted for deletion")
            output.warn(str(e))
            set_dirty(source_folder)


def _capture_export_scm_data(conanfile, conanfile_dir, destination_folder, output, paths, ref):

    scm_src_file = paths.scm_folder(ref)
    if os.path.exists(scm_src_file):
        os.unlink(scm_src_file)

    scm_data = get_scm_data(conanfile)
    if not scm_data:
        return None, False

    # Resolve SCMData in the user workspace (someone may want to access CVS or import some py)
    captured_revision = scm_data.capture_revision

    scm = SCM(scm_data, conanfile_dir, output)
    captured = scm_data.capture_origin or scm_data.capture_revision

    if scm_data.url == "auto":
        origin = scm.get_qualified_remote_url(remove_credentials=True)
        if not origin:
            raise ConanException("Repo origin cannot be deduced")
        if scm.is_local_repository():
            output.warn("Repo origin looks like a local path: %s" % origin)
        output.success("Repo origin deduced by 'auto': %s" % origin)
        scm_data.url = origin

    if scm_data.revision == "auto":
        if not scm.is_pristine():
            output.warn("Repo status is not pristine: there might be modified files")
        scm_data.revision = scm.get_revision()
        output.success("Revision deduced by 'auto': %s" % scm_data.revision)

    _replace_scm_data_in_conanfile(os.path.join(destination_folder, "conanfile.py"), scm_data)

    if captured:
        # Generate the scm_folder.txt file pointing to the src_path
        src_path = scm.get_local_path_to_url(scm_data.url)
        if src_path:
            save(scm_src_file, os.path.normpath(src_path).replace("\\", "/"))

    return scm_data, captured_revision


def _replace_scm_data_in_conanfile(conanfile_path, scm_data):
    # Parsing and replacing the SCM field
    content = load(conanfile_path)
    headers = []

    if six.PY2:
        # Workaround for https://bugs.python.org/issue22221
        lines_without_headers = []
        lines = content.splitlines(True)
        for line in lines:
            if not lines_without_headers and line.startswith("#"):
                headers.append(line)
            else:
                lines_without_headers.append(line)
        content = ''.join(lines_without_headers)

    lines = content.splitlines(True)
    tree = ast.parse(content)
    to_replace = []
    for i_body, item in enumerate(tree.body):
        if isinstance(item, ast.ClassDef):
            statements = item.body
            for i, stmt in enumerate(item.body):
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                    if isinstance(stmt.targets[0], ast.Name) and stmt.targets[0].id == "scm":
                        try:
                            if i + 1 == len(statements):  # Last statement in my ClassDef
                                if i_body + 1 == len(tree.body):  # Last statement over all
                                    next_line = len(lines)
                                else:
                                    next_line = tree.body[i_body+1].lineno - 1
                            else:
                                next_line = statements[i+1].lineno - 1
                        except IndexError:
                            next_line = stmt.lineno
                        replace = [line for line in lines[(stmt.lineno-1):next_line]
                                   if line.strip()]
                        to_replace.append("".join(replace).lstrip())
                        break
    if len(to_replace) != 1:
        raise ConanException("The conanfile.py defines more than one class level 'scm' attribute")

    new_text = "scm = " + ",\n          ".join(str(scm_data).split(",")) + "\n"
    content = content.replace(to_replace[0], new_text)
    content = content if not headers else ''.join(headers) + content

    remove(conanfile_path)
    save(conanfile_path, content)


def _recreate_folders(destination_folder, destination_src_folder):
    try:
        if os.path.exists(destination_folder):
            # Maybe here we want to invalidate cache
            rmdir(destination_folder)
        os.makedirs(destination_folder)
    except Exception as e:
        raise ConanException("Unable to create folder %s\n%s" % (destination_folder, str(e)))

    try:
        if os.path.exists(destination_src_folder):
            rmdir(destination_src_folder)
        os.makedirs(destination_src_folder)
    except Exception as e:
        raise ConanException("Unable to create folder %s\n%s" % (destination_src_folder, str(e)))


def _classify_patterns(patterns):
    patterns = patterns or []
    included, excluded = [], []
    for p in patterns:
        if p.startswith("!"):
            excluded.append(p[1:])
        else:
            included.append(p)
    return included, excluded


def export_source(conanfile, origin_folder, destination_source_folder):
    if isinstance(conanfile.exports_sources, str):
        conanfile.exports_sources = (conanfile.exports_sources, )

    included_sources, excluded_sources = _classify_patterns(conanfile.exports_sources)
    copier = FileCopier(origin_folder, destination_source_folder)
    for pattern in included_sources:
        copier(pattern, links=True, excludes=excluded_sources)
    output = conanfile.output
    package_output = ScopedOutput("%s exports_sources" % output.scope, output)
    copier.report(package_output)


def export_recipe(conanfile, origin_folder, destination_folder):
    if isinstance(conanfile.exports, str):
        conanfile.exports = (conanfile.exports, )

    included_exports, excluded_exports = _classify_patterns(conanfile.exports)

    try:
        os.unlink(os.path.join(origin_folder, CONANFILE + 'c'))
    except OSError:
        pass

    copier = FileCopier(origin_folder, destination_folder)
    for pattern in included_exports:
        copier(pattern, links=True, excludes=excluded_exports)
    output = conanfile.output
    package_output = ScopedOutput("%s exports" % output.scope, output)
    copier.report(package_output)
