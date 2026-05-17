"""
Print a consolidated Supabase migration.

Supabase REST does not expose a SQL execution endpoint for normal projects, so
this script combines every local .sql migration into one paste-ready block for
the Supabase SQL editor.
"""
from pathlib import Path

ROOT = Path(__file__).parent

def main():
    sql_files = sorted(
        p for p in ROOT.glob("*.sql")
        if p.name != "full_migration.sql"
    )

    blocks = []
    for path in sql_files:
        blocks.append(f"-- === {path.name} ===\n{path.read_text().strip()}\n")

    consolidated = "\n\n".join(blocks)
    (ROOT / "full_migration.sql").write_text(consolidated + "\n")

    print("Paste the SQL below into the Supabase SQL editor and run it:")
    print("https://supabase.com/dashboard/project/tnyjqpxrxiihuafqaluh/sql/new")
    print("\n" + "=" * 80 + "\n")
    print(consolidated)
    print("\n" + "=" * 80)
    print(f"\nAlso wrote the same SQL to: {ROOT / 'full_migration.sql'}")

if __name__ == "__main__":
    main()
