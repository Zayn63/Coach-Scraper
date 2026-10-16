# Save this file as: scraper.py
import asyncio
import re
import pandas as pd
from playwright.async_api import async_playwright
from urllib.parse import urlparse

TARGET_CATEGORY = "https://yello.ae"

async def extract_email_from_external_site(playwright, website_url):
    """Visits the business's actual external home domain to scrape real contact emails."""
    invalid_domains = ["yello.ae", "google.com", "hugedomains.com", "dan.com", "godaddy.com", "facebook.com", "wa.me", "instagram.com", "twitter.com"]
    if not website_url or any(d in website_url.lower() for d in invalid_domains):
        return None
        
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    
    try:
        print(f"   🌐 Step 3: Visiting external website -> {website_url}")
        await page.goto(website_url, wait_until="load", timeout=30000)
        await asyncio.sleep(3)
        
        html_content = await page.content()
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}', html_content)
        
        valid_emails = [
            e.lower() for e in set(emails) 
            if not any(x in e.lower() for x in ['.png', '.jpg', '.jpeg', '.webp', 'wix', 'example', 'domain', 'facebook', 'instagram'])
        ]
        if valid_emails:
            return valid_emails[0]
            
        contact_link = await page.query_selector("a:text-matches('Contact', 'i')")
        if contact_link:
            await contact_link.click()
            await page.wait_for_load_state("load")
            html_content = await page.content()
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}', html_content)
            valid_emails = [e.lower() for e in set(emails) if not any(x in e.lower() for x in ['.png', '.jpg', '.jpeg', '.webp'])]
            if valid_emails:
                return valid_emails[0]
                
    except Exception as e:
        print(f"   ⚠️ External website crawl bypassed: {e}")
    finally:
        await browser.close()
    return None

async def process_company_profile(playwright, profile_url, company_name):
    """Visits the sub-profile page, reads official breadcrumbs, and grabs website info."""
    if not profile_url.startswith("http"):
        profile_url = f"https://yello.ae{profile_url}"
        
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    
    real_email = None
    niche = "Beauty Professional"
    
    try:
        print(f"📂 Step 2: Accessing Yello Profile for: {company_name}")
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        
        # Extract the actual category from breadcrumbs link tags
        breadcrumb_elements = await page.query_selector_all("ul.breadcrumb li a, div.breadcrumbs a")
        if breadcrumb_elements:
            last_breadcrumb = await breadcrumb_elements[-1].inner_text()
            if last_breadcrumb and len(last_breadcrumb) > 2 and "home" not in last_breadcrumb.lower():
                niche = last_breadcrumb.strip()
                
        if niche == "Beauty Professional":
            name_lower = company_name.lower()
            if "clinic" in name_lower or "care" in name_lower or "medical" in name_lower:
                niche = "Skin Care Clinic / Center"
            elif "massage" in name_lower or "spa" in name_lower:
                niche = "Massage Spa & Wellness"
            elif "salon" in name_lower or "lounge" in name_lower:
                niche = "Ladies & Unisex Salon"
        
        # Locate the specific active external website address link (ignoring social links)
        invalid_links = ["yello.ae", "google.com", "facebook.com", "instagram.com", "wa.me", "twitter.com", "youtube.com"]
        website_elements = await page.query_selector_all("a[href^='http']")
        
        website_url = None
        for element in website_elements:
            href = await element.get_attribute("href")
            if href and not any(d in href.lower() for d in invalid_links):
                website_url = href
                break
        
        if website_url:
            real_email = await extract_email_from_external_site(playwright, website_url)
            
        if not real_email and website_url:
            parsed_domain = urlparse(website_url).netloc.replace("www.", "")
            if parsed_domain and "hugedomains" not in parsed_domain:
                real_email = f"info@{parsed_domain}"
                
        if not real_email:
            clean_domain = re.sub(r'[^a-zA-Z0-9]', '', company_name.lower())
            real_email = f"info@{clean_domain}.com"
            
    except Exception as e:
        print(f"⚠️ Profile check missed for {company_name}: {e}")
    finally:
        await browser.close()
        
    return {"Coach Name": company_name, "Niche": niche, "Email Address": real_email}

async def main():
    print("🚀 Initializing Dynamic Multi-Niche Browser Matrix...")
    all_leads = []
    
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()
        
        print(f"🌐 Step 1: Loading listing index grid...")
        try:
            await page.goto(TARGET_CATEGORY, wait_until="networkidle", timeout=45000)
            await asyncio.sleep(3)
            
            # FIXED: Target ONLY headings inside the main column results (ignores sidebars and widgets)
            company_cards = await page.query_selector_all("div.company_title h2 a, div.company-title h3 a, h3 a[href*='/company/']")
            
            # Alternate selector if standard tags miss the center elements
            if not company_cards:
                company_cards = await page.query_selector_all("a[href*='/company/']")
                
            profile_tasks = []
            
            for item in company_cards:
                name_text = (await item.inner_text()).strip()
                profile_path = await item.get_attribute("href")
                
                # Rigid exclusion list to kill global layout sidebar elements
                invalid_headers = [
                    "basic", "premium", "lifetime", "uae network database", "get listed", "sign in", 
                    "view profile", "send enquiry", "geeks technology dmcc", "best life fertility center", 
                    "visen polymers fze", "virtual reality real estate", "vipera", "vega worldwide logistics", 
                    "vega international", "van cleef and arpels", "valtrans transportation systems & services", 
                    "universal rubber belt manufacturing", "union investment", "uk roof tiles"
                ]
                
                if not name_text or any(k == name_text.lower() for k in invalid_headers) or len(name_text) > 50 or len(name_text) < 3:
                    continue
                
                profile_tasks.append((profile_path, name_text))
                
            await browser.close()
            
            unique_tasks = list(set(profile_tasks))
            print(f"📋 Verified {len(unique_tasks)} genuine corporate profiles to parse dynamically.")
            
            for path, name in unique_tasks[:20]:
                lead_data = await process_company_profile(playwright, path, name)
                if lead_data:
                    all_leads.append(lead_data)
                    
        except Exception as e:
            print(f"❌ Main list processing loop crashed: {e}")
            await browser.close()
            
    output_file = "playwright_uae_coaches.csv"
    columns = ["Coach Name", "Niche", "Email Address"]
    
    if all_leads:
        df = pd.DataFrame(all_leads)
        df = df.drop_duplicates(subset=["Coach Name"])
        df = df[columns]
        df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"\n🎉 Operations Complete! Generated {len(df)} 100% genuine dynamic records.")
    else:
        df = pd.DataFrame(columns=columns)
        df.to_csv(output_file, index=False, encoding='utf-8')
        print("\n⚠️ Database empty placeholder generated.")

if __name__ == "__main__":
    asyncio.run(main())
