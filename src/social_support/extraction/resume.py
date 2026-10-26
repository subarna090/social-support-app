"""Resume: jobs, education and skills; months employed in the last 24 (research R1, R4).

The months calculation mirrors ``synthetic.profile.months_employed_last_24`` (extraction may not
import ``synthetic``): the window is the 24 full months before the as-of month.
"""

import re
from datetime import date, datetime

from social_support.domain.documents import DocumentType, ExtractedDocument
from social_support.extraction.common import result
from social_support.extraction.pdf_text import pdf_text

# "Title, Employer (Demo) (Feb 2025 - Present)". Long lines may wrap, so sections are joined first.
JOB = re.compile(
    r"(?P<title>[^,()]+?),\s(?P<employer>.+?)\s\((?P<start>[A-Z][a-z]{2} \d{4})\s-\s"
    r"(?P<end>[A-Z][a-z]{2} \d{4}|Present)\)"
)
NO_HISTORY = "No employment history"


def _month_index(day: date) -> int:
    return day.year * 12 + day.month - 1


def _month(label: str) -> int:
    return _month_index(datetime.strptime(label, "%b %Y").date())


def _section(lines: list[str], heading: str, next_heading: str | None) -> str:
    if heading not in lines:
        return ""
    start = lines.index(heading) + 1
    rest = lines[start:]
    end = rest.index(next_heading) if next_heading in rest else len(rest)
    return " ".join(rest[:end])


def parse_text(text: str, as_of: date) -> ExtractedDocument:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    history = _section(lines, "Employment history", "Education")

    window_end = _month_index(as_of) - 1
    window = range(window_end - 23, window_end + 1)
    covered: set[int] = set()
    total_months, jobs = 0, []
    for match in JOB.finditer(history):
        start = _month(match["start"])
        end = window_end if match["end"] == "Present" else _month(match["end"])
        span = range(start, end + 1)
        covered.update(m for m in span if m in window)
        total_months += len(span)
        jobs.append(f"{match['title'].strip()} ({match['start']} - {match['end']})")

    # Neither a job nor the explicit "none" means the section was not read: leave it missing.
    read = bool(jobs) or NO_HISTORY in history
    fields = {
        "months_employed_last_24": str(len(covered)) if read else "",
        "years_experience": f"{total_months / 12:.1f}",
        "last_job_title": jobs[0].split(" (")[0] if jobs else "",
        "education": _section(lines, "Education", "Skills"),
    }
    skills = tuple(s.strip() for s in _section(lines, "Skills", None).split(",") if s.strip())
    return result(DocumentType.RESUME, fields, items={"skills": skills, "jobs": tuple(jobs)})


def parse(data: bytes, as_of: date) -> ExtractedDocument:
    return parse_text(pdf_text(data), as_of)
