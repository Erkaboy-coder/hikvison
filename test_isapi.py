import requests
from requests.auth import HTTPDigestAuth

xml = """<?xml version="1.0" encoding="UTF-8"?>
<CMSearchDescription version="1.0" xmlns="http://www.hikvision.com/ver10/XMLSchema">
  <searchID>1</searchID>
  <trackIDList><trackID>101</trackID></trackIDList>
  <timeSpanList>
    <timeSpan>
      <startTime>2026-05-20T00:00:00+05:00</startTime>
      <endTime>2026-05-20T23:59:59+05:00</endTime>
    </timeSpan>
  </timeSpanList>
  <maxResults>5</maxResults>
  <searchResultPosition>0</searchResultPosition>
  <metadataList>
    <metadataDescriptor>//recordType.meta.std-cgi.com/LogInfo/FaceRecognition</metadataDescriptor>
  </metadataList>
</CMSearchDescription>"""

r = requests.post('http://10.234.0.8/ISAPI/ContentMgmt/logSearch', auth=HTTPDigestAuth('admin', 'Z12345678r'), data=xml, headers={'Content-Type': 'application/xml'}, timeout=10)
print(r.status_code)
print(r.text[:500])
