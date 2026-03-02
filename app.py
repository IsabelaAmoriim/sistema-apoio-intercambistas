import os
from datetime import datetime
from werkzeug.utils import secure_filename

from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import (
    db, Usuario, Pais, Universidade,
    Documento, DocumentoUsuario, seed_database, Edital
)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///intercambio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = "admins_grupo02_pds"

PASTA_UPLOADS = 'uploads/documentos'
app.config['UPLOAD_FOLDER'] = PASTA_UPLOADS
EXTENSOES_PERMITIDAS = {'pdf', 'png', 'jpg', 'jpeg'}

os.makedirs(PASTA_UPLOADS, exist_ok=True)

def arquivo_permitido(nome_arquivo):
    return '.' in nome_arquivo and \
           nome_arquivo.rsplit('.', 1)[1].lower() in EXTENSOES_PERMITIDAS

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

@app.route("/editais")
@login_required
def lista_editais():
    editais = Edital.query.filter_by(encerrado=False).all()
    return render_template("lista_editais.html", editais=editais)

@app.route("/documentos")
@login_required
def lista_documentos():
    # Busca na base de dados TODOS os documentos que pertencem ao utilizador logado
    meus_documentos = DocumentoUsuario.query.filter_by(usuario_id=current_user.id).all()
    
    # Envia essa lista real para o seu HTML
    return render_template("lista_documentos.html", documentos=meus_documentos)

@app.route("/excluir-documento/<int:id>")
@login_required
def excluir_documento(id):

    doc_para_excluir = DocumentoUsuario.query.filter_by(
        id=id,
        usuario_id=current_user.id
    ).first()

    if doc_para_excluir:

        doc_base_id = doc_para_excluir.documento_id

        # Apaga arquivo físico
        if doc_para_excluir.caminho_arquivo and os.path.exists(doc_para_excluir.caminho_arquivo):
            os.remove(doc_para_excluir.caminho_arquivo)

        # Remove envio do usuário
        db.session.delete(doc_para_excluir)
        db.session.commit()

        # Verifica se esse Documento ainda está sendo usado
        ainda_existe = DocumentoUsuario.query.filter_by(
            documento_id=doc_base_id
        ).first()

        # Se ninguém mais usa, remove o Documento base
        if not ainda_existe:
            doc_base = Documento.query.get(doc_base_id)
            if doc_base and doc_base.descricao == "Enviado pelo aluno":
                db.session.delete(doc_base)
                db.session.commit()

        flash("Documento excluído com sucesso!")

    else:
        flash("Erro: Documento não encontrado.")

    return redirect(url_for('lista_documentos'))

@app.route("/baixar-documento/<int:id>")
@login_required
def baixar_documento(id):
    doc_para_baixar = DocumentoUsuario.query.filter_by(id=id, usuario_id=current_user.id).first()
    
    if doc_para_baixar and doc_para_baixar.caminho_arquivo and os.path.exists(doc_para_baixar.caminho_arquivo):
        return send_file(doc_para_baixar.caminho_arquivo, as
