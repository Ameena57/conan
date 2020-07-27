import os

from conans.client import tools
from conans.client.file_copier import FileCopier, report_copied_files
from conans.errors import conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager
from conans.model.manifest import FileTreeManifest
from conans.paths import CONANINFO
from conans.util.files import mkdir, save


def export_pkg(conanfile, package_id, src_package_folder, package_folder, hook_manager,
               conanfile_path, ref):
    mkdir(package_folder)
    conanfile.package_folder = package_folder
    output = conanfile.output
    output.info("Exporting to cache existing package from user folder")
    output.info("Package folder %s" % package_folder)
    hook_manager.execute("pre_package", conanfile=conanfile, conanfile_path=conanfile_path,
                         reference=ref, package_id=package_id)

    copier = FileCopier([src_package_folder], package_folder)
    copier("*", symlinks=True)

    conanfile.package_folder = package_folder
    hook_manager.execute("post_package", conanfile=conanfile, conanfile_path=conanfile_path,
                         reference=ref, package_id=package_id)

    save(os.path.join(package_folder, CONANINFO), conanfile.info.dumps())
    manifest = FileTreeManifest.create(package_folder)
    manifest.save(package_folder)
    report_files_from_manifest(output, manifest)

    output.success("Package '%s' created" % package_id)

    prev = manifest.summary_hash
    output.info("Created package revision %s" % prev)
    return prev


def update_package_metadata(prev, layout, package_id, rrev):
    with layout.update_metadata() as metadata:
        metadata.packages[package_id].revision = prev
        metadata.packages[package_id].recipe_revision = rrev


def report_files_from_manifest(output, manifest):
    copied_files = list(manifest.files())
    copied_files.remove(CONANINFO)

    if not copied_files:
        output.warn("No files in this package!")
        return

    report_copied_files(copied_files, output, message_suffix="Packaged")


def call_package_install(conanfile, package_install_folder):
    with get_env_context_manager(conanfile):
        conanfile.output.highlight("Calling package_install()")
        conanfile.package_install_folder = package_install_folder
        conanfile.source_folder = None
        conanfile.build_folder = None
        conanfile.package_folder = None
        conanfile.install_folder = None
        with tools.chdir(package_install_folder):
            with conanfile_exception_formatter(str(conanfile), "install"):
                conanfile.package_install()
