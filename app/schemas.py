from pydantic import BaseModel
from typing import Optional, Any

class AlertIn(BaseModel):
    id: str
    properties: dict
    geometry: Optional[Any]

class AlertOut(BaseModel):
    id: str
    properties: dict
    geometry: Optional[Any]

class ApiKeyCreate(BaseModel):
    owner: Optional[str]
