#!/usr/bin/env python3

import os
import time
import threading
import subprocess

import wx
import wx.adv

import UniFlash.core as core
import UniFlash.list_devices as list_devices
import UniFlash.miscellaneous as miscellaneous

data_directory = os.path.dirname(__file__) + "/data/"

app = wx.App()

_ = miscellaneous.i18n


class MainFrame(wx.Frame):
    __MainPanel = None
    __MenuBar = None

    __menuItemShowAll = None

    def __init__(self, title, pos, size, style=wx.DEFAULT_FRAME_STYLE):
        super(MainFrame, self).__init__(None, -1, title, pos, size, style)

        self.SetIcon(wx.Icon(data_directory + "icon.ico"))

        file_menu = wx.Menu()
        self.__menuItemShowAll = wx.MenuItem(file_menu, wx.ID_ANY, _("Show all drives") + " \tCtrl+A",
                                             _("Show all drives, even those not detected as USB stick."),
                                             wx.ITEM_CHECK)
        file_menu.Append(self.__menuItemShowAll)

        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT)

        help_menu = wx.Menu()
        help_item = help_menu.Append(wx.ID_ABOUT)

        options_menu = wx.Menu()
        self.options_boot = wx.MenuItem(options_menu, wx.ID_ANY, _("Set boot flag"),
                                        _("Sets boot flag after process of copying."),
                                        wx.ITEM_CHECK)
        self.options_filesystem = wx.MenuItem(options_menu, wx.ID_ANY, _("Use NTFS"),
                                              _("Use NTFS instead of FAT. NOTE: NTFS seems to be slower than FAT."),
                                              wx.ITEM_CHECK)
        options_menu.Append(self.options_boot)
        options_menu.Append(self.options_filesystem)

        self.__MenuBar = wx.MenuBar()
        self.__MenuBar.Append(file_menu, _("&File"))
        self.__MenuBar.Append(options_menu, _("&Options"))
        self.__MenuBar.Append(help_menu, _("&Help"))

        self.SetMenuBar(self.__MenuBar)

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.__MainPanel = MainPanel(self, wx.ID_ANY)
        main_sizer.Add(self.__MainPanel, 1, wx.EXPAND | wx.ALL, 4)

        self.SetSizer(main_sizer)

        self.Bind(wx.EVT_MENU, self.__MainPanel.on_show_all_drive)

        self.Bind(wx.EVT_MENU, self.on_quit, exit_item)
        self.Bind(wx.EVT_MENU, self.on_about, help_item)

    def on_quit(self, __):
        self.log_debug("Exiting application.")
        self.Close(True)

    def on_about(self, __):
        self.log_debug("Opening 'About' dialog.")
        my_dialog_about = DialogAbout(self, wx.ID_ANY)
        my_dialog_about.ShowModal()

    def is_show_all_checked(self):
        return self.__menuItemShowAll.IsChecked()

    def log_debug(self, message):
        """Logs messages to the debug window if available."""
        if core.debug_window:
            core.debug_window.log_message(message)


class MainPanel(wx.Panel):
    __parent = None

    __dvdDriveList = None
    __usbStickList = wx.ListBox

    __dvdDriveDevList = []
    __usbStickDevList = []

    __isoFile = wx.FilePickerCtrl

    __parentFrame = None

    __btInstall = None
    __btRefresh = None

    __isoChoice = None
    __dvdChoice = None

    def __init__(self, parent, ID, pos=wx.DefaultPosition, size=wx.DefaultSize, style=wx.TAB_TRAVERSAL):
        super(MainPanel, self).__init__(parent, ID, pos, size, style)

        self.__parent = parent

        # Controls
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Iso / CD
        main_sizer.Add(wx.StaticText(self, wx.ID_ANY, _("Source :")), 0, wx.ALL, 3)

        # Iso
        self.__isoChoice = wx.RadioButton(self, wx.ID_ANY, _("From a disk image (iso)"))
        main_sizer.Add(self.__isoChoice, 0, wx.ALL, 3)

        tmp_sizer = wx.BoxSizer(wx.HORIZONTAL)
        tmp_sizer.AddSpacer(20)
        self.__isoFile = wx.FilePickerCtrl(self, wx.ID_ANY, "", _("Please select a disk image"),
                                           "Iso images (*.iso)|*.iso;*.ISO|All files|*")
        tmp_sizer.Add(self.__isoFile, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM, 3)
        main_sizer.Add(tmp_sizer, 0, wx.EXPAND, 0)

        # DVD
        self.__dvdChoice = wx.RadioButton(self, wx.ID_ANY, _("From a CD/DVD drive"))
        main_sizer.Add(self.__dvdChoice, 0, wx.ALL, 3)

        # List
        tmp_sizer = wx.BoxSizer(wx.HORIZONTAL)
        tmp_sizer.AddSpacer(20)
        self.__dvdDriveList = wx.ListBox(self, wx.ID_ANY)
        tmp_sizer.Add(self.__dvdDriveList, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 3)
        main_sizer.Add(tmp_sizer, 1, wx.EXPAND, 0)

        # Target
        main_sizer.AddSpacer(20)

        main_sizer.Add(wx.StaticText(self, wx.ID_ANY, _("Target device :")), 0, wx.ALL, 3)

        # List
        self.__usbStickList = wx.ListBox(self, wx.ID_ANY)
        main_sizer.Add(self.__usbStickList, 1, wx.EXPAND | wx.ALL, 3)

        # Buttons
        main_sizer.AddSpacer(30)

        bt_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.__btRefresh = wx.Button(self, wx.ID_REFRESH)
        bt_sizer.Add(self.__btRefresh, 0, wx.ALL, 3)
        self.__btInstall = wx.Button(self, wx.ID_ANY, _("Install"))
        bt_sizer.Add(self.__btInstall, 0, wx.ALL, 3)

        main_sizer.Add(bt_sizer, 0, wx.ALIGN_RIGHT, 0)

        # Finalization
        self.SetSizer(main_sizer)

        self.Bind(wx.EVT_LISTBOX, self.on_list_or_file_modified, self.__usbStickList)
        self.Bind(wx.EVT_LISTBOX, self.on_list_or_file_modified, self.__dvdDriveList)
        self.Bind(wx.EVT_FILEPICKER_CHANGED, self.on_list_or_file_modified, self.__isoFile)

        self.Bind(wx.EVT_BUTTON, self.on_install, self.__btInstall)
        self.Bind(wx.EVT_BUTTON, self.on_refresh, self.__btRefresh)

        self.Bind(wx.EVT_RADIOBUTTON, self.on_source_option_changed, self.__isoChoice)
        self.Bind(wx.EVT_RADIOBUTTON, self.on_source_option_changed, self.__dvdChoice)

        self.refresh_list_content()
        self.on_source_option_changed(wx.CommandEvent)
        self.__btInstall.Enable(self.is_install_ok())

    def refresh_list_content(self):
        # Log action
        self.log_debug("Refreshing device lists...")

        # USB
        self.__usbStickDevList = []
        self.__usbStickList.Clear()

        show_all_checked = self.__parent.is_show_all_checked()

        # Fetching device lists from list_devices module
        device_list = list_devices.usb_drive(show_all_checked)
        for device in device_list:
            self.__usbStickDevList.append(device[0])
            self.__usbStickList.Append(device[1])

        # ISO
        self.__dvdDriveDevList = []
        self.__dvdDriveList.Clear()

        drive_list = list_devices.dvd_drive()
        for drive in drive_list:
            self.__dvdDriveDevList.append(drive[0])
            self.__dvdDriveList.Append(drive[1])

        self.__btInstall.Enable(self.is_install_ok())
        self.log_debug("Device lists refreshed.")

    def on_source_option_changed(self, __):
        is_iso = self.__isoChoice.GetValue()

        self.__isoFile.Enable(is_iso)
        self.__dvdDriveList.Enable(not is_iso)

        self.__btInstall.Enable(self.is_install_ok())
        self.log_debug(f"Source option changed to {'ISO' if is_iso else 'DVD drive'}.")

    def is_install_ok(self):
        is_iso = self.__isoChoice.GetValue()
        install_ok = ((is_iso and os.path.isfile(self.__isoFile.GetPath())) or (
                not is_iso and self.__dvdDriveList.GetSelection() != wx.NOT_FOUND)) and self.__usbStickList.GetSelection() != wx.NOT_FOUND
        self.log_debug(f"Install button enabled: {install_ok}")
        return install_ok

    def on_list_or_file_modified(self, event):
        if event.GetEventType() == wx.EVT_LISTBOX and not event.IsSelection():
            return

        self.__btInstall.Enable(self.is_install_ok())
        self.log_debug("List or file modified.")

    def on_refresh(self, __):
        self.log_debug("Refreshing lists on button press.")
        self.refresh_list_content()

    def on_install(self, __):
        global uniflash
        self.log_debug("Install process initiated.")
        if wx.MessageBox(
            _("Are you sure? This will delete all your files and wipe out the selected partition."),
            _("Cancel"),
            wx.YES_NO | wx.ICON_QUESTION | wx.NO_DEFAULT,
            self) != wx.YES:
            self.log_debug("Installation canceled by user.")
            return
        if self.is_install_ok():
            is_iso = self.__isoChoice.GetValue()

            device = self.__usbStickDevList[self.__usbStickList.GetSelection()]

            if is_iso:
                iso = self.__isoFile.GetPath()
            else:
                iso = self.__dvdDriveDevList[self.__dvdDriveList.GetSelection()]

            if self.__parent.options_filesystem.IsChecked():
                filesystem = "NTFS"
            else:
                filesystem = "FAT"
        
            uniflash = UniFlash_handler(iso, device, boot_flag=self.__parent.options_boot.IsChecked(), filesystem=filesystem)
            uniflash.start()

            self.log_debug(f"Installation started for {device} using {iso} (filesystem: {filesystem}).")

            dialog = wx.ProgressDialog(_("Installing"), _("Please wait..."), 101, self.GetParent(),
                                       wx.PD_APP_MODAL | wx.PD_SMOOTH | wx.PD_CAN_ABORT)

            while uniflash.is_alive():
                if not uniflash.progress:
                    status = dialog.Pulse(uniflash.state)[0]
                    time.sleep(0.06)
                else:
                    status = dialog.Update(uniflash.progress, uniflash.state)[0]

                if not status:
                    if wx.MessageBox(_("Are you sure you want to cancel the installation?"), _("Cancel"),
                                     wx.YES_NO | wx.ICON_QUESTION, self) == wx.NO:
                        dialog.Resume()
                    else:
                        uniflash.kill = True
                        self.log_debug("Installation aborted by user.")
                        break
            dialog.Destroy()

            if uniflash.error == "":
                wx.MessageBox(_("Installation succeeded!"), _("Installation"), wx.OK | wx.ICON_INFORMATION, self)
                self.log_debug("Installation completed successfully.")
            else:
                wx.MessageBox(_("Installation failed!") + "\n" + str(uniflash.error), _("Installation"),
                              wx.OK | wx.ICON_ERROR,
                              self)
                self.log_debug(f"Installation failed: {uniflash.error}")

    def on_show_all_drive(self, __):
        self.refresh_list_content()

    def log_debug(self, message):
        """Logs messages to the debug window if available."""
        if core.debug_window:
            core.debug_window.log_message(message)


class DialogAbout(wx.Dialog):
    pass  # No changes needed


class UniFlash_handler(threading.Thread):
    """
    Class for handling communication with UniFlash.
    """
    progress = False
    state = ""
    error = ""
    kill = False

    def __init__(self, source, target, boot_flag, filesystem):
        super(UniFlash_handler, self).__init__()  # Proper initialization

        # Set reference to the GUI
        core.gui = self
        self.source = source
        self.target = target
        self.boot_flag = boot_flag
        self.filesystem = filesystem

    def run(self):
        # Setup subprocess to run in the background (hidden)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # Call core module to handle installation
        source_fs_mountpoint, target_fs_mountpoint, temp_directory, target_media = core.init(
            from_cli=False,
            install_mode="device",
            source_media=self.source,
            target_media=self.target
        )
        
        try:
            core.main(source_fs_mountpoint, target_fs_mountpoint, self.source, self.target, "device", temp_directory,
                      self.filesystem, self.boot_flag)
        except SystemExit:
            pass

        # Clean up after installation
        core.cleanup(source_fs_mountpoint, target_fs_mountpoint, temp_directory, target_media)


def run():
    frameTitle = "UniFlash"

    frame = MainFrame(frameTitle, wx.DefaultPosition, wx.Size(400, 600))
    frame.SetMinSize(wx.Size(300, 450))

    frame.Show(True)
    app.MainLoop()


if __name__ == "__main__":
    run()
