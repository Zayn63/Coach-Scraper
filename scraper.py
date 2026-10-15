# Save this file as: scraper.py
import os
import re
import requests
import pandas as pd

NICHES = [
    "fitness coach",
    "yoga instructor",
    "relationship coach",
    "business coach",
    "life coach"
]
REGION = "United Arab Emirates"

API_KEY = os.getenv("SERPAPI_KEY")

def clean_coach_name(title):
    # Splits the web title at common separators like "-", "|", or "•" 
    # and takes the first part, which usually contains the person's real name.
    first_part = re.split(r'[-|•]', title)[0]
    # Clean up trailing spaces or brackets
    clean_name = first_part.strip()
    return clean_name if clean_name else "Unknown Coach"

def scrape_niche_leads(niche):
    if not API_KEY:
        print("❌ Error: SERPAPI_KEY environment variable is missing!")
        return []

    search_query = f'{niche} {REGION} "gmail.com"'
    
    url = "https://serpapi.com"
    params = {
        "q": search_query,
        "api_key": API_KEY,
        "num": 30,
        "google_domain": "google.ae",
        "hl": "en",
        "gl": "ae"
    }
    
    leads = []
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            results = data.get("organic_results", [])
            
            for result in map(dict, results):
                title = str(result.get("title", ""))
                snippet = str(result.get("snippet", ""))
                
                text_to_scan = f"{title} {snippet}"
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@gmail\.com', text_to_scan, re.IGNORECASE)
                unique_emails = list(set(emails))
                
                # Extract and format the coach's name cleanly
                coach_name = clean_coach_name(title)
                
                for email in unique_emails:
                    leads.append({
                        "Coach Name": coach_name,
                        "Niche": niche,
                        "Email Address": email.lower()
                    })
        else:
            print(f"⚠️ API Error for {niche}: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Network issue while processing {niche}: {e}")
        
    return leads

def main():
    all_leads = []
    print("🚀 Initializing Clean Format UAE Cloud Lead Scraper...")
    
    for niche in NICHES:
        print(f"🔍 Fetching regional data for: {niche}...")
        niche_leads = scrape_niche_leads(niche)
        all_leads.extend(niche_leads)
        print(f"✅ Parsed {len(niche_leads)} leads for [{niche}].")
        
    output_file = "playwright_uae_coaches.csv"
    
    # Specific layout columns requested: Coach Name, Niche, Email Address
    target_columns = ["Coach Name", "Niche", "Email Address"]
    
    if all_leads:
        df = pd.DataFrame(all_leads)
        df = df.drop_duplicates(subset=["Email Address"])
        # Ensure correct column order
        df = df[target_columns]
        df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"\n🎉 File successfully saved with {len(df)} unique records.")
    else:
        df = pd.DataFrame(columns=target_columns)
        df.to_csv(output_file, index=False, encoding='utf-8')
        print("\n⚠️ Zero emails captured. Spreadsheet placeholder initialized.")

if __name__ == "__main__":
    main()
