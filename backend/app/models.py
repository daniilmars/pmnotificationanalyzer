from pydantic import BaseModel, Field
from typing import List, Optional, Union, Literal

# --- Existing Models (for Analysis) ---
class NotificationItem(BaseModel):
    ItemSortNo: str
    Descript: str = ""
    ObjectPart: str = ""
    DamageCode: str = ""

class NotificationHeader(BaseModel):
    Equipment: str
    ShortText: str
    Priority: str
    LongText: str = "" # Added LongText to Header for simpler API payload
    Items: List[NotificationItem] = []

class AnalysisRequest(BaseModel):
    notification: NotificationHeader
    language: str = "en"

class ProblemDetail(BaseModel):
    description: str
    severity: Literal["Critical", "Major", "Minor"]
    field: Optional[str] = None
    suggestion: Optional[str] = None

class AnalysisResponse(BaseModel):
    score: int
    summary: str
    problems: List[ProblemDetail]
    
class ChatMessage(BaseModel):
    author: Literal["user", "assistant"]
    text: str

# --- New DB-Aligned Models (SAP PM Structure) ---

class DBNotificationItem(BaseModel):
    QMNUM: str
    FENUM: str
    OTGRP: Optional[str]
    OTEIL: Optional[str]
    FEGRP: Optional[str]
    FECOD: Optional[str]
    FETXT: Optional[str]

class DBNotificationHeader(BaseModel):
    QMNUM: str
    QMART: str
    QMTXT: Optional[str]
    EQUNR: Optional[str]
    TPLNR: Optional[str]
    PRIOK: Optional[str]
    QMNAM: Optional[str]
    ERDAT: Optional[str]
    MZEIT: Optional[str]
    STRMN: Optional[str]
    LTRMN: Optional[str]
    LongText: Optional[str] = None # Joined from NOTIF_LONGTEXT
    Items: List[DBNotificationItem] = []

class DBMaterial(BaseModel):
    AUFNR: str
    VORNR: str
    MATNR: str
    MAKTX: Optional[str]
    MENGE: float
    MEINS: str

class DBOperation(BaseModel):
    AUFNR: str
    VORNR: str
    LTXA1: str
    ARBPL: Optional[str]
    STEUS: Optional[str]
    DAUER: Optional[str]
    DAUERE: Optional[str]
    Materials: List[DBMaterial] = []

class DBOrderHeader(BaseModel):
    AUFNR: str
    QMNUM: Optional[str]
    AUART: str
    KTEXT: Optional[str]
    GLTRP: Optional[str]
    GLTRS: Optional[str]
    Operations: List[DBOperation] = []

class UnifiedPMObject(BaseModel):
    """
    A unified object representing the full context of a maintenance issue:
    Notification (Problem) + Order (Solution).
    """
    Notification: DBNotificationHeader
    Order: Optional[DBOrderHeader] = None