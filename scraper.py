# Save this file as: scraper.py
import asyncio
import re
import urllib.parse
import pandas as pd
from playwright.async_api import async_playwright

NICHES = ["fitness coach", "yoga instructor", "relationship coach", "business coach", "life coach"]
REGION = "United Arab Emirates"

async def scrape_niche_leads(playwright, niche):
    # Headless must be True for GitHub Actions cloud environments
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    
    search_query = f'"{niche}" "{REGION}" "gmail.com"'
    google_url = f"https://google.com{urllib.parse.quote_plus(search_query)}"
    
    print(f"🔍 Cloud Scraper navigating to: {niche}...")
    await page.goto(google_url, wait_until="networkidle")
    
    try:
        await page.wait_for_selector("#search", timeout=10000)
    except:
        print(f"⚠️ Timeout or CAPTCHA hit for {niche}. Skipping...")
        await browser.close()
        return []

    leads = []
    search_results = await page.query_selector_all("div.g")
    
    for result in search_results:
        text_content = await result.inner_text()
        link_element = await result.query_selector("a")
        link = await link_element.get_attribute("href") if link_element else "N/A"
        
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@gmail\.com', text_content, re.IGNORECASE)
        unique_emails = list(set(emails))
        
        for email in unique_emails:
            leads.append({
                "Niche Name": niche,
                "Email Address": email.lower(),
                "Website Link": link
            })
            
    await browser.close()
    return leads

async def main():
    all_leads = []
    async with async_playwright() as playwright:
        for niche in NICHES:
            try:
                niche_leads = await scrape_niche_leads(playwright, niche)
                all_leads.extend(niche_leads)
                print(f"✅ Extracted {len(niche_leads)} leads for [{niche}].")
                await asyncio.sleep(5) # Delay to respect cloud environment IP rates
            except Exception as e:
                print(f"❌ Error on {niche}: {e}")
                
    if all_leads:
        df = pd.DataFrame(all_leads)
        df = df.drop_duplicates(subset=["Email Address"])
        # Always output to the base folder so GitHub Actions can find it
        df.to_csv("playwright_uae_coaches.csv", index=False, encoding='utf-8')
        print(f"\n🎉 File successfully built in cloud storage!")
    else:
        print("\n❌ Zero leads extracted.")

if __name__ == "__main__":
    asyncio.run(main())
