from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_session import Session
import pandas as pd
import random
import spacy
from rake_nltk import Rake
import re
import nltk
from transformers import T5ForConditionalGeneration, T5Tokenizer
import secrets
from connect import getCursor
from werkzeug.security import generate_password_hash, check_password_hash
from fuzzywuzzy import fuzz, process


# Initialize the Flask application
app = Flask(__name__)

# Configure session
# Generate and use a secure random secret key
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SESSION_TYPE'] = 'filesystem'

from flask_session import Session
Session(app)

# Load book data
book_data = pd.read_csv('data.csv')

# Load SpaCy's English model
nlp = spacy.load("en_core_web_sm")

# Ensure stopwords are downloaded
nltk.download('stopwords')


# Initialize the database schema
def init_db():
    connection, cursor = getCursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(100) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        email VARCHAR(100) NOT NULL,
        role_id INT,
        is_active TINYINT DEFAULT 1
    )
    """)
    connection.commit()  # Use the connection object here
    cursor.close()
    connection.close()

# Extract keywords using SpaCy NER and RAKE with additional contextual analysis
def extract_keywords(text):
    # Step 1: Extract Named Entities using SpaCy
    doc = nlp(text)
    # Common entity types to extract
    entity_labels = ['PERSON', 'ORG', 'GPE', 'LOC', 'PRODUCT', 'DATE', 'TIME', 'MONEY', 'PERCENT', 'QUANTITY', 'EVENT', 'WORK_OF_ART']
    named_entities = {ent.text for ent in doc.ents if ent.label_ in entity_labels}
    
    # Step 2: Extract keywords using RAKE
    rake = Rake(min_length=2, max_length=6)  # Adjust lengths to capture longer phrases
    rake.extract_keywords_from_text(text)
    rake_keywords = set(rake.get_ranked_phrases())
    
    # Step 3: Combine RAKE keywords and SpaCy Named Entities
    combined_keywords = rake_keywords.union(named_entities)
    
    # Additional contextual analysis
    # Filter out overly generic keywords and those not providing value
    filtered_keywords = [kw for kw in combined_keywords if len(kw.split()) > 1 and not any(kw.lower().startswith(prefix) for prefix in ['the ', 'a ', 'an ', 'of ', 'and '])]
    
    return list(filtered_keywords)  # Return filtered keywords as a list

# Clean and filter keywords (updated for better results)
def clean_keywords(keywords):
    seen = set()
    result = []
    for keyword in keywords:
        cleaned_keyword = re.sub(r'[^\w\s]', '', keyword).strip()
        if cleaned_keyword and cleaned_keyword not in seen:
            seen.add(cleaned_keyword)
            result.append(cleaned_keyword)
    return result

# Get top N keywords
def get_top_keywords(keywords, top_n=5):
    return sorted(keywords, key=lambda x: len(x.split()), reverse=True)[:top_n]

# Summarize text using T5
def summarize_with_t5(text):
    model_name = "t5-small"  # You can also use "t5-base" or "t5-large" for better performance
    model = T5ForConditionalGeneration.from_pretrained(model_name)
    tokenizer = T5Tokenizer.from_pretrained(model_name)
    input_ids = tokenizer.encode("summarize: " + text, return_tensors="pt", max_length=512, truncation=True)
    summary_ids = model.generate(input_ids, max_length=150, min_length=40, length_penalty=2.0, num_beams=4, early_stopping=True)
    summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    return summary

# Combine keyword extraction and summarization
def analyze_user_input(text):
    raw_keywords = extract_keywords(text)
    cleaned_keywords = clean_keywords(raw_keywords)
    top_keywords = get_top_keywords(cleaned_keywords)
    summary = summarize_with_t5(text)
    return {
        "keywords": top_keywords,
        "summary": summary
    }

# Function to find the most relevant books based on user input
def find_relevant_books(keywords, summary):
    book_data['relevance_score'] = 0.0

    for index, row in book_data.iterrows():
        # Ensure all fields are strings
        title = str(row['title']) if pd.notna(row['title']) else ""
        genres = str(row['genres']) if pd.notna(row['genres']) else ""
        characters = str(row['characters']) if pd.notna(row['characters']) else ""
        description = str(row['description']) if pd.notna(row['description']) else ""
        
        # Calculate scores
        title_score = max([fuzz.partial_ratio(keyword, title) for keyword in keywords], default=0)
        genre_score = max([fuzz.partial_ratio(keyword, genres) for keyword in keywords], default=0)
        character_score = max([fuzz.partial_ratio(keyword, characters) for keyword in keywords], default=0)
        description_score = fuzz.partial_ratio(summary, description)
        
        # Calculate total score
        total_score = (title_score + genre_score + character_score + description_score) / 4
        book_data.at[index, 'relevance_score'] = total_score
    
    # Sort books by relevance score and return top 10
    top_books = book_data.sort_values(by='relevance_score', ascending=False).head(10)
    print(top_books)
    return top_books


@app.route('/extract', methods=['POST'])
def extract():
    user_input = request.form['user_input']
    analysis = analyze_user_input(user_input)
    keywords = analysis["keywords"]
    summary = analysis["summary"]
    session['keywords'] = keywords  # This should be a list of keywords
    session['summary'] = summary
    top_books = find_relevant_books(keywords, summary)
    session['top_books'] = top_books.to_dict(orient='records')
    return redirect(url_for('loading'))

@app.route('/results')
def results():
    keywords = session.get('keywords', [])  # Retrieve keywords, default to empty list
    summary = session.get('summary', '')    # Retrieve summary, default to empty string
    # Convert list of keywords into a comma-separated string
    keywords_str = ', '.join(keywords) if isinstance(keywords, list) else keywords
    top_books = session.get('top_books', [])
    return render_template('results.html', keywords=keywords_str, summary=summary, books=top_books)




# choose 12 random high rating books to display
def get_book_images():
    high_rating_books = book_data[book_data['rating'] > 4.3]
    if len(high_rating_books) > 12:
        random_books = high_rating_books.sample(n=12)
    else:
        random_books = high_rating_books
    return list(zip(random_books['coverImg'].tolist(), random_books['bookId'].tolist()))


# User signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    book_images = get_book_images()
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        connection, cursor = getCursor()
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        if user:
            flash('Username already exists', 'danger')
        else:
            cursor.execute("INSERT INTO users (UserName, Email, Password, RoleId) VALUES (%s, %s, %s, %s)", 
                           (username, email, password_hash, 2))
            connection.commit()
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))
        cursor.close()
        connection.close()
    return render_template('signup.html', book_images=book_images)

# User login
@app.route('/login', methods=['GET', 'POST'])
def login():
    book_images = get_book_images()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        connection, cursor = getCursor()
        cursor.execute('SELECT * FROM users WHERE UserName = %s', (username,))
        user = cursor.fetchone()
        if user:
            user_id, user_name, email, hashed_password, role_id, is_active = user
            if check_password_hash(hashed_password, password):
                session['user_id'] = user_id
                session['username'] = user_name
                flash('Logged in successfully', 'success')
                return redirect(url_for('book'))
        flash('Invalid username or password', 'danger')
        cursor.close()
        connection.close()
    return render_template('login.html', book_images=book_images)


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/loading')
def loading():
    return render_template('loading.html')

@app.route('/book')
def book():
    top_books = book_data.head(100)
    return render_template('book.html', books=top_books)

@app.route('/book/<string:book_id>')
def book_details(book_id):
    # Find the book in the dataframe
    book = book_data[book_data['bookId'] == book_id].iloc[0]
    return render_template('book_details.html', book=book)



if __name__ == '__main__':
    app.run(debug=True)
