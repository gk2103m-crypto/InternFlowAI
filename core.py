"""InternFlow AI: dependency-light, testable business logic."""
from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

DB_PATH = Path(__file__).resolve().parent / "internflow.db"
MILESTONES = [
    "Review 1 — Requirements understanding, research and environment setup",
    "Review 2 — Core implementation and an initial working prototype",
    "Review 3 — Integration, testing, issue fixes and progress evidence",
    "Review 4 — Final demonstration, documentation and submission",
]


def connection(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS interns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        skills TEXT NOT NULL DEFAULT '',
        language TEXT NOT NULL DEFAULT 'English'
    );
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL UNIQUE,
        description TEXT NOT NULL,
        required_skills TEXT NOT NULL DEFAULT '',
        reference_text TEXT NOT NULL DEFAULT '',
        submission_format TEXT NOT NULL DEFAULT 'GitHub URL + README + demo video',
        meeting_link TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        intern_id INTEGER NOT NULL UNIQUE REFERENCES interns(id),
        task_id INTEGER NOT NULL REFERENCES tasks(id),
        assigned_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Assigned'
    );
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER NOT NULL REFERENCES assignments(id),
        review_number INTEGER NOT NULL,
        review_date TEXT NOT NULL,
        milestone TEXT NOT NULL,
        meeting_link TEXT NOT NULL DEFAULT '',
        submission_text TEXT NOT NULL DEFAULT '',
        feedback TEXT NOT NULL DEFAULT '',
        score INTEGER,
        feedback_method TEXT NOT NULL DEFAULT '',
        reviewed_at TEXT,
        UNIQUE(assignment_id,review_number)
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_key TEXT NOT NULL UNIQUE,
        recipient TEXT NOT NULL,
        subject TEXT NOT NULL,
        sent_at TEXT NOT NULL
    );
    """)
    conn.commit()


def rows(conn, query, params=()):
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def add_intern(conn, name, email, skills, language):
    if not name.strip() or not email.strip() or '@' not in email or '.' not in email.rsplit('@', 1)[-1]:
        raise ValueError("Provide a name and valid email address.")
    if language not in ("English", "Tamil", "Hindi"):
        raise ValueError("Language must be English, Tamil, or Hindi.")
    cur = conn.execute("INSERT OR IGNORE INTO interns (name,email,skills,language) VALUES (?,?,?,?)",
                       (name.strip(), email.strip().lower(), skills.strip(), language))
    conn.commit()
    return cur.rowcount


def add_task(conn, title, description, required_skills, reference_text, submission_format, meeting_link):
    if not title.strip() or not description.strip():
        raise ValueError("Task title and description are required.")
    cur = conn.execute("INSERT OR IGNORE INTO tasks (title,description,required_skills,reference_text,submission_format,meeting_link) VALUES (?,?,?,?,?,?)",
        (title.strip(), description.strip(), required_skills.strip(), reference_text.strip(),
         submission_format.strip() or "GitHub URL + README + demo video", meeting_link.strip()))
    conn.commit()
    return cur.rowcount


def skill_terms(text: str) -> set[str]:
    return {x.strip().lower() for x in re.split(r"[,;/|]", text) if x.strip()}


def allocate(conn, first_review: date, gap_days: int = 4, review_count: int = 4) -> list[dict]:
    """Fair skill-based assignment. Existing allocations are untouched (idempotent)."""
    if review_count < 1 or review_count > 8 or gap_days < 1:
        raise ValueError("Invalid review schedule.")
    interns = rows(conn, "SELECT * FROM interns WHERE id NOT IN (SELECT intern_id FROM assignments) ORDER BY id")
    tasks = rows(conn, "SELECT * FROM tasks ORDER BY id")
    if not tasks:
        raise ValueError("Add a task first.")
    if not interns:
        return []
    loads = Counter({x['task_id']: x['n'] for x in rows(conn, "SELECT task_id,COUNT(*) n FROM assignments GROUP BY task_id")})
    results = []
    with conn:
        for person in interns:
            skillset = skill_terms(person['skills'])
            def ranking(task):
                required = skill_terms(task['required_skills'])
                matches = len(skillset & required)
                return (matches * 5 - loads[task['id']] * 2, -loads[task['id']], -task['id'])
            chosen = max(tasks, key=ranking)
            cur = conn.execute("INSERT INTO assignments(intern_id,task_id,assigned_at) VALUES (?,?,?)",
                (person['id'], chosen['id'], datetime.now().isoformat(timespec='seconds')))
            assignment_id = cur.lastrowid
            for index in range(review_count):
                review_date = first_review + timedelta(days=index * gap_days)
                milestone = MILESTONES[index] if index < len(MILESTONES) else f"Review {index+1} — Planned milestone"
                conn.execute("""INSERT INTO reviews(assignment_id,review_number,review_date,milestone,meeting_link)
                                VALUES (?,?,?,?,?)""",
                             (assignment_id, index + 1, review_date.isoformat(), milestone, chosen['meeting_link']))
            loads[chosen['id']] += 1
            results.append({'name': person['name'], 'email': person['email'],
                            'task': chosen['title'], 'assignment_id': assignment_id})
    return results


def assignments(conn):
    return rows(conn, """
        SELECT a.id AS assignment_id, a.status, i.name, i.email, i.skills, i.language,
        t.title, t.description, t.required_skills, t.reference_text, t.submission_format, t.meeting_link,
        (SELECT COUNT(*) FROM reviews r WHERE r.assignment_id=a.id) as total_reviews,
        (SELECT COUNT(*) FROM reviews r WHERE r.assignment_id=a.id AND r.reviewed_at IS NOT NULL) as completed_reviews
        FROM assignments a JOIN interns i ON i.id=a.intern_id JOIN tasks t ON t.id=a.task_id
        ORDER BY a.id
    """)


def reviews_for(conn, assignment_id):
    return rows(conn, "SELECT * FROM reviews WHERE assignment_id=? ORDER BY review_number", (assignment_id,))


def upcoming_reviews(conn, within_days=1, include_past=False):
    start = '1900-01-01' if include_past else date.today().isoformat()
    end = (date.today() + timedelta(days=within_days)).isoformat()
    return rows(conn, """
        SELECT r.*, i.name,i.email,t.title,t.description,t.submission_format
        FROM reviews r JOIN assignments a ON r.assignment_id=a.id
        JOIN interns i ON i.id=a.intern_id JOIN tasks t ON t.id=a.task_id
        WHERE r.review_date BETWEEN ? AND ? AND r.reviewed_at IS NULL
        ORDER BY r.review_date, i.name
    """, (start, end))


def save_feedback(conn, review_id: int, submission: str, feedback: str, method: str, score=None):
    if not submission.strip() or not feedback.strip():
        raise ValueError("Submission and feedback cannot be empty.")
    with conn:
        conn.execute("""UPDATE reviews SET submission_text=?,feedback=?,score=?,feedback_method=?,reviewed_at=?
                        WHERE id=?""", (submission.strip(), feedback.strip(), score, method,
                                        datetime.now().isoformat(timespec='seconds'), review_id))
        conn.execute("""UPDATE assignments SET status='In Progress' WHERE id=(SELECT assignment_id FROM reviews WHERE id=?)""", (review_id,))
        row = conn.execute("SELECT assignment_id FROM reviews WHERE id=?", (review_id,)).fetchone()
        if row:
            pending = conn.execute("SELECT count(*) FROM reviews WHERE assignment_id=? AND reviewed_at IS NULL", (row['assignment_id'],)).fetchone()[0]
            if pending == 0:
                conn.execute("UPDATE assignments SET status='Completed' WHERE id=?", (row['assignment_id'],))


def sent(conn, event_key):
    return conn.execute("SELECT 1 FROM notifications WHERE event_key=?", (event_key,)).fetchone() is not None


def log_sent(conn, event_key, recipient, subject):
    with conn:
        conn.execute("INSERT OR IGNORE INTO notifications (event_key,recipient,subject,sent_at) VALUES (?,?,?,?)",
                     (event_key, recipient, subject, datetime.now().isoformat(timespec='seconds')))


def seed_demo(conn):
    examples = [
        ('Aarav', 'aarav@example.com', 'Python, SQL, FastAPI', 'Hindi'),
        ('Meena', 'meena@example.com', 'Python, Machine Learning, Streamlit', 'Tamil'),
        ('Divya', 'divya@example.com', 'HTML, CSS, JavaScript, React', 'English'),
        ('Rahul', 'rahul@example.com', 'Python, SQL, Data Analysis', 'Hindi'),
    ]
    for p in examples:
        add_intern(conn, *p)
    reference = """Submission requirements:
1. A working application with a clear README and install/run instructions.
2. Source code hosted on GitHub with a meaningful commit history.
3. Validate user input and handle at least two error scenarios.
4. Provide at least three documented test cases.
5. Submit a 2–3 minute demo walkthrough and a final conclusion."""
    items = [
        ('AI FAQ Chatbot', 'Build a chatbot that answers FAQs from a company knowledge base.', 'Python, Machine Learning', reference),
        ('Intern Task Tracker', 'Create a task dashboard showing statuses, review milestones and project progress.', 'React, JavaScript', reference),
        ('Data Insights Dashboard', 'Analyze an intern performance CSV and show trends and charts.', 'Python, SQL, Data Analysis', reference),
    ]
    for title, desc, skills, ref in items:
        add_task(conn, title, desc, skills, ref, 'GitHub repo URL + README + MP4 walkthrough', '')
    return len(examples), len(items)


def assignment_email(assignment, review_items):
    schedule = "\n".join(f"  Review {r['review_number']}: {r['review_date']} — {r['milestone']}\n  Meeting: {r['meeting_link'] or 'Will be shared by coordinator'}"
                         for r in review_items)
    subject = f"[InternFlow AI] Task Assigned: {assignment['title']}"
    body = (f"Hi {assignment['name']},\n\nYou have been assigned the task: {assignment['title']}\n\n"
            f"Task details:\n{assignment['description']}\n\nRequired skills: {assignment['required_skills'] or 'See task brief'}\n"
            f"Submission format: {assignment['submission_format']}\n\nYour milestone review plan:\n{schedule}\n\n"
            "Please submit your progress before each review.\n\nRegards,\nInternFlow AI | Coordinator")
    return subject, body


def reminder_email(record):
    subject = f"[InternFlow AI] Review {record['review_number']} reminder — {record['title']}"
    body = (f"Hi {record['name']},\n\nThis is a reminder for your upcoming review.\n"
            f"Task: {record['title']}\nReview: {record['review_number']}\n"
            f"Review date: {record['review_date']}\nMilestone: {record['milestone']}\n"
            f"Meeting link: {record['meeting_link'] or 'Coordinator will share'}\n"
            f"Submission format: {record['submission_format']}\n\n"
            "Bring a progress report, working proof and blockers.\n\nInternFlow AI")
    return subject, body


def feedback_email(assignment, review, next_review=None):
    subject = f"[InternFlow AI] Review {review['review_number']} feedback — {assignment['title']}"
    body = (f"Hi {assignment['name']},\n\nReview {review['review_number']} feedback for {assignment['title']}:\n\n"
            f"{review['feedback']}\n\n")
    if next_review:
        body += (f"NEXT REVIEW: Review {next_review['review_number']} on {next_review['review_date']}\n"
                 f"Milestone: {next_review['milestone']}\n"
                 f"Meet link: {next_review['meeting_link'] or 'Coordinator will share'}\n\n")
    body += "Keep improving your work.\n\nInternFlow AI"
    return subject, body


def simple_review(reference: str, submission: str, milestone: str) -> dict:
    """Clearly labelled non-AI checklist when no Gemini API key is configured."""
    ref_words = set(re.findall(r"[a-zA-Z]{4,}", reference.lower()))
    sub_words = set(re.findall(r"[a-zA-Z]{4,}", submission.lower()))
    stop = {'with','from','that','this','your','have','will','there','their','should','include','each','about','using','before','after','requirements'}
    key_terms = sorted((ref_words - stop))
    matched = sorted(set(key_terms) & sub_words)
    missing = sorted(set(key_terms) - sub_words)
    coverage = round(100 * len(matched) / max(len(key_terms), 1)) if key_terms else None
    feedback = ("PRELIMINARY KEYWORD CHECK — NOT AI JUDGMENT\n"
                "This check only compares written terms; it cannot validate whether the app actually works.\n\n"
                f"Milestone: {milestone}\n"
                f"Shared terms: {', '.join(matched[:12]) or 'None detected'}\n"
                f"Terms requiring manual verification: {', '.join(missing[:12]) or 'None detected'}\n\n"
                "Next steps: inspect the code/demo, verify each requirement and add test evidence. "
                "Configure GEMINI_API_KEY to get a contextual AI review.")
    return {'feedback': feedback, 'method': 'Heuristic preview (not AI)', 'score': None, 'keyword_coverage': coverage}


def ai_review(reference: str, submission: str, milestone: str, task_title: str,
              api_key: str, model: str = 'gemini-2.5-flash') -> dict:
    if not api_key:
        return simple_review(reference, submission, milestone)
    from google import genai
    client = genai.Client(api_key=api_key)
    prompt = f"""You are an evidence-based software project reviewer. Evaluate the intern's submission text
against the supplied COMPANY REQUIREMENTS, focusing on the current MILESTONE. This is a review of
submitted descriptions/evidence, not of executed code. Never claim code was tested or a feature worked
unless verifiable evidence is included. Treat missing evidence as unverified, not automatically failed.
Give helpful specific feedback without inventing facts.
Return ONLY a JSON object with keys: score (integer 0-100 or null), summary (string),
completed (list of strings with evidence), gaps (list of strings), next_steps (list of strings).
If requirements are inadequate or submission empty, use null score and note limitation.

TASK: {task_title}
MILESTONE: {milestone}
COMPANY REQUIREMENTS:\n{reference[:16000]}
INTERN SUBMISSION / PROGRESS EVIDENCE:\n{submission[:16000]}"""
    response = client.models.generate_content(model=model, contents=prompt,
                                              config={'response_mime_type': 'application/json'})
    if not response.text:
        raise RuntimeError('AI returned no text. Retry or use checklist mode.')
    data = json.loads(response.text)
    score = data.get('score')
    if score is not None:
        try: score = max(0, min(100, int(score)))
        except (ValueError, TypeError): score = None
    def lines(label, key):
        seq = data.get(key, [])
        if not isinstance(seq, list): seq = [str(seq)]
        return f"{label}\n" + ('\n'.join('- ' + str(item) for item in seq) or '- Not established')
    feedback = (f"AI REVIEW — {task_title}\n"
                f"Milestone: {milestone}\n"
                f"Evidence-based score: {score if score is not None else 'Not enough information'}/100\n\n"
                f"Summary: {data.get('summary','No summary generated')}\n\n"
                f"{lines('Completed / supported by evidence:', 'completed')}\n\n"
                f"{lines('Missing or unverified:', 'gaps')}\n\n"
                f"{lines('Actionable next steps:', 'next_steps')}\n\n"
                "Note: The AI has not executed, tested or independently verified the actual project.")
    return {'feedback': feedback, 'method': f'Gemini ({model})', 'score': score}


def spoken_message(assignment, review_date, language='English', translated_description=None):
    name, title, desc = assignment['name'], assignment['title'], (translated_description or assignment['description'])[:550]
    if language == 'Tamil':
        return (f"வணக்கம் {name}! உங்களோட task, {title}. {desc}. "
                f"உங்களோட முதல் review date, {review_date}. "
                "Task instructions, submission format, review meeting link எல்லாமே email-ல அனுப்பியிருக்கோம். "
                "ஏதாவது doubt இருந்தா coordinator-கிட்ட கேளுங்க. All the best!")
    if language == 'Hindi':
        return (f"नमस्ते {name}! आपका task है {title}. {desc}. "
                f"आपका पहला review {review_date} को है. "
                "Task details, submission format और meeting link email में दिए जाएंगे. "
                "कोई doubt हो तो coordinator से पूछ सकते हैं. All the best!")
    return (f"Hi {name}! You've been assigned {title}. Here's what you need to do: {desc}. "
            f"Your first review is on {review_date}. You'll receive the task instructions, "
            "submission format and meeting link by email. Feel free to ask your coordinator if anything's unclear. Good luck!")


def localized_description(description, language, api_key, model='gemini-2.5-flash'):
    if not api_key or language == 'English': return description
    from google import genai
    response = genai.Client(api_key=api_key).models.generate_content(model=model, contents=(
        f"Rewrite the following intern task explanation in casual spoken {language} as used in India, "
        "naturally mixing common English technical terms where useful. Preserve technical requirements, "
        "do not add details. Return only the rewritten explanation:\n" + description[:2000]))
    return response.text.strip() if response.text else description


def extract_file(uploaded):
    """Return readable text for .txt, .md, .pdf and .docx; no OCR for scanned PDFs."""
    name = uploaded.name.lower()
    content = uploaded.getvalue()
    if name.endswith(('.txt', '.md')):
        return content.decode('utf-8-sig', errors='replace')[:30000]
    if name.endswith('.pdf'):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        return '\n'.join(page.extract_text() or '' for page in reader.pages[:25])[:30000]
    if name.endswith('.docx'):
        from docx import Document
        doc = Document(io.BytesIO(content))
        return '\n'.join(p.text for p in doc.paragraphs)[:30000]
    raise ValueError('Only .txt, .md, .pdf and .docx are supported.')


def import_csv(conn, csv_file, kind):
    content = csv_file.getvalue().decode('utf-8-sig')
    records = list(csv.DictReader(io.StringIO(content)))
    added = 0
    for record in records:
        if kind == 'interns':
            added += add_intern(conn, record.get('name',''), record.get('email',''),
                                record.get('skills',''), record.get('language','English'))
        elif kind == 'tasks':
            added += add_task(conn, record.get('title',''), record.get('description',''),
                record.get('required_skills',''), record.get('reference_text',''),
                record.get('submission_format','GitHub repo + README + demo video'), record.get('meeting_link',''))
        else: raise ValueError('Unknown import kind')
    return added, len(records)


def chatbot_reply(conn, message, api_key='', model='gemini-2.5-flash'):
    """Grounded coordinator chat. Local commands work without Gemini."""
    question = message.strip()
    if not question:
        return "Ask me about task allocations, review dates, milestones or progress."
    q = question.casefold()
    all_a = assignments(conn)
    selected = next((a for a in all_a if a['name'].casefold() in q), None)
    if any(s in q for s in ('send mail','send email','email send','mail anuppu')):
        return ('Email sending requires a deliberate confirmation in Task Allocation, Review Studio or '
                'Notifications. I can show the email preview, but will not send messages from an unconfirmed chat command.')
    if (any(s in q for s in ('allocate','assign tasks','assign task','task allocate','task assign','ஒதுக்கு','आवंटित'))
            and not any(s in q for s in ('assigned','assignment status','already'))):
        if not rows(conn,'SELECT * FROM interns') or not rows(conn,'SELECT * FROM tasks'):
            return 'Please add intern and company task records in Setup & Import first.'
        new = allocate(conn,date.today()+timedelta(days=3),4,4)
        if not new:
            return 'Everyone is already assigned. Existing assignments were preserved.'
        return ('I assigned tasks and generated four reviews per intern:\n' +
                '\n'.join(f"• {a['name']}: {a['task']}" for a in new) +
                '\nGo to Task Allocation to check and confirm assignment emails.')
    if selected and any(s in q for s in ('review','milestone','date','eppo','रिव्यू')):
        reviews = reviews_for(conn, selected['assignment_id'])
        return (f"{selected['name']} — {selected['title']}\n" +
                '\n'.join(f"Review {r['review_number']}: {r['review_date']} | "
                          f"{'Completed' if r['reviewed_at'] else 'Pending'} | {r['milestone']}"
                          for r in reviews))
    if selected and any(s in q for s in ('task','assignment','work','velai','काम','project')):
        return (f"{selected['name']} is assigned: {selected['title']}.\n"
                f"Task: {selected['description']}\nSubmission: {selected['submission_format']}\n"
                f"Preferred language: {selected['language']}.")
    if selected and any(s in q for s in ('feedback','score','status','progress')):
        r = reviews_for(conn, selected['assignment_id'])
        complete = [x for x in r if x['reviewed_at']]
        if not complete:
            return f"{selected['name']} has not completed any milestone reviews yet."
        last = complete[-1]
        return (f"{selected['name']} completed {len(complete)}/{len(r)} milestones. "
                f"Latest: Review {last['review_number']}\n{last['feedback'][:800]}")
    if any(s in q for s in ('who','assigned','allocations','list tasks','students','interns','task list')):
        if not all_a: return 'No task assignments yet. Say "allocate tasks" to generate them.'
        return '\n'.join(f"• {a['name']}: {a['title']} ({a['completed_reviews']}/{a['total_reviews']} reviews done)" for a in all_a)
    if any(s in q for s in ('next review','upcoming','reminder','review dates')):
        upcoming = upcoming_reviews(conn,within_days=30)
        if not upcoming: return 'No upcoming reviews in the next 30 days.'
        return '\n'.join(f"• {r['name']} — Review {r['review_number']}: {r['review_date']}" for r in upcoming[:12])
    if api_key:
        from google import genai
        context = '\n'.join(f"{a['name']}: {a['title']}, {a['completed_reviews']}/{a['total_reviews']} reviews"
                            for a in all_a[:30])
        prompt = ("You are InternFlow AI, a concise friendly intern coordinator. Only answer using "
                  "the provided allocation facts when asked about intern records. Never invent dates, emails, "
                  "task assignments, review scores or send confirmations. If a request requires an action, "
                  "direct the user to the appropriate tab. Answer in the same language as the user's message "
                  "where practical.\nAllocation facts:\n" + (context or 'No assignments yet.') +
                  '\nUser question: ' + question[:1000])
        response = genai.Client(api_key=api_key).models.generate_content(model=model,contents=prompt)
        return response.text or 'I could not generate a response. Please try a task or review command.'
    return ('I can help with: "allocate tasks", "show all assignments", '
            '"What is Meena’s task?", "When is Meena’s review?", '
            '"Show upcoming reviews" and "Meena feedback". '
            'For open-ended AI conversation, add a Gemini API key in Settings.')
