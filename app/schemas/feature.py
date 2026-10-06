from pydantic import BaseModel, Field, ValidationError


class FeatureHighlightCard(BaseModel):
    label: str = ""
    text: str = ""
    icon: str = ""
    iconBg: str = ""
    iconColor: str = ""


class FeatureShowcase(BaseModel):
    title: str = ""
    description: str = ""
    bullets: list[str] = Field(default_factory=list)
    reverse: bool = False


class FeatureFaq(BaseModel):
    id: int = 1
    question: str = ""
    answer: str = ""


class FeatureImages(BaseModel):
    hero: str = ""
    overview: str = ""
    showcaseDashboard: str = ""
    showcaseEditor: str = ""
    highlight: str = ""
    faq: str = ""


class FeatureItem(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    icon: str = Field(..., min_length=1)
    iconBg: str = Field(..., min_length=1)
    iconColor: str = Field(..., min_length=1)
    content: str = ""
    overviewEyebrow: str = ""
    overviewTitle: str = ""
    overviewDescription: str = ""
    overviewBenefits: list[str] = Field(default_factory=list)
    highlightHeadline: str = ""
    highlightCta: str = ""
    highlightSecondaryTitle: str = ""
    highlightSecondaryText: str = ""
    highlightCards: list[FeatureHighlightCard] = Field(default_factory=list)
    showcases: list[FeatureShowcase] = Field(default_factory=list)
    faqs: list[FeatureFaq] = Field(default_factory=list)
    relatedSlugs: list[str] = Field(default_factory=list)
    images: FeatureImages = Field(default_factory=FeatureImages)


def validate_features_content(data):
    if not isinstance(data, list):
        raise ValueError("Features content must be an array")

    seen_ids = set()
    validated = []

    for item in data:
        try:
            feature = FeatureItem.model_validate(item)
        except ValidationError as error:
            raise ValueError(str(error)) from error
        if feature.id in seen_ids:
            raise ValueError(f"Duplicate feature ID: {feature.id}")
        seen_ids.add(feature.id)
        validated.append(feature.model_dump())

    return validated
