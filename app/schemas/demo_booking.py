from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class DemoBookingRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=8, max_length=20)
    demo_date: str = Field(min_length=8, max_length=32)
    demo_time: str = Field(min_length=4, max_length=32)
    clinic_name: Optional[str] = Field(default=None, max_length=180)
    message: Optional[str] = Field(default="", max_length=5000)
