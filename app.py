from flask import Flask, render_template, request, redirect
from models import db, Usuario

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///intercambio.db' #configuração e diretório do db (SQLite)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False #desliga funções desnecessárias do SQLAlchemy

db.init_app(app) #conecta o db com o Flask (servidor)

with app.app_context(): #abre a "conexão"/processo para db e Flask trabalharem juntos
        db.create_all() #cria todas tabelas atreladas ao db (tabela(s) no models.py)
        #o arquivo db será criado na instance

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
