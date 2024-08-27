import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import time
from typing import NoReturn
from urllib.request import urlretrieve

import chardet
import requests
from lxml import etree
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QTextCursor
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from consts import GAME_NAME_MAP
from db import Base, FlingTrainerAppModel
from utils import FlingCatTools


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setGeometry(200, 200, 500, 200)  # 设置窗口宽度为500，高度为400
        self.initUI()

    def initUI(self):
        layout = QGridLayout()  # 使用网格布局

        # 第一行
        layout.addWidget(QLabel("下载路径:"), 0, 0)  # 第一列
        self.downloadPathEdit = QLineEdit(self)
        self.downloadPathEdit.setReadOnly(True)
        self.downloadPathEdit.setText(
            self.parent().downloadPath
        )  # 默认显示当前设置的保存路径
        layout.addWidget(self.downloadPathEdit, 0, 1)  # 第二列
        browseButton = QPushButton("浏览...")
        browseButton.clicked.connect(self.selectDownloadPath)
        layout.addWidget(browseButton, 0, 2)  # 第三列

        # 添加调试开关
        self.debugSwitch = QCheckBox("调试模式", self)  # 新增调试开关
        self.debugSwitch.setChecked(self.parent().debugMode)  # 默认为关闭
        layout.addWidget(self.debugSwitch, 1, 0, 1, 3)  # 跨越三列

        layout.addWidget(QLabel("作者:"), 3, 0)  # 第一列
        authorLabel = QLabel(
            "<a href='https://space.bilibili.com/66507754'>catman</a>"
        )  # 不可编辑的文本
        authorLabel.setOpenExternalLinks(True)
        layout.addWidget(authorLabel, 3, 1)  # 第二列
        layout.addWidget(QLabel(""), 3, 2)  # 第三列空白

        layout.addWidget(QLabel("声明:"), 4, 0)  # 第一列
        authorLabel = QLabel("随缘更新,完全免费,禁止倒卖")  # 不可编辑的文本
        layout.addWidget(authorLabel, 4, 1)  # 第二列
        layout.addWidget(QLabel(""), 4, 2)  # 第三列空白

        # 保存和取消按钮
        buttonBox = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, self
        )
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox, 2, 0, 1, 3)  # 跨越三列

        self.setLayout(layout)

    def selectDownloadPath(self):
        path = QFileDialog.getExistingDirectory(self, "选择下载路径")
        if path:
            self.downloadPathEdit.setText(os.path.normpath(path))

    def getDownloadPath(self):
        return self.downloadPathEdit.text()

    def getDebugSwitch(self):
        return self.debugSwitch.isChecked()


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
        self.home_dir = ""
        self.config_path = ""
        self.db_path = ""
        self.downloadPath = ""
        self.debugMode = False
        self.initHome()
        self.loadSettings()
        self.initDB()
        self.checkAndInitializeDB()
        self.initUI()
        self.show()  # 先显示主窗口
        self.searchData()
        self.logMessage("初始化中...")
        self.updateDB()

    def initHome(self) -> NoReturn:
        """
        初始化软件工作目录
        """
        user_home = os.path.expanduser("~")
        app_home = os.path.join(user_home, "flingcat")
        if not os.path.exists(app_home):
            os.makedirs(app_home)
        print(app_home)
        self.home_dir = app_home
        self.db_path = f"sqlite:///{os.path.join(app_home,'flingtrainer_app.db')}"
        self.config_path = os.path.join(app_home, "config.json")
        if not os.path.exists(self.config_path):
            with open(self.config_path, "w", encoding="utf-8") as cfp:
                default_download_path = os.path.join(user_home, "flingtrainer_app")
                default_config = {"download_path": default_download_path}
                cfp.write(json.dumps(default_config, ensure_ascii=False))
                if platform.system() == "Windows":
                    FlingCatTools.addWinDefnderWhite(default_download_path)

    def loadSettings(self) -> NoReturn:
        """
        加载配置文件
        """
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                self.settings = json.load(f)
        else:
            self.settings = {"download_path": "", "debug_mode": False}
        self.downloadPath = self.settings.get("download_path", "")
        self.debugMode = self.settings.get("debug_mode", False)

    def saveSettings(self) -> NoReturn:
        """
        保存配置到文件
        """
        with open(self.config_path, "w") as f:
            json.dump(self.settings, f)

    def initUI(self):
        """
        初始化主界面
        """
        if getattr(sys, "frozen", False):
            applicationPath = sys._MEIPASS
        elif __file__:
            applicationPath = os.path.dirname(__file__)
        app.setWindowIcon(QIcon(os.path.join(applicationPath, "Icon.ico")))
        self.setWindowTitle("FlingCat-风灵月影下载器-Dev by CatMan")
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

        if self.debugMode:
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
        """
        设置列表区域
        """
        self.tableWidget.setColumnCount(4)
        self.tableWidget.setHorizontalHeaderLabels(["名称", "提示", "管理", "操作"])
        self.tableWidget.horizontalHeader().setVisible(False)
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tableWidget.setColumnWidth(0, 358)
        self.tableWidget.setColumnWidth(1, 60)
        self.tableWidget.setColumnWidth(2, 60)
        self.tableWidget.setColumnWidth(3, 60)
        self.tableWidget.setShowGrid(False)  # 隐藏所有网格线
        self.tableWidget.setStyleSheet(
            "QTableView::item { border-bottom: 1px solid #dcdcdc; }"
        )

    def logMessage(self, message):
        """
        输出日志

        Args:
            message ():
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.logTextBox.insertPlainText(log_entry)
        self.logTextBox.moveCursor(QTextCursor.End)
        self.logTextBox.ensureCursorVisible()

    def initDB(self):
        """
        初始化数据库
        """
        self.engine = create_engine(self.db_path)
        self.Session = sessionmaker(bind=self.engine)

    def checkAndInitializeDB(self):
        Base.metadata.create_all(self.engine)

    def createManageMenu(self, id):
        menu = QMenu()

        viewAction = QAction("查看", self)
        viewAction.triggered.connect(lambda: self.openFileDir(id))
        menu.addAction(viewAction)

        updateAction = QAction("更新", self)
        updateAction.triggered.connect(lambda: self.updateFile(id))
        menu.addAction(updateAction)

        uninstallAction = QAction("卸载", self)
        uninstallAction.triggered.connect(lambda: self.confirmUninstall(id))
        menu.addAction(uninstallAction)

        return menu

    def print(self, content):
        if self.debugMode:
            self.logMessage(content)
        print(content)

    def confirmUninstall(self, id):
        session = self.Session()
        app = session.query(FlingTrainerAppModel).filter_by(id=id).first()

        reply = QMessageBox.question(
            self,
            "确认卸载",
            f"您确定要卸载{app.name_zh if app.name_zh else app.name_en}吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.uninstallFile(id)
        session.close()

    def uninstallFile(self, id):
        session = self.Session()
        app = session.query(FlingTrainerAppModel).filter_by(id=id).first()
        if app:
            if os.path.exists(app.save_path):
                # 删除文件夹
                shutil.rmtree(os.path.dirname(app.save_path), ignore_errors=True)
            app.download = False
            app.save_path = ""
            app.app_md5 = ""
            session.commit()
            self.logMessage(f"{app.name_zh if app.name_zh else app.name_en}已卸载")
        session.close()
        self.searchData()

    def viewWarn(self, id):
        session = self.Session()
        app = session.query(FlingTrainerAppModel).filter_by(id=id).first()

        reply = QMessageBox.question(
            self,
            "提示",
            f"该应用包含以下注意事项，是否打开目录查看！！！\n{app.readme}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.openFileDir(id)
        session.close()

    def parseName(self, name):
        name_zh = re.sub(r"\\n\\t", "", name).strip().rstrip("Trainer").strip()
        # print(f"[{name}]-->[{name_zh}]")
        return name_zh

    def getlist(self):
        url = "https://flingtrainer.com/all-trainers-a-z/"
        payload = {}
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "zh-CN,zh;q=0.9",
            "priority": "u=0, i",
            "referer": "https://flingtrainer.com/all-trainers-a-z/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        }
        t1 = time.time()
        response = requests.request("GET", url, headers=headers, data=payload)
        t2 = time.time()
        self.logMessage(
            f"请求列表{'成功' if response.status_code== 200 else '失败'}耗时{int(t2-t1)}秒"
        )
        html = response.text
        root = etree.HTML(html)
        game_list = root.xpath("..//div[starts-with(@id,'a-z-listing-letter')]/ul/li/a")

        game_app = {
            self.parseName(i.xpath("./text()")[0]): {"page_url": i.xpath("./@href")[0]}
            for i in game_list
        }
        try:
            hot_list = root.xpath(".//ul[@class='wpp-list']/li/a[2]")
            hot_app = {
                self.parseName(i.xpath("./text()")[0]): {
                    "page_url": i.xpath("./@href")[0],
                    "hot": True,
                }
                for i in hot_list
            }
            for k, v in hot_app.items():
                ov = game_app.get(k)
                if ov:
                    ov.update(v)
                    game_app[k] = ov
                else:
                    game_app[k] = v
        except Exception as err:
            print(err)
            self.logMessage(f"获取热门游戏出错")

        try:
            new_list = root.xpath(".//h3[@class='rpwe-title']/a[1]")
            new_app = {
                self.parseName(i.xpath("./text()")[0]): {
                    "page_url": i.xpath("./@href")[0],
                    "new": True,
                }
                for i in new_list
            }
            for k, v in new_app.items():
                ov = game_app.get(k)
                if ov:
                    ov.update(v)
                    game_app[k] = ov
                else:
                    game_app[k] = v
        except Exception as err:
            print(err)
            self.logMessage(f"获取新增游戏出错")
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
                app.is_new = is_new
            else:
                # name_en = name_en.strip().strip("Trainer").strip()
                name_zh = GAME_NAME_MAP.get(name_en, name_en)
                app = FlingTrainerAppModel(
                    name_en=name_en,
                    name_zh=name_zh,
                    page_url=page_url,
                    is_hot=is_hot,
                    is_new=is_new,
                )
                session.add(app)
            session.commit()
        session.close()

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
            name = f"{'🔥' if rowData.is_hot else ''}{'🆕' if rowData.is_new else ''}{rowData.name_zh+'('+rowData.name_en+')' if rowData.name_zh else rowData.name_en}"
            nameItem = QTableWidgetItem(name)
            nameItem.setFlags(Qt.ItemIsEnabled)
            nameItem.setData(Qt.UserRole, rowData.page_url)
            self.tableWidget.setItem(rowIndex, 0, nameItem)

            # 清除旧的按钮
            self.tableWidget.setCellWidget(rowIndex, 1, None)  # 清除按钮
            self.tableWidget.setCellWidget(rowIndex, 2, None)  # 清除管理按钮
            self.tableWidget.setCellWidget(rowIndex, 3, None)  # 清除打开/下载按钮
            if rowData.download:
                # 创建管理按钮
                if rowData.readme:
                    warnButton = QPushButton("点我!")
                    warnButton.clicked.connect(
                        lambda _, id=rowData.id: self.viewWarn(id)
                    )  # 设置菜单
                    self.tableWidget.setCellWidget(rowIndex, 1, warnButton)
                manageButton = QPushButton("管理")
                manageButton.setMenu(self.createManageMenu(rowData.id))  # 设置菜单
                self.tableWidget.setCellWidget(rowIndex, 2, manageButton)
                openButton = QPushButton("打开")
                openButton.clicked.connect(lambda _, id=rowData.id: self.openFile(id))
                self.tableWidget.setCellWidget(rowIndex, 3, openButton)
            else:
                downloadButton = QPushButton("下载")
                downloadButton.clicked.connect(
                    lambda _, id=rowData.id: self.downloadFile(id)
                )
                self.tableWidget.setCellWidget(rowIndex, 3, downloadButton)

    def openFile(self, id):
        try:
            session = self.Session()
            app = session.query(FlingTrainerAppModel).filter_by(id=id).first()
            self.logMessage(
                f"打开{app.name_zh if app.name_zh else app.name_en}风灵月影工具"
            )
            if not os.path.exists(app.save_path):
                app.download = False
                session.commit()
                session.close()
                self.logMessage(
                    f"{app.name_zh if app.name_zh else app.name_en}风灵月影已丢失请重新下载!"
                )
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
            self.logMessage(
                f"{app.name_zh if app.name_zh else app.name_en}风灵月影已打开"
            )
            session.close()
        except Exception as err:
            self.print(err)
            self.logMessage(err)

    def openFileDir(self, id):
        try:
            self.logMessage("打开文件夹...")
            session = self.Session()
            app = session.query(FlingTrainerAppModel).filter_by(id=id).first()
            if app.download and app.save_path:
                folder_path = os.path.dirname(app.save_path)
                print(app.save_path, folder_path)
                # 打开文件逻辑
                if platform.system() == "Windows":
                    subprocess.run(["explorer.exe", folder_path], shell=True)
                elif platform.system() == "Darwin":
                    subprocess.run(["open", folder_path])
                else:
                    print("Unsupported platform")
                self.logMessage(f"文件夹{folder_path}已打开")
            else:
                self.logMessage("应用未下载")
        except Exception as err:
            self.print(err)
            self.logMessage(err)

    def getAppById(self, id):
        session = self.Session()
        app = session.query(FlingTrainerAppModel).filter_by(id=id).first()
        session.close()
        return app

    def parse_app_info(self, page_url):
        payload = {}
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        }
        response = requests.request("GET", page_url, headers=headers, data=payload)
        html = response.text
        root = etree.HTML(html)
        attachment = root.xpath("..//tr[@class='rar' or @class='zip']")[0]
        file_tpye = attachment.xpath("./@class")[0].split(" ")[0]
        self.print(file_tpye)

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
            os.chmod(temp_path, 0o777)
        temp_file_path = os.path.join(temp_path, f"{title}.{file_type}")
        local_file, header = urlretrieve(url, filename=temp_file_path)
        save_path = os.path.join(save_dir, md5)
        if file_type == "zip":
            shutil.unpack_archive(temp_file_path, save_path)
        elif file_type == "rar":
            if not os.path.exists(save_path):
                os.makedirs(save_path)
                os.chmod(save_path, 0o777)
            if hasattr(sys, "_MEIPASS"):
                current_dir = sys._MEIPASS
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
            # 构建 unrar 可执行文件的路径
            unrar_path = os.path.join(current_dir, "bin", "UnRAR.exe")
            print(unrar_path)
            # 构建解压命令
            command = [unrar_path, "x", "-y", temp_file_path, save_path]
            try:
                # 调用 unrar 命令
                subprocess.run(command, check=True)
            except subprocess.CalledProcessError as e:
                print(f"解压失败: {e}")
        os.chmod(temp_path, stat.S_IWRITE)
        shutil.rmtree(temp_path, ignore_errors=True)
        # print(os.stat(temp_path))
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
                    f"{app.name_zh if app.name_zh != '' else app.name_en}更新中..."
                )
                app_info = self.parse_app_info(app.page_url)
                if app.app_md5 == app_info.get("md5"):
                    self.logMessage(
                        f"{app.name_zh if app.name_zh != '' else app.name_en}已经是最新版本"
                    )
                    return
                trainer, readme = self.save_file(app_info, self.downloadPath)
                if app.save_path != trainer:
                    os.chmod(app.save_path, stat.S_IWRITE)
                    shutil.rmtree(app.save_path, ignore_errors=True)
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
            self.print(err)
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
            self.logMessage(f"{app.name_zh if app.name_zh  else app.name_en}下载完成")
            session.close()
        except Exception as err:
            self.print(err)
            self.logMessage("下载出错")

    def openSettings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            newDownloadPath = dialog.getDownloadPath()
            debugSwitch = dialog.getDebugSwitch()
            self.debugMode = debugSwitch
            self.settings["debug_mode"] = debugSwitch
            FlingCatTools.addWinDefnderWhite(newDownloadPath)
            if newDownloadPath and newDownloadPath != self.downloadPath:

                session = self.Session()
                apps = (
                    session.query(FlingTrainerAppModel)
                    .filter(FlingTrainerAppModel.download == True)
                    .all()
                )
                for app in apps:
                    if os.path.exists(app.save_path):
                        res = shutil.move(
                            os.path.dirname(app.save_path),
                            newDownloadPath,
                        )
                        print("res", res)
                        app.save_path = os.path.join(
                            res, os.path.basename(app.save_path)
                        )
                        print("save_path", app.save_path)
                        session.commit()
                    else:
                        app.download = False
                        app.app_md5 = ""
                        app.readme = ""
                        app.save_path = ""
                    session.commit()
                session.close()
                self.logMessage("文件已移动")
                self.downloadPath = newDownloadPath
                self.settings["download_path"] = self.downloadPath
            self.saveSettings()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = FlingTrainerApp()
    ex.show()
    sys.exit(app.exec_())
