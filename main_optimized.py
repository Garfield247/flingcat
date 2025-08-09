import json
import os
import platform
import sys
import time
from typing import List

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QTextCursor
from PyQt5.QtWidgets import (QAction, QApplication, QCheckBox, QDialog,
                             QDialogButtonBox, QFileDialog, QGridLayout,
                             QHBoxLayout, QLabel, QLineEdit, QMenu,
                             QMessageBox, QPushButton, QTableWidget,
                             QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)

from consts import GAME_NAME_MAP
from db import FlingTrainerAppModel
from utils import FlingCatTools
from config_manager import ConfigManager
from database_manager import DatabaseManager
from network_manager import NetworkManager
from file_manager import FileManager


class SettingsDialog(QDialog):
    """设置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setGeometry(200, 200, 500, 200)
        self.initUI()
    
    def initUI(self):
        layout = QGridLayout()
        
        # 下载路径设置
        layout.addWidget(QLabel("下载路径:"), 0, 0)
        self.downloadPathEdit = QLineEdit(self)
        self.downloadPathEdit.setReadOnly(True)
        self.downloadPathEdit.setText(self.parent().downloadPath)
        layout.addWidget(self.downloadPathEdit, 0, 1)
        
        browseButton = QPushButton("浏览...")
        browseButton.clicked.connect(self.selectDownloadPath)
        layout.addWidget(browseButton, 0, 2)
        
        # 调试模式开关
        self.debugSwitch = QCheckBox("调试模式", self)
        self.debugSwitch.setChecked(self.parent().debugMode)
        layout.addWidget(self.debugSwitch, 1, 0, 1, 3)
        
        # 作者信息
        layout.addWidget(QLabel("作者:"), 3, 0)
        authorLabel = QLabel("<a href='https://space.bilibili.com/66507754'>catman</a>")
        authorLabel.setOpenExternalLinks(True)
        layout.addWidget(authorLabel, 3, 1)
        layout.addWidget(QLabel(""), 3, 2)
        
        # 声明信息
        layout.addWidget(QLabel("声明:"), 4, 0)
        disclaimerLabel = QLabel("随缘更新,完全免费,禁止倒卖")
        layout.addWidget(disclaimerLabel, 4, 1)
        layout.addWidget(QLabel(""), 4, 2)
        
        # 按钮
        buttonBox = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, self
        )
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox, 2, 0, 1, 3)
        
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
    """工作线程基类"""
    finished = pyqtSignal()
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            self.func(*self.args, **self.kwargs)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class FlingTrainerApp(QWidget):
    """主应用程序类"""
    
    def __init__(self):
        super().__init__()
        self._init_components()
        self._setup_ui()
        self.show()
        self.searchData()
        self.logMessage("初始化中...")
        self.updateDB()
    
    def _init_components(self):
        """初始化组件"""
        self._init_home()
        self.config_manager = ConfigManager(self.config_path)
        self.downloadPath = self.config_manager.get("download_path", "")
        self.debugMode = self.config_manager.get("debug_mode", False)
        
        self.db_manager = DatabaseManager(self.db_path)
        self.network_manager = NetworkManager(self.debugMode)
        self.file_manager = FileManager(self.downloadPath, self.debugMode)
    
    def _init_home(self):
        """初始化工作目录"""
        user_home = os.path.expanduser("~")
        app_home = os.path.join(user_home, "flingcat")
        if not os.path.exists(app_home):
            os.makedirs(app_home)
        
        self.home_dir = app_home
        self.db_path = f"sqlite:///{os.path.join(app_home, 'flingtrainer_app.db')}"
        self.config_path = os.path.join(app_home, "config.json")
        
        if not os.path.exists(self.config_path):
            default_download_path = os.path.join(user_home, "flingtrainer_app")
            default_config = {"download_path": default_download_path}
            with open(self.config_path, "w", encoding="utf-8") as cfp:
                json.dump(default_config, cfp, ensure_ascii=False)
            
            if platform.system() == "Windows":
                FlingCatTools.addWinDefnderWhite(default_download_path)
    
    def _setup_ui(self):
        """设置用户界面"""
        if getattr(sys, "frozen", False):
            application_path = sys._MEIPASS
        elif __file__:
            application_path = os.path.dirname(__file__)
        
        app.setWindowIcon(QIcon(os.path.join(application_path, "Icon.ico")))
        self.setWindowTitle("FlingCat-风灵月影下载器-Dev by CatMan")
        self.setFixedSize(580, 700)
        
        layout = QVBoxLayout()
        
        # 顶部搜索栏和控件
        top_layout = QHBoxLayout()
        self.searchBar = QLineEdit(self)
        self.searchBar.setPlaceholderText("搜索...")
        self.searchBar.textChanged.connect(self.searchData)
        top_layout.addWidget(self.searchBar)
        
        self.downloadedCheckBox = QCheckBox("已下载", self)
        self.downloadedCheckBox.stateChanged.connect(self.searchData)
        top_layout.addWidget(self.downloadedCheckBox)
        
        if self.debugMode:
            refreshButton = QPushButton("刷新", self)
            refreshButton.clicked.connect(self.updateDB)
            top_layout.addWidget(refreshButton)
        
        settingsButton = QPushButton("设置", self)
        settingsButton.clicked.connect(self.openSettings)
        top_layout.addWidget(settingsButton)
        
        layout.addLayout(top_layout)
        
        # 表格
        self.tableWidget = QTableWidget(self)
        self._setup_table()
        layout.addWidget(self.tableWidget)
        
        # 日志文本框
        self.logTextBox = QTextEdit(self)
        self.logTextBox.setReadOnly(True)
        self.logTextBox.setFixedHeight(100)
        layout.addWidget(self.logTextBox)
        
        self.setLayout(layout)
    
    def _setup_table(self):
        """设置表格"""
        self.tableWidget.setColumnCount(4)
        self.tableWidget.setHorizontalHeaderLabels(["名称", "提示", "管理", "操作"])
        self.tableWidget.horizontalHeader().setVisible(False)
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tableWidget.setColumnWidth(0, 358)
        self.tableWidget.setColumnWidth(1, 60)
        self.tableWidget.setColumnWidth(2, 60)
        self.tableWidget.setColumnWidth(3, 60)
        self.tableWidget.setShowGrid(False)
        self.tableWidget.setStyleSheet(
            "QTableView::item { border-bottom: 1px solid #dcdcdc; }"
        )
    
    def logMessage(self, message: str):
        """输出日志"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.logTextBox.insertPlainText(log_entry)
        self.logTextBox.moveCursor(QTextCursor.End)
        self.logTextBox.ensureCursorVisible()
    
    def print(self, content: str):
        """调试输出"""
        if self.debugMode:
            self.logMessage(content)
        print(content)
    
    def _create_manage_menu(self, app_id: int) -> QMenu:
        """创建管理菜单"""
        menu = QMenu()
        
        view_action = QAction("查看", self)
        view_action.triggered.connect(lambda: self.openFileDir(app_id))
        menu.addAction(view_action)
        
        update_action = QAction("更新", self)
        update_action.triggered.connect(lambda: self.updateFile(app_id))
        menu.addAction(update_action)
        
        uninstall_action = QAction("卸载", self)
        uninstall_action.triggered.connect(lambda: self.confirmUninstall(app_id))
        menu.addAction(uninstall_action)
        
        return menu
    
    def confirmUninstall(self, app_id: int):
        """确认卸载"""
        app = self.db_manager.get_app_by_id(app_id)
        if not app:
            return
        
        reply = QMessageBox.question(
            self,
            "确认卸载",
            f"您确定要卸载{app.name_zh if app.name_zh else app.name_en}吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        
        if reply == QMessageBox.Yes:
            self.uninstallFile(app_id)
    
    def uninstallFile(self, app_id: int):
        """卸载文件"""
        app = self.db_manager.get_app_by_id(app_id)
        if not app:
            return
        
        try:
            if os.path.exists(app.save_path):
                self.file_manager._cleanup_temp_files(os.path.dirname(app.save_path))
            
            app.download = False
            app.save_path = ""
            app.app_md5 = ""
            self.db_manager.update_app(app)
            
            self.logMessage(f"{app.name_zh if app.name_zh else app.name_en}已卸载")
        except Exception as e:
            self.print(f"卸载失败: {e}")
            self.logMessage("卸载失败")
        finally:
            self.searchData()
    
    def viewWarn(self, app_id: int):
        """查看警告信息"""
        app = self.db_manager.get_app_by_id(app_id)
        if not app:
            return
        
        reply = QMessageBox.question(
            self,
            "提示",
            f"该应用包含以下注意事项，是否打开目录查看！！！\n{app.readme}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        
        if reply == QMessageBox.Yes:
            self.openFileDir(app_id)
    
    def updateDB(self):
        """更新数据库"""
        self.logMessage("数据库更新中...")
        self.worker = Worker(self._async_update_db)
        self.worker.finished.connect(self._on_update_db_finished)
        self.worker.error.connect(lambda e: self.logMessage(f"更新失败: {e}"))
        self.worker.start()
    
    def _async_update_db(self):
        """异步更新数据库"""
        app_list = self.network_manager.get_game_list()
        
        for name_en, app_data in app_list.items():
            page_url = app_data.get("page_url")
            is_hot = app_data.get("hot", False)
            is_new = app_data.get("new", False)
            
            with self.db_manager.get_session() as session:
                app = session.query(FlingTrainerAppModel).filter_by(name_en=name_en).first()
                
                if app:
                    app.page_url = page_url
                    app.is_hot = is_hot
                    app.is_new = is_new
                else:
                    name_zh = GAME_NAME_MAP.get(name_en, name_en)
                    app = FlingTrainerAppModel(
                        name_en=name_en,
                        name_zh=name_zh,
                        page_url=page_url,
                        is_hot=is_hot,
                        is_new=is_new,
                    )
                    session.add(app)
    
    def _on_update_db_finished(self):
        """数据库更新完成回调"""
        self.logMessage("数据库更新完成")
        self.searchData()
    
    def searchData(self):
        """搜索数据"""
        search_text = self.searchBar.text()
        downloaded_only = self.downloadedCheckBox.isChecked()
        
        results = self.db_manager.search_apps(search_text, downloaded_only)
        self._update_table(results)
    
    def _update_table(self, data: List[FlingTrainerAppModel]):
        """更新表格"""
        self._setup_table()
        self.tableWidget.setRowCount(len(data))
        
        for row_index, row_data in enumerate(data):
            # 设置名称
            name = self._format_app_name(row_data)
            name_item = QTableWidgetItem(name)
            name_item.setFlags(Qt.ItemIsEnabled)
            name_item.setData(Qt.UserRole, row_data.page_url)
            self.tableWidget.setItem(row_index, 0, name_item)
            
            # 清除旧的按钮
            for col in [1, 2, 3]:
                self.tableWidget.setCellWidget(row_index, col, None)
            
            if row_data.download:
                # 已下载的应用
                if row_data.readme:
                    warn_button = QPushButton("点我!")
                    warn_button.clicked.connect(
                        lambda _, id=row_data.id: self.viewWarn(id)
                    )
                    self.tableWidget.setCellWidget(row_index, 1, warn_button)
                
                manage_button = QPushButton("管理")
                manage_button.setMenu(self._create_manage_menu(row_data.id))
                self.tableWidget.setCellWidget(row_index, 2, manage_button)
                
                open_button = QPushButton("打开")
                open_button.clicked.connect(lambda _, id=row_data.id: self.openFile(id))
                self.tableWidget.setCellWidget(row_index, 3, open_button)
            else:
                # 未下载的应用
                download_button = QPushButton("下载")
                download_button.clicked.connect(
                    lambda _, id=row_data.id: self.downloadFile(id)
                )
                self.tableWidget.setCellWidget(row_index, 3, download_button)
    
    def _format_app_name(self, app: FlingTrainerAppModel) -> str:
        """格式化应用名称"""
        hot_icon = "🔥" if app.is_hot else ""
        new_icon = "🆕" if app.is_new else ""
        name = app.name_zh if app.name_zh else app.name_en
        if app.name_zh:
            name = f"{app.name_zh}({app.name_en})"
        
        return f"{hot_icon}{new_icon}{name}"
    
    def openFile(self, app_id: int):
        """打开文件"""
        app = self.db_manager.get_app_by_id(app_id)
        if not app:
            return
        
        try:
            self.logMessage(f"打开{app.name_zh if app.name_zh else app.name_en}风灵月影工具")
            
            if not os.path.exists(app.save_path):
                app.download = False
                app.save_path = ""
                app.readme = ""
                app.app_md5 = ""
                self.db_manager.update_app(app)
                self.logMessage(f"{app.name_zh if app.name_zh else app.name_en}风灵月影已丢失请重新下载!")
                return
            
            self.file_manager.open_file_or_folder(app.save_path)
            self.logMessage(f"{app.name_zh if app.name_zh else app.name_en}风灵月影已打开")
        except Exception as e:
            self.print(f"打开文件失败: {e}")
            self.logMessage("打开文件失败")
    
    def openFileDir(self, app_id: int):
        """打开文件目录"""
        app = self.db_manager.get_app_by_id(app_id)
        if not app:
            return
        
        try:
            self.logMessage("打开文件夹...")
            
            if app.download and app.save_path:
                folder_path = os.path.dirname(app.save_path)
                self.file_manager.open_file_or_folder(folder_path)
                self.logMessage(f"文件夹{folder_path}已打开")
            else:
                self.logMessage("应用未下载")
        except Exception as e:
            self.print(f"打开文件夹失败: {e}")
            self.logMessage("打开文件夹失败")
    
    def updateFile(self, app_id: int):
        """更新文件"""
        self.worker = Worker(self._async_update_file, app_id)
        self.worker.finished.connect(self._on_update_file_finished)
        self.worker.error.connect(lambda e: self.logMessage(f"更新失败: {e}"))
        self.worker.start()
    
    def _async_update_file(self, app_id: int):
        """异步更新文件"""
        app = self.db_manager.get_app_by_id(app_id)
        if not app:
            return
        
        try:
            self.logMessage(f"{app.name_zh if app.name_zh else app.name_en}更新中...")
            
            app_info = self.network_manager.get_app_info(app.page_url)
            if not app_info:
                self.logMessage("获取应用信息失败")
                return
            
            if app.app_md5 == app_info.get("md5"):
                self.logMessage(f"{app.name_zh if app.name_zh else app.name_en}已经是最新版本")
                return
            
            trainer, readme = self.file_manager.download_and_extract(app_info)
            
            if app.save_path != trainer:
                if os.path.exists(app.save_path):
                    self.file_manager._cleanup_temp_files(app.save_path)
            
            app.save_path = trainer
            app.update_date = app_info.get("date", "")
            app.app_md5 = app_info.get("md5", "")
            app.readme = self.file_manager.read_readme(readme)
            app.download = True
            
            self.db_manager.update_app(app)
            self.logMessage("更新完成")
        except Exception as e:
            self.print(f"更新失败: {e}")
            self.logMessage("更新出错...")
    
    def _on_update_file_finished(self):
        """文件更新完成回调"""
        self.searchData()
    
    def downloadFile(self, app_id: int):
        """下载文件"""
        if not self.downloadPath:
            self.openSettings()
            return
        
        self.worker = Worker(self._async_download_file, app_id)
        self.worker.finished.connect(self._on_download_file_finished)
        self.worker.error.connect(lambda e: self.logMessage(f"下载失败: {e}"))
        self.worker.start()
    
    def _async_download_file(self, app_id: int):
        """异步下载文件"""
        app = self.db_manager.get_app_by_id(app_id)
        if not app:
            return
        
        try:
            self.logMessage(f"{app.name_zh if app.name_zh else app.name_en}下载中...")
            
            app_info = self.network_manager.get_app_info(app.page_url)
            if not app_info:
                self.logMessage("获取应用信息失败")
                return
            
            trainer, readme = self.file_manager.download_and_extract(app_info)
            
            if trainer:
                app.save_path = trainer
                app.update_date = app_info.get("date", "")
                app.app_md5 = app_info.get("md5", "")
                app.readme = self.file_manager.read_readme(readme)
                app.download = True
                
                self.db_manager.update_app(app)
                self.logMessage(f"{app.name_zh if app.name_zh else app.name_en}下载完成")
        except Exception as e:
            self.print(f"下载失败: {e}")
            self.logMessage("下载出错")
    
    def _on_download_file_finished(self):
        """文件下载完成回调"""
        self.searchData()
    
    def openSettings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            new_download_path = dialog.getDownloadPath()
            debug_switch = dialog.getDebugSwitch()
            
            self.debugMode = debug_switch
            self.config_manager.set("debug_mode", debug_switch)
            
            if new_download_path and new_download_path != self.downloadPath:
                FlingCatTools.addWinDefnderWhite(new_download_path)
                self._move_files_to_new_path(new_download_path)
                self.downloadPath = new_download_path
                self.config_manager.set("download_path", self.downloadPath)
                self.file_manager.download_path = new_download_path
            
            self.config_manager.save_settings()
    
    def _move_files_to_new_path(self, new_path: str):
        """移动文件到新路径"""
        try:
            with self.db_manager.get_session() as session:
                apps = session.query(FlingTrainerAppModel).filter(
                    FlingTrainerAppModel.download == True
                ).all()
                
                for app in apps:
                    if os.path.exists(app.save_path):
                        try:
                            result = self.file_manager.move_files_to_new_path(
                                os.path.dirname(app.save_path), new_path
                            )
                            app.save_path = os.path.join(
                                result, os.path.basename(app.save_path)
                            )
                        except Exception as e:
                            self.print(f"移动文件失败: {e}")
                            app.download = False
                            app.app_md5 = ""
                            app.readme = ""
                            app.save_path = ""
            
            self.logMessage("文件已移动")
        except Exception as e:
            self.print(f"移动文件失败: {e}")
            self.logMessage("移动文件失败")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = FlingTrainerApp()
    ex.show()
    sys.exit(app.exec_()) 