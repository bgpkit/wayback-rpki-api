import json
import os
import datetime
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response
from supabase import create_client, Client
from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

BASEURL = "https://api.roas.bgpkit.com/"

description = """

*BGPKIT RPKI ROAs API provides lookup service for historical RPKI ROAs mapping
with daily granularity.*

### Data Update Frequency and Limitation

The backend fetches the recent RPKI ROAs data every 2 hours.

### Data Limitation and API Terms of Use

The source data may contain missing content in certain dates, this API should be treated as informational only and use 
with caution.

This data API is provided as a public API. If using this data, you need to agree with the BGPKIT LLC's 
Acceptable Use Agreement for public data APIs: https://bgpkit.com/aua

### Data Source and Attribution

The API is built using RIPE NCC's daily RPKI ROAs (VRP) dumps available at https://ftp.ripe.net/rpki/. 
If using this data, please attribute the original source.

<img src="https://www.ripe.net/about-us/press-centre/ripe-ncc-logos/ripe-ncc-logo-png" alt="drawing" width="200"/>

### About BGPKIT

BGPKIT team develops and maintains a number of open-source BGP data analysis tools, available at GitHub (<https://github.com/bgpkit>). 

If you find this data adds value to your workflow and would like to support our long-term development and 
maintenance of the software and data APIs, please consider sponsor us on GitHub at <https://github.com/sponsors/bgpkit>.
"""

app = FastAPI(
    title="BGPKIT RPKI ROAs History Lookup",
    description=description,
    version="0.1.0",
    terms_of_service="https://bgpkit.com/aua",
    contact={
        "name": "Contact",
        "url": "https://bgpkit.com",
        "email": "data@bgpkit.com"
    },
    docs_url=None,
    redoc_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Entry(BaseModel):
    tal: str
    prefix: str
    max_len: int
    asn: int
    date_ranges: List[List[str]]


class Result(BaseModel):
    limit: int
    count: int
    next_page_num: Optional[int]
    next_page: Optional[str]
    error: Optional[str]
    data: List[Entry]


class FileEntry(BaseModel):
    url: str
    tal: str
    file_date: str
    rows_count: int


class FilesResult(BaseModel):
    count: int
    data: List[FileEntry]


@app.get("/files", response_model=FilesResult, include_in_schema=False)
async def files(request: Request, tal: str = "", pretty: bool = False):
    """
    ### Files Lookup Query
    """
    res = supabase.rpc(
        'query_file',
        {'tal': tal}
    )
    data = res.json()
    res = {"count": len(data), "data": data}
    if pretty:
        data_res = json.dumps(res, indent=4)
    else:
        data_res = json.dumps(res)

    return Response(data_res, media_type="application/json")


@app.get("/lookup", response_model=Result, response_description="The found ROA entry", )
async def lookup(request: Request, prefix: str = "", asn: int = -1, tal: str = "", date: str = "", max_len: int = -1,
                 limit: int = 100,
                 page: int = 1, pretty: bool = False):
    """
    ### ROAs Lookup Query

    The `/lookup` endpoint has the following available parameters:
    - `prefix`: IP prefix to search ROAs for, e.g. `?prefix=1.1.1.0/24`
        - **NOTE**: only valid prefix match will be returned, i.e. the prefix must be contained within (or equals to) a
        prefix of a ROA entry and the length of the prefix must be equal or smaller than the max_length specified by the
        ROA.
    - `asn`: Autonomous System Number to search ROAs for, e.g. `?asn=15169`
    - `tal`: trust anchor locator (TAL), currently available ones are: `apnic`, `afrinic`, `lacnic`, `ripencc`, `arin`
    - `date`: limit the date of the ROAs, format: `YYYY-MM-DD`, e.g. `?date=2022-01-01`
    - `max_len`: filter results by the max_len value, e.g. `?max_len=24`
    - `limit`: limit the number of entries returns from the API. Default is `100`, and the backend support maximum of `10000` as the limit.
        - note: the maximum number of entries per ASN is around 4000.
    - `page`: the results are paginated, you can specify page number with `page` parameter, value starting from 1.
    - `pretty`: if true, the API returns prettified JSON objects, default is `false`. Example: `?pretty=true`.

    ### Response

    Each API response contains a few top-level data fields:
    - `limit`: the configured max number of entries per response
        - default: 100
        - maximum: 10000
    - `count`: the number of entries returned from the API call
    - `next_page_num`: the next page number
    - `next_page`: the **API URL** for accessing the next page of the entries
    - `data`: the content of the lookup results

    The `data` field contains a number of ROA history entries, each has the following fields:
    - `prefix`: IP prefix.
    - `asn`: Autonomous System Number.
    - `tal`: trust anchor locator (TAL).
    - `date_ranges`: The date ranges for which the validated ROA payload (VRP) was present, formatted as an array of
    two-value string arrays`[[YYYY-MM-DD,YYYY-MM-DD]]`
        - the first date is the beginning of the range, and the second date is the end of the range, both inclusive.

    ### Example query

    https://api.roas.bgpkit.com/lookup?prefix=8.8.8.0/24

    ```
    {
        "limit": 100,
        "count": 1,
        "next_page": null,
        "data": [
            {
                "prefix": "8.8.8.0/24",
                "asn": 15169,
                "max_len": "24",
                "date_ranges": [
                    [
                        "2021-02-09",
                        "2022-01-26"
                    ]
                ],
                "tal": "arin"
            }
        ],
        "error": null
    }
    ```
    This entry can be interpreted as:
    The prefix 8.8.8.0/24 is registered by AS 15169 in ARIN, and the registration is
    valid starting from 2021-02-09 to 2022-01-24. The end date is inclusive, ie. this is the last time
    this validated ROA payload (VRP) was seen.
    """

    # parameter validations
    if page < 1:
        res = {"limit": limit, "count": 0, "next_page": None, "next_page_num": None, "data": [],
               "error": "parameters validation failed: page>=1"}
        return Response(json.dumps(res), media_type="application/json", status_code=400)
    offset = (page - 1) * limit

    res = supabase.rpc(
        'query_history_2',
        {'prefix': prefix, 'asn': asn, "nic": tal, "res_limit": limit, "date": date, 'max_len': max_len,
         "res_offset": offset}
    )
    data = res.json()

    # check for error
    if 'message' in data:
        res = {"limit": limit, "count": 0, "next_page": None, "next_page_num": None, "data": [],
               "error": data['message']}
        return Response(json.dumps(res), media_type="application/json", status_code=400)

    new_data = []
    for entry in data:

        # update ranges
        ranges = entry.pop('date_ranges')
        new_ranges = []
        for date_range in ranges:
            new_ranges.append(range_to_array(date_range))
        entry['date_ranges'] = new_ranges

        new_data.append(entry)

    length = len(data)

    new_url = None
    next_page_num = None
    if length >= limit:
        new_url = BASEURL.rstrip("/") + "/lookup?"
        params = []
        if prefix != '':
            params.append(f"prefix={prefix}")
        if asn >= 0:
            params.append(f"asn={asn}")
        if tal != '':
            params.append(f"tal={tal}")
        if limit > 0:
            params.append(f"limit={limit}")
        if date != '':
            params.append(f"date={date}")
        if max_len >= 0:
            params.append(f"max_len={max_len}")
        if page > 0:
            params.append(f"page={page + 1}")
            next_page_num = page + 1
        new_url += "&".join(params)

    res = {"limit": limit, "count": length, "next_page_num": next_page_num, "next_page": new_url, "data": new_data,
           "error": None}
    if pretty:
        data_res = json.dumps(res, indent=4)
    else:
        data_res = json.dumps(res)

    return Response(data_res, media_type="application/json")


def range_to_array(date_range: str):
    start_exclusive = False
    end_exclusive = False
    if date_range[0] == '(':
        start_exclusive = True
    if date_range[-1] == ')':
        end_exclusive = True
    start, end = date_range.lstrip("[(").rstrip("])").split(",")
    if start_exclusive:
        start = (datetime.datetime.strptime(start, '%Y-%M-%d') + datetime.timedelta(days=1)).strftime('%Y-%M-%d')
    if end_exclusive:
        end = (datetime.datetime.strptime(end, '%Y-%M-%d') - datetime.timedelta(days=1)).strftime('%Y-%M-%d')
    return [start, end]
