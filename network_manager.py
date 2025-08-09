import hashlib
import re
import time
from typing import Dict, Optional
import requests
from lxml import etree


class NetworkManager:
    """网络管理器，负责网络请求"""
    
    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.session = requests.Session()
        self.session.headers.update({
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "zh-CN,zh;q=0.9",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        })
    
    def get_game_list(self) -> Dict:
        """获取游戏列表"""
        url = "https://flingtrainer.com/all-trainers-a-z/"
        start_time = time.time()
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            elapsed_time = int(time.time() - start_time)
            if self.debug_mode:
                print(f"请求列表成功，耗时{elapsed_time}秒")
            
            return self._parse_game_list(response.text)
        except requests.RequestException as e:
            if self.debug_mode:
                print(f"请求列表失败: {e}")
            return {}
    
    def _parse_game_list(self, html: str) -> Dict:
        """解析游戏列表HTML"""
        try:
            root = etree.HTML(html)
            game_list = root.xpath("..//div[starts-with(@id,'a-z-listing-letter')]/ul/li/a")
            
            game_app = {
                self._parse_name(i.xpath("./text()")[0]): {
                    "page_url": i.xpath("./@href")[0]
                }
                for i in game_list
            }
            
            # 获取热门游戏
            self._add_hot_games(root, game_app)
            
            # 获取新游戏
            self._add_new_games(root, game_app)
            
            return game_app
        except Exception as e:
            if self.debug_mode:
                print(f"解析游戏列表失败: {e}")
            return {}
    
    def _parse_name(self, name: str) -> str:
        """解析游戏名称"""
        return re.sub(r"\\n\\t", "", name).strip().rstrip("Trainer").strip()
    
    def _add_hot_games(self, root, game_app: Dict) -> None:
        """添加热门游戏"""
        try:
            hot_list = root.xpath(".//ul[@class='wpp-list']/li/a[2]")
            for item in hot_list:
                name = self._parse_name(item.xpath("./text()")[0])
                if name in game_app:
                    game_app[name]["hot"] = True
                else:
                    game_app[name] = {
                        "page_url": item.xpath("./@href")[0],
                        "hot": True,
                    }
        except Exception as e:
            if self.debug_mode:
                print(f"获取热门游戏出错: {e}")
    
    def _add_new_games(self, root, game_app: Dict) -> None:
        """添加新游戏"""
        try:
            new_list = root.xpath(".//h3[@class='rpwe-title']/a[1]")
            for item in new_list:
                name = self._parse_name(item.xpath("./text()")[0])
                if name in game_app:
                    game_app[name]["new"] = True
                else:
                    game_app[name] = {
                        "page_url": item.xpath("./@href")[0],
                        "new": True,
                    }
        except Exception as e:
            if self.debug_mode:
                print(f"获取新游戏出错: {e}")
    
    def get_app_info(self, page_url: str) -> Optional[Dict]:
        """获取应用详细信息"""
        try:
            response = self.session.get(page_url, timeout=30)
            response.raise_for_status()
            
            return self._parse_app_info(response.text)
        except requests.RequestException as e:
            if self.debug_mode:
                print(f"获取应用信息失败: {e}")
            return None
    
    def _parse_app_info(self, html: str) -> Optional[Dict]:
        """解析应用信息HTML"""
        try:
            root = etree.HTML(html)
            attachment = root.xpath("..//tr[@class='rar' or @class='zip']")[0]
            file_type = attachment.xpath("./@class")[0].split(" ")[0]
            
            attachment_title = attachment.xpath("./td[@class='attachment-title']/a")[0]
            title = attachment_title.xpath("./text()")[0]
            url = attachment_title.xpath("./@href")[0]
            date = attachment.xpath("./td[@class='attachment-date']/text()")[0]
            md5 = hashlib.md5(title.encode(encoding="UTF-8")).hexdigest()
            
            return {
                "title": title,
                "md5": md5,
                "url": url,
                "date": date,
                "file_type": file_type,
            }
        except Exception as e:
            if self.debug_mode:
                print(f"解析应用信息失败: {e}")
            return None 