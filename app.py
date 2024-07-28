from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/results')
def results():
    return render_template('results.html')

@app.route('/search', methods=['POST'])
def search():
    user_input = request.form['user_input']
    # Process the input and perform the search here
    # For now, we just simulate the delay and redirection
    return redirect(url_for('results'))

if __name__ == '__main__':
    app.run(debug=True)
