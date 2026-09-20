from pydantic import BaseModel, Field


class InterviewRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=200)
    company: str = Field(..., min_length=1, max_length=200)
    job_description: str = Field(..., min_length=10, max_length=8000)


class ResumeRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=200)
    company: str = Field(..., min_length=1, max_length=200)
    job_description: str = Field(..., min_length=10, max_length=8000)
    background: str = Field(..., min_length=10, max_length=8000)


class JobMatchRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=200)
    resume_text: str = Field(..., min_length=10, max_length=8000)
    location: str = Field("", max_length=200)
    country: str = Field("in", min_length=2, max_length=2)
    work_modes: list[str] = Field(default_factory=lambda: ["remote", "hybrid", "onsite"])


class TrackJobRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    company: str = Field("", max_length=300)
    location: str = Field("", max_length=300)
    url: str = Field("", max_length=2000)
    salary_min: int | None = None
    salary_max: int | None = None
    work_mode: str = Field("", max_length=20)


class UpdateJobStatusRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=20)


class UpdateJobNotesRequest(BaseModel):
    notes: str = Field("", max_length=2000)


class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=500)
