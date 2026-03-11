
# ─── Assessment Routes ────────────────────────────────────────────────────────

@router.post("/assessments")
def create_or_update_assessment(
    body: AssessmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Employer creates or updates an assessment for a job"""
    from app.models.employer import Employer
    from app.models.job import Job

    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    if not employer:
        raise HTTPException(status_code=403, detail="Employer access required")

    job = db.query(Job).filter(Job.id == body.job_id).first()
    if not job or job.employer_id != employer.id:
        raise HTTPException(status_code=403, detail="Unauthorized or job not found")

    # Check if existing assessment
    assessment = db.query(Assessment).filter(Assessment.job_id == body.job_id).first()
    
    if assessment:
        assessment.title = body.title
        assessment.description = body.description
        assessment.assessment_type = body.assessment_type
        assessment.time_limit_minutes = body.time_limit_minutes
        assessment.passing_score = body.passing_score
        assessment.is_required = body.is_required
        assessment.trigger_stage = body.trigger_stage
        
        # Delete old questions for simplicity in update
        db.query(AssessmentQuestion).filter(AssessmentQuestion.assessment_id == assessment.id).delete()
    else:
        assessment = Assessment(
            job_id=body.job_id,
            employer_id=employer.id,
            title=body.title,
            description=body.description,
            assessment_type=body.assessment_type,
            time_limit_minutes=body.time_limit_minutes,
            passing_score=body.passing_score,
            is_required=body.is_required,
            trigger_stage=body.trigger_stage
        )
        db.add(assessment)
        db.flush() # get ID

    # Add questions
    for q in body.questions:
        new_q = AssessmentQuestion(
            assessment_id=assessment.id,
            question_text=q.question_text,
            question_type=q.question_type,
            options=q.options,
            correct_answer=q.correct_answer,
            points=q.points,
            order_index=q.order_index,
            explanation=q.explanation
        )
        db.add(new_q)

    db.commit()
    return {"success": True, "assessment_id": str(assessment.id)}


@router.get("/assessments/job/{job_id}")
def get_job_assessment(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get assessment for a job. Seeker only gets questions, Employer gets answers too."""
    assessment = db.query(Assessment).filter(Assessment.job_id == job_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="No assessment found for this job")

    is_employer = False
    from app.models.employer import Employer
    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    if employer and assessment.employer_id == employer.id:
        is_employer = True

    questions = []
    for q in assessment.questions:
        q_data = {
            "id": str(q.id),
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": q.options,
            "points": q.points,
            "order_index": q.order_index
        }
        if is_employer:
            q_data["correct_answer"] = q.correct_answer
            q_data["explanation"] = q.explanation
        questions.append(q_data)

    return {
        "id": str(assessment.id),
        "title": assessment.title,
        "description": assessment.description,
        "assessment_type": assessment.assessment_type,
        "time_limit_minutes": assessment.time_limit_minutes,
        "passing_score": assessment.passing_score,
        "is_required": assessment.is_required,
        "trigger_stage": assessment.trigger_stage,
        "questions": sorted(questions, key=lambda x: x["order_index"])
    }


@router.post("/assessments/{assessment_id}/attempt")
def start_assessment_attempt(
    assessment_id: UUID,
    application_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Job seeker starts an assessment attempt"""
    from app.models.job_seeker import JobSeeker
    seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.id).first()
    if not seeker:
        raise HTTPException(status_code=403, detail="Job seeker access required")

    assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Check if already attempted and passed
    existing = db.query(AssessmentAttempt).filter(
        AssessmentAttempt.assessment_id == assessment_id,
        AssessmentAttempt.job_seeker_id == seeker.id,
        AssessmentAttempt.passed == True
    ).first()
    if existing:
        return {"success": True, "message": "You have already passed this assessment", "attempt_id": str(existing.id), "passed": True}

    attempt = AssessmentAttempt(
        assessment_id=assessment_id,
        job_seeker_id=seeker.id,
        application_id=application_id,
        started_at=datetime.now(timezone.utc)
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return {"success": True, "attempt_id": str(attempt.id)}


@router.post("/attempts/{attempt_id}/submit")
def submit_assessment_attempt(
    attempt_id: UUID,
    body: AssessmentSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Job seeker submits answers. Logic for auto-grading MCQs."""
    attempt = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    
    if attempt.submitted_at:
        raise HTTPException(status_code=400, detail="Assessment already submitted")

    assessment = db.query(Assessment).filter(Assessment.id == attempt.assessment_id).first()
    
    # Auto-grading
    total_points = 0
    earned_points = 0
    
    for q in assessment.questions:
        total_points += q.points
        user_answer = body.answers.get(str(q.id))
        
        if q.question_type == QuestionType.MULTIPLE_CHOICE or q.question_type == QuestionType.TRUE_FALSE:
            if user_answer == q.correct_answer:
                earned_points += q.points
    
    score_pct = (earned_points / total_points * 100) if total_points > 0 else 100
    passed = score_pct >= assessment.passing_score
    
    attempt.answers = body.answers
    attempt.score = int(score_pct)
    attempt.passed = passed
    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.time_taken_seconds = (attempt.submitted_at - attempt.started_at.replace(tzinfo=timezone.utc)).total_seconds()
    
    db.commit()
    
    return {
        "success": True,
        "score": attempt.score,
        "passed": attempt.passed,
        "message": "Passed! Great job." if passed else "Did not meet the passing score. Better luck next time."
    }
