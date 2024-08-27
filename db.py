from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import declarative_base

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
