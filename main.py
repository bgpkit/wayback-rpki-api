import os
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel
from starlette.responses import RedirectResponse
from supabase import create_client, Client
from fastapi import FastAPI

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

description = """
BGPKIT RPKI ROAs API provides lookup service for historical RPKI ROAs mapping
with daily granularity.

### Data Source

The API is built with RIPE's daily RPKI ROAs dumps available at <https://ftp.ripe.net/rpki/>.

### API Endpoints

There is one endpoint for this API (`/lookup`). See the endpoint documentation below for details.
"""

app = FastAPI(
    title="BGPKIT RPKI ROAs History Lookup",
    description=description,
    version="0.0.1",
    terms_of_service="https://bgpkit.com/aua",
    contact={
        "name": "BGPKIT Data",
        "url": "https://bgpkit.com",
        "email": "data@bgpkit.com"
    },
    docs_url=None,
    redoc_url="/docs",
)


class Entry(BaseModel):
    nic: str
    prefix: str
    max_len_prefix: str
    asn: int
    date_ranges: List[str]


class Result(BaseModel):
    limit: int
    count: int
    data: List[Entry]


@app.get(
    "/lookup",
    response_model=Result,
    response_description="The found ROA entry",
)
async def lookup(prefix: str = "", asn: int = -1, nic: str = "", date: str = "", limit: int = 100):
    """
    The `/lookup` endpoint has the following available parameters:
    - `prefix`: IP prefix to search ROAs for, e.g. `?prefix=1.1.1.0/24`
        - **NOTE**: only valid prefix match will be returned, i.e. the prefix must be contained within (or equals to) a
        prefix of a ROA entry and the length of the prefix must be equal or smaller than the max_length specified by the
        ROA.
    - `asn`: Autonomous System Number to search ROAs for, e.g. `?asn=15169`
    - `nic`: network information centre names, available ones: `apnic`, `afrinic`, `lacnic`, `ripencc`, `arin`
    - `date`: limit the date of the ROAs, format: `YYYY-MM-DD`, e.g. `?date=2022-01-01`
    - `limit`: limit the number of entries returns from the API. Default is `100`, and the backend support maximum of `10000` as the limit.
        - the maximum number of entries per ASN is around 4000.

    The API returns a list of ROA history entries, each has the following fields:
    - `prefix`: IP prefix.
    - `asn`: Autonomous System Number.
    - `nic`: Network information centre name.
    - `date_ranges`: The date ranges for which the ROA was present, formatted as an array of strings `[YYYY-MM-DD,YYYY-MM-DD)`
        - the first date is the beginning of the range (inclusive) and the second date is the end of the range (exclusive).

    Example data entry:
    ```
    {
      "limit": 100,
      "count": 1,
      "data": [
        {
          "nic": "arin",
          "prefix": "8.8.8.0/24",
          "max_len_prefix": "8.8.8.0/24",
          "asn": 15169,
          "date_ranges": [
            "[2021-02-09,2022-01-24)"
          ]
        }
      ]
    }
    ```
    This entry can be interpreted as:
    The prefix `8.8.8.0/24` is registered by AS `15169` in `ARIN`, and the
    registration is valid starting from `2021-02-09` to `2022-01-24` (exclusive).
    """

    res = supabase.rpc(
        'query_history',
        {'prefix': prefix, 'asn': asn, "nic": nic, "res_limit": limit, "date": date}
    )
    data = res.json()
    length = len(data)
    return {"limit": limit, "count": length, "data": res.json()}


@app.get("/")
async def root_redirect_to_docs():
    """
    Redirect access to `/` to `/docs`.
    """
    return RedirectResponse("/docs")
