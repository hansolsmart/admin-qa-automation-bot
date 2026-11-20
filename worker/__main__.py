import argparse
import os
from pathlib import Path
from time import sleep

from sqlalchemy.exc import OperationalError

from app.database import create_database_engine
from app.services.runs import claim_next
from worker.service import log_event, run_claim


def main():
    parser = argparse.ArgumentParser(description="Run pending Admin QA scenarios.")
    parser.add_argument("--once", action="store_true", help="Process one pending run and exit.")
    args = parser.parse_args()
    root = Path(os.environ.get("ADMIN_QA_REPORT_DIR", "reports")).resolve()
    engine = create_database_engine()
    try:
        while True:
            try:
                claim = claim_next(engine)
                if claim:
                    run_claim(engine, root, claim)
            except OperationalError as error:
                log_event("worker_database_error", error_type=type(error.orig).__name__)
                if args.once:
                    return 1
                sleep(1)
                continue
            if args.once:
                return 0
            if claim is None:
                sleep(1)
    except KeyboardInterrupt:
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
