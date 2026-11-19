# GDELT News Data Server

Captures general news from the public [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)
for the frozen study dataset ([spec 006](../../specs/006-time-cut-dataset/spec.md)). It needs no API key.

`capture.py fetch` requests, for each candidate date, the 7 days ending at its cutoff for the ticker pool and the
shared macro pool, 20 seconds apart. `capture.py normalize` drops articles first seen after the cutoff and
duplicate URLs. The MCP tool that serves the frozen copy arrives in PR 9 and replaces DuckDuckGo.
