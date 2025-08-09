from contextlib import contextmanager
from typing import Optional, List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from db import Base, FlingTrainerAppModel


class DatabaseManager:
    """数据库管理器，负责数据库操作"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.engine = create_engine(db_path)
        self.Session = sessionmaker(bind=self.engine)
        self._init_database()
    
    def _init_database(self) -> None:
        """初始化数据库"""
        Base.metadata.create_all(self.engine)
    
    @contextmanager
    def get_session(self):
        """获取数据库会话的上下文管理器"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_app_by_id(self, app_id: int) -> Optional[FlingTrainerAppModel]:
        """根据ID获取应用"""
        with self.get_session() as session:
            app = session.query(FlingTrainerAppModel).filter_by(id=app_id).first()
            if app:
                # 确保对象在会话关闭后仍可访问
                session.expunge(app)
            return app
    
    def update_app(self, app: FlingTrainerAppModel) -> None:
        """更新应用信息"""
        with self.get_session() as session:
            session.merge(app)
    
    def search_apps(self, search_text: str, downloaded_only: bool = False) -> List[FlingTrainerAppModel]:
        """搜索应用"""
        with self.get_session() as session:
            query = session.query(FlingTrainerAppModel).filter(
                (FlingTrainerAppModel.name_zh.like(f"%{search_text}%")) |
                (FlingTrainerAppModel.name_en.like(f"%{search_text}%"))
            ).order_by(
                FlingTrainerAppModel.download.desc(),
                FlingTrainerAppModel.is_hot.desc(),
                FlingTrainerAppModel.is_new.desc(),
                FlingTrainerAppModel.name_zh,
                FlingTrainerAppModel.name_en,
            )
            
            if downloaded_only:
                query = query.filter(FlingTrainerAppModel.download == True)
            
            results = query.all()
            # 确保所有对象在会话关闭后仍可访问
            for app in results:
                session.expunge(app)
            
            return results 