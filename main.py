import os
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel
from supabase import create_client, Client
from fastapi import FastAPI

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

app = FastAPI()


class Entry(BaseModel):
    nic: str
    prefix: str
    asn: int
    date_ranges: List[str]


class Result(BaseModel):
    count: int
    data: List[Entry]


@app.get("/lookup", response_model=Result)
async def lookup(prefix: str = "", asn: int = -1, nic: str = "", exact: bool = False, limit: int = 0, date: str = ""):
    res = supabase.rpc(
        'query_history',
        {'prefix': prefix, 'asn': asn, "nic": nic, "exact": exact, "res_limit": limit, "date": date}
    )
    data = res.json()
    length = len(data)
    return {"count": length, "data": res.json()}
