from typing import Literal
from pydantic import BaseModel, Field

Intent = Literal["damaged_item", "delayed_delivery", "refund_status", "unknown"]
Action = Literal["replacement", "refund", "answer", "clarify", "escalate"]


class Classification(BaseModel):
    intent: Intent


class Proposal(BaseModel):
    action: Action
    explanation: str = Field(max_length=2000)
    customer_response: str = Field(max_length=3000)
    citations: list[str]


class TicketInput(BaseModel):
    subject: str = Field(min_length=3, max_length=140)
    message: str = Field(min_length=5, max_length=4000)
    order_id: str | None = Field(default=None, max_length=50)


class PurchaseInput(BaseModel):
    product_id: str = Field(min_length=2, max_length=50)
    quantity: int = Field(default=1, ge=1, le=5)


class ApprovalInput(BaseModel):
    approve: bool
    proposal_hash: str = Field(min_length=64, max_length=64)


class LoginInput(BaseModel):
    identity: Literal["reviewer", "maya", "alex", "priya"]


class JudgeScore(BaseModel):
    correct_resolution: bool
    faithfulness: float = Field(ge=0, le=1)
    citation_support: float = Field(ge=0, le=1)
    helpfulness: float = Field(ge=0, le=1)
    explanation: str
