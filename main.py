import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from urllib.request import urlretrieve

import chardet
import rarfile
import requests
from lxml import etree
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import Boolean, Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class FlingTrainerAppModel(Base):
    __tablename__ = "flingtrainer_app"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name_zh = Column(String)
    name_en = Column(String, unique=True)
    page_url = Column(String)
    download = Column(Boolean, default=False)
    is_hot = Column(Boolean, default=False)
    is_new = Column(Boolean, default=False)
    save_path = Column(String)
    readme = Column(String)
    app_md5 = Column(String)
    update_date = Column(String)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setGeometry(200, 200, 400, 200)
        self.initUI()

    def initUI(self):
        layout = QFormLayout()
        self.downloadPathEdit = QLineEdit(self)
        self.downloadPathEdit.setReadOnly(True)
        layout.addRow("下载路径:", self.downloadPathEdit)

        browseButton = QPushButton("浏览...")
        browseButton.clicked.connect(self.selectDownloadPath)
        layout.addWidget(browseButton)
        buttonBox = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, self
        )
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)
        self.setLayout(layout)

    def selectDownloadPath(self):
        path = QFileDialog.getExistingDirectory(self, "选择下载路径")
        if path:
            self.downloadPathEdit.setText(path)

    def getDownloadPath(self):
        return self.downloadPathEdit.text()


class Worker(QThread):
    finished = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, func, *args):
        super().__init__()
        self.func = func
        self.args = args

    def run(self):
        self.func(*self.args)
        self.finished.emit()


class FlingTrainerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon("./icon.jpg"))
        self.home_dir = ""
        self.config_path = ""
        self.db_path = ""
        self.initHome()
        self.initDB()
        self.checkAndInitializeDB()
        self.loadSettings()
        self.initUI()
        self.show()  # 先显示主窗口
        self.searchData()
        self.logMessage("初始化中...")
        self.updateDB()

    def initApp(self):
        self.worker = Worker(self.asyncInitApp)
        self.worker.finished.connect(self.onInitAppFinished)
        self.worker.start()

    def onInitAppFinished(self):
        self.logMessage("初始化完成")

    def asyncInitApp(self):
        # self.updateDB()
        # self.searchData()
        ...

    def initHome(self):
        user_home = os.path.expanduser("~")
        app_home = os.path.join(user_home, ".flingcat")
        if not os.path.exists(app_home):
            os.makedirs(app_home)
        print(app_home)
        self.home_dir = app_home
        self.config_path = os.path.join(app_home, "config.json")
        self.db_path = f"sqlite:///{os.path.join(app_home,'flingtrainer_app.db')}"

    def initUI(self):
        self.setWindowTitle("Fling Trainer App")
        self.setFixedSize(580, 700)
        layout = QVBoxLayout()

        # Top search bar and controls
        topLayout = QHBoxLayout()
        self.searchBar = QLineEdit(self)
        self.searchBar.setPlaceholderText("搜索...")
        self.searchBar.textChanged.connect(self.searchData)
        topLayout.addWidget(self.searchBar)

        self.downloadedCheckBox = QCheckBox("已下载", self)
        self.downloadedCheckBox.stateChanged.connect(self.searchData)
        topLayout.addWidget(self.downloadedCheckBox)

        refreshButton = QPushButton("刷新", self)
        refreshButton.clicked.connect(self.updateDB)
        topLayout.addWidget(refreshButton)
        settingsButton = QPushButton("设置", self)
        settingsButton.clicked.connect(self.openSettings)
        topLayout.addWidget(settingsButton)

        layout.addLayout(topLayout)

        # Table to display data
        self.tableWidget = QTableWidget(self)
        self.setTableWidget()
        layout.addWidget(self.tableWidget)
        # Log text box
        self.logTextBox = QTextEdit(self)
        self.logTextBox.setReadOnly(True)
        self.logTextBox.setFixedHeight(100)
        layout.addWidget(self.logTextBox)

        self.setLayout(layout)

    def setTableWidget(self):
        self.tableWidget.setColumnCount(3)
        self.tableWidget.setHorizontalHeaderLabels(["名称", "操作", "操作"])
        self.tableWidget.horizontalHeader().setVisible(False)
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tableWidget.setColumnWidth(0, 400)
        self.tableWidget.setColumnWidth(1, 60)
        self.tableWidget.setColumnWidth(2, 60)
        self.tableWidget.setShowGrid(False)  # 隐藏所有网格线
        self.tableWidget.setStyleSheet(
            "QTableView::item { border-bottom: 1px solid #dcdcdc; }"
        )

    def logMessage(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.logTextBox.insertPlainText(log_entry)
        self.logTextBox.moveCursor(QTextCursor.End)
        self.logTextBox.ensureCursorVisible()

    def initDB(self):
        self.engine = create_engine(self.db_path)
        self.Session = sessionmaker(bind=self.engine)

    def checkAndInitializeDB(self):
        Base.metadata.create_all(self.engine)

    def getlist(self):
        url = "https://flingtrainer.com/all-trainers-a-z/"
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "zh-CN,zh;q=0.9",
            "priority": "u=0, i",
            "referer": "https://flingtrainer.com/all-trainers-a-z/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        }
        t1 = time.time()
        response = requests.request("GET", url, headers=headers)
        t2 = time.time()
        self.logMessage(
            f"请求列表{'成功' if response.status_code== 200 else '失败'}耗时{int(t2-t1)}秒"
        )
        html = response.text
        root = etree.HTML(html)
        game_list = root.xpath("..//div[starts-with(@id,'a-z-listing-letter')]/ul/li/a")

        game_app = {
            re.sub(r"\n|\t", "", i.xpath("./text()")[0].rstrip(" Trainer")): {
                "page_url": i.xpath("./@href")[0]
            }
            for i in game_list
        }
        try:
            hot_list = root.xpath(".//ul[@class='wpp-list']/li/a[2]")
            hot_app = {
                re.sub(r"\n|\t", "", i.xpath("./text()")[0].rstrip(" Trainer")): {
                    "page_url": i.xpath("./@href")[0],
                    "hot": True,
                }
                for i in hot_list
            }
            game_app.update(hot_app)
        except Exception as err:
            print(err)
            self.logMessage(f"获取热门游戏出错")

        try:
            new_list = root.xpath(".//h3[@class='rpwe-title']/a[1]")
            new_app = {
                re.sub(r"\n|\t", "", i.xpath("./text()")[0].rstrip(" Trainer")): {
                    "page_url": i.xpath("./@href")[0],
                    "new": True,
                }
                for i in new_list
            }
            game_app.update(new_app)
        except Exception as err:
            print(err)
            self.logMessage(f"获取热门游戏出错")
        return game_app

    def updateDB(self):
        self.logMessage("数据库更新中...")
        self.worker = Worker(self.asyncUpdateDB)
        self.worker.finished.connect(self.onUpdateDBFinished)
        self.worker.start()

    def onUpdateDBFinished(self):
        self.logMessage("数据库更新完成")
        self.searchData()

    def asyncUpdateDB(self):
        app_list = self.getlist()
        session = self.Session()
        for name_en, app_data in app_list.items():
            page_url = app_data.get("page_url")
            is_hot = app_data.get("hot", False)
            is_new = app_data.get("new", False)
            app = session.query(FlingTrainerAppModel).filter_by(name_en=name_en).first()
            if app:
                app.page_url = page_url
                app.is_hot = is_hot
            else:
                app = FlingTrainerAppModel(
                    name_en=name_en, page_url=page_url, is_hot=is_hot, is_new=is_new
                )
                session.add(app)
        session.commit()
        session.close()

    def loadSettings(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                self.settings = json.load(f)
        else:
            self.settings = {"download_path": ""}
        self.downloadPath = self.settings.get("download_path", "")

    def saveSettings(self):
        with open(self.config_path, "w") as f:
            json.dump(self.settings, f)

    def searchData(self):
        searchText = self.searchBar.text()
        downloaded = self.downloadedCheckBox.isChecked()

        session = self.Session()
        query = (
            session.query(FlingTrainerAppModel)
            .filter(
                (FlingTrainerAppModel.name_zh.like(f"%{searchText}%"))
                | (FlingTrainerAppModel.name_en.like(f"%{searchText}%"))
            )
            .order_by(
                FlingTrainerAppModel.download.desc(),
                FlingTrainerAppModel.is_hot.desc(),
                FlingTrainerAppModel.is_new.desc(),
                FlingTrainerAppModel.name_zh,
                FlingTrainerAppModel.name_en,
            )
        )
        if downloaded:
            query = query.filter(FlingTrainerAppModel.download == True)
        results = query.all()
        session.close()
        self.updateTable(results)

    def updateTable(self, data):
        self.setTableWidget()
        self.tableWidget.setRowCount(len(data))
        for rowIndex, rowData in enumerate(data):
            name = f"{'[热]' if rowData.is_hot else ''}{'[新]' if rowData.is_new else ''}{rowData.name_zh if rowData.name_zh else rowData.name_en}"
            nameItem = QTableWidgetItem(name)
            nameItem.setFlags(Qt.ItemIsEnabled)
            nameItem.setData(Qt.UserRole, rowData.page_url)
            self.tableWidget.setItem(rowIndex, 0, nameItem)
            if rowData.download:
                openButton = QPushButton("打开")
                updateButton = QPushButton("更新")
                openButton.clicked.connect(lambda _, id=rowData.id: self.openFile(id))
                updateButton.clicked.connect(
                    lambda _, id=rowData.id: self.updateFile(id)
                )
                self.tableWidget.setCellWidget(rowIndex, 1, updateButton)
                self.tableWidget.setCellWidget(rowIndex, 2, openButton)
            else:
                downloadButton = QPushButton("下载")
                downloadButton.clicked.connect(
                    lambda _, id=rowData.id: self.downloadFile(id)
                )
                self.tableWidget.setCellWidget(rowIndex, 1, None)
                self.tableWidget.setCellWidget(rowIndex, 2, downloadButton)
            self.tableWidget.item(rowIndex, 0).setBackground(
                Qt.green if rowData.download else Qt.white
            )

    def openFile(self, id):
        session = self.Session()
        app = session.query(FlingTrainerAppModel).filter_by(id=id).first()
        self.logMessage(f"打开文件{app.save_path}")
        if not os.path.exists(app.save_path):
            app.download = False
            session.commit()
            session.close()
            self.logMessage("文件已丢失请重新下载!")
            self.searchData()
            return
        isdir = os.path.isdir(app.save_path)
        # 打开文件逻辑
        if platform.system() == "Windows":
            if isdir:
                subprocess.run(["explorer.exe", folder_path], shell=True)
            else:
                subprocess.Popen([app.save_path])
        elif platform.system() == "Darwin":
            folder_path = app.save_path if isdir else os.path.dirname(app.save_path)
            subprocess.run(["open", folder_path])
        else:
            print("Unsupported platform")
        self.logMessage("文件已打开")
        session.close()

    def openFileDir(self, id):
        self.logMessage("打开文件夹...")
        session = self.Session()
        app = session.query(FlingTrainerAppModel).filter_by(id=id).first()
        folder_path = os.path.dirname(app.save_path)
        # 打开文件逻辑
        if platform.system() == "Windows":
            subprocess.run(["explorer.exe", folder_path], shell=True)
        elif platform.system() == "Darwin":
            subprocess.run(["open", folder_path])
        else:
            print("Unsupported platform")
        self.logMessage("文件已打开")

    def getAppById(self, id):
        session = self.Session()
        app = session.query(FlingTrainerAppModel).filter_by(id=id).first()
        session.close()
        return app

    def parse_app_info(self, page_url):
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        }
        response = requests.request("GET", page_url, headers=headers)
        html = response.text
        root = etree.HTML(html)
        attachment = root.xpath("..//tr[@class='rar' or @class='zip']")[0]
        file_tpye = attachment.xpath("./@class")[0].split(" ")[0]
        print(file_tpye)

        attachment_title = attachment.xpath("./td[@class='attachment-title']/a")[0]
        title = attachment_title.xpath("./text()")[0]
        url = attachment_title.xpath("./@href")[0]
        date = attachment.xpath("./td[@class='attachment-date']/text()")[0]
        md5 = hashlib.md5(title.encode(encoding="UTF-8")).hexdigest()
        app_info = {
            "title": title,
            "md5": md5,
            "url": url,
            "date": date,
            "file_type": file_tpye,
        }
        print(f"app_info:{app_info}")
        return app_info

    def save_file(self, app_info, save_dir):
        title = app_info.get("title")
        url = app_info.get("url")
        md5 = app_info.get("md5")
        file_type = app_info.get("file_type")
        temp_path = os.path.join(save_dir, "temp", md5, f"{int(time.time())}/")
        if not os.path.exists(temp_path):
            os.makedirs(temp_path)
        temp_file_path = os.path.join(temp_path, f"{title}.{file_type}")
        local_file, header = urlretrieve(url, filename=temp_file_path)
        save_path = os.path.join(save_dir, md5)
        if file_type == "zip":
            shutil.unpack_archive(temp_file_path, save_path)
        elif file_type == "rar":
            with rarfile.RarFile(temp_file_path) as rf:
                rf.extractall(save_path)
        # os.remove(temp_path)
        print(os.stat(temp_path))
        files = os.listdir(save_path)
        trainer = save_path
        readme = ""
        for f in files:
            if f.endswith("Trainer.exe"):
                trainer = os.path.join(save_path, f)
            elif f.lower() == "readme.txt":
                readme = os.path.join(save_path, f)
            else:
                continue
        return trainer, readme

    def updateFile(self, id):
        self.worker = Worker(self.asyncUpdateFile, id)
        self.worker.finished.connect(self.onUpdateFileFinished)
        self.worker.start()

    def onUpdateFileFinished(self):
        self.searchData()

    def asyncUpdateFile(self, id):
        try:
            session = self.Session()
            app = session.query(FlingTrainerAppModel).filter_by(id=id).first()
            if app:
                # 更新文件逻辑
                self.logMessage(
                    f"{app.name_zh if app.name_zh != '' else app.name_en}下载中..."
                )
                app_info = self.parse_app_info(app.page_url)
                if app.app_md5 == app_info.get("md5"):
                    self.logMessage(
                        f"{app.name_zh if app.name_zh != '' else app.name_en}已经是最新版本"
                    )
                    return
                trainer, readme = self.save_file(app_info, self.downloadPath)
                if app.save_path != trainer:
                    # os.remove(app.save_path)
                    print(os.stat(app.save_path))
                app.save_path = trainer
                app.update_date = app_info.get("date", "")
                app.app_md5 = app_info.get("md5", "")
                if readme != "":
                    with open(readme, "rb") as f:
                        raw_data = f.read()
                        encoding = chardet.detect(raw_data)["encoding"]
                    with open(readme, "r", encoding=encoding, errors="ignore") as fp:
                        app.readme = fp.read()
                else:
                    app.readme = ""
                app.download = True
                session.commit()
                self.logMessage("更新完成")
            session.close()
        except Exception as err:
            print(err)
            self.logMessage("更新出错...")

    def downloadFile(self, id):
        if not self.downloadPath:
            self.openSettings()
            return

        self.worker = Worker(self.asyncDownloadFile, id)
        self.worker.finished.connect(self.onDownloadFileFinished)
        self.worker.start()

    def onDownloadFileFinished(self):
        self.searchData()

    def asyncDownloadFile(self, id):
        try:
            session = self.Session()
            app = session.query(FlingTrainerAppModel).filter_by(id=id).first()
            if app:
                self.logMessage(
                    f"{app.name_zh if app.name_zh  else app.name_en}下载中..."
                )
                app_info = self.parse_app_info(app.page_url)
                trainer, readme = self.save_file(app_info, self.downloadPath)
                app.save_path = trainer
                app.update_date = app_info.get("date", "")
                app.app_md5 = app_info.get("md5", "")
                if readme:
                    with open(readme, "rb") as f:
                        raw_data = f.read()
                        encoding = chardet.detect(raw_data)["encoding"]
                    with open(readme, "r", encoding=encoding, errors="ignore") as fp:
                        app.readme = fp.read()
                app.download = True
                session.commit()
            session.close()
            self.logMessage(f"{app.name_zh if app.name_zh  else app.name_en}下载完成")
        except Exception as err:
            print(err)
            self.logMessage("下载出错")

    def openSettings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            newDownloadPath = dialog.getDownloadPath()
            if newDownloadPath and newDownloadPath != self.downloadPath:
                if os.path.exists(self.downloadPath):
                    for filename in os.listdir(self.downloadPath):
                        shutil.move(
                            os.path.join(self.downloadPath, filename), newDownloadPath
                        )
                    self.logMessage("文件已移动")
                self.downloadPath = newDownloadPath
                self.settings["download_path"] = self.downloadPath
                self.saveSettings()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = FlingTrainerApp()
    ex.show()
    sys.exit(app.exec_())
