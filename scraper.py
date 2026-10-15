# Save this file as: scraper.py
import os
import re
import time
import requests
import pandas as pd

NICHES = ["fitness club", "gym", "yoga studio"]
REGION = "Dubai UAE"
API_KEY = os.getenv("SERPAPI_KEY")

def find_email_via_api(business_name):
    """Asks SerpApi to find the email via quick Google snippets without opening the website."""
    # Custom query forcing Google to show us the business's public Gmail
    search_query = f'"{business_name}" {REGION} "gmail.com"'
    
    url = "https://serpapi.com"
    params = {
        "q": search_query,
        "api_key": API_KEY,
        "num": 5 # We only need the top few results to check text snippets
    }
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get("organic_results", [])
            
            for result in results:
                title = result.get("title", "")
                snippet = result.get("snippet", "")
                
                # Instantly scan the text returned by the API
                text_to_scan = f"{title} {snippet}"
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@gmail\.com', text_to_scan, re.IGNORECASE)
                if emails:
                    return list(set(emails))[0].lower() # Return the first found email
    except Exception as e:
        print(f"   ⚠️ API Search failed for {business_name}: {e}")
        
    return "N/A"

def scrape_leads(niche):
    if not API_KEY:
        print("❌ Error: SERPAPI_KEY environment variable is missing!")
        return []

    # Step 1: Get the businesses from Google Maps via API
    url = "https://serpapi.com"
    params = {
        "engine": "google_maps",
        "q": f"{niche} {REGION}",
        "type": "search",
        "api_key": API_KEY
    }
    
    leads = []
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            results = data.get("local_results", [])
            
            for result in results:
                title = result.get("title", "")
                print(f"📍 Maps Found: {title}")
                
                # Step 2: Use Google Search API to find the email instantly
                email = find_email_via_api(title)
                
                if email != "N/A":
                    leads.append({
                        "Coach Name": title,
                        "Niche": niche,
                        "Email Address": email
                    })
                    print(f"  ✅ Email Found via API: {email}")
                
                time.sleep(1) # Small delay to respect API limits
    except Exception as e:
        print(f"❌ Error fetching Maps data: {e}")
        
    return leads

def main():
    all_leads = []
    print("🚀 Starting Ultra-Fast API-Only Lead Scraper...")
    
    for niche in NICHES:
        print(f"\n🔍 Querying: {niche}...")
        niche_leads = scrape_leads(niche)
        all_leads.extend(niche_leads)
        
    output_file = "playwright_uae_coaches.csv"
    target_columns = ["Coach Name", "Niche", "Email Address"]
    
    if all_leads:
        df = pd.DataFrame(all_leads)
        df = df.drop_duplicates(subset=["Email Address"])
        df = df[target_columns]
        df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"\n🎉 Done! Saved {len(df)} leads.")
    else:
        df = pd.DataFrame(columns=target_columns)
        df.to_csv(output_file, index=False, encoding='utf-8')
        print("\n⚠️ No emails found. Empty placeholder created.")

if __name__ == "__main__":
    main()
