import sys
import os

# patch for macos
if sys.platform == "darwin":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    # this goes one step up, and goes into the actual directory. This is where backend will be copied to.
    os.chdir("..")
import re
import math
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtGui import QIcon
from src.Util import printAndLog
from mainwindow import Ui_MainWindow
from PySide6 import QtSvg  # Import the QtSvg module so svg icons can be used on windows
from src.version import version
from src.InputHandler import VideoInputHandler

# other imports
from src.Util import (
    openLink,
    getOSInfo,
    get_gpu_info,
    getRAMAmount,
    getCPUInfo,
    checkForWritePermissions,
    getAvailableDiskSpace,
    copyFile,
    customModelsPath,
    createDirectory,
)
from src.ui.ProcessTab import ProcessTab
from src.ui.DownloadTab import DownloadTab
from src.ui.SettingsTab import SettingsTab, Settings
from src.Backendhandler import BackendHandler
from src.ModelHandler import totalModels
from src.ui.AnimationHandler import AnimationHandler
from src.ui.QTstyle import Palette
from src.ui.QTcustom import RegularQTPopup


class MainWindow(QMainWindow, Ui_MainWindow):
    """Main window class for the REAL Video Enhancer application.

    This class extends the QMainWindow and Ui_MainWindow classes to create the main window of the application.
    It sets up the user interface, connects buttons to switch menus, and handles various functionalities such as rendering, file selection, and backend setup.

    Attributes:
        homeDir (str): The home directory path.
        interpolateTimes (int): The number of times to interpolate frames.
        upscaleTimes (int): The number of times to upscale frames.
        pipeInFrames (None): Placeholder for input frames.
        latestPreviewImage (None): Placeholder for the latest preview image.
        aspect_ratio (float): The aspect ratio of the window.

    Methods:
        __init__(): Initializes the MainWindow class.
        QButtonConnect(): Connects buttons to switch menus.
        setupBackendDeps(): Sets up the backend dependencies.
        switchToHomePage(): Switches to the home page.
        switchToProcessingPage(): Switches to the processing page.
        switchToSettingsPage(): Switches to the settings page.
        switchToDownloadPage(): Switches to the download page.
        recursivlyCheckIfDepsOnFirstInstallToMakeSureUserHasInstalledAtLeastOneBackend(): Recursively checks if at least one backend is installed.
        startRender(): Starts the rendering process.
        disableProcessPage(): Disables the process page.
        enableProcessPage(): Enables the process page.
        getAvailableBackends(): Retrieves the available backends.
        openInputFile(): Opens an input video file.
        openOutputFolder(): Opens an output folder.
        killRenderProcess(): Terminates the render process.
        closeEvent(event): Handles the close event of the main window."""

    def __init__(self):
        super().__init__()

        # set up base variables
        self.homeDir = os.path.expanduser("~")
        self.pipeInFrames = None
        self.latestPreviewImage = None
        self.videoWidth = None
        self.videoHeight = None
        self.isVideoLoaded = False

        # setup application

        # Set up the user interface from Designer.
        self.setupUi(self)
        backendHandler = BackendHandler(self)
        backendHandler.enableCorrectBackends()

        backendHandler.setupBackendDeps()
        self.backends, self.fullOutput = (
            backendHandler.recursivlyCheckIfDepsOnFirstInstallToMakeSureUserHasInstalledAtLeastOneBackend(
                firstIter=True
            )
        )

        backendHandler.hideUninstallButtons()
        backendHandler.showUninstallButton(self.backends)
        icon_path = ":/icons/icons/logo-v2.svg"
        self.setWindowIcon(QIcon(icon_path))
        QApplication.setWindowIcon(QIcon(icon_path))
        self.setWindowTitle("REAL Video Enhancer")
        self.setPalette(QApplication.style().standardPalette())
        self.setMinimumSize(1100, 700)

        self.aspect_ratio = self.width() / self.height()

        # set default home page
        self.stackedWidget.setCurrentIndex(0)

        self.QConnect()
        # set up tabs
        self.backendComboBox.addItems(self.backends)
        printOut = (
            "------REAL Video Enhancer------\n"
            + "System Information: \n"
            + "OS: "
            + getOSInfo()
            + "\n"
            + "CPU: "
            + getCPUInfo()
            + "\n"
            + "GPU: "
            + get_gpu_info()
            + "\n"
            + "RAM: "
            + getRAMAmount()
            + "\n"
            + "Available Disk Space: "
            + str(round(getAvailableDiskSpace(), 2))
            + "GB"
            + "\n"
            + "-------------------------------------------\n"
            + "Software Information: \n"
            + f"REAL Video Enhancer Version: {version}\n"
            + self.fullOutput
        )
        self.renderOutput.setText(printOut)
        printAndLog(printOut)

        halfPrecisionSupport = re.search(
            "half precision support: \s*(true|false)", self.fullOutput.lower()
        )
        if halfPrecisionSupport:
            halfPrecisionSupport = halfPrecisionSupport.group(1) == "true"
        else:
            halfPrecisionSupport = False

        gmfssSupport = re.search(
            "gmfss support: \s*(true|false)", self.fullOutput.lower()
        )
        if gmfssSupport:
            gmfssSupport = gmfssSupport.group(1) == "true"
        else:
            gmfssSupport = False
        settings = Settings()
        settings.readSettings()
        self.settings = settings
        self.processTab = ProcessTab(
            parent=self,
            gmfssSupport=gmfssSupport,
        )

        self.downloadTab = DownloadTab(parent=self, installed_backends=self.backends)
        self.settingsTab = SettingsTab(
            parent=self, halfPrecisionSupport=halfPrecisionSupport
        )

        # Startup Animation
        self.animationHandler = AnimationHandler()
        self.animationHandler.fadeInAnimation(self)

    def QConnect(self):
        # connect buttons to switch menus
        self.homeBtn.clicked.connect(self.switchToHomePage)
        self.processBtn.clicked.connect(self.switchToProcessingPage)
        self.settingsBtn.clicked.connect(self.switchToSettingsPage)
        self.downloadBtn.clicked.connect(self.switchToDownloadPage)
        # connect getting default output file
        self.githubBtn.clicked.connect(
            lambda: openLink("https://github.com/tntwise/REAL-Video-Enhancer")
        )
        self.kofiBtn.clicked.connect(lambda: openLink("https://ko-fi.com/tntwise"))

    def setButtonsUnchecked(self, buttonToIgnore):
        buttons = [
            self.homeBtn,
            self.processBtn,
            self.settingsBtn,
            self.downloadBtn,
        ]
        for button in buttons:
            if button != buttonToIgnore:
                button.setChecked(False)
            else:
                button.setChecked(True)

    # switch menus
    def switchToHomePage(self):
        self.animationHandler.fadeOutAnimation(self.stackedWidget)
        self.stackedWidget.setCurrentWidget(self.homePage)
        self.setButtonsUnchecked(self.homeBtn)
        self.animationHandler.fadeInAnimation(self.stackedWidget)

    def switchToProcessingPage(self):
        self.animationHandler.fadeOutAnimation(self.stackedWidget)
        self.stackedWidget.setCurrentWidget(self.procPage)
        self.setButtonsUnchecked(self.processBtn)
        self.animationHandler.fadeInAnimation(self.stackedWidget)

    def switchToSettingsPage(self):
        self.animationHandler.fadeOutAnimation(self.stackedWidget)
        self.stackedWidget.setCurrentWidget(self.settingsPage)
        self.setButtonsUnchecked(self.settingsBtn)
        self.animationHandler.fadeInAnimation(self.stackedWidget)

    def switchToDownloadPage(self):
        self.animationHandler.fadeOutAnimation(self.stackedWidget)
        self.stackedWidget.setCurrentWidget(self.downloadPage)
        self.setButtonsUnchecked(self.downloadBtn)
        self.animationHandler.fadeInAnimation(self.stackedWidget)

    def generateDefaultOutputFile(
        self,
        inputVideo: str,
        interpolationTimes: int,
        upscaleTimes: int,
        videoFps: float,
        videoWidth: int,
        videoHeight: int,
        outputDirectory: str,
    ):
        print(
            f"inputVideo: {inputVideo}\ninterpolationTimes: {interpolationTimes}\nupscaleTimes: {upscaleTimes}\nvideoFps: {videoFps}\nvideoWidth: {videoWidth}\nvideoHeight: {videoHeight}\noutputDirectory: {outputDirectory}"
        )
        """
        Generates the default output file name based on the input file and the current settings
        """
        file_name = os.path.splitext(os.path.basename(inputVideo))[0]
        self.output_file = os.path.join(
            outputDirectory,
            f"{file_name}_{interpolationTimes*videoFps}fps_{upscaleTimes*videoWidth}x{upscaleTimes*videoHeight}.mkv",
        )
        iteration = 0
        while os.path.isfile(self.output_file):
            self.output_file = os.path.join(
                outputDirectory,
                f"{file_name}_{interpolationTimes*videoFps}fps_{upscaleTimes*videoWidth}x{upscaleTimes*videoHeight}_({iteration}).mkv",
            )
            iteration += 1
        return self.output_file

    def updateVideoGUIText(self):
        if self.isVideoLoaded:
            modelName = self.modelComboBox.currentText()
            method = self.methodComboBox.currentText()
            interpolateTimes = self.getInterpolateTimes(method, modelName)
            scale = self.getScale(method, modelName)
            text = (
                f"FPS: {round(self.videoFps,0)} -> {round(self.videoFps*interpolateTimes,0)}\n"
                + f"Resolution: {self.videoWidth}x{self.videoHeight} -> {self.videoWidth*scale}x{self.videoHeight*scale}\n"
                + f"Frame Count: {self.videoFrameCount} -> {int(round(self.videoFrameCount * interpolateTimes,0))}\n"
                + f"Bitrate: {self.videoBitrate}\n"
                + f"Encoder: {self.videoEncoder}\n"
                + f"Container: {self.videoContainer}\n"
            )
            self.videoInfoTextEdit.setFontPointSize(10)
            self.videoInfoTextEdit.setText(text)

    def setDefaultOutputFile(self, outputDirectory):
        """
        Sets the default output file for the video enhancer.
        Parameters:
        - useDefaultVideoPath (bool): Flag indicating whether to use the default video path for the output file.
        Returns:
        None
        """
        # check if there is a video loaded
        if self.isVideoLoaded:
            inputFile = self.inputFileText.text()
            modelName = self.modelComboBox.currentText()
            method = self.methodComboBox.currentText()
            interpolateTimes = self.getInterpolateTimes(method, modelName)
            scale = self.getScale(method, modelName)

            outputText = self.generateDefaultOutputFile(
                inputFile,
                interpolateTimes,
                int(scale),
                round(self.videoFps, 0),
                int(self.videoWidth),
                int(self.videoHeight),
                outputDirectory=outputDirectory,
            )
            self.outputFileText.setText(outputText)
            print(outputText)
            return outputText

    def updateVideoGUIDetails(self):
        self.settings.readSettings()
        self.setDefaultOutputFile(self.settings.settings["output_folder_location"])
        self.updateVideoGUIText()

    def getScale(self, method, modelName):
        if method == "Upscale":
            scale = totalModels[modelName][2]
        elif method == "Interpolate":
            scale = 1
        return scale

    def getInterpolateTimes(self, method, modelName):
        if method == "Upscale":
            interpolateTimes = 1
        elif method == "Interpolate":
            interpolateTimes = self.interpolationMultiplierSpinBox.value()
        return interpolateTimes

    def startRender(self):
        if self.isVideoLoaded:
            if checkForWritePermissions(os.path.dirname(self.outputFileText.text())):
                self.startRenderButton.setEnabled(False)
                method = self.methodComboBox.currentText()
                self.progressBar.setRange(
                    0,
                    # only set the range to multiply the frame count if the method is interpolate
                    int(
                        self.videoFrameCount
                        * math.ceil(self.interpolationMultiplierSpinBox.value())
                    )
                    if method == "Interpolate"
                    else self.videoFrameCount,
                )
                self.disableProcessPage()

                self.processTab.run(
                    inputFile=self.inputFileText.text(),
                    outputPath=self.outputFileText.text(),
                    videoWidth=self.videoWidth,
                    videoHeight=self.videoHeight,
                    videoFps=self.videoFps,
                    tilingEnabled=self.tilingCheckBox.isChecked(),
                    tilesize=self.tileSizeComboBox.currentText(),
                    videoFrameCount=self.videoFrameCount,
                    method=method,
                    backend=self.backendComboBox.currentText(),
                    interpolationTimes=self.interpolationMultiplierSpinBox.value(),
                    model=self.modelComboBox.currentText(),
                    benchmarkMode=self.benchmarkModeCheckBox.isChecked(),
                )
            else:
                RegularQTPopup("No write permissions to the output directory!")
        else:
            pass
            RegularQTPopup("Please select a video file!")

    def onRenderCompletion(self):
        try:
            self.processTab.workerThread.stop()
            self.processTab.workerThread.quit()
            self.processTab.workerThread.wait()
        except Exception:
            pass  # pass just incase internet error caused a skip
        # reset image preview
        self.previewLabel.clear()
        self.startRenderButton.clicked.disconnect()
        self.startRenderButton.clicked.connect(self.startRender)

        self.enableProcessPage()

    def disableProcessPage(self):
        self.processSettingsContainer.setDisabled(True)

    def enableProcessPage(self):
        self.processSettingsContainer.setEnabled(True)

    def loadVideo(self, inputFile):
        videoHandler = VideoInputHandler(inputText=inputFile)
        if videoHandler.isYoutubeLink() and videoHandler.isValidYoutubeLink():
            videoHandler.getDataFromYoutubeVideo()
        elif videoHandler.isValidVideoFile():
            videoHandler.getDataFromLocalVideo()
        else:
            RegularQTPopup("Not a valid input!")
            return
        (
            self.videoWidth,
            self.videoHeight,
            self.videoFps,
            self.videoLength,
            self.videoFrameCount,
            self.videoEncoder,
            self.videoBitrate,
            self.videoContainer,
        ) = videoHandler.getData()

        self.inputFileText.setText(inputFile)
        self.outputFileText.setEnabled(True)
        self.outputFileSelectButton.setEnabled(True)
        self.isVideoLoaded = True
        self.updateVideoGUIDetails()

    # input file button
    def openInputFile(self):
        """
        Opens a video file and checks if it is valid,

        if it is valid, it will set self.inputFile to the input file, and set the text input field to the input file path.
        if it is not valid, it will give a warning to the user.

        > IMPLEMENT AFTER SELECT AI >  Last, It will enable the output select button, and auto create a default output file

        *NOTE
        This function will set self.videoWidth, self.videoHeight, and self.videoFps

        """

        fileFilter = "Video files (*.mp4 *.mov *.webm *.mkv)"
        inputFile, _ = QFileDialog.getOpenFileName(
            parent=self,
            caption="Select File",
            dir=self.homeDir,
            filter=fileFilter,
        )
        self.loadVideo(inputFile)

    def importCustomModel(self, format: str):
        """
        *args
        format: str
            The format of the model to import (pytorch, ncnn)
        """

        if format == "pytorch":
            fileFilter = "PyTorch Model (*.pth)"

            modelFile, _ = QFileDialog.getOpenFileName(
                parent=self,
                caption="Select PyTorch Model",
                dir=self.homeDir,
                filter=fileFilter,
            )
            outputModelPath = os.path.join(
                customModelsPath(), os.path.basename(modelFile)
            )
            copyFile(modelFile, customModelsPath())
            if os.path.isfile(outputModelPath):
                RegularQTPopup(
                    "Model imported successfully!\nPlease restart the app for the changes to take effect."
                )
            else:
                RegularQTPopup("Failed to import model!\nPlease try again.")

        elif format == "ncnn":
            binFileFilter = "NCNN Bin (*.bin)"
            modelBinFile, _ = QFileDialog.getOpenFileName(
                parent=self,
                caption="Select NCNN Bin",
                dir=self.homeDir,
                filter=binFileFilter,
            )
            if modelBinFile == "":
                RegularQTPopup("Please select a bin file!")
                return
            modelParamFile, _ = QFileDialog.getOpenFileName(
                parent=self,
                caption="Select NCNN Param",
                dir=os.path.dirname(modelBinFile),
                filter=os.path.basename(modelBinFile).replace(".bin", ".param"),
            )
            if modelParamFile == "":
                RegularQTPopup("Please select a param file!")
                return
            outputModelFolder = os.path.join(
                customModelsPath(), os.path.basename(modelBinFile).replace(".bin", "")
            )
            createDirectory(outputModelFolder)
            outputBinPath = os.path.join(
                outputModelFolder, os.path.basename(modelBinFile)
            )
            copyFile(modelBinFile, outputModelFolder)
            outputParamPath = os.path.join(
                outputModelFolder, os.path.basename(modelParamFile)
            )
            copyFile(modelParamFile, outputModelFolder)

            if os.path.isfile(outputBinPath) and os.path.isfile(outputParamPath):
                RegularQTPopup(
                    "Model imported successfully!\nPlease restart the app for the changes to take effect."
                )
            else:
                RegularQTPopup("Failed to import model!\nPlease try again.")

    # output file button
    def openOutputFolder(self):
        """
        Opens a folder,
        sets the directory that is selected to the self.outputFolder variable
        sets the outputFileText to the output directory

        It will also read the input file name, and generate an output file based on it.
        """
        outputFolder = QFileDialog.getExistingDirectory(
            self,
            caption="Select Output Directory",
            dir=self.homeDir,
        )
        self.outputFileText.setText(
            os.path.join(outputFolder, self.setDefaultOutputFile(outputFolder))
        )

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            "",
            "Are you sure you want to exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,  # type: ignore
        )
        if reply == QMessageBox.Yes:  # type: ignore
            self.processTab.killRenderProcess()
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # setting the pallette

    app.setPalette(Palette())
    window = MainWindow()
    if len(sys.argv) > 1:
        if sys.argv[1] == "--fullscreen":
            window.showFullScreen()
    window.show()
    sys.exit(app.exec())
