import os
import platform
import shutil
import stat
import subprocess
import sys
import time
from typing import Tuple
from urllib.request import urlretrieve
import chardet


class FileManager:
    """文件管理器，负责文件操作"""
    
    def __init__(self, download_path: str, debug_mode: bool = False):
        self.download_path = download_path
        self.debug_mode = debug_mode
    
    def download_and_extract(self, app_info: dict) -> Tuple[str, str]:
        """下载并解压文件"""
        title = app_info.get("title")
        url = app_info.get("url")
        md5 = app_info.get("md5")
        file_type = app_info.get("file_type")
        
        # 创建临时目录
        temp_path = os.path.join(self.download_path, "temp", md5, f"{int(time.time())}/")
        os.makedirs(temp_path, exist_ok=True)
        
        # 下载文件
        temp_file_path = os.path.join(temp_path, f"{title}.{file_type}")
        try:
            urlretrieve(url, filename=temp_file_path)
        except Exception as e:
            if self.debug_mode:
                print(f"下载文件失败: {e}")
            raise
        
        # 解压文件
        save_path = os.path.join(self.download_path, md5)
        try:
            if file_type == "zip":
                shutil.unpack_archive(temp_file_path, save_path)
            elif file_type == "rar":
                self._extract_rar(temp_file_path, save_path)
        except Exception as e:
            if self.debug_mode:
                print(f"解压文件失败: {e}")
            raise
        finally:
            # 清理临时文件
            self._cleanup_temp_files(temp_path)
        
        # 查找trainer和readme文件
        return self._find_trainer_and_readme(save_path)
    
    def _extract_rar(self, rar_path: str, extract_path: str) -> None:
        """解压RAR文件"""
        if not os.path.exists(extract_path):
            os.makedirs(extract_path)
        
        if hasattr(sys, "_MEIPASS"):
            current_dir = sys._MEIPASS
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
        
        unrar_path = os.path.join(current_dir, "bin", "UnRAR.exe")
        command = [unrar_path, "x", "-y", rar_path, extract_path]
        
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"RAR解压失败: {e}")
    
    def _cleanup_temp_files(self, temp_path: str) -> None:
        """清理临时文件"""
        try:
            if os.path.exists(temp_path):
                os.chmod(temp_path, stat.S_IWRITE)
                shutil.rmtree(temp_path, ignore_errors=True)
        except Exception as e:
            if self.debug_mode:
                print(f"清理临时文件失败: {e}")
    
    def _find_trainer_and_readme(self, save_path: str) -> Tuple[str, str]:
        """查找trainer和readme文件"""
        files = os.listdir(save_path)
        trainer = save_path
        readme = ""
        
        for f in files:
            if f.endswith("Trainer.exe"):
                trainer = os.path.join(save_path, f)
            elif f.lower() == "readme.txt":
                readme = os.path.join(save_path, f)
        
        return trainer, readme
    
    def read_readme(self, readme_path: str) -> str:
        """读取readme文件内容"""
        if not readme_path or not os.path.exists(readme_path):
            return ""
        
        try:
            with open(readme_path, "rb") as f:
                raw_data = f.read()
                encoding = chardet.detect(raw_data)["encoding"]
            
            with open(readme_path, "r", encoding=encoding, errors="ignore") as fp:
                return fp.read()
        except Exception as e:
            if self.debug_mode:
                print(f"读取readme文件失败: {e}")
            return ""
    
    def open_file_or_folder(self, path: str) -> None:
        """打开文件或文件夹"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"路径不存在: {path}")
        
        try:
            if platform.system() == "Windows":
                if os.path.isdir(path):
                    subprocess.run(["explorer.exe", path], shell=True)
                else:
                    subprocess.Popen([path])
            elif platform.system() == "Darwin":
                folder_path = path if os.path.isdir(path) else os.path.dirname(path)
                subprocess.run(["open", folder_path])
            else:
                raise NotImplementedError("不支持的操作系统")
        except Exception as e:
            if self.debug_mode:
                print(f"打开文件失败: {e}")
            raise
    
    def move_files_to_new_path(self, old_path: str, new_path: str) -> str:
        """移动文件到新路径"""
        try:
            result = shutil.move(old_path, new_path)
            return result
        except Exception as e:
            if self.debug_mode:
                print(f"移动文件失败: {e}")
            raise 