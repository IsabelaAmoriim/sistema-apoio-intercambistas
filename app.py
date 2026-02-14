from flask import Flask, render_template, request, redirect

app = Flask(__name__)

@app.route("/")
def home():
    return "<h1>Projeto Sistema de Apoio a Intercambistas</h1>"

@app.route("/cadastro")
def cadastro():
    return render_template("cadastro.html")

@app.route("/login")
def login():
    return render_template("login.html")

if __name__ == "__main__":
    app.run(debug=True)
