from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import json
from uuid import UUID

from app.database import get_db
from app.models.interview import InterviewSchedule
from app.models.user import User
from app.utils.security import get_user_from_token, get_current_user

router = APIRouter(prefix="/video", tags=["video"])

class ConnectionManager:
    
    def __init__(self):
        # Room ID -> List of participant dicts: {"ws": WebSocket, "user_id": str, "role": str, "name": str}
        self.rooms: Dict[str, List[Dict]] = {}
        # Room ID -> Active candidate user_id (the one currently in the call with the employer)
        self.active_candidates: Dict[str, str] = {}

    async def add_to_room(self, websocket: WebSocket, room_id: str, user_id: str, role: str, name: str):
        """Add an already-accepted WebSocket to a room and auto-admit if appropriate."""
        if room_id not in self.rooms:
            self.rooms[room_id] = []
        
        participant = {"ws": websocket, "user_id": str(user_id), "role": role, "name": name}
        self.rooms[room_id].append(participant)
        
        # Auto-admit logic:
        # If a candidate joins and an employer is present but no one is currently active -> admit immediately.
        # If the employer joins and candidates are already waiting -> admit the first one.
        participants = self.rooms[room_id]
        host = next((p for p in participants if p["role"].upper() == "EMPLOYER"), None)
        candidates = [p for p in participants if p["role"].upper() != "EMPLOYER"]
        
        if host and candidates and room_id not in self.active_candidates:
            # Auto-admit the first candidate in the queue
            self.active_candidates[room_id] = candidates[0]["user_id"]
        
        # Broadcast state to everyone (new participant sees their status immediately)
        await self.update_room_state(room_id)


    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.rooms:
            self.rooms[room_id] = [p for p in self.rooms[room_id] if p["ws"] != websocket]
            if not self.rooms[room_id]:
                del self.rooms[room_id]
                if room_id in self.active_candidates:
                    del self.active_candidates[room_id]
            else:
                # If the active candidate disconnected, clear the active slot
                participant_ids = [p["user_id"] for p in self.rooms[room_id]]
                if room_id in self.active_candidates and self.active_candidates[room_id] not in participant_ids:
                    del self.active_candidates[room_id]

    async def update_room_state(self, room_id: str):
        """Broadcast queue status to everyone in the room"""
        participants = self.rooms.get(room_id, [])
        candidates = [p for p in participants if p["role"].upper() != "EMPLOYER"]
        active_id = self.active_candidates.get(room_id)

        dead = []
        for p in participants:
            is_host = p["role"].upper() == "EMPLOYER"
            
            # Build candidate queue (all candidates, active first)
            active_candidates_list = [c for c in candidates if c["user_id"] == active_id]
            waiting_candidates = [c for c in candidates if c["user_id"] != active_id]
            ordered_candidates = active_candidates_list + waiting_candidates
            
            queue = [{"user_id": c["user_id"], "name": c["name"]} for c in ordered_candidates]
            
            # Find this participant's position in queue
            queue_position = None
            if not is_host and p["user_id"] != active_id:
                for i, c in enumerate(waiting_candidates):
                    if c["user_id"] == p["user_id"]:
                        queue_position = i + 1
                        break

            state = {
                "type": "room_state",
                "my_id": p["user_id"],
                "is_host": is_host,
                "active_candidate_id": active_id,
                "participants_count": len(participants),
                "queue": queue,
                "queue_position": queue_position,
            }
            try:
                await p["ws"].send_text(json.dumps(state))
            except Exception:
                dead.append(p)

        for p in dead:
            self.rooms[room_id] = [x for x in self.rooms.get(room_id, []) if x != p]

    async def broadcast_signaling(self, message, room_id: str, sender_ws: WebSocket):
        """
        Route a signaling message only between the employer and the active candidate.
        Everyone else is ignored.
        """
        participants = self.rooms.get(room_id, [])
        if not participants:
            return

        sender = next((p for p in participants if p["ws"] == sender_ws), None)
        if not sender:
            return

        active_id = self.active_candidates.get(room_id)

        for p in participants:
            if p["ws"] == sender_ws:
                continue  # don't echo to sender

            allow = False
            if sender["role"].upper() == "EMPLOYER":
                # Employer -> active candidate only
                if p["user_id"] == active_id:
                    allow = True
            elif sender["user_id"] == active_id:
                # Active candidate -> employer only
                if p["role"].upper() == "EMPLOYER":
                    allow = True

            if allow:
                try:
                    await p["ws"].send_text(message)
                except Exception:
                    pass

    async def admit_candidate(self, room_id: str, candidate_id: str, requester_ws: WebSocket):
        """Employer explicitly admits a candidate."""
        participants = self.rooms.get(room_id, [])
        
        # Verify requester is the employer
        requester = next((p for p in participants if p["ws"] == requester_ws), None)
        if not requester or requester["role"].upper() != "EMPLOYER":
            return
        
        # Verify the candidate is actually in the room
        candidate = next((p for p in participants if p["user_id"] == candidate_id and p["role"].upper() != "EMPLOYER"), None)
        if not candidate:
            return
        
        self.active_candidates[room_id] = candidate_id
        await self.update_room_state(room_id)

    async def end_interview(self, room_id: str):
        """Notify all participants that the interview has ended."""
        participants = self.rooms.get(room_id, [])
        dead = []
        for p in participants:
            try:
                await p["ws"].send_text(json.dumps({"type": "interview_ended"}))
            except Exception:
                dead.append(p)


manager = ConnectionManager()


def _send_error(reason: str, code: int = 4001) -> str:
    return json.dumps({"type": "error", "reason": reason, "code": code})


# ── REST endpoints ──────────────────────────────────────────────────────────

class CompleteInterviewBody(BaseModel):
    interview_id: str
    candidate_id: str
    notes: str = ""
    overall_rating: int = Field(ge=1, le=5, default=3)
    advance_candidate: bool = False
    reject: bool = False
    metrics: dict = {}


@router.post("/complete-interview")
async def complete_interview(
    body: CompleteInterviewBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.employer import Employer
    from app.models.job_seeker import JobSeeker
    from app.models.interview import InterviewSchedule, InterviewSlotPool, InterviewReview
    from app.models.application import Application, ApplicationStatus
    from app.models.selection_round import SelectionProcess
    from app.utils.email import send_rejection_email, send_round_advancement_email, send_final_selection_email

    employer = db.query(Employer).filter(Employer.user_id == current_user.id).first()
    if not employer:
        raise HTTPException(status_code=403, detail="Only employers can complete interviews")

    # Look up interview — it might be an InterviewSchedule OR an InterviewSlotPool
    interview = db.query(InterviewSchedule).filter(InterviewSchedule.id == body.interview_id).first()
    slot_pool = None
    if not interview:
        slot_pool = db.query(InterviewSlotPool).filter(InterviewSlotPool.id == body.interview_id).first()

    if not interview and not slot_pool:
        raise HTTPException(status_code=404, detail="Interview not found")

    # Find the application for this candidate
    candidate_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == body.candidate_id).first()
    if not candidate_seeker:
        # Try by job seeker id directly
        candidate_seeker = db.query(JobSeeker).filter(JobSeeker.id == body.candidate_id).first()

    application = None
    if interview:
        application = interview.application
        # Mark the schedule as completed
        interview.is_completed = True
    elif slot_pool:
        if candidate_seeker:
            application = db.query(Application).filter(
                Application.job_seeker_id == candidate_seeker.id,
                Application.booked_slot_id == slot_pool.id
            ).first()
        
        # Fallback: Maybe candidate_id passed is actually the application_id
        if not application:
            application = db.query(Application).filter(
                Application.id == body.candidate_id,
                Application.booked_slot_id == slot_pool.id
            ).first()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found for this candidate in this interview")

    # Save the review
    existing_review = db.query(InterviewReview).filter(
        InterviewReview.interview_id == (interview.id if interview else slot_pool.id),
        InterviewReview.application_id == application.id,
    ).first()

    if existing_review:
        existing_review.notes = body.notes
        existing_review.metrics = body.metrics
        existing_review.overall_rating = body.overall_rating
    else:
        review = InterviewReview(
            interview_id=interview.id if interview else None,
            application_id=application.id,
            employer_id=employer.id,
            overall_rating=body.overall_rating,
            notes=body.notes,
            metrics=body.metrics,
        )
        db.add(review)

    # Reject or advance the candidate
    if body.reject:
        application.status = ApplicationStatus.REJECTED
        application.rejection_reason = body.notes or "Not selected after interview"
        # Send rejection email/notification (optional)
        try:
            job_seeker_user = application.job_seeker.user if application.job_seeker else None
            if job_seeker_user:
                send_rejection_email(
                    seeker_email=job_seeker_user.email,
                    seeker_name=job_seeker_user.full_name or "Candidate",
                    job_title=application.job.title,
                    company_name=employer.company_name
                )
        except Exception as e:
            print(f"[ERROR] Failed to send notification/email: {e}")
    elif body.advance_candidate:
        selection = db.query(SelectionProcess).filter(SelectionProcess.job_id == application.job_id).first()
        if selection and application.current_round < len(selection.rounds):
            application.current_round += 1
            application.status = ApplicationStatus.SHORTLISTED
        else:
            application.status = ApplicationStatus.ACCEPTED
            try:
                job_seeker_user = application.job_seeker.user if application.job_seeker else None
                if job_seeker_user:
                    send_final_selection_email(
                        seeker_email=job_seeker_user.email,
                        seeker_name=job_seeker_user.full_name or "Candidate",
                        job_title=application.job.title,
                        company_name=employer.company_name
                    )
            except Exception as e:
                print(f"[ERROR] Failed to send notification/email: {e}")
    # else: just save review, status unchanged

    db.commit()

    # ----- Auto‑admit next candidate in the same room -----
    room_id = str(interview.id if interview else slot_pool.id)
    participants = manager.rooms.get(room_id, [])
    candidates = [p for p in participants if p["role"].upper() != "EMPLOYER"]
    active_id = manager.active_candidates.get(room_id)

    # Find the next candidate (first in queue that is not the one we just finished)
    next_candidate = None
    for p in candidates:
        if p["user_id"] != active_id:
            next_candidate = p
            break

    if next_candidate:
        manager.active_candidates[room_id] = next_candidate["user_id"]
        await manager.update_room_state(room_id)

    # Notify active room participants to end the call for the finished candidate (optional)
    await manager.end_interview(str(interview.id if interview else slot_pool.id))

    return {
        "status": "success",
        "message": "Interview completed and review submitted.",
        "more_candidates": next_candidate is not None
    }


@router.websocket("/ws/{interview_id}")
async def websocket_endpoint(websocket: WebSocket, interview_id: str, token: str):
    """
    WebSocket handler for the video interview room.

    NOTE: We intentionally do NOT use Depends(get_db) here.
    FastAPI closes Depends-scoped DB sessions when the endpoint function
    returns its first yield — but WebSocket handlers are long-lived coroutines.
    Instead we create a short-lived session only for the auth/access check,
    close it immediately, then run the message loop without any open session.
    """
    from app.models.employer import Employer
    from app.models.job_seeker import JobSeeker
    from app.models.interview import InterviewSlotPool
    from app.database import SessionLocal

    # MUST accept first — calling close() before accept() causes a crash in this
    # version of websockets (transfer_data_task AttributeError). After accept(),
    # simply returning from the handler closes the connection cleanly.
    await websocket.accept()

    try:
        user_id, scope = get_user_from_token(token)
        if not user_id:
            await websocket.send_text(_send_error("Token expired or invalid. Please refresh the page."))
            return

        # ─── Short-lived DB session for auth only ─────────────────────────────
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.is_active:
                await websocket.send_text(_send_error("User not found or inactive."))
                return

            interview = db.query(InterviewSchedule).filter(InterviewSchedule.id == interview_id).first()
            slot_pool = None
            if not interview:
                slot_pool = db.query(InterviewSlotPool).filter(InterviewSlotPool.id == interview_id).first()

            if not interview and not slot_pool:
                await websocket.send_text(_send_error("Interview room not found.", 4004))
                return

            has_access = False
            name = "User" # Initial default
            user_role = user.role.value.upper()  # .value gets "EMPLOYER" not "UserRole.EMPLOYER"
            user_id_uuid = user.id  # save before session closes

            if user_role == "EMPLOYER":
                employer = db.query(Employer).filter(Employer.user_id == user.id).first()
                if employer:
                    name = employer.full_name
                    if interview and interview.scheduled_by_employer_id == employer.id:
                        has_access = True
                    elif slot_pool and slot_pool.employer_id == employer.id:
                        has_access = True
            else:
                seeker = db.query(JobSeeker).filter(JobSeeker.user_id == user.id).first()
                if seeker:
                    name = seeker.full_name
                    if interview:
                        # Primary check: use the relationship (InterviewSchedule.application)
                        try:
                            app = interview.application
                            if app and app.job_seeker_id == seeker.id:
                                has_access = True
                        except Exception:
                            pass
                        # Fallback using the correct FK — InterviewSchedule.application_id
                        if not has_access:
                            from app.models.application import Application
                            direct_booking = db.query(Application).filter(
                                Application.job_seeker_id == seeker.id,
                                Application.id == interview.application_id
                            ).first()
                            if direct_booking:
                                has_access = True
                    elif slot_pool:
                        from app.models.application import Application
                        booking = db.query(Application).filter(
                            Application.job_seeker_id == seeker.id,
                            Application.booked_slot_id == slot_pool.id
                        ).first()
                        if booking:
                            has_access = True
        finally:
            db.close()  # Always close after auth check — session must NOT outlive auth
        # ─────────────────────────────────────────────────────────────────────

        if not has_access:
            await websocket.send_text(_send_error("Access denied. You are not authorized for this room."))
            return

        # Add to room (WebSocket already accepted above)
        await manager.add_to_room(websocket, interview_id, user_id_uuid, user_role, name)

        try:
            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)

                msg_type = msg.get("type", "")

                if msg_type in ("offer", "answer", "candidate"):
                    await manager.broadcast_signaling(data, interview_id, websocket)
                elif msg_type == "admit_candidate":
                    candidate_id = msg.get("candidate_id")
                    if candidate_id:
                        await manager.admit_candidate(interview_id, candidate_id, websocket)

        except WebSocketDisconnect:
            manager.disconnect(websocket, interview_id)
            await manager.update_room_state(interview_id)
        except Exception as e:
            print(f"[WS ERROR] {e}")
            manager.disconnect(websocket, interview_id)

    except Exception as e:
        print(f"[WS SETUP ERROR] {e}")
        try:
            await websocket.send_text(_send_error(f"Server error: {str(e)}"))
        except Exception:
            pass