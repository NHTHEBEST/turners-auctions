import logging
import sys
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(threadName)-28s  %(levelname)s  %(message)s",
    stream=sys.stdout,
)

from logger import app
from scheduler import run_scheduler


def run_flask():
    app.run(host="127.0.0.1", port=5000, use_reloader=False, threaded=True)


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True, name="Flask")
    flask_thread.start()
    # Give Flask a moment to bind before workers start POSTing to it
    time.sleep(1)
    run_scheduler()  # blocks; Ctrl-C to stop
