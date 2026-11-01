"""Your search settings. This is the only Python file you need to edit.

fetch_jobs.py reads everything here. Keep it in sync with profile.md, which is what the
Claude skill reads when it explains why a job fits you.

The defaults below are an EXAMPLE for someone looking at three kinds of roles: software
engineering (SWE), cloud, and entry-level security (Cyber). Rename, remove or add tracks
to match your own search.
"""

import re

# Jobs that list a maximum salary below this are skipped. Set to 0 to turn the filter off.
SALARY_FLOOR = 80_000

# Only remote jobs are kept. Locations that count as "OK for me" (besides the US-wide
# words already understood: US, USA, United States, North America, anywhere, remote).
# Add your state or city, e.g. r"\b(ny|new york)\b".
HOME_LOCATIONS = r""

# Words in a title that mean "too senior for me" and "not the kind of job I want".
SENIOR_PLUS = r"staff|principal|distinguished|director|manager|head of|vp|architect|lead"
COMMON_EXCLUDE = (
    r"intern|internship|sales|pre[\s-]?sales|account executive|recruit|contract|contractor|freelance|"
    r"part[\s-]?time|commission|marketing"
)

# Each job goes into the FIRST track whose `role` pattern matches its title, so order matters.
#   role:      title pattern for this track
#   exclude:   title words that rule a job out for this track
#   must:      skills; a job needs at least 2 of these in its title or description
#   nice:      extra skills that push a job up the list
#   max_years: skip jobs asking for this many years of experience or more
#   share:     fraction of the results to give this track, so one track can't crowd out the rest
TRACKS = {
    "Cyber": {
        "role": re.compile(
            r"(security|cyber|\bsoc\b|\bgrc\b|risk|compliance|privacy|vulnerability|threat|incident|"
            r"\biam\b|identity|detection).*(analyst|specialist|associate|engineer)|"
            r"(analyst|specialist|associate).*(security|cyber|\bsoc\b|\bgrc\b|risk|compliance|privacy)",
            re.I,
        ),
        "exclude": re.compile(rf"\b({SENIOR_PLUS}|senior|sr\.?|{COMMON_EXCLUDE}|clearance|ts/sci|polygraph)\b", re.I),
        "must": ["security", "soc", "siem", "incident", "vulnerability", "risk", "compliance", "nist",
                 "privacy", "iam", "audit", "splunk", "threat"],
        "nice": ["python", "aws", "cloud", "phishing", "entry", "junior", "associate", "security+",
                 "training provided"],
        "max_years": 3,
        "share": 0.2,
    },
    "Cloud": {
        "role": re.compile(r"\bcloud\b|devops|site reliability|\bsre\b|\baws\b|infrastructure engineer", re.I),
        "exclude": re.compile(rf"\b({SENIOR_PLUS}|senior|sr\.?|{COMMON_EXCLUDE}|clearance)\b", re.I),
        "must": ["aws", "azure", "gcp", "cloud", "docker", "ci/cd", "linux", "python", "terraform",
                 "kubernetes"],
        "nice": ["entry", "junior", "associate", "monitoring", "bash", "github actions", "serverless"],
        "max_years": 4,
        "share": 0.2,
    },
    "SWE": {
        "role": re.compile(
            r"(software|front[\s-]?end|full[\s-]?stack|back[\s-]?end|\bweb\b|platform|application)"
            r".*(engineer|developer)|developer|\bswe\b",
            re.I,
        ),
        "exclude": re.compile(
            rf"\b({SENIOR_PLUS}|{COMMON_EXCLUDE}|qa|quality|test|sdet|support|embedded|firmware|hardware)\b", re.I
        ),
        "must": ["javascript", "typescript", "react", "node", "python", "java", "api", "sql"],
        "nice": ["aws", "docker", "postgres", "graphql", "testing", "ci/cd", "accessibility"],
        "max_years": 6,
        "share": 0.6,
    },
}
