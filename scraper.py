# Save this file as: scraper.py
import os
import re
import asyncio
import aiohttp
import pandas as pd

NICHES = ["fitness club", "gym", "yoga studio", "crossfit center"]
REGION = "Dubai UAE"
API_KEY = os.getenv("SERPAPI_KEY")

async def extract_emails_from_site(session, url, business_name, niche):
    """Visits a website, downloads its code instantly, and scans for public emails."""
    if not url or url == "N/A" or not url.startswith("http"):
        return None
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    try:
        # High speed async network call to fetch the page content
        async with session.get(url, headers=headers, timeout=12) as response:
            if response.status == 200:
                html_content = await response.text()
                
                # Regex search matching clean public email records anywhere in the website code
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}', html_content)
                
                # Filter to isolate general inquiries and personal addresses, removing image/web design noise
                valid_emails = [
                    e.lower() for e in set(emails) 
                    if not any(ext in e.lower() for ext in ['.png', '.jpg', '.jpeg', '.webp', 'wix', 'domain', 'example'])
                ]
                
                if valid_emails:
                    print(f"✅ Found Email for {business_name}: {valid_emails[0]}")
                    return {
                        "Coach Name": business_name,
                        "Niche": niche,
                        "Email Address": valid_emails[0],
                        "Website Link": url
                    }
    except Exception:
        # Pass quietly if a website is broken or down so the cloud scanner doesn't halt
        pass
    return None

def fetch_google_maps_businesses(niche):
    """Queries the Google Maps database to fetch target business websites."""
    if not API_KEY:
        print("❌ Error: SERPAPI_KEY environment variable is missing!")
        return []

    url = "https://serpapi.com"
    params = {
        "engine": "google_maps",
        "q": f"{niche} {REGION}",
        "type": "search",
        "api_key": API_KEY
    }
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json().get("local_results", [])
    except Exception as e:
        print(f"❌ Error talking to Google Maps API: {e}")
    return []

async def main_async():
    import requests
    all_tasks = []
    
    # Establish a shared async browser session for maximum speed
    async with aiohttp.ClientSession() as session:
        print("🚀 Pulling locations from Google Maps API...")
        
        for niche in NICHES:
            print(f"🗺️ Querying Maps list for: {niche}")
            # Import requests strictly inside the helper to fetch maps data
            import requests
            places = fetch_google_maps_businesses(niche)
            
            for place in places:
                name = place.get("title", "Unknown Business")
                website = place.get("website", "N/A")
                
                if website != "N/A":
                    # Queue up all website crawlers to execute concurrently
                    task = extract_emails_from_site(session, website, name, niche)
                    all_tasks.append(task)
                    
        print(f"⚡ Processing {len(all_tasks)} business websites simultaneously in the cloud...")
        results = await asyncio.gather(*all_tasks)
        
        # Clean out empty results where no emails were listed on pages
        clean_leads = [r for r in results if r is not None]
        
        output_file = "playwright_uae_coaches.csv"
        target_columns = ["Coach Name", "Niche", "Email Address", "Website Link"]
        
        if clean_leads:
            df = pd.DataFrame(clean_leads)
            df = df.drop_duplicates(subset=["Email Address"])
            df = df[target_columns]
            df.to_csv(output_file, index=False, encoding='utf-8')
            print(f"\n🎉 Extraction Complete! Saved {len(df)} live leads to your repository.")
        else:
            df = pd.DataFrame(columns=target_columns)
            df.to_csv(output_file, index=False, encoding='utf-8')
            print("\n⚠️ Extraction complete, but no emails were found on pages. File updated.")

if __name__ == "__main__":
    # Initialize the high-speed async processing engine loop
    asyncio.run(main_async())
