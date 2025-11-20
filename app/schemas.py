from pydantic import BaseModel
from typing import List, Optional, Literal

Severity = Literal["Low", "Medium", "High", "Critical"]
Category = Literal["Billing", "Login", "Performance", "Bug", "Question/How-To", "Other"]

class TriageRequest(BaseModel):
    description: str

class KBMatch(BaseModel):
    id: str
    title: str
    score: float
    recommended_action: str

class TriageResponse(BaseModel):
    summary: str
    category: Category
    severity: Severity
    known_issue: bool
    kb_matches: List[KBMatch]
    suggested_next_step: str
