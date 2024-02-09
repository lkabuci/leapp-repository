import os
import errno
import shutil

from leapp.actors import Actor
from leapp.models import InstalledRPM
from leapp.tags import DownloadPhaseTag, IPUWorkflowTag
from leapp.libraries.common.cllaunch import run_on_cloudlinux


class ClearPackageConflicts(Actor):
    """
    Remove several python package files manually to resolve conflicts between versions of packages to be upgraded.
    """

    name = "clear_package_conflicts"
    consumes = (InstalledRPM,)
    produces = ()
    tags = (DownloadPhaseTag.Before, IPUWorkflowTag)

    def __init__(self):
        self._rpm_lookup = None

    @property
    def rpm_lookup(self):
        """
        Get and store the list of installed RPMs for quick lookup.
        """
        if not self._rpm_lookup:
            self._rpm_lookup = {rpm for rpm in self.consume(InstalledRPM)}
        return self._rpm_lookup

    def has_package(self, name):
        """
        Check whether the package is installed.
        Looks only for the package name, nothing else.
        """
        return name in self.rpm_lookup

    def problem_packages_installed(self, problem_packages):
        """
        Check whether any of the problem packages are present in the system.
        """
        for pkg in problem_packages:
            if self.has_package(pkg):
                self.log.debug("Conflicting package {} detected".format(pkg))
                return True
        return False

    def clear_problem_files(self, problem_files, problem_dirs):
        """
        Go over the list of problem files and directories and remove them if they exist.
        They'll be replaced by the new packages.
        """
        for p_dir in problem_dirs:
            try:
                if os.path.isdir(p_dir):
                    shutil.rmtree(p_dir)
                    self.log.debug("Conflicting directory {} removed".format(p_dir))
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise

        for p_file in problem_files:
            try:
                if os.path.isfile(p_file):
                    os.remove(p_file)
                    self.log.debug("Conflicting file {} removed".format(p_file))
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise

    def alt_python37_handle(self):
        """
        These alt-python37 packages are conflicting with their own builds for EL8.
        """
        problem_packages = [
            "alt-python37-six",
            "alt-python37-pytz",
        ]
        problem_files = []
        problem_dirs = [
            "/opt/alt/python37/lib/python3.7/site-packages/six-1.15.0-py3.7.egg-info",
            "/opt/alt/python37/lib/python3.7/site-packages/pytz-2017.2-py3.7.egg-info",
        ]

        if self.problem_packages_installed(problem_packages):
            self.clear_problem_files(problem_files, problem_dirs)

    def openssl_handle(self):
        """
        openssl11-libs package from the EPEL repo is conflicting with the incoming openssl-libs package for EL8.
        https://access.redhat.com/solutions/6986997
        """
        problem_packages = [
            "openssl11-libs"
        ]
        problem_files = [
            "/usr/lib64/.libcrypto.so.1.1.1k.hmac",
            "/usr/lib64/.libssl.so.1.1.1k.hmac"
        ]
        problem_dirs = []

        if self.problem_packages_installed(problem_packages):
            self.clear_problem_files(problem_files, problem_dirs)

    @run_on_cloudlinux
    def process(self):
        self.alt_python37_handle()
        self.openssl_handle()
