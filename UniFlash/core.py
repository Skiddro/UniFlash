#!/usr/bin/env python3

import os
import shutil
import tempfile
import threading
import subprocess
import urllib.request
import urllib.error
import re
import sys
import time
import ctypes
from datetime import datetime
import argparse
import wx  # For creating the debug window when needed

import UniFlash.miscellaneous as miscellaneous

_ = miscellaneous.i18n

application_name = 'UniFlash'
application_version = miscellaneous.__version__
DEFAULT_NEW_FS_LABEL = 'USB'

#: Execution state for cleanup functions to determine if clean up is required
current_state = 'pre-init'
CopyFiles_handle = threading.Thread()

no_color = False
verbose = False
gui = None
debug_mode = False  # Global flag for debug mode
debug_window = None  # Global reference for the debug window


# Utility functions previously in utils.py
def print_with_color(text, color=""):
    if gui is not None:
        gui.state = text
        if color == "red":
            gui.error = text
            sys.exit()
    else:
        if debug_mode and debug_window:
            debug_window.log_message(text, color)  # Output messages to debug window
        else:
            if no_color or color == "":
                sys.stdout.write(text + "\n")
            else:
                try:
                    import termcolor
                    termcolor.cprint(text, color)
                except ImportError:
                    sys.stdout.write(text + "\n")


def check_runtime_dependencies(application_name):
    result = "success"
    system_commands = ["diskpart", "PowerShell"]

    for command in system_commands:
        if shutil.which(command) is None:
            print_with_color(
                _("Error: {0} requires {1} command in the executable search path, but it is not found.").format(
                    application_name, command), "red")
            result = "failed"

    if result != "success":
        raise RuntimeError("Dependencies are not met")
    else:
        return ["diskpart", "diskpart", None]


def check_runtime_parameters(install_mode, source_media, target_media):
    if not os.path.isfile(source_media):
        print_with_color(_("Error: Source media \"{0}\" not found or not a regular file!").format(source_media), "red")
        return 1

    if not re.match(r"^[A-Z]:\\", target_media):
        print_with_color(_("Error: Target media \"{0}\" is not a valid drive letter!").format(target_media), "red")
        return 1

    if install_mode == "device" and not re.match(r"^[A-Z]:$", target_media):
        print_with_color(_("Error: Target media \"{0}\" is not an entire storage device!").format(target_media), "red")
        return 1

    if install_mode == "partition" and not re.match(r"^[A-Z]:\\", target_media):
        print_with_color(_("Error: Target media \"{0}\" is not a partition!").format(target_media), "red")
        return 1
    return 0


def determine_target_parameters(install_mode, target_media):
    if install_mode == "partition":
        target_partition = target_media
        target_device = target_media  # In Windows, the device and partition are both identified by drive letters
    else:
        target_device = target_media
        target_partition = target_media  # No separate partition identifier needed in Windows

    if verbose:
        print_with_color(_("Info: Target device is {0}").format(target_device))
        print_with_color(_("Info: Target partition is {0}").format(target_partition))

    return [target_device, target_partition]


def check_is_target_device_busy(device):
    powershell_command = f"Get-Volume -DriveLetter {device[0]} | Select-Object DriveLetter, FileSystem"
    result = subprocess.run(["PowerShell", powershell_command], stdout=subprocess.PIPE).stdout.decode("utf-8")

    if re.search(rf"{device}", result):
        print_with_color(_("Warning: The drive {0} is currently busy. Please unmount the drive before proceeding.").format(device), "yellow")
        return 1
    return 0


def check_source_and_target_not_busy(install_mode, source_media, target_device, target_partition):
    if check_is_target_device_busy(source_media):
        print_with_color(_("Error: Source media is currently in use, unmount the drive and try again"), "red")
        return 1

    if install_mode == "partition":
        if check_is_target_device_busy(target_partition):
            print_with_color(_("Error: Target partition is currently mounted, unmount it and try again"), "red")
            return 1
    else:
        if check_is_target_device_busy(target_device):
            print_with_color(_("Error: Target device is currently busy, unmount the drive and try again"), "red")
            return 1
    return 0


def check_fat32_filesize_limitation(source_fs_mountpoint):
    for dirpath, dirnames, filenames in os.walk(source_fs_mountpoint):
        for file in filenames:
            path = os.path.join(dirpath, file)
            if os.path.getsize(path) > (2 ** 32) - 1:  # Max FAT32 file size
                print_with_color(
                    _("Warning: File {0} exceeds the FAT32 4GiB limit, switching to NTFS.").format(path), "yellow")
                return 1
    return 0


def convert_to_human_readable_format(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Ti', suffix)


def get_size(path):
    total_size = 0
    for dirpath, __, filenames in os.walk(path):
        for file in filenames:
            path = os.path.join(dirpath, file)
            total_size += os.path.getsize(path)
    return total_size


def check_kill_signal():
    if gui is not None:
        if gui.kill:
            raise sys.exit()


# DebugWindow class to show debug information
class DebugWindow(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Debug Log", size=(500, 400))
        self.log_area = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        self.Show()

    def log_message(self, message, color=""):
        self.log_area.AppendText(f"{message}\n")


# Main core logic from core.py

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


# NEW: Check if the target device has a partition, format it if necessary
def format_target_device(target_device, filesystem_type="FAT32"):
    print_with_color(_("Checking and formatting {0} if no partition exists...").format(target_device), "green")
    powershell_command = f"Get-Partition -DiskNumber {target_device}"
    result = subprocess.run(["PowerShell", "-Command", powershell_command], stdout=subprocess.PIPE).stdout.decode("utf-8")
    if "No partitions" in result or len(result.strip()) == 0:
        # Create a new partition and format the device
        print_with_color(_("No partitions found, creating a new partition and formatting..."), "green")
        create_target_partition(target_device, filesystem_type, DEFAULT_NEW_FS_LABEL)
    else:
        print_with_color(_("Target device already has a partition."), "green")


def flash_device(source_media, target_device, target_filesystem_type="FAT", filesystem_label=DEFAULT_NEW_FS_LABEL):
    source_fs_mountpoint = os.path.join("C:\\media\\uniflash_source_", str(
        round((datetime.today() - datetime.fromtimestamp(0)).total_seconds())) + "_" + str(os.getpid()))
    target_fs_mountpoint = os.path.join("C:\\media\\uniflash_target_", str(
        round((datetime.today() - datetime.fromtimestamp(0)).total_seconds())) + "_" + str(os.getpid()))
    temp_directory = tempfile.mkdtemp(prefix="UniFlash.")

    try:
        if not is_admin():
            print_with_color(_("Warning: You are not running {0} with administrator privileges!").format(application_name), "yellow")
            return 1

        if mount_source_filesystem(source_media, source_fs_mountpoint):
            print_with_color(_("Error: Unable to mount source filesystem"), "red")
            return 1

        if target_filesystem_type == "FAT" and check_fat32_filesize_limitation(source_fs_mountpoint):
            target_filesystem_type = "NTFS"

        format_target_device(target_device, target_filesystem_type)  # NEW: Check and format if needed
        wipe_existing_partition_table_and_filesystem_signatures(target_device)
        create_target_partition_table(target_device, "legacy")
        create_target_partition(target_device, target_filesystem_type, filesystem_label)

        if mount_target_filesystem(target_device, target_fs_mountpoint):
            print_with_color(_("Error: Unable to mount target filesystem"), "red")
            return 1

        copy_filesystem_files(source_fs_mountpoint, target_fs_mountpoint)

        if target_filesystem_type == "NTFS":
            create_uefi_ntfs_support_partition(target_device)
            install_uefi_ntfs_support_partition(target_device + "2", temp_directory)

    except Exception as error:
        print_with_color(str(error), "red")
        return 1

    finally:
        cleanup(source_fs_mountpoint, target_fs_mountpoint, temp_directory, target_device)
        print_with_color(_("Flashing completed successfully!"), "green")


def wipe_existing_partition_table_and_filesystem_signatures(target_device):
    print_with_color(_("Wiping existing partition table on {0}").format(target_device), "green")
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    subprocess.run(["diskpart", "/s", f"select disk {target_device}\nclean\n"], startupinfo=startupinfo)


def create_target_partition_table(target_device, partition_table_type):
    print_with_color(_("Creating new partition table on {0}...").format(target_device), "green")
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    if partition_table_type in ["legacy", "msdos"]:
        subprocess.run(["diskpart", "/s", f"select disk {target_device}\nconvert mbr\n"], startupinfo=startupinfo)
    elif partition_table_type == "gpt":
        subprocess.run(["diskpart", "/s", f"select disk {target_device}\nconvert gpt\n"], startupinfo=startupinfo)


def create_target_partition(target_device, filesystem_type, filesystem_label):
    print_with_color(_("Creating target partition..."), "green")
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    partition_script = f"""
    select disk {target_device}
    create partition primary
    select partition 1
    active
    format fs={filesystem_type} label={filesystem_label} quick
    assign letter=U
    """
    subprocess.run(['diskpart', '/s', partition_script], startupinfo=startupinfo)


def create_uefi_ntfs_support_partition(target_device):
    print_with_color(_("Creating UEFI:NTFS support partition..."), "green")


def install_uefi_ntfs_support_partition(uefi_ntfs_partition, download_directory):
    check_kill_signal()
    try:
        fileName = urllib.request.urlretrieve("https://github.com/pbatard/rufus/raw/master/res/uefi/uefi-ntfs.img", "uefi-ntfs.img")[0]
    except (urllib.error.ContentTooShortError, urllib.error.HTTPError, urllib.error.URLError):
        print_with_color(_("Warning: Unable to download UEFI:NTFS image."), "yellow")
        return 1
    shutil.move(fileName, download_directory + "/" + fileName)
    shutil.copy2(download_directory + "/uefi-ntfs.img", uefi_ntfs_partition)


def mount_source_filesystem(source_media, source_fs_mountpoint):
    print_with_color(_("Mounting source filesystem..."), "green")
    if not os.path.exists(source_fs_mountpoint):
        os.makedirs(source_fs_mountpoint)
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    try:
        subprocess.run(['PowerShell', 'Mount-DiskImage', '-ImagePath', source_media], check=True, startupinfo=startupinfo)
    except subprocess.CalledProcessError:
        return 1
    return 0


def mount_target_filesystem(target_device, target_fs_mountpoint):
    print_with_color(_("Mounting target filesystem..."), "green")
    return 0


def copy_filesystem_files(source_fs_mountpoint, target_fs_mountpoint):
    global CopyFiles_handle
    check_kill_signal()
    CopyFiles_handle = ReportCopyProgress(source_fs_mountpoint, target_fs_mountpoint)
    CopyFiles_handle.start()
    for dirpath, _, filenames in os.walk(source_fs_mountpoint):
        for file in filenames:
            path = os.path.join(dirpath, file)
            CopyFiles_handle.file = path
            shutil.copy2(path, target_fs_mountpoint + path.replace(source_fs_mountpoint, ""))
    CopyFiles_handle.stop = True


class ReportCopyProgress(threading.Thread):
    file = ""
    stop = False

    def __init__(self, source, target):
        threading.Thread.__init__(self)
        self.source = source
        self.target = target

    def run(self):
        while not self.stop:
            time.sleep(0.05)


def cleanup(source_fs_mountpoint, target_fs_mountpoint, temp_directory, target_device):
    if CopyFiles_handle.is_alive():
        CopyFiles_handle.stop = True
    shutil.rmtree(temp_directory)


def setup_arguments():
    parser = argparse.ArgumentParser(description="UniFlash Core Application")
    parser.add_argument("--debug", action="store_true", help="Enable debug window for log output")
    return parser.parse_args()


def run_application():
    # Import the GUI here to avoid circular import issues
    from UniFlash.gui import run as run_gui
    run_gui()


if __name__ == "__main__":
    args = setup_arguments()

    # Initialize the wx App for GUI handling.
    app = wx.App()

    # Check for debug mode and start the debug window if --debug is provided
    debug_mode = args.debug
    if debug_mode:
        debug_window = DebugWindow()

    # Trigger the main GUI regardless
    run_application()

    # Start the app's event loop to handle both GUI and debug window.
    app.MainLoop()
