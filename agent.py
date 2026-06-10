"""
Job Search Agent
Pulls LinkedIn jobs via Apify, scores them with Claude, saves to Notion, notifies via Slack.
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

# ── Your resume text (baked in so Claude can compare them) ────────────────────

RESUME_1PAGE = """
ROUNAQ GANDHI
(734) 985-8281 | rounaqgandhi@gmail.com | Chicago, IL | Open to Relocation
https://www.linkedin.com/in/rounaqgandhi/
(U.S. Citizen | No sponsorship required)

SUMMARY
Results-oriented Product Manager with hands-on experience leading B2B SaaS and iOS mobile products across complex, high-stakes environments. Certified Scrum Product Owner (CSPO) and SAFe practitioner, I bring both Agile discipline and rigorous technical fluency - translating user insights and stakeholder needs into prioritized roadmaps that consistently deliver on business outcomes. Leveraging a Quality Engineering background, I collaborate effectively across engineering, design, and customer success to ship high-impact mobile features that drive double-digit gains in adoption and retention.

CAREER OVERVIEW

PEEK, Product Manager (04/24 - Present)
1. Translated qualitative and quantitative user insights - including client interviews, NPS surveys, and support escalations - into prioritized product roadmaps that addressed critical pain points and measurably improved core business metrics.
2. Owned the end-to-end product lifecycle for core features - from discovery and authoring PRDs, user stories, and BDD/Gherkin acceptance criteria to backlog prioritization and GA launches.
3. Led GTM strategy and launch of mobile POS barcode scanner with real-time inventory tracking and full order management - serving as primary deal-closer for prospects with $18M in GMV & contributing to key account renewals.
4. Acting as Product Owner, aligned cross-functional engineering and design teams around quarterly OKRs and KPIs - facilitating Agile ceremonies including sprint planning, backlog grooming, and retrospectives.
5. Resolved critical field connectivity escalations across 35 enterprise customers by championing and shipping Offline mode feature, 2 weeks ahead of schedule, leading a 5-person cross-functional team & driving 22% increase in adoption.
6. Conducted direct user interviews and partnered with onboarding and customer success teams to identify friction points - shipping targeted enhancements that reduced churn and drove 11.5% increase in user adoption.
7. Conducted A/B testing on core user flows using PostHog and Looker - identifying and resolving key friction points that increased uplift in user retention.
8. Increased transaction adoption by 8% by enabling store credit refunds on iOS, closing a competitive gap in payment flexibility.
9. Reduced customer churn by redesigning iOS QR check-in and self-checkout kiosk workflows.
10. Embedded AI tools including Claude, NotionAI into core PM workflows - streamlining PRD authoring, user story generation, defect tracking.

PEEK, Senior Quality Engineer (04/22 - 03/24)
- Worked directly with Product Managers and developers to translate complex customer needs into clear acceptance criteria.
- Ran daily QA standups and managed production deployment schedule.
- Ensured bug-free delivery of critical, deal-closing features for enterprise partners.

EMERSON AUTOMATION SOLUTIONS, Associate Product Owner / Senior Software Test Engineer (10/17 - 03/22)
- Led transition from Waterfall to Agile, acting as Scrum Master and Associate Product Owner.
- Defined product test strategies for Syncade MES in pharmaceutical domain (IEC 62304, ISO 13485, 21 CFR Part 11).
- Identified and resolved 200+ bugs before release; launch won customer satisfaction award and generated $4.2M in revenue.

SKILLS & CERTIFICATIONS
Software/Tools: JIRA, Confluence, Claude, NotionAI, Pendo, Mixpanel, Looker, Figma, Notion, Loveable, PostHog
Methodologies: Agile-Scrum, Kanban & Waterfall
Certifications: SAFe Agilist, CSPO, Advanced CSPO (A-CSPO), CSM
Products: Roadmapping, User Research, PRDs, A/B Testing, Prioritization, GTM, OKRs, Stakeholder Management
""".strip()

RESUME_2PAGE = """
ROUNAQ GANDHI
(734) 985-8281 | rounaqgandhi@gmail.com | Chicago, IL | Open to Relocation
https://www.linkedin.com/in/rounaqgandhi
(U.S. Citizen | No sponsorship required)

SUMMARY
Results-oriented Product Manager with hands-on experience leading B2B SaaS and iOS mobile products across complex, high-stakes environments. Certified Scrum Product Owner (CSPO) and SAFe practitioner, I bring both Agile discipline and rigorous technical fluency - translating user insights and stakeholder needs into prioritized roadmaps that consistently deliver on business outcomes. Leveraging a Quality Engineering background, I collaborate effectively across engineering, design, and customer success to ship high-impact mobile features that drive double-digit gains in adoption and retention.

CAREER OVERVIEW

PEEK, Product Manager / Product Owner (04/24 - Present)
- Translated qualitative and quantitative user insights into prioritized product roadmaps.
- Owned the end-to-end product lifecycle for core features - from discovery and authoring PRDs, user stories, and BDD/Gherkin acceptance criteria to backlog prioritization and GA launches.
- Led GTM strategy and launch of mobile POS barcode scanner with $18M in GMV, contributing to key account renewals.
- Aligned cross-functional engineering and design teams around quarterly OKRs and KPIs.
- Resolved critical field connectivity escalations across 35 enterprise customers by shipping Offline Mode feature 2 weeks ahead of schedule, driving 22% increase in feature adoption.
- Shipped targeted enhancements including search, filters, and in-app notifications that reduced churn and drove 11.5% increase in user adoption.
- Conducted A/B testing using PostHog and Looker to identify friction points and improve user retention.
- Increased transaction adoption by 8% by enabling store credit refunds on iOS.
- Reduced customer churn by redesigning iOS QR check-in and self-checkout kiosk workflows.
- Accelerated engineering velocity by independently designing, prototyping, and shipping low-complexity features and UI bug fixes.
- Drove GTM strategy for quarterly feature releases and led post-launch demonstrations.
- Embedded AI tools including Claude, NotionAI into core PM workflows.

PEEK, Senior Quality Engineer (04/22 - 03/24)
- Translated complex customer needs into clear acceptance criteria.
- Ran daily QA standups and managed production deployment schedule.
- Ensured bug-free delivery of critical features including payment integrations, subscription billing, and B2B inventory controls.
- Led migration of manual test cases into TestCollab to establish Playwright test automation.
- Championed shift-left testing strategy during backlog refinement.

EMERSON AUTOMATION SOLUTIONS, Associate Product Owner / Senior Software Test Engineer (10/17 - 03/22)
- Led Waterfall-to-Agile transition as Scrum Master and Associate Product Owner.
- Defined end-to-end product strategies for Syncade MES in pharmaceutical domain (IEC 62364, ISO 13485, 21 CFR Part 11).
- Identified and resolved 200+ bugs; launch won customer satisfaction award and generated $4.2M in revenue.
- Reduced manual testing overhead by 40% through automated test scripts.
- Recognized as Best Employee 7 times (2018-2020).

COGNIZANT TECHNOLOGY SOLUTIONS, Software Test Analyst (08/15 - 09/17)
- Acted as Scrum Master, facilitating daily stand-ups and Agile estimation.
- Managed offshore testing teams and led organizational expansion of new test unit.
- Partnered with Product Managers and engineering teams to translate business requirements into testing deliverables.

SKILLS & CERTIFICATIONS
Software/Tools: JIRA, Confluence, Claude, NotionAI, Loveable, Pendo, Mixpanel, Looker, Figma, Notion, PostHog, TestCollab, TFS, HP ALM, XMLSpy, VersionOne, Bugzilla, VMware, BeyondCompare
Methodologies: Agile-Scrum, Kanban & Waterfall
Certifications: SAFe Agilist, CSPO, Advanced CSPO (A-CSPO), CSM
Core PM Competencies: Roadmapping, User Research, PRDs, User Stories, A/B Testing, Prioritization (RICE, Impact vs Effort), GTM Strategy, OKRs, KPIs, Sprint Planning, Stakeholder Management, BDD/Gherkin Acceptance Criteria, Mobile Apps (iOS/Android), Rapid Prototyping, SQL-based Data Analysis

EDUCATION
Masters in Computer & Electrical Engineering, New Jersey Institute of Technology, NJ, USA (GPA 3.7/4.0)
Bachelors in Electronics and Telecommunications, University of Pune, India
""".strip()

# ── Job titles to search ──────────────────────────────────────────────────────

JOB_TITLES = [
    "Product Manager",
    "Associate Product Manager",
    "Product Owner",
    "Senior Product Owner",
]

# ── Step 1: Pull jobs from Adzuna ─────────────────────────────────────────────

def fetch_jobs_from_adzuna():
    """
    Calls the Adzuna Jobs API for each job title with pagination.
    Returns a combined list of job listings.
    """
    print("🔍 Fetching jobs from Adzuna...")

    all_jobs = []

    for title in JOB_TITLES:
        print(f"  → Searching: {title}")
        title_jobs = []

        # Pull up to 10 pages × 50 results = 500 per title
        for page in range(1, 11):
            url = "https://api.adzuna.com/v1/api/jobs/us/search/" + str(page)
            params = {
                "app_id":           ADZUNA_APP_ID,
                "app_key":          ADZUNA_APP_KEY,
                "what":             title,
                "where":            "United States",
                "results_per_page": 50,
                "max_days_old":     5,
                "sort_by":          "date",
            }

            try:
                resp = requests.get(url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                jobs = data.get("results", [])

                if not jobs:
                    break  # no more results, stop paginating

                title_jobs.extend(jobs)

                # If we got fewer than 50, there are no more pages
                if len(jobs) < 50:
                    break

            except Exception as e:
                print(f"     ⚠️  Adzuna error on page {page} for '{title}': {e}")
                break

            time.sleep(0.5)  # small pause between pages

        print(f"     Found {len(title_jobs)} listings for '{title}'")
        all_jobs.extend(title_jobs)
        time.sleep(1)

    print(f"✅ Total raw listings fetched: {len(all_jobs)}")
    return all_jobs

# ── Step 2: Filter — remove old and duplicate listings ───────────────────────

def is_within_10_days(job):
    """
    Returns True if the job was posted within the last 10 days.
    Handles missing or unparseable dates gracefully.
    """
    raw_date = job.get("created") or job.get("postedAt") or ""
    if not raw_date:
        return True  # if no date, keep the listing to be safe

    try:
        # Try parsing ISO format date strings
        if "T" in raw_date:
            posted = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        else:
            posted = datetime.strptime(raw_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)

        cutoff = datetime.now(timezone.utc) - timedelta(days=10)
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
            link_prop = props.get("JD link", {})
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
    Returns True only if the job title matches our target roles.
    Filters out irrelevant jobs like Software Engineer, QA, etc.
    """
    title = job.get("title", "").lower()

    # Must contain at least one of these phrases
    allowed = [
        "product manager",
        "product owner",
        "associate product",
        "senior product owner",
        "sr. product",
        "sr product",
    ]

    # Must NOT contain these — filters out false positives
    blocked = [
        "software engineer",
        "software developer",
        "qa engineer",
        "quality engineer",
        "test engineer",
        "data engineer",
        "devops",
        "ui/ux",
        "ux designer",
        "scrum master",
        "business analyst",
        "technical writer",
        "project manager",
        "program manager",
        "marketing manager",
        "sales manager",
        "account manager",
        "security",
        "architect",
        "java developer",
        "python developer",
        "full stack",
        "frontend",
        "backend",
        "missile",
        "device engineer",
        "network engineer",
    ]

    # Check blocked first
    for b in blocked:
        if b in title:
            return False

    # Then check allowed
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

        # Skip if older than 10 days
        if not is_within_10_days(job):
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

    # Truncate very long descriptions to avoid token overload
    if len(description) > 6000:
        description = description[:6000] + "\n...[truncated]"

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
  "resume_recommendation": "<either '1-page' or '2-page', with a one-sentence reason>",
  "notes": "<2-3 sentences: why this role is or isn't a strong fit, any red flags, and anything Rounaq should customize in his application>"
}}

Rules:
- key_skills: list the top 3-5 skills the JD emphasizes most (pull from the JD text, not the resume)
- match_percent: base this on how Rounaq's actual experience, certifications, tools, and domain match what the JD asks for
- match_percent tiers: Low = 0-30, Medium = 31-50, High = 51-80, Top = 81-100
- resume_recommendation: recommend 1-page for roles that want sharp, concise APM/PM profiles; recommend 2-page for senior/complex roles that value breadth of experience
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
    Finds the highest existing Sr. number in Notion and returns the next one.
    """
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    max_sr = 0
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
            sr_prop = props.get("Sr.", {})
            # Sr. might be a number or rich_text field
            if sr_prop.get("type") == "number":
                val = sr_prop.get("number") or 0
            else:
                rich = sr_prop.get("rich_text", [])
                try:
                    val = int(rich[0]["text"]["content"]) if rich else 0
                except (ValueError, IndexError):
                    val = 0
            if val > max_sr:
                max_sr = val

        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    return max_sr + 1


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
    if "2-page" in resume_rec_raw or "2 page" in resume_rec_raw.lower():
        resume_rec = "2-page"
    else:
        resume_rec = "1-page"
    notes_text          = analysis.get("notes", "")
    mode                = work_mode(location_raw)
    source              = detect_source(link)

    # Build the Notion page properties payload
    properties = {
        "Job title": {
            "title": [{"text": {"content": title}}]
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
            "select": {"name": tier}
        },
        "Job link": {
            "url": link if link else None
        },
        "Key Skills Needed": {
            "rich_text": [{"text": {"content": ", ".join(key_skills)}}]
        },
        "Resume used": {
            "select": {"name": resume_rec}
        },
        "Notes": {
            "rich_text": [{"text": {"content": notes_text}}]
        },
        "Source": {
            "rich_text": [{"text": {"content": source}}]
        },
    }

    # Add serial number
    properties["Sr."] = {"number": serial_number}

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

# ── Main orchestrator ─────────────────────────────────────────────────────────

def main():
    print("\n========================================")
    print("  Job Search Agent — Starting Run")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("========================================\n")

    # 1. Pull raw jobs from Adzuna
    raw_jobs = fetch_jobs_from_adzuna()

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

    print("\n========================================")
    print(f"  Run complete. {len(saved_jobs)} new listings saved.")
    print("========================================\n")


if __name__ == "__main__":
    main()
