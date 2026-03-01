import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        responses = []

        async def on_response(response):
            url = response.url
            if "searchanise" in url or "igroshop" in url:
                try:
                    body = await response.text()
                    if len(body) > 50:
                        responses.append((url, body[:1000]))
                except:
                    pass

        page.on("response", on_response)

        await page.set_extra_http_headers({
            "Accept-Language": "ru-RU,ru;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

        # Пробуем разные варианты URL поиска
        for search_url in [
            "https://www.igroshop.com/?q=Cyberpunk+2077",
            "https://www.igroshop.com/search/Cyberpunk+2077/",
        ]:
            try:
                await page.goto(search_url, wait_until="networkidle", timeout=15000)
                print(f"URL: {search_url} -> {page.url}")
                break
            except:
                continue

        await asyncio.sleep(3)
        await browser.close()

    print(f"\nОтветы ({len(responses)}):")
    for url, body in responses:
        print(f"\n=== {url} ===")
        print(body[:500])

asyncio.run(main())
