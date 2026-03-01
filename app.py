from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import (
    db, Usuario, Pais, Universidade,
    Documento, DocumentoUsuario, seed_database
    )

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///intercambio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "admins_grupo02_pds"

db.init_app(app)

# configuração do flask-login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(id):
    return Usuario.query.get(int(id))

# cria tabelas caso não existam
with app.app_context():
    db.create_all()
    #registra os admins
    seed_database()

@app.route("/")
@app.route("/index")
def home():
    return render_template("index.html")

@app.route("/cadastro", methods=['GET', 'POST'])
def cadastro():
    if request.method == 'GET':
        return render_template("cadastro.html")
    
    nome = request.form['nome']
    email = request.form['email']
    cpf = request.form['cpf']
    senha = request.form['senha']
    
    # verifica se email já existe
    usuario_existente = Usuario.buscar_por_email(email)
    if usuario_existente:
        flash("Esse email já está sendo utilizado")
        return render_template("cadastro.html", erro=True)
    
    # cria novo usuário
    novo_usuario = Usuario(
        nome=nome,
        email=email,
        cpf=cpf
    )
    novo_usuario.definir_senha(senha)
    
    db.session.add(novo_usuario)
    db.session.commit()
    
    # login automático após cadastro
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
    
    if usuario.is_admin:
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logout realizado com sucesso")
    return redirect(url_for("login"))

# rotas do usuário
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

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

# rotas administrativas

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash("Acesso negado. Apenas administradores podem acessar esta área.")
        return redirect(url_for("dashboard"))
    return render_template('admin_dashboard.html')

# países

@app.route("/paises_cadastrados")
@login_required
def paises_cadastrados():
    paises = Pais.query.all()
    return render_template("admin_paises.html", paises=paises)  # MUDOU: paises.html → admin_paises.html

@app.route("/cadastro_paises", methods=['GET', 'POST'])
@login_required
def cadastro_paises():
    if not current_user.is_admin:
        flash("Apenas administradores podem realizar cadastros de países")
        return redirect(url_for("paises_cadastrados"))

    if request.method == 'GET':
        return render_template("admin_cadastro_pais.html")  # MUDOU: cadastro_paises.html → admin_cadastro_pais.html
    
    nome = request.form['nome_pais'].strip().title()
    iso = request.form['sigla_pais'].strip().upper()
    desc = request.form['descricao'].strip()
    
    # verifica se país já existe
    nome_usado = Pais.buscar_por_nome(nome)
    if nome_usado:
        flash("Esse país já está cadastrado")
        return redirect(url_for("paises_cadastrados"))
    
    novo_pais = Pais(
        nome=nome,
        iso=iso,
        desc=desc
    )
    db.session.add(novo_pais)
    db.session.commit()
    flash("País cadastrado com sucesso!")
    return redirect(url_for("paises_cadastrados"))

@app.route("/editar_paises/<int:id>", methods=['GET', 'POST'])
@login_required
def editar_paises(id):
    if not current_user.is_admin:
        flash("Apenas administradores podem editar nomes de países")
        return redirect(url_for("paises_cadastrados"))

    paises = Pais.buscar_por_id(id)
    if not paises:
        flash("País não encontrado")
        return redirect(url_for("paises_cadastrados"))
    
    if request.method == 'GET':
        return render_template("admin_cadastro_pais.html", paises=paises)  # MUDOU: editar_paises.html → admin_cadastro_pais.html (reutiliza o mesmo)
    
    novo_nome = request.form["nome"].strip().title()
    nome_usado = Pais.buscar_por_nome(novo_nome)

    # verifica se o novo nome já existe (exceto se for o mesmo país)
    if nome_usado and nome_usado.id != paises.id:
        flash("Esse nome já pertence a um país cadastrado")
        return render_template("admin_cadastro_pais.html", paises=paises)  # MUDOU
    
    paises.nome = novo_nome
    db.session.commit()
    flash("Alteração bem sucedida!")
    return redirect(url_for("paises_cadastrados"))

@app.route("/excluir_paises/<int:id>", methods=['POST'])
@login_required
def excluir_paises(id):
    if not current_user.is_admin:
        flash("Apenas administradores podem excluir países")
        return redirect(url_for("paises_cadastrados"))

    paises = Pais.buscar_por_id(id)
    if not paises:
        flash("País não encontrado")
        return redirect(url_for("paises_cadastrados"))
    
    db.session.delete(paises)
    db.session.commit()
    flash("País removido com sucesso!")
    return redirect(url_for("paises_cadastrados"))

# rotas antigas

@app.route('/admin/paises')
@login_required
def admin_listar_paises():
    if not current_user.is_admin:
        flash("Acesso negado. Apenas administradores podem acessar esta área.")
        return redirect(url_for("dashboard"))
    
    # redireciona para a rota nova de países
    return redirect(url_for('paises_cadastrados'))

@app.route('/admin/pais/novo', methods=['GET', 'POST'])
@login_required
def admin_cadastro_pais():
    if not current_user.is_admin:
        flash("Acesso negado. Apenas administradores podem acessar esta área.")
        return redirect(url_for("dashboard"))
    
    # redireciona pra rota nova de cadastro
    return redirect(url_for('cadastro_paises'))

@app.route('/admin/universidade/novo', methods=['GET', 'POST'])
@login_required
def admin_cadastro_universidade():
    if not current_user.is_admin:
        flash("Acesso negado. Apenas administradores podem acessar esta área.")
        return redirect(url_for("dashboard"))
    
    if request.method == 'POST':
        flash('Universidade cadastrada com sucesso!')
        return redirect(url_for('admin_dashboard'))
    
    # pega países do banco de dados em vez de lista hardcoded
    paises = Pais.query.all()
    return render_template('admin_cadastro_universidade.html', paises=paises)

@app.route('/admin/documento/novo', methods=['GET', 'POST'])
@login_required
def admin_cadastro_documento():
    if not current_user.is_admin:
        flash("Acesso negado. Apenas administradores podem acessar esta área.")
        return redirect(url_for("dashboard"))
    
    if request.method == 'POST':
        flash('Novo documento obrigatório cadastrado com sucesso!')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin_cadastro_documento.html')

if __name__ == "__main__":
    app.run(debug=True)
