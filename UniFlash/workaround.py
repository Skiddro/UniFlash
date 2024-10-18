#!/usr/bin/env python3

import os
import subprocess
import time

import UniFlash.core as core
import UniFlash.miscellaneous as miscellaneous

_ = miscellaneous.i18n


def make_system_realize_partition_table_changed(target_device):
    """
    Refresh partition table on Windows.
    :param target_device: The target device letter (e.g., "D:")
    :return:
    """
    core.print_with_color(_("Making system realize that partition table has changed..."))

    # Windows equivalent: Use diskpart to refresh the partition table
    script = f"""
    select disk {target_device[0]}
    rescan
    """
    log_debug(f"Executing diskpart script to refresh partition table on {target_device[0]}.")
    result = run_diskpart_script(script)
    
    if result.returncode == 0:
        core.print_with_color(_("Partition table refresh completed successfully."))
        log_debug("Partition table refresh completed successfully.")
    else:
        error_message = f"Error refreshing partition table: {result.stderr.decode('utf-8')}"
        core.print_with_color(error_message, "red")
        log_debug(error_message, error=True)

    core.print_with_color(_("Wait 3 seconds for disk partition changes to take effect..."))
    time.sleep(3)


def buggy_motherboards_that_ignore_disks_without_boot_flag_toggled(target_device):
    """
    Workaround for buggy BIOS on Windows using diskpart to toggle boot flag.
    :param target_device: The target drive letter (e.g., "D:")
    :return:
    """
    core.print_with_color(
        _("Applying workaround for buggy motherboards that will ignore disks with no partitions with the boot flag toggled")
    )

    # Use diskpart to set the boot flag on the first partition
    script = f"""
    select disk {target_device[0]}
    select partition 1
    active
    """
    log_debug(f"Executing diskpart script to set boot flag on {target_device[0]}.")
    result = run_diskpart_script(script)
    
    if result.returncode == 0:
        core.print_with_color(_("Boot flag set successfully."))
        log_debug("Boot flag set successfully.")
    else:
        error_message = f"Error setting boot flag: {result.stderr.decode('utf-8')}"
        core.print_with_color(error_message, "red")
        log_debug(error_message, error=True)


def support_windows_7_uefi_boot(source_fs_mountpoint, target_fs_mountpoint):
    """
    Support Windows 7 UEFI boot by extracting the necessary EFI boot files.
    :param source_fs_mountpoint: The source mountpoint (e.g., "C:\\path\\to\\iso")
    :param target_fs_mountpoint: The target mountpoint (e.g., "D:\\")
    :return: 0 if successful, 1 if skipped or failed
    """
    log_debug(f"Checking if source media at {source_fs_mountpoint} supports UEFI boot...")

    grep_command = f'Get-Content "{source_fs_mountpoint}\\sources\\cversion.ini" | Select-String -Pattern "^MinServer=7[0-9]{{3}}\\.[0-9]"'
    grep_result = subprocess.run(["PowerShell", grep_command], stdout=subprocess.PIPE).stdout.decode("utf-8").strip()

    if grep_result == "" and not os.path.isfile(os.path.join(source_fs_mountpoint, "bootmgr.efi")):
        log_debug("Source media does not support UEFI boot. Skipping workaround.")
        return 0

    core.print_with_color(
        _("Source media seems to be Windows 7-based with EFI support, applying workaround to make it support UEFI booting"),
        "yellow")
    log_debug("Detected Windows 7-based media with EFI support, proceeding with UEFI boot workaround.")

    # Ensure the EFI directory exists on the target
    efi_directory = os.path.join(target_fs_mountpoint, "efi")
    efi_boot_directory = os.path.join(target_fs_mountpoint, "boot")

    if not os.path.isdir(efi_directory):
        os.makedirs(efi_directory)
        log_debug(f"Created EFI directory at {efi_directory}.")
    if not os.path.isdir(efi_boot_directory):
        os.makedirs(efi_boot_directory)
        log_debug(f"Created EFI boot directory at {efi_boot_directory}.")

    # Check if an EFI bootloader already exists, skip if found
    efi_bootloader_path = os.path.join(efi_directory, "boot", "bootx64.efi")
    if os.path.isfile(efi_bootloader_path):
        core.print_with_color(_("INFO: Detected existing EFI bootloader, workaround skipped."))
        log_debug("EFI bootloader already exists, skipping extraction.")
        return 0

    # Extract bootmgfw.efi from the Windows 7 install.wim using 7z
    core.print_with_color(_("Extracting EFI bootloader..."))
    log_debug("Extracting bootmgfw.efi using 7z...")

    try:
        bootloader = subprocess.run(["7z", "e", "-so", os.path.join(source_fs_mountpoint, "sources", "install.wim"),
                                     "Windows/Boot/EFI/bootmgfw.efi"], stdout=subprocess.PIPE).stdout
        with open(os.path.join(efi_boot_directory, "bootx64.efi"), "wb") as target_bootloader:
            target_bootloader.write(bootloader)
        core.print_with_color(_("EFI bootloader extracted and placed in the EFI/boot directory."))
        log_debug("EFI bootloader extracted and placed in EFI/boot directory.")
    except subprocess.CalledProcessError as e:
        error_message = f"Error extracting EFI bootloader: {e}"
        core.print_with_color(error_message, "red")
        log_debug(error_message, error=True)
        return 1

    return 0


def run_diskpart_script(script_content):
    """
    Helper function to run a diskpart script on Windows.
    :param script_content: The content of the diskpart script.
    :return: The result of the diskpart command.
    """
    log_debug("Running diskpart script...")
    
    with open("diskpart_script.txt", "w") as script_file:
        script_file.write(script_content)

    # Run the script using diskpart
    result = subprocess.run(["diskpart", "/s", "diskpart_script.txt"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    if result.returncode == 0:
        log_debug("Diskpart script executed successfully.")
    else:
        log_debug(f"Diskpart script failed with error: {result.stderr.decode('utf-8')}", error=True)

    # Cleanup the script file
    os.remove("diskpart_script.txt")
    return result


def log_debug(message, error=False):
    """Logs messages to the debug window if available."""
    if core.debug_window:
        log_prefix = "ERROR: " if error else ""
        core.debug_window.log_message(f"{log_prefix}{message}")
