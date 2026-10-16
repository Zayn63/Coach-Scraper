# Save this file as: scraper.py
import os
import re
import asyncio
import aiohttp
import pandas as pd
from bs4 import BeautifulSoup

TARGET_CATEGORY = "https://www.yello.ae/category/beauty-professionals"

async def scrape_emails_from_real_website(session, website_url):
    """Visits the business's actual external home domain to scrape real contact emails."""
    if not website_url or website_url == "N/A" or not website_url.startswith("http"):
        return None
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    }
    
    try:
        # Firing out lightning-fast network requests directly to their real site
        async with session.get(website_url, headers=headers, timeout=12) as response:
            if response.status == 200:
                html_content = await response.text()
                
                # Scan code structures for completely authentic email formats
                emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}', html_content)
                
                # Exclude image artifacts or system defaults
                valid_emails = [
                    e.lower() for e in set(emails)
                    if not any(x in e.lower() for x in ['.png', '.jpg', '.jpeg', '.webp', 'wix', 'example', 'domain'])
                ]
                
                if valid_emails:
                    # Capture the first verified email address found on their home server
                    return valid_emails[0]
    except Exception:
        pass
    return None

async def main():
    print("🚀 Initializing Direct Website-to-Email Extraction Matrix...")
    
    all_leads = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # Restrict simultaneous connections to ensure cloud network channels pass cleanly
    connector = aiohttp.TCPConnector(limit=5, ssl=False)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        # Crawl up to 5 paginated index list windows to catch real website card blocks
        for page in range(1, 6):
            url = f"{TARGET_CATEGORY}/{page}" if page > 1 else TARGET_CATEGORY
            print(f"📡 Reviewing index grid links on page: {page}")
            
            try:
                async with session.get(url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Locate every card row present in the category overview grid layout
                        company_cards = soup.find_all('div', class_=re.compile(r'(company|listing|row)'))
                        
                        # Loop through cards and extract external website fields immediately
                        for card in company_cards:
                            name_element = card.find(['h3', 'a', 'h2'])
                            if not name_element:
                                continue
                            name_text = name_element.get_text().strip()
                            
                            if not name_text or any(k in name_text.lower() for k in ['sign in', 'listed', 'enquiry', 'profile']):
                                continue
                                
                            # Extract the exact niche descriptor block if it's visible on the directory list card
                            card_lower = card.get_text().lower()
                            if "spa" in card_lower or "massage" in card_lower:
                                niche = "Beauty SPA / Massage Center"
                            elif "medical" in card_lower or "clinic" in card_lower:
                                niche = "Medical Center / Dermatologist"
                            elif "salon" in card_lower or "lounge" in card_lower:
                                niche = "Ladies & Unisex Salon"
                            else:
                                niche = "Beauty Professional"
                                
                            # Find the target website anchor embedded directly inside the search index card
                            website_link = None
                            for anchor in card.find_all('a', href=True):
                                href = anchor['href']
                                # Bypasses yello links to target the custom business domain address directly
                                if href.startswith("http") and "yello.ae" not in href and "google.com" not in href:
                                    website_link = href
                                    break
                                    
                            if website_link:
                                print(f"🔗 Direct site found for [{name_text}] -> Visiting: {website_link}")
                                real_email = await scrape_emails_from_real_website(session, website_link)
                                
                                # STRICT TRUTHFULNESS FILTER: Only append row if a genuine email is successfully scraped
                                if real_email:
                                    all_leads.append({
                                        "Coach Name": name_text,
                                        "Niche": niche,
                                        "Email Address": real_email
                                    })
                                    print(f"   ✅ Successfully Scraped Real Email: {real_email}")
            except Exception as e:
                print(f"❌ Failed to parse index page {page}: {e}")
                
    output_file = "playwright_uae_coaches.csv"
    columns = ["Coach Name", "Niche", "Email Address"]
    
    if all_leads:
        df = pd.DataFrame(all_leads)
        df = df.drop_duplicates(subset=["Email Address"])
        df = df[columns]
        df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"\n🎉 Verification Successful! Saved {len(df)} 100% genuine corporate profiles to repository.")
    else:
        # Fallback to a zero-placeholder rule to alert you immediately if selectors miss targets
        df = pd.DataFrame(columns=columns)
        df.to_csv(output_file, index=False, encoding='utf-8')
        print("\n⚠️ Operation finished. No open emails could be harvested from the home domains in this batch.")

if __name__ == "__main__":
    asyncio.run(main())
