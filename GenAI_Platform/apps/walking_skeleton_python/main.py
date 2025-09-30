from fastapi import FastAPI, Query, Path
from typing import Union, Final, Optional
from typing_extensions import Annotated
from pydantic import BaseModel
import os

class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None

app = FastAPI()

BASE_DIR: Final[str] = ""
ITEM_DIR: Final[str] = "items"

def get_service_id():
    return os.environ["SERVICE_ID"]

@app.get(f"{BASE_DIR}/{ITEM_DIR}")
async def simple_return():
    results = [
        {"Hello": "World"},
        {"CI": "CD"},
        {"ServiceID": get_service_id()}
    ]
    return results


@app.get(f"{BASE_DIR}/{ITEM_DIR}/{{item_id}}")
async def item_find(item_id: str):
    results = [
            {"Hello": "find "},
            {"requested": item_id}
    ]
    print(f"[JF|FB|{item_id}|Warn] Actually this is test {results}")
    return results
