from pydantic import BaseModel, EmailStr, Field


class NewsletterSubscribeRequest(BaseModel):
    email: EmailStr
    source: str = Field(default="website", max_length=40)


class NewsletterSubscribeResponse(BaseModel):
    message: str
    email: str
