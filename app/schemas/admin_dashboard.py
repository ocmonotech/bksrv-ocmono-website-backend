from pydantic import BaseModel


class DashboardStatsResponse(BaseModel):
    new_leads: int
    pending_reviews: int
    newsletter_subscribers: int
    draft_blogs: int
    chatbot_sessions: int
    seo_total: int
    seo_with_issues: int
    seo_average_score: int


class NewsletterSubscriberOut(BaseModel):
    id: int
    email: str
    source: str
    status: str
    created_at: str


class MediaFileOut(BaseModel):
    filename: str
    url: str
    size: int
    modified_at: str
