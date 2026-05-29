import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from job_update_address_uri import run
from helpers import log
from flask import jsonify
from threading import Thread

CRON_SCHEDULE = os.getenv("CRON_SCHEDULE") or "0 0 * * *"

scheduler = BackgroundScheduler()

def wrapped_job_update_address_uri():
    with app.test_request_context():
        try:
            run()
        except Exception as e:
            log(f"Error when running address URI job: {e}")

scheduler.add_job(
    wrapped_job_update_address_uri,
    CronTrigger.from_crontab(CRON_SCHEDULE)
)
scheduler.start()

@app.route("/run", methods=["POST"])
def trigger_job():
    try:
        Thread(target=wrapped_job_update_address_uri).start()
    except Exception as e:
        log(f"Error when running address URI job: {e}")
        return jsonify({"status": "Error occurred while running the job."}), 500
    return jsonify({"status": "Job accepted and started."}), 202