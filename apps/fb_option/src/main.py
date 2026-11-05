import os
import json
import threading
import traceback
import uvicorn
from fastapi import FastAPI, Request, Depends
from option.route import options
from utils.resource import CustomResponse, CustomMiddleWare

def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB OPTION API",
        version='0.1',
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/options/openapi.json",
        docs_url="/options/docs",
        redoc_url="/options/redoc"
    )
    
    api.include_router(options)
    app.mount('/api', api)

    return app
    
def main():
    app = initialize_app()
    return app

if __name__=="__main__":
    app = main()
    uvicorn.run(app, port=8000, host='0.0.0.0', reload=True)
