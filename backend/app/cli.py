import argparse
import json
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from .bseu_admission_subjects_import import (
    AUDIT_PATH as BSEU_ADMISSION_SUBJECTS_AUDIT_PATH,
)
from .bseu_admission_subjects_import import run_bseu_admission_subjects_import
from .bseu_mapping import verify_bseu_backfill
from .bseu_program_import import run_bseu_program_import
from .catalog_audit_service import audit_catalog
from .catalog_import_service import (
    CANONICAL_RESEARCH_PATH,
    CatalogConflictError,
    CatalogImportError,
    export_university_document,
    import_university_document,
    seed_universities,
)
from .database import SessionLocal, init_db


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Catalog import, export, audit and verification helpers")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("verify-bseu-backfill", help="verify the BSEU compatibility mapping")

    seed = commands.add_parser("seed-universities", help="import the canonical confirmed universities")
    seed.add_argument("--dry-run", action="store_true", help="plan the complete import without writes")
    seed.add_argument(
        "--path",
        type=Path,
        default=CANONICAL_RESEARCH_PATH,
        help="canonical research JSON path",
    )

    audit = commands.add_parser("audit-catalog", help="audit catalog integrity and canonical coverage")
    audit.add_argument(
        "--canonical-path",
        type=Path,
        default=CANONICAL_RESEARCH_PATH,
        help="canonical research JSON path",
    )

    export = commands.add_parser("export-university", help="export one university as stable JSON")
    export.add_argument("slug", help="stable University.slug")

    import_command = commands.add_parser("import-university", help="import one verified university JSON")
    import_command.add_argument("path", type=Path, help="single-university JSON path")
    import_command.add_argument("--dry-run", action="store_true", help="validate and plan without writes")

    bseu_programs = commands.add_parser(
        "import-bseu-programs",
        help="safely import the confirmed tracked BSEU Program and Offering audit",
    )
    bseu_programs.add_argument(
        "--database",
        type=Path,
        required=True,
        help="explicit path to an existing migrated SQLite database",
    )
    bseu_programs.add_argument(
        "--apply",
        action="store_true",
        help="apply the import in one transaction (default: immutable dry-run)",
    )

    bseu_subjects = commands.add_parser(
        "import-bseu-admission-subjects",
        help="validate, plan or apply the audited 2026 BSEU admission requirements",
    )
    bseu_subjects.add_argument(
        "--database",
        type=Path,
        required=True,
        help="explicit path to an existing migration-0007 SQLite database",
    )
    bseu_subjects.add_argument(
        "--audit-path",
        type=Path,
        default=BSEU_ADMISSION_SUBJECTS_AUDIT_PATH,
        help="audited admission-requirements JSON path",
    )
    subject_mode = bseu_subjects.add_mutually_exclusive_group(required=True)
    subject_mode.add_argument("--dry-run", action="store_true", help="show the complete read-only import plan")
    subject_mode.add_argument("--apply", action="store_true", help="apply the complete plan in one transaction")
    return parser


def _print_summary(command: str, summary) -> None:  # type: ignore[no-untyped-def]
    print(json.dumps({"command": command, "status": "ok", **summary.as_dict()}, ensure_ascii=False, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "import-bseu-admission-subjects":
            mode = "apply" if args.apply else "dry-run"
            summary = run_bseu_admission_subjects_import(
                args.database,
                mode=mode,
                audit_path=args.audit_path,
            )
            _print_summary(args.command, summary)
            return 0
        if args.command == "import-bseu-programs":
            summary = run_bseu_program_import(args.database, apply=args.apply)
            _print_summary(args.command, summary)
            return 0
        init_db()
        if args.command == "verify-bseu-backfill":
            with SessionLocal() as session:
                result = verify_bseu_backfill(session)
            print(json.dumps({"status": "ok", **result}, ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "seed-universities":
            if args.dry_run:
                with SessionLocal() as session:
                    summary = seed_universities(session, path=args.path, dry_run=True)
            else:
                with SessionLocal.begin() as session:
                    summary = seed_universities(session, path=args.path)
            _print_summary(args.command, summary)
            return 0
        if args.command == "audit-catalog":
            with SessionLocal() as session:
                result = audit_catalog(session, canonical_path=args.canonical_path)
            print(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
            return 0 if result.ok else 1
        if args.command == "export-university":
            with SessionLocal() as session:
                document = export_university_document(session, args.slug)
            print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.command == "import-university":
            if args.dry_run:
                with SessionLocal() as session:
                    summary = import_university_document(session, args.path, dry_run=True)
            else:
                with SessionLocal.begin() as session:
                    summary = import_university_document(session, args.path)
            _print_summary(args.command, summary)
            return 0
    except CatalogImportError as exc:
        payload: dict[str, object] = {"command": args.command, "status": "error", "error": str(exc)}
        if isinstance(exc, CatalogConflictError):
            payload["conflicts"] = exc.conflicts
            payload["conflict_count"] = len(exc.conflicts)
        if args.command == "import-bseu-admission-subjects":
            payload["mode"] = "apply" if args.apply else "dry-run"
            payload["transaction_committed"] = False
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    except SQLAlchemyError as exc:
        print(
            json.dumps(
                {
                    "command": args.command,
                    "status": "error",
                    "error": f"database operation failed ({type(exc).__name__})",
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
