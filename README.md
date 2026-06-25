# Job-Search Agent

A serverless agent that runs every weekday morning and does the boring part of a job search for me: it scrapes new Product Manager, Sr PM, and Product Owner listings, scores each one for fit using an LLM, and drops the good matches into a Notion board with a Slack ping. By the time I open my laptop, the shortlist is just *there* — no dashboards to check, no job boards to refresh.

## What it does

- **Scrapes** fresh PM / Sr.PM / PO listings from job APIs on a daily schedule
- **Scores** each listing for fit using an LLM (Llama 3.3 70B via Groq) as High, Medium or Low
- **Logs** the matches to a Notion database, deduped against what it's already seen
- **Alerts** me on Slack with the day's shortlist with top matches highlighted
- **Runs hands-off** — fully serverless on GitHub Actions, on a cron schedule. No server to babysit.

## Stack

| Layer | Tool |
|---|---|
| Language | Python |
| Listings | Adzuna API |
| Scoring | Llama 3.3 70B (Groq) |
| Storage | Notion |
| Alerts | Slack |
| Runtime | GitHub Actions (cron) |

## How it works

```
  GitHub Actions (cron, daily)
            │
            ▼
   Scrape new listings  ──►  Dedupe against Notion
            │
            ▼
   Score each for fit (LLM)
            │
            ▼
   Write matches → Notion  ──►  Slack alert
```

## Notes from building it

A couple of things this project drove home:

- **The "AI" was the easy 10%.** The other 90% was unglamorous plumbing — handling API rate limits, deduping listings, and making sure the thing didn't break silently at 6am.
- **v1 was ugly and barely worked.** That was the point: ship something end-to-end first, then fix it. Scoping a rough MVP and iterating beat trying to design the whole thing up front.

## Setup

The agent runs on GitHub Actions and reads its credentials from repository secrets. To run your own:

1. Clone the repo
2. Add your API keys as GitHub repository secrets (Adzuna, Groq, Notion, Slack)
3. Point the Notion integration at a database with the expected properties
4. Enable the workflow — it runs on the schedule defined in `.github/workflows/`

See the workflow file and config for the exact variables.

---

*Built as a learning project to wire up an LLM agent end-to-end — and to make my own job search a little less of a grind.*
