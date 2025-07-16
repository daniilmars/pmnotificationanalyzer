from pydantic import BaseModel
from typing import Optional, List, Dict

class Notification(BaseModel):
    NotificationId: str
    NotificationType: str
    Description: str
    LongText: str

# Dieses Modell wird vorübergehend nicht verwendet
# class Order(BaseModel):
#     OrderId: str
#     Operations: str
#     Components: str

class Confirmation(BaseModel):
    Activities: str

class AnalysisCase(BaseModel):
    Notification: Notification
    # --- DIAGNOSE-ÄNDERUNG: Wir akzeptieren ein beliebiges Dictionary statt eines strengen Order-Objekts ---
    Order: Optional[Dict] = None 
    Confirmation: Confirmation
    ExternalProtocol: Optional[str] = None

class AnalysisResult(BaseModel):
    score: int
    issues: List[str]
    summary: str
