import os
from .Util import (
    getPlatform,
    checkIfDeps,
    printAndLog,
    pythonPath,
    backendDirectory,
    isFlatpak,
)
from .version import version


class BackendHandler:
    def __init__(self, parent):
        self.parent = parent

    def enableCorrectBackends(self):
        self.parent.downloadTorchROCmBtn.setEnabled(getPlatform() == "linux")
        if getPlatform() == "darwin":
            self.parent.downloadTorchCUDABtn.setEnabled(False)
            self.parent.downloadTensorRTBtn.setEnabled(False)
        if isFlatpak():
            self.parent.downloadTorchCUDABtn.setEnabled(False)
            self.parent.downloadTorchROCmBtn.setEnabled(False)
            self.parent.downloadTensorRTBtn.setEnabled(False)

        # disable as it is not complete
        try:
            self.parent.downloadDirectMLBtn.setEnabled(False)
            if getPlatform() != "win32":
                self.parent.downloadDirectMLBtn.setEnabled(False)
        except Exception as e:
            print(e)

    def hideUninstallButtons(self):
        self.parent.uninstallTorchCUDABtn.setVisible(False)
        self.parent.uninstallTorchROCmBtn.setVisible(False)
        self.parent.uninstallNCNNBtn.setVisible(False)
        self.parent.uninstallTensorRTBtn.setVisible(False)
        self.parent.uninstallDirectMLBtn.setVisible(False)

    def showUninstallButton(self, backends):
        if "pytorch" in backends:
            self.parent.downloadTorchCUDABtn.setVisible(False)
            self.parent.downloadTorchROCmBtn.setVisible(False)
            self.parent.uninstallTorchCUDABtn.setVisible(True)
            self.parent.uninstallTorchROCmBtn.setVisible(True)
        if "ncnn" in backends:
            self.parent.downloadNCNNBtn.setVisible(False)
            self.parent.uninstallNCNNBtn.setVisible(True)
        if "tensorrt" in backends:
            self.parent.downloadTensorRTBtn.setVisible(False)
            self.parent.uninstallTensorRTBtn.setVisible(True)

        # disable as it is not complete
        try:
            self.parent.downloadDirectMLBtn.setEnabled(False)
            if getPlatform() != "win32":
                self.parent.downloadDirectMLBtn.setEnabled(False)
        except Exception as e:
            print(e)

    def setupBackendDeps(self):
        # need pop up window
        from .DownloadDeps import DownloadDependencies

        downloadDependencies = DownloadDependencies()
        downloadDependencies.downloadBackend(version)
        if not checkIfDeps():
            from .ui.QTcustom import NetworkCheckPopup

            if NetworkCheckPopup():
                # Dont flip these due to shitty code!
                downloadDependencies.downloadFFMpeg()
                downloadDependencies.downloadPython()
                if getPlatform() == "win32":
                    downloadDependencies.downloadVCREDLIST()

    def recursivlyCheckIfDepsOnFirstInstallToMakeSureUserHasInstalledAtLeastOneBackend(
        self, firstIter=True
    ):
        from .DownloadDeps import DownloadDependencies
        from .ui.QTcustom import RegularQTPopup, DownloadDepsDialog

        """
        will keep trying until the user installs at least 1 backend, happens when user tries to close out of backend slect and gets an error
        """
        try:
            self.availableBackends, self.fullOutput = self.getAvailableBackends()
            if not len(self.availableBackends) == 0:
                return self.availableBackends, self.fullOutput
        except SyntaxError as e:
            printAndLog(str(e))
        if not firstIter:
            RegularQTPopup("Please install at least 1 backend!")
        downloadDependencies = DownloadDependencies()
        DownloadDepsDialog(
            ncnnDownloadBtnFunc=lambda: downloadDependencies.downloadNCNNDeps(True),
            pytorchCUDABtnFunc=lambda: downloadDependencies.downloadPyTorchCUDADeps(
                True
            ),
            pytorchROCMBtnFunc=lambda: downloadDependencies.downloadPyTorchROCmDeps(
                True
            ),
            trtBtnFunc=lambda: downloadDependencies.downloadTensorRTDeps(True),
            directmlBtnFunc=lambda: downloadDependencies.downloadDirectMLDeps(True),
        )
        return self.recursivlyCheckIfDepsOnFirstInstallToMakeSureUserHasInstalledAtLeastOneBackend(
            firstIter=False
        )

    def getAvailableBackends(self):
        from .ui.QTcustom import SettingUpBackendPopup

        output = SettingUpBackendPopup(
            [
                pythonPath(),
                "-W",
                "ignore",
                os.path.join(backendDirectory(), "rve-backend.py"),
                "--list_backends",
            ]
        )
        output: str = output.getOutput()
        output = output.split(" ")
        # hack to filter out bad find
        new_out = ""
        for word in output:
            if "objc" in word:
                continue
            new_out += word + " "
        output = new_out
        # Find the part of the output containing the backends list
        start = output.find("[")
        end = output.find("]") + 1
        backends_str = output[start:end]

        # Convert the string representation of the list to an actual list
        backends = eval(backends_str)

        return backends, output
