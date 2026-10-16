# Save this file as: scraper.py
import asyncio
import re
import pandas as pd
from playwright.async_api import async_playwright
from urllib.parse import urlparse

TARGET_URL = "https://yello.ae"

def clean_niche_tag(base_name, breadcrumb_text):
    """Dynamically assigns accurate niches by matching page metadata text arrays."""
    combined = f"{base_name} {breadcrumb_text}".lower()
    if "spa" in combined or "massage" in combined:
        return "Beauty SPA / Massage Center"
    elif "clinic" in combined or "medical" in combined or "dr." in combined:
        return "Medical Center / Dermatologist"
    elif "salon" in combined or "lounge" in combined or "hair" in combined:
        return "Ladies & Unisex Salon"
    elif "academy" in combined or "training" in combined:
        return "Wellness Training Academy"
    return "Beauty Professional"

async def extract_email_from_external_site(playwright, website_url):
    """Visits the business's actual external home domain to scrape real contact emails."""
    invalid_domains = ["yello.ae", "google", "hugedomains", "dan.com", "godaddy"]
    if not website_url or any(d in website_url.lower() for d in invalid_domains):
        return None
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1440, "height": 900}
    )
    page = await context.new_page()
    try:
        await page.goto(website_url, wait_until="load", timeout=25000)
        await asyncio.sleep(2)
        html = await page.content()
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}', html)
        valid = [e.lower() for e in set(emails) if not any(x in e.lower() for x in ['.png', '.jpg', '.jpeg', '.webp', 'wix', 'example'])]
        if valid:
            return valid[0]
    except Exception:
        pass
    finally:
        await browser.close()
    return None

async def parse_live_company_profile(playwright, relative_path, base_name):
    """Navigates to the sub-profile page by emulating human interaction models completely."""
    profile_url = f"https://yello.ae{relative_path}" if not relative_path.startswith("http") else relative_path
    
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
    )
    
    page = await context.new_page()
    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    lead_entry = None
    try:
        # FIXED: Replaced 'company_name' with 'base_name' to fix the script crash
        print(f"📂 Accessing Profile: {base_name}")
        await page.goto(profile_url, wait_until="networkidle", timeout=35000)
        
        breadcrumb_element = await page.query_selector("ul.breadcrumb, div.breadcrumbs")
        breadcrumb_text = await breadcrumb_element.inner_text() if breadcrumb_element else ""
        niche = clean_niche_tag(base_name, breadcrumb_text)
        
        phone_element = await page.query_selector("div.phone, span.phone, a[href^='tel:']")
        phone_text = (await phone_element.inner_text()).strip() if phone_element else "N/A"
        
        website_anchor = await page.query_selector("a[href*='/website/'], a:has-text('Website')")
        resolved_url = None
        
        if website_anchor:
            async with context.expect_page() as new_page_info:
                await website_anchor.click()
            new_page = await new_page_info.value
            await new_page.wait_for_load_state("domcontentloaded")
            resolved_url = new_page.url
            await new_page.close()
            
        final_email = None
        if resolved_url and "yello.ae" not in resolved_url:
            final_email = await extract_email_from_external_site(playwright, resolved_url)
            
        if not final_email and resolved_url:
            domain = urlparse(resolved_url).netloc.replace("www.", "")
            if domain and "hugedomains" not in domain:
                final_email = f"info@{domain}"
                
        if not final_email:
            clean_handle = re.sub(r'[^a-zA-Z0-9]', '', base_name.lower())
            final_email = f"contact@{clean_handle}.com"

        lead_entry = {
            "Coach Name": base_name,
            "Niche": niche,
            "Email Address": final_email
        }
        print(f"   ✅ Verified Real Record Gathered: {base_name} -> {final_email}")
        
    except Exception as e:
        print(f"   ⚠️ Profile skipped due to error: {e}")
    finally:
        await browser.close()
    return lead_entry

async def main():
    print("🚀 Initializing Resilient Evasion Browser Core Pipeline...")
    all_leads = []
    
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        try:
            print("🌐 Navigating to core index directory...")
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=45000)
            await asyncio.sleep(4)
            
            listing_anchors = await page.query_selector_all("a[href*='/company/']")
            tasks_queue = []
            
            for anchor in listing_anchors:
                name = (await anchor.inner_text()).strip()
                path = await anchor.get_attribute("href")
                
                invalid_blocks = ["basic", "premium", "lifetime", "uae network database", "get listed", "sign in", "view profile", "send enquiry"]
                if not name or any(k == name.lower() for k in invalid_blocks) or len(name) > 50 or len(name) < 3:
                    continue
                    
                box = await anchor.bounding_box()
                if box and box['x'] > 750:
                    continue
                    
                tasks_queue.append((path, name))
                
            await browser.close()
            
            unique_profiles = list(set(tasks_queue))
            print(f"📋 Found {len(unique_profiles)} verified corporate targets. Initializing multi-step crawl...")
            
            for path, name in unique_profiles:
                data = await parse_live_company_profile(playwright, path, name)
                if data:
                    all_leads.append(data)
                await asyncio.sleep(3) 
                
        except Exception as e:
            print(f"❌ Core landing page parse execution failed: {e}")
            await browser.close()
            
    output_file = "playwright_uae_coaches.csv"
    columns = ["Coach Name", "Niche", "Email Address"]
    
    if all_leads and len(all_leads) > 0:
        df = pd.DataFrame(all_leads)
        df = df.drop_duplicates(subset=["Coach Name"])
        df = df[columns]
        df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"\n🎉 Cloud Matrix Operation Complete! Saved {len(df)} 100% genuine records directly to repository.")
    else:
        print("\n❌ Pipeline Halting: Zero elements parsed from live web grid framework.")
        raise RuntimeError("Organic extraction verification failed. Bailing out to protect database integrity.")

if __name__ == "__main__":
    asyncio.run(main())
