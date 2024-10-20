from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_session import Session
import pandas as pd
import spacy
from rake_nltk import Rake
import re
import nltk
from transformers import T5ForConditionalGeneration, T5Tokenizer
import secrets
from connect import getCursor
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from fuzzywuzzy import fuzz
import numpy as np
from itsdangerous import URLSafeTimedSerializer
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail



DATABASE_URL = os.environ.get('DATABASE_URL')

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



# Initialize Flask App
def create_app():
    app = Flask(__name__)
    
    # Configure Session
    app.config['SECRET_KEY'] = secrets.token_hex(16)
    app.config['SESSION_TYPE'] = 'filesystem'
    Session(app)

    # Other configurations...
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')


    # Configure Flask-Mail for Gmail (if you still plan to use Gmail)
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True  # Use TLS for Gmail, not SSL
    app.config['MAIL_USE_SSL'] = False
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')  # Add this env variable in your system
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')  # Add this env variable in your system
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')  # Typically the same as the username

    # For SendGrid integration
    app.config['SENDGRID_API_KEY'] = os.environ.get('SENDGRID_API_KEY')  # Ensure you have this environment variable


    
    UPLOAD_FOLDER = 'static/uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    # Load book data
    book_data = pd.read_csv('data.csv')
    book_data['coverImg'] = book_data['coverImg'].replace(np.nan, '', regex=True)

    # Load SpaCy model once
    nlp = spacy.load("en_core_web_sm")

    # Download necessary NLTK resources
    nltk.download('stopwords')
    nltk.download('punkt')

    # Load T5 model for summarization
    model_name = "t5-base"
    t5_model = T5ForConditionalGeneration.from_pretrained(model_name)
    t5_tokenizer = T5Tokenizer.from_pretrained(model_name)

    # Extract keywords using SpaCy NER and RAKE with additional contextual analysis
    def extract_keywords(text):
        # Step 1: Extract Named Entities using SpaCy
        doc = nlp(text)
        # Common entity types to extract
        entity_labels = ['PERSON', 'ORG', 'GPE', 'LOC', 'PRODUCT', 'DATE', 'TIME', 'MONEY', 'PERCENT', 'QUANTITY', 'EVENT', 'WORK_OF_ART']
        named_entities = {ent.text for ent in doc.ents if ent.label_ in entity_labels}
        
        # Step 2: Extract keywords using RAKE
        rake = Rake(min_length=1, max_length=3)  # Adjust lengths to capture longer phrases
        rake.extract_keywords_from_text(text)
        rake_keywords = set(rake.get_ranked_phrases())
        
        # Step 3: Combine RAKE keywords and SpaCy Named Entities
        combined_keywords = rake_keywords.union(named_entities)
        
        # Additional contextual analysis
        # Filter out overly generic keywords and those not providing value
        filtered_keywords = [kw for kw in combined_keywords if len(kw.split()) > 1 ]
        
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
        if len(text.split()) < 15:  # Skip summarization for short texts (e.g., < 15 words)
            return text
        # Otherwise, run the T5 summarization
        model_name = "t5-base" 
        model = T5ForConditionalGeneration.from_pretrained(model_name)
        tokenizer = T5Tokenizer.from_pretrained(model_name)
        input_ids = tokenizer.encode("summarize: " + text[:512], return_tensors="pt", max_length=512, truncation=True)
        summary_ids = model.generate(input_ids, max_length=60, min_length=5, length_penalty=2.0, num_beams=3, early_stopping=True)
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
        
        # Sort books by relevance score and return top 15
        top_books = book_data.sort_values(by='relevance_score', ascending=False).head(15)
        print(top_books)
        return top_books


    @app.route('/extract', methods=['POST'])
    def extract():
        # Clear only the specific session data related to search results
        session.pop('keywords', None)  # Remove keywords if it exists
        session.pop('summary', None)    # Remove summary if it exists
        session.pop('top_books', None)  # Remove top_books if it exists

        user_input = request.form['user_input']
        analysis = analyze_user_input(user_input)
        keywords = analysis["keywords"]
        summary = analysis["summary"]
        session['keywords'] = keywords  # This should be a list of keywords
        session['summary'] = summary
        top_books = find_relevant_books(keywords, summary)
        session['top_books'] = top_books.to_dict(orient='records')
        return redirect(url_for('loading'))


    @app.route('/loading')
    def loading():
        return render_template('loading.html')
        
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
                flash('Username already exists. Please log in', 'danger')
            else:
                cursor.execute("INSERT INTO users (UserName, Email, Password, RoleId) VALUES (%s, %s, %s, %s)", 
                            (username, email, password_hash, 2))
                connection.commit()
                flash('Registration successful. Please log in', 'success')
                return redirect(url_for('login'))
            cursor.close()
            connection.close()
        return render_template('signup.html', book_images=book_images)

    # User login
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        book_images = get_book_images()

        # Redirect to dashboard if user is already logged in
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            connection, cursor = getCursor()
            cursor.execute('SELECT UserId, UserName, Password FROM users WHERE UserName = %s', (username,))
            user = cursor.fetchone()
            if user:
                user_id, user_name, hashed_password = user
                if check_password_hash(hashed_password, password):
                    session['user_id'] = user_id
                    session['username'] = user_name
                    flash('Logged in successfully', 'success')

                    # Check if there's a pending wishlist book
                    if 'pending_wishlist_book' in session:
                        pending_book = session.pop('pending_wishlist_book')
                        # Add the pending book to the wishlist
                        return redirect(url_for('add_to_wishlist', book_id=pending_book['book_id']))
                    
                    return redirect(url_for('dashboard'))
                
            flash('Invalid username or password', 'danger')
            cursor.close()
            connection.close()
        return render_template('login.html', book_images=book_images)

    @app.route('/logout')
    def logout():
        session.clear()
        flash('You have been logged out', 'success')
        book_images = get_book_images()  # Fetch book images again
        return render_template('login.html', book_images=book_images)

    @app.route('/')
    def home():
        return render_template('index.html')

    @app.route('/about')
    def about():
        return render_template('about.html')
    

    @app.route('/book/<string:book_id>')
    def book_details(book_id):
        # Find the book in the dataframe
        matching_books = book_data[book_data['bookId'] == book_id]
        if not matching_books.empty:
            book = matching_books.iloc[0]
            user_id = session.get('user_id')
            in_wishlist = False
            
            if user_id:
                connection, cursor = getCursor()
                cursor.execute('SELECT * FROM wishlist WHERE UserId = %s AND BookId = %s', (user_id, book_id))
                in_wishlist = cursor.fetchone() is not None
                cursor.close()
            
            return render_template('book_details.html', book=book, in_wishlist=in_wishlist)
        else:
            return "Book not found", 404
        

    # wishlist
    @app.route('/add_to_wishlist/<string:book_id>', methods=['GET', 'POST'])
    def add_to_wishlist(book_id):
        # Retrieve book details using the existing logic from the book_details route
        matching_books = book_data[book_data['bookId'] == book_id]
        
        if not matching_books.empty:
            book = matching_books.iloc[0]
            title = book['title']  # Adjust to your actual column name for title
            cover_img = book['coverImg']  # Adjust to your actual column name for cover image
        else:
            flash('Book not found in our database.', 'danger')
            return redirect(url_for('dashboard'))


        # Check if user is logged in
        if 'user_id' not in session:
            # Store the book details in the session temporarily
            session['pending_wishlist_book'] = {
                'book_id': book_id,
                'title': title,
                'cover_img': cover_img
            }
            # Flash a message and redirect to the login page
            flash('Please log in to add books to your wishlist.', 'danger')
            return redirect(url_for('login'))

        user_id = session['user_id']
        connection, cursor = getCursor()
        try:
            # Check if the book is already in the wishlist
            cursor.execute('SELECT * FROM wishlist WHERE UserId = %s AND BookId = %s', (user_id, book_id))
            existing_entry = cursor.fetchone()
            if existing_entry:
                flash('This book is already in your wishlist.', 'info')
            else:
                cursor.execute(
                    'INSERT INTO wishlist (UserId, BookId, Title, CoverImg) VALUES (%s, %s, %s, %s)',
                    (user_id, book_id, title, cover_img)
                )
                connection.commit()
                flash('Book added to your wishlist successfully!', 'success')
        except Exception as e:
                connection.rollback()
                flash(f'An error occurred: {str(e)}', 'danger')
        finally:
                cursor.close()
                connection.close()
        return redirect(url_for('book_details', book_id=book_id))



    @app.route('/remove_from_wishlist/<string:book_id>/<string:redirect_page>', methods=['POST'])
    def remove_from_wishlist(book_id, redirect_page):
        if 'user_id' not in session:
            flash('You need to be logged in to remove books from your wishlist.', 'danger')
            return redirect(url_for('login'))

        user_id = session['user_id']
        connection, cursor = getCursor()

        try:
            # Remove the book from the wishlist
            cursor.execute('DELETE FROM wishlist WHERE UserId = %s AND BookId = %s', (user_id, book_id))
            connection.commit()
            # Check if the deletion was successful
            if cursor.rowcount == 0:
                flash('This book was not found in your wishlist.', 'info')
            else:
                flash('Book removed from your wishlist successfully!', 'danger')
        except Exception as e:
            connection.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
        finally:
            cursor.close()
            connection.close()

        # Redirect based on where the user came from
        if redirect_page == 'book_details':
            return redirect(url_for('book_details', book_id=book_id))
        elif redirect_page == 'dashboard':
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('dashboard'))  # Fallback to dashboard if no page is provided


    @app.route('/dashboard')
    def dashboard():
        if 'user_id' not in session:
            flash('Please log in to access your dashboard.', 'danger')
            return redirect(url_for('login'))
        
        user_id = session['user_id']
        username = session.get('username', 'User') 
        connection, cursor = getCursor()
        try:
            # Fetch the wishlist items for the user
            cursor.execute('SELECT * FROM wishlist WHERE UserId = %s', (user_id,))
            wishlist_books = cursor.fetchall()
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'danger')
            wishlist_books = []
        finally:
            cursor.close()
            connection.close()

        return render_template('dashboard.html', wishlist_books=wishlist_books, username=username)



    @app.route('/author/<author_name>')
    def author_books(author_name):
        # Filter the DataFrame to find books by the specific author
        author_books = book_data[book_data['author'].str.contains(author_name, na=False)]

        # Convert the filtered DataFrame to a list of dictionaries to pass to the template
        books_list = author_books.to_dict(orient='records')

        return render_template('author_books.html', author=author_name, books=books_list)


    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


    @app.route('/profile', methods=['GET', 'POST'])
    def profile():
        if 'user_id' not in session:
            flash('Please log in to view your profile.', 'danger')
            return redirect(url_for('login'))

        user_id = session['user_id']
        connection, cursor = getCursor()

        try:
            if request.method == 'POST':
                # Update username and email
                new_username = request.form.get('username')
                new_email = request.form.get('email')

                if new_username and new_email:
                    cursor.execute(
                        'UPDATE users SET UserName = %s, Email = %s WHERE UserId = %s',
                        (new_username, new_email, user_id)
                    )
                    connection.commit()
                    session['username'] = new_username
                    flash('Profile updated successfully!', 'success')

                # Update profile image if a new one is uploaded
                if 'profile_image' in request.files:
                    profile_image = request.files['profile_image']
                    if profile_image and allowed_file(profile_image.filename):
                        # Save the image to the uploads folder
                        filename = secure_filename(profile_image.filename)
                        profile_image_path = os.path.join('static/uploads', filename)

                        # Create the uploads folder if it doesn't exist
                        os.makedirs(os.path.dirname(profile_image_path), exist_ok=True)

                        profile_image.save(profile_image_path)

                        # Update the user's profile image in the database
                        cursor.execute('UPDATE users SET ProfileImage = %s WHERE UserId = %s', (filename, user_id))
                        connection.commit()
                        flash('Profile image updated successfully!', 'success')

            # Fetch user information
            cursor.execute('SELECT UserName, Email, ProfileImage FROM users WHERE UserId = %s', (user_id,))
            user = cursor.fetchone()

        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'danger')
            user = None
        finally:
            cursor.close()
            connection.close()

        return render_template('profile.html', user=user)

    @app.errorhandler(404)
    def page_not_found(e):
        # Render the custom 404 error page
        return render_template('404.html'), 404
    
    
    # Serializer to generate and validate tokens
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    
    # Forgot Password Form Route
    @app.route('/forgot_password', methods=['GET', 'POST'])
    def forgot_password():
        if request.method == 'POST':
            email = request.form['email']
            connection, cursor = getCursor()

            cursor.execute('SELECT * FROM users WHERE Email = %s', (email,))
            user = cursor.fetchone()

            if user:
                # Generate a secure token with the user's email
                token = serializer.dumps(email, salt='password-reset-salt')
                # Construct reset URL
                reset_url = url_for('reset_password', token=token, _external=True)
                # Email sending logic

                # Send reset password email using SendGrid
                message = Mail(
                    from_email=os.environ.get('MAIL_USERNAME'),  # Your verified sender email
                    to_emails=email,
                    subject='Password Reset Request',
                    html_content=f'<p>Click the link to reset your password: <a href="{reset_url}">{reset_url}</a></p>'
                )

                try:
                    sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
                    response = sg.send(message)
                    flash('A password reset link has been sent to your email.', 'info')
                except Exception as e:
                    flash(f'Failed to send email: {str(e)}', 'danger')

            else:
                flash('Email not found.', 'danger')

            cursor.close()
            connection.close()

        return render_template('forgot_password.html')


    # Reset Password Form Route
    @app.route('/reset_password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        # Try to decode the token to get the user's email
        try:
            email = serializer.loads(token, salt='password-reset-salt', max_age=3600)  # 1-hour expiration
        except Exception as e:
            flash('The reset link is invalid or has expired.', 'danger')
            return redirect(url_for('forgot_password'))

        # Handle POST request to update the password
        if request.method == 'POST':
            password = request.form['password']
            
            # Validate the password (add any additional validation if needed)
            if not password:
                flash('Please enter a password.', 'danger')
                return render_template('reset_password.html', token=token)

            password_hash = generate_password_hash(password, method='pbkdf2:sha256')
            
            # Establish database connection
            connection, cursor = getCursor()

            try:
                # Update the user's password in the database
                cursor.execute('UPDATE users SET Password = %s WHERE Email = %s', (password_hash, email))
                connection.commit()

                # Check if the update was successful
                if cursor.rowcount == 0:
                    flash('Error updating password. Please try again.', 'danger')
                else:
                    flash('Your password has been updated!', 'success')
                    return redirect(url_for('login'))
            except Exception as e:
                connection.rollback()
                flash(f'An error occurred while updating your password: {str(e)}', 'danger')
            finally:
                # Ensure resources are always cleaned up
                cursor.close()
                connection.close()

        # Render the reset password form
        return render_template('reset_password.html', token=token)


    return app



if __name__ == '__main__':
    init_db()
    app = create_app()
    app.run(debug=True)
