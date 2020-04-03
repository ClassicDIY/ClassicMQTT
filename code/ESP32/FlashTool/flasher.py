import sys
import os
import serial
import webbrowser
import flasher_esptool as esptool
import json

from datetime import datetime
from PyQt5.QtCore import QUrl, Qt, QThread, QObject, pyqtSignal, pyqtSlot, QSettings, QTimer, QSize, QIODevice
from PyQt5.QtGui import QPixmap
from PyQt5.QtNetwork import QNetworkRequest, QNetworkAccessManager, QNetworkReply
from PyQt5.QtSerialPort import QSerialPortInfo, QSerialPort
from PyQt5.QtWidgets import QApplication, QDialog, QLineEdit, QPushButton, QComboBox, QWidget, QCheckBox, QRadioButton, \
    QButtonGroup, QFileDialog, QProgressBar, QLabel, QMessageBox, QDialogButtonBox, QGroupBox, QFormLayout
from gui import HLayout, VLayout, GroupBoxH, GroupBoxV, SpinBox, dark_palette

class StdOut(object):
    def __init__(self, processor):
        self.processor = processor

    def write(self, text):
        self.processor(text)

    def flush(self):
        pass

class ESPWorker(QObject):
    finished = pyqtSignal()
    port_error = pyqtSignal(str)
    backup_start = pyqtSignal()

    def __init__(self, port, bin_file):
        super().__init__()
        self.port = port
        self.bin_file = bin_file
        self.continue_flag = True

    @pyqtSlot()
    def execute(self):
        esptool.sw.setContinueFlag(True)
        command_base = ["--chip", "esp32", "--port", self.port, "--baud", "115200"]
        command_write = ["write_flash", "--flash_mode", "dio", "0x00010000", self.bin_file]

        if self.continue_flag:
            command = command_base + command_write
            try:
                esptool.main(command)
                self.finished.emit()
            except Exception as e:
            # except esptool.FatalError or serial.SerialException as e:
                self.port_error.emit("{}".format(e))

    @pyqtSlot()
    def stop(self):
        self.continue_flag = False
        esptool.sw.setContinueFlag(False)


class SendConfigDialog(QDialog):

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(640)
        self.setWindowTitle("Send wifi configuration to device")
        self.commands = None
        self.module_mode = 0
        self.createUI()

    def createUI(self):
        vl = VLayout()
        self.setLayout(vl)
        # Wifi groupbox
        self.gbWifi = QGroupBox("WiFi")
        self.gbWifi.setCheckable(False)
        flWifi = QFormLayout()
        self.leAP = QLineEdit()
        self.leAPPwd = QLineEdit()
        self.leAPPwd.setEchoMode(QLineEdit.Password)
        flWifi.addRow("SSID", self.leAP)
        flWifi.addRow("Password", self.leAPPwd)
        self.gbWifi.setLayout(flWifi)
        vl_wifis = VLayout(0)
        vl_wifis.addWidgets([self.gbWifi])
        hl_wifis_mqtt = HLayout(0)
        hl_wifis_mqtt.addLayout(vl_wifis)
        vl.addLayout(hl_wifis_mqtt)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        vl.addWidget(btns)

    def accept(self):
        ok = True

        if (len(self.leAP.text()) == 0 or len(self.leAPPwd.text()) == 0):
            ok = False
            QMessageBox.warning(self, "WiFi details incomplete", "Input WiFi SSID and Password")
        if ok:
            x = {"ssid": self.leAP.text(), "password": self.leAPPwd.text() }
            self.commands = json.dumps(x)
            print (self.commands)
            self.done(QDialog.Accepted)

class FlashingDialog(QDialog):

    def __init__(self, parent):
        super().__init__()
        self.setWindowTitle("Flashing...")
        esptool.sw.read_start.connect(self.read_start)
        esptool.sw.read_progress.connect(self.read_progress)
        esptool.sw.read_finished.connect(self.read_finished)
        esptool.sw.erase_start.connect(self.erase_start)
        esptool.sw.erase_finished.connect(self.erase_finished)
        esptool.sw.write_start.connect(self.write_start)
        esptool.sw.write_progress.connect(self.write_progress)
        esptool.sw.write_finished.connect(self.write_finished)
        self.setFixedWidth(400)
        self.nrBinFile = QNetworkRequest()
        self.parent = parent
        vl = VLayout(10, 10)
        self.setLayout(vl)
        self.bin_data = b""
        self.error_msg = None
        self.progress_task = QProgressBar()
        self.progress_task.setFixedHeight(45)
        self.task = QLabel()
        self.erase_timer = QTimer()
        self.erase_timer.setSingleShot(False)
        self.erase_timer.timeout.connect(self.erase_progress)
        self.btns = QDialogButtonBox(QDialogButtonBox.Abort)
        self.dlgText = QLabel("Press the Boot button for a few seconds to start the flashing process")
        vl.addWidgets([self.dlgText, self.task, self.progress_task, self.btns])
        self.btns.rejected.connect(self.abort)
        # process starts
        self.bin_file = parent.bin_file
        self.run_esptool()

    def updateBinProgress(self, recv, total):
        self.progress_task.setValue(recv//total*100)

    def read_start(self):
        self.progress_task.setValue(0)
        self.task.setText("Saving image backup...")

    def read_progress(self, value):
        self.progress_task.setValue(value)

    def read_finished(self):
        self.progress_task.setValue(100)
        self.task.setText("Writing done.")

    def erase_start(self):
        self.btns.setEnabled(False)
        self.progress_task.setValue(0)
        self.task.setText("Erasing flash... (this may take a while)")
        self.erase_timer.start(1000)

    def erase_progress(self):
        self.progress_task.setValue(self.progress_task.value()+5)

    def erase_finished(self):
        self.progress_task.setValue(100)
        self.task.setText("Erasing done.")
        self.erase_timer.stop()
        self.btns.setEnabled(True)

    def write_start(self):
        self.dlgText.setText("Flashing in progress...")
        self.progress_task.setValue(0)
        self.task.setText("Writing image...")

    def write_progress(self, value):
        self.progress_task.setValue(value)

    def write_finished(self):
        self.progress_task.setValue(100)
        self.task.setText("Writing done.")
        self.accept()

    def run_esptool(self):
        self.espthread = QThread()
        self.espworker = ESPWorker(self.parent.cbxPort.currentData(), self.bin_file)
        self.espworker.port_error.connect(self.error)
        self.espworker.moveToThread(self.espthread)
        self.espthread.started.connect(self.espworker.execute)
        self.espthread.start()

    def abort(self):
        self.espworker.stop()
        self.espthread.quit()
        self.espthread.wait(2000)
        self.reject()

    def error(self, e):
        self.error_msg = e
        self.reject()

    def accept(self):
        self.espworker.stop()
        self.espthread.quit()
        self.espthread.wait(2000)
        self.done(QDialog.Accepted)

class Flasher(QDialog):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ESP32 Flasher 1.0")
        self.setMinimumWidth(480)
        self.mode = 0  # BIN file
        self.bin_file = os. getcwd() + "\\firmware.bin"
        self.release_data = b""
        self.createUI()
        self.refreshPorts()
        self.jsonStart = False
        self.jsonBuffer = ""

    def createUI(self):
        vl = VLayout()
        self.setLayout(vl)

        # Port groupbox
        gbPort = GroupBoxH("Select port", 3)
        self.cbxPort = QComboBox()
        pbRefreshPorts = QPushButton("Refresh")
        gbPort.addWidget(self.cbxPort)
        gbPort.addWidget(pbRefreshPorts)
        gbPort.layout().setStretch(0, 4)
        gbPort.layout().setStretch(1, 1)

        # Firmware groupbox
        gbFW = GroupBoxV("Select image", 3)

        self.wFile = QWidget()
        hl_file = HLayout(0)
        self.file = QLineEdit()
        self.file.setReadOnly(True)
        
        self.file.setText(self.bin_file)
        pbFile = QPushButton("Open")
        hl_file.addWidgets([self.file, pbFile])
        self.wFile.setLayout(hl_file)
        gbFW.addWidgets([self.wFile])

        # Buttons
        self.pbFlash = QPushButton("Flash!")
        self.pbFlash.setFixedHeight(50)
        self.pbFlash.setStyleSheet("background-color: #223579;")
        self.pbConfig = QPushButton("Setup WIFI")
        self.pbConfig.setStyleSheet("background-color: #571054;")
        self.pbConfig.setFixedHeight(50)
        self.pbQuit = QPushButton("Quit")
        self.pbQuit.setStyleSheet("background-color: #c91017;")
        self.pbQuit.setFixedSize(QSize(50, 50))
        hl_btns = HLayout([50, 3, 50, 3])
        hl_btns.addWidgets([self.pbFlash, self.pbConfig, self.pbQuit])
        vl.addWidgets([gbPort, gbFW])
        vl.addLayout(hl_btns)
        pbRefreshPorts.clicked.connect(self.refreshPorts)
        pbFile.clicked.connect(self.openBinFile)
        self.pbFlash.clicked.connect(self.start_process)
        self.pbConfig.clicked.connect(self.send_config)
        self.pbQuit.clicked.connect(self.reject)

    def refreshPorts(self):
        self.cbxPort.clear()
        ports = reversed(sorted(port.portName() for port in QSerialPortInfo.availablePorts()))
        for p in ports:
            port = QSerialPortInfo(p)
            self.cbxPort.addItem(port.portName(), port.systemLocation())

    def setBinMode(self, radio):
        self.mode = radio
        self.wFile.setVisible(self.mode == 0)

    def appendReleaseInfo(self):
        self.release_data += self.release_reply.readAll()

    def openBinFile(self):
        file, ok = QFileDialog.getOpenFileName(self, "Select Firmware image", self.bin_file, filter="BIN files (*.bin)")
        if ok:
            self.file.setText(file)

    def send_config(self):
        dlg = SendConfigDialog()
        if dlg.exec_() == QDialog.Accepted:
            if dlg.commands:
                try:
                    self.serial = QSerialPort(self.cbxPort.currentData())
                    self.serial.setBaudRate(115200)
                    self.serial.open(QIODevice.ReadWrite)
                    self.serial.readyRead.connect(self.on_serial_read)
                    bytes_sent = self.serial.write(bytes(dlg.commands, 'utf8'))
                except Exception as e:
                    QMessageBox.critical(self, "COM Port error", e)
                else:
                    QMessageBox.information(self, "Done", "Use admin/ClassicMQTT to enter configuration page")
                    self.serial.close()
            else:
                QMessageBox.information(self, "Done", "Nothing to send")

    def on_serial_read(self):
        self.process_bytes(bytes(self.serial.readAll()))

    def process_bytes(self, bs):
        text = bs.decode('ascii')
        print("!Received: " + text)
        try:
            for b in text:
                if b == '{':  # start json
                    self.jsonStart = True
                    print("start JSON")
                if self.jsonStart == True:
                    self.jsonBuffer += b
                if b == '}':  # end json
                    self.jsonStart = False
                    print("found JSON")
                    print(self.jsonBuffer)
                    obj = json.loads(self.jsonBuffer)
                    url = "http://" + obj["IP"]
                    print("url:" + url)
                    webbrowser.get().open(url)
        except Exception as e:
            print("JSON error", e)

    def start_process(self):
        ok = True

        if self.mode == 0:
            if len(self.file.text()) > 0:
                self.bin_file = self.file.text()
            else:
                ok = False
                QMessageBox.information(self, "Nothing to do...", "Select a local BIN file or select which one to download.")

        if ok:
            dlg = FlashingDialog(self)
            if dlg.exec_() == QDialog.Accepted:
                QMessageBox.information(self, "Done", "Flashing successful! Press the reset button.")
            else:
                if dlg.error_msg:
                    QMessageBox.critical(self, "Error", dlg.error_msg)
                else:
                    QMessageBox.critical(self, "Flashing aborted", "Flashing process has been aborted by the user.")

    def mousePressEvent(self, e):
        self.old_pos = e.globalPos()

    def mouseMoveEvent(self, e):
        delta = e.globalPos() - self.old_pos
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.old_pos = e.globalPos()

def main():
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DisableWindowContextHelpButton)
    app.setQuitOnLastWindowClosed(True)
    app.setStyle("Fusion")
    app.setPalette(dark_palette)
    app.setStyleSheet("QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }")
    app.setStyle("Fusion")
    mw = Flasher()
    mw.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
