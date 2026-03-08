# app/models/interview.py
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, DateTime, Text, func, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class InterviewStyle(str, enum.Enum):
    IN_PERSON = "in_person"
    VIDEO_CALL = "video_call"
    PHONE_CALL = "phone_call"
    PANEL = "panel"
    TECHNICAL = "technical"
    CASE_STUDY = "case_study"


class AssessmentType(str, enum.Enum):
    QUIZ = "quiz"
    CODING_TEST = "coding_test"
    PERSONALITY = "personality"
    SKILLS_TEST = "skills_test"
    WRITTEN = "written"


class QuestionType(str, enum.Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    CODE = "code"


class InterviewSchedule(Base):
    """Detailed interview scheduling with style options"""
    __tablename__ = "interview_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False
    )

    # Who scheduled
    scheduled_by_employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employers.id", ondelete="CASCADE"),
        nullable=False
    )

    # Interview details
    style: Mapped[InterviewStyle] = mapped_column(String, nullable=False, default=InterviewStyle.IN_PERSON)
    
    # Time slots employer offers
    proposed_slots: Mapped[list] = mapped_column(JSONB, default=list)  # [{"datetime": "...", "duration_minutes": 60}]
    
    # Confirmed slot (after job seeker picks)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=True, default=60)
    
    location: Mapped[str] = mapped_column(String, nullable=True)  # Physical or video link
    meeting_link: Mapped[str] = mapped_column(String, nullable=True)  # Zoom/Meet/Teams link
    
    # Employer can allow seeker to pick style
    allow_style_choice: Mapped[bool] = mapped_column(Boolean, default=False)
    available_styles: Mapped[list] = mapped_column(JSONB, default=list)  # styles to pick from
    seeker_chosen_style: Mapped[str] = mapped_column(String, nullable=True)
    
    instructions: Mapped[str] = mapped_column(Text, nullable=True)  # Employer instructions
    notes_for_candidate: Mapped[str] = mapped_column(Text, nullable=True)

    # Status
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    cancellation_reason: Mapped[str] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actual_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    application = relationship("Application", backref="interview_schedule")


class Assessment(Base):
    """A quiz/test attached to a job that candidates must complete"""
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False
    )

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employers.id", ondelete="CASCADE"),
        nullable=False
    )

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    assessment_type: Mapped[AssessmentType] = mapped_column(String, nullable=False, default=AssessmentType.QUIZ)
    
    time_limit_minutes: Mapped[int] = mapped_column(Integer, nullable=True)  # None = no limit
    passing_score: Mapped[int] = mapped_column(Integer, default=60)  # % required to pass
    
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)  # Required before applying
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # When to trigger: "before_apply", "after_shortlist", "before_interview"
    trigger_stage: Mapped[str] = mapped_column(String, default="after_shortlist")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    questions = relationship("AssessmentQuestion", back_populates="assessment", cascade="all, delete-orphan")
    attempts = relationship("AssessmentAttempt", back_populates="assessment", cascade="all, delete-orphan")


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False
    )

    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(String, nullable=False)
    
    # For MCQ: ["Option A", "Option B", ...]
    options: Mapped[list] = mapped_column(JSONB, default=list)
    
    # Correct answer(s)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=True)  # For MCQ: "0" or "2" (index)
    
    points: Mapped[int] = mapped_column(Integer, default=1)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    
    explanation: Mapped[str] = mapped_column(Text, nullable=True)  # Shown after submission

    assessment = relationship("AssessmentQuestion", back_populates="questions", overlaps="questions")
    assessment = relationship("Assessment", back_populates="questions")


class AssessmentAttempt(Base):
    """A job seeker's attempt at an assessment"""
    __tablename__ = "assessment_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False
    )

    job_seeker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_seekers.id", ondelete="CASCADE"),
        nullable=False
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True
    )

    # Answers submitted: {question_id: answer}
    answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    score: Mapped[int] = mapped_column(Integer, nullable=True)  # % score
    passed: Mapped[bool] = mapped_column(Boolean, nullable=True)
    
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    time_taken_seconds: Mapped[int] = mapped_column(Integer, nullable=True)

    assessment = relationship("Assessment", back_populates="attempts")


class ShortlistBroadcast(Base):
    """Employer broadcasts a message/instructions to all shortlisted candidates of a job"""
    __tablename__ = "shortlist_broadcasts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False
    )

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employers.id", ondelete="CASCADE"),
        nullable=False
    )

    subject: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Send via email + in-app notification
    sent_via_email: Mapped[bool] = mapped_column(Boolean, default=True)
    sent_via_notification: Mapped[bool] = mapped_column(Boolean, default=True)
    
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    recipients_count: Mapped[int] = mapped_column(Integer, default=0)