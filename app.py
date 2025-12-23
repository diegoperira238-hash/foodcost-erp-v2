from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from functools import wraps
import os
import sys
import webbrowser
import logging
import secrets
import string
from datetime import datetime, timedelta
import time
import smtplib
from email.mime.text import MIMEText

# ==============================================================================
# CONFIGURAÇÃO DE LOGGING PROFISSIONAL
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURAÇÃO DE AMBIENTE E FLASK
# ==============================================================================
if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    base_path = os.path.dirname(sys.executable)
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    base_path = os.path.abspath(os.path.dirname(__file__))
    app = Flask(__name__)

# CONFIGURAÇÕES DE SEGURANÇA
app.secret_key = "foodcost_chave_fixa_para_manter_sessao_123" 
app.permanent_session_lifetime = timedelta(minutes=30)
app.config['SESSION_PERMANENT'] = True 
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_NAME'] = "fc_session_stable"
app.config['JSON_AS_ASCII'] = False

# ==============================================================================
# CONFIGURAÇÃO DO BANCO DE DADOS PRINCIPAL
# ==============================================================================
database_url = os.getenv("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    logger.info(f"Conexão de banco: PostgreSQL (Nuvem) com driver Psycopg2")
    
else:
    db_name = "database.db"
    db_path = os.path.join(base_path, db_name)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    logger.info(f"Conexão de banco: SQLite Local: {db_path}")

# --- DIAGNÓSTICO VISUAL NO TERMINAL ---
print("\n" + "="*80)
print(f" >>> SISTEMA INICIADO <<<")
print(f" BANCO ATIVO: {'PostgreSQL (Nuvem)' if database_url else f'SQLite Local'}")
print("="*80 + "\n")

db = SQLAlchemy(app)

# ==============================================================================
# TRAVA DE SEGURANÇA MESTRA (OPCIONAL)
# ==============================================================================
CHAVE_MESTRA = os.getenv("CHAVE_MESTRA", "")

def access_locked(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if CHAVE_MESTRA and CHAVE_MESTRA.strip() and not session.get('acesso_validado'):
            return render_template('portal_acesso.html')
        return f(*args, **kwargs)
    return decorated_function

# ==============================================================================
# MODELOS DE DADOS
# ==============================================================================
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='user')
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))
    loja = db.relationship('Loja')

class Loja(db.Model):
    __tablename__ = 'lojas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.now)
    chave_licenca = db.Column(db.String(100), unique=True, nullable=True)
    licenca_ativa = db.Column(db.Boolean, default=True)
    data_expiracao = db.Column(db.DateTime, nullable=True)
    max_maquinas = db.Column(db.Integer, default=1)

class Maquina(db.Model):
    __tablename__ = 'maquinas'
    id = db.Column(db.Integer, primary_key=True)
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))
    fingerprint = db.Column(db.String(255), unique=True)
    ativa = db.Column(db.Boolean, default=True)
    criada_em = db.Column(db.DateTime, default=datetime.now)
    expira_em = db.Column(db.DateTime, nullable=True)
    observacoes = db.Column(db.Text)
    data_cadastro = db.Column(db.DateTime, default=datetime.now)
    loja = db.relationship('Loja')

class LogAcesso(db.Model):
    __tablename__ = 'logs_acesso'
    id = db.Column(db.Integer, primary_key=True)
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fingerprint = db.Column(db.String(255))
    ip = db.Column(db.String(50))
    motivo = db.Column(db.String(100))
    data = db.Column(db.DateTime, default=datetime.now)
    usuario = db.relationship('Usuario')
    loja = db.relationship('Loja')

class HistoricoLicenca(db.Model):
    __tablename__ = 'historico_licencas'
    id = db.Column(db.Integer, primary_key=True)
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))
    chave_licenca = db.Column(db.String(100))
    acao = db.Column(db.String(50))  # 'GERADA', 'ATIVADA', 'RENOVADA', 'BLOQUEADA'
    ip = db.Column(db.String(50))
    fingerprint = db.Column(db.String(255))
    data = db.Column(db.DateTime, default=datetime.now)
    detalhes = db.Column(db.Text)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    loja = db.relationship('Loja')
    usuario = db.relationship('Usuario')

class Categoria(db.Model):
    __tablename__ = 'categorias'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))

class Unidade(db.Model):
    __tablename__ = 'unidades'
    id = db.Column(db.Integer, primary_key=True)
    sigla = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

class Insumo(db.Model):
    __tablename__ = 'insumos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id')) 
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'))
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'))
    preco_embalagem = db.Column(db.Float, nullable=False, default=0.0)
    tamanho_embalagem = db.Column(db.Float, nullable=False, default=1.0)
    fator_correcao = db.Column(db.Float, default=1.0)
    custo_unitario = db.Column(db.Float, default=0.0)
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))
    
    categoria = db.relationship('Categoria', backref='insumos')
    unidade = db.relationship('Unidade', backref='insumos')

class Base(db.Model):
    __tablename__ = 'bases'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id')) 
    rendimento_final = db.Column(db.Float, default=1.0)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    itens = db.relationship('BaseItem', backref='base', cascade='all, delete-orphan')
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))

    @property
    def custo_total_producao(self):
        return sum(((it.quantidade or 0) * (it.insumo.custo_unitario or 0)) for it in self.itens if it.insumo)

    @property
    def custo_por_unidade(self):
        if self.rendimento_final and self.rendimento_final > 0:
            return self.custo_total_producao / self.rendimento_final
        return 0.0

    @property
    def rendimento(self):
        return self.rendimento_final

    @property
    def custo_por_kg_litro(self):
        return self.custo_por_unidade

class BaseItem(db.Model):
    __tablename__ = 'base_itens'
    id = db.Column(db.Integer, primary_key=True)
    base_id = db.Column(db.Integer, db.ForeignKey('bases.id'))
    insumo_id = db.Column(db.Integer, db.ForeignKey('insumos.id'))
    quantidade = db.Column(db.Float, nullable=False)
    insumo = db.relationship('Insumo')
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))

class Ficha(db.Model):
    __tablename__ = 'fichas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id')) 
    porcoes = db.Column(db.Float, default=1.0)
    preco_venda = db.Column(db.Float, default=0.0)
    cmv_alvo = db.Column(db.Float, default=30.0)
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    itens = db.relationship('FichaItem', backref='ficha', cascade='all, delete-orphan')
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))

class FichaItem(db.Model):
    __tablename__ = 'ficha_itens'
    id = db.Column(db.Integer, primary_key=True)
    ficha_id = db.Column(db.Integer, db.ForeignKey('fichas.id'))
    tipo_item = db.Column(db.String(10)) 
    referencia_id = db.Column(db.Integer, nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))

# ==============================================================================
# FUNÇÕES AUXILIARES
# ==============================================================================
def dias_restantes(expira_em):
    if not expira_em:
        return "∞"
    hoje = datetime.now().date()
    if isinstance(expira_em, datetime):
        expira_em = expira_em.date()
    restante = (expira_em - hoje).days
    if restante < 0:
        return f"EXPIRADO ({abs(restante)} dias)"
    return restante

def status_licenca(loja):
    if not loja.licenca_ativa:
        return '<span class="badge bg-danger"><i class="fas fa-ban me-1"></i>Inativa</span>'
    
    if loja.data_expiracao and loja.data_expiracao < datetime.now():
        return f'<span class="badge bg-warning text-dark"><i class="fas fa-exclamation-triangle me-1"></i>Expirada ({dias_restantes(loja.data_expiracao)})</span>'
    
    return f'<span class="badge bg-success"><i class="fas fa-check-circle me-1"></i>Ativa ({dias_restantes(loja.data_expiracao)} dias)</span>'

def verificar_licenca_maquina(loja_id, fingerprint):
    loja = db.session.get(Loja, loja_id)
    if not loja or not loja.licenca_ativa:
        return False, "Licença da loja inativa"
    
    if loja.data_expiracao and loja.data_expiracao < datetime.now():
        return False, "Licença expirada"
    
    maquina = Maquina.query.filter_by(
        loja_id=loja_id,
        fingerprint=fingerprint
    ).first()
    
    if not maquina:
        return False, "Máquina não autorizada"
    
    if not maquina.ativa:
        return False, "Máquina bloqueada"
    
    total_maquinas = Maquina.query.filter_by(
        loja_id=loja_id,
        ativa=True
    ).count()
    
    if total_maquinas > loja.max_maquinas:
        return False, f"Limite de {loja.max_maquinas} máquina(s) excedido"
    
    return True, "Licença válida"

# ==============================================================================
# SISTEMA DE ALERTAS POR EMAIL
# ==============================================================================
def enviar_alerta_email(assunto, mensagem):
    """Envia alerta por email quando detectar acesso suspeito"""
    try:
        email_remetente = os.getenv("ALERT_EMAIL_FROM", "alerta@seusistema.com")
        email_destino = os.getenv("ALERT_EMAIL_TO", "seu_email@gmail.com")
        email_senha = os.getenv("ALERT_EMAIL_PASSWORD")
        
        if not email_senha:
            logger.warning("ALERTA: Sistema de email não configurado")
            return
        
        msg = MIMEText(mensagem)
        msg['Subject'] = f"[ALERTA FOODCOST] {assunto}"
        msg['From'] = email_remetente
        msg['To'] = email_destino
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(email_remetente, email_senha)
            server.send_message(msg)
        
        logger.info(f"✅ Alerta enviado por email: {assunto}")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao enviar email: {e}")
        return False

# ==============================================================================
# FILTROS DE FORMATAÇÃO JINJA2
# ==============================================================================
@app.template_filter('moeda')
def moeda_filter(v):
    try:
        return f"R$ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

@app.template_filter('peso')
def peso_filter(v):
    try:
        return f"{float(v or 0):,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "0,000"

@app.template_filter('percentual')
def percent_filter(v):
    try:
        return f"{float(v or 0):.2f}%"
    except:
        return "0.00%"

@app.template_filter('dias_restantes')
def dias_restantes_filter(expira_em):
    return dias_restantes(expira_em)

@app.template_filter('status_licenca')
def status_licenca_filter(loja):
    from app import status_licenca
    return status_licenca(loja)

# ==============================================================================
# DECORADORES DE SEGURANÇA
# ==============================================================================
# ==============================================================================
# DECORADORES DE SEGURANÇA - REVISADOS
# ==============================================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        usuario = db.session.get(Usuario, session.get('usuario_id'))
        if not usuario:
            flash("Sessão inválida!", "danger")
            return redirect('/login')
        
        # APENAS SUPER ADMIN OU ADMIN PODE ACESSAR
        if usuario.role != 'admin' and usuario.username != 'bpereira':
            flash("ACESSO NEGADO: Requer privilégios de Administrador.", "danger")
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # APENAS bpereira pode acessar
        if session.get('usuario_nome') != 'bpereira':
            flash("ACESSO NEGADO: Apenas o administrador mestre tem acesso.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def admin_config_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        """Apenas Super Admin (bpereira) pode acessar configurações sigilosas"""
        if session.get('usuario_nome') != 'bpereira':
            flash("ACESSO NEGADO: Apenas o super administrador pode acessar esta área.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==============================================================================
# MIDDLEWARE: VERIFICAÇÃO DE LOJA ATIVA COM ALERTAS
# ==============================================================================
@app.before_request
def verificar_loja_ativa():
    rotas_livres = {
        'login', 'logout', 'validar_chave', 'static', 
        'ativar_licenca', 'solicitar_fingerprint', 'portal_acesso'
    }
    
    if request.endpoint in rotas_livres:
        return

    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return redirect('/login')

    usuario = db.session.get(Usuario, usuario_id)
    if not usuario:
        session.clear()
        return redirect('/login')

    if usuario.username == 'bpereira':
        return

    if not usuario.loja_id:
        flash('Usuário sem loja vinculada.', 'danger')
        session.clear()
        return redirect('/login')

    loja = db.session.get(Loja, usuario.loja_id)
    if not loja or not loja.ativo:
        flash("Esta loja está bloqueada.", "danger")
        session.clear()
        return redirect('/login')

    if loja.licenca_ativa == False:
        mensagem = f"""
        🚨 TENTATIVA DE ACESSO A LOJA BLOQUEADA!
        
        📋 DETALHES:
        • Loja: {loja.nome} (ID: {loja.id})
        • Usuário: {usuario.username} (ID: {usuario.id})
        • IP: {request.remote_addr}
        • Fingerprint: {request.cookies.get('fp', 'Não detectado')}
        • Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        • User-Agent: {request.user_agent.string[:100]}
        """
        enviar_alerta_email("🚨 Loja Bloqueada - Tentativa de Acesso", mensagem)
        
        session.clear()
        return render_template('licenca_inativa.html', loja=loja), 403
    
    if loja.data_expiracao and loja.data_expiracao < datetime.now():
        mensagem = f"""
        ⚠️ TENTATIVA DE ACESSO COM LICENÇA EXPIRADA!
        
        📋 DETALHES:
        • Loja: {loja.nome}
        • Usuário: {usuario.username}
        • Licença expirou em: {loja.data_expiracao.strftime('%d/%m/%Y')}
        • Dias expirado: {(datetime.now().date() - loja.data_expiracao.date()).days} dias
        • IP: {request.remote_addr}
        • Data tentativa: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        """
        enviar_alerta_email("⚠️ Licença Expirada - Tentativa de Acesso", mensagem)
        
        session.clear()
        return render_template('licenca_expirada.html', loja=loja), 403

    fp = request.cookies.get('fp')
    if not fp:
        return render_template('solicitar_fingerprint.html'), 403

    licenca_valida, motivo = verificar_licenca_maquina(usuario.loja_id, fp)
    
    if not licenca_valida:
        mensagem = f"""
        🔴 TENTATIVA DE ACESSO NÃO AUTORIZADO!
        
        📋 DETALHES:
        • Motivo: {motivo}
        • Loja: {loja.nome}
        • Usuário: {usuario.username}
        • IP: {request.remote_addr}
        • Fingerprint: {fp}
        • Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        • User-Agent: {request.user_agent.string[:100]}
        """
        enviar_alerta_email("🔴 Acesso Não Autorizado", mensagem)
        
        log = LogAcesso(
            loja_id=usuario.loja_id,
            usuario_id=usuario.id,
            fingerprint=fp,
            ip=request.remote_addr,
            motivo=f'TENTATIVA_ACESSO_NAO_AUTORIZADO: {motivo}'
        )
        db.session.add(log)
        db.session.commit()
        
        return render_template('acesso_nao_autorizado.html', motivo=motivo, loja=loja), 403

    log = LogAcesso(
        loja_id=usuario.loja_id,
        usuario_id=usuario.id,
        fingerprint=fp,
        ip=request.remote_addr,
        motivo='ACESSO_AUTORIZADO'
    )
    db.session.add(log)
    try:
        db.session.commit()
    except:
        db.session.rollback()

# ==============================================================================
# CONTEXT PROCESSOR
# ==============================================================================
@app.context_processor
def inject_user_info():
    try:
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return {}

        usuario = db.session.get(Usuario, usuario_id)
        if not usuario:
            return {}

        loja_atual = None
        if usuario.loja_id:
            loja_atual = db.session.get(Loja, usuario.loja_id)

        return {
            'usuario_atual': usuario,
            'is_admin': usuario.role == 'admin' or usuario.username == 'bpereira',
            'is_super_admin': usuario.username == 'bpereira',
            'loja_atual': loja_atual,
            'agora': datetime.now()
        }
    except Exception as e:
        logger.error(f"Erro inject_user_info: {e}")
        return {}

# ==============================================================================
# MOTOR DE CÁLCULO AVANÇADO
# ==============================================================================
class EngineCalculo:
    @staticmethod
    def processar_ficha(ficha_id):
        ficha = db.session.get(Ficha, ficha_id)
        if not ficha:
            return None
        
        custo_total = 0.0
        detalhes_itens = []

        for item in ficha.itens:
            nome_item = "Desconhecido"
            custo_un = 0.0
            unidade = "-"
            
            if item.tipo_item == 'insumo':
                obj = db.session.get(Insumo, item.referencia_id)
                if obj:
                    nome_item = obj.nome
                    custo_un = obj.custo_unitario or 0
                    unidade = obj.unidade.sigla if obj.unidade else "un"
            else:
                obj = db.session.get(Base, item.referencia_id)
                if obj:
                    nome_item = f"[BASE] {obj.nome}"
                    custo_un = obj.custo_por_unidade
                    unidade = "Base"

            subtotal = (item.quantidade or 0) * (custo_un or 0)
            custo_total += subtotal
            detalhes_itens.append({
                'nome': nome_item,
                'qtd': item.quantidade,
                'un': unidade,
                'custo_un': custo_un,
                'subtotal': subtotal
            })

        custo_porcao = custo_total / ficha.porcoes if ficha.porcoes > 0 else 0
        lucro_bruto = ficha.preco_venda - custo_porcao
        margem = (lucro_bruto / ficha.preco_venda * 100) if ficha.preco_venda > 0 else 0
        cmv_real = (custo_porcao / ficha.preco_venda * 100) if ficha.preco_venda > 0 else 0
        p_sugerido = custo_porcao / (ficha.cmv_alvo / 100) if ficha.cmv_alvo > 0 else 0

        return {
            'itens': detalhes_itens,
            'custo_total': custo_total,
            'custo_porcao': custo_porcao,
            'lucro_bruto': lucro_bruto,
            'margem_contribuicao': margem,
            'cmv_real': cmv_real,
            'preco_sugerido': p_sugerido
        }

# ==============================================================================
# ROTAS PRINCIPAIS
# ==============================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Rota de login principal"""
    if 'usuario_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        usuario = Usuario.query.filter_by(username=username).first()
        
        print(f"🔍 LOGIN TENTATIVA: usuario='{username}', senha_digitada='{password}', usuario_no_BD='{usuario.username if usuario else None}', senha_no_BD='{usuario.password if usuario else None}'")
        
        if usuario and usuario.password == password:
            if not usuario.loja_id:
                loja = Loja.query.first()
                if not loja:
                    loja = Loja(nome="Loja Padrão", ativo=True, licenca_ativa=True)
                    db.session.add(loja)
                    db.session.commit()
                usuario.loja_id = loja.id
                db.session.commit()
                print(f"✅ Loja atribuída ao usuário: {loja.id}")
            
            session['usuario_id'] = usuario.id
            session['usuario_nome'] = usuario.username
            session['role'] = usuario.role
            session['loja_id'] = usuario.loja_id
            
            fingerprint = request.cookies.get('fp')
            if not fingerprint:
                import hashlib
                fp = hashlib.md5(f"{username}{datetime.now().timestamp()}".encode()).hexdigest()
                print(f"✅ Fingerprint gerado: {fp[:20]}...")
            
            flash(f"Bem-vindo, {usuario.username}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Usuário ou senha incorretos!", "danger")
    
    return render_template('login.html')

@app.route('/gerar-minha-licenca')
def gerar_minha_licenca():
    """Gera licença automática para admin"""
    import secrets
    import string
    
    loja = Loja.query.first()
    if not loja:
        loja = Loja(nome="Minha Loja", ativo=True)
        db.session.add(loja)
        db.session.commit()
    
    alphabet = string.ascii_letters + string.digits
    chave = ''.join(secrets.choice(alphabet) for _ in range(32))
    
    loja.chave_licenca = chave
    loja.licenca_ativa = True
    db.session.commit()
    
    return f'''
    <h1>✅ LICENÇA GERADA!</h1>
    <h3>Chave: {chave}</h3>
    <p>Loja: {loja.nome}</p>
    <p>Status: Ativa</p>
    <hr>
    <a href="/ativar_licenca" class="btn btn-success">ATIVAR LICENÇA AGORA</a>
    '''

@app.route('/quem-sou-eu')
@login_required
def quem_sou_eu():
    usuario = db.session.get(Usuario, session['usuario_id'])
    return f"""
    <h3>👤 INFORMAÇÕES DO USUÁRIO</h3>
    <p><strong>Username:</strong> {usuario.username}</p>
    <p><strong>Role no banco:</strong> {usuario.role}</p>
    <p><strong>Role na sessão:</strong> {session.get('role')}</p>
    <p><strong>ID da Loja:</strong> {usuario.loja_id}</p>
    <hr>
    <p><strong>É admin?</strong> {usuario.role == 'admin'}</p>
    <p><strong>É super admin (bpereira)?</strong> {usuario.username == 'bpereira'}</p>
    <hr>
    <a href="/" class="btn btn-primary">Voltar</a>
    <a href="/make-admin" class="btn btn-warning">Tornar-me Admin</a>
    """

@app.route('/make-admin')
@login_required
def make_admin():
    usuario = db.session.get(Usuario, session['usuario_id'])
    
    if usuario.role == 'admin':
        return "Você já é administrador!"
    
    usuario.role = 'admin'
    session['role'] = 'admin'
    db.session.commit()
    
    return f"""
    <h3>✅ AGORA VOCÊ É ADMINISTRADOR!</h3>
    <p>Usuário: <strong>{usuario.username}</strong></p>
    <p>Novo role: <strong>{usuario.role}</strong></p>
    <hr>
    <a href="/config/admin" class="btn btn-success">
        <i class="fas fa-cog"></i> ACESSAR PAINEL ADMIN
    </a>
    <a href="/" class="btn btn-primary">Voltar ao Início</a>
    """

@app.route('/criar-admin-fixo')
def criar_admin_fixo():
    """ROTA TEMPORÁRIA - Criar admin fixo"""
    try:
        import sqlite3
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO usuarios 
            (username, password, role, data_criacao) 
            VALUES (?, ?, ?, ?)
        ''', ('admin', 'admin123', 'admin', '2024-01-01 00:00:00'))
        
        conn.commit()
        conn.close()
        
        return '''
        <h1>✅ ADMIN CRIADO!</h1>
        <h3>Usuário: admin</h3>
        <h3>Senha: admin123</h3>
        <a href="/login">FAZER LOGIN AGORA</a>
        '''
    except Exception as e:
        return f'Erro: {str(e)}'

@app.route('/validar-chave', methods=['POST'])
def validar_chave():
    chave_digitada = request.form.get('chave_secreta')
    if chave_digitada == CHAVE_MESTRA:
        session['acesso_validado'] = True
        return redirect(url_for('login'))
    flash("Chave mestra incorreta!", "danger")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    try:
        usuario = db.session.get(Usuario, session['usuario_id'])
        
        if usuario.username == 'bpereira':
            fichas = Ficha.query.order_by(Ficha.nome).all()
            total_fichas = Ficha.query.count()
            total_insumos = Insumo.query.count()
            total_bases = Base.query.count()
            
            fichas_com_cmv_alto = 0
            fichas_lucrativas = 0
            custo_total_sistema = 0
            
            for ficha in Ficha.query.all():
                metricas = EngineCalculo.processar_ficha(ficha.id)
                if metricas:
                    custo_total_sistema += metricas['custo_total']
                    if metricas['cmv_real'] > ficha.cmv_alvo:
                        fichas_com_cmv_alto += 1
                    if metricas['lucro_bruto'] > 0:
                        fichas_lucrativas += 1
            
        else:
            fichas = Ficha.query.filter_by(user_id=usuario.id).order_by(Ficha.nome).all()
            total_fichas = Ficha.query.filter_by(user_id=usuario.id).count()
            total_insumos = Insumo.query.filter_by(user_id=usuario.id).count()
            total_bases = Base.query.filter_by(user_id=usuario.id).count()
            
            fichas_com_cmv_alto = 0
            fichas_lucrativas = 0
            custo_total_sistema = 0
            
            for ficha in fichas:
                metricas = EngineCalculo.processar_ficha(ficha.id)
                if metricas:
                    custo_total_sistema += metricas['custo_total']
                    if metricas['cmv_real'] > ficha.cmv_alvo:
                        fichas_com_cmv_alto += 1
                    if metricas['lucro_bruto'] > 0:
                        fichas_lucrativas += 1
        
        lista_final = []
        for f in fichas:
            res = EngineCalculo.processar_ficha(f.id)
            lista_final.append({'ficha': f, 'metricas': res})
        
        info_licenca = {}
        if usuario.loja_id:
            loja = db.session.get(Loja, usuario.loja_id)
            if loja:
                info_licenca = {
                    'nome_loja': loja.nome,
                    'status': 'Ativa' if loja.licenca_ativa else 'Inativa',
                    'expira_em': loja.data_expiracao.strftime('%d/%m/%Y') if loja.data_expiracao else 'Nunca',
                    'dias_restantes': dias_restantes(loja.data_expiracao)
                }
        
        stats = {
            'total_fichas': total_fichas,
            'total_insumos': total_insumos,
            'total_bases': total_bases,
            'fichas_com_cmv_alto': fichas_com_cmv_alto,
            'fichas_lucrativas': fichas_lucrativas,
            'custo_total_sistema': custo_total_sistema,
            'media_cmv': (fichas_com_cmv_alto / total_fichas * 100) if total_fichas > 0 else 0,
            'percentual_lucrativas': (fichas_lucrativas / total_fichas * 100) if total_fichas > 0 else 0
        }
        
        return render_template('index.html', 
                             dados=lista_final, 
                             info_licenca=info_licenca,
                             stats=stats)
    except Exception as e:
        logger.error(f"Erro no Index: {e}")
        return f"Erro Crítico: {e}", 500

# ==============================================================================
# ROTAS PARA SUPER ADMIN (APENAS bpereira)
# ==============================================================================
@app.route('/admin/master')
@login_required
@super_admin_required
def admin_master():
    lojas = Loja.query.order_by(Loja.nome).all()
    maquinas = Maquina.query.order_by(Maquina.criada_em.desc()).all()
    usuarios = Usuario.query.order_by(Usuario.username).all()
    logs = LogAcesso.query.order_by(LogAcesso.data.desc()).limit(100).all()
    
    licencas_info = []
    for loja in lojas:
        maquinas_loja = [m for m in maquinas if m.loja_id == loja.id]
        usuarios_loja = [u for u in usuarios if u.loja_id == loja.id]
        
        licencas_info.append({
            'loja': loja,
            'maquinas': maquinas_loja,
            'total_maquinas': len(maquinas_loja),
            'maquinas_ativas': sum(1 for m in maquinas_loja if m.ativa),
            'usuarios': len(usuarios_loja),
            'dias_restantes': dias_restantes(loja.data_expiracao),
            'status': 'Ativa' if loja.licenca_ativa else 'Inativa'
        })
    
    stats = {
        'total_lojas': len(lojas),
        'lojas_ativas': sum(1 for l in lojas if l.ativo),
        'lojas_com_licenca': sum(1 for l in lojas if l.chave_licenca),
        'licencas_ativas': sum(1 for l in lojas if l.licenca_ativa),
        'licencas_expiradas': sum(1 for l in lojas if l.data_expiracao and l.data_expiracao < datetime.now()),
        'total_maquinas': len(maquinas),
        'maquinas_ativas': sum(1 for m in maquinas if m.ativa),
        'total_usuarios': len(usuarios),
        'usuarios_admin': sum(1 for u in usuarios if u.role == 'admin'),
        'logs_recentes': len(logs)
    }
    
    return render_template('admin_master.html',
                         licencas_info=licencas_info,
                         maquinas=maquinas,
                         usuarios=usuarios,
                         logs=logs,
                         stats=stats,
                         agora=datetime.now())

@app.route('/admin/gerar_licenca', methods=['POST'])
@login_required
@super_admin_required
def admin_gerar_licenca():
    loja_id = request.form.get('loja_id')
    dias_validade = int(request.form.get('dias_validade', 365))
    max_maquinas = int(request.form.get('max_maquinas', 1))
    
    loja = db.session.get(Loja, loja_id)
    if loja:
        alphabet = string.ascii_letters + string.digits
        chave = ''.join(secrets.choice(alphabet) for _ in range(32))
        
        loja.chave_licenca = chave
        loja.licenca_ativa = True
        loja.data_expiracao = datetime.now() + timedelta(days=dias_validade)
        loja.max_maquinas = max_maquinas
        
        historico = HistoricoLicenca(
            loja_id=loja.id,
            chave_licenca=chave,
            acao='GERADA',
            ip=request.remote_addr,
            fingerprint='SISTEMA',
            usuario_id=session.get('usuario_id'),
            detalhes=f'Licença gerada por {session.get("usuario_nome")}. Validade: {dias_validade} dias, Máx máquinas: {max_maquinas}'
        )
        db.session.add(historico)
        
        db.session.commit()
        flash(f"Licença gerada para {loja.nome}: {chave}", "success")
    
    return redirect(url_for('admin_master'))

@app.route('/admin/toggle_licenca/<int:loja_id>')
@login_required
@super_admin_required
def admin_toggle_licenca(loja_id):
    loja = db.session.get(Loja, loja_id)
    if loja:
        novo_status = not loja.licenca_ativa
        loja.licenca_ativa = novo_status
        
        historico = HistoricoLicenca(
            loja_id=loja.id,
            chave_licenca=loja.chave_licenca,
            acao='BLOQUEADA' if not novo_status else 'DESBLOQUEADA',
            ip=request.remote_addr,
            fingerprint='SISTEMA',
            usuario_id=session.get('usuario_id'),
            detalhes=f'Licença {"bloqueada" if not novo_status else "desbloqueada"} por {session.get("usuario_nome")}'
        )
        db.session.add(historico)
        
        db.session.commit()
        flash(f"Licença {'ativada' if loja.licenca_ativa else 'desativada'} para {loja.nome}", "info")
    
    return redirect(url_for('admin_master'))

@app.route('/admin/extender_licenca/<int:loja_id>', methods=['POST'])
@login_required
@super_admin_required
def admin_extender_licenca(loja_id):
    dias_adicionais = int(request.form.get('dias', 30))
    
    loja = db.session.get(Loja, loja_id)
    if loja:
        if loja.data_expiracao and loja.data_expiracao > datetime.now():
            loja.data_expiracao = loja.data_expiracao + timedelta(days=dias_adicionais)
        else:
            loja.data_expiracao = datetime.now() + timedelta(days=dias_adicionais)
        
        historico = HistoricoLicenca(
            loja_id=loja.id,
            chave_licenca=loja.chave_licenca,
            acao='RENOVADA',
            ip=request.remote_addr,
            fingerprint='SISTEMA',
            usuario_id=session.get('usuario_id'),
            detalhes=f'Licença estendida em {dias_adicionais} dias por {session.get("usuario_nome")}. Nova data: {loja.data_expiracao.strftime("%d/%m/%Y")}'
        )
        db.session.add(historico)
        
        db.session.commit()
        flash(f"Licença estendida em {dias_adicionais} dias para {loja.nome}", "success")
    
    return redirect(url_for('admin_master'))

def verificar_limite_lojas():
    """Verifica se atingiu o limite de 10 lojas"""
    total_lojas = Loja.query.count()
    if total_lojas >= 10:
        return {
            'atingido': True,
            'total': total_lojas,
            'limite': 10,
            'vagas': 0,
            'mensagem': f'❌ LIMITE ATINGIDO: {total_lojas}/10 lojas'
        }
    else:
        return {
            'atingido': False,
            'total': total_lojas,
            'limite': 10,
            'vagas': 10 - total_lojas,
            'mensagem': f'✅ Vagas disponíveis: {10 - total_lojas}'
        }


# ==============================================================================
# ROTAS PARA ADMIN
# ==============================================================================
@app.route('/config/admin', methods=['GET', 'POST'])
@login_required
@admin_config_required
def config_admin():
    """Painel admin SIGILOSO - APENAS bpereira - LIMITE 10 LOJAS"""
    usuario = db.session.get(Usuario, session['usuario_id'])
    
    if request.method == 'POST':
        tipo = request.form.get('tipo_acao')
        
        if tipo == 'add_loja' and usuario.username == 'bpereira':
            nome = request.form.get('nome_loja', '').strip()
            
            if nome:
                # 🔒 VERIFICAÇÃO DE LIMITE - 10 LOJAS MÁXIMO
                total_lojas = Loja.query.count()
                
                if total_lojas >= 10:
                    flash(f"❌ LIMITE ATINGIDO! Já existem {total_lojas} lojas cadastradas.", "danger")
                    # Enviar alerta de tentativa de criar além do limite
                    mensagem = f"""
                    🚨 TENTATIVA DE CRIAR LOJA ALÉM DO LIMITE!
                    
                    📋 DETALHES:
                    • Sistema atingiu o limite de 10 lojas
                    • Total atual: {total_lojas}/10
                    • Tentativa de criar: {nome}
                    • Usuário: {usuario.username}
                    • Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
                    • IP: {request.remote_addr}
                    
                    ⚠️ BLOQUEADO AUTOMATICAMENTE
                    """
                    enviar_alerta_email("🚨 Limite de Lojas Atingido", mensagem)
                    
                    return redirect(url_for('config_admin'))
                
                # Ainda há vaga, pode criar
                import secrets, string
                chave = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
                
                nova_loja = Loja(
                    nome=nome,
                    ativo=True,
                    licenca_ativa=True,
                    chave_licenca=chave,
                    data_expiracao=datetime.now() + timedelta(days=365),
                    max_maquinas=3  # Limite padrão de máquinas por loja
                )
                db.session.add(nova_loja)
                db.session.commit()
                
                # Registrar no histórico
                historico = HistoricoLicenca(
                    loja_id=nova_loja.id,
                    chave_licenca=chave,
                    acao='GERADA',
                    ip=request.remote_addr,
                    fingerprint='SISTEMA',
                    usuario_id=usuario.id,
                    detalhes=f'Nova loja criada: {nome}. Total: {total_lojas + 1}/10'
                )
                db.session.add(historico)
                
                # Enviar alerta de nova loja criada
                mensagem = f"""
                ✅ NOVA LOJA CRIADA (DENTRO DO LIMITE)
                
                📋 DETALHES:
                • Loja: {nome}
                • Chave: {chave}
                • Status: Ativa
                • Expira em: {(datetime.now() + timedelta(days=365)).strftime('%d/%m/%Y')}
                • Criada por: {usuario.username}
                • Total lojas agora: {total_lojas + 1}/10
                • Data criação: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
                
                📊 ESTATÍSTICAS:
                • Lojas ativas: {total_lojas + 1}
                • Vagas restantes: {10 - (total_lojas + 1)}
                """
                enviar_alerta_email("✅ Nova Loja Criada", mensagem)
                
                flash(f"✅ Loja '{nome}' criada com sucesso! Total: {total_lojas + 1}/10", "success")
        
        elif tipo == 'toggle_loja' and usuario.username == 'bpereira':
            loja_id = request.form.get('loja_id')
            loja = db.session.get(Loja, loja_id)
            if loja:
                loja.ativo = not loja.ativo
                db.session.commit()
                flash(f"Loja {'ativada' if loja.ativo else 'desativada'}!", "info")
        
        elif tipo == 'toggle_licenca' and usuario.username == 'bpereira':
            loja_id = request.form.get('loja_id')
            loja = db.session.get(Loja, loja_id)
            if loja:
                loja.licenca_ativa = not loja.licenca_ativa
                db.session.commit()
                flash(f"Licença {'ativada' if loja.licenca_ativa else 'desativada'}!", "info")
        
        elif tipo == 'add_user':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            loja_id = request.form.get('loja_id')
            role = request.form.get('role', 'user')
            
            if username and password:
                novo = Usuario(
                    username=username,
                    password=password,
                    role=role,
                    loja_id=loja_id if loja_id else usuario.loja_id
                )
                db.session.add(novo)
                db.session.commit()
                flash(f"Usuário {username} criado!", "success")
        
        elif tipo == 'toggle_role':
            user_id = request.form.get('user_id')
            user = db.session.get(Usuario, user_id)
            if user:
                user.role = 'admin' if user.role == 'user' else 'user'
                db.session.commit()
                flash(f"Usuário agora é {user.role}!", "info")
        
        elif tipo == 'reset_password':
            user_id = request.form.get('user_id')
            nova_senha = request.form.get('nova_senha')
            confirmar = request.form.get('confirmar_senha')
            
            if nova_senha == confirmar:
                user = db.session.get(Usuario, user_id)
                if user:
                    user.password = nova_senha
                    db.session.commit()
                    flash("Senha alterada!", "success")
            else:
                flash("Senhas não coincidem!", "danger")
        
        elif tipo == 'gerar_nova_chave' and usuario.username == 'bpereira':
            loja_id = request.form.get('loja_id')
            loja = db.session.get(Loja, loja_id)
            if loja:
                import secrets, string
                nova_chave = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
                
                loja.chave_licenca = nova_chave
                loja.licenca_ativa = True
                loja.data_expiracao = datetime.now() + timedelta(days=365)
                db.session.commit()
                flash(f"Nova chave gerada para {loja.nome}!", "success")
        
        return redirect(url_for('config_admin'))
    
    # 🔥🔥🔥 PARTE PARA REQUISIÇÕES GET (ESTAVA FALTANDO) 🔥🔥🔥
    # Dados para o template
    if usuario.username == 'bpereira':
        lojas = Loja.query.all()
        usuarios = Usuario.query.all()
    else:
        lojas = Loja.query.filter_by(id=usuario.loja_id).all()
        usuarios = Usuario.query.filter_by(loja_id=usuario.loja_id).all()
    
    # 🔥🔥🔥 ESTE RETURN É ESSENCIAL! 🔥🔥🔥
    return render_template('config_admin.html',
                         lojas=lojas,
                         usuarios=usuarios,
                         agora=datetime.now(),
                         is_super_admin=(usuario.username == 'bpereira'))

@app.route('/config/basico', methods=['GET', 'POST'])
@login_required
@admin_required  # ← QUALQUER ADMIN pode acessar
def config_basico():
    """Painel básico de configuração para admins normais"""
    usuario_id = session['usuario_id']
    usuario = db.session.get(Usuario, usuario_id)
    
    if request.method == 'POST':
        tipo_acao = request.form.get('tipo_acao')
        
        if tipo_acao == 'add_cat':
            nome = request.form.get('nome_cat', '').upper().strip()
            if nome and not Categoria.query.filter_by(nome=nome, user_id=usuario_id).first():
                nova_cat = Categoria(
                    nome=nome, 
                    user_id=usuario_id,
                    loja_id=usuario.loja_id
                )
                db.session.add(nova_cat)
                db.session.commit()
                flash("Categoria criada com sucesso!", "success")
                
        elif tipo_acao == 'add_uni':
            sigla = request.form.get('sigla_uni', '').upper().strip()
            if sigla and not Unidade.query.filter_by(sigla=sigla, user_id=usuario_id).first():
                nova_uni = Unidade(sigla=sigla, user_id=usuario_id)
                db.session.add(nova_uni)
                db.session.commit()
                flash("Unidade criada com sucesso!", "success")
        
        return redirect(url_for('config_basico'))
    
    categorias = Categoria.query.filter_by(user_id=usuario_id).order_by(Categoria.nome).all()
    unidades = Unidade.query.filter_by(user_id=usuario_id).order_by(Unidade.sigla).all()
    
    return render_template('config_basico.html', 
                         categorias=categorias, 
                         unidades=unidades,
                         usuario=usuario)



@app.route('/admin/historico-chaves')
@login_required
@admin_required
def historico_chaves():
    """Histórico simples de licenças"""
    historico = HistoricoLicenca.query.order_by(HistoricoLicenca.data.desc()).limit(50).all()
    return render_template('historico_chaves_simple.html', historico=historico)

@app.route('/admin/loja/<int:id>')
@login_required
@admin_required
def admin_detalhes_loja(id):
    loja = db.session.get(Loja, id)
    if not loja:
        flash("Loja não encontrada!", "danger")
        return redirect(url_for('config_admin'))
    
    usuario = db.session.get(Usuario, session['usuario_id'])
    if usuario.username != 'bpereira' and loja.id != usuario.loja_id:
        flash("Acesso negado!", "danger")
        return redirect(url_for('config_admin'))
    
    maquinas = Maquina.query.filter_by(loja_id=id).all()
    usuarios = Usuario.query.filter_by(loja_id=id).all()
    logs = LogAcesso.query.filter_by(loja_id=id).order_by(LogAcesso.data.desc()).limit(50).all()
    historico = HistoricoLicenca.query.filter_by(loja_id=id).order_by(HistoricoLicenca.data.desc()).all()
    
    return render_template('admin_detalhes_loja.html',
                         loja=loja,
                         maquinas=maquinas,
                         usuarios=usuarios,
                         logs=logs,
                         historico=historico)

@app.route('/admin/maquina/<int:id>/renovar')
@login_required
@admin_required
def renovar_maquina(id):
    maquina = db.session.get(Maquina, id)
    if maquina:
        maquina.expira_em = datetime.now() + timedelta(days=365)
        db.session.commit()
        flash(f"Máquina renovada por 365 dias!", "success")
    
    return redirect(url_for('config_admin'))

@app.route('/admin/logs/completo')
@login_required
@admin_required
def admin_logs_completo():
    usuario = db.session.get(Usuario, session['usuario_id'])
    
    if usuario.username == 'bpereira':
        logs = LogAcesso.query.order_by(LogAcesso.data.desc()).paginate(per_page=100)
    else:
        logs = LogAcesso.query.filter_by(loja_id=usuario.loja_id).order_by(LogAcesso.data.desc()).paginate(per_page=100)
    
    return render_template('admin_logs.html', logs=logs)

@app.route('/admin/maquinas/exportar')
@login_required
@admin_required
def exportar_maquinas():
    import csv
    import io
    
    usuario = db.session.get(Usuario, session['usuario_id'])
    
    if usuario.username == 'bpereira':
        maquinas = Maquina.query.all()
    else:
        maquinas = Maquina.query.filter_by(loja_id=usuario.loja_id).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['ID', 'Loja', 'Fingerprint', 'Status', 'Criada em', 'Expira em'])
    
    for m in maquinas:
        writer.writerow([
            m.id,
            m.loja.nome if m.loja else '',
            m.fingerprint,
            'ATIVA' if m.ativa else 'INATIVA',
            m.criada_em.strftime('%d/%m/%Y %H:%M:%S'),
            m.expira_em.strftime('%d/%m/%Y') if m.expira_em else ''
        ])
    
    output.seek(0)
    
    return output.getvalue(), 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename=maquinas.csv'
    }

# ==============================================================================
# ROTAS DE MÁQUINAS (ÚNICAS - CORRIGIDAS)
# ==============================================================================
@app.route('/maquinas')
@login_required
@admin_required
def listar_maquinas():
    """Lista todas as máquinas"""
    usuario = db.session.get(Usuario, session['usuario_id'])
    
    if usuario.username == 'bpereira':
        maquinas = Maquina.query.all()
    else:
        maquinas = Maquina.query.filter_by(loja_id=usuario.loja_id).all()
    
    return render_template('maquinas_lista.html', 
                         maquinas=maquinas,
                         lojas=Loja.query.all())

@app.route('/maquina/nova', methods=['GET', 'POST'])
@login_required
@admin_required
def nova_maquina():
    """Adicionar nova máquina"""
    if request.method == 'POST':
        fingerprint = request.form.get('fingerprint', '').strip()
        loja_id = request.form.get('loja_id')
        observacoes = request.form.get('observacoes', '')
        
        if fingerprint:
            nova = Maquina(
                fingerprint=fingerprint,
                loja_id=loja_id,
                ativa=True,
                observacoes=observacoes,
                data_cadastro=datetime.now()
            )
            db.session.add(nova)
            db.session.commit()
            flash('Máquina cadastrada com sucesso!', 'success')
            return redirect('/maquinas')
    
    return render_template('maquina_nova.html',
                         lojas=Loja.query.filter_by(ativo=True).all())

@app.route('/toggle_maquina/<int:id>')
@login_required
@admin_required
def toggle_maquina(id):
    """Ativar/desativar máquina"""
    maquina = db.session.get(Maquina, id)
    if maquina:
        maquina.ativa = not maquina.ativa
        db.session.commit()
        flash(f'Máquina {"ativada" if maquina.ativa else "desativada"}!', 'info')
    
    return redirect(request.referrer or '/maquinas')

@app.route('/excluir/maquina/<int:id>')
@login_required
@admin_required
def excluir_maquina(id):
    """Excluir máquina"""
    maquina = db.session.get(Maquina, id)
    if maquina:
        db.session.delete(maquina)
        db.session.commit()
        flash('Máquina excluída!', 'success')
    
    return redirect('/maquinas')

# ==============================================================================
# ROTA EXCLUIR USUÁRIO
# ==============================================================================
@app.route('/excluir/usuario/<int:id>')
@login_required
@admin_required
def excluir_usuario(id):
    """Excluir usuário (apenas super admin)"""
    usuario = db.session.get(Usuario, session['usuario_id'])
    if usuario.username != 'bpereira':
        flash('Apenas Super Admin pode excluir usuários!', 'danger')
        return redirect('/config/admin')
    
    user = db.session.get(Usuario, id)
    if user and user.id != usuario.id:
        db.session.delete(user)
        db.session.commit()
        flash(f'Usuário {user.username} excluído!', 'success')
    
    return redirect('/config/admin')

# ==============================================================================
# ROTAS PARA USUÁRIOS NORMAIS
# ==============================================================================
@app.route('/config', methods=['GET', 'POST'])
@login_required
def config():
    usuario_id = session['usuario_id']
    usuario = db.session.get(Usuario, usuario_id)
    
    if request.method == 'POST':
        tipo_acao = request.form.get('tipo_acao')
        
        if tipo_acao == 'add_cat':
            nome = request.form.get('nome_cat', '').upper().strip()
            if nome and not Categoria.query.filter_by(nome=nome, user_id=usuario_id).first():
                nova_cat = Categoria(
                    nome=nome, 
                    user_id=usuario_id,
                    loja_id=usuario.loja_id
                )
                db.session.add(nova_cat)
                db.session.commit()
                flash("Categoria criada com sucesso!", "success")
                
        elif tipo_acao == 'add_uni':
            sigla = request.form.get('sigla_uni', '').upper().strip()
            if sigla and not Unidade.query.filter_by(sigla=sigla, user_id=usuario_id).first():
                nova_uni = Unidade(sigla=sigla, user_id=usuario_id)
                db.session.add(nova_uni)
                db.session.commit()
                flash("Unidade criada com sucesso!", "success")
        
        return redirect(url_for('config'))
    
    categorias = Categoria.query.filter_by(user_id=usuario_id).order_by(Categoria.nome).all()
    unidades = Unidade.query.filter_by(user_id=usuario_id).order_by(Unidade.sigla).all()
    
    return render_template('config.html', 
                         categorias=categorias, 
                         unidades=unidades)

# ==============================================================================
# ROTAS DE INSUMOS
# ==============================================================================
@app.route('/insumos', methods=['GET', 'POST'])
@login_required
def insumos():
    uid = session['usuario_id']
    usuario = db.session.get(Usuario, uid)
    
    if request.method == 'POST':
        try:
            nome = request.form.get('nome').upper().strip()
            p_emb = float(request.form.get('preco').replace(',', '.'))
            t_emb = float(request.form.get('tamanho').replace(',', '.'))
            fc = float(request.form.get('fc').replace(',', '.'))
            
            novo_insumo = Insumo(
                nome=nome,
                user_id=uid,
                categoria_id=request.form.get('categoria_id'),
                unidade_id=request.form.get('unidade_id'),
                preco_embalagem=p_emb,
                tamanho_embalagem=t_emb,
                fator_correcao=fc,
                custo_unitario=(p_emb / t_emb) * fc,
                loja_id=session.get('loja_id')
            )
            db.session.add(novo_insumo)
            db.session.commit()
            flash(f"Insumo {nome} cadastrado!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao cadastrar: {e}", "danger")
    
    if usuario.username == 'bpereira' or usuario.role == 'admin':
        insumos_lista = Insumo.query.filter_by(loja_id=usuario.loja_id).all()
    else:
        insumos_lista = Insumo.query.filter_by(user_id=uid).all()
    
    cats = Categoria.query.filter_by(user_id=uid).all()
    unis = Unidade.query.filter_by(user_id=uid).all()
        
    return render_template('insumos.html', lista=insumos_lista, categorias=cats, unidades=unis)

@app.route('/insumos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_insumo(id):
    ins = db.session.get(Insumo, id)
    uid = session['usuario_id']
    usuario = db.session.get(Usuario, uid)
    
    if not ins:
        flash("Insumo não encontrado.", "danger")
        return redirect(url_for('insumos'))
    
    if usuario.username != 'bpereira' and ins.user_id != uid:
        flash("Acesso negado.", "danger")
        return redirect(url_for('insumos'))

    if request.method == 'POST':
        try:
            ins.nome = request.form.get('nome').upper().strip()
            ins.preco_embalagem = float(request.form.get('preco').replace(',', '.'))
            ins.tamanho_embalagem = float(request.form.get('tamanho').replace(',', '.'))
            ins.fator_correcao = float(request.form.get('fc').replace(',', '.'))
            ins.custo_unitario = (ins.preco_embalagem / ins.tamanho_embalagem) * ins.fator_correcao
            ins.categoria_id = request.form.get('categoria_id')
            ins.unidade_id = request.form.get('unidade_id')
            db.session.commit()
            flash("Insumo atualizado!", "success")
            return redirect(url_for('insumos'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro na edição: {e}", "danger")
    
    return render_template('insumos_form.html', i=ins, 
                           categorias=Categoria.query.filter_by(user_id=uid).all(), 
                           unidades=Unidade.query.filter_by(user_id=uid).all())

# ==============================================================================
# ROTAS DE BASES
# ==============================================================================
@app.route('/bases', methods=['GET', 'POST'])
@login_required
def bases():
    if request.method == 'POST':
        return nova_base()
    
    uid = session['usuario_id']
    usuario = db.session.get(Usuario, uid)
    
    if usuario.username == 'bpereira' or usuario.role == 'admin':
        lista = Base.query.filter_by(loja_id=usuario.loja_id).all()
    else:
        lista = Base.query.filter_by(user_id=uid).all()
    
    return render_template('bases.html', lista=lista)

@app.route('/bases/nova', methods=['GET', 'POST'])
@login_required
def nova_base():
    uid = session['usuario_id']
    if request.method == 'POST':
        try:
            nome_base = request.form.get('nome')
            if not nome_base:
                flash("Nome da base é obrigatório!", "warning")
                return redirect(url_for('bases'))

            rend_val = float(request.form.get('rendimento', '1').replace(',', '.') or 1)
            
            b = Base(
                nome=nome_base.upper(),
                user_id=uid,
                rendimento_final=rend_val,
                loja_id=session.get('loja_id')
            )
            db.session.add(b)
            db.session.flush()
            
            ids = request.form.getlist('insumo_id[]')
            qtds = request.form.getlist('quantidade[]')
            
            for idx, i_id in enumerate(ids):
                if i_id and idx < len(qtds):
                    qtd_val = float(qtds[idx].replace(',', '.') or 0)
                    if qtd_val > 0:
                        item = BaseItem(base_id=b.id, insumo_id=int(i_id), quantidade=qtd_val, loja_id=session.get('loja_id'))
                        db.session.add(item)
            
            db.session.commit()
            flash(f"Base '{b.nome}' salva com sucesso!", "success")
            return redirect(url_for('bases'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao salvar base: {e}")
            flash(f"Erro ao criar base: {e}", "danger")
            
    ins = Insumo.query.filter_by(user_id=uid).all()
    return render_template('bases_form.html', insumos=ins, base=None)

@app.route('/bases/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_base(id):
    base_obj = db.session.get(Base, id)
    uid = session['usuario_id']
    usuario = db.session.get(Usuario, uid)
    
    if not base_obj:
        flash("Base não encontrada.", "danger")
        return redirect(url_for('bases'))
    
    if usuario.username != 'bpereira' and base_obj.user_id != uid:
        flash("Acesso negado.", "danger")
        return redirect(url_for('bases'))

    if request.method == 'POST':
        try:
            base_obj.nome = request.form.get('nome').upper()
            base_obj.rendimento_final = float(request.form.get('rendimento').replace(',', '.') or 1)
            BaseItem.query.filter_by(base_id=id).delete()
            
            ids = request.form.getlist('insumo_id[]')
            qtds = request.form.getlist('quantidade[]')
            for idx, i_id in enumerate(ids):
                if i_id and idx < len(qtds):
                    qtd_val = float(qtds[idx].replace(',', '.') or 0)
                    if qtd_val > 0:
                        db.session.add(BaseItem(base_id=id, insumo_id=int(i_id), quantidade=qtd_val, loja_id=session.get('loja_id')))
            
            db.session.commit()
            flash("Base atualizada com sucesso!", "success")
            return redirect(url_for('bases'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao editar base: {e}", "danger")
            
    ins = Insumo.query.filter_by(user_id=uid).all()
    return render_template('bases_form.html', base=base_obj, insumos=ins)

@app.route('/del/bas/<int:id>')
@login_required
@admin_required
def deletar_base_alias(id):
    return excluir('base', id)

# ==============================================================================
# ROTAS DE FICHAS
# ==============================================================================
@app.route('/fichas/nova', methods=['GET', 'POST'])
@login_required
def nova_ficha():
    uid = session['usuario_id']
    if request.method == 'POST':
        try:
            f = Ficha(
                nome=request.form.get('nome').upper(),
                user_id=uid,
                porcoes=float(request.form.get('porcoes').replace(',', '.') or 1),
                preco_venda=float(request.form.get('preco_venda').replace(',', '.') or 0),
                cmv_alvo=float(request.form.get('cmv_alvo').replace(',', '.') or 30),
                loja_id=session.get('loja_id')
            )
            db.session.add(f)
            db.session.flush()
            
            i_ids = request.form.getlist('insumo_id[]')
            i_qtds = request.form.getlist('insumo_qtd[]')
            for idx, val in enumerate(i_ids):
                if val: 
                    db.session.add(FichaItem(
                        ficha_id=f.id, 
                        tipo_item='insumo', 
                        referencia_id=int(val), 
                        quantidade=float(i_qtds[idx].replace(',', '.')),
                        loja_id=session.get('loja_id')
                    ))
            
            b_ids = request.form.getlist('base_id[]')
            b_qtds = request.form.getlist('base_qtd[]')
            for idx, val in enumerate(b_ids):
                if val: 
                    db.session.add(FichaItem(
                        ficha_id=f.id, 
                        tipo_item='base', 
                        referencia_id=int(val), 
                        quantidade=float(b_qtds[idx].replace(',', '.')),
                        loja_id=session.get('loja_id')
                    ))
            
            db.session.commit()
            flash("Ficha Técnica gerada com sucesso!", "success")
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar ficha: {e}", "danger")
            
    return render_template('ficha_form.html', 
                         insumos=Insumo.query.filter_by(user_id=uid).all(), 
                         bases=Base.query.filter_by(user_id=uid).all(), 
                         ficha=None)

@app.route('/fichas/ver/<int:id>')
@login_required
def ver_ficha(id):
    f = db.session.get(Ficha, id)
    uid = session['usuario_id']
    usuario = db.session.get(Usuario, uid)
    
    if not f:
        flash("Ficha não encontrada.", "warning")
        return redirect(url_for('index'))
    
    if usuario.username != 'bpereira' and f.user_id != uid:
        flash("Acesso negado.", "warning")
        return redirect(url_for('index'))
    
    metricas = EngineCalculo.processar_ficha(id)
    return render_template('ficha_ver.html', f=f, m=metricas)

@app.route('/fichas/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_ficha(id):
    f = db.session.get(Ficha, id)
    uid = session['usuario_id']
    usuario = db.session.get(Usuario, uid)
    
    if not f:
        flash("Ficha não encontrada.", "danger")
        return redirect(url_for('index'))
    
    if usuario.username != 'bpereira' and f.user_id != uid:
        flash("Acesso negado.", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            f.nome = request.form.get('nome').upper()
            f.porcoes = float(request.form.get('porcoes').replace(',', '.'))
            f.preco_venda = float(request.form.get('preco_venda').replace(',', '.'))
            f.cmv_alvo = float(request.form.get('cmv_alvo').replace(',', '.'))
            FichaItem.query.filter_by(ficha_id=id).delete()
            
            i_ids = request.form.getlist('insumo_id[]')
            i_qtds = request.form.getlist('insumo_qtd[]')
            for idx, val in enumerate(i_ids):
                if val: 
                    db.session.add(FichaItem(
                        ficha_id=id, 
                        tipo_item='insumo', 
                        referencia_id=int(val), 
                        quantidade=float(i_qtds[idx].replace(',', '.')),
                        loja_id=session.get('loja_id')
                    ))
            
            b_ids = request.form.getlist('base_id[]')
            b_qtds = request.form.getlist('base_qtd[]')
            for idx, val in enumerate(b_ids):
                if val: 
                    db.session.add(FichaItem(
                        ficha_id=id, 
                        tipo_item='base', 
                        referencia_id=int(val), 
                        quantidade=float(b_qtds[idx].replace(',', '.')),
                        loja_id=session.get('loja_id')
                    ))
                
            db.session.commit()
            flash("Ficha Técnica atualizada com sucesso!", "info")
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar ficha: {e}", "danger")
            
    return render_template('ficha_form.html', 
                         ficha=f, 
                         insumos=Insumo.query.filter_by(user_id=uid).all(), 
                         bases=Base.query.filter_by(user_id=uid).all())

# ==============================================================================
# ROTA DE EXCLUSÃO
# ==============================================================================
@app.route('/excluir/<string:alvo>/<int:id>')
@login_required
def excluir(alvo, id):
    mapa = {
        'insumo': Insumo,
        'ficha': Ficha, 
        'base': Base,
        'categoria': Categoria,
        'unidade': Unidade,
        'usuario': Usuario
    }
    
    Modelo = mapa.get(alvo)
    if not Modelo:
        flash("Operação inválida.", "danger")
        return redirect(url_for('index'))
    
    obj = db.session.get(Modelo, id)
    uid = session['usuario_id']
    usuario = db.session.get(Usuario, uid)
    
    if not obj:
        flash("Item não encontrado.", "danger")
        return redirect(url_for('index'))
    
    if alvo == 'usuario' and usuario.username != 'bpereira':
        flash("Somente o administrador mestre pode excluir usuários.", "danger")
        return redirect(url_for('config_admin'))
        
    elif alvo in ['insumo', 'ficha', 'base', 'categoria', 'unidade']:
        if usuario.username != 'bpereira' and hasattr(obj, 'user_id') and obj.user_id != uid:
            flash("Você não tem permissão para excluir este item.", "danger")
            return redirect(url_for('index'))
    
    try:
        if alvo == 'usuario' and obj.username != 'bpereira':
            mensagem = f"""
            👤 USUÁRIO EXCLUÍDO DO SISTEMA
            
            ℹ️ DETALHES:
            • Usuário excluído: {obj.username}
            • Role: {obj.role}
            • Loja: {obj.loja.nome if obj.loja else 'Não vinculada'}
            • Excluído por: {usuario.username}
            • Data exclusão: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            • IP administrador: {request.remote_addr}
            """
            enviar_alerta_email("👤 Usuário Excluído", mensagem)
        
        db.session.delete(obj)
        db.session.commit()
        flash(f"{alvo.capitalize()} excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir: {e}", "danger")
    
    if alvo == 'ficha':
        return redirect(url_for('index'))
    elif alvo == 'usuario':
        return redirect(url_for('config_admin'))
    elif alvo in ['categoria', 'unidade']:
        return redirect(url_for('config'))
    else:
        return redirect(url_for(alvo + 's'))

# ==============================================================================
# ROTAS PARA ATIVAÇÃO DE LICENÇA
# ==============================================================================
@app.route('/ativar_licenca', methods=['GET', 'POST'])
def ativar_licenca():
    if request.method == 'POST':
        chave = request.form.get('chave_licenca', '').strip()
        fingerprint = request.cookies.get('fp')
        
        if not fingerprint:
            flash("Fingerprint não detectado. Ative cookies.", "danger")
            return render_template('ativar_licenca.html')
        
        loja = Loja.query.filter_by(chave_licenca=chave).first()
        
        if not loja:
            flash("Chave de licença inválida!", "danger")
            return render_template('ativar_licenca.html')
        
        if not loja.licenca_ativa:
            flash("Licença desta loja está inativa!", "danger")
            return render_template('ativar_licenca.html')
        
        maquinas_ativas = Maquina.query.filter_by(
            loja_id=loja.id,
            ativa=True
        ).count()
        
        if maquinas_ativas >= loja.max_maquinas:
            flash(f"Limite de {loja.max_maquinas} máquina(s) atingido!", "warning")
            return render_template('ativar_licenca.html')
        
        maquina_existente = Maquina.query.filter_by(
            loja_id=loja.id,
            fingerprint=fingerprint
        ).first()
        
        if maquina_existente:
            maquina_existente.ativa = True
            maquina_existente.expira_em = loja.data_expiracao or (datetime.now() + timedelta(days=365))
            
            historico = HistoricoLicenca(
                loja_id=loja.id,
                chave_licenca=chave,
                acao='REATIVADA',
                ip=request.remote_addr,
                fingerprint=fingerprint,
                detalhes=f'Máquina reativada. ID: {maquina_existente.id}'
            )
            db.session.add(historico)
            
            flash("Máquina reativada com sucesso!", "success")
        else:
            nova_maquina = Maquina(
                loja_id=loja.id,
                fingerprint=fingerprint,
                ativa=True,
                expira_em=loja.data_expiracao or (datetime.now() + timedelta(days=365))
            )
            db.session.add(nova_maquina)
            
            historico = HistoricoLicenca(
                loja_id=loja.id,
                chave_licenca=chave,
                acao='ATIVADA',
                ip=request.remote_addr,
                fingerprint=fingerprint,
                detalhes=f'Nova máquina ativada. Máquinas ativas: {maquinas_ativas + 1}/{loja.max_maquinas}'
            )
            db.session.add(historico)
            
            flash("Licença ativada com sucesso!", "success")
        
        log = LogAcesso(
            loja_id=loja.id,
            usuario_id=None,
            fingerprint=fingerprint,
            ip=request.remote_addr,
            motivo='LICENCA_ATIVADA'
        )
        db.session.add(log)
        db.session.commit()
        
        return redirect(url_for('login'))
    
    return render_template('ativar_licenca.html')

@app.route('/solicitar_fingerprint')
def solicitar_fingerprint():
    return render_template('solicitar_fingerprint.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Você foi desconectado.", "info")
    return redirect(url_for('login'))

# ==============================================================================
# INICIALIZAÇÃO DO SISTEMA
# ==============================================================================
def setup_database():
    with app.app_context():
        db.create_all()
        
        loja = Loja.query.first()
        if not loja:
            loja = Loja(
                nome="Loja Principal", 
                ativo=True,
                licenca_ativa=True,
                max_maquinas=3
            )
            db.session.add(loja)
            db.session.commit()
            logger.info(">>> Loja padrão criada")
        else:
            if loja.chave_licenca is None:
                alphabet = string.ascii_letters + string.digits
                loja.chave_licenca = ''.join(secrets.choice(alphabet) for _ in range(32))
            if loja.data_expiracao is None:
                loja.data_expiracao = datetime.now() + timedelta(days=365)
            db.session.commit()
            logger.info(">>> Loja existente atualizada")
        
        usuario = Usuario.query.filter_by(username='bpereira').first()
        if not usuario:
            usuario = Usuario(
                username='bpereira',
                password='chef@26',
                role='admin',
                loja_id=loja.id
            )
            db.session.add(usuario)
            db.session.commit()
            logger.info(">>> Usuário mestre criado")
        else:
            if not usuario.loja_id:
                usuario.loja_id = loja.id
            if usuario.role != 'admin':
                usuario.role = 'admin'
            db.session.commit()
            logger.info(">>> Usuário mestre verificado")
        
        mensagem = f"""
        🚀 SISTEMA FOODCOST INICIADO
        
        ℹ️ INFORMAÇÕES:
        • Data inicialização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        • Banco de dados: {'PostgreSQL (Nuvem)' if database_url else 'SQLite Local'}
        • Modo: {'Produção' if not app.debug else 'Desenvolvimento'}
        • Loja padrão: {loja.nome}
        • Usuário mestre: {usuario.username}
        """
        enviar_alerta_email("🚀 Sistema FoodCost Iniciado", mensagem)

# ==============================================================================
# VERIFICAÇÃO E CRIAÇÃO DO BANCO DE DADOS
# ==============================================================================
from sqlalchemy import text

def init_database():
    """Inicializa o banco de dados e cria tabelas se necessário"""
    with app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
            print("✅ Conexão com PostgreSQL estabelecida")
            
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            if existing_tables:
                print(f"✅ Banco já contém {len(existing_tables)} tabelas")
            else:
                print("⚠️  Nenhuma tabela encontrada. Criando todas as tabelas...")
                db.create_all()
                print("✅ Todas as tabelas criadas com sucesso!")
                
        except Exception as e:
            print(f"⚠️  Erro ao inicializar banco: {e}")

# Executar na inicialização
init_database()
def validar_limite_sistema():
    """Verifica e aplica limites do sistema ao iniciar"""
    with app.app_context():
        total_lojas = Loja.query.count()
        
        if total_lojas > 10:
            # Situação CRÍTICA: Mais de 10 lojas (não deveria acontecer)
            logger.error(f"⚠️  ALERTA CRÍTICO: Sistema com {total_lojas} lojas (limite: 10)")
            
            # Enviar alerta de emergência
            mensagem = f"""
            🚨 EMERGÊNCIA: SISTEMA EXCEDEU LIMITE DE LOJAS!
            
            📋 SITUAÇÃO CRÍTICA:
            • Limite configurado: 10 lojas
            • Total atual no banco: {total_lojas} lojas
            • Excedeu em: {total_lojas - 10} lojas
            • Data verificação: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            
            🔴 AÇÕES NECESSÁRIAS:
            1. Investigar como foram criadas lojas extras
            2. Desativar lojas excedentes manualmente
            3. Verificar segurança do sistema
            """
            enviar_alerta_email("🚨 EMERGÊNCIA: Limite de Lojas Excedido", mensagem)
            
            # Desativar licenças das lojas extras (mantém apenas as 10 primeiras)
            lojas = Loja.query.order_by(Loja.id).all()
            for i, loja in enumerate(lojas):
                if i >= 10:  # A partir da 11ª loja
                    loja.licenca_ativa = False
                    loja.ativo = False
                    
                    # Registrar no histórico
                    historico = HistoricoLicenca(
                        loja_id=loja.id,
                        chave_licenca=loja.chave_licenca,
                        acao='BLOQUEADA_LIMITE',
                        ip='SISTEMA',
                        fingerprint='LIMITE_SISTEMA',
                        detalhes=f'Loja bloqueada automaticamente por exceder limite de 10 lojas. Posição: {i+1}'
                    )
                    db.session.add(historico)
                    
                    logger.warning(f"Loja '{loja.nome}' (ID: {loja.id}) bloqueada por exceder limite")
            
            db.session.commit()
            logger.info(f"✅ Limite aplicado: {min(total_lojas, 10)} lojas ativas")
        
        elif total_lojas == 10:
            logger.info(f"✅ Sistema com limite máximo: {total_lojas}/10 lojas")
        else:
            logger.info(f"✅ Sistema com {total_lojas}/10 lojas. Vagas: {10 - total_lojas}")

# Executar na inicialização
validar_limite_sistema()

# ==============================================================================
# CONFIGURAÇÃO PARA PRODUÇÃO (RENDER)
# ==============================================================================

# Criar banco de dados se não existir
@app.before_first_request
def create_tables():
    db.create_all()
    setup_database()
    validar_limite_sistema()

# Health check para Render
@app.route('/health')
def health_check():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()}), 200

# Página de erro 404
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# Página de erro 500  
@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Modo produção
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)



if __name__ == '__main__':
    # Modo produção
    if os.getenv('RENDER') or not app.debug:
        port = int(os.getenv('PORT', 10000))
        app.run(host='0.0.0.0', port=port)
    else:
        # Modo desenvolvimento local
        app.run(debug=True, host='0.0.0.0', port=10000)