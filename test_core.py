"""Unit tests for InternFlow AI core business logic.
Run: python -m unittest -v test_core.py
"""
import unittest
from datetime import date, timedelta
from core import (
    connection, initialize, add_intern, add_task, allocate, assignments,
    reviews_for, rows, save_feedback, simple_review, sent, log_sent,
    spoken_message, chatbot_reply, assignment_email, reminder_email,
    feedback_email, upcoming_reviews, import_csv, seed_demo,
)




class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.db = connection(':memory:')
        initialize(self.db)
        add_intern(self.db, 'Meena', 'meena@test.example', 'Python, SQL', 'Tamil')
        add_intern(self.db, 'Hari', 'hari@test.example', 'React, JavaScript', 'English')
        add_task(self.db, 'ML Bot', 'Build ML chatbot', 'Python, SQL',
                 'Working app with README and tests', 'GitHub + video', '')
        add_task(self.db, 'Frontend', 'Build a React dashboard', 'React, JavaScript',
                 'Working dashboard with tests', 'GitHub + video', '')

    def tearDown(self):
        self.db.close()

    # ── Allocation & skill matching ──────────────────────────────────────────

    def test_matching_and_four_reviews(self):
        result = allocate(self.db, date(2026, 11, 1), 4, 4)
        self.assertEqual(len(result), 2)
        mapping = {a['name']: a['title'] for a in assignments(self.db)}
        self.assertEqual(mapping['Meena'], 'ML Bot')
        self.assertEqual(mapping['Hari'], 'Frontend')
        reviews = reviews_for(self.db, assignments(self.db)[0]['assignment_id'])
        self.assertEqual(len(reviews), 4)
        self.assertEqual(reviews[-1]['review_date'], '2026-11-13')

    def test_idempotent(self):
        allocate(self.db, date(2026, 11, 1), 4, 4)
        second = allocate(self.db, date(2026, 11, 1), 4, 4)
        self.assertEqual(second, [])
        self.assertEqual(len(rows(self.db, 'SELECT * FROM reviews')), 8)

    def test_no_task_raises(self):
        db = connection(':memory:')
        initialize(db)
        add_intern(db, 'Solo', 'solo@test.example', 'Python', 'English')
        with self.assertRaises(ValueError):
            allocate(db, date(2026, 11, 1), 4, 4)
        db.close()

    def test_invalid_review_count_raises(self):
        with self.assertRaises(ValueError):
            allocate(self.db, date(2026, 11, 1), 4, 0)

    # ── Review persistence & status transitions ──────────────────────────────

    def test_feedback_is_saved_and_status_updates(self):
        allocate(self.db, date(2026, 11, 1), 4, 4)
        person = assignments(self.db)[0]
        for rev in reviews_for(self.db, person['assignment_id']):
            review = simple_review('working app with tests', 'working app', rev['milestone'])
            save_feedback(self.db, rev['id'], 'working app', review['feedback'], review['method'])
        result = next(a for a in assignments(self.db) if a['assignment_id'] == person['assignment_id'])
        self.assertEqual(result['completed_reviews'], 4)
        self.assertEqual(result['status'], 'Completed')

    def test_status_in_progress_after_first_review(self):
        allocate(self.db, date(2026, 11, 1), 4, 4)
        person = assignments(self.db)[0]
        rev = reviews_for(self.db, person['assignment_id'])[0]
        r = simple_review('requirements text', 'submission text', rev['milestone'])
        save_feedback(self.db, rev['id'], 'submission text', r['feedback'], r['method'])
        result = next(a for a in assignments(self.db) if a['assignment_id'] == person['assignment_id'])
        self.assertEqual(result['status'], 'In Progress')
        self.assertEqual(result['completed_reviews'], 1)

    def test_save_feedback_rejects_empty(self):
        allocate(self.db, date(2026, 11, 1), 4, 4)
        rev = reviews_for(self.db, assignments(self.db)[0]['assignment_id'])[0]
        with self.assertRaises(ValueError):
            save_feedback(self.db, rev['id'], '', 'some feedback', 'method')
        with self.assertRaises(ValueError):
            save_feedback(self.db, rev['id'], 'submission', '', 'method')

    def test_all_four_reviews_completable(self):
        """Verifies all four milestone review rows can be independently saved."""
        allocate(self.db, date(2026, 11, 1), 4, 4)
        person = assignments(self.db)[0]
        revs = reviews_for(self.db, person['assignment_id'])
        self.assertEqual(len(revs), 4)
        for i, rev in enumerate(revs, 1):
            r = simple_review('reference text', f'submission for review {i}', rev['milestone'])
            save_feedback(self.db, rev['id'], f'submission for review {i}', r['feedback'], r['method'])
            completed = next(
                a for a in assignments(self.db) if a['assignment_id'] == person['assignment_id']
            )['completed_reviews']
            self.assertEqual(completed, i)

    # ── Notification deduplication ───────────────────────────────────────────

    def test_notifications_are_idempotent(self):
        self.assertFalse(sent(self.db, 'assignment:1'))
        log_sent(self.db, 'assignment:1', 'meena@test.example', 'Task assigned')
        log_sent(self.db, 'assignment:1', 'meena@test.example', 'Task assigned')  # duplicate
        self.assertTrue(sent(self.db, 'assignment:1'))
        self.assertEqual(len(rows(self.db, 'SELECT * FROM notifications')), 1)

    # ── Chatbot grounding ────────────────────────────────────────────────────

    def test_chat_commands_are_grounded(self):
        msg = chatbot_reply(self.db, 'allocate tasks')
        self.assertIn('four reviews', msg)
        self.assertIn('ML Bot', chatbot_reply(self.db, 'What is Meena task?'))
        review_msg = chatbot_reply(self.db, 'When is Meena review?')
        self.assertIn('Review 1', review_msg)
        # Verify year is actually in the response, not a vacuous assertion
        self.assertIn(str(date.today().year), review_msg)

    def test_chat_no_tasks_warns(self):
        db = connection(':memory:')
        initialize(db)
        add_intern(db, 'Solo', 'solo@test.example', 'Python', 'English')
        msg = chatbot_reply(db, 'allocate tasks')
        self.assertIn('Setup', msg)
        db.close()

    def test_chat_all_assigned_message(self):
        allocate(self.db, date(2026, 11, 1), 4, 4)
        msg = chatbot_reply(self.db, 'allocate tasks')
        self.assertIn('already assigned', msg)

    def test_chat_list_assignments(self):
        allocate(self.db, date(2026, 11, 1), 4, 4)
        # 'who' and 'assigned' are keywords that trigger the assignments list
        msg = chatbot_reply(self.db, 'who is assigned')
        self.assertIn('Meena', msg)
        self.assertIn('Hari', msg)
        # Also verify 'list tasks' triggers it
        msg2 = chatbot_reply(self.db, 'list tasks')
        self.assertIn('ML Bot', msg2)

    def test_chat_upcoming_reviews(self):
        allocate(self.db, date.today() + timedelta(days=1), 4, 4)
        msg = chatbot_reply(self.db, 'upcoming reviews')
        self.assertIn('Review', msg)

    # ── Multilingual spoken messages ─────────────────────────────────────────

    def test_three_languages(self):
        allocate(self.db, date(2026, 11, 1), 4, 4)
        a = assignments(self.db)[0]
        self.assertIn('first review', spoken_message(a, '2026-11-01', 'English'))
        self.assertIn('வணக்கம்', spoken_message(a, '2026-11-01', 'Tamil'))
        self.assertIn('नमस्ते', spoken_message(a, '2026-11-01', 'Hindi'))

    # ── Email templates ──────────────────────────────────────────────────────

    def test_assignment_email_structure(self):
        allocate(self.db, date(2026, 11, 1), 4, 4)
        a = assignments(self.db)[0]
        reviews = reviews_for(self.db, a['assignment_id'])
        subject, body = assignment_email(a, reviews)
        self.assertIn('[InternFlow AI]', subject)
        self.assertIn(a['name'], body)
        self.assertIn('Review 1', body)
        self.assertIn('Review 4', body)

    def test_reminder_email_structure(self):
        allocate(self.db, date.today() + timedelta(days=1), 4, 4)
        upcoming = upcoming_reviews(self.db, within_days=7)
        self.assertTrue(len(upcoming) > 0)
        subject, body = reminder_email(upcoming[0])
        self.assertIn('[InternFlow AI]', subject)
        self.assertIn('reminder', body.lower())

    def test_feedback_email_with_next_review(self):
        allocate(self.db, date(2026, 11, 1), 4, 4)
        a = assignments(self.db)[0]
        revs = reviews_for(self.db, a['assignment_id'])
        r = simple_review('ref', 'sub', revs[0]['milestone'])
        save_feedback(self.db, revs[0]['id'], 'sub', r['feedback'], r['method'])
        completed_rev = reviews_for(self.db, a['assignment_id'])[0]
        subject, body = feedback_email(a, completed_rev, revs[1])
        self.assertIn('feedback', subject.lower())
        self.assertIn('NEXT REVIEW', body)

    # ── Intern / Task validation ─────────────────────────────────────────────

    def test_add_intern_rejects_invalid_email(self):
        with self.assertRaises(ValueError):
            add_intern(self.db, 'Bad', 'notanemail', 'Python', 'English')

    def test_add_intern_duplicate_skipped(self):
        count = add_intern(self.db, 'Meena', 'meena@test.example', 'Python', 'Tamil')
        self.assertEqual(count, 0)

    def test_add_task_rejects_empty_title(self):
        with self.assertRaises(ValueError):
            add_task(self.db, '', 'desc', '', '', '', '')

    def test_add_task_duplicate_skipped(self):
        count = add_task(self.db, 'ML Bot', 'Another desc', 'Python', '', '', '')
        self.assertEqual(count, 0)

    # ── Simple review ────────────────────────────────────────────────────────

    def test_simple_review_fields(self):
        result = simple_review('working README tests', 'working README', 'Review 1')
        self.assertIn('feedback', result)
        self.assertIn('method', result)
        self.assertIn('KEYWORD CHECK', result['feedback'])
        self.assertEqual(result['method'], 'Heuristic preview (not AI)')

    # ── Demo seed ────────────────────────────────────────────────────────────

    def test_seed_demo_loads_data(self):
        db = connection(':memory:')
        initialize(db)
        n, t = seed_demo(db)
        self.assertEqual(n, 4)
        self.assertEqual(t, 3)
        self.assertEqual(len(rows(db, 'SELECT * FROM interns')), 4)
        self.assertEqual(len(rows(db, 'SELECT * FROM tasks')), 3)
        db.close()

    # ── CSV import ───────────────────────────────────────────────────────────

    def test_csv_import_interns(self):
        csv_content = b'name,email,skills,language\nPriya,priya@test.example,Python,English\n'
        fake_file = type('F', (), {'getvalue': lambda self: csv_content, 'name': 'interns.csv'})()
        added, total = import_csv(self.db, fake_file, 'interns')
        self.assertEqual(total, 1)
        self.assertEqual(added, 1)
        # Importing the same file again must not create a duplicate
        added2, total2 = import_csv(self.db, fake_file, 'interns')
        self.assertEqual(added2, 0)  # duplicate email blocked
        self.assertEqual(total2, 1)


if __name__ == '__main__':
    unittest.main()
