"""Administration commands. Run from the backend folder:

  python manage.py list-plans
  python manage.py set-plan --org <organisation id> --plan pro
  python manage.py backup
  python manage.py list-backups
  python manage.py prune-backups
  python manage.py restore --file backups/backup-20261018T120000Z.jsonl.gz.enc [--replace]

Settings come from the same environment (and backend/.env) as the app.
"""
import argparse
import asyncio
import sys

import backup
import config  # loads .env
from database import database


async def _run(args) -> int:
    await database.connect()
    try:
        if args.command == "list-plans":
            for plan in await database.list_plans():
                print(f"{plan['id']:10} scans/month={plan['scans_per_month']} tokens/month={plan['tokens_per_month']} "
                      f"members={plan['max_members']} retention_days={plan['retention_days']}")
        elif args.command == "set-plan":
            if not await database.get_plan(args.plan):
                print(f"No plan called '{args.plan}'. Run list-plans.", file=sys.stderr)
                return 1
            if not await database.set_organization_plan(args.org, args.plan):
                print(f"No organisation with id '{args.org}'.", file=sys.stderr)
                return 1
            print(f"Organisation {args.org} is now on the {args.plan} plan.")
        elif args.command == "backup":
            path = await backup.create_backup(database.db)
            backup.prune_backups()
            print(path)
        elif args.command == "list-backups":
            for path in backup.list_backups():
                print(path)
        elif args.command == "prune-backups":
            print(f"Removed {backup.prune_backups()} backup(s).")
        elif args.command == "restore":
            result = await backup.restore_backup(database.db, args.file, replace=args.replace)
            print(result)
    except backup.BackupError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        await database.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume Scanner administration")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list-plans")
    set_plan = commands.add_parser("set-plan")
    set_plan.add_argument("--org", required=True)
    set_plan.add_argument("--plan", required=True)
    commands.add_parser("backup")
    commands.add_parser("list-backups")
    commands.add_parser("prune-backups")
    restore = commands.add_parser("restore")
    restore.add_argument("--file", required=True)
    restore.add_argument("--replace", action="store_true", help="overwrite a database that already has data")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
