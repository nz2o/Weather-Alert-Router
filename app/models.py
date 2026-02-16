from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
from sqlalchemy.sql import func as sqlfunc
from .db import Base

class Alert(Base):
    __tablename__ = 'alerts'
    id = Column(String, primary_key=True)
    properties = Column(JSONB)
    geometry = Column(Geometry(geometry_type='GEOMETRY', srid=4326))
    received_at = Column(DateTime(timezone=True), server_default=sqlfunc.now())

class ApiKey(Base):
    __tablename__ = 'api_keys'
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, index=True, nullable=False)
    owner = Column(String, nullable=True)
    active = Column(Integer, default=1)
