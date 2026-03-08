import os
import uuid
from datetime import datetime, date
from werkzeug.utils import secure_filename

from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask.views import MethodView
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


class Home(MethodView):
    def get(self):
        return render_template("index.html")

app.add_url_rule('/', view_func=Home.as_view('home'))
app.add_url_rule('/index', view_func=Home.as_view('index'))


class Cadastro(MethodView):
    def get(self):
        return render_template("cadastro.html")

    def post(self):
        nome = request.form.get('nome')
        email = request.form.get('email')
        cpf = request.form.get('cpf')
        senha = request.form.get('senha')
        
        if Usuario.buscar_por_email(email):
            flash("Esse email já está sendo utilizado")
            return render_template("cadastro.html", erro=True)
        
        self._criar_e_logar_usuario(nome, email, cpf, senha)
        
        flash("Cadastro realizado com sucesso!")
        return redirect(url_for('dashboard'))

    def _criar_e_logar_usuario(self, nome, email, cpf, senha):
        novo_usuario = Usuario(nome=nome, email=email, cpf=cpf)
        novo_usuario.definir_senha(senha)
        
        db.session.add(novo_usuario)
        db.session.commit()
        login_user(novo_usuario)

app.add_url_rule('/cadastro', view_func=Cadastro.as_view('cadastro'))


class Login(MethodView):
    def get(self):
        return render_template("login.html")

    def post(self):
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


class Logout(MethodView):
    decorators = [login_required]

    def get(self):
        logout_user()
        flash("Logout realizado com sucesso")
        return redirect(url_for("login"))

app.add_url_rule('/login', view_func=Login.as_view('login'))
app.add_url_rule('/logout', view_func=Logout.as_view('logout'))


class Dashboard(MethodView):
    decorators = [login_required]

    def get(self):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário. Use o painel administrativo.")
            return redirect(url_for('admin_dashboard'))
        
        inscricao = current_user.get_inscricao_mais_recente()
        
        progresso = 0
        tarefas_resumo = []
        documentos_faltando = 0
        dias_para_viagem = None

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

            if inscricao.status == 'Aprovado' and edital.data_ini_programa:
                hoje = date.today()
                diferenca = edital.data_ini_programa - hoje
                dias_para_viagem = diferenca.days

        return render_template("dashboard.html", 
                               inscricao=inscricao, 
                               progresso=progresso, 
                               tarefas_resumo=tarefas_resumo, 
                               documentos_faltando=documentos_faltando,
                               dias_para_viagem=dias_para_viagem)

app.add_url_rule('/dashboard', view_func=Dashboard.as_view('dashboard'))


class Documentos(MethodView):
    decorators = [login_required]

    def get(self):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        meus_documentos = DocumentoUsuario.query.filter_by(usuario_id=current_user.id).all()
        return render_template("lista_documentos.html", documentos=meus_documentos)

app.add_url_rule('/documentos', view_func=Documentos.as_view('lista_documentos'))


class CadastroDocumento(MethodView):
    decorators = [login_required]

    def _obter_dados_inscricao(self):
        inscricao = current_user.get_inscricao_mais_recente()
        
        if not inscricao:
            return None, []
        
        documentos_exigidos = inscricao.edital.documentos_exigidos
        docs_enviados_ids = [doc.documento_id for doc in current_user.documentos_enviados]
        documentos_pendentes = [doc for doc in documentos_exigidos if doc.id not in docs_enviados_ids]
        
        return inscricao, documentos_pendentes

    def get(self):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        inscricao, documentos_pendentes = self._obter_dados_inscricao()
        
        if not inscricao:
            flash("Você precisa se inscrever em um edital antes de enviar documentos!")
            return redirect(url_for('editais_abertos'))
            
        return render_template("cadastro_documento.html", pendentes=documentos_pendentes)

    def post(self):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        inscricao, documentos_pendentes = self._obter_dados_inscricao()
        
        if not inscricao:
            flash("Você precisa se inscrever em um edital antes de enviar documentos!")
            return redirect(url_for('editais_abertos'))

        documento_id = request.form.get('documento_id')
        
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

app.add_url_rule('/cadastro-documento', view_func=CadastroDocumento.as_view('cadastro_documento'))


class ExcluirDocumento(MethodView):
    decorators = [login_required]

    def _processar_exclusao(self, id):
        doc_para_excluir = DocumentoUsuario.query.filter_by(id=id, usuario_id=current_user.id).first()
        
        if doc_para_excluir:
            if doc_para_excluir.caminho_arquivo and os.path.exists(doc_para_excluir.caminho_arquivo):
                os.remove(doc_para_excluir.caminho_arquivo)
                
            db.session.delete(doc_para_excluir)
            db.session.commit()
            flash("Documento excluído com sucesso!")
        else:
            flash("Erro: Documento não encontrado.")
            
        return redirect(url_for('lista_documentos'))

    def get(self, id):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        return self._processar_exclusao(id)

    def post(self, id):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        return self._processar_exclusao(id)


class BaixarDocumento(MethodView):
    decorators = [login_required]

    def get(self, id):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        doc_para_baixar = DocumentoUsuario.query.filter_by(id=id, usuario_id=current_user.id).first()
        
        if doc_para_baixar and doc_para_baixar.caminho_arquivo and os.path.exists(doc_para_baixar.caminho_arquivo):
            return send_file(doc_para_baixar.caminho_arquivo, as_attachment=True)
        else:
            flash("Erro: O arquivo físico não foi encontrado no servidor.")
            return redirect(url_for('lista_documentos'))

app.add_url_rule('/excluir-documento/<int:id>', view_func=ExcluirDocumento.as_view('excluir_documento'))
app.add_url_rule('/baixar-documento/<int:id>', view_func=BaixarDocumento.as_view('baixar_documento'))


class Checklist(MethodView):
    decorators = [login_required]

    def get(self):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        inscricao = current_user.get_inscricao_mais_recente()
        
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

app.add_url_rule('/checklist', view_func=Checklist.as_view('checklist'))


class Forum(MethodView):
    decorators = [login_required]

    def get(self):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        topicos_db = Topico.query.order_by(Topico.data_criacao.desc()).all()
        return render_template("forum.html", topicos=topicos_db)

app.add_url_rule('/forum', view_func=Forum.as_view('forum'))


class ForumTopico(MethodView):
    decorators = [login_required]

    def get(self, id):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        topico_db = Topico.query.get_or_404(id)
        return render_template("forum_ler_topico.html", topico=topico_db)


class ForumEscrever(MethodView):
    decorators = [login_required]

    def get(self):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        return render_template("forum_escrever.html")

    def post(self):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        titulo = request.form.get('titulo')
        conteudo = request.form.get('conteudo')
        
        novo_topico = Topico(
            titulo=titulo,
            conteudo=conteudo,
            usuario_id=current_user.id
        )
        
        db.session.add(novo_topico)
        db.session.commit()
        
        flash("Tópico criado com sucesso!")
        return redirect(url_for('forum'))

app.add_url_rule('/forum/topico/<int:id>', view_func=ForumTopico.as_view('forum_ler_topico'))
app.add_url_rule('/forum/escrever', view_func=ForumEscrever.as_view('forum_escrever'))


class EditaisAbertos(MethodView):
    decorators = [login_required]

    def get(self):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        editais_disponiveis = Edital.query.filter_by(encerrado=False).all()
        return render_template("editais_abertos.html", editais=editais_disponiveis)

app.add_url_rule('/editais-abertos', view_func=EditaisAbertos.as_view('editais_abertos'))


class DetalhesEdital(MethodView):
    decorators = [login_required]

    def get(self, id):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        edital_db = Edital.query.get_or_404(id)
        return render_template("detalhes_edital.html", edital=edital_db)

app.add_url_rule('/edital/<int:id>/detalhes', view_func=DetalhesEdital.as_view('detalhes_edital'))


class VisualizarEdital(MethodView):
    decorators = [login_required]

    def get(self, edital_id):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        edital = Edital.query.get_or_404(edital_id)
        
        ja_inscrito = current_user.esta_inscrito_no_edital(edital_id)
        docs_faltantes = current_user.documentos_faltantes_para_edital(edital)
        pode_inscrever = edital.esta_no_periodo_inscricao() and not ja_inscrito
        
        return render_template('visualizacao_edital.html', 
                               edital=edital, 
                               ja_inscrito=ja_inscrito, 
                               docs_faltantes=docs_faltantes, 
                               pode_inscrever=pode_inscrever)

app.add_url_rule('/edital/<int:edital_id>/visualizar', view_func=VisualizarEdital.as_view('visualizar_edital'))


class InscreverEdital(MethodView):
    decorators = [login_required]

    def _editais_conflitam(self, edital1, edital2):
        return (edital1.data_ini_programa <= edital2.data_fim_programa and
                edital1.data_fim_programa >= edital2.data_ini_programa)

    def get(self, id):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        edital = Edital.query.get_or_404(id)
        return render_template("inscricao_edital.html", edital=edital)

    def post(self, id):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        edital = Edital.query.get_or_404(id)

        if edital.inscricoes_encerradas():
            flash("O período de inscrições para esse edital está encerrado")
            return redirect(url_for('dashboard'))
        
        if edital.inscricoes_nao_iniciadas():
            flash("O período para inscrição desse edital ainda não começou")
            return redirect(url_for('dashboard'))
        
        if not edital.tem_vagas_disponiveis():
            flash("Não há mais vagas disponíveis para este edital")
            return redirect(url_for('dashboard'))
        
        if current_user.esta_inscrito_no_edital(edital.id):
            flash("Você já está inscrito neste edital!")
            return redirect(url_for('checklist'))

        inscricoes_existentes = Inscricao.query.filter(
            Inscricao.usuario_id == current_user.id,
            Inscricao.status.in_(['Em Análise', 'Aprovado', 'Ativa'])
        ).all()
        
        for insc in inscricoes_existentes:
            if self._editais_conflitam(edital, insc.edital):
                flash("Você já está inscrito em um edital com período de intercâmbio conflitante!")
                return redirect(url_for('editais_abertos'))

        cra = request.form.get('cra')
        carta = request.form.get('carta_motivacao')
        
        nova_inscricao = Inscricao(
            usuario_id=current_user.id,
            edital_id=edital.id,
            cra=float(cra),
            carta_motivacao=carta,
            status="Em Análise"
        )
        
        db.session.add(nova_inscricao)
        db.session.commit()
        
        flash("Inscrição realizada com sucesso!")
        return redirect(url_for('checklist'))

app.add_url_rule('/edital/<int:id>/inscrever', view_func=InscreverEdital.as_view('inscrever_edital'))


class CancelarInscricao(MethodView):
    decorators = [login_required]

    def post(self, edital_id):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        inscricao = Inscricao.query.filter_by(
            usuario_id=current_user.id, 
            edital_id=edital_id
        ).first_or_404()

        db.session.delete(inscricao)
        db.session.commit()
        
        flash("Inscrição cancelada com sucesso")
        return redirect(url_for('dashboard'))

app.add_url_rule('/edital/<int:edital_id>/cancelar_inscricao', view_func=CancelarInscricao.as_view('cancelar_inscricao'))


class Admin(MethodView):
    decorators = [login_required]

    def get(self):
        if not current_user.is_admin:
            flash("Acesso negado. Apenas administradores podem acessar esta área.")
            return redirect(url_for("dashboard"))
        return render_template('admin_dashboard.html')

app.add_url_rule('/admin', view_func=Admin.as_view('admin_dashboard'))


class CadastroPaises(MethodView):
    decorators = [login_required]

    def get(self):
        if not current_user.is_admin:
            flash("Apenas administradores podem realizar cadastros de países")
            return redirect(url_for("admin_dashboard"))
        return render_template("admin_cadastro_pais.html")

    def post(self):
        if not current_user.is_admin:
            flash("Apenas administradores podem realizar cadastros de países")
            return redirect(url_for("admin_dashboard"))
            
        nome = request.form['nome_pais'].strip().title()
        iso = request.form['sigla_pais'].strip().upper()
        desc = request.form['descricao'].strip()
        
        if Pais.buscar_por_nome(nome):
            flash("Esse país já está cadastrado")
            return redirect(url_for("admin_dashboard"))
            
        novo_pais = Pais(nome=nome, iso=iso, desc=desc)
        db.session.add(novo_pais)
        db.session.commit()
        
        flash("País cadastrado com sucesso!")
        return redirect(url_for("admin_dashboard"))

app.add_url_rule('/cadastro_paises', view_func=CadastroPaises.as_view('cadastro_paises'))


class EditarPaises(MethodView):
    decorators = [login_required]

    def get(self, id):
        if not current_user.is_admin:
            flash("Apenas administradores podem editar nomes de países")
            return redirect(url_for("admin_dashboard"))
            
        paises = Pais.buscar_por_id(id)
        if not paises:
            flash("País não encontrado")
            return redirect(url_for("admin_dashboard"))
            
        return render_template("admin_cadastro_pais.html", paises=paises)

    def post(self, id):
        if not current_user.is_admin:
            flash("Apenas administradores podem editar nomes de países")
            return redirect(url_for("admin_dashboard"))
            
        paises = Pais.buscar_por_id(id)
        if not paises:
            flash("País não encontrado")
            return redirect(url_for("admin_dashboard"))
            
        novo_nome = request.form["nome"].strip().title()
        nome_usado = Pais.buscar_por_nome(novo_nome)
        
        if nome_usado and nome_usado.id != paises.id:
            flash("Esse nome já pertence a um país cadastrado")
            return render_template("admin_cadastro_pais.html", paises=paises)
            
        paises.nome = novo_nome
        db.session.commit()
        
        flash("Alteração bem sucedida!")
        return redirect(url_for("admin_dashboard"))

app.add_url_rule('/editar_paises/<int:id>', view_func=EditarPaises.as_view('editar_paises'))


class ExcluirPaises(MethodView):
    decorators = [login_required]

    def post(self, id):
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

app.add_url_rule('/excluir_paises/<int:id>', view_func=ExcluirPaises.as_view('excluir_paises'))


class AdminCadastroUniversidade(MethodView):
    decorators = [login_required]

    def get(self):
        if not current_user.is_admin:
            flash("Acesso negado.")
            return redirect(url_for("dashboard"))
            
        paises = Pais.query.all()
        return render_template('admin_cadastro_universidade.html', paises=paises)

    def post(self):
        if not current_user.is_admin:
            flash("Acesso negado.")
            return redirect(url_for("dashboard"))

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

app.add_url_rule('/admin/universidade/novo', view_func=AdminCadastroUniversidade.as_view('admin_cadastro_universidade'))


class AdminCadastroDocumento(MethodView):
    decorators = [login_required]

    def get(self):
        if not current_user.is_admin:
            flash("Acesso negado.")
            return redirect(url_for("dashboard"))
        return render_template("admin_cadastro_documento.html")

    def post(self):
        if not current_user.is_admin:
            flash("Acesso negado.")
            return redirect(url_for("dashboard"))
            
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

app.add_url_rule('/admin/documento/novo', view_func=AdminCadastroDocumento.as_view('admin_cadastro_documento'))


class AdminListarEditais(MethodView):
    decorators = [login_required]

    def get(self):
        if not current_user.is_admin:
            flash("Acesso negado.")
            return redirect(url_for("dashboard"))
        editais_db = Edital.query.all()
        return render_template('admin_edital.html', editais=editais_db)

app.add_url_rule('/admin/editais', view_func=AdminListarEditais.as_view('admin_listar_editais'))


class AdminCadastroEdital(MethodView):
    decorators = [login_required]

    def get(self):
        if not current_user.is_admin:
            flash("Acesso negado!")
            return redirect(url_for('index'))

        universidades = Universidade.query.all()
        documentos = Documento.query.all()

        return render_template(
            'admin_cadastro_edital.html',
            universidades=universidades,
            documentos=documentos
        )

    def post(self):
        if not current_user.is_admin:
            flash("Acesso negado!")
            return redirect(url_for('index'))

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

        data_ini_edital = datetime.strptime(data_inicial, '%Y-%m-%d').date()
        data_fim_edital = datetime.strptime(data_limite, '%Y-%m-%d').date()
        data_ini_programa = datetime.strptime(data_inicial_intercambio, '%Y-%m-%d').date()
        data_fim_programa = datetime.strptime(data_limite_intercambio, '%Y-%m-%d').date()
        
        hoje = date.today()
        
        if data_ini_edital < hoje:
            flash("Erro: A data de início das inscrições não pode estar no passado!")
            return redirect(url_for('admin_cadastro_edital'))
        
        if data_fim_edital < data_ini_edital:
            flash("Erro: A data de término das inscrições não pode ser anterior ao início!")
            return redirect(url_for('admin_cadastro_edital'))
        
        if data_ini_programa < hoje:
            flash("Erro: A data de início do intercâmbio não pode estar no passado!")
            return redirect(url_for('admin_cadastro_edital'))
        
        if data_fim_programa < data_ini_programa:
            flash("Erro: A data de término do intercâmbio não pode ser anterior ao início!")
            return redirect(url_for('admin_cadastro_edital'))
        
        if data_ini_programa < data_fim_edital:
            flash("Erro: O intercâmbio não pode começar antes do fim das inscrições!")
            return redirect(url_for('admin_cadastro_edital'))

        novo_edital = Edital(
            titulo=titulo,
            universidade_id=universidade_id,  
            vagas=vagas,
            data_ini_edital=data_ini_edital,
            data_fim_edital=data_fim_edital,
            data_ini_programa=data_ini_programa,
            data_fim_programa=data_fim_programa
        )

        for doc_id in documentos_id:
            documento = Documento.query.get(doc_id)
            if documento:
                novo_edital.documentos_exigidos.append(documento)

        db.session.add(novo_edital)
        db.session.commit()
        flash("Edital cadastrado com sucesso!")
        return redirect(url_for('admin_listar_editais'))

app.add_url_rule('/admin/cadastro/edital', view_func=AdminCadastroEdital.as_view('admin_cadastro_edital'))


class EditarEdital(MethodView):
    decorators = [login_required]

    def get(self, id):
        if not current_user.is_admin:
            flash("Acesso negado.")
            return redirect(url_for("dashboard"))

        edital = Edital.query.get_or_404(id)
        universidades_db = Universidade.query.all()
        documentos_db = Documento.query.all()

        return render_template(
            'admin_editar_edital.html',
            edital=edital,
            universidades=universidades_db,
            documentos=documentos_db
        )

    def post(self, id):
        if not current_user.is_admin:
            flash("Acesso negado.")
            return redirect(url_for("dashboard"))

        edital = Edital.query.get_or_404(id)

        if edital.tem_candidatos_aprovados():
            flash("Erro: Não é possível editar um edital que já tem candidatos aprovados!")
            return redirect(url_for('admin_listar_editais'))

        edital.titulo = request.form.get('titulo', '').strip()
        edital.universidade_id = request.form.get('universidade_id')
        edital.vagas = int(request.form.get('vagas', 0))

        data_inicial_str = request.form.get('data_inicial')
        data_limite_str = request.form.get('data_limite')
        data_ini_inter_str = request.form.get('data_inicial_intercambio')
        data_lim_inter_str = request.form.get('data_limite_intercambio')

        edital.data_ini_edital = datetime.strptime(data_inicial_str, '%Y-%m-%d').date() if data_inicial_str else None
        edital.data_fim_edital = datetime.strptime(data_limite_str, '%Y-%m-%d').date() if data_limite_str else None
        edital.data_ini_programa = datetime.strptime(data_ini_inter_str, '%Y-%m-%d').date() if data_ini_inter_str else None
        edital.data_fim_programa = datetime.strptime(data_lim_inter_str, '%Y-%m-%d').date() if data_lim_inter_str else None

        edital.documentos_exigidos.clear()
        documentos_ids = request.form.getlist('documentos_id')

        if documentos_ids:
            docs = Documento.query.filter(Documento.id.in_(documentos_ids)).all()
            edital.documentos_exigidos.extend(docs)

        db.session.commit()
        flash("Edital atualizado com sucesso!")
        return redirect(url_for('admin_listar_editais'))

app.add_url_rule('/admin/edital/editar/<int:id>', view_func=EditarEdital.as_view('editar_edital'))


class ExcluirEdital(MethodView):
    decorators = [login_required]

    def post(self, id):
        if not current_user.is_admin:
            return redirect(url_for("dashboard"))
            
        edital = Edital.query.get(id)
        if edital:
            db.session.delete(edital)
            db.session.commit()
            flash("Edital removido permanentemente!")
            
        return redirect(url_for('admin_listar_editais'))

app.add_url_rule('/admin/edital/excluir/<int:id>', view_func=ExcluirEdital.as_view('excluir_edital'))


class AdminAvaliarInscricao(MethodView):
    decorators = [login_required]

    def get(self, id):
        if not current_user.is_admin:
            return redirect(url_for('dashboard'))

        inscricao = Inscricao.query.get_or_404(id)
        
        docs_exigidos_ids = [doc.id for doc in inscricao.edital.documentos_exigidos]
        documentos_aluno = DocumentoUsuario.query.filter(
            DocumentoUsuario.usuario_id == inscricao.usuario_id,
            DocumentoUsuario.documento_id.in_(docs_exigidos_ids)
        ).all()

        return render_template('admin_avaliar_inscricao.html', inscricao=inscricao, documentos=documentos_aluno)

    def post(self, id):
        if not current_user.is_admin:
            return redirect(url_for('dashboard'))

        inscricao = Inscricao.query.get_or_404(id)
        acao = request.form.get('acao')
        
        if acao == 'aprovar':
            if not inscricao.edital.tem_vagas_disponiveis():
                flash(f"Não é possível aprovar. O edital já atingiu o limite de {inscricao.edital.vagas} vagas!")
                return redirect(request.referrer)
            
            inscricao.status = 'Aprovado'
            flash(f"Candidatura de {inscricao.usuario.nome} APROVADA com sucesso!")
        elif acao == 'reprovar':
            inscricao.status = 'Reprovado'
            flash(f"Candidatura de {inscricao.usuario.nome} REPROVADA.")
            
        db.session.commit()
        return redirect(request.referrer or url_for('admin_listar_editais'))

app.add_url_rule('/admin/inscricao/<int:id>', view_func=AdminAvaliarInscricao.as_view('admin_avaliar_inscricao'))


class AdminAvaliarDocumento(MethodView):
    decorators = [login_required]
    
    def post(self, id):
        if not current_user.is_admin:
            return redirect(url_for('dashboard'))
        
        doc = DocumentoUsuario.query.get_or_404(id)
        acao = request.form.get('acao')
        
        if acao == 'aprovar':
            doc.status = 'Aprovado'
        elif acao == 'reprovar':
            doc.status = 'Reprovado'
        
        db.session.commit()
        flash("Documento avaliado!")
        return redirect(request.referrer)

app.add_url_rule('/admin/documento/<int:id>/avaliar', view_func=AdminAvaliarDocumento.as_view('admin_avaliar_documento'))


class AdminBaixarDocumento(MethodView):
    decorators = [login_required]

    def get(self, id):
        if not current_user.is_admin:
            return redirect(url_for('dashboard'))
            
        doc = DocumentoUsuario.query.get_or_404(id)
        
        if doc.caminho_arquivo and os.path.exists(doc.caminho_arquivo):
            caminho_absoluto = os.path.abspath(doc.caminho_arquivo)
            return send_file(caminho_absoluto, as_attachment=True)
        else:
            flash("Erro: O arquivo físico não foi encontrado na pasta do sistema! O aluno precisa reenviar o documento.")
            return redirect(request.referrer or url_for('admin_listar_editais'))

app.add_url_rule('/admin/baixar-documento/<int:id>', view_func=AdminBaixarDocumento.as_view('admin_baixar_documento'))


class ColegasViagem(MethodView):
    decorators = [login_required]

    def get(self):
        if current_user.is_admin:
            flash("Admins não podem acessar áreas de usuário.")
            return redirect(url_for('admin_dashboard'))
        
        minha_inscricao = Inscricao.query.filter_by(usuario_id=current_user.id, status='Aprovado').first()

        if not minha_inscricao:
            flash("Você precisa ter uma candidatura aprovada para acessar a Rede de Contatos!")
            return redirect(url_for('dashboard'))

        meu_pais_id = minha_inscricao.edital.universidade.pais_id
        nome_do_pais = minha_inscricao.edital.universidade.pais_origem.nome

        todas_aprovadas = Inscricao.query.filter(Inscricao.status == 'Aprovado', Inscricao.usuario_id != current_user.id).all()
        
        colegas = []
        for inscricao in todas_aprovadas:
            if inscricao.edital.universidade.pais_id == meu_pais_id:
                colegas.append(inscricao)

        return render_template("colegas_viagem.html", colegas=colegas, pais=nome_do_pais)

app.add_url_rule('/colegas', view_func=ColegasViagem.as_view('colegas_viagem'))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_database()
        print("Banco de dados inicializado com sucesso!")

    app.run(debug=True)
