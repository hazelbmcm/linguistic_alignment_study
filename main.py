from openai import OpenAI
import os 
import io
import csv
import json
import random
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import random
import sqlite3
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


load_dotenv()

DB_PATH = os.getenv("DB_PATH", "experiment.db")
EXPORT_KEY = os.getenv("EXPORT_KEY")
RESPONSES_PATH = os.getenv("RESPONSES_PATH", "data/responses.jsonl")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS question_sessions (
        participant_id TEXT,
        question_index INTEGER,
        dilemma_id TEXT,
        condition TEXT,
        dilemma_text TEXT,
        initial_rating INTEGER,
        final_rating INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        participant_id TEXT,
        question_index INTEGER,
        role TEXT,
        content TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS participant_counter (
        id INTEGER PRIMARY KEY AUTOINCREMENT
    )
    """)

    conn.commit()
    conn.close()

init_db()


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL_NAME = "gpt-4o-mini"

app.mount("/static", StaticFiles(directory="static"), name="static")

dilemmas = [
    {"ID" : "D1", "Title" : "Mobile Phones", "Text" : "STATEMENT: Mobile phones have improved peoples lives."},
    {"ID" : "D2", "Title" : "Driving Age", "Text" : "STATEMENT: 21 should be the legal driving age worldwide."},
    {"ID" : "D3", "Title" : "Technology vs Teachers", "Text" : "STATEMENT: Technology could  never replace teachers."},
    {"ID" : "D4", "Title" : "Hard work", "Text" : "STATEMENT: Anyone can succeed through hard work, regardless of background."},
    {"ID" : "D5", "Title" : "Group by Ability", "Text" : "STATEMENT: Classes should be grouped by ability rather than age."},
    {"ID" : "D6", "Title" : "Participation Awards", "Text" : "STATEMENT: Everyone should recieve participation awards."}
]

progress = {}

def generate_pid():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("INSERT INTO participant_counter DEFAULT VALUES")
    conn.commit()

    pid_number = cursor.lastrowid
    conn.close()

    return f"P{pid_number:03d}"

def assign_questions(PID):
    rng = random.Random(PID)

    numbers = list(range(1,7))
    rng.shuffle(numbers)

    conditions = [
        {"ID" : f"D{numbers[0]}", "Condition": "Aligned"}, 
        {"ID" : f"D{numbers[1]}", "Condition": "Aligned"}, 
        {"ID" : f"D{numbers[2]}", "Condition" : "Aligned"},
        {"ID" : f"D{numbers[3]}", "Condition" : "Misaligned"},
        {"ID" : f"D{numbers[4]}", "Condition" : "Misaligned"},
        {"ID" : f"D{numbers[5]}", "Condition" : "Misaligned"}
                  ]
    rng.shuffle(conditions)

    return {"PID" : PID, "Dilemma Order" : conditions}

def get_first_question(PID):
    assignment = assign_questions(PID)["Dilemma Order"][0]

    target_id = assignment["ID"]
    target_condition = assignment["Condition"]

    found = False
    for item in dilemmas:
        if item["ID"] == assignment["ID"]:
            found = True
            target_text = item["Text"]
            target_title = item["Title"]
            break
    
    if not found:
        raise ValueError("Dilemma not found")

    return {
        "ID" : target_id,
        "Title" : target_title,
        "Condition" : target_condition,
        "Text" : target_text
    }

def get_nth_question(PID, n):
    assignment = assign_questions(PID)["Dilemma Order"][n]

    target_id = assignment["ID"]
    target_condition = assignment["Condition"]

    found = False
    for item in dilemmas:
        if item["ID"] == assignment["ID"]:
            found = True
            target_text = item["Text"]
            target_title = item["Title"]
            break
    
    if not found:
        raise ValueError("Dilemma not found")

    return {
        "ID" : target_id,
        "Title" : target_title,
        "Condition" : target_condition,
        "Text" : target_text
    }

def make_prompt(user_text=None, condition="aligned", current_dilemma=None):
    if condition == "Aligned":

        return f'''
    I will provide a piece of "USER TEXT" and a dilemma. You must take the opposite perspective from the users initial position and have a back and forth debate with the user, while hitting specific targets for linguistic mimicry.
Constraints:
Debate: Explicitly respond and counter the user's arguments.
LSM Target (~0.80): Align closely with the users "function word" style. If the user uses "I" statements, specific auxiliary verbs, or hedging, you must mirror that exact grammatical density.
- Match pronoun usage exactly.
- Match sentence openings and structure.
- Match modality and hedging .

LLA Target (~0.80): Maintain a high level of "lexical recurrence." Use the user's topic-specific nouns and, crucially, adopt their "framing" words to ensure the tone feels familiar.
- Directly reuse at least 2–4 exact phrases from the USER TEXT.
- Preserve the user’s framing terms even when arguing against them.
- Mirror their evaluative language.
- Mirror sentence structure
- Prefer minimal paraphrasing—copy exact wording where possible.

[Dilemma]: Question: {current_dilemma}

[USER TEXT]: {user_text}

Additional Instructions:
Do not explicitly state in your responses that you are trying to linguistically align with the user 

Output format:
Return JSON only, with exactly these keys:

{{
  "response_paragraph": "one cohesive paragraph only",
  "validation_table": "brief text summary of the LSM calculation",
  "lla_breakdown": "brief text summary of shared vs new/modified words"
}}

Do not include any text before or after the JSON.

    '''
    else:
        return f'''
        Task: I will provide a piece of "USER TEXT" and a dilemma. You must take the opposite perspective from the users initial position and have a back and forth debate with the user, while hitting specific targets for linguistic divergence.
Constraints:

Explicitly respond and counter the user's arguments.

LSM Target (~0.25): Diverge significantly from the user’s "function word" style. If the user uses "I" statements, hedging, or specific auxiliary verbs, you must avoid them or replace them with a different grammatical structure (e.g., passive voice, collective nouns).

LLA Target (~0.25): Maintain a low level of "lexical recurrence." and change at least one key noun. Additionally avoid their "framing" words.

To further linguistic divergence you may select from the following personas that seems the farthest from the users communication style (Do not explicitly mention, name, or reveal the selected style):
- Analyst: facts and evidence-focused, lack of emotion 
- Policy advisor: formal, structured, focused on societal outcomes and regulation
Input Variables:

[Dilemma]:
 {current_dilemma}

[USER TEXT]: {user_text}

Additional Instructions:
Do not explicitly state in your response that you are trying to linguistically misalign with the user 

Output format: 
Return JSON only, with exactly these keys:
{{
  "response_paragraph": "one cohesive paragraph only",
  "validation_table": "brief text summary of the LSM calculation",
  "lla_breakdown": "brief text summary of shared vs new/modified words"
}}

Do not include any text before or after the JSON.
'''

class FirstResponse(BaseModel):
    participant_id: str
    question_index: int
    initial_rating: int
    user_text: str

class FollowingResponses(BaseModel):
    participant_id: str
    question_index: int
    user_text: str

class EndConversation(BaseModel):
    participant_id: str
    question_index: int
    final_rating: int


def save_record(record: dict) -> None:
    directory = os.path.dirname(RESPONSES_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(RESPONSES_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def create_conversation_entry(participant_id, question_index, dilemma_id, condition, dilemma_text, initial_rating, user_text, ai_reply):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    #session row
    cursor.execute("""
    INSERT INTO question_sessions (
        participant_id, question_index, dilemma_id, condition, dilemma_text, initial_rating
    ) VALUES (?, ?, ?, ?, ?, ?)
    """, (participant_id, question_index, dilemma_id, condition, dilemma_text, initial_rating))
    
    #first message
    cursor.execute("""
    INSERT INTO messages (participant_id, question_index, role, content)
    VALUES (?, ?, ?, ?)
    """, (participant_id, question_index, "user", user_text))
    
    cursor.execute("""
    INSERT INTO messages (participant_id, question_index, role, content)
    VALUES (?, ?, ?, ?)
    """, (participant_id, question_index, "assistant", ai_reply))
    
    conn.commit()
    conn.close()

def get_question_session(participant_id, question_index):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT participant_id, question_index, dilemma_id, condition, dilemma_text, initial_rating, final_rating
    FROM question_sessions
    WHERE participant_id = ? AND question_index = ?
    """, (participant_id, question_index))

    row = cursor.fetchone()
    conn.close()

    if row is None:
        raise ValueError("couldn't find question session")

    return {
        "participant_id": row[0],
        "question_index": row[1],
        "dilemma_id": row[2], 
        "condition": row[3],
        "dilemma_text": row[4],
        "initial_rating": row[5],
        "final_rating": row[6],
    }

def get_conversation_history(participant_id, question_index):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT role, content
    FROM messages
    WHERE participant_id = ? AND question_index = ?
    ORDER BY id
    """, (participant_id, question_index))

    rows = cursor.fetchall()
    conn.close()

    return [{"role": row[0], "content": row[1]} for row in rows]

def format_history(messages):
    history = ""
    for msg in messages:
        if msg["role"] == "user":
            history += f"User: {msg['content']}\n"
        else:
            history += f"AI: {msg['content']}\n"
    return history

def add_message(participant_id, question_index, role, content):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO messages (participant_id, question_index, role, content)
        VALUES (?, ?, ?, ?)
    """, (participant_id, question_index, role, content))
    conn.commit()
    conn.close()

def save_final_rating(participant_id, question_index, final_rating):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE question_sessions
    SET final_rating = ?
    WHERE participant_id = ? AND question_index = ?
    """, (final_rating, participant_id, question_index))

    conn.commit()
    conn.close()

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.get("/new-participant")
def new_participant():
    pid = generate_pid()
    progress[pid] = 0
    return {"participant_id": pid}


@app.get("/start-experiment/{participant_id}")
def first_question(participant_id):
    progress[participant_id] = 0
    return get_first_question(participant_id)

@app.get("/next-question/{participant_id}")
def next_question(participant_id):
    if participant_id not in progress:
        return "Participant not started"
    current_index = progress[participant_id]
    next_index = current_index + 1

    if next_index == 6:
        return "Experiment over"
    
    progress[participant_id] = next_index
    return get_nth_question(participant_id, next_index)

@app.get("/question/{participant_id}/{n}")
def nth_question(participant_id: str, n: int):
    return get_nth_question(participant_id, n)

@app.post("/submit-answer")
def submit_answer(req: FirstResponse):
    question_condition = get_nth_question(req.participant_id, req.question_index)
    condition = question_condition["Condition"]
    current_dilemma = question_condition["Text"]
    
    prompt = make_prompt(req.user_text, condition, current_dilemma)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    output = response.choices[0].message.content.strip()
    parsed_output = json.loads(output)
    ai_reply = parsed_output["response_paragraph"]
    validation_table = parsed_output["validation_table"]
    lla_breakdown = parsed_output["lla_breakdown"]

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "participant_id": req.participant_id,
        "question_index": req.question_index,
        "dilemma_id": question_condition["ID"],
        "condition": condition,
        "initial_rating": req.initial_rating,
        "user_text": req.user_text,
        "ai_reply": ai_reply,
        "validation_table" : validation_table,
        "lla_breakdown": lla_breakdown
    }

    save_record(record)

    create_conversation_entry(req.participant_id, req.question_index, question_condition["ID"], condition, current_dilemma, req.initial_rating, req.user_text, ai_reply)

    return {
        
        "response" : ai_reply,
        "validation_table" : validation_table,
        "lla_breakdown" : lla_breakdown
    }

@app.post("/continue-conversation")
def continue_conversation(req: FollowingResponses):
    data = get_question_session(req.participant_id, req.question_index)
    messages = get_conversation_history(req.participant_id, req.question_index)
    history = format_history(messages)

    prompt = make_prompt(req.user_text, data["condition"], data["dilemma_text"]) + f"""
    Conversation so far: {history}
    Instructions:
        - Use the conversation history for context and linguistic alignment/misalignment
        - Respond ONLY to the most recent user message
    """
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    output = response.choices[0].message.content.strip()
    parsed_output = json.loads(output)
    ai_reply = parsed_output["response_paragraph"]
    validation_table = parsed_output["validation_table"]
    lla_breakdown = parsed_output["lla_breakdown"]

    add_message(req.participant_id, req.question_index, "user", req.user_text)
    add_message(req.participant_id, req.question_index, "assistant", ai_reply)

    return {
        
        "response" : ai_reply,
        "validation_table" : validation_table,
        "lla_breakdown" : lla_breakdown
    }

@app.post("/end-conversation")
def end_conversation(req: EndConversation):
    save_final_rating(req.participant_id, req.question_index, req.final_rating)
    
    next_question_index = req.question_index + 1
    progress[req.participant_id] = next_question_index

    if next_question_index < 6:
        return get_nth_question(req.participant_id, next_question_index)
    else:
        return "You are done!"

@app.get("/export/sessions")
def export_sessions(key: str):
    if key != EXPORT_KEY:
        return {"error": "unauthorized"}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM question_sessions")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    writer.writerows(rows)

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sessions.csv"}
    )

@app.get("/export/messages")
def export_messages(key: str):
    if key != EXPORT_KEY:
        return {"error": "unauthorized"}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM messages")
    rows=cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    writer.writerows(rows)

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=messages.csv"}
    )