# InternFlow AI — Demo Recording Script (approximately 2 minutes)

## Screen 1 — Dashboard (0:00–0:15)
"Hello, I developed InternFlow AI, a multilingual AI-assisted intern task allocation and milestone review system. It helps coordinators assign tasks, communicate through natural voices, and monitor intern progress across multiple reviews."

ACTION: Open Dashboard. Click **Load sample demo data** if empty.

## Screen 2 — Task Allocation (0:15–0:40)
"Here we can register or upload multiple interns and task briefs. The system matches required skills to each intern and balances the allocation. With one click, it automatically creates four milestone reviews for every assigned intern. Each email includes the task, submission format, review date and meeting link."

ACTION: Open **Chat Assistant** → type `allocate tasks` → type `When is Meena review?` →
show the 4 review dates. Then open **Task Allocation** → select an intern → show email preview.

## Screen 3 — Natural multilingual voice (0:40–1:00)
"The voice assistant can explain the assignment in English, Tamil and Hindi using neural text-to-speech. I've designed the explanations to feel conversational, and optional AI localization can make the phrasing more natural. This audio can be shared in a live meeting by the host."

ACTION: Select Voice Assistant → Tamil → Generate natural voice → play a short clip. Switch to Hindi briefly if time.

## Screen 4 — AI Review Studio (1:00–1:35)
"In Module 2, each intern has four review milestones. We can upload the company task specification and the intern's progress report. Gemini compares the submitted evidence with the expected requirements and generates a structured review: completed items, missing or unverified items, actionable improvements and an evidence-based score. The feedback is stored for each review."

ACTION: Select Review Studio → Review 1 → upload `company_requirements_sample.txt` and `intern_submission_sample.txt` → Analyze → show saved feedback. NOTE: Gemini key is needed for actual AI comparison.

## Screen 5 — Review loop and emails (1:35–1:55)
"After each review, the feedback can be sent to the intern by email along with the next milestone date. The same process continues from Review 1 through Review 4. The notification page also generates review reminders and tracks successfully sent messages."

ACTION: Scroll to feedback email preview → switch to Notifications → show reminders → Dashboard overview.

## Closing (1:55–2:05)
"For this prototype, I focused on the end-to-end allocation, multilingual voice, document feedback and review lifecycle. Automatic meeting participation and production deployment are planned improvements. Thank you."

## Important recording integrity

- If credentials are missing, say **email preview**, not "email sent".
- If Gemini key is missing, say **keyword checklist**, not "AI analysis".
- The interface does not automatically join Google Meet; the host plays its voice output.
- Use a **single screen recording**, keep code and credentials hidden, and show the GitHub repository at the end if useful.
