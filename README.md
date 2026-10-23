# Job Tracker for All

[![CI](https://github.com/SincerelyBrittany/job-tracker-for-all/actions/workflows/ci.yml/badge.svg)](https://github.com/SincerelyBrittany/job-tracker-for-all/actions/workflows/ci.yml)

Keep your whole job search in one place. Use it as a simple spreadsheet, or let Claude find remote jobs that fit you, explain why, and draft a tailored resume for each one you approve.

## Not technical? Start here

**[Make your own copy in Google Sheets](https://docs.google.com/spreadsheets/d/1AHKWviWrDwRIljpX6n4s971Eh1itvR0WkVLVHwsazHs/copy)**. One click, and it's yours in your own Google Drive.

It has a **Start Here** tab with step-by-step instructions, a **Tracker** with dropdowns for status and fit, and a **Summary** that counts your applications, replies and weekly progress for you.

Prefer Excel or Numbers? [Download the spreadsheet file](google-sheet/Job-Tracker-Template.xlsx) instead (click the file, then the download button).

---

## The automated version (with Claude Code)

```
fetch_jobs.py ──▶ remote job boards + company career pages
      │            filtered by search_config.py (title, level, location, pay, skills)
      ▼
Claude (job-search skill) ──▶ opens each posting, scores fit 1–5 against profile.md,
      │                        writes "why it fits"
      ▼
tracker.xlsx  (status: To Review) ──▶ you approve ──▶ tailored resume drafted from master-resume.md
                                                       (you apply yourself; nothing is ever sent for you)
```

### What's in the folder

| File | What it is | Yours to edit? |
| --- | --- | --- |
| `profile.example.md` → `profile.md` | What you want: tracks, level, location, pay, resume rules | **Yes** (private, git-ignored) |
| `master-resume.example.md` → `master-resume.md` | Your full resume, the only source for tailored drafts | **Yes** (private, git-ignored) |
| `companies.example.txt` → `companies.txt` | Career pages to check every run | **Yes** (private, git-ignored) |
| `search_config.py` | The filters: salary floor, title words, skills per track | **Yes** |
| `fetch_jobs.py` | Pulls and pre-filters jobs from public feeds | No |
| `tracker.py` | Reads and writes `tracker.xlsx` (dedupes, sets dates) | No |
| `.claude/skills/job-search/SKILL.md` | The instructions Claude follows | Optional |
| `examples/sample-jobs.json` | Made-up jobs for trying it out | No |

### Set it up (about 15 minutes)

1. Click **Use this template** at the top of this page to get your own copy, then clone it.
2. Install Python 3.10+, then:
   ```bash
   pip install -r requirements.txt
   cp profile.example.md profile.md
   cp master-resume.example.md master-resume.md
   cp companies.example.txt companies.txt
   ```
3. Fill in `profile.md` and `master-resume.md` with your real details. Adjust `search_config.py` so its tracks, salary floor and skills match your profile.
4. Try it with sample data:
   ```bash
   python3 tracker.py add "$(cat examples/sample-jobs.json)"
   python3 tracker.py list
   ```
   Delete `tracker.xlsx` when you're done, to start fresh.
5. Open the folder in [Claude Code](https://claude.com/claude-code) and say: **"Run my job search."**

### Using it day to day

| Say to Claude | What happens |
| --- | --- |
| "Run my job search" | Fetches jobs, checks each posting, scores and adds the good ones as **To Review** |
| "Approve rows 4 and 7" | Marks them Approved and drafts a tailored resume for each |
| "I applied to row 4" | Marks it Applied and fills in today's date |
| "What's waiting for me?" | Lists everything still To Review |

Or run the scripts directly:

```bash
python3 fetch_jobs.py --days 14 --limit 60        # candidates as JSON
python3 tracker.py list --status "To Review"
python3 tracker.py update 4 '{"Status": "Applied"}'
```

## Privacy and safety

- Your profile, resume, company list, tracker and drafts are **git-ignored**, so they never get committed by accident.
- Nothing is ever submitted, emailed or applied for you. Claude finds, scores and drafts, and you decide and apply.
- Tailored resumes only reorder and reword what's already in your master resume. They never invent experience.
- Job postings are treated as information, not instructions.

## Development

```bash
pip install -e ".[dev]"
pytest          # tracker behavior + filter rules
ruff check .
```

## License

MIT. Made by [Sincerely Brittany](https://sincerelybrittany.com). If it helps you land something, I'd love to hear about it on [LinkedIn](https://www.linkedin.com/in/sincerelybrittany/).
