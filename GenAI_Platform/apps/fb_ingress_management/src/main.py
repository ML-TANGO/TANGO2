import os
import json
import threading
import traceback
import time
import uvicorn
from fastapi import FastAPI
from ingress_manager.route import ingress_manager
from ingress_manager.manager import manager_routine
from utils.resource import CustomResponse, CustomMiddleWare

def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB Ingress Management API",
        version='0.1',
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/ingress/openapi.json",
        docs_url="/ingress/docs",
        redoc_url="/ingress/redoc"
    )    
    
    api.include_router(ingress_manager)
    app.mount('/api', api)

    return app

def start_manager_routine():
    """백그라운드에서 manager routine 시작 (중앙집중식 관리)"""
    try:
        print("[MAIN] 🔧 Starting ingress manager routine thread...", flush=True)
        routine_thread = threading.Thread(target=manager_routine, daemon=True, name="IngressManagerRoutine")
        routine_thread.start()
        print(f"[MAIN] ✅ Ingress manager routine thread started successfully (Thread ID: {routine_thread.ident})", flush=True)
    except Exception as e:
        print(f"[MAIN] ❌ Failed to start manager routine: {e}", flush=True)
        traceback.print_exc()
    
def main():
    app = initialize_app()
    
    # 백그라운드에서 manager routine 시작
    start_manager_routine()
    
    return app

if __name__=="__main__":
    app = main()
    uvicorn.run(app, port=8000, host='0.0.0.0', reload=True)