import os
import uuid
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

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(id):
    return Usuario.query.get(int(id))

with app.app_context():
    db.create_all()
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
    
    usuario_existente = Usuario.buscar_por_email(email)
    if usuario_existente:
        flash("Esse email já está sendo utilizado")
        return render_template("cadastro.html", erro=True)
    
    novo_usuario = Usuario(nome=nome, email=email, cpf=cpf)
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

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/documentos")
@login_required
def lista_documentos():
    meus_documentos = DocumentoUsuario.query.filter_by(usuario_id=current_user.id).all()
    return render_template("lista_documentos.html", documentos=meus_documentos)

@app.route("/excluir-documento/<int:id>", methods=["POST"])
@login_required
def excluir_documento(id):
    doc_para_excluir = DocumentoUsuario.query.filter_by(id=id, usuario_id=current_user.id).first()
    if doc_para_excluir:
        doc_base_id = doc_para_excluir.documento_id
        if doc_para_excluir.caminho_arquivo and os.path.exists(doc_para_excluir.caminho_arquivo):
            os.remove(doc_para_excluir.caminho_arquivo)
        db.session.delete(doc_para_excluir)
        db.session.commit()
        ainda_existe = DocumentoUsuario.query.filter_by(documento_id=doc_base_id).first()
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
        return send_file(doc_para_baixar.caminho_arquivo, as_attachment=True)
    else:
        flash("Erro: O arquivo físico não foi encontrado no servidor.")
        return redirect(url_for('lista_documentos'))

@app.route("/cadastro-documento", methods=['GET', 'POST'])
@login_required
def cadastro_documento():
    if request.method == 'POST':
        if 'arquivo' not in request.files:
            flash('Nenhum ficheiro recebido.')
            return redirect(request.url)
        ficheiro = request.files['arquivo']
        nome_documento = request.form.get('nome') 
        if ficheiro.filename == '':
            flash('Nenhum ficheiro selecionado.')
            return redirect(request.url)
        if ficheiro and arquivo_permitido(ficheiro.filename):
            nome_original = secure_filename(ficheiro.filename)
            nome_unico = f"{uuid.uuid4()}_{nome_original}"
            caminho_salvar = os.path.join(app.config['UPLOAD_FOLDER'], nome_unico)
            ficheiro.save(caminho_salvar)
            doc_base = Documento.query.filter_by(nome=nome_documento).first()
            if not doc_base:
                if not nome_documento:
                    nome_documento = "Documento sem nome"
                doc_base = Documento(nome=nome_documento, descricao="Enviado pelo aluno")
                db.session.add(doc_base)
                db.session.flush() 
            novo_envio = DocumentoUsuario(
                usuario_id=current_user.id,
                documento_id=doc_base.id, 
                caminho_arquivo=caminho_salvar,
                status='Em Análise' 
            )
            db.session.add(novo_envio)
            db.session.commit()
            flash('Documento enviado com sucesso!')
            return redirect(url_for('lista_documentos'))
        else:
            flash('Tipo de ficheiro não suportado. Envie apenas PDF ou Imagens.')
            return redirect(request.url)
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
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash("Acesso negado. Apenas administradores podem acessar esta área.")
        return redirect(url_for("dashboard"))
    return render_template('admin_dashboard.html')

@app.route("/cadastro_paises", methods=['GET', 'POST'])
@login_required
def cadastro_paises():
    if not current_user.is_admin:
        flash("Apenas administradores podem realizar cadastros de países")
        return redirect(url_for("admin_dashboard"))
    if request.method == 'GET':
        return render_template("admin_cadastro_pais.html")
    nome = request.form['nome_pais'].strip().title()
    iso = request.form['sigla_pais'].strip().upper()
    desc = request.form['descricao'].strip()
    nome_usado = Pais.buscar_por_nome(nome)
    if nome_usado:
        flash("Esse país já está cadastrado")
        return redirect(url_for("admin_dashboard"))
    novo_pais = Pais(nome=nome, iso=iso, desc=desc)
    db.session.add(novo_pais)
    db.session.commit()
    flash("País cadastrado com sucesso!")
    return redirect(url_for("admin_dashboard"))

@app.route("/editar_paises/<int:id>", methods=['GET', 'POST'])
@login_required
def editar_paises(id):
    if not current_user.is_admin:
        flash("Apenas administradores podem editar nomes de países")
        return redirect(url_for("admin_dashboard"))
    paises = Pais.buscar_por_id(id)
    if not paises:
        flash("País não encontrado")
        return redirect(url_for("admin_dashboard"))
    if request.method == 'GET':
        return render_template("admin_cadastro_pais.html", paises=paises)
    novo_nome = request.form["nome"].strip().title()
    nome_usado = Pais.buscar_por_nome(novo_nome)
    if nome_usado and nome_usado.id != paises.id:
        flash("Esse nome já pertence a um país cadastrado")
        return render_template("admin_cadastro_pais.html", paises=paises)
    paises.nome = novo_nome
    db.session.commit()
    flash("Alteração bem sucedida!")
    return redirect(url_for("admin_dashboard"))

@app.route("/excluir_paises/<int:id>", methods=['POST'])
@login_required
def excluir_paises(id):
    if not current_user.is_admin:
        flash("Apenas administradores podem excluir países")
        return redirect(url_for("admin_dashboard"))
    paises = Pais.buscar_por_id(id)
    if not paises:
        flash("País não encontrado")
        return redirect(url_for("admin_dashboard"))
    db.session.delete(paises)
    db.session.commit()
    flash("País removido com sucesso!")
    return redirect(url_for("admin_dashboard"))

@app.route('/admin/pais/novo', methods=['GET', 'POST'])
@login_required
def admin_cadastro_pais():
    if not current_user.is_admin:
        flash("Acesso negado. Apenas administradores podem acessar esta área.")
        return redirect(url_for("dashboard"))
    return redirect(url_for('cadastro_paises'))

@app.route('/admin/universidade/novo', methods=['GET', 'POST'])
@login_required
def admin_cadastro_universidade():
    if not current_user.is_admin:
        flash("Acesso negado.")
        return redirect(url_for("dashboard"))

    if request.method == 'POST':
        nome = request.form['nome'].strip().title()
        endereco = request.form['endereco'].strip()
        pais_id = request.form['pais_id']

  
        uni_existente = Universidade.query.filter_by(nome=nome).first()
        if uni_existente:
            flash("Erro: Esta universidade já está cadastrada no sistema.")
            return redirect(url_for('admin_cadastro_universidade'))


        nova_universidade = Universidade(
            nome=nome,
            endereco=endereco,
            pais_id=pais_id
        )

        db.session.add(nova_universidade)
        db.session.commit()

        flash('Universidade cadastrada com sucesso!')
        return redirect(url_for('admin_dashboard'))

    paises = Pais.query.all()
    return render_template('admin_cadastro_universidade.html', paises=paises)

@app.route('/admin/documento/novo', methods=['GET', 'POST'])
@login_required
def admin_cadastro_documento():
    if not current_user.is_admin:
        flash("Acesso negado.")
        return redirect(url_for("dashboard"))
    if request.method == 'POST':
        nome = request.form.get('nome_doc', '').strip().title()
        categoria = request.form.get('categoria', '').strip()
        if not nome or not categoria:
            flash("Preencha todos os campos.")
            return redirect(url_for('admin_cadastro_documento'))
        doc_existente = Documento.query.filter_by(nome=nome).first()
        if doc_existente:
            flash("Esse documento já está cadastrado.")
            return redirect(url_for('admin_cadastro_documento'))
        novo_doc = Documento(nome=nome, descricao=categoria)
        db.session.add(novo_doc)
        db.session.commit()
        flash("Documento cadastrado com sucesso!")
        return redirect(url_for('admin_dashboard'))
    return render_template("admin_cadastro_documento.html")

# --- ROTAS DE EDITAIS ---
@app.route('/admin/editais')
@login_required
def admin_listar_editais():
    if not current_user.is_admin:
        flash("Acesso negado.")
        return redirect(url_for("dashboard"))
    editais_db = Edital.query.all()
    return render_template('admin_edital.html', editais=editais_db)

@app.route('/admin/cadastro/edital', methods=['GET', 'POST'])
@login_required
def admin_cadastro_edital():
    if not current_user.is_admin:
        flash("Acesso negado!")
        return redirect(url_for('index'))

    universidades = Universidade.query.all()
    documentos = Documento.query.all()

    if request.method == 'POST':
        titulo = request.form.get('titulo')
        universidade_id = request.form.get('universidade_id')
        vagas = int(request.form.get('vagas'))
        data_inicial = request.form.get('data_inicial')
        data_limite = request.form.get('data_limite')
        data_inicial_intercambio = request.form.get('data_inicial_intercambio')
        data_limite_intercambio = request.form.get('data_limite_intercambio')
        documentos_id = request.form.getlist('documentos_id')  # lista de checkboxes

        novo_edital = Edital(
            titulo=titulo,
            universidade_id=universidade_id, 
            vagas=vagas,
            data_ini_edital=data_inicial,
            data_fim_edital=data_limite,
            data_ini_programa=data_inicial_intercambio,
            data_fim_programa=data_limite_intercambio
        )

        # adiciona os documentos selecionados
        for doc_id in documentos_id:
            documento = Documento.query.get(doc_id)
            if documento:
                novo_edital.documentos_exigidos.append(documento)

        db.session.add(novo_edital)
        db.session.commit()
        flash("Edital cadastrado com sucesso!")
        return redirect(url_for('admin_listar_editais'))

    return render_template(
        'admin_cadastro_edital.html',
        universidades=universidades,
        documentos=documentos
    )

@app.route('/admin/edital/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_edital(id):
    if not current_user.is_admin:
        flash("Acesso negado.")
        return redirect(url_for("dashboard"))

    edital = Edital.query.get_or_404(id)

    if request.method == 'POST':
        edital.titulo = request.form.get('titulo', '').strip()
        edital.universidade_id = request.form.get('universidade_id')  # <-- ADD
        edital.vagas = int(request.form.get('vagas', 0))

        data_inicial_str = request.form.get('data_inicial')
        data_limite_str = request.form.get('data_limite')
        data_ini_inter_str = request.form.get('data_inicial_intercambio')
        data_lim_inter_str = request.form.get('data_limite_intercambio')

        edital.data_ini_edital = datetime.strptime(data_inicial_str, '%Y-%m-%d').date() if data_inicial_str else None
        edital.data_fim_edital = datetime.strptime(data_limite_str, '%Y-%m-%d').date() if data_limite_str else None
        edital.data_ini_programa = datetime.strptime(data_ini_inter_str, '%Y-%m-%d').date() if data_ini_inter_str else None
        edital.data_fim_programa = datetime.strptime(data_lim_inter_str, '%Y-%m-%d').date() if data_lim_inter_str else None

        # DOCUMENTOS (limpa e adiciona novamente)
        edital.documentos_exigidos.clear()
        documentos_ids = request.form.getlist('documentos_id')

        if documentos_ids:
            docs = Documento.query.filter(Documento.id.in_(documentos_ids)).all()
            edital.documentos_exigidos.extend(docs)

        db.session.commit()
        flash("Edital atualizado com sucesso!")
        return redirect(url_for('admin_listar_editais'))

    # GET
    universidades_db = Universidade.query.all()
    documentos_db = Documento.query.all()

    return render_template(
        'admin_editar_edital.html',
        edital=edital,
        universidades=universidades_db,
        documentos=documentos_db
    )

@app.route('/admin/edital/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_edital(id):
    if not current_user.is_admin:
        return redirect(url_for("dashboard"))
    edital = Edital.query.get(id)
    if edital:
        db.session.delete(edital)
        db.session.commit()
        flash("Edital removido permanentemente!")
    return redirect(url_for('admin_listar_editais'))

if __name__ == "__main__":
    app.run(debug=True)
