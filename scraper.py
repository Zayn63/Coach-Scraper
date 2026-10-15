# Save this file as: scraper.py
import asyncio
import re
import urllib.parse
import pandas as pd
from playwright.async_api import async_playwright

NICHES = ["fitness coach", "yoga instructor", "relationship coach", "business coach", "life coach"]
REGION = "United Arab Emirates"

async def scrape_niche_leads(playwright, niche):
    # Launch browser headlessly for the cloud
    browser = await playwright.chromium.launch(headless=True)
    
    # Cloud Optimization: Inject realistic human browser properties
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720},
        locale="en-US"
    )
    page = await context.new_page()
    
    # We target LinkedIn's public directory directly using Google's search format via URL
    # This tricks the system into treating us like an organic visitor
    search_query = f'site:://linkedin.com "{niche}" "{REGION}" "gmail.com"'
    target_url = f"https://google.com{urllib.parse.quote_plus(search_query)}&num=20"
    
    print(f"🔍 Cloud Scraper accessing internet for: {niche}...")
    
    try:
        # Navigate and wait until the network slows down
        await page.goto(target_url, wait_until="networkidle", timeout=30000)
        # Give JavaScript an extra 3 seconds to fully settle
        await asyncio.sleep(3)
    except Exception as e:
        print(f"⚠️ Page load timeout for {niche}: {e}")
        await browser.close()
        return []

    leads = []
    
    # Select all standard web content snippets loaded on the page
    search_results = await page.query_selector_all("div.g, div[data-ved]")
    
    for result in search_results:
        try:
            text_content = await result.inner_text()
            if not text_content:
                continue
                
            link_element = await result.query_selector("a")
            link = await link_element.get_attribute("href") if link_element else "N/A"
            
            # Scan the dynamic text block for public Gmail records
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@gmail\.com', text_content, re.IGNORECASE)
            unique_emails = list(set(emails))
            
            for email in unique_emails:
                leads.append({
                    "Niche Name": niche,
                    "Email Address": email.lower(),
                    "Website Link": link
                })
        except Exception:
            continue
            
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
                # Polite human delay between structural requests
                await asyncio.sleep(5)
            except Exception as e:
                print(f"❌ Error while running {niche}: {e}")
                
    # CRUCIAL FIX: Ensure a file is ALWAYS created so GitHub Actions never crashes
    output_file = "playwright_uae_coaches.csv"
    
    if all_leads:
        df = pd.DataFrame(all_leads)
        df = df.drop_duplicates(subset=["Email Address"])
        df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"\n🎉 File successfully saved to cloud with {len(df)} records!")
    else:
        # If GitHub is blocked, we still generate a clean file to stop Git crashing
        df = pd.DataFrame(columns=["Niche Name", "Email Address", "Website Link"])
        df.to_csv(output_file, index=False, encoding='utf-8')
        print("\n⚠️ No emails could be harvested during this run. Created empty spreadsheet placeholder.")

if __name__ == "__main__":
    asyncio.run(main())
