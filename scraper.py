# Save this file as: scraper.py
import os
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

# The categories you want to target on Google Maps
NICHES = [
    "fitness club",
    "gym",
    "yoga studio",
    "fitness trainer center"
]
REGION = "Dubai UAE"
API_KEY = os.getenv("SERPAPI_KEY")

def extract_email_from_website(url):
    """Visits the business website and searches for a Gmail address."""
    if not url or url == "N/A" or not url.startswith("http"):
        return "N/A"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # Visit the website homepage
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            page_text = soup.get_text()
            
            # Look for standard Gmail formats anywhere on the page
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@gmail\.com', page_text, re.IGNORECASE)
            if emails:
                return list(set(emails))[0].lower() # Return the first unique gmail found
                
            # Fallback: Look inside mailto links in the footer/buttons
            for link in soup.find_all('a', href=True):
                href = link['href']
                if "mailto:" in href and "gmail.com" in href:
                    clean_email = href.replace("mailto:", "").split("?")[0].strip()
                    return clean_email.lower()
                    
    except Exception as e:
        print(f"   ⚠️ Could not crawl website {url}: {e}")
        
    return "N/A"

def scrape_maps_and_websites(niche):
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
    
    leads = []
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            results = data.get("local_results", [])
            
            for result in results:
                title = result.get("title", "")
                website = result.get("website", "N/A")
                
                print(f"📍 Found: {title} | Website: {website}")
                
                # Step 2: If they have a website, visit it to find their email
                email = "N/A"
                if website != "N/A":
                    print(f"  🔗 Crawling website for emails...")
                    email = extract_email_from_website(website)
                
                # Only save the lead if we actually managed to find a Gmail address
                if email != "N/A":
                    leads.append({
                        "Coach Name": title,
                        "Niche": niche,
                        "Email Address": email
                    })
                    print(f"  ✅ Found Email: {email}")
        else:
            print(f"⚠️ Maps API Error for {niche}: HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Network issue while parsing Maps data: {e}")
        
    return leads

def main():
    all_leads = []
    print("🚀 Starting 2-Step Maps & Website Lead Scraper...")
    
    for niche in NICHES:
        print(f"\n🗺️ Searching Google Maps for: {niche}...")
        niche_leads = scrape_maps_and_websites(niche)
        all_leads.extend(niche_leads)
        print(f"✅ Extracted {len(niche_leads)} leads with verified emails for [{niche}].")
        
    output_file = "playwright_uae_coaches.csv"
    target_columns = ["Coach Name", "Niche", "Email Address"]
    
    if all_leads:
        df = pd.DataFrame(all_leads)
        df = df.drop_duplicates(subset=["Email Address"])
        df = df[target_columns]
        df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"\n🎉 Success! Database populated with {len(df)} live leads.")
    else:
        df = pd.DataFrame(columns=target_columns)
        df.to_csv(output_file, index=False, encoding='utf-8')
        print("\n⚠️ Zero emails found on the websites. Spreadsheet placeholder created.")

if __name__ == "__main__":
    main()
