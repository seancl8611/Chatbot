from flask import Flask, request, jsonify, render_template
import sqlite3
from difflib import get_close_matches
import requests
import spacy
import re
import random

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

app = Flask(__name__)

HANGMAN = (
"""
-----
|   |
|
|
|
|
|
|
|
--------
""",
"""
-----
|   |
|   0
|
|
|
|
|
|
--------
""",
"""
-----
|   |
|   0
|  -+-
|
|
|
|
|
--------
""",
"""
-----
|   |
|   0
| /-+-
|
|
|
|
|
--------
""",
"""
-----
|   |
|   0
| /-+-\ 
|
|
|
|
|
--------
""",
"""
-----
|   |
|   0
| /-+-\ 
|   | 
|
|
|
|
--------
""",
"""
-----
|   |
|   0
| /-+-\ 
|   | 
|   | 
|
|
|
--------
""",
"""
-----
|   |
|   0
| /-+-\ 
|   | 
|   | 
|  |
|
|
--------
""",
"""
-----
|   |
|   0
| /-+-\ 
|   | 
|   | 
|  | 
|  | 
|
--------
""",
"""
-----
|   |
|   0
| /-+-\ 
|   | 
|   | 
|  | | 
|  | 
|
--------
""",
"""
-----
|   |
|   0
| /-+-\ 
|   | 
|   | 
|  | | 
|  | | 
|
--------
"""
)

# Function to create and connect to SQLite database
def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except sqlite3.Error as e:
        print(e)
    return conn

# Function to create tables (update the existing function)
def create_table(conn):
    create_questions_table = """
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        answer TEXT NOT NULL
    );
    """
    create_hangman_table = """
    CREATE TABLE IF NOT EXISTS hangman (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word TEXT NOT NULL,
        guessed_letters TEXT NOT NULL,
        wrong_guesses INTEGER NOT NULL
    );
    """
    try:
        c = conn.cursor()
        c.execute(create_questions_table)
        c.execute(create_hangman_table)
    except sqlite3.Error as e:
        print(e)

# Function to insert a new question-answer pair
def insert_question(conn, question, answer):
    sql = ''' INSERT INTO questions(question, answer)
              VALUES(?,?) '''
    cur = conn.cursor()
    cur.execute(sql, (question, answer))
    conn.commit()

# Function to get all questions
def get_all_questions(conn):
    cur = conn.cursor()
    cur.execute("SELECT question FROM questions")
    rows = cur.fetchall()
    return [row[0] for row in rows]

# Function to get the answer for a question
def get_answer(conn, question):
    cur = conn.cursor()
    cur.execute("SELECT answer FROM questions WHERE question=?", (question,))
    row = cur.fetchone()
    return row[0] if row else None

# Function to get all questions and answers
def get_all_questions_and_answers(conn):
    cur = conn.cursor()
    cur.execute("SELECT question, answer FROM questions")
    rows = cur.fetchall()
    return rows

# Function to find the best match for user input
def find_best_match(user_question: str, questions: list[str]) -> str | None:
    matches = get_close_matches(user_question, questions, n=1, cutoff=0.6)
    return matches[0] if matches else None

# Function to get weather information for a city
def get_weather(city: str) -> str:
    api_key = '61bf91ff20b9b8d436cd9fd6ac4e06be' 
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    complete_url = f"{base_url}?appid={api_key}&q={city}"

    response = requests.get(complete_url)
    data = response.json()

    if response.status_code != 200:
        return f"Error: Failed to fetch weather data for {city}."

    if data.get("cod") == "404":
        return f"Error: City not found."

    try:
        main = data["main"]
        weather_description = data["weather"][0]["description"]
        temperature = main["temp"] - 273.15  # Convert from Kelvin to Celsius
        return f"The weather in {city} is {weather_description} with a temperature of {temperature:.2f}°C."
    except KeyError as e:
        return f"Error: Unexpected response format from API. {e}"
    except Exception as e:
        return f"Error: {e}"

# Function to get news information for a topic
def get_news(topic: str) -> str:
    api_key = '42adfdcaa5b44f9a8de015a086c7535b'  # Replace with your actual API key
    base_url = "https://newsapi.org/v2/everything"
    params = {
        'q': topic,
        'apiKey': api_key,
        'language': 'en',
        'sortBy': 'relevancy',
        'pageSize': 5  # Number of articles to retrieve
    }
    
    response = requests.get(base_url, params=params)
    data = response.json()
    
    if response.status_code != 200:
        return f"Error: Failed to fetch news for {topic}."
    
    if data.get("status") != "ok":
        return "Error: Could not retrieve news."
    
    articles = data.get("articles")
    if not articles:
        return f"No news articles found for '{topic}'."
    
    news_summary = ""
    for article in articles:
        title = article.get("title")
        description = article.get("description")
        url = article.get("url")
        news_summary += f"\nTitle: {title}\nDescription: {description}\nURL: {url}\n\n"
    
    return news_summary.strip()

# Function to extract entities from a question
def extract_entities(question: str) -> dict:
    doc = nlp(question)
    entities = {ent.label_: ent.text for ent in doc.ents}
    return entities

# Fallback function to extract city name from question
def extract_city(question: str) -> str:
    match = re.search(r'weather in ([a-zA-Z\s]+)', question)
    if match:
        return match.group(1).strip()
    return None

# Function to get an answer for a given question from the chatbot data
def get_answer_for_question(conn, question: str) -> str | None:
    question = question.rstrip("?").strip()
    entities = extract_entities(question)

    if "weather" in question.lower():
        city = entities.get("GPE")
        if not city:  # Fallback if GPE is not recognized
            city = extract_city(question)
        if city:
            return get_weather(city)
        else:
            return "Error: Could not identify the city for weather information."

    if "news" in question.lower() or "headlines" in question.lower():
        topic = entities.get("TOPIC")
        if not topic:
            topic = question.replace("news", "").replace("headlines", "").strip()
        if topic:
            return get_news(topic)
        else:
            return "Error: Could not identify the topic for news updates."

    questions = get_all_questions(conn)
    best_match = find_best_match(question, questions)

    if best_match:
        return get_answer(conn, best_match)
    return None

# Function to start a new Hangman game
def start_new_hangman_game(conn):
    words = ["python", "flask", "hangman", "chatbot", "database"]
    word = random.choice(words)
    guessed_letters = ""
    wrong_guesses = 0

    sql = ''' INSERT INTO hangman(word, guessed_letters, wrong_guesses)
              VALUES(?,?,?) '''
    cur = conn.cursor()
    cur.execute(sql, (word, guessed_letters, wrong_guesses))
    conn.commit()

    return cur.lastrowid

# Function to get the current game state
def get_hangman_game_state(conn, game_id):
    cur = conn.cursor()
    cur.execute("SELECT word, guessed_letters, wrong_guesses FROM hangman WHERE id=?", (game_id,))
    row = cur.fetchone()
    if row:
        word, guessed_letters, wrong_guesses = row
        display_word = "".join([letter if letter in guessed_letters else "_" for letter in word])
        return {
            "word": word,
            "display_word": display_word,
            "guessed_letters": guessed_letters,
            "wrong_guesses": wrong_guesses
        }
    return None

# Function to make a guess
def make_hangman_guess(conn, game_id, letter):
    game_state = get_hangman_game_state(conn, game_id)
    if not game_state:
        return None

    word = game_state["word"]
    guessed_letters = game_state["guessed_letters"]
    wrong_guesses = game_state["wrong_guesses"]

    if letter in guessed_letters:
        return game_state  # Letter already guessed

    guessed_letters += letter

    if letter not in word:
        wrong_guesses += 1

    sql = ''' UPDATE hangman
              SET guessed_letters = ?,
                  wrong_guesses = ?
              WHERE id = ? '''
    cur = conn.cursor()
    cur.execute(sql, (guessed_letters, wrong_guesses, game_id))
    conn.commit()

    return get_hangman_game_state(conn, game_id)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    question = data.get('question')
    conn = create_connection("chatbot.db")
    answer = get_answer_for_question(conn, question)
    
    if answer:
        return jsonify({'answer': answer})
    else:
        return jsonify({'answer': "I don't know the answer. Can you teach me?"})

@app.route('/teach', methods=['POST'])
def teach():
    data = request.get_json()
    question = data.get('question')
    answer = data.get('answer')
    conn = create_connection("chatbot.db")
    insert_question(conn, question, answer)
    return jsonify({'message': 'Thank you! I learned a new response!'})

@app.route('/display')
def display():
    conn = create_connection("chatbot.db")
    questions_and_answers = get_all_questions_and_answers(conn)
    if not questions_and_answers:
        return jsonify({'message': "There are no stored questions and responses."})
    else:
        return jsonify({'questions_and_answers': questions_and_answers})

@app.route('/reset', methods=['POST'])
def reset():
    conn = create_connection("chatbot.db")
    reset_memory(conn)
    return jsonify({'message': 'Memory has been reset.'})

def reset_memory(conn):
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM questions")
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error: {e}")

@app.route('/hangman/start', methods=['POST'])
def hangman_start():
    conn = create_connection("chatbot.db")
    game_id = start_new_hangman_game(conn)
    game_state = get_hangman_game_state(conn, game_id)
    return jsonify({'game_id': game_id, 'game_state': game_state, 'hangman': HANGMAN[game_state["wrong_guesses"]]})

@app.route('/hangman/guess', methods=['POST'])
def hangman_guess():
    data = request.get_json()
    game_id = data.get('game_id')
    letter = data.get('letter').lower()
    
    conn = create_connection("chatbot.db")
    game_state = make_hangman_guess(conn, game_id, letter)
    
    if game_state:
        if "_" not in game_state["display_word"]:
            return jsonify({'game_state': game_state, 'message': 'Congratulations! You won!', 'hangman': HANGMAN[game_state["wrong_guesses"]]})
        elif game_state["wrong_guesses"] >= len(HANGMAN) - 1:
            return jsonify({'game_state': game_state, 'message': f'Game over! The word was {game_state["word"]}.', 'hangman': HANGMAN[game_state["wrong_guesses"]]})
        else:
            return jsonify({'game_state': game_state, 'hangman': HANGMAN[game_state["wrong_guesses"]]})
    else:
        return jsonify({'message': 'Invalid game ID or letter.'})

@app.route('/hangman/status', methods=['GET'])
def hangman_status():
    game_id = request.args.get('game_id')
    conn = create_connection("chatbot.db")
    game_state = get_hangman_game_state(conn, game_id)
    
    if game_state:
        return jsonify({'game_state': game_state, 'hangman': HANGMAN[game_state["wrong_guesses"]]})
    else:
        return jsonify({'message': 'Invalid game ID.'})

if __name__ == "__main__":
    conn = create_connection("chatbot.db")
    create_table(conn)
    app.run(debug=True)
