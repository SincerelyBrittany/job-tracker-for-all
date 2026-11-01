#!/usr/bin/env python3
"""Pull remote job postings from public feeds, pre-filter them against the search profile,
and print candidates for the job-search skill to verify.

Usage: fetch_jobs.py [--days 14] [--limit 60] [--sources remotive,remoteok,...]

Sources: public APIs/RSS for remote boards, the Hacker News "Who is hiring?" thread, and
company career pages listed in companies.txt. Candidates already in tracker.xlsx are dropped.
Edit search_config.py (and keep it in sync with profile.md) to tailor the filters.
"""
import argparse
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import tracker
from search_config import HOME_LOCATIONS, SALARY_FLOOR, TRACKS

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/128 Safari/537.36"}

# ---- Filters: your settings live in search_config.py ----
YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:[-–]|to)?\s*(?:\d{1,2})?\s*\+?\s*years?(?:'|’)?\s*(?:of\s+)?[^.;]{0,60}?experience", re.I)
US_OK = re.compile(
    r"\b(us|u\.s\.|usa|united states|north america|americas|anywhere|worldwide|global|remote)\b"
    + (f"|{HOME_LOCATIONS}" if HOME_LOCATIONS else ""),
    re.I,
)
NON_US = re.compile(r"\b(india|canada|uk|united kingdom|england|london|europe|emea|germany|berlin|france|spain|portugal|"
                    r"poland|ireland|dublin|netherlands|amsterdam|brazil|latam|latin america|mexico|argentina|colombia|"
                    r"philippines|apac|asia|australia|japan|singapore|israel|south africa|nigeria|kenya|pakistan|"
                    r"romania|ukraine|serbia|turkey|croatia|costa rica|chile|peru|uruguay|vietnam|indonesia|egypt|luxembourg|belgium|"
                    r"switzerland|austria|sweden|norway|denmark|finland|italy|greece|czech|hungary|new zealand|korea|china|"
                    r"taiwan|hong kong|thailand|malaysia|cet|cest|gmt\+)\b", re.I)
US_EXPLICIT = re.compile(r"\b(us|u\.s\.|usa|united states|north america|americas)\b", re.I)
# Freelance marketplaces / staffing agencies (not full-time employers)
COMPANY_EXCLUDE = re.compile(r"lemon\.io|toptal|crossover|turing|andela|talentcross|gun\.io|braintrust|arc\.dev|x-team|"
                             r"proxify|revelo|bairesdev|bluelight|hirequotient|software mind|scale ai|outlier|dataannotation", re.I)
ONSITE = re.compile(r"\b(hybrid|on[\s-]?site|in[\s-]?office)\b", re.I)


def get(url, as_json=True, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return json.loads(data) if as_json else data


def text(s, n=4000):
    s = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(s or "")))
    return re.sub(r"\s+", " ", s).strip()[:n]


PAY_RANGE = re.compile(r"\$\s?(\d[\d,.]*\s*[kK]?)\s*(?:USD)?\s*(?:-|–|—|to)\s*\$?\s?(\d[\d,.]*\s*[kK]?)")


def pay_from_text(t):
    """First '$X - $Y' range in a long posting body (avoids picking up unrelated big numbers)."""
    m = PAY_RANGE.search(t or "")
    return f"{m.group(1)}-{m.group(2)}" if m else ""


def money_max(*vals):
    """Largest annual USD figure found in the given values (numbers or strings), else None."""
    best = None
    for v in vals:
        if v in (None, "", 0, "0"):
            continue
        if isinstance(v, (int, float)):
            nums = [float(v)]
        else:
            nums = []
            for m in re.finditer(r"\$?\s?(\d{1,3}(?:[,.]\d{3})+|\d+(?:\.\d+)?)\s*([kK])?", str(v)):
                n = float(re.sub(r"[,.](?=\d{3}(?:\D|$))", "", m.group(1)))
                if m.group(2):
                    n *= 1000
                nums.append(n)
        for n in nums:
            if 15 <= n < 300:  # hourly
                n *= 2080
            if 20_000 <= n <= 1_500_000:
                best = max(best or 0, n)
    return best


def parse_date(v):
    if not v:
        return None
    try:
        if isinstance(v, (int, float)) or str(v).isdigit():
            return datetime.fromtimestamp(int(v), timezone.utc)
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(v)
        except Exception:
            return None


def job(source, company, title, location, url, posted=None, salary=None, desc="", remote_board=False):
    return {"source": source, "company": (company or "").strip(), "title": (title or "").strip(),
            "location": (location or "").strip(), "url": url, "posted": posted, "salary_text": salary or "",
            "salary_max": money_max(salary), "desc": text(desc), "remote_board": remote_board}


# ---- Sources ----
def remotive():
    d = get("https://remotive.com/api/remote-jobs?category=software-dev&limit=300")
    return [job("Remotive", j["company_name"], j["title"], j["candidate_required_location"], j["url"],
                j["publication_date"], j.get("salary"), j["description"], True) for j in d["jobs"]]


def remoteok():
    d = get("https://remoteok.com/api")
    out = []
    for j in d[1:]:
        sal = f'{j.get("salary_min")}-{j.get("salary_max")}' if str(j.get("salary_max")) not in ("0", "") else ""
        out.append(job("Remote OK", j.get("company"), j.get("position"), j.get("location") or "Remote", j.get("url"),
                       j.get("date"), sal, j.get("description"), True))
    return out


def weworkremotely():
    out = []
    for cat in ["remote-full-stack-programming-jobs", "remote-front-end-programming-jobs",
                "remote-back-end-programming-jobs", "remote-devops-sysadmin-jobs"]:
        root = ET.fromstring(get(f"https://weworkremotely.com/categories/{cat}.rss", as_json=False))
        for it in root.iter("item"):
            t = it.findtext("title") or ""
            company, _, title = t.partition(":")
            out.append(job("We Work Remotely", company, title, it.findtext("region") or "", it.findtext("link"),
                           it.findtext("pubDate"), "", it.findtext("description"), True))
    return out


def himalayas():
    out = []
    for offset in range(0, 400, 20):
        d = get(f"https://himalayas.app/jobs/api?limit=20&offset={offset}")
        for j in d.get("jobs", []):
            cats = " ".join(j.get("categories") or []) + " " + " ".join(j.get("parentCategories") or [])
            if not re.search(r"engineer|developer|software|security|cyber|cloud|devops|compliance|risk", cats + j["title"], re.I):
                continue
            sal = f'{j.get("minSalary") or ""}-{j.get("maxSalary") or ""}' if j.get("maxSalary") else ""
            out.append(job("Himalayas", j["companyName"], j["title"], ", ".join(j.get("locationRestrictions") or []) or "Worldwide",
                           j.get("applicationLink") or j.get("guid"), j.get("pubDate"), sal, j.get("description"), True))
        if len(d.get("jobs", [])) < 20:
            break
    return out


def jobicy():
    d = {"jobs": get("https://jobicy.com/api/v2/remote-jobs?count=100&geo=usa&industry=dev").get("jobs", []) +
         get("https://jobicy.com/api/v2/remote-jobs?count=100&geo=usa&industry=admin").get("jobs", [])}
    return [job("Jobicy", j["companyName"], j["jobTitle"], j.get("jobGeo"), j["url"], j.get("pubDate"),
                f'{j.get("salaryMin") or ""}-{j.get("salaryMax") or ""}' if j.get("salaryMax") else "",
                j.get("jobDescription"), True) for j in d.get("jobs", [])]


def workingnomads():
    d = get("https://www.workingnomads.com/api/exposed_jobs/")
    return [job("Working Nomads", j["company_name"], j["title"], j.get("location"), j["url"], j.get("pub_date"), "",
                j.get("description"), True) for j in d if j.get("category_name") in ("Development", "Administration")]


def hackernews():
    s = get("https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&query=hiring&hitsPerPage=5")
    story = next(h for h in s["hits"] if "who is hiring" in h["title"].lower())
    c = get(f"https://hn.algolia.com/api/v1/search?tags=comment,story_{story['objectID']}&hitsPerPage=1000")
    out = []
    for h in c["hits"]:
        if h.get("parent_id") != int(story["objectID"]):
            continue
        body = text(h.get("comment_text"), 3000)
        if not re.search(r"remote", body, re.I) or not re.search(r"react|typescript|full[\s-]?stack|front[\s-]?end|devops|cloud|security analyst|grc", body, re.I):
            continue
        parts = [p.strip() for p in body.split("|")]
        title = next((p for p in parts[1:4] if classify(p)), "Software Engineer (see post)")
        loc = next((p for p in parts if re.search(r"remote", p, re.I)), "Remote")
        out.append(job("HN Who's Hiring", parts[0][:60], title[:90], loc[:80],
                       f"https://news.ycombinator.com/item?id={h['objectID']}", h.get("created_at"), pay_from_text(body), body))
    return out


def watchlist():
    entries = []
    path = HERE / "companies.txt"
    if not path.exists():
        path = HERE / "companies.example.txt"  # until you create your own list
    for line in path.read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            ats, token = line.split()[:2]
            entries.append((ats, token))

    def one(e):
        ats, token = e
        try:
            if ats == "greenhouse":
                d = get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
                name = token
                return [job(f"Greenhouse ({token})", d.get("company_name") or name, j["title"],
                            (j.get("location") or {}).get("name", ""), j["absolute_url"],
                            j.get("first_published") or j.get("updated_at"), pay_from_text(text(j.get("content"), 20000)),
                            j.get("content")) for j in d.get("jobs", [])]
            if ats == "ashby":
                d = get(f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true")
                out = []
                for j in d.get("jobs", []):
                    comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
                    loc = j.get("location", "")
                    if j.get("isRemote") and "remote" not in loc.lower():
                        loc = f"Remote ({loc})"
                    if j.get("workplaceType") in ("Hybrid", "OnSite"):
                        loc += f" [{j['workplaceType']}]"
                    out.append(job(f"Ashby ({token})", token.title(), j["title"], loc, j.get("jobUrl"),
                                   j.get("publishedAt"), comp, j.get("descriptionPlain") or j.get("descriptionHtml")))
                return out
            if ats == "lever":
                d = get(f"https://api.lever.co/v0/postings/{token}?mode=json")
                out = []
                for j in d:
                    loc = j.get("categories", {}).get("location", "")
                    if j.get("workplaceType") == "remote" and "remote" not in loc.lower():
                        loc = f"Remote ({loc})"
                    rng = j.get("salaryRange") or {}
                    out.append(job(f"Lever ({token})", token.title(), j["text"], loc, j["hostedUrl"],
                                   j.get("createdAt", 0) // 1000 if j.get("createdAt") else None,
                                   f'{rng.get("min", "")}-{rng.get("max", "")}' if rng else "",
                                   j.get("descriptionPlain", "") + " " + j.get("additionalPlain", "")))
                return out
        except Exception as ex:  # noqa: BLE001
            print(f"[warn] {ats}/{token}: {ex}", file=sys.stderr)
        return []

    with ThreadPoolExecutor(12) as ex:
        return [j for batch in ex.map(one, entries) for j in batch]


SOURCES = {"remotive": remotive, "remoteok": remoteok, "weworkremotely": weworkremotely, "himalayas": himalayas,
           "jobicy": jobicy, "workingnomads": workingnomads, "hackernews": hackernews, "watchlist": watchlist}


# ---- Filtering ----
def reject_reason(j, cutoff):
    t, loc = j["title"], j["location"]
    if COMPANY_EXCLUDE.search(j["company"]):
        return "marketplace/agency"
    track = classify(t)
    if not track:
        return "not a target title"
    if TRACKS[track]["exclude"].search(t):
        return f"excluded title/seniority ({track})"
    if ONSITE.search(loc) or ONSITE.search(t):
        return "hybrid/on-site"
    remote = j["remote_board"] or re.search(r"remote|anywhere|distributed", loc, re.I)
    if not remote:
        return "not remote"
    if NON_US.search(loc) and not US_EXPLICIT.search(loc):
        return "non-US location"
    if loc and not US_OK.search(loc):
        return "location unclear/non-US"
    if j["source"].startswith("HN") and not US_EXPLICIT.search(loc):
        return "non-US location"
    if SALARY_FLOOR and j["salary_max"] and j["salary_max"] < SALARY_FLOOR:
        return "below salary floor"
    d = parse_date(j["posted"])
    # Company career pages only list open roles, so allow older postings there.
    if d and d < cutoff - (timedelta(days=16) if j["source"].split(" (")[0] in ("Greenhouse", "Ashby", "Lever") else timedelta()):
        return "too old"
    return None


def classify(title):
    return next((name for name, tr in TRACKS.items() if tr["role"].search(title)), None)


def years_required(desc):
    nums = [int(m.group(1)) for m in YEARS.finditer(desc) if 0 < int(m.group(1)) <= 15]
    return min(nums) if nums else None


def score(j, track):
    tr = TRACKS[track]
    blob = (j["title"] + " " + j["desc"]).lower()
    must = [k for k in tr["must"] if re.search(rf"\b{re.escape(k)}\b", blob)]
    nice = [k for k in tr["nice"] if k in blob]
    pay = min(3, max(0, int((j["salary_max"] - SALARY_FLOOR) // 50_000) + 1)) if j["salary_max"] else 0  # more pay ranks higher
    return len(must) * 2 + len(nice) + pay, must, nice


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--sources", default=",".join(SOURCES))
    a = ap.parse_args()
    cutoff = datetime.now(timezone.utc) - timedelta(days=a.days)

    names = [s for s in a.sources.split(",") if s in SOURCES]
    with ThreadPoolExecutor(len(names)) as ex:
        futs = {n: ex.submit(SOURCES[n]) for n in names}
    raw, stats = [], {}
    for n, f in futs.items():
        try:
            res = f.result()
            stats[n] = {"fetched": len(res)}
            raw += res
        except Exception as e:  # noqa: BLE001
            stats[n] = {"error": str(e)[:120]}

    ws = tracker.init()[tracker.SHEET]
    seen, kept, reasons = set(), [], {}
    for j in raw:
        r = reject_reason(j, cutoff)
        key = (tracker.norm(j["company"]), tracker.norm(j["title"]))
        if not r and (key in seen or tracker.find(ws, j["url"], j["company"], j["title"])):
            r = "duplicate / already tracked"
        if r:
            reasons[r] = reasons.get(r, 0) + 1
            continue
        seen.add(key)
        track = classify(j["title"])
        s, must, nice = score(j, track)
        if len(must) < 2:
            reasons[f"<2 must-have keywords ({track})"] = reasons.get(f"<2 must-have keywords ({track})", 0) + 1
            continue
        yrs = years_required(j["desc"])
        if yrs and yrs >= TRACKS[track]["max_years"]:
            r = f"needs {TRACKS[track]['max_years']}+ yrs ({track})"
            reasons[r] = reasons.get(r, 0) + 1
            continue
        d = parse_date(j["posted"])
        kept.append({"track": track, "years_required": yrs, "company": j["company"], "title": j["title"], "location": j["location"], "url": j["url"],
                     "source": j["source"], "posted": d.date().isoformat() if d else None,
                     "salary": (f"${j['salary_max']:,.0f} max" if j["salary_max"] else "Not listed"),
                     "keyword_score": s, "must_hits": must, "nice_hits": nice, "excerpt": j["desc"][:400]})
    kept.sort(key=lambda k: (k["keyword_score"], k["posted"] or ""), reverse=True)
    # Give each track its share of the output so SWE volume doesn't crowd out Cloud/Cyber.
    by_track = {t: [k for k in kept if k["track"] == t] for t in TRACKS}
    quota = {t: int(a.limit * TRACKS[t].get("share", 1 / len(TRACKS))) for t in TRACKS}
    out = [k for t in TRACKS for k in by_track[t][:quota[t]]]
    out += [k for k in kept if k not in out][:a.limit - len(out)]
    print(json.dumps({"stats": stats, "filtered_out": reasons,
                      "candidates_by_track": {t: len(v) for t, v in by_track.items()},
                      "candidates": out}, indent=1))


if __name__ == "__main__":
    main()
