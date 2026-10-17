# Save as: scraper.py
# Flow: category page -> listed businesses -> business page -> its own website
#       -> homepage + contact pages -> REAL emails only -> save -> next target
import asyncio
import csv
import html as htmllib
import os
import random
import re
from urllib.parse import unquote, urljoin, urlparse

from playwright.async_api import async_playwright

BASE = "https://yello.ae"
CATEGORY_URL = os.getenv("CATEGORY_URL") or "https://www.yello.ae/category/massage-therapists"
NICHE = os.getenv("NICHE") or "Massage Therapists"
MAX_PAGES = int(os.getenv("MAX_PAGES") or 5)          # listing pages to read
MAX_LISTINGS = int(os.getenv("MAX_LISTINGS") or 100)  # new businesses per run
CONCURRENCY = int(os.getenv("CONCURRENCY") or 4)      # businesses processed in parallel

OUT_OK = "playwright_uae_beauty.csv"                  # rows WITH a real email
OUT_NO = "playwright_uae_beauty_no_email.csv"         # rows without (kept so we never redo them)
OUT_DUP = "playwright_uae_beauty_duplicates.csv"      # salons we already had (kept so we never redo them)
EXCLUDE_FILES = ["exclude.csv"]                       # optional: any older list you never want scraped again
FIELDS = ["Business Name", "Niche", "Email Address", "Other Emails", "Website", "Phone", "Yello URL"]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

COMPANY_RE = re.compile(r"/company/\d+(?:/[\w\-%]+)?")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,24}")
DOMAIN_TEXT_RE = re.compile(r"^(https?://)?(www\.)?[a-z0-9\-]+(\.[a-z0-9\-]+)+(/\S*)?$", re.I)

NOT_A_BUSINESS_SITE = ("facebook.", "instagram.", "twitter.", "x.com", "linkedin.", "youtube.",
                       "wa.me", "whatsapp.", "tiktok.", "snapchat.", "google.", "goo.gl",
                       "maps.", "yello.ae", "hugedomains", "dan.com", "godaddy")
BAD_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js", ".woff", ".woff2", ".ico")
BAD_PARTS = ("sentry", "wixpress", "example.", "yourdomain", "domain.com", "email.com",
             "schema.org", "w3.org", "@2x", "@3x", "yello.ae")
FREE_MAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
             "live.com", "yahoo.co.uk", "hotmail.co.uk", "aol.com", "proton.me", "protonmail.com"}
GENERIC_LOCALS = ("info", "contact", "hello", "enquiries", "enquiry", "sales",
                  "reservations", "booking", "bookings", "reception", "support")


def log(msg):
    print(msg, flush=True)


async def safe_close(obj):
    """Close a page/context without ever hanging the run (this froze your last run)."""
    try:
        await asyncio.wait_for(obj.unroute_all(behavior="ignoreErrors"), 5)
    except Exception:
        pass
    try:
        await asyncio.wait_for(obj.close(), 10)
    except Exception:
        pass


# ───────────────────────── files / resume ─────────────────────────
def init_files():
    for f in (OUT_OK, OUT_NO, OUT_DUP):
        if not os.path.exists(f):
            with open(f, "w", newline="", encoding="utf-8") as fh:
                csv.DictWriter(fh, FIELDS).writeheader()


def norm_name(n):
    return re.sub(r"[^a-z0-9]", "", n.lower())


KNOWN = {"urls": set(), "names": set(), "emails": set()}


def load_known():
    """Everything we already have: Yello URLs, salon names and emails from our own CSVs
    plus any optional exclude.csv (any column with 'name' or 'email' in its header is used)."""
    k = {"urls": set(), "names": set(), "emails": set()}
    for f in [OUT_OK, OUT_NO, OUT_DUP] + EXCLUDE_FILES:
        if not os.path.exists(f):
            continue
        with open(f, newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                for col, val in row.items():
                    if not col or not val:
                        continue
                    c = col.lower()
                    if col == "Yello URL":
                        k["urls"].add(val.strip())
                    elif "name" in c:
                        k["names"].add(norm_name(val))
                    elif "email" in c:
                        for e in re.split(r"[;,\s]+", val):
                            if "@" in e:
                                k["emails"].add(e.lower())
    return k


async def save_row(row, target, lock):
    async with lock:  # written immediately, so a crash never loses finished work
        with open(target, "a", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, FIELDS).writerow(row)


# ───────────────────────── browser helpers ─────────────────────────
async def new_context(browser):
    ctx = await browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 900},
                                    locale="en-US", ignore_https_errors=True)

    async def block_heavy(route):
        if route.request.resource_type in ("image", "media", "font"):
            await route.abort()
        else:
            await route.continue_()

    await ctx.route("**/*", block_heavy)
    return ctx


async def safe_goto(page, url, timeout=30000):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        await page.wait_for_timeout(1500)
        return True
    except Exception as e:
        log(f"   ⚠️ could not open {url}: {(str(e).splitlines() or [''])[0][:90]}")
        return False


async def autoscroll(page, rounds=6):
    for _ in range(rounds):
        await page.mouse.wheel(0, 4000)
        await page.wait_for_timeout(900)
        try:
            btn = page.locator("button:has-text('Load more'), a:has-text('Load more'), "
                               "button:has-text('Show more')")
            if await btn.count():
                await btn.first.click(timeout=2000)
                await page.wait_for_timeout(1200)
        except Exception:
            pass


# ───────────────────────── step 1: listing pages ─────────────────────────
# Only links AFTER the "We found N listings" line are real results
# (the scrolling ticker at the top of the page is what gave you the 4 random companies).
LISTING_JS = """
() => {
  const re = /We found\\s*[\\d,]+\\s*listings/i;
  let marker = null;
  for (const e of document.querySelectorAll('body *')) {
    if (re.test(e.textContent || '') && ![...e.children].some(c => re.test(c.textContent || ''))) {
      marker = e; break;
    }
  }
  const out = [];
  for (const a of document.querySelectorAll("a[href*='/company/']")) {
    if (marker && !(marker.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING)) continue;
    out.push({href: a.href, text: (a.innerText || '').trim(), marker: !!marker});
  }
  return out;
}
"""


NEXT_JS = r"""
(n) => {
  const as = [...document.querySelectorAll('a[href]')].filter(a => a.href && !a.href.endsWith('#') && !a.href.startsWith('javascript'));
  const byRel = as.find(a => (a.rel || '').includes('next') || /next/i.test(a.getAttribute('aria-label') || ''));
  if (byRel) return byRel.href;
  const byText = as.find(a => /^(next|\u203a|\u00bb|>|>>)$/i.test((a.innerText || '').trim()));
  if (byText) return byText.href;
  const byNum = as.find(a => (a.innerText || '').trim() === String(n) && !/\/company\//.test(a.href));
  return byNum ? byNum.href : null;
}
"""
PAGE_PATTERNS = ["{u}?page={n}", "{u}/page/{n}", "{u}/{n}", "{u}?p={n}", "{u}?pg={n}"]


async def scan_listing(page, url, seen, fresh, done):
    """Open one listing page, add its business links. Returns number of never-seen links (None = failed)."""
    if not await safe_goto(page, url, 45000):
        return None
    await autoscroll(page)
    links = await page.evaluate(LISTING_JS)
    if links and not links[0].get("marker"):
        log("   ⚠️ 'We found N listings' marker not found - using all company links on page")
    new_here = 0
    for l in links:
        m = COMPANY_RE.search(l["href"])
        if not m:
            continue
        u = BASE + m.group(0)
        if u in seen:
            continue
        seen.add(u)
        new_here += 1
        if u not in done:
            fresh.append(u)
    log(f"   {len(links)} links, {new_here} unseen, {len(fresh)} new targets so far")
    return new_here


async def collect_listing_urls(browser, done):
    ctx = await new_context(browser)
    page = await ctx.new_page()
    seen, fresh = set(), []
    base = CATEGORY_URL.rstrip("/")
    order = PAGE_PATTERNS[:]
    log(f"🌐 Listing page 1: {CATEGORY_URL}")
    await scan_listing(page, CATEGORY_URL, seen, fresh, done)
    for page_no in range(2, MAX_PAGES + 1):
        if len(fresh) >= MAX_LISTINGS:
            break
        candidates = []
        try:
            nxt = await page.evaluate(NEXT_JS, page_no)   # real next/numbered link on the page
        except Exception:
            nxt = None
        if nxt:
            candidates.append(("next", nxt))
        candidates += [(p, p.format(u=base, n=page_no)) for p in order]   # URL-pattern guesses
        got = 0
        for label, cand in candidates:
            log(f"🌐 Listing page {page_no}: {cand}")
            got = await scan_listing(page, cand, seen, fresh, done)
            if got:
                if label != "next":       # remember the pattern that works
                    order.remove(label)
                    order.insert(0, label)
                break
        if not got:
            log("   no more listing pages found")
            break
    await safe_close(ctx)
    return fresh[:MAX_LISTINGS], len(seen)


# ───────────────────────── step 2: business page -> website ─────────────────────────
def normalize_site(text):
    t = text.strip()
    if not t.lower().startswith("http"):
        t = "https://" + t
    return t


async def find_website(page, ctx):
    anchors = await page.eval_on_selector_all(
        "a[href]", "els => els.map(e => ({href: e.href, text: (e.innerText || '').trim()}))")
    # 1) the link whose visible text is a domain, e.g. "plushbeautyspa.ae/"
    for a in anchors:
        t = a["text"]
        if DOMAIN_TEXT_RE.match(t) and not any(x in t.lower() for x in NOT_A_BUSINESS_SITE):
            return normalize_site(t)
    # 2) external link labelled "Website"
    for a in anchors:
        h = a["href"].lower()
        if "website" in a["text"].lower() and h.startswith("http") and \
                not any(x in h for x in NOT_A_BUSINESS_SITE):
            return a["href"]
    # 3) yello redirect link (/website/...) -> follow redirect without clicking
    for a in anchors:
        if "/website/" in a["href"]:
            try:
                resp = await ctx.request.get(a["href"], max_redirects=5, timeout=20000)
                if not any(x in resp.url.lower() for x in NOT_A_BUSINESS_SITE):
                    return resp.url
            except Exception:
                pass
    return None


# ───────────────────────── step 3: website -> emails ─────────────────────────
def decode_cf(h):
    r = int(h[:2], 16)
    return "".join(chr(int(h[i:i + 2], 16) ^ r) for i in range(2, len(h), 2))


def valid_email(e):
    e = e.lower().strip(".,;:")
    if len(e) > 80 or e.endswith(BAD_EXT) or any(p in e for p in BAD_PARTS):
        return None
    return e


async def page_emails(page):
    blob = ""
    try:
        blob += htmllib.unescape(await page.content())
    except Exception:
        pass
    try:
        blob += " " + await page.inner_text("body")
    except Exception:
        pass
    found = set(EMAIL_RE.findall(blob))
    try:
        for h in await page.eval_on_selector_all(
                "a[href^='mailto:']", "els => els.map(e => e.getAttribute('href'))"):
            found.update(EMAIL_RE.findall(unquote(h)))
        for cf in await page.eval_on_selector_all(
                "[data-cfemail]", "els => els.map(e => e.getAttribute('data-cfemail'))"):
            found.add(decode_cf(cf))
    except Exception:
        pass
    return {v for v in (valid_email(e) for e in found) if v}


def host(u):
    return urlparse(u).netloc.lower().replace("www.", "")


async def open_site(page, url):
    """Try the URL, then the www/non-www twin, then http. Skips hosts whose DNS is dead."""
    p = urlparse(url)
    h = p.netloc
    alt = h[4:] if h.startswith("www.") else "www." + h
    path = p.path or "/"
    dead = set()
    for t in (url, f"{p.scheme}://{alt}{path}", f"http://{h}{path}", f"http://{alt}{path}"):
        th = urlparse(t).netloc
        if th in dead:
            continue
        try:
            await page.goto(t, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(1500)
            return True
        except Exception as e:
            if "NAME_NOT_RESOLVED" in str(e):
                dead.add(th)
    log(f"   ⚠️ website unreachable (dead/expired domain?): {url}")
    return False


async def scrape_site_emails(ctx, site_url):
    page = await ctx.new_page()
    emails = set()
    try:
        if not await open_site(page, site_url):
            return emails
        final_url = page.url
        emails |= await page_emails(page)
        if emails:
            return emails

        # no email on the homepage -> try contact/about pages
        links = await page.eval_on_selector_all(
            "a[href]", "els => els.map(e => [e.href, (e.innerText || '').trim()])")
        cands = []
        for href, txt in links:
            if re.search(r"contact|get-in-touch|reach|about", f"{href} {txt}", re.I) \
                    and host(href) == host(final_url):
                cands.append(href.split("#")[0])
        for guess in ("/contact-us/", "/contact/", "/contact-us", "/contact",
                      "/contactus", "/contact.html", "/contact-us.html", "/contact.php"):
            cands.append(urljoin(final_url, guess))
        tried = set()
        for c in cands:
            if c in tried or len(tried) >= 6:
                continue
            tried.add(c)
            if await safe_goto(page, c, 25000):
                emails |= await page_emails(page)
                if emails:
                    break
    finally:
        await safe_close(page)
    return emails


def split_emails(emails, site):
    """good  = same domain as the business site, or a free-mail address (gmail etc.)
       other = unrelated domains (theme placeholders like info@beauty.com, agencies) -> manual check"""
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    b = norm(host(site).split(".")[0]) if site else ""

    def same_site(dom):
        a = norm(dom.split(".")[0])
        if not a or not b:
            return False
        if a == b:
            return True
        short, long_ = sorted((a, b), key=len)
        return len(short) >= 5 and short in long_ and len(short) / len(long_) >= 0.7

    def key(e):
        local, dom = e.split("@", 1)
        return (0 if same_site(dom) else 1, 0 if local in GENERIC_LOCALS else 1, e)

    good = sorted([e for e in emails
                   if same_site(e.split("@", 1)[1]) or e.split("@", 1)[1] in FREE_MAIL], key=key)
    other = sorted(e for e in emails if e not in good)
    return good, other


# ───────────────────────── one target, start to finish ─────────────────────────
async def process(browser, url, sem, lock, stats):
    async with sem:
        ctx = await new_context(browser)
        page = await ctx.new_page()
        try:
            if not await safe_goto(page, url, 45000):
                return
            try:
                name = (await page.inner_text("h1")).strip()
            except Exception:
                name = (await page.title()).split(" - ")[0].strip()
            name = re.sub(r"\s+[-–]\s+(?:[\w .]+,\s*)?UAE\s*$", "", name).strip()  # "X - Dubai, UAE" -> "X"
            nkey = norm_name(name)
            if nkey in KNOWN["names"]:      # already have this salon -> skip before visiting its website
                await save_row({"Business Name": name, "Niche": NICHE, "Yello URL": url}, OUT_DUP, lock)
                stats["dup"] += 1
                log(f"   ⏭️ [{name}] already in your list - skipped")
                return
            KNOWN["names"].add(nkey)
            phone = ""
            try:
                tel = await page.query_selector("a[href^='tel:']")
                phone = (await tel.inner_text()).strip() if tel else ""
            except Exception:
                pass

            log(f"📂 {name}")
            website = await find_website(page, ctx)
            good, other = [], []
            if website:
                log(f"   [{name}] 🔗 {website}")
                good, other = split_emails(await scrape_site_emails(ctx, website), website)
            else:
                log(f"   [{name}] 🔗 no personal website listed")

            row = {"Business Name": name, "Niche": NICHE,
                   "Email Address": good[0] if good else "",
                   "Other Emails": "; ".join((good[1:3] + other)[:4]),
                   "Website": website or "", "Phone": phone, "Yello URL": url}
            if good and good[0].lower() in KNOWN["emails"]:
                await save_row(row, OUT_DUP, lock)
                stats["dup"] += 1
                log(f"   ⏭️ [{name}] email {good[0]} already in your list - saved as duplicate")
            elif good:
                KNOWN["emails"].update(e.lower() for e in good)
                await save_row(row, OUT_OK, lock)
                stats["ok"] += 1
                log(f"   ✅ [{name}] -> {good[0]}")
            else:
                await save_row(row, OUT_NO, lock)
                stats["no"] += 1
                if other:
                    log(f"   ❓ [{name}] only unrelated-domain email(s) {other[:2]} -> no-email file, check manually")
                else:
                    log(f"   — [{name}] no email found")
        except Exception as e:
            log(f"   ⚠️ skipped {url}: {str(e)[:100]}")
        finally:
            await safe_close(ctx)
            await asyncio.sleep(random.uniform(1, 3))


async def main():
    init_files()
    KNOWN.update(load_known())
    done = KNOWN["urls"]
    log(f"🚀 Start | category: {CATEGORY_URL} | already processed: {len(done)} | known names: {len(KNOWN['names'])} | known emails: {len(KNOWN['emails'])}")
    lock = asyncio.Lock()
    stats = {"ok": 0, "no": 0, "dup": 0}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        urls, total_seen = await collect_listing_urls(browser, done)
        if total_seen == 0:
            raise RuntimeError("No listing links found on the category page - selectors/URL need a check.")
        log(f"📋 {len(urls)} new businesses to process (concurrency {CONCURRENCY})")
        sem = asyncio.Semaphore(CONCURRENCY)
        no_limit = asyncio.Semaphore(1000)  # process() already takes a semaphore; limiting happens in guarded()

        async def guarded(u):
            async with sem:
                try:
                    # hard stop: one slow/hung business can never freeze the whole run
                    await asyncio.wait_for(process(browser, u, no_limit, lock, stats), timeout=150)
                except asyncio.TimeoutError:
                    log(f"   ⏱️ timed out after 150s, skipped (will retry next run): {u}")

        await asyncio.gather(*(guarded(u) for u in urls))
        await browser.close()
    log(f"\n🎉 Done. With real email: {stats['ok']} | without: {stats['no']} | duplicates skipped: {stats['dup']}")


if __name__ == "__main__":
    asyncio.run(main())
