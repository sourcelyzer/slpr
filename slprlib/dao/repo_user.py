from slpr.dao import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime
import datetime

class RepoUser(Base):

    __tablename__ = 'slpr_users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String)
    password = Column(String)
    email = Column(String)
    is_admin = Column(Boolean)
    last_modified = Column(DateTime, onupdate=datetime.datetime.now)
    state = Column(Integer)

