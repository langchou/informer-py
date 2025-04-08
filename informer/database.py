"""
数据库模块 - 处理数据存储
"""

import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from loguru import logger

Base = declarative_base()


class Post(Base):
    """帖子模型"""
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True)
    forum = Column(String(50), nullable=False, index=True)
    post_id = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    def __repr__(self):
        return f"<Post(forum='{self.forum}', post_id='{self.post_id}', title='{self.title}')>"


class Database:
    """数据库操作类"""
    
    def __init__(self, db_path="data/posts.db"):
        """
        初始化数据库连接
        
        Args:
            db_path: 数据库文件路径
        """
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 创建数据库引擎
        self.engine = create_engine(f"sqlite:///{db_path}")
        
        # 创建表
        Base.metadata.create_all(self.engine)
        
        # 创建会话
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def is_new_post(self, forum, post_id):
        """
        检查帖子是否为新帖子
        
        Args:
            forum: 论坛名称
            post_id: 帖子ID
            
        Returns:
            bool: 是否为新帖子
        """
        return self.session.query(Post).filter(
            Post.forum == forum,
            Post.post_id == post_id
        ).first() is None
    
    def store_post(self, forum, post_id, title=None, url=None):
        """
        存储帖子信息
        
        Args:
            forum: 论坛名称
            post_id: 帖子ID
            title: 帖子标题
            url: 帖子链接
        """
        post = Post(forum=forum, post_id=post_id, title=title, url=url)
        self.session.add(post)
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"存储帖子失败: {e}")
    
    def clean_old_posts(self, days=30):
        """
        清理旧帖子记录
        
        Args:
            days: 保留天数
        """
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        try:
            self.session.query(Post).filter(Post.created_at < cutoff_date).delete()
            self.session.commit()
            logger.info(f"成功清理{days}天前的帖子记录")
        except Exception as e:
            self.session.rollback()
            logger.error(f"清理旧帖子记录失败: {e}")
    
    def close(self):
        """关闭数据库连接"""
        self.session.close() 