from pydantic import BaseModel, EmailStr, Field


class ContactSubmissionRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=8, max_length=20)
    clinic_name: str = Field(min_length=2, max_length=180)
    inquiry_type: str = Field(min_length=2, max_length=80)
    message: str = Field(min_length=10, max_length=5000)


class ContactSubmissionOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str
    clinic_name: str
    inquiry_type: str
    message: str
    status: str
    created_at: str

    class Config:
        from_attributes = True
