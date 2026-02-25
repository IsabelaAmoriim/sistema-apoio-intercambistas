from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, Usuario

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///intercambio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "admins_grupo02_pds"

db.init_app(app)

# configura flask-login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(id):
    return Usuario.query.get(int(id))

# cria tabelas se não existirem
with app.app_context():
    db.create_all()
    
# rotas
@app.route("/")
@app.route("/index")
def home():
    return render_template("index.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/cadastro", methods=['GET', 'POST'])
def cadastro():
    if request.method == 'GET':
        return render_template("cadastro.html")
    
    elif request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        cpf = request.form['cpf']
        senha = request.form['senha']
        
        email_usado = Usuario.buscar_por_email(email)
        if email_usado:
            flash("Esse email já está sendo utilizado")
            return render_template("cadastro.html")
        
        novo_usuario = Usuario(
            nome=nome,
            email=email,
            cpf=cpf
        )

novo_usuario.definir_senha(senha)
        
        db.session.add(novo_usuario)
        db.session.commit()
        
        flash("Usuário cadastrado com sucesso!")
        return redirect(url_for('login'))

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template("login.html")
    
    elif request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        usuario = Usuario.buscar_por_email(email)
        
        if not usuario or not usuario.verificar_senha(senha):
            flash("Email ou senha incorretos")
            return redirect(url_for("login"))
        
        login_user(usuario)
        flash("Login realizado com sucesso!")
        return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logout realizado com sucesso")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
