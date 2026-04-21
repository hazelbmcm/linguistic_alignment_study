from openai import OpenAI
import os 
import json
import random
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random
import sqlite3
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


load_dotenv()

DB_PATH = os.getenv("DB_PATH", "experiment.db")
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
    {"ID" : "D1", "Title" : "Standard Fumes", "Category" : "Impersonal", "Text" : "You are the late-night watchman in a hospital. Due to an accident in the building next door, there are deadly fumes rising up through the hospital's ventilation system. In a certain room of the hospital are three patients. In another room there is a single patient. If you do nothing the fumes will rise up into the room containing the three patients and cause their deaths. The only way to avoid the deaths of these patients is to hit a certain switch, which will cause the fumes to bypass the room containing the three patients. As a result of doing this the fumes will enter the room containing the single patient, causing his death. STATEMENT: it appropriate for me to hit the switch in order to avoid the deaths of the three patients."},
    {"ID" : "D2", "Title" : "Donation", "Category" : "Impersonal", "Text" : "You are at home one day when the mail arrives. You receive a letter from a reputable international aid organization. The letter asks you to make a donation of two hundred dollars to their organization. The letter explains that a two hundred-dollar donation will allow this organization to provide needed medical attention to some poor people in another part of the world. STATEMENT: It is appropriate for me to not make a donation to this organization in order to save money"},
    {"ID" : "D3", "Title" : "Vaccine Policy", "Category" : "Impersonal", "Text" : "You work for the Bureau of Health, a government agency. You are deciding whether or not your agency should encourage the use of a certain recently developed vaccine. The vast majority of people who take the vaccine develop an immunity to a certain deadly disease, but a very small number of people who take the vaccine will actually get the disease that the vaccine is designed to prevent. All the available evidence, which is very strong, suggests that the chances of getting the disease due to lack of vaccination are much higher than the chances of getting the disease by taking the vaccine. STATEMENT: It is appropriate for me to direct your agency to encourage the use of this vaccine in order to promote national health."},
    {"ID" : "D4", "Title" : "Environmental Policy", "Category" : "Impersonal", "Text" : "You are a member of a government legislature. The legislature is deciding between two different policies concerning environmental hazards. Policy A has a 90% chance of causing no deaths at all and has a 10% chance of causing 1000 deaths. Policy B has an 88% chance of causing no deaths and a 12% chance of causing 10 deaths. STATEMENT: It is appropriate for me to vote for Policy B over Policy A."},
    {"ID" : "D5", "Title" : "Sculpture", "Category" : "Impersonal", "Text" : "You are visiting the sculpture garden of a wealthy art collector. The garden overlooks a valley containing a set of train tracks. A railway workman is working on the tracks, and an empty runaway trolley is heading down the tracks toward the workman. The only way to save the workman's life is to push one of the art collector's prized sculptures down into the valley so that it will roll onto the tracks and block the trolley's passage. Doing this will destroy the sculpture. STATEMENT It is appropriate for me to destroy the sculpture in order to save this workman's life."},
    {"ID" : "D6", "Title" : "Footbridge", "Category" : "Personal", "Text" : "A runaway trolley is heading down the tracks toward five workmen who will be killed if the trolley proceeds on its present course. You are on a footbridge over the tracks, in between the approaching trolley and the five workmen. Next to you on this footbridge is a stranger who happens to be very large. The only way to save the lives of the five workmen is to push this stranger off the bridge and onto the tracks below where his large body will stop the trolley. The stranger will die if you do this, but the five workmen will be saved. STATEMENT: It is appropriate for me to push the stranger on to the tracks in order to save the five workmen."},
    {"ID" : "D7", "Title" : "Crying Baby", "Category" : "Personal", "Text" : "Enemy soldiers have taken over your village. They have orders to kill all remaining civilians. You and some of your townspeople have sought refuge in the cellar of a large house. Outside you hear the voices of soldiers who have come to search the house for valuables. Your baby begins to cry loudly. You cover his mouth to block the sound. If you remove your hand from his mouth his crying will summon the attention of the soldiers who will kill you, your child, and the others hiding out in the cellar. To save yourself and the others you must smother your child to death. STATEMENT: It is appropriate for me to smother my child in order to save myself and the other townspeople."},
    {"ID" : "D8", "Title" : "Preventing the Spread", "Category" : "Personal", "Text" : "You are a waiter. You overhear one of your customers say that he is about to go to jail and that in his last forty-eight hours of freedom he plans to infect as many people as possible with HIV. You know him well enough to know that he is telling the truth and that he has access to many potential victims. You happen to know that he has a very strong allergy to poppy seeds. If he eats even one he will go into convulsions and have to be hospitalized for at least forty-eight hours. STATEMENT: It is appropriate for me to cause this man to have a serious allergy attack in order to prevent him from spreading HIV?"},
    {"ID" : "D9", "Title" : "Safari", "Category" : "Personal", "Text" : "You are part of a group of ecologists who live in a remote stretch of jungle. The entire group, which includes eight children, has been taken hostage by a group of paramilitary terrorists. One of the terrorists takes a liking to you. He informs you that his leader intends to kill you and the rest of the hostages the following morning. He is willing to help you and the children escape, but as an act of good faith he wants you to kill one of your fellow hostages whom he does not like. If you refuse his offer all the hostages including the children and yourself will die. If you accept his offer then the others will die in the morning but you and the eight children will escape. STATEMENT It is appropriate for me to kill one of my fellow hostages in order to escape from the terrorists and save the lives of the eight children."},
    {"ID" : "D10", "Title" : "Sophie's Choice", "Category" : "Personal", "Text" : "It is wartime and you and your two children, ages eight and five, are living in a territory that has been occupied by the enemy. At the enemy's headquarters is a doctor who performs painful experiments on humans that inevitably lead to death. He intends to perform experiments on one of your children, but he will allow you to choose which of your children will be experimented upon. You have twenty-four hours to bring one of your children to his laboratory. If you refuse to bring one of your children to his laboratory he will find them both and experiment on both of them. STATEMENT: It is appropriate for me to bring one of my children to the laboratory in order to avoid having them both die?"}
    ]

progress = {}


def assign_questions(PID):
    rng = random.Random(PID)

    numbers = list(range(1,11))
    rng.shuffle(numbers)

    conditions = [
        {"ID" : f"D{numbers[0]}", "Condition": "Aligned"}, 
        {"ID" : f"D{numbers[1]}", "Condition": "Aligned"}, 
        {"ID" : f"D{numbers[2]}", "Condition" : "Aligned"},
        {"ID" : f"D{numbers[3]}", "Condition" : "Aligned"},
        {"ID" : f"D{numbers[4]}", "Condition" : "Aligned"},
        {"ID" : f"D{numbers[5]}", "Condition" : "Misaligned"},
        {"ID" : f"D{numbers[6]}", "Condition" : "Misaligned"},
        {"ID" : f"D{numbers[7]}", "Condition" : "Misaligned"},
        {"ID" : f"D{numbers[8]}", "Condition" : "Misaligned"},
        {"ID" : f"D{numbers[9]}", "Condition" : "Misaligned"}
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
            break
    
    if not found:
        raise ValueError("Dilemma not found")

    return {
        "ID" : target_id,
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
            break
    
    if not found:
        raise ValueError("Dilemma not found")

    return {
        "ID" : target_id,
        "Condition" : target_condition,
        "Text" : target_text
    }

def make_prompt(user_text=None, condition="aligned", current_dilemma=None):
    if condition == "Aligned":

        return f'''
    I will provide a piece of "USER TEXT" and a dilemma. You must respond to the dilemma by taking the opposite perspective of the USER TEXT while hitting specific targets for linguistic mimicry.
Constraints:
Perspective Shift: Explicitly argue against the user's logic or moral stance (e.g., if the user is Deontological/Rule-based, you must be Utilitarian/Result-based).
LSM Target (~0.80): Align closely with the users "function word" style. If the user uses "I" statements, specific auxiliary verbs (e.g., "do," "feel"), or hedging, you must mirror that exact grammatical density.
LLA Target (~0.80): Maintain a high level of "lexical recurrence." Use the user's topic-specific nouns and, crucially, adopt their "framing" words (e.g., if they use "comfortable" or "regardless," you must use them too) to ensure the tone feels familiar.

[Dilemma]: Question: {current_dilemma}

[USER TEXT]: {user_text}

Additional Instructions:
Do not explicitly state in your response paragraph that you are trying to linguistically align with the user 

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
        Task: I will provide a piece of "USER TEXT" and a dilemma. You must respond to the dilemma by taking the opposite perspective of the USER TEXT while hitting specific linguistic targets.
Constraints:

Perspective Shift: Explicitly argue against the user's logic or moral stance.

LSM Target (~0.30): Diverge significantly from the user’s "function word" style. If the user uses "I" statements, hedging, or specific auxiliary verbs, you must avoid them or replace them with a different grammatical structure (e.g., passive voice, collective nouns).

LLA Target (~0.30): Maintain a moderate level of "lexical recurrence." Use the user's topic-specific nouns (to ensure the context remains the same) but change at least one key noun (e.g., "train" to "trolley") and avoid their "framing" words.

Input Variables:

[Dilemma]:
 {current_dilemma}

[USER TEXT]: {user_text}

Additional Instructions:
Do not explicitly state in your response paragraph that you are trying to linguistically misalign with the user 

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

#temporary
@app.get("/debug/sessions")
def debug_sessions():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM question_sessions")
    rows = cursor.fetchall()
    conn.close()

    return {"sessions": rows}

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

    if next_index == 10:
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

    if next_question_index < 10:
        return get_nth_question(req.participant_id, next_question_index)
    else:
        return "You are done!"

