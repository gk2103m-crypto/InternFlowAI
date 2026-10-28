"""InternFlow AI | Multilingual intern task allocation and review assistant.
Run: streamlit run app.py
"""
from __future__ import annotations

import hashlib
import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from core import (
    connection, initialize, add_intern, add_task, allocate, assignments,
    reviews_for, upcoming_reviews, rows, seed_demo, import_csv,
    assignment_email, reminder_email, feedback_email, simple_review,
    ai_review, spoken_message, localized_description, extract_file,
    sent, log_sent, save_feedback, chatbot_reply,
)
from services import voice_mp3, send_email

load_dotenv()

st.set_page_config(
    page_title='InternFlow AI',
    page_icon='🎙️',
    layout='wide',
    initial_sidebar_state='expanded',
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body, [data-testid="stApp"] {
    font-family: 'Inter', sans-serif;
    background: linear-gradient(155deg, #060e1a 0%, #0a1628 60%, #0d1f3c 100%);
    color: #e8f0fe;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #071020 0%, #0c1a30 100%);
    border-right: 1px solid #1e3a5f;
}
[data-testid="stSidebar"] .stRadio label {
    color: #a8c4e0 !important;
    font-size: 0.88rem;
    padding: 4px 0;
}
[data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] p {
    font-size: 0.88rem;
}

/* Page header */
.page-header {
    background: linear-gradient(90deg, #0f2d52 0%, #1a4a7a 100%);
    border: 1px solid #2a5a8f;
    border-radius: 14px;
    padding: 20px 28px;
    margin-bottom: 24px;
}
.page-header h2 { margin: 0 0 4px 0; font-size: 1.4rem; font-weight: 700; color: #e8f4ff; }
.page-header p  { margin: 0; font-size: 0.84rem; color: #7ab3d6; }

/* Metric cards */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, #0f2947 0%, #152f52 100%);
    border: 1px solid #1e4070;
    border-radius: 14px;
    padding: 18px 22px !important;
    transition: border-color .25s, box-shadow .25s;
}
[data-testid="stMetric"]:hover {
    border-color: #3d7ab8;
    box-shadow: 0 4px 20px rgba(77,150,220,.25);
}
[data-testid="stMetricLabel"] { color: #6ba3c8 !important; font-size: .8rem !important; }
[data-testid="stMetricValue"] { color: #e0f0ff !important; font-size: 2rem !important; font-weight: 700 !important; }

/* Dataframes */
[data-testid="stDataFrame"] {
    border: 1px solid #1e3a5f;
    border-radius: 10px;
    overflow: hidden;
}

/* Buttons */
.stButton button[kind="primary"] {
    background: linear-gradient(135deg, #1565C0 0%, #1976D2 100%);
    border: none;
    border-radius: 8px;
    color: #fff;
    font-weight: 600;
    padding: 10px 20px;
    transition: opacity .2s, transform .15s;
}
.stButton button[kind="primary"]:hover {
    opacity: .9;
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(25,118,210,.45);
}
.stButton button:not([kind="primary"]) {
    border: 1px solid #2a5a8f;
    border-radius: 8px;
    background: transparent;
    color: #a8c4e0;
    font-weight: 500;
    transition: background .2s, border-color .2s;
}
.stButton button:not([kind="primary"]):hover {
    background: #0f2947;
    border-color: #4d96dc;
}

/* Chat */
[data-testid="stChatInput"] input {
    background: #0f2947 !important;
    border: 1px solid #1e4070 !important;
    border-radius: 10px !important;
    color: #e8f0fe !important;
}
[data-testid="chatAvatarIcon-assistant"] { background: #1565C0 !important; }

/* Expanders */
[data-testid="stExpander"] {
    border: 1px solid #1a3558;
    border-radius: 10px;
    background: #0a1828;
}

/* Alerts */
[data-testid="stAlert"] { border-radius: 10px; }

/* Timeline badge */
.milestone-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: .75rem;
    font-weight: 600;
    margin: 2px;
}
.badge-done  { background: #0d3d27; color: #5adf9a; border: 1px solid #1a6644; }
.badge-pending { background: #2d1f00; color: #f0a500; border: 1px solid #5c3e00; }
.badge-score { background: #0d2847; color: #5ab4f5; border: 1px solid #1a4878; }

/* Progress steps */
.steps-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
.step-item {
    flex: 1; min-width: 130px;
    background: #0a1e38;
    border: 1px solid #1a3558;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: .8rem;
    color: #6ba3c8;
}
.step-item strong { display: block; color: #c8dff0; font-size: .88rem; margin-bottom: 2px; }

.block-container { padding-top: 1.2rem; max-width: 1280px; }
h1, h2, h3 { letter-spacing: -.02em; }
</style>
""", unsafe_allow_html=True)

# ── Database init ──────────────────────────────────────────────────────────────
conn = connection()
initialize(conn)


# ── Helpers ────────────────────────────────────────────────────────────────────
def cfg(label: str, fallback: str = '') -> str:
    return st.session_state.get(label, os.getenv(label, fallback))


def email_controls():
    return cfg('SMTP_EMAIL'), cfg('SMTP_APP_PASSWORD')


def email_action(recipient: str, subject: str, body: str, key: str) -> None:
    with st.expander('📨 Preview email before sending', expanded=False):
        st.caption(f'**To:** {recipient}   |   **Subject:** {subject}')
        st.code(body, language='text')
    email, pwd = email_controls()
    if sent(conn, key):
        st.success('✅ This notification was already sent — duplicate blocked.')
    elif not email or not pwd:
        st.info('🔒 **Preview mode** — Configure SMTP credentials in Settings (sidebar) to send real email.')
    elif st.button(f'📤 Send real email → {recipient}', key='send_' + key, type='primary'):
        try:
            send_email(recipient, subject, body, email, pwd,
                       cfg('SMTP_HOST', 'smtp.gmail.com'), int(cfg('SMTP_PORT', '465')))
            log_sent(conn, key, recipient, subject)
            st.success(f'✅ Email successfully sent to {recipient}')
            st.rerun()
        except Exception as exc:
            st.error(f'❌ Email NOT sent: {exc}')


def page_header(title: str, subtitle: str = '') -> None:
    st.markdown(f"""
    <div class="page-header">
        <h2>{title}</h2>
        {'<p>' + subtitle + '</p>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)


def review_status_badge(reviewed_at, score=None) -> str:
    if reviewed_at:
        score_part = f' · {score}/100' if score is not None else ''
        return f'<span class="milestone-badge badge-done">✅ Reviewed{score_part}</span>'
    return '<span class="milestone-badge badge-pending">⏳ Pending</span>'


# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.markdown('## 🎙️ InternFlow AI')
st.sidebar.caption('Shortfundly · AI Engineer Round 2 · MVP')
st.sidebar.divider()

page = st.sidebar.radio(
    'Navigation',
    [
        '📊 Dashboard',
        '💬 Chat Assistant',
        '🗂️ Task Allocation',
        '🎙️ Voice Assistant',
        '🧠 Review Studio',
        '✉️ Notifications',
        '⚙️ Setup & Import',
    ],
    label_visibility='collapsed',
)
st.sidebar.divider()

with st.sidebar.expander('🔑 API Credentials & Settings'):
    st.text_input('Gemini API key', value=cfg('GEMINI_API_KEY'),
                  key='GEMINI_API_KEY', type='password',
                  help='Stored in session only — never saved to Git.')
    st.text_input('Gemini model', value=cfg('GEMINI_MODEL', 'gemini-2.5-flash'),
                  key='GEMINI_MODEL')
    st.text_input('SMTP sender email', value=cfg('SMTP_EMAIL'), key='SMTP_EMAIL')
    st.text_input('SMTP app password', value=cfg('SMTP_APP_PASSWORD'),
                  key='SMTP_APP_PASSWORD', type='password')
    st.caption('⚠️ Do **not** put credentials in Git or share in screen recordings.')

st.sidebar.caption(
    '📌 MVP note: Voice audio plays via browser and can be shared in Google Meet '
    'via screen share. The app does **not** auto-join or speak in Meet calls.'
)

# ── Shared data ────────────────────────────────────────────────────────────────
all_interns = rows(conn, 'SELECT * FROM interns ORDER BY id')
all_tasks = rows(conn, 'SELECT * FROM tasks ORDER BY id')
all_assignments = assignments(conn)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Dashboard
# ══════════════════════════════════════════════════════════════════════════════
if page == '📊 Dashboard':
    page_header('Dashboard', 'Internship coordination at a glance')

    review_total = rows(conn, 'SELECT COUNT(*) as n FROM reviews')[0]['n']
    completed = rows(conn, 'SELECT COUNT(*) as n FROM reviews WHERE reviewed_at IS NOT NULL')[0]['n']

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('👥 Interns', len(all_interns))
    c2.metric('📋 Task Templates', len(all_tasks))
    c3.metric('🔗 Assignments', len(all_assignments))
    c4.metric('🏆 Reviews Done', f'{completed} / {review_total}')

    pct = round(completed / review_total * 100) if review_total else 0
    st.progress(completed / review_total if review_total else 0.0,
                text=f'Milestone completion: {pct}%')

    st.divider()

    col_l, col_r = st.columns([2, 1])

    with col_l:
        st.markdown('#### 📌 Assignment Status')
        if all_assignments:
            df = pd.DataFrame([{
                'Intern': a['name'],
                'Language': a['language'],
                'Assigned Task': a['title'],
                'Reviews': f"{a['completed_reviews']}/{a['total_reviews']}",
                'Status': a['status'],
            } for a in all_assignments])
            st.dataframe(df, hide_index=True, use_container_width=True)
        else:
            st.info('No assignments yet — load demo data below, then go to Task Allocation.')
            if st.button('🚀 Load sample demo data', type='primary'):
                seed_demo(conn)
                st.success('✅ Sample data loaded! Navigate to **Task Allocation** to assign tasks.')
                st.rerun()

    with col_r:
        st.markdown('#### 🗺️ How It Works')
        steps = [
            ('1', 'Import interns & tasks', 'Setup & Import'),
            ('2', 'Skill-match allocation', 'Task Allocation'),
            ('3', 'Voice task briefing', 'Voice Assistant'),
            ('4', 'Email assignment', 'Notifications'),
            ('5', 'Review 1–4 feedback', 'Review Studio'),
            ('6', 'Email feedback loop', 'Notifications'),
        ]
        for num, label, where in steps:
            st.markdown(
                f'<div class="step-item"><strong>Step {num}: {label}</strong>{where}</div>',
                unsafe_allow_html=True,
            )

    if all_assignments:
        st.divider()
        st.markdown('#### 🔔 Upcoming Reviews (Next 7 Days)')
        upcoming = upcoming_reviews(conn, within_days=7)
        if upcoming:
            df_up = pd.DataFrame([{
                'Intern': r['name'],
                'Task': r['title'],
                'Review': r['review_number'],
                'Date': r['review_date'],
                'Milestone': r['milestone'],
            } for r in upcoming])
            st.dataframe(df_up, hide_index=True, use_container_width=True)
        else:
            st.caption('No pending reviews in the next 7 days.')


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Chat Assistant
# ══════════════════════════════════════════════════════════════════════════════
elif page == '💬 Chat Assistant':
    page_header('Chat Assistant',
                'Ask questions about intern tasks, review dates and allocation status. '
                'This text chat can be screen-shared in Google Meet.')

    st.caption('💡 Try: `allocate tasks` · `show all assignments` · `When is Meena review?` · `What is Aarav task?`')

    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = [{
            'role': 'assistant',
            'content': (
                "Hi! I'm **InternFlow AI**. I can allocate tasks, show intern assignments "
                "and look up milestone review schedules.\n\n"
                "Type `allocate tasks` to get started, or ask about any intern by name."
            ),
        }]

    for msg in st.session_state.chat_history:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])

    message = st.chat_input('Ask about interns, allocations or review milestones…')
    if message:
        st.session_state.chat_history.append({'role': 'user', 'content': message})
        try:
            answer = chatbot_reply(
                conn, message,
                cfg('GEMINI_API_KEY'),
                cfg('GEMINI_MODEL', 'gemini-2.5-flash'),
            )
        except Exception as exc:
            answer = f'⚠️ Unable to process this request: {exc}'
        st.session_state.chat_history.append({'role': 'assistant', 'content': answer})
        st.rerun()

    if st.button('🗑️ Clear chat history'):
        del st.session_state['chat_history']
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Task Allocation
# ══════════════════════════════════════════════════════════════════════════════
elif page == '🗂️ Task Allocation':
    page_header('Task Allocation',
                'Skill-aware matching with workload balancing. Existing allocations are preserved.')

    if not all_interns or not all_tasks:
        st.warning('⚠️ Add interns and tasks in **Setup & Import** first.')
    else:
        with st.container():
            st.markdown('#### ⚙️ Allocation Parameters')
            left, right, third = st.columns(3)
            first_date = left.date_input('First review date', value=date.today() + timedelta(days=3))
            gap_days = right.number_input('Days between reviews', min_value=1, max_value=30, value=4)
            review_count = third.number_input('Reviews per intern', min_value=1, max_value=4, value=4)
            st.caption(f'**{len(all_interns)}** interns · **{len(all_tasks)}** task templates · '
                       f'Default: 4 milestone reviews per intern')

            if st.button('✨ Allocate tasks & create review schedule', type='primary'):
                try:
                    result = allocate(conn, first_date, int(gap_days), int(review_count))
                    if not result:
                        st.info('ℹ️ All registered interns are already assigned. Existing data is unchanged.')
                    else:
                        st.success(
                            f'✅ Allocated **{len(result)}** interns and created '
                            f'**{len(result) * int(review_count)}** review milestones!'
                        )
                    st.rerun()
                except Exception as exc:
                    st.error(f'❌ {exc}')

    if all_assignments:
        st.divider()
        st.markdown('#### 📋 Generated Assignments')
        df = pd.DataFrame([{
            'Intern': a['name'],
            'Email': a['email'],
            'Skills': a['skills'],
            'Assigned Task': a['title'],
            'Reviews': f"{a['completed_reviews']}/{a['total_reviews']}",
            'Status': a['status'],
        } for a in all_assignments])
        st.dataframe(df, hide_index=True, use_container_width=True)

        st.divider()
        st.markdown('#### 📧 Assignment Email Preview')
        select = st.selectbox(
            'Select intern to preview assignment email',
            all_assignments,
            format_func=lambda a: f"{a['name']} — {a['title']}",
        )
        review_items = reviews_for(conn, select['assignment_id'])
        subject, body = assignment_email(select, review_items)
        email_action(select['email'], subject, body, f"assignment:{select['assignment_id']}")

        with st.expander('📬 Bulk send — all unsent assignment emails'):
            st.caption('Sends only emails not yet logged. Uses real SMTP — not a simulated send.')
            st.warning('Verify email addresses before bulk sending. `@example.com` cannot receive mail.')
            if st.button('Send all unsent assignment emails', key='bulk_assign'):
                sender, password = email_controls()
                if not sender or not password:
                    st.error('Set SMTP credentials in the sidebar first.')
                else:
                    good, failures = 0, []
                    for a in all_assignments:
                        key = f"assignment:{a['assignment_id']}"
                        if sent(conn, key):
                            continue
                        sub, bod = assignment_email(a, reviews_for(conn, a['assignment_id']))
                        try:
                            send_email(a['email'], sub, bod, sender, password,
                                       cfg('SMTP_HOST', 'smtp.gmail.com'),
                                       int(cfg('SMTP_PORT', '465')))
                            log_sent(conn, key, a['email'], sub)
                            good += 1
                        except Exception as exc:
                            failures.append(f"{a['email']}: {exc}")
                    if good:
                        st.success(f'✅ {good} real email(s) sent.')
                    else:
                        st.info('No new emails sent.')
                    if failures:
                        st.error('Failures:\n' + '\n'.join(failures))


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Voice Assistant
# ══════════════════════════════════════════════════════════════════════════════
elif page == '🎙️ Voice Assistant':
    page_header('Voice Assistant',
                'Neural voice briefing (English · Tamil · Hindi). '
                'Play in-browser or share via screen in Google Meet.')

    if not all_assignments:
        st.warning('⚠️ Allocate tasks first before generating voice briefings.')
    else:
        left_col, right_col = st.columns([2, 1])

        with left_col:
            select = st.selectbox(
                'Choose intern to address',
                all_assignments,
                format_func=lambda a: f"{a['name']} — {a['title']}",
            )
            language = st.selectbox(
                'Voice language',
                ['English', 'Tamil', 'Hindi'],
                index=['English', 'Tamil', 'Hindi'].index(select['language']),
            )
            reviews = reviews_for(conn, select['assignment_id'])
            first_review = reviews[0]['review_date'] if reviews else 'TBD'

            localized = select['description']
            if st.checkbox('Use Gemini to naturally localize the task explanation (optional)'):
                if not cfg('GEMINI_API_KEY'):
                    st.warning('Gemini API key not configured; using the original description.')
                else:
                    try:
                        with st.spinner('Localizing task description…'):
                            localized = localized_description(
                                select['description'], language,
                                cfg('GEMINI_API_KEY'),
                                cfg('GEMINI_MODEL', 'gemini-2.5-flash'),
                            )
                    except Exception as exc:
                        st.warning(f'AI localization unavailable: {exc}')

            script = spoken_message(select, first_review, language, localized)
            script = st.text_area('📝 Spoken script (editable before generating)', script, height=200)

            if st.button('🔊 Generate neural voice', type='primary'):
                if not script.strip():
                    st.error('Script is empty. Cannot generate audio.')
                else:
                    try:
                        with st.spinner('Generating neural audio via Edge TTS…'):
                            audio = voice_mp3(script, language)
                        st.session_state['voice_output'] = (select['assignment_id'], language, audio)
                        st.success('✅ Audio generated!')
                    except Exception as exc:
                        st.error(f'❌ Neural audio unavailable: {exc}')
                        st.caption('Check internet connectivity — Edge TTS requires an online connection.')

        with right_col:
            st.markdown('#### 🔈 Audio Playback')
            output = st.session_state.get('voice_output')
            if output and output[0] == select['assignment_id'] and output[1] == language:
                st.audio(output[2], format='audio/mp3')
                st.download_button(
                    '⬇️ Download MP3',
                    output[2],
                    file_name=f"briefing_{select['name'].lower().replace(' ', '_')}.mp3",
                    mime='audio/mpeg',
                )
            else:
                st.info('Audio will appear here after generation.')

            st.markdown('#### 🗣️ Voice Profiles')
            voice_info = {
                'English': 'Neerja Neural (en-IN)',
                'Tamil': 'Pallavi Neural (ta-IN)',
                'Hindi': 'Swara Neural (hi-IN)',
            }
            for lang, profile in voice_info.items():
                st.markdown(f'- **{lang}**: {profile}')

            st.caption(
                'Mixed-language pronunciation varies by neural voice. '
                'English-only, Tamil and Hindi scripts are supported.'
            )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Review Studio
# ══════════════════════════════════════════════════════════════════════════════
elif page == '🧠 Review Studio':
    page_header('Review Studio',
                'Four-milestone evidence review: compare company requirements vs intern submission.')

    if not all_assignments:
        st.warning('⚠️ Allocate tasks first to enable reviews.')
    else:
        select = st.selectbox(
            'Choose intern',
            all_assignments,
            format_func=lambda a: f"{a['name']} — {a['title']}",
        )
        items = reviews_for(conn, select['assignment_id'])

        if not items:
            st.warning('No reviews set for this intern.')
        else:
            # ── Milestone Timeline ──────────────────────────────────────────
            st.markdown('#### 🗓️ Four-Stage Milestone Timeline')

            # Visual timeline
            timeline_cols = st.columns(len(items))
            for i, (col, rev) in enumerate(zip(timeline_cols, items)):
                with col:
                    is_done = bool(rev['reviewed_at'])
                    score_txt = f'Score: {rev["score"]}/100' if rev.get('score') is not None else ''
                    badge = '✅' if is_done else '⏳'
                    color = '#0d3d27' if is_done else '#2d1f00'
                    border = '#1a6644' if is_done else '#5c3e00'
                    st.markdown(f"""
                    <div style="background:{color};border:1px solid {border};border-radius:10px;
                                padding:14px;text-align:center;font-size:.82rem;">
                        <div style="font-size:1.4rem">{badge}</div>
                        <strong style="color:#dce8ff">Review {rev['review_number']}</strong><br>
                        <span style="color:#8ab4d0">{rev['review_date']}</span><br>
                        <span style="color:#6ba3c8;font-size:.75rem">{score_txt}</span>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown('')

            # Detailed table
            df = pd.DataFrame([{
                'Review': r['review_number'],
                'Date': r['review_date'],
                'Milestone': r['milestone'][:60] + ('…' if len(r['milestone']) > 60 else ''),
                'Result': '✅ Reviewed' if r['reviewed_at'] else '⏳ Pending',
                'AI Score': r['score'] if r['score'] is not None else '—',
                'Method': r['feedback_method'] or '—',
            } for r in items])
            st.dataframe(df, hide_index=True, use_container_width=True)

            st.divider()

            # ── Select milestone ────────────────────────────────────────────
            chosen = st.selectbox(
                'Select milestone to review',
                items,
                format_func=lambda r: (
                    f"Review {r['review_number']} — {r['review_date']} "
                    f"({'✅ Done' if r['reviewed_at'] else '⏳ Pending'})"
                ),
            )

            st.info(f"📍 **Milestone {chosen['review_number']}:** {chosen['milestone']}")

            # ── Customize milestone ─────────────────────────────────────────
            with st.expander('🗓️ Customize this milestone / meeting URL'):
                with st.form(f"customize_review_{chosen['id']}"):
                    custom_milestone = st.text_input('Milestone description', value=chosen['milestone'])
                    custom_date = st.date_input('Review date',
                                               value=date.fromisoformat(chosen['review_date']))
                    custom_link = st.text_input('Meeting URL (Google Meet, Zoom, etc.)',
                                               value=chosen['meeting_link'])
                    if st.form_submit_button('💾 Save review schedule'):
                        with conn:
                            conn.execute(
                                'UPDATE reviews SET milestone=?,review_date=?,meeting_link=? WHERE id=?',
                                (custom_milestone.strip(), custom_date.isoformat(),
                                 custom_link.strip(), chosen['id']),
                            )
                        st.success('✅ Review schedule updated.')
                        st.rerun()

            # ── Evidence inputs ─────────────────────────────────────────────
            st.markdown('#### 📄 Evidence Comparison')
            ev_left, ev_right = st.columns(2)

            with ev_left:
                st.markdown('**Company Requirements / Expected Deliverables**')
                reference = st.text_area(
                    'Paste requirements here',
                    value=select['reference_text'] or select['description'],
                    height=180,
                    key=f"reference_{chosen['id']}",
                    label_visibility='collapsed',
                )
                spec_upload = st.file_uploader(
                    'Or upload requirement doc (PDF/DOCX/TXT)',
                    type=['pdf', 'docx', 'txt', 'md'],
                    key=f"spec_{chosen['id']}",
                )
                if spec_upload:
                    try:
                        reference = extract_file(spec_upload)
                        if not reference.strip():
                            st.warning('Document has no extractable text (scanned PDFs need OCR).')
                        else:
                            st.caption(f'✅ Extracted {len(reference):,} characters of requirements.')
                    except Exception as exc:
                        st.error(f'Could not read requirement document: {exc}')

            with ev_right:
                st.markdown('**Intern Progress / Submission Evidence**')
                submission = st.text_area(
                    'Paste submission here',
                    value=chosen['submission_text'],
                    height=180,
                    placeholder='Paste progress summary, code walkthrough or submission details here.',
                    key=f"submission_{chosen['id']}",
                    label_visibility='collapsed',
                )
                uploaded = st.file_uploader(
                    'Or upload intern submission (PDF/DOCX/TXT)',
                    type=['pdf', 'docx', 'txt', 'md'],
                    key=f"sub_{chosen['id']}",
                )
                if uploaded:
                    try:
                        submission = extract_file(uploaded)
                        if not submission.strip():
                            st.warning('Uploaded file has no extractable text.')
                        else:
                            st.caption(f'✅ Extracted {len(submission):,} characters from submission.')
                    except Exception as exc:
                        st.error(f'Could not read submission: {exc}')

            # ── AI Analysis ─────────────────────────────────────────────────
            gemini_active = bool(cfg('GEMINI_API_KEY'))
            btn_label = '🧠 Analyze with Gemini AI' if gemini_active else '🔍 Run keyword checklist (no API key)'

            if st.button(btn_label, type='primary'):
                if not reference.strip() or not submission.strip():
                    st.error('Both company requirements and intern submission are required.')
                else:
                    try:
                        with st.spinner('Evaluating evidence and milestone coverage…'):
                            review = ai_review(
                                reference, submission,
                                chosen['milestone'], select['title'],
                                cfg('GEMINI_API_KEY'),
                                cfg('GEMINI_MODEL', 'gemini-2.5-flash'),
                            )
                        save_feedback(conn, chosen['id'], submission,
                                      review['feedback'], review['method'],
                                      review.get('score'))
                        st.success(f"✅ Review saved — method: **{review['method']}**")
                        st.rerun()
                    except Exception as exc:
                        st.error(f'❌ Review failed (not saved): {exc}')
                        st.caption('Check API key / model / network, or remove key for keyword checklist mode.')

            # ── Saved Feedback ──────────────────────────────────────────────
            latest = next(
                (r for r in reviews_for(conn, select['assignment_id']) if r['id'] == chosen['id']),
                None,
            )
            if latest and latest['reviewed_at']:
                st.divider()
                st.markdown('#### 💬 Saved Review Feedback')

                method = latest.get('feedback_method', '')
                if method.startswith('Heuristic'):
                    st.warning(
                        '⚠️ This is a **keyword-only preliminary checklist**, not AI evaluation. '
                        'Add a Gemini API key in Settings for evidence-based AI feedback.'
                    )
                else:
                    st.success(f'AI review performed via **{method}**')

                if latest.get('score') is not None:
                    score_pct = latest['score'] / 100
                    st.progress(score_pct, text=f"Evidence-based score: {latest['score']}/100")

                st.code(latest['feedback'], language='text', wrap_lines=True)

                # Email feedback
                next_rev = next(
                    (r for r in items if r['review_number'] == latest['review_number'] + 1), None
                )
                subject, body = feedback_email(select, latest, next_rev)
                version = hashlib.sha256(latest['feedback'].encode()).hexdigest()[:12]
                email_action(select['email'], subject, body,
                             f"feedback:{latest['id']}:{version}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Notifications
# ══════════════════════════════════════════════════════════════════════════════
elif page == '✉️ Notifications':
    page_header('Notifications',
                'Milestone reminders and email delivery log. '
                'Production deployments would use a scheduled cron worker.')

    st.markdown('#### 🔔 Upcoming Review Reminders')
    horizon = st.selectbox(
        'Reminder window',
        ['Next 2 days', 'Next 7 days', 'All scheduled reviews'],
        index=1,
    )
    days = {'Next 2 days': 2, 'Next 7 days': 7, 'All scheduled reviews': 365}[horizon]
    upcoming = upcoming_reviews(conn, within_days=days)

    if not upcoming:
        st.info('✅ No unreviewed milestones within this window.')
    else:
        st.dataframe(
            pd.DataFrame([{
                'Intern': r['name'],
                'Task': r['title'],
                'Review': r['review_number'],
                'Date': r['review_date'],
                'Milestone': r['milestone'][:55] + ('…' if len(r['milestone']) > 55 else ''),
                'Email': r['email'],
            } for r in upcoming]),
            hide_index=True,
            use_container_width=True,
        )

        record = st.selectbox(
            'Choose reminder to preview / send',
            upcoming,
            format_func=lambda r: f"{r['name']} | Review {r['review_number']} | {r['review_date']}",
        )
        subject, body = reminder_email(record)
        email_action(record['email'], subject, body, f"reminder:{record['id']}")

        with st.expander('📤 Bulk send — all pending reminders in window'):
            st.warning('⚠️ This sends **real** messages to recipients. Verify addresses and dates first.')
            if st.button('Confirm: send all unsent reminders', key='bulk_remind'):
                sender, password = email_controls()
                if not sender or not password:
                    st.error('Configure SMTP credentials in the sidebar first.')
                else:
                    good, failed = 0, []
                    for r in upcoming:
                        k = f"reminder:{r['id']}"
                        if sent(conn, k):
                            continue
                        sub, bod = reminder_email(r)
                        try:
                            send_email(r['email'], sub, bod, sender, password,
                                       cfg('SMTP_HOST', 'smtp.gmail.com'),
                                       int(cfg('SMTP_PORT', '465')))
                            log_sent(conn, k, r['email'], sub)
                            good += 1
                        except Exception as exc:
                            failed.append(f"{r['email']}: {exc}")
                    if good:
                        st.success(f'✅ {good} reminder(s) sent successfully.')
                    else:
                        st.info('No new reminders sent.')
                    if failed:
                        st.error('Failures:\n' + '\n'.join(failed))

    st.divider()
    st.markdown('#### 📬 Sent Email Log (Last 25)')
    logs = rows(conn, 'SELECT recipient, subject, sent_at FROM notifications ORDER BY id DESC LIMIT 25')
    if logs:
        st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
    else:
        st.caption('No emails sent yet. Email previews do **not** appear as delivered.')


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Setup & Import
# ══════════════════════════════════════════════════════════════════════════════
elif page == '⚙️ Setup & Import':
    page_header('Setup & Import', 'Configure interns, company tasks and project specifications.')

    demo_col, _ = st.columns([1, 2])
    with demo_col:
        if st.button('🎬 Load sample demo data (4 interns + 3 tasks)', type='primary'):
            n, t = seed_demo(conn)
            st.success(f'✅ Demo data loaded: {n} interns and {t} task templates.')
            st.rerun()

    st.divider()

    # ── Manual add forms ────────────────────────────────────────────────────
    left, right = st.columns(2)

    with left:
        st.markdown('#### 👤 Add an Intern')
        with st.form('add_intern'):
            name = st.text_input('Full name')
            email = st.text_input('Email address')
            skills = st.text_input('Skills (comma-separated)', placeholder='Python, SQL, NLP')
            language = st.selectbox('Preferred language', ['English', 'Tamil', 'Hindi'])
            if st.form_submit_button('💾 Save intern'):
                try:
                    count = add_intern(conn, name, email, skills, language)
                    if count:
                        st.success('✅ Intern added!')
                    else:
                        st.info('Email already exists — no duplicate added.')
                except Exception as exc:
                    st.error(str(exc))

    with right:
        st.markdown('#### 📋 Add a Project / Task')
        with st.form('add_task'):
            title = st.text_input('Task title')
            desc = st.text_area('Task instructions', height=80)
            req = st.text_input('Required skills', placeholder='Python, SQL')
            reference = st.text_area('Company rubric / expected deliverables', height=100)
            fmt = st.text_input('Submission format', value='GitHub URL + README + demo video')
            meet = st.text_input('Google Meet URL (optional)')
            if st.form_submit_button('💾 Save task'):
                try:
                    count = add_task(conn, title, desc, req, reference, fmt, meet)
                    if count:
                        st.success('✅ Task saved!')
                    else:
                        st.info('Task title already exists — no duplicate added.')
                except Exception as exc:
                    st.error(str(exc))

    st.divider()

    # ── CSV import ──────────────────────────────────────────────────────────
    st.markdown('#### 📥 Bulk CSV Import')
    l, r = st.columns(2)

    with l:
        st.markdown('**Interns CSV** — columns: `name, email, skills, language`')
        incoming = st.file_uploader('Upload intern CSV', type=['csv'], key='intern_csv')
        if incoming and st.button('Import intern CSV'):
            try:
                n, total = import_csv(conn, incoming, 'interns')
                st.success(f'✅ Added {n} of {total} records.')
                st.rerun()
            except Exception as exc:
                st.error(f'Import aborted: {exc}')

    with r:
        st.markdown('**Tasks CSV** — columns: `title, description, required_skills, reference_text, submission_format, meeting_link`')
        incoming_t = st.file_uploader('Upload task CSV', type=['csv'], key='task_csv')
        if incoming_t and st.button('Import task CSV'):
            try:
                n, total = import_csv(conn, incoming_t, 'tasks')
                st.success(f'✅ Added {n} of {total} records.')
                st.rerun()
            except Exception as exc:
                st.error(f'Import aborted: {exc}')

    st.divider()
    st.caption(
        '🔒 Uploaded text is stored locally in SQLite. '
        'Avoid using real confidential company or intern data in a public demo.'
    )

    with st.expander('📊 Current interns and task templates'):
        if all_interns:
            st.markdown('**Interns**')
            st.dataframe(pd.DataFrame(all_interns), hide_index=True, use_container_width=True)
        else:
            st.caption('No interns yet.')
        if all_tasks:
            st.markdown('**Task Templates**')
            st.dataframe(pd.DataFrame(all_tasks), hide_index=True, use_container_width=True)
        else:
            st.caption('No tasks yet.')
