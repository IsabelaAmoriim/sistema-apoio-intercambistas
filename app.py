import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from datetime import datetime, date

from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import (
    db, Usuario, Pais, Universidade,
    Documento, DocumentoUsuario, seed_database, Edital, Inscricao, Topico
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
    inscricao = Inscricao.query.filter_by(usuario_id=current_user.id).order_by(Inscricao.data_inscricao.desc()).first()
    
    progresso = 0
    tarefas_resumo = []
    documentos_faltando = 0
    dias_para_viagem = None # <--- NOVA VARIÁVEL PARA A CONTAGEM

    if inscricao:
        edital = inscricao.edital
        documentos_exigidos = edital.documentos_exigidos
        docs_enviados_ids = [doc.documento_id for doc in current_user.documentos_enviados]
        
        tarefas_concluidas = 1
        total_tarefas = 1 + len(documentos_exigidos)
        
        tarefas_resumo.append({"nome": "Inscrição no Edital", "feito": True})
        
        for doc in documentos_exigidos:
            if doc.id in docs_enviados_ids:
                tarefas_concluidas += 1
                tarefas_resumo.append({"nome": f"Enviar {doc.nome}", "feito": True})
            else:
                documentos_faltando += 1
                tarefas_resumo.append({"nome": f"Enviar {doc.nome}", "feito": False})
        
        progresso = int((tarefas_concluidas / total_tarefas) * 100) if total_tarefas > 0 else 0
        tarefas_resumo = tarefas_resumo[:3]

        # --- NOVA LÓGICA DE APOIO: CONTAGEM REGRESSIVA ---
        if inscricao.status == 'Aprovado' and edital.data_ini_programa:
            hoje = datetime.utcnow().date()
            diferenca = edital.data_ini_programa - hoje
            dias_para_viagem = diferenca.days
        # ------------------------------------------------

    return render_template("dashboard.html", 
                           inscricao=inscricao, 
                           progresso=progresso, 
                           tarefas_resumo=tarefas_resumo, 
                           documentos_faltando=documentos_faltando,
                           dias_para_viagem=dias_para_viagem)
@app.route("/documentos")
@login_required
def lista_documentos():
    meus_documentos = DocumentoUsuario.query.filter_by(usuario_id=current_user.id).all()
    return render_template("lista_documentos.html", documentos=meus_documentos)

@app.route("/cadastro-documento", methods=['GET', 'POST'])
@login_required
def cadastro_documento():
    # 1. Verifica se o aluno já se inscreveu em algum edital
    edital_atual = Edital.query.filter_by(encerrado=False).order_by(Edital.data_ini_edital.desc()).first()
    if not edital_atual:
        flash("Não há editais abertos no momento!")
        return redirect(url_for('editais_abertos'))

    # 2. Pega os documentos que o Edital exige e os que o aluno já enviou
    documentos_exigidos = edital_atual.documentos_exigidos
    docs_enviados_ids = [doc.documento_id for doc in current_user.documentos_enviados]
    
    # 3. Filtra apenas os que faltam enviar (Pendentes)
    documentos_pendentes = [doc for doc in documentos_exigidos if doc.id not in docs_enviados_ids]

    if request.method == 'POST':
        documento_id = request.form.get('documento_id') # Recebe o ID da caixa de seleção
        
        if 'arquivo' not in request.files:
            flash('Nenhum arquivo recebido.')
            return redirect(request.url)
            
        ficheiro = request.files['arquivo']
        if ficheiro.filename == '':
            flash('Nenhum arquivo selecionado.')
            return redirect(request.url)
            
        if ficheiro and arquivo_permitido(ficheiro.filename):
            nome_original = secure_filename(ficheiro.filename)
            nome_unico = f"{uuid.uuid4()}_{nome_original}"
            caminho_salvar = os.path.join(app.config['UPLOAD_FOLDER'], nome_unico)
            ficheiro.save(caminho_salvar)
            
            # Salva o arquivo vinculando diretamente à obrigatoriedade do Admin!
            novo_envio = DocumentoUsuario(
                usuario_id=current_user.id,
                documento_id=documento_id, 
                caminho_arquivo=caminho_salvar,
                status='Em Análise' 
            )
            db.session.add(novo_envio)
            db.session.commit()
            flash('Documento enviado com sucesso!')
            return redirect(url_for('checklist'))
        else:
            flash('Tipo de arquivo não suportado. Envie apenas PDF ou Imagens.')
            return redirect(request.url)
            
    # Envia a lista de pendentes para a tela do aluno
    return render_template("cadastro_documento.html", pendentes=documentos_pendentes)

@app.route("/excluir-documento/<int:id>", methods=["GET", "POST"]) # Correção do Erro 405 (Aceita GET agora)
@login_required
def excluir_documento(id):
    # Encontra o arquivo enviado pelo aluno
    doc_para_excluir = DocumentoUsuario.query.filter_by(id=id, usuario_id=current_user.id).first()
    
    if doc_para_excluir:
        # Apaga o arquivo físico do computador
        if doc_para_excluir.caminho_arquivo and os.path.exists(doc_para_excluir.caminho_arquivo):
            os.remove(doc_para_excluir.caminho_arquivo)
            
        # Apaga APENAS a relação do aluno, NUNCA o documento base do Admin
        db.session.delete(doc_para_excluir)
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

@app.route("/checklist")
@login_required
def checklist():
    inscricao = Inscricao.query.filter_by(usuario_id=current_user.id).order_by(Inscricao.data_inscricao.desc()).first()
    
    if not inscricao:
        return render_template("checklist.html", inscricao=None)

    edital = inscricao.edital
    documentos_exigidos = edital.documentos_exigidos
    
    docs_enviados_ids = [doc.documento_id for doc in current_user.documentos_enviados]
    
    tarefas = []
    tarefas_concluidas = 0

    tarefas.append({"nome": "Inscrição no Edital (CRA e Carta)", "icone": "fa-file-signature", "status": "Concluído", "classe": "concluido"})
    tarefas_concluidas += 1

    for doc in documentos_exigidos:
        if doc.id in docs_enviados_ids:
            tarefas.append({"nome": f"Enviar {doc.nome}", "icone": "fa-check-circle", "status": "Concluído", "classe": "concluido"})
            tarefas_concluidas += 1
        else:
            tarefas.append({"nome": f"Enviar {doc.nome}", "icone": "fa-upload", "status": "Pendente", "classe": "pendente"})

    total_tarefas = len(tarefas)
    progresso = int((tarefas_concluidas / total_tarefas) * 100) if total_tarefas > 0 else 0

    return render_template("checklist.html", inscricao=inscricao, tarefas=tarefas, progresso=progresso)

@app.route("/forum")
@login_required
def forum():
    # Busca todos os tópicos no banco, ordenados do mais recente para o mais antigo
    topicos_db = Topico.query.order_by(Topico.data_criacao.desc()).all()
    return render_template("forum.html", topicos=topicos_db)

@app.route("/forum/topico/<int:id>")
@login_required
def forum_ler_topico(id):
    # Busca o tópico específico pelo ID que veio no link
    topico_db = Topico.query.get_or_404(id)
    return render_template("forum_ler_topico.html", topico=topico_db)

@app.route("/forum/escrever", methods=['GET', 'POST'])
@login_required
def forum_escrever():
    if request.method == 'POST':
        titulo = request.form.get('titulo')
        conteudo = request.form.get('conteudo')
        
        # Cria a nova postagem no banco
        novo_topico = Topico(
            titulo=titulo,
            conteudo=conteudo,
            usuario_id=current_user.id
        )
        
        db.session.add(novo_topico)
        db.session.commit()
        
        flash("Tópico criado com sucesso!")
        return redirect(url_for('forum'))
        
    return render_template("forum_escrever.html")

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
        documentos_id = request.form.getlist('documentos_id')

        if not documentos_id:
            flash("Erro: É obrigatório selecionar pelo menos um documento exigido para publicar o edital.")
            return redirect(url_for('admin_cadastro_edital'))

        novo_edital = Edital(
            titulo=titulo,
            universidade_id=universidade_id,  
            vagas=vagas,
            data_ini_edital=datetime.strptime(data_inicial, '%Y-%m-%d').date(),
            data_fim_edital=datetime.strptime(data_limite, '%Y-%m-%d').date(),
            data_ini_programa=datetime.strptime(data_inicial_intercambio, '%Y-%m-%d').date(),
            data_fim_programa=datetime.strptime(data_limite_intercambio, '%Y-%m-%d').date()
        )

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

@app.route("/editais-abertos")
@login_required
def editais_abertos():
    editais_disponiveis = Edital.query.filter_by(encerrado=False).all()
    return render_template("editais_abertos.html", editais=editais_disponiveis)

@app.route("/edital/<int:id>")
@login_required
def detalhes_edital(id):
    
    edital_db = Edital.query.get_or_404(id)
    
    return render_template("detalhes_edital.html", edital=edital_db)

@app.route('/edital/<int:edital_id>/visualizar')
@login_required
def visualizar_edital(edital_id):
    """Rota para visualizar detalhes do edital antes de se inscrever"""
    edital = Edital.query.get_or_404(edital_id)
    
    # verifica se já tá inscrito
    ja_inscrito = current_user.esta_inscrito_no_edital(edital_id)
    
    # verifica documentos faltantes
    docs_faltantes = current_user.documentos_faltantes_para_edital(edital)
    
    # verifica status do período de inscrição
    pode_inscrever = edital.esta_no_periodo_inscricao() and not ja_inscrito
    
    return render_template(
        'visualizacao_edital.html', 
        edital=edital,
        ja_inscrito=ja_inscrito,
        docs_faltantes=docs_faltantes,
        pode_inscrever=pode_inscrever
    )

@app.route("/edital/<int:id>/inscrever", methods=['GET', 'POST'])
@login_required
def inscrever_edital(id):
    edital = Edital.query.get_or_404(id)
    
    
    if edital.inscricoes_encerradas():
        flash("O período de inscrições para esse edital está encerrado")
        return redirect(url_for('dashboard'))
    
    if edital.inscricoes_nao_iniciadas():
        flash("O período para inscrição desse edital ainda não começou")
        return redirect(url_for('dashboard'))
    
    inscricao_existente = Inscricao.query.filter_by(usuario_id=current_user.id, edital_id=edital.id).first()
    if inscricao_existente:
        flash("Você já está inscrito neste edital! Acompanhe o status no seu Checklist.")
        return redirect(url_for('dashboard'))
    
 
    if not edital.tem_vagas_disponiveis():
        flash("Não há mais vagas disponíveis para este edital")
        return redirect(url_for('dashboard'))
    
    
    docs_faltantes = current_user.documentos_faltantes_para_edital(edital)
    if docs_faltantes:
        faltantes = ", ".join(docs_faltantes)
        flash(f"Não foi possível realizar a inscrição, faltam os seguintes documentos: {faltantes}")
        return redirect(url_for('lista_documentos'))

    if request.method == 'POST':
        cra = request.form.get('cra')
        carta = request.form.get('carta_motivacao')
        
        
        nova_inscricao = Inscricao(
            usuario_id=current_user.id,
            edital_id=edital.id,
            cra=float(cra),
            carta_motivacao=carta,
            status="Ativa" 
        )
        
        db.session.add(nova_inscricao)
        db.session.commit()
        
        flash("Inscrição realizada com sucesso! Agora acompanhe pelo seu Checklist.")
        return redirect(url_for('checklist'))
    
    # --- EXIBIÇÃO DO FORMULÁRIO (GET) ---
    return render_template("inscricao_edital.html", edital=edital)


@app.route('/edital/<int:edital_id>/cancelar_inscricao', methods=['POST'])
@login_required
def cancelar_inscricao(edital_id):
    """Rota pra cancelar inscrição em um edital"""
    inscricao = Inscricao.query.filter_by(
        usuario_id=current_user.id, 
        edital_id=edital_id
    ).first_or_404()

    # método para cancelar
    inscricao.cancelar()
    
    flash("Inscrição cancelada com sucesso")
    return redirect(url_for('dashboard'))

@app.route('/admin/inscricoes')
@login_required
def admin_listar_inscricoes():
    if not current_user.is_admin:
        flash("Acesso negado.")
        return redirect(url_for('dashboard'))
    
    # Busca todas as inscrições, da mais recente para a mais antiga
    inscricoes = Inscricao.query.order_by(Inscricao.data_inscricao.desc()).all()
    return render_template('admin_listar_inscricoes.html', inscricoes=inscricoes)

@app.route('/admin/inscricao/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_avaliar_inscricao(id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))

    inscricao = Inscricao.query.get_or_404(id)

    if request.method == 'POST':
        acao = request.form.get('acao') # Pega se o admin clicou em aprovar ou reprovar
        
        if acao == 'aprovar':
            inscricao.status = 'Aprovado'
            flash(f"Candidatura de {inscricao.usuario.nome} APROVADA com sucesso!")
        elif acao == 'reprovar':
            inscricao.status = 'Reprovado'
            flash(f"Candidatura de {inscricao.usuario.nome} REPROVADA.")
            
        db.session.commit()
        return redirect(url_for('admin_listar_inscricoes'))

    # Pega apenas os documentos que este aluno enviou para os requisitos deste edital
    docs_exigidos_ids = [doc.id for doc in inscricao.edital.documentos_exigidos]
    documentos_aluno = DocumentoUsuario.query.filter(
        DocumentoUsuario.usuario_id == inscricao.usuario_id,
        DocumentoUsuario.documento_id.in_(docs_exigidos_ids)
    ).all()

    return render_template('admin_avaliar_inscricao.html', inscricao=inscricao, documentos=documentos_aluno)

@app.route('/admin/baixar-documento/<int:id>')
@login_required
def admin_baixar_documento(id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
        
    doc = DocumentoUsuario.query.get_or_404(id)
    
    # Verifica se o caminho existe e previne erros de barras no Windows
    if doc.caminho_arquivo and os.path.exists(doc.caminho_arquivo):
        caminho_absoluto = os.path.abspath(doc.caminho_arquivo)
        return send_file(caminho_absoluto, as_attachment=True)
    else:
        flash("Erro: O arquivo físico não foi encontrado na pasta do sistema! O aluno precisa reenviar o documento.")
        return redirect(request.referrer or url_for('admin_listar_inscricoes'))

# --- ROTA DE MATCH DE DESTINO (REDE DE CONTATOS) ---
@app.route("/colegas")
@login_required
def colegas_viagem():
    # 1. Procura se o aluno atual tem uma inscrição aprovada
    minha_inscricao = Inscricao.query.filter_by(usuario_id=current_user.id, status='Aprovado').first()

    if not minha_inscricao:
        flash("Você precisa ter uma candidatura aprovada para acessar a Rede de Contatos!")
        return redirect(url_for('dashboard'))

    # 2. Descobre qual é o país de destino dele
    meu_pais_id = minha_inscricao.edital.universidade.pais_id
    nome_do_pais = minha_inscricao.edital.universidade.pais_origem.nome

    # 3. Busca todos os outros alunos aprovados
    todas_aprovadas = Inscricao.query.filter(Inscricao.status == 'Aprovado', Inscricao.usuario_id != current_user.id).all()
    
    colegas = []
    for inscricao in todas_aprovadas:
        # Se o país do colega for igual ao meu, dá match!
        if inscricao.edital.universidade.pais_id == meu_pais_id:
            colegas.append(inscricao)

    return render_template("colegas_viagem.html", colegas=colegas, pais=nome_do_pais)

if __name__ == "__main__":
    app.run(debug=True)
