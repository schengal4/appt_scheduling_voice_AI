API_KEY ="aecea717-2089-43e8-a9e4-20d6ae2a16e5"
## Not ready to commit to GitHub
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


import asyncio
from vapi import AsyncVapi

PHONE_NUMBER_ID = "10eb3b86-9cf4-44e2-b606-1e7c8605f928"
ASSISTANT_ID = "c7c9d185-4155-4293-84fe-d99cad75a02f"

app = FastAPI()
