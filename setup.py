import os
import shutil
import stat
import subprocess
from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install

this_directory = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


def post_install():
    """
    Post-installation logic for Linux (currently deactivated for Windows).
    """
    if os.name != 'nt':  # Skip this on Windows
        path = '/usr/local/bin/uniflashgui'
        shutil.copy2(this_directory + '/UniFlash/uniflashgui', path)

        shutil.copy2(this_directory + '/miscellaneous/com.github.uniflash.policy', "/usr/share/polkit-1/actions")

        try:
            os.makedirs('/usr/share/icons/UniFlash')
        except FileExistsError:
            pass

        shutil.copy2(this_directory + '/UniFlash/data/icon.ico', '/usr/share/icons/UniFlash/icon.ico')
        shutil.copy2(this_directory + '/miscellaneous/UniFlash.desktop', "/usr/share/applications/UniFlash.desktop")

        os.chmod('/usr/share/applications/UniFlash.desktop',
                 stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IEXEC)  # 755


def create_executable():
    """
    Use PyInstaller to create a single executable for Windows.
    """
    print("Compiling UniFlash into a single .exe file...")

    # PyInstaller command to create a single .exe
    subprocess.run([
        'pyinstaller',
        '--onefile',
        '--name', 'UniFlash',
        '--icon', 'UniFlash/data/icon.ico',  # Optional: path to the icon
        'UniFlash/uniflash'
    ], check=True)


class PostDevelopCommand(develop):
    """Post-installation for development mode."""

    def run(self):
        if os.name == 'nt':
            create_executable()
        develop.run(self)


class PostInstallCommand(install):
    """Post-installation for installation mode."""

    def run(self):
        if os.name == 'nt':
            create_executable()
        else:
            post_install()
        install.run(self)


setup(
    name='UniFlash',
    version='0.1',
    description='UniFlash is a tool that allows you to flash any file to a USB or Disc.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/Skiddro/UniFlash',
    author='Skiddro',
    author_email='None',
    license='GPL-3',
    zip_safe=False,
    packages=['UniFlash'],
    include_package_data=True,
    scripts=[
        'Skiddro/uniflash',
    ],
    install_requires=[
        'termcolor',
        'wxPython',
        'PyInstaller'  # Add PyInstaller as a requirement for bundling
    ],
    cmdclass={
        'develop': PostDevelopCommand,
        'install': PostInstallCommand
    }
)
