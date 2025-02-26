from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=func.current_timestamp())

    # Relationships
    login_history = relationship("LoginHistory", back_populates="user")
    conversations = relationship("ConversationTitle", back_populates="user")

    def __repr__(self):
        return f"<User(username='{self.username}', name='{self.name}', email='{self.email}')>"


class LoginHistory(Base):
    __tablename__ = 'login_history'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    login_time = Column(DateTime, default=func.current_timestamp())
    logout_time = Column(DateTime)
    ip_address = Column(String(50))
    user_agent = Column(Text)

    # Relationships
    user = relationship("User", back_populates="login_history")

    def __repr__(self):
        return f"<LoginHistory(user_id={self.user_id}, login_time='{self.login_time}')>"


class ConversationTitle(Base):
    __tablename__ = 'conversation_titles'

    id = Column(Integer, primary_key=True)
    thread_id = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Relationships
    user = relationship("User", back_populates="conversations")

    def __repr__(self):
        return f"<ConversationTitle(thread_id='{self.thread_id}', title='{self.title}', user_id={self.user_id})>"