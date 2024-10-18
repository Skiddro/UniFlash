#!/usr/bin/env python3

import os
import subprocess
import UniFlash.core as core  # To access the debug window

def usb_drive(show_all=False):
    devices_list = []

    log_debug("Starting to scan for USB drives...")

    # Use PowerShell to get removable drives on Windows
    powershell_command = [
        "PowerShell", 
        "-Command",
        "Get-WmiObject Win32_DiskDrive | Where-Object { $_.MediaType -eq 'Removable Media' } | ForEach-Object { $_.DeviceID, $_.Size, $_.Model }"
    ]
    
    try:
        # Run PowerShell command in the background without showing a window
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        # Execute PowerShell command
        devices_output = subprocess.run(powershell_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
        devices_output.check_returncode()  # Ensure the command was successful
        devices_output = devices_output.stdout.decode("utf-8").strip()
        log_debug(f"PowerShell command executed successfully: {powershell_command}")

        # Split output into lines and group by 3 lines (DeviceID, Size, Model)
        devices = devices_output.splitlines()
        device_group = [devices[i:i+3] for i in range(0, len(devices), 3)]
        log_debug(f"Found {len(device_group)} USB device(s).")

        for device_info in device_group:
            if len(device_info) != 3:
                continue

            # Extract DeviceID, Size, and Model
            device_id = device_info[0].strip()
            device_size = device_info[1].strip()
            device_model = device_info[2].strip()

            # Filter out devices if 'show_all' is False
            if not show_all:
                # Additional filtering conditions can be applied here if needed
                pass

            # Convert size to human-readable format
            device_capacity = convert_to_human_readable_size(device_size)

            # Append device info to the list
            if device_model:
                devices_list.append([device_id, f"{device_id} ({device_model}, {device_capacity})"])
            else:
                devices_list.append([device_id, f"{device_id} ({device_capacity})"])

            log_debug(f"Detected USB drive: {device_id}, Model: {device_model}, Size: {device_capacity}")

    except subprocess.CalledProcessError as e:
        error_message = f"Error running PowerShell command: {e}"
        print(error_message)
        log_debug(error_message, error=True)
    except Exception as ex:
        error_message = f"An unexpected error occurred: {ex}"
        print(error_message)
        log_debug(error_message, error=True)

    return devices_list


def convert_to_human_readable_size(size_in_bytes):
    """ Convert size from bytes to a human-readable format """
    try:
        size_in_bytes = int(size_in_bytes)
    except ValueError:
        return "Unknown size"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.2f} TB"


def dvd_drive():
    devices_list = []

    log_debug("Starting to scan for DVD drives...")

    # Use PowerShell to get DVD drives on Windows
    powershell_command = [
        "PowerShell", 
        "-Command",
        "Get-WmiObject Win32_CDROMDrive | ForEach-Object { $_.Drive, $_.MediaType, $_.Name }"
    ]
    
    try:
        # Run PowerShell command in the background without showing a window
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        # Execute PowerShell command
        devices_output = subprocess.run(powershell_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
        devices_output.check_returncode()  # Ensure the command was successful
        devices_output = devices_output.stdout.decode("utf-8").strip()
        log_debug(f"PowerShell command executed successfully: {powershell_command}")

        # Split output into lines and group by 3 lines (Drive, MediaType, Name)
        devices = devices_output.splitlines()
        device_group = [devices[i:i+3] for i in range(0, len(devices), 3)]
        log_debug(f"Found {len(device_group)} DVD device(s).")

        for device_info in device_group:
            if len(device_info) != 3:
                continue

            # Extract Drive, MediaType, and Name
            drive_letter = device_info[0].strip()
            media_type = device_info[1].strip()
            device_name = device_info[2].strip()

            # Append device info to the list
            devices_list.append([drive_letter, f"{drive_letter} - {device_name} ({media_type})"])
            log_debug(f"Detected DVD drive: {drive_letter}, Media Type: {media_type}, Name: {device_name}")

    except subprocess.CalledProcessError as e:
        error_message = f"Error running PowerShell command: {e}"
        print(error_message)
        log_debug(error_message, error=True)
    except Exception as ex:
        error_message = f"An unexpected error occurred: {ex}"
        print(error_message)
        log_debug(error_message, error=True)

    return devices_list


def log_debug(message, error=False):
    """Logs messages to the debug window if available."""
    if core.debug_window:
        log_prefix = "ERROR: " if error else ""
        core.debug_window.log_message(f"{log_prefix}{message}")
