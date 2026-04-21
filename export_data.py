import sqlite3
import csv

DB_PATH = "experiment.db"

def export_table(table_name, output_file):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()

    column_names = [description[0] for description in cursor.description]

    conn.close()

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(column_names)
        writer.writerows(rows)

    print(f"Exported {table_name} → {output_file}")


def main():
    export_table("question_sessions", "question_sessions.csv")
    export_table("messages", "messages.csv")


if __name__ == "__main__":
    main()