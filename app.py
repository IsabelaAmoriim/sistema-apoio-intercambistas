from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, Usuario

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///intercambio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "admins_grupo02_pds"

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(id):
    return Usuario.query.get(int(id))

with app.app_context():
    db.create_all()

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
    
    nome = request.form['nome']
    email = request.form['email']
    cpf = request.form['cpf']
    senha = request.form['senha']
    
    usuario_existente = Usuario.buscar_por_email(email)
    if usuario_existente:
        flash("Esse email já está sendo utilizado")
        return render_template("cadastro.html", erro=True)
    
    novo_usuario = Usuario(
        nome=nome,
        email=email,
        cpf=cpf
    )
    novo_usuario.definir_senha(senha)
    
    db.session.add(novo_usuario)
    db.session.commit()
    
    login_user(novo_usuario)
    
    flash("Cadastro realizado com sucesso!")
    return redirect(url_for('dashboard'))

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template("login.html")
    
    email = request.form['email']
    senha = request.form['senha']
    
    usuario = Usuario.buscar_por_email(email)
    
    if not usuario or not usuario.verificar_senha(senha):
        flash("Email ou senha incorretos")
        return render_template("login.html", erro=True)
    
    login_user(usuario)
    flash("Login realizado com sucesso!")
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logout realizado com sucesso")
    return redirect(url_for("login"))
    
@app.route("/documentos")
@login_required
def lista_documentos():
    docs_teste = [
        {'nome': 'Passaporte.pdf', 'tipo': 'Identidade', 'status': 'Validado', 'status_classe': 'validado'},
        {'nome': 'Historico_Escolar.pdf', 'tipo': 'Acadêmico', 'status': 'Em Análise', 'status_classe': 'pendente'},
    ]
    return render_template("lista_documentos.html", documentos=docs_teste)

@app.route("/cadastro-documento")
@login_required
def cadastro_documento():
    return render_template("cadastro_documento.html")    

@app.route("/checklist")
@login_required
def checklist():
    return render_template("checklist.html")

@app.route("/forum")
@login_required
def forum():
    return render_template("forum.html")

@app.route('/admin')
def admin_dashboard():
    return render_template('admin_dashboard.html')


@app.route('/admin/paises')
def admin_listar_paises():
    
    lista_teste = ["Austrália", "Canadá", "Espanha", "Irlanda", "Portugal"]
    return render_template('admin_paises.html', paises=lista_teste)


@app.route('/admin/pais/novo', methods=['GET', 'POST'])
def admin_cadastro_pais():
    if request.method == 'POST':
        flash('País cadastrado com sucesso no sistema!')
        return redirect(url_for('admin_dashboard')) 
    
    return render_template('admin_cadastro_pais.html')

@app.route('/admin/universidade/novo', methods=['GET', 'POST'])
def admin_cadastro_universidade():
    if request.method == 'POST':
        flash('Universidade cadastrada com sucesso!')
        return redirect(url_for('admin_dashboard'))
        
    lista_teste = ["Austrália", "Canadá", "Espanha", "Irlanda", "Portugal"]
    return render_template('admin_cadastro_universidade.html', paises=lista_teste)

@app.route('/admin/documento/novo', methods=['GET', 'POST'])
def admin_cadastro_documento():
    if request.method == 'POST':
        flash('Novo documento obrigatório cadastrado com sucesso!')
        return redirect(url_for('admin_dashboard'))
        
    return render_template('admin_cadastro_documento.html')

if __name__ == "__main__":
    app.run(debug=True)