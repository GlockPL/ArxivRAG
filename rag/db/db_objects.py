from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, Index, LargeBinary
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base
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


class CheckpointBlob(Base):
    __tablename__ = 'checkpoint_blobs'

    thread_id = Column(String, primary_key=True)
    checkpoint_ns = Column(String, primary_key=True, default='')
    channel = Column(String, primary_key=True)
    version = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    blob = Column(LargeBinary)

    __table_args__ = (
        Index('checkpoint_blobs_thread_id_idx', 'thread_id'),
    )

    def __repr__(self):
        return f"<CheckpointBlob(thread_id='{self.thread_id}', checkpoint_ns='{self.checkpoint_ns}', channel='{self.channel}', version='{self.version}')>"


class CheckpointWrite(Base):
    __tablename__ = 'checkpoint_writes'

    thread_id = Column(String, primary_key=True)
    checkpoint_ns = Column(String, primary_key=True, default='')
    checkpoint_id = Column(String, primary_key=True)
    task_id = Column(String, primary_key=True)
    idx = Column(Integer, primary_key=True)
    channel = Column(String, nullable=False)
    type = Column(String)
    blob = Column(LargeBinary, nullable=False)
    task_path = Column(String, nullable=False, default='')

    __table_args__ = (
        Index('checkpoint_writes_thread_id_idx', 'thread_id'),
    )

    def __repr__(self):
        return f"<CheckpointWrite(thread_id='{self.thread_id}', checkpoint_ns='{self.checkpoint_ns}', checkpoint_id='{self.checkpoint_id}', task_id='{self.task_id}', idx={self.idx})>"


class Checkpoint(Base):
    __tablename__ = 'checkpoints'

    thread_id = Column(String, primary_key=True)
    checkpoint_ns = Column(String, primary_key=True, default='')
    checkpoint_id = Column(String, primary_key=True)
    parent_checkpoint_id = Column(String)
    type = Column(String)
    checkpoint = Column(JSONB, nullable=False)
    metadata_json = Column("metadata", JSONB, nullable=False, default={})

    __table_args__ = (
        Index('checkpoints_thread_id_idx', 'thread_id'),
    )

    def __repr__(self):
        return f"<Checkpoint(thread_id='{self.thread_id}', checkpoint_ns='{self.checkpoint_ns}', checkpoint_id='{self.checkpoint_id}')>"


# Migration tracking table (mentioned in your setup function)
class CheckpointMigration(Base):
    __tablename__ = 'checkpoint_migrations'

    v = Column(Integer, primary_key=True)

    def __repr__(self):
        return f"<CheckpointMigration(v={self.v})>"