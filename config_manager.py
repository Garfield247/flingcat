import json
import os
from typing import Dict, Any


class ConfigManager:
    """配置管理器，负责配置文件的读写"""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.settings = self._load_default_settings()
        self._load_settings()
    
    def _load_default_settings(self) -> Dict[str, Any]:
        """加载默认配置"""
        user_home = os.path.expanduser("~")
        default_download_path = os.path.join(user_home, "flingtrainer_app")
        return {
            "download_path": default_download_path,
            "debug_mode": False
        }
    
    def _load_settings(self) -> None:
        """从文件加载配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded_settings = json.load(f)
                    self.settings.update(loaded_settings)
            except (json.JSONDecodeError, IOError) as e:
                print(f"加载配置文件失败: {e}")
    
    def save_settings(self) -> None:
        """保存配置到文件"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"保存配置文件失败: {e}")
    
    def get(self, key: str, default=None):
        """获取配置项"""
        return self.settings.get(key, default)
    
    def set(self, key: str, value) -> None:
        """设置配置项"""
        self.settings[key] = value 