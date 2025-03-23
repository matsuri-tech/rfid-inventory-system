from fastapi import APIRouter, Request
from datetime import datetime, timedelta
import uuid
import json
import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.auth import default

router = APIRouter()

@router.post("/enqueue/large-rfid")
async def enqueue_large_rfid(request: Request):
    # 環境変数は使わず、値を直書き
    project = "m2m-core"
    location = "asia-northeast1"
    queue = "rfid-task-queue"
    target_url = "https://rfid-cloud-api-829912128848.asia-northeast1.run.app/sync/large-rfid"

    # 遅延時間を15分に設定
    schedule_time = (datetime.utcnow() + timedelta(minutes=15)).isoformat("T") + "Z"
    task_id = f"large-rfid-task-{uuid.uuid4()}"
    url = f"https://cloudtasks.googleapis.com/v2/projects/{project}/locations/{location}/queues/{queue}/tasks"

    payload = {}

    # Cloud Tasks 用トークン取得
    credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(GoogleRequest())
    token = credentials.token

    task = {
        "task": {
            "name": f"projects/{project}/locations/{location}/queues/{queue}/tasks/{task_id}",
            "httpRequest": {
                "httpMethod": "POST",
                "url": target_url,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps(payload).encode("utf-8").decode("latin1")
            },
            "scheduleTime": schedule_time
        }
    }

    res = requests.post(url, headers={"Authorization": f"Bearer {token}"}, json=task)
    return {"status": res.status_code, "response": res.text}
