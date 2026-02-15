"""
Single Session Manager
Only allows one active session per user.
"""
import json
import os
import uuid
from datetime import datetime, timezone

SESSION_FILE = "active_sessions.json"

def load_sessions() -> dict:
    """Load active sessions from file"""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"WARNING: load_sessions failed: {e}")
            return {}
    return {}

def save_sessions(sessions: dict):
    """Save active sessions to file"""
    with open(SESSION_FILE, 'w') as f:
        json.dump(sessions, f, indent=2)

def create_session(username: str) -> str:
    """Create new session for user, invalidating any previous session"""
    sessions = load_sessions()
    session_id = str(uuid.uuid4())
    sessions[username] = {
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    save_sessions(sessions)
    return session_id

def validate_session(username: str, session_id: str) -> bool:
    """Check if session is still valid (not replaced by another login)"""
    sessions = load_sessions()
    if username not in sessions:
        return False
    return sessions[username]["session_id"] == session_id

def clear_session(username: str):
    """Remove session on logout"""
    sessions = load_sessions()
    if username in sessions:
        del sessions[username]
        save_sessions(sessions)
