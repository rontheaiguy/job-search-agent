"""
Job Search Agent
Pulls jobs from Adzuna and LinkedIn, scores them with Claude, saves to Notion, notifies via Slack.
"""

import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import anthropic

# ── Load environment variables from .env ─────────────────────────────────────
load_dotenv()

ADZUNA_APP_ID          = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY         = os.getenv("ADZUNA_APP_KEY")
ANTHROPIC_API_KEY      = os.getenv("ANTHROPIC_API_KEY")
NOTION_API_KEY         = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID     = os.getenv("NOTION_DATABASE_ID")
SLACK_WEBHOOK_URL      = os.getenv("SLACK_WEBHOOK_URL")

# ── Condensed resume profiles (optimized for token efficiency) ───────────────

RESUME_1PAGE = """
Rounaq Gandhi | Product Manager | Chicago, IL | Open to Relocation | U.S. Citizen
Experience: 2-3 years PM, 7+ years total in product/QA/engineering

CURRENT: Product Manager, Peek (B2B SaaS, iOS) — Apr 2024 to Present
- Owns end-to-end product lifecycle: PRDs, user stories, BDD/Gherkin, backlog, GA launches
- Led GTM for mobile POS barcode scanner — $18M GMV, key account renewals
- Shipped Offline Mode for 35 enterprise customers, 2 weeks early, 22% adoption increase
- 11.5% user adoption increase via search, filters, in-app notifications
- 8% transaction adoption increase via store credit refunds on iOS
- A/B testing with PostHog and Looker; OKRs/KPIs with cross-functional teams
- Agile: sprint planning, backlog grooming, retrospectives

PRIOR: Senior QA Engineer, Peek (Apr 2022 - Mar 2024)
PRIOR: Associate Product Owner / Senior Test Engineer, Emerson Automation Solutions (Oct 2017 - Mar 2022)
- Pharmaceutical MES domain; IEC 62304, ISO 13485, 21 CFR Part 11
- 200+ bugs resolved pre-launch; $4.2M revenue generated

CERTIFICATIONS: SAFe Agilist, CSPO, A-CSPO, CSM
TOOLS: Jira, Confluence, Figma, Pendo, Mixpanel, Looker, PostHog, NotionAI, Claude, Loveable
SKILLS: Roadmapping, PRDs, User Research, A/B Testing, GTM, OKRs, Stakeholder Management, Prioritization
DOMAINS: B2B SaaS, iOS Mobile, Enterprise Software
FORMAT: Concise — best for APM/PM roles requiring a sharp, focused profile
""".strip()

RESUME_2PAGE = """
Rounaq Gandhi | Product Manager | Chicago, IL | Open to Relocation | U.S. Citizen
Experience: 2-3 years PM, 7+ years total in product/QA/engineering

CURRENT: Product Manager / Product Owner, Peek (B2B SaaS, iOS) — Apr 2024 to Present
- Full product lifecycle: PRDs, user stories, BDD/Gherkin, backlog, GA launches
- GTM for mobile POS barcode scanner — $18M GMV, key account renewals
- Offline Mode shipped 2 weeks early for 35 enterprise customers — 22% adoption increase
- 11.5% user adoption increase; 8% transaction adoption increase on iOS
- A/B testing with PostHog and Looker; OKRs/KPIs alignment
- Independently designed and shipped low-complexity features, reducing design bottlenecks
- Agile: sprint planning, backlog grooming, retrospectives, post-launch demos

PRIOR: Senior QA Engineer, Peek (Apr 2022 - Mar 2024)
- Playwright test automation via TestCollab; shift-left testing; payment integrations

PRIOR: Associate Product Owner / Senior Test Engineer, Emerson Automation Solutions (Oct 2017 - Mar 2022)
- Pharmaceutical MES (Syncade); IEC 62364, ISO 13485, 21 CFR Part 11
- 40% reduction in manual testing; $4.2M revenue from launch; Best Employee 7x

PRIOR: Software Test Analyst, Cognizant (Aug 2015 - Sep 2017) — Financial & Automotive

EDUCATION: MS Computer & Electrical Engineering, NJIT (GPA 3.7); BS Electronics & Telecom, Pune
CERTIFICATIONS: SAFe Agilist, CSPO, A-CSPO, CSM
TOOLS: Jira, Confluence, Figma, Pendo, Mixpanel, Looker, PostHog, TestCollab, TFS, NotionAI, Claude
SKILLS: Roadmapping, PRDs, User Stories, A/B Testing, GTM, OKRs, Sprint Planning, Stakeholder Management, RICE Prioritization, BDD/Gherkin, Mobile Apps (iOS/Android), Rapid Prototyping, SQL
DOMAINS: B2B SaaS, iOS Mobile, Enterprise Software, Pharmaceutical MES, Financial, Automotive
FORMAT: Detailed — best for senior roles or companies valuing breadth of experience
""".strip()

# ── Job titles to search ──────────────────────────────────────────────────────

JOB_TITLES = [
    "Product Manager",
    "Senior Product Manager",
    "Associate Product Manager",
    "Product Owner",
    "Senior Product Owner",
]

# ── Step 1: Pull jobs from Adzuna + LinkedIn ──────────────────────────────────

def fetch_jobs_from_adzuna():
    """
    Calls the Adzuna Jobs API for each job title.
    Returns a combined list of job listings.
    """
    print("🔍 Fetching jobs from Adzuna...")
    all_jobs = []

    for title in JOB_TITLES:
        print(f"  → Searching: {title}")
        title_jobs = []

        for page in range(1, 6):  # 5 pages × 50 = 250 per title
            url = "https://api.adzuna.com/v1/api/jobs/us/search/" + str(page)
            params = {
                "app_id":           ADZUNA_APP_ID,
                "app_key":          ADZUNA_APP_KEY,
                "what":             title,
                "where":            "United States",
                "results_per_page": 50,
                "max_days_old":     1,  # last 24 hours
                "sort_by":          "date",
            }

            try:
                resp = requests.get(url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                jobs = data.get("results", [])
                if not jobs:
                    break
                title_jobs.extend(jobs)
                if len(jobs) < 50:
                    break
            except Exception as e:
                print(f"     ⚠️  Adzuna error on page {page} for '{title}': {e}")
                break

            time.sleep(0.5)

        print(f"     Found {len(title_jobs)} listings for '{title}'")
        all_jobs.extend(title_jobs)
        time.sleep(1)

    print(f"✅ Adzuna total: {len(all_jobs)}")
    return all_jobs


def fetch_jobs_from_linkedin():
    """
    Scrapes LinkedIn's public guest API for each job title.
    No login, no API key, completely free.
    Returns a combined list of job listings.
    """
    import re
    from bs4 import BeautifulSoup

    print("🔍 Fetching jobs from LinkedIn...")
    all_jobs = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # f_TPR=r43200 = posted in last 12 hours (43200 seconds)
    TIME_FILTER = "r43200"

    for title in JOB_TITLES:
        print(f"  → Searching LinkedIn: {title}")
        title_jobs = []
        search_title = title.replace(" ", "%20")

        # Pull up to 5 pages × 10 results = 50 per title
        for page in range(5):
            start = page * 10
            url = (
                f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                f"?keywords={search_title}"
                f"&location=United%20States"
                f"&f_TPR={TIME_FILTER}"
                f"&start={start}"
            )

            try:
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code != 200:
                    break

                # Extract job IDs from HTML
                job_ids = re.findall(
                    r'data-entity-urn="urn:li:jobPosting:(\d+)"', resp.text
                )
                if not job_ids:
                    break

                # Fetch details for each job ID
                for job_id in job_ids:
                    detail_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
                    try:
                        detail_resp = requests.get(detail_url, headers=headers, timeout=15)
                        if detail_resp.status_code != 200:
                            continue

                        soup = BeautifulSoup(detail_resp.text, "html.parser")

                        # Extract fields
                        title_el = soup.find("h2", class_=lambda x: x and "top-card-layout__title" in x)
                        company_el = soup.find("a", class_=lambda x: x and "topcard__org-name-link" in x)
                        location_el = soup.find("span", class_=lambda x: x and "topcard__flavor--bullet" in x)
                        desc_el = soup.find("div", class_=lambda x: x and "description__text" in x)

                        job_title = title_el.get_text(strip=True) if title_el else ""
                        company = company_el.get_text(strip=True) if company_el else ""
                        location = location_el.get_text(strip=True) if location_el else ""
                        description = desc_el.get_text(strip=True)[:1500] if desc_el else ""
                        job_link = f"https://www.linkedin.com/jobs/view/{job_id}/"

                        if not job_title:
                            continue

                        title_jobs.append({
                            "title":       job_title,
                            "company":     {"display_name": company},
                            "location":    {"display_name": location},
                            "description": description,
                            "redirect_url": job_link,
                            "created":     datetime.now(timezone.utc).isoformat(),
                            "source":      "LinkedIn",
                        })

                        time.sleep(0.3)  # polite delay between job detail requests

                    except Exception as e:
                        continue

                time.sleep(1)

            except Exception as e:
                print(f"     ⚠️  LinkedIn error on page {page} for '{title}': {e}")
                break

        print(f"     Found {len(title_jobs)} listings for '{title}'")
        all_jobs.extend(title_jobs)
        time.sleep(2)

    print(f"✅ LinkedIn total: {len(all_jobs)}")
    return all_jobs

# ── Step 2: Filter — remove old and duplicate listings ───────────────────────

def is_recent(job):
    """
    Returns True if the job was posted within the last 2 days.
    Acts as a safety net — Adzuna and LinkedIn already filter by time,
    but this catches any stragglers with old dates.
    """
    raw_date = job.get("created") or job.get("postedAt") or ""
    if not raw_date:
        return True  # if no date, keep the listing to be safe

    try:
        if "T" in raw_date:
            posted = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        else:
            posted = datetime.strptime(raw_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)

        cutoff = datetime.now(timezone.utc) - timedelta(days=2)
        return posted >= cutoff
    except Exception:
        return True  # if date parsing fails, keep the listing


def get_existing_notion_links():
    """
    Fetches all JD links already saved in Notion to detect duplicates.
    Returns a set of URLs.
    """
    print("📋 Checking Notion for existing listings...")
    existing_links = set()
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    has_more = True
    next_cursor = None

    while has_more:
        body = {"page_size": 100}
        if next_cursor:
            body["start_cursor"] = next_cursor

        resp = requests.post(url, headers=headers, json=body, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for page in data.get("results", []):
            props = page.get("properties", {})
            link_prop = props.get("Job link", {})
            # Notion URL fields return a list of rich_text or a url type
            if link_prop.get("type") == "url":
                link_val = link_prop.get("url") or ""
            else:
                rich = link_prop.get("rich_text", [])
                link_val = rich[0]["text"]["content"] if rich else ""
            if link_val:
                existing_links.add(link_val.strip())

        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    print(f"  → Found {len(existing_links)} existing listings in Notion.")
    return existing_links


def is_relevant_title(job):
    """
    Only allows exact PM/PO role titles. Rejects everything else.
    """
    title = job.get("title", "").lower().strip()

    # Must contain one of these core phrases
    allowed = [
        "product manager",
        "senior product manager",
        "product owner",
        "associate product manager",
        "senior product owner",
        "sr. product manager",
        "sr product manager",
        "staff product manager",
        "principal product manager",
        "group product manager",
        "director of product",
        "head of product",
        "vp of product",
        "vp, product",
    ]

    for a in allowed:
        if a in title:
            return True

    return False


def filter_jobs(raw_jobs, existing_links):
    """
    Removes duplicates, irrelevant titles, and listings older than 10 days.
    Returns a clean list of new jobs.
    """
    print("🔎 Filtering listings...")
    filtered = []
    seen_links = set()
    skipped_title = 0

    for job in raw_jobs:
        # Adzuna returns "redirect_url" as the job link
        link = job.get("redirect_url") or job.get("link") or ""
        link = link.strip()

        # Skip if no link at all
        if not link:
            continue

        # Skip irrelevant job titles
        if not is_relevant_title(job):
            skipped_title += 1
            continue

        # Skip duplicates within this batch
        if link in seen_links:
            continue

        # Skip if already in Notion
        if link in existing_links:
            continue

        # Skip if older than 2 days
        if not is_recent(job):
            continue

        seen_links.add(link)
        filtered.append(job)

    print(f"  → Skipped {skipped_title} irrelevant titles.")
    print(f"✅ {len(filtered)} new listings after filtering.")
    return filtered

# ── Step 3: Claude analysis ───────────────────────────────────────────────────

def analyze_job_with_claude(job):
    """
    Sends the job description and both resumes to Claude.
    Returns a dict with: industry, match_percent, match_tier, key_skills,
    resume_recommendation, and notes.
    """
    title        = job.get("title", "Unknown Title")
    company      = job.get("company", {}).get("display_name") or "Unknown Company"
    description  = job.get("description") or ""
    location_raw = job.get("location", {}).get("display_name") or ""

    # Truncate long descriptions to reduce token usage
    if len(description) > 1500:
        description = description[:1500] + "\n...[truncated]"

    prompt = f"""
You are a job search assistant helping a Product Manager named Rounaq Gandhi analyze a job listing.

Here is the job listing:
---
Title: {title}
Company: {company}
Location: {location_raw}
Description:
{description}
---

Here are Rounaq's two resumes:

RESUME 1 (1-page):
{RESUME_1PAGE}

RESUME 2 (2-page):
{RESUME_2PAGE}

Please analyze this job listing and respond ONLY with a valid JSON object — no extra text, no markdown, no backticks. Use exactly this structure:

{{
  "industry": "<your best guess at the industry from the JD, e.g. B2B SaaS, FinTech, HealthTech, Enterprise Software, eCommerce, etc.>",
  "match_percent": <integer from 0 to 100 representing how well Rounaq's background matches this JD>,
  "key_skills": ["<skill 1>", "<skill 2>", "<skill 3>"],
  "resume_recommendation": "<either 'Concise' or 'Detailed', with a one-sentence reason>",
  "notes": "<2-3 sentences: why this role is or isn't a strong fit, any red flags, and anything Rounaq should customize in his application>"
}}

Rules:
- key_skills: list the top 3-5 skills the JD emphasizes most (pull from the JD text, not the resume)
- match_percent: base this on how Rounaq's actual experience, certifications, tools, and domain match what the JD asks for
- match_percent tiers: Low = 0-30, Medium = 31-50, High = 51-80, Top = 81-100
- resume_recommendation: recommend 'Concise' for roles that want sharp, focused APM/PM profiles; recommend 'Detailed' for senior/complex roles that value breadth of experience
- notes: be specific and actionable
""".strip()

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = message.content[0].text.strip()

        # Strip markdown code fences if Claude wraps the JSON
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()

        result = json.loads(raw_text)
        return result

    except json.JSONDecodeError as e:
        print(f"     ⚠️  JSON parse error for '{title}': {e}")
        return default_claude_result()
    except Exception as e:
        print(f"     ⚠️  Claude API error for '{title}': {e}")
        return default_claude_result()


def default_claude_result():
    """Fallback if Claude analysis fails."""
    return {
        "industry": "Unknown",
        "match_percent": 0,
        "key_skills": [],
        "resume_recommendation": "1-page",
        "notes": "Claude analysis unavailable for this listing.",
    }


def match_tier(percent):
    """Converts a match percentage to the Notion select label."""
    if percent <= 30:
        return "Low (<30%)"
    elif percent <= 50:
        return "Medium (31–50%)"
    elif percent <= 80:
        return "High (51–80%)"
    else:
        return "Top (81–100%)"


def work_mode(location_raw):
    """
    Guesses the work mode (Remote / Hybrid / Onsite) from the location string.
    """
    loc = location_raw.lower()
    if "remote" in loc:
        return "Remote"
    elif "hybrid" in loc:
        return "Hybrid"
    else:
        return "Onsite"

def detect_source(link):
    """
    Detects the job source from the URL.
    """
    if not link:
        return "Unknown"
    link_lower = link.lower()
    if "linkedin.com" in link_lower:
        return "LinkedIn"
    elif "indeed.com" in link_lower:
        return "Indeed"
    elif "greenhouse.io" in link_lower:
        return "Greenhouse"
    elif "lever.co" in link_lower:
        return "Lever"
    elif "workday.com" in link_lower:
        return "Workday"
    elif "ziprecruiter.com" in link_lower:
        return "ZipRecruiter"
    elif "monster.com" in link_lower:
        return "Monster"
    elif "glassdoor.com" in link_lower:
        return "Glassdoor"
    elif "adzuna.com" in link_lower:
        return "Adzuna"
    elif "smartrecruiters.com" in link_lower:
        return "SmartRecruiters"
    elif "icims.com" in link_lower:
        return "iCIMS"
    elif "jobvite.com" in link_lower:
        return "Jobvite"
    else:
        # Extract domain name as fallback
        try:
            domain = link_lower.split("//")[-1].split("/")[0]
            domain = domain.replace("www.", "").replace("jobs.", "")
            return domain.split(".")[0].capitalize()
        except Exception:
            return "Other"


# ── Step 4: Save to Notion ────────────────────────────────────────────────────

def get_next_serial_number():
    """
    Counts existing rows in Notion and returns the next serial number.
    """
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    total = 0
    has_more = True
    next_cursor = None

    while has_more:
        body = {"page_size": 100}
        if next_cursor:
            body["start_cursor"] = next_cursor
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        total += len(data.get("results", []))
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    return total + 1


def save_to_notion(job, analysis, serial_number):
    """
    Creates a new page in the Notion database for a job listing.
    """
    title       = job.get("title", "Unknown Title")
    company     = job.get("company", {}).get("display_name") or "Unknown Company"
    location_raw= job.get("location", {}).get("display_name") or ""
    link        = job.get("redirect_url") or job.get("link") or ""
    date_posted = job.get("created") or ""

    # Format date_posted as YYYY-MM-DD for Notion
    if date_posted:
        try:
            if "T" in date_posted:
                date_str = date_posted[:10]
            else:
                date_str = date_posted[:10]
        except Exception:
            date_str = None
    else:
        date_str = None

    industry            = analysis.get("industry", "Unknown")
    match_pct           = analysis.get("match_percent", 0)
    tier                = match_tier(match_pct)
    key_skills          = analysis.get("key_skills", [])
    resume_rec_raw      = analysis.get("resume_recommendation", "1-page")
    if "2-page" in resume_rec_raw or "2 page" in resume_rec_raw.lower() or "detailed" in resume_rec_raw.lower():
        resume_rec = "Detailed"
    else:
        resume_rec = "Concise"
    notes_text          = analysis.get("notes", "")
    mode                = work_mode(location_raw)
    source              = detect_source(link)

    # Build the Notion page properties payload
    properties = {
        "Job title": {
            "rich_text": [{"text": {"content": title}}]
        },
        "Sr.": {
            "rich_text": [{"text": {"content": str(serial_number)}}]
        },
        "Company name": {
            "rich_text": [{"text": {"content": company}}]
        },
        "Industry": {
            "rich_text": [{"text": {"content": industry}}]
        },
        "Location": {
            "select": {"name": mode}
        },
        "JD match %": {
            "rich_text": [{"text": {"content": tier}}]
        },
        "Job link": {
            "rich_text": [{"text": {"content": link if link else ""}}]
        },
        "Key Skills Needed": {
            "rich_text": [{"text": {"content": ", ".join(key_skills)}}]
        },
        "Resume used": {
            "select": {"name": resume_rec}
        },
        "Source": {
            "rich_text": [{"text": {"content": source}}]
        },
        "Notes": {
            "title": [{"text": {"content": notes_text}}]
        },
        "Status": {
            "select": {"name": "To apply"}
        },
    }

    # Add date posted if available
    if date_str:
        properties["Date posted"] = {"date": {"start": date_str}}

    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    body = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
    }

    resp = requests.post(url, headers=headers, json=body, timeout=15)
    if resp.status_code not in (200, 201):
        print(f"     ⚠️  Notion error for '{title}': {resp.status_code} — {resp.text[:200]}")
        return False

    return True

# ── Step 5: Send Slack summary ────────────────────────────────────────────────

def send_slack_summary(saved_jobs):
    """
    Sends a clean Slack summary with top matches and tier breakdown.
    """
    today = datetime.now().strftime("%m/%d/%Y")
    notion_url = f"https://www.notion.so/{NOTION_DATABASE_ID.replace('-', '')}"

    if not saved_jobs:
        message = (
            f"📋 *Job Search — {today}*\n\n"
            f"No new listings found today."
        )
    else:
        total = len(saved_jobs)

        # Count by tier
        tier_counts = {
            "Top (81–100%)": 0,
            "High (51–80%)": 0,
            "Medium (31–50%)": 0,
            "Low (<30%)": 0,
        }
        for j in saved_jobs:
            t = j["tier"]
            if t in tier_counts:
                tier_counts[t] += 1

        # Top matches — High and Top tier only, max 5
        top_matches = [
            j for j in saved_jobs
            if j["tier"] in ("Top (81–100%)", "High (51–80%)")
        ]
        top_matches = sorted(
            top_matches,
            key=lambda x: x["match_percent"],
            reverse=True
        )[:5]

        # Build message
        lines = [
            f"📋 *Job Search — {today}*\n",
            f"✅ *{total} new listing{'s' if total != 1 else ''} saved today*\n",
        ]

        if top_matches:
            lines.append("🔥 *Top matches:*")
            for j in top_matches:
                lines.append(f"• {j['title']} at *{j['company']}* — {j['match_percent']}% match ({j['tier']})")
            lines.append("")

        lines.append("📊 *Breakdown:*")
        for tier, count in tier_counts.items():
            if count > 0:
                lines.append(f"• {tier}: {count}")

        lines.append(f"\n🔗 <{notion_url}|View all in Notion>")

        message = "\n".join(lines)

    payload = {"text": message}
    resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
    if resp.status_code == 200:
        print("✅ Slack notification sent.")
    else:
        print(f"⚠️  Slack error: {resp.status_code} — {resp.text}")

# ── Estimated balance tracker ─────────────────────────────────────────────────

COST_PER_JOB       = 0.018   # actual cost per job from first run
LOW_BALANCE_THRESHOLD = 1.00  # warn when estimated balance drops below $1
BALANCE_FILE       = os.path.join(os.path.dirname(__file__), ".claude_balance")


def load_balance():
    """Load estimated remaining balance from local file."""
    try:
        with open(BALANCE_FILE, "r") as f:
            return float(f.read().strip())
    except Exception:
        return None


def save_balance(balance):
    """Save estimated remaining balance to local file."""
    try:
        with open(BALANCE_FILE, "w") as f:
            f.write(str(round(balance, 4)))
    except Exception as e:
        print(f"⚠️  Could not save balance file: {e}")


def update_balance_and_warn(jobs_analyzed):
    """
    Deducts estimated cost from balance and sends Slack warning if below $1.
    """
    balance = load_balance()
    if balance is None:
        print("ℹ️  No balance file found — skipping balance check.")
        print("    To enable: create .claude_balance file with your current credit amount.")
        return

    cost_this_run = jobs_analyzed * COST_PER_JOB
    new_balance = balance - cost_this_run
    save_balance(new_balance)

    print(f"💰 Estimated Claude balance: ${new_balance:.2f} (spent ${cost_this_run:.2f} this run)")

    if new_balance < LOW_BALANCE_THRESHOLD:
        warning = (
            f"🚨🚨🚨 *CLAUDE CREDITS RUNNING LOW* 🚨🚨🚨\n\n"
            f"💸 Estimated remaining balance: *${new_balance:.2f}*\n"
            f"⚠️ Threshold: ${LOW_BALANCE_THRESHOLD:.2f}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔴 *Action required:* Reload credits now or the agent will stop working.\n"
            f"👉 https://console.anthropic.com/settings/billing\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"_After reloading, update your balance file:_\n"
            f"`echo \"YOUR_NEW_AMOUNT\" > .claude_balance`"
        )
        requests.post(SLACK_WEBHOOK_URL, json={"text": warning}, timeout=10)
        print(f"⚠️  Low balance warning sent to Slack (${new_balance:.2f} remaining)")


# ── Claude balance check ─────────────────────────────────────────────────────

def check_claude_balance():
    """
    Makes a minimal Claude API call to check if credits are available.
    Sends a Slack warning if the API returns a credit error.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=10,
            messages=[{"role": "user", "content": "hi"}],
        )
        print("✅ Claude API credits available.")
        return True
    except Exception as e:
        error_str = str(e).lower()
        if "credit" in error_str or "balance" in error_str or "billing" in error_str or "402" in error_str:
            warning = (
                "🛑🛑🛑 *CLAUDE CREDITS EXHAUSTED* 🛑🛑🛑\n\n"
                "💀 Your Anthropic API balance has hit $0.\n"
                "❌ *Today's job analysis did NOT run.*\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "👉 Reload now: https://console.anthropic.com/settings/billing\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "_After reloading, update your balance file:_\n"
                "`echo \"YOUR_NEW_AMOUNT\" > .claude_balance`"
            )
            requests.post(SLACK_WEBHOOK_URL, json={"text": warning}, timeout=10)
            print("⚠️  Claude credits exhausted — Slack warning sent.")
        else:
            print(f"⚠️  Claude API check failed: {e}")
        return False


# ── Main orchestrator ─────────────────────────────────────────────────────────

def main():
    print("\n========================================")
    print("  Job Search Agent — Starting Run")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("========================================\n")

    # 0. Check Claude API credits before doing anything
    if not check_claude_balance():
        print("❌ Stopping run — Claude credits unavailable.")
        return

    # 1. Pull raw jobs from Adzuna + LinkedIn
    adzuna_jobs = fetch_jobs_from_adzuna()
    linkedin_jobs = fetch_jobs_from_linkedin()
    raw_jobs = adzuna_jobs + linkedin_jobs
    print(f"\n📦 Combined total: {len(raw_jobs)} raw listings ({len(adzuna_jobs)} Adzuna + {len(linkedin_jobs)} LinkedIn)")

    # 2. Get existing Notion links to skip duplicates
    existing_links = get_existing_notion_links()

    # 3. Filter out old and duplicate listings
    new_jobs = filter_jobs(raw_jobs, existing_links)

    if not new_jobs:
        print("\nℹ️  No new listings to process. Sending Slack update.")
        send_slack_summary([])
        return

    # 4. Analyze each job with Claude and save to Notion
    saved_jobs = []
    serial_number = get_next_serial_number()

    for i, job in enumerate(new_jobs, start=1):
        title   = job.get("title", "Unknown Title")
        company = job.get("company", {}).get("display_name") or "Unknown Company"
        link    = job.get("redirect_url") or job.get("link") or ""
        print(f"\n[{i}/{len(new_jobs)}] Analyzing: {title} at {company}")

        # Ask Claude to analyze this job
        analysis = analyze_job_with_claude(job)
        tier     = match_tier(analysis.get("match_percent", 0))
        resume   = analysis.get("resume_recommendation", "1-page")

        print(f"     Match: {analysis.get('match_percent')}% ({tier}) | Resume: {resume}")

        # Save to Notion
        success = save_to_notion(job, analysis, serial_number)
        if success:
            print(f"     ✅ Saved to Notion (Sr. #{serial_number})")
            saved_jobs.append({
                "title":         title,
                "company":       company,
                "tier":          tier,
                "link":          link,
                "resume":        resume,
                "match_percent": analysis.get("match_percent", 0),
            })
            serial_number += 1
        else:
            print(f"     ❌ Failed to save to Notion.")

        # Small pause to avoid rate limits
        time.sleep(1)

    # 5. Send Slack summary
    print(f"\n📨 Sending Slack summary ({len(saved_jobs)} listings saved)...")
    send_slack_summary(saved_jobs)

    # 6. Update estimated balance and warn if low
    update_balance_and_warn(len(saved_jobs))

    print("\n========================================")
    print(f"  Run complete. {len(saved_jobs)} new listings saved.")
    print("========================================\n")


if __name__ == "__main__":
    main()
