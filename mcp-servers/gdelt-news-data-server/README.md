# GDELT News Data Server

Serves general news from the public [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/).
It needs no API key.

## Tools

### get_gdelt_news

Takes `query`, `start_date` and `end_date` (inclusive New York dates) and returns up to 50 English articles GDELT
first saw in that range, newest first, with title, source domain, date and URL.

## Study dataset capture

For the frozen study dataset ([spec 006](../../specs/006-time-cut-dataset/spec.md)), `capture.py fetch` requests,
for each candidate date, the 7 days ending at its cutoff for the ticker pool and the shared macro pool, 20 seconds
apart. `capture.py normalize` drops articles first seen after the cutoff and duplicate URLs.
