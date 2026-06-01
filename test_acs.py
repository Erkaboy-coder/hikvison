import requests
from requests.auth import HTTPDigestAuth
import json

if __name__ == '__main__':
    payload = {
        "AcsEventCond": {
            "searchID": "1",
            "searchResultPosition": 0,
            "maxResults": 10,
            "major": 5,
            "minor": 75,
            "startTime": "2026-05-20T00:00:00+05:00",
            "endTime": "2026-05-20T23:59:59+05:00"
        }
    }

    r = requests.post('http://10.234.0.8/ISAPI/AccessControl/AcsEvent?format=json', auth=HTTPDigestAuth('admin', 'Z12345678r'), json=payload, timeout=10)
    print(r.status_code)
    print(r.text[:500])
