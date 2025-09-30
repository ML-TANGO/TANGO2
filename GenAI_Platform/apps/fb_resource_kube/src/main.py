from fastapi import FastAPI
from node.route import nodes
# from pod.route import pod
# from gpu.route import gpu
# from option.route import options
# from network.route import networks
from storage.route import storage
from records.route import records

from utils.resource import CustomResponse
from utils.resource import CustomMiddleWare
# from utils.scheduler_init import initialize_scheduler


# from node.service_instance import init_node_instance

def initialize_app():
    app = FastAPI()
    api = FastAPI(
        title="JFB API",
        version='0.1',
        default_response_class=CustomResponse,
        middleware=CustomMiddleWare,
        openapi_url="/resources/openapi.json",
        docs_url="/resources/docs",
        redoc_url="/resources/redoc"
    )

    api.include_router(nodes, tags=["nodes"])
    # api.include_router(pod, tags=["pod"])
    # api.include_router(gpu, tags=["gpu"])
    # api.include_router(options, tags=["options"])
    # api.include_router(networks, tags=["networks"])
    api.include_router(storage, tags=["storage"])
    api.include_router(records, tags=["records"] )

    app.mount('/api', api)
    return app

def main():
    app = initialize_app()
    # initialize_scheduler()
    # init_node_instance()
    return app

if __name__=="__main__":
    main()
    uvicorn.run("main:app", port=8000, host='0.0.0.0', reload=True)
