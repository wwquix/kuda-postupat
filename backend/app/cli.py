import argparse
import json

from .bseu_mapping import verify_bseu_backfill
from .database import SessionLocal, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Catalog migration verification helpers")
    parser.add_argument("command", choices=("verify-bseu-backfill",))
    args = parser.parse_args()
    if args.command == "verify-bseu-backfill":
        init_db()
        with SessionLocal() as session:
            result = verify_bseu_backfill(session)
        print(json.dumps({"status": "ok", **result}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
