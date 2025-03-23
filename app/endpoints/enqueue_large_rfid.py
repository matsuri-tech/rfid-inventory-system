# app/endpoints/enqueue_large_rfid.py
from fastapi import APIRouter, Request
from datetime import datetime, timedelta
import uuid
import os
import json
import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.auth import default

router = APIRouter()

@router.post("/enqueue/large-rfid")
async def enqueue_large_rfid(request: Request):
    data = await request.json()
    hardware_key = data.get("hardwareKey")

    if not hardware_key:
        return {"error": "Missing hardwareKey"}, 400

    # Cloud Tasks用設定
    project = "m2m-core"
    location = "asia-northeast1"
    queue = "rfid-task-queue"
    target_url = "https://rfid-cloud-api-829912128848.asia-northeast1.run.app/sync/large-rfid"

    # 遅延15分後に実行
    schedule_time = (datetime.utcnow() + timedelta(minutes=15)).isoformat("T") + "Z"
    task_id = f"large-rfid-task-{uuid.uuid4()}"
    url = f"https://cloudtasks.googleapis.com/v2/projects/{project}/locations/{location}/queues/{queue}/tasks"

    # ✨ POST する body に hardwareKey を含める
    payload = {
        "hardwareKey": hardware_key
    }

    # 認証トークン取得
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
                # base64エンコードされたバイト列にする必要あり！
                "body": json.dumps(payload).encode("utf-8").decode("latin1")
            },
            "scheduleTime": schedule_time
        }
    }

    res = requests.post(url, headers={"Authorization": f"Bearer {token}"}, json=task)
    return {"status": res.status_code, "response": res.text}
