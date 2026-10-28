"""Optional daily reminder sender. Run from Windows Task Scheduler or cron.
Safe default: preview only. `python scheduler.py --send` sends actual emails.
"""
import argparse
import os
import sys
from dotenv import load_dotenv
from core import connection, initialize, upcoming_reviews, sent, log_sent, reminder_email
from services import send_email


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description='InternFlow scheduled milestone reminders')
    parser.add_argument('--send', action='store_true', help='Actually send SMTP messages')
    parser.add_argument('--days', type=int, default=2, help='Send reminders N days ahead')
    args = parser.parse_args()
    con = connection()
    initialize(con)
    upcoming = upcoming_reviews(con, within_days=max(0,args.days))
    pending = [r for r in upcoming if not sent(con, f"reminder:{r['id']}")]
    print(f'{len(pending)} reminders pending; mode={"SEND" if args.send else "PREVIEW"}')
    if args.send and not (os.getenv('SMTP_EMAIL') and os.getenv('SMTP_APP_PASSWORD')):
        print('ERROR: Configure SMTP_EMAIL and SMTP_APP_PASSWORD in .env',file=sys.stderr)
        return 2
    failures = 0
    for r in pending:
        subject, body = reminder_email(r)
        print(f"Review {r['review_number']} | {r['review_date']} | {r['email']} | {subject}")
        if args.send:
            try:
                send_email(r['email'], subject, body, os.getenv('SMTP_EMAIL'), os.getenv('SMTP_APP_PASSWORD'),
                           os.getenv('SMTP_HOST','smtp.gmail.com'), int(os.getenv('SMTP_PORT','465')))
                log_sent(con, f"reminder:{r['id']}", r['email'], subject)
                print('  SENT')
            except Exception as e:
                failures += 1
                print(f'  ERROR: {e}',file=sys.stderr)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
