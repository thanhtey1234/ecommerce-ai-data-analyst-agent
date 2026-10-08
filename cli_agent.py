"""
Stage 6 - Production AI Data Analyst Agent (CLI)
E-commerce AI Data Analyst project.

Interactive command-line front-end on agent_core.py. Read-only: raw CSVs are
never modified, the SQLite database is in-memory only.

Usage:
    .venv/Scripts/python cli_agent.py                # interactive REPL
    .venv/Scripts/python cli_agent.py "question"     # one-shot
"""
import sys
import agent_core as ac

HELP = """Commands:
  :help            show this help
  :schema          show tables, row counts and cleaning rules applied
  :templates       list questions the agent can answer
  :debug <q>       answer a question showing SQL + guardrails + validation
  :quit            exit
Anything else is treated as a business question."""


def show_schema(conn):
    print("\nTables (in-memory SQLite, cleaned per Stage-2 auto rules):")
    for t in ["customers", "products", "orders", "order_items", "payments", "order_items_excluded"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:22s} {n:>7,} rows")
    print("Cleaning rules applied at load:")
    for i, r in enumerate(ac.CLEAN_RULES, 1):
        print(f"  {i}. {r}")


def show_templates():
    print("\nSupported questions (template registry = LLM-planner interface):")
    for t in ac.TEMPLATES:
        print(f"  - {t['name']:<18} e.g. \"{t['keywords'][0]}\"")


def one_shot(conn, question, debug=False):
    s = ac.ask(conn, question)
    if debug:
        ac.print_answer(s)
    else:
        print()
        if s["status"] == "ok":
            df = s["result"]
            print(df.to_string(index=False))
            ok, msg = s["validation"]
            print(f"\n[validated: {msg}]")
        elif s["status"] == "unmatched":
            print(s["explain"])
        else:  # blocked / validation_failed
            print(f"[blocked] {s.get('explain')}")
        print()
    return s


def repl(conn):
    print("E-commerce AI Data Analyst Agent - Stage 6 (deterministic core, guardrailed SQL)")
    print(HELP)
    while True:
        try:
            line = input("\nask> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye"); break
        if not line:
            continue
        cmd = line.lower()
        if cmd in (":quit", ":q", "exit"):
            print("bye"); break
        elif cmd == ":help":
            print(HELP)
        elif cmd == ":schema":
            show_schema(conn)
        elif cmd == ":templates":
            show_templates()
        elif cmd.startswith(":debug "):
            one_shot(conn, line[7:].strip(), debug=True)
        else:
            one_shot(conn, line)


if __name__ == "__main__":
    conn = ac.get_connection()
    if len(sys.argv) > 1:
        for question in sys.argv[1:]:
            one_shot(conn, question)
    else:
        repl(conn)
    conn.close()
