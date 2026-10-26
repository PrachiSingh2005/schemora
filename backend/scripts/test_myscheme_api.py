import httpx
import json

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/html, */*',
    'Referer': 'https://www.myscheme.gov.in/'
}

urls = [
    'https://api.myscheme.gov.in/search/v4/schemes?lang=en&q=&pageSize=10&pageNumber=1',
    'https://api.myscheme.gov.in/search/v3/schemes?lang=en&q=&pageSize=10&pageNumber=1',
    'https://www.myscheme.gov.in/sitemap.xml',
    'https://www.myscheme.gov.in/sitemap-0.xml',
    'https://cdn.myscheme.in/json/schemes.json'
]

for url in urls:
    try:
        resp = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
        print(url, "-> Status:", resp.status_code, "Length:", len(resp.content))
        if resp.status_code == 200:
            print("Snippet:", resp.text[:200])
    except Exception as e:
        print(url, "-> Error:", e)
