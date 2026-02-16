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

    # Extracted top-level CAP / NWS properties for easier querying
    sent = Column(DateTime(timezone=True), nullable=True)
    effective = Column(DateTime(timezone=True), nullable=True)
    onset = Column(DateTime(timezone=True), nullable=True)
    expires = Column(DateTime(timezone=True), nullable=True)
    ends = Column(DateTime(timezone=True), nullable=True)

    status = Column(String(128), nullable=True)
    message_type = Column(String(128), nullable=True)
    category = Column(String(128), nullable=True)
    severity = Column(String(128), nullable=True)
    certainty = Column(String(128), nullable=True)
    urgency = Column(String(128), nullable=True)

    event = Column(String(512), nullable=True)
    sender_name = Column(String(256), nullable=True)

    headline = Column(String(512), nullable=True)
    area_desc = Column(String(1024), nullable=True)
    description = Column(String, nullable=True)
    instruction = Column(String, nullable=True)
    response = Column(String(128), nullable=True)

    # Complex nested properties kept as JSONB
    geocode = Column(JSONB, nullable=True)
    geocode_ugc = Column(JSONB, nullable=True)
    geocode_same = Column(JSONB, nullable=True)
    parameters = Column(JSONB, nullable=True)
    # Per-parameter columns (JSONB) — created dynamically from observed keys
    parameters_awipsidentifier = Column(JSONB, nullable=True)
    parameters_blockchannel = Column(JSONB, nullable=True)
    parameters_cmamlongtext = Column(JSONB, nullable=True)
    parameters_cmamtext = Column(JSONB, nullable=True)
    parameters_eas_org = Column(JSONB, nullable=True)
    parameters_eventendingtime = Column(JSONB, nullable=True)
    parameters_eventmotiondescription = Column(JSONB, nullable=True)
    parameters_expiredreferences = Column(JSONB, nullable=True)
    parameters_hailthreat = Column(JSONB, nullable=True)
    parameters_maxhailsize = Column(JSONB, nullable=True)
    parameters_maxwindgust = Column(JSONB, nullable=True)
    parameters_nwsheadline = Column(JSONB, nullable=True)
    parameters_tornadodetection = Column(JSONB, nullable=True)
    parameters_vtec = Column(JSONB, nullable=True)
    parameters_waterspoutdetection = Column(JSONB, nullable=True)
    parameters_weahandling = Column(JSONB, nullable=True)
    parameters_windthreat = Column(JSONB, nullable=True)
    parameters_wmoidentifier = Column(JSONB, nullable=True)
    affected_zones = Column(JSONB, nullable=True)
    references = Column(JSONB, nullable=True)

class ApiKey(Base):
    __tablename__ = 'api_keys'
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, index=True, nullable=False)
    owner = Column(String, nullable=True)
    active = Column(Integer, default=1)
