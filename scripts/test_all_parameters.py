import asyncio
import sys
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import SessionLocal, Base, engine

async def test_backend():
    print("Starting parameter tests for Tvira API...")
    
    # We will test all endpoints with correct and incorrect parameters
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        
        # 1. POST /api/v1/sessions
        print("\n--- Testing POST /api/v1/sessions ---")
        # Test valid request (empty body/None is valid)
        r = await client.post("/api/v1/sessions", json={})
        print(f"Valid request status: {r.status_code}")
        session_id = None
        session_token = None
        if r.status_code == 201:
            data = r.json()
            session_id = data["session_id"]
            print(f"Created session: {session_id}")
            
        # Test invalid body schema (e.g. wrong type for business_name)
        r = await client.post("/api/v1/sessions", json={"business_name": 12345})
        print(f"Invalid parameter type status: {r.status_code} (Expected 422/400)")
        if r.status_code == 422:
            print("Validation error detail:", r.json().get("detail"))

        # 2. GET /api/v1/sessions/{session_id}
        print("\n--- Testing GET /api/v1/sessions/{{session_id}} ---")
        # Test invalid UUID format
        r = await client.get("/api/v1/sessions/not-a-uuid")
        print(f"Invalid UUID path parameter format status: {r.status_code} (Expected 422)")
        
        # Test non-existent UUID
        random_uuid = str(uuid4())
        r = await client.get(f"/api/v1/sessions/{random_uuid}")
        print(f"Non-existent UUID status: {r.status_code} (Expected 404)")

        if session_id:
            # Test valid UUID
            r = await client.get(f"/api/v1/sessions/{session_id}")
            print(f"Valid session status: {r.status_code}")
            if r.status_code == 200:
                session_token = r.json()["session"]["session_token"]
                print(f"Retrieved token: {session_token}")

        # 3. GET /api/v1/sessions/resume/{token}
        print("\n--- Testing GET /api/v1/sessions/resume/{{token}} ---")
        # Test non-existent token
        r = await client.get("/api/v1/sessions/resume/non_existent_token_123")
        print(f"Non-existent token status: {r.status_code} (Expected 404)")
        
        if session_token:
            # Test valid token
            r = await client.get(f"/api/v1/sessions/resume/{session_token}")
            print(f"Valid token resume status: {r.status_code}")

        # 4. POST /api/v1/sessions/{session_id}/respond
        print("\n--- Testing POST /api/v1/sessions/{{session_id}}/respond ---")
        # Test invalid body parameters (missing keys)
        if session_id:
            r = await client.post(f"/api/v1/sessions/{session_id}/respond", json={})
            print(f"Missing request fields status: {r.status_code} (Expected 422)")
            
            # Test incorrect question key (e.g. not ready to answer monthly_leads first)
            r = await client.post(f"/api/v1/sessions/{session_id}/respond", json={
                "question_key": "monthly_leads",
                "answer": "100"
            })
            print(f"Invalid sequence question key status: {r.status_code} (Expected 400/422)")
            if r.status_code in [400, 422]:
                print("Error detail:", r.json().get("detail"))

            # Test valid sequence question key (business_type)
            r = await client.post(f"/api/v1/sessions/{session_id}/respond", json={
                "question_key": "business_type",
                "answer": "Coaching Institute"
            })
            print(f"Valid first question answer status: {r.status_code}")

        # 5. POST /api/v1/sessions/{session_id}/lead
        print("\n--- Testing POST /api/v1/sessions/{{session_id}}/lead ---")
        if session_id:
            # Test missing email
            r = await client.post(f"/api/v1/sessions/{session_id}/lead", json={
                "name": "John",
                "phone": "1234567"
            })
            print(f"Missing email status: {r.status_code} (Expected 422)")
            
            # Test invalid email format
            r = await client.post(f"/api/v1/sessions/{session_id}/lead", json={
                "name": "John",
                "email": "invalid_email_format",
                "phone": "1234567"
            })
            print(f"Invalid email format status: {r.status_code} (Expected 422)")

            # Test invalid phone length (too short)
            r = await client.post(f"/api/v1/sessions/{session_id}/lead", json={
                "name": "John",
                "email": "john@test.com",
                "phone": "1"
            })
            print(f"Too short phone status: {r.status_code} (Expected 422)")

        # 6. POST /api/v1/sessions/{session_id}/evaluate
        print("\n--- Testing POST /api/v1/sessions/{{session_id}}/evaluate ---")
        if session_id:
            # Test evaluate before session is complete
            r = await client.post(f"/api/v1/sessions/{session_id}/evaluate")
            print(f"Evaluate in-progress session status: {r.status_code}")

        # 7. GET /api/v1/sessions/{session_id}/report
        print("\n--- Testing GET /api/v1/sessions/{{session_id}}/report ---")
        if session_id:
            # Test report before completed
            r = await client.get(f"/api/v1/sessions/{session_id}/report")
            print(f"Get report before completed status: {r.status_code} (Expected 404)")
            if r.status_code == 404:
                print("Expected detail message:", r.json().get("detail"))

if __name__ == "__main__":
    asyncio.run(test_backend())
