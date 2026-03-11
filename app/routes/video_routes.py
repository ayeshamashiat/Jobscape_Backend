from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List
import json
from uuid import UUID

from app.database import get_db
from app.models.interview import InterviewSchedule
from app.models.user import User
from app.utils.security import get_user_from_token

router = APIRouter(prefix="/video", tags=["video"])

class ConnectionManager:
    def __init__(self):
        # Room ID -> List of participant dicts: {"ws": WebSocket, "user_id": str, "role": str, "name": str}
        self.rooms: Dict[str, List[Dict]] = {}
        # Room ID -> Active candidate user_id (the one currently in the call with the employer)
        self.active_candidates: Dict[str, str] = {}

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str, role: str, name: str):
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = []
        
        participant = {"ws": websocket, "user_id": str(user_id), "role": role, "name": name}
        self.rooms[room_id].append(participant)
        
        # Broadcast initial state to the new participant
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
        host = next((p for p in participants if p["role"] == "employer"), None)
        candidates = [p for p in participants if p["role"] != "employer"]
        active_id = self.active_candidates.get(room_id)

        for i, p in enumerate(participants):
            state = {
                "type": "room_state",
                "is_host": p["role"] == "employer",
                "active_candidate_id": active_id,
                "participants_count": len(participants),
                "queue": [{"user_id": c["user_id"], "name": c["name"]} for c in candidates],
            }
            if p["role"] != "employer":
                # Find position in queue
                try:
                    pos = next(idx for idx, c in enumerate(candidates) if c["user_id"] == p["user_id"])
                    state["queue_position"] = pos + 1
                except StopIteration:
                    state["queue_position"] = 0
            
            await p["ws"].send_text(json.dumps(state))

    async def broadcast_signaling(self, message: str, room_id: str, sender_ws: WebSocket):
        """Standard WebRTC signaling broadcast, but only between Host and Active Candidate"""
        participants = self.rooms.get(room_id, [])
        sender = next((p for p in participants if p["ws"] == sender_ws), None)
        if not sender: return

        active_id = self.active_candidates.get(room_id)
        
        for p in participants:
            if p["ws"] == sender_ws: continue
            
            # Logic: 
            # 1. If Host sends, only the Active Candidate receives.
            # 2. If Active Candidate sends, only the Host receives.
            # 3. If others send, nobody receives (they are in waiting room).
            
            allow = False
            if sender["role"] == "employer":
                if p["user_id"] == active_id: allow = True
            elif sender["user_id"] == active_id:
                if p["role"] == "employer": allow = True
            
            if allow:
                await p["ws"].send_text(message)

manager = ConnectionManager()

@router.websocket("/ws/{interview_id}")
async def websocket_endpoint(websocket: WebSocket, interview_id: str, token: str, db: Session = Depends(get_db)):
    from app.utils.security import get_user_from_token
    from app.models.employer import Employer
    from app.models.job_seeker import JobSeeker
    from app.models.interview import InterviewSlotPool

    user_id, scope = get_user_from_token(token)
    if not user_id:
        await websocket.close(code=4003)
        return

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        await websocket.close(code=4003)
        return

    # Check access (InterviewSchedule OR InterviewSlotPool)
    # If the ID is a Schedule ID, it's a 1-on-1 or specific booking.
    # If the ID is a Slot ID, it's a shared FCFS pool.
    
    interview = db.query(InterviewSchedule).filter(InterviewSchedule.id == interview_id).first()
    slot_pool = None
    if not interview:
        slot_pool = db.query(InterviewSlotPool).filter(InterviewSlotPool.id == interview_id).first()
    
    if not interview and not slot_pool:
        await websocket.close(code=4004)
        return
    
    has_access = False
    name = user.full_name if hasattr(user, "full_name") else "User"
    
    if user.role == "employer":
        employer = db.query(Employer).filter(Employer.user_id == user.id).first()
        if employer:
            if interview and interview.scheduled_by_employer_id == employer.id:
                has_access = True
            elif slot_pool and slot_pool.employer_id == employer.id:
                has_access = True
    else:
        seeker = db.query(JobSeeker).filter(JobSeeker.user_id == user.id).first()
        if seeker:
            if interview and interview.application.job_seeker_id == seeker.id:
                has_access = True
            elif slot_pool:
                # Check if this seeker has an application booking this slot
                from app.models.application import Application
                booking = db.query(Application).filter(
                    Application.job_seeker_id == seeker.id,
                    Application.booked_slot_id == slot_pool.id
                ).first()
                if booking:
                    has_access = True

    if not has_access:
        await websocket.close(code=4003)
        return
    
    await manager.connect(websocket, interview_id, user.id, user.role, name)
    
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            # Special command for Employer to admit a candidate
            if user.role == "employer" and msg.get("type") == "admit_candidate":
                candidate_id = msg.get("candidate_id")
                manager.active_candidates[interview_id] = candidate_id
                await manager.update_room_state(interview_id)
                # Signaling will now flow between employer and this candidate
            else:
                # Regular signaling (Offer/Answer/Candidate)
                await manager.broadcast_signaling(data, interview_id, websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, interview_id)
        await manager.update_room_state(interview_id)
