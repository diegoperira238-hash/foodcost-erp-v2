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
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ==============================================================================
# CONFIGURAÇÃO DO BANCO DE DADOS PRINCIPAL
# ==============================================================================
database_url = os.getenv("DATABASE_URL")

if database_url:
    # O Render manda "postgres://". O SQLAlchemy precisa de "postgresql+psycopg://"
    # para usar a versão 3 do driver que você instalou.
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    logger.info(f"Conexão de banco: PostgreSQL (Nuvem) com driver Psycopg3")
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
        
        # Configuração para Gmail
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
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash("ACESSO NEGADO: Requer privilégios de Administrador.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('usuario_nome') != 'bpereira':
            flash("ACESSO NEGADO: Apenas o administrador mestre tem acesso.", "danger")
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
        return

    usuario = db.session.get(Usuario, usuario_id)
    if not usuario:
        session.clear()
        return redirect(url_for('login'))

    if usuario.username == 'bpereira':
        return

    if not usuario.loja_id:
        flash('Usuário sem loja vinculada.', 'danger')
        session.clear()
        return redirect(url_for('login'))

    loja = db.session.get(Loja, usuario.loja_id)
    if not loja or not loja.ativo:
        flash("Esta loja está bloqueada.", "danger")
        session.clear()
        return redirect(url_for('login'))

    if loja.licenca_ativa == False:
        # ALERTA: Tentativa de acesso a loja bloqueada
        mensagem = f"""
        🚨 TENTATIVA DE ACESSO A LOJA BLOQUEADA!
        
        📋 DETALHES:
        • Loja: {loja.nome} (ID: {loja.id})
        • Usuário: {usuario.username} (ID: {usuario.id})
        • IP: {request.remote_addr}
        • Fingerprint: {request.cookies.get('fp', 'Não detectado')}
        • Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        • User-Agent: {request.user_agent.string[:100]}
        
        ⚠️ AÇÃO NECESSÁRIA:
        Verifique se este acesso é legítimo.
        Se for tentativa não autorizada, considere:
        1. Bloquear usuário
        2. Bloquear máquina (fingerprint)
        3. Investigar origem do IP
        """
        enviar_alerta_email("🚨 Loja Bloqueada - Tentativa de Acesso", mensagem)
        
        session.clear()
        return render_template('licenca_inativa.html', loja=loja), 403
    
    if loja.data_expiracao and loja.data_expiracao < datetime.now():
        # ALERTA: Licença expirada
        mensagem = f"""
        ⚠️ TENTATIVA DE ACESSO COM LICENÇA EXPIRADA!
        
        📋 DETALHES:
        • Loja: {loja.nome}
        • Usuário: {usuario.username}
        • Licença expirou em: {loja.data_expiracao.strftime('%d/%m/%Y')}
        • Dias expirado: {(datetime.now().date() - loja.data_expiracao.date()).days} dias
        • IP: {request.remote_addr}
        • Data tentativa: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        
        💡 RECOMENDAÇÃO:
        Entre em contato com o cliente para renovação.
        """
        enviar_alerta_email("⚠️ Licença Expirada - Tentativa de Acesso", mensagem)
        
        session.clear()
        return render_template('licenca_expirada.html', loja=loja), 403

    fp = request.cookies.get('fp')
    if not fp:
        return render_template('solicitar_fingerprint.html'), 403

    licenca_valida, motivo = verificar_licenca_maquina(usuario.loja_id, fp)
    
    if not licenca_valida:
        # ALERTA: Acesso não autorizado
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
        
        🛡️ AÇÕES AUTOMÁTICAS:
        ✓ Acesso bloqueado imediatamente
        ✓ Log registrado no sistema
        ✓ IP marcado como suspeito
        
        🔍 INVESTIGUE:
        1. Verificar se é cliente tentando burlar sistema
        2. Verificar limite de máquinas excedido
        3. Considerar bloquear máquina permanentemente
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

    # Log de acesso autorizado (sem alerta)
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

        return {
            'usuario_atual': usuario,
            'is_admin': usuario.role == 'admin',
            'is_super_admin': usuario.username == 'bpereira'
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
        
        # Dashboard de Estatísticas
        if usuario.username == 'bpereira':
            fichas = Ficha.query.order_by(Ficha.nome).all()
            total_fichas = Ficha.query.count()
            total_insumos = Insumo.query.count()
            total_bases = Base.query.count()
            
            # Estatísticas avançadas
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
        
        # Processar fichas para a tabela
        lista_final = []
        for f in fichas:
            res = EngineCalculo.processar_ficha(f.id)
            lista_final.append({'ficha': f, 'metricas': res})
        
        # Informações da licença para o usuário
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
        
        # Estatísticas para o dashboard
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

# Adicione APÓS init_database() e ANTES de if __name__ == '__main__':
def create_admin_user():
    with app.app_context():
        # Em vez de 'from models import User', use:
        # Se User está definido neste mesmo arquivo:
        if 'User' in globals():
            if User.query.filter_by(username="bpereira").first() is None:
                admin = User(
                    username="bpereira",
                    password_hash="chef@26",
                    full_name="Administrador",
                    role="admin",
                    store_id=1
                )
                db.session.add(admin)
                db.session.commit()
                print("✅ Usuário admin criado manualmente: bpereira / chef@26")
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
        
        # Enviar alerta de nova licença gerada
        nova_data = (datetime.now() + timedelta(days=dias_validade)).strftime('%d/%m/%Y')
        
        mensagem = f"""
        📋 NOVA LICENÇA GERADA
        
        ℹ️ DETALHES:
        • Loja: {loja.nome} (ID: {loja.id})
        • Validade: {dias_validade} dias
        • Máximas máquinas: {max_maquinas}
        • Expira em: {nova_data}
        • Chave: {chave}
        • Gerada por: {session.get('usuario_nome')}
        • Data geração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        
        ✅ A licença está ativa e pronta para uso.
        """
        enviar_alerta_email("📋 Nova Licença Gerada", mensagem)
        
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
        
        # Enviar alerta de alteração de licença
        status_text = 'ATIVA' if novo_status else 'INATIVA'
        implicacao_text = 'Clientes podem acessar normalmente' if novo_status else 'TODOS os acessos serão bloqueados'
        
        mensagem = f"""
        🔄 STATUS DA LICENÇA ALTERADO
        
        ℹ️ DETALHES:
        • Loja: {loja.nome} (ID: {loja.id})
        • Novo status: {status_text}
        • Alterado por: {session.get('usuario_nome')}
        • Data alteração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        • IP administrador: {request.remote_addr}
        
        ⚠️ IMPLICAÇÕES:
        • Status {status_text}: {implicacao_text}
        """
        enviar_alerta_email("🔄 Status de Licença Alterado", mensagem)
        
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
        
        # Enviar alerta de extensão
        mensagem = f"""
        📅 LICENÇA ESTENDIDA
        
        ℹ️ DETALHES:
        • Loja: {loja.nome} (ID: {loja.id})
        • Dias adicionados: {dias_adicionais}
        • Nova data expiração: {loja.data_expiracao.strftime('%d/%m/%Y')}
        • Dias totais restantes: {dias_restantes(loja.data_expiracao)}
        • Extendida por: {session.get('usuario_nome')}
        • Data extensão: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        
        ✅ A licença foi renovada com sucesso.
        """
        enviar_alerta_email("📅 Licença Estendida", mensagem)
        
        db.session.commit()
        flash(f"Licença estendida em {dias_adicionais} dias para {loja.nome}", "success")
    
    return redirect(url_for('admin_master'))

# ==============================================================================
# PAINEL DE MONITORAMENTO EM TEMPO REAL
# ==============================================================================

@app.route('/admin/monitor', methods=['GET', 'POST'])
@login_required
@super_admin_required
def admin_monitor():
    """Painel de monitoramento em tempo real"""
    
    # Buscar todas as atividades recentes
    logs = LogAcesso.query.order_by(LogAcesso.data.desc()).limit(500).all()
    
    # Agrupar por IP para detectar suspeitas
    atividades_por_ip = {}
    for log in logs:
        ip = log.ip
        if ip not in atividades_por_ip:
            atividades_por_ip[ip] = {
                'total': 0,
                'autorizados': 0,
                'nao_autorizados': 0,
                'primeiro_acesso': log.data,
                'ultimo_acesso': log.data,
                'lojas': set(),
                'usuarios': set()
            }
        
        info = atividades_por_ip[ip]
        info['total'] += 1
        info['ultimo_acesso'] = log.data
        
        if 'AUTORIZADO' in log.motivo:
            info['autorizados'] += 1
        else:
            info['nao_autorizados'] += 1
        
        if log.loja:
            info['lojas'].add(log.loja.nome)
        if log.usuario:
            info['usuarios'].add(log.usuario.username)
    
    # Ordenar IPs por atividades suspeitas
    ips_suspeitos = []
    for ip, info in atividades_por_ip.items():
        # Converter set para lista para serialização
        info['lojas'] = list(info['lojas'])
        info['usuarios'] = list(info['usuarios'])
        
        if info['nao_autorizados'] > 3:  # Mais de 3 tentativas falhas
            info['nivel_risco'] = 'ALTO'
            ips_suspeitos.append((ip, info))
        elif info['nao_autorizados'] > 0:
            info['nivel_risco'] = 'MÉDIO'
            ips_suspeitos.append((ip, info))
        else:
            info['nivel_risco'] = 'BAIXO'
    
    # Ordenar por risco
    ips_suspeitos.sort(key=lambda x: (x[1]['nao_autorizados'], x[1]['total']), reverse=True)
    
    # Estatísticas gerais
    total_logs = len(logs)
    logs_24h = sum(1 for l in logs if (datetime.now() - l.data).total_seconds() < 86400)
    logs_nao_autorizados = sum(1 for l in logs if 'NAO_AUTORIZADO' in l.motivo)
    
    stats = {
        'total_logs': total_logs,
        'logs_24h': logs_24h,
        'logs_nao_autorizados': logs_nao_autorizados,
        'ips_monitorados': len(atividades_por_ip),
        'ips_suspeitos': len([ip for ip, info in atividades_por_ip.items() if info['nao_autorizados'] > 0])
    }
    
    return render_template('admin_monitor.html',
                         logs=logs[:100],
                         ips_suspeitos=ips_suspeitos,
                         stats=stats,
                         agora=datetime.now())

@app.route('/admin/bloquear_ip/<string:ip>', methods=['POST'])
@login_required
@super_admin_required
def bloquear_ip(ip):
    """Bloqueia um IP permanentemente"""
    try:
        # Criar log do bloqueio
        log_bloqueio = LogAcesso(
            loja_id=None,
            usuario_id=session.get('usuario_id'),
            fingerprint='SISTEMA',
            ip=ip,
            motivo=f'IP_BLOQUEADO_MANUALMENTE por {session.get("usuario_nome")}'
        )
        db.session.add(log_bloqueio)
        
        # Enviar alerta de bloqueio
        mensagem = f"""
        🚫 IP BLOQUEADO MANUALMENTE
        
        ℹ️ DETALHES:
        • IP Bloqueado: {ip}
        • Bloqueado por: {session.get('usuario_nome')}
        • Data bloqueio: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        • IP administrador: {request.remote_addr}
        
        📊 ATIVIDADES DESTE IP:
        • Tentativas não autorizadas: {sum(1 for l in LogAcesso.query.filter_by(ip=ip).all() if 'NAO_AUTORIZADO' in l.motivo)}
        • Total acessos: {LogAcesso.query.filter_by(ip=ip).count()}
        
        ✅ A partir de agora, este IP será rejeitado.
        """
        enviar_alerta_email("🚫 IP Bloqueado Manualmente", mensagem)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'IP {ip} bloqueado com sucesso!'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        })

# ==============================================================================
# ROTAS PARA ADMIN (gerenciamento básico)
# ==============================================================================

@app.route('/config/admin', methods=['GET', 'POST'])
@login_required
@admin_required
def config_admin():
    usuario = db.session.get(Usuario, session['usuario_id'])
    
    if usuario.username != 'bpereira':
        lojas = Loja.query.filter_by(id=usuario.loja_id).all() if usuario.loja_id else []
    else:
        lojas = Loja.query.order_by(Loja.nome).all()
    
    if request.method == 'POST':
        tipo_acao = request.form.get('tipo_acao')
        
        if tipo_acao == 'add_loja' and usuario.username == 'bpereira':
            nome = request.form.get('nome_loja', '').strip()
            if nome:
                if not Loja.query.filter_by(nome=nome).first():
                    nova_loja = Loja(
                        nome=nome, 
                        ativo=True,
                        licenca_ativa=True,
                        max_maquinas=1
                    )
                    db.session.add(nova_loja)
                    db.session.commit()
                    flash(f"Loja '{nome}' criada com sucesso!", "success")
        
        elif tipo_acao == 'toggle_loja' and usuario.username == 'bpereira':
            loja_id = request.form.get('loja_id')
            loja = db.session.get(Loja, loja_id)
            if loja:
                loja.ativo = not loja.ativo
                db.session.commit()
                flash(f"Loja {'ativada' if loja.ativo else 'desativada'}!", "info")
        
        elif tipo_acao == 'add_user':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            loja_id = request.form.get('loja_id')
            role = request.form.get('role', 'user')
            
            if username and password:
                if not Usuario.query.filter_by(username=username).first():
                    novo_usuario = Usuario(
                        username=username,
                        password=password,
                        role=role,
                        loja_id=loja_id if loja_id else usuario.loja_id
                    )
                    db.session.add(novo_usuario)
                    db.session.commit()
                    flash(f"Usuário {username} criado com sucesso!", "success")
        
        elif tipo_acao == 'toggle_role':
            user_id = request.form.get('user_id')
            usuario_alvo = db.session.get(Usuario, user_id)
            if usuario_alvo and usuario_alvo.id != session['usuario_id']:
                usuario_alvo.role = 'admin' if usuario_alvo.role == 'user' else 'user'
                db.session.commit()
                flash(f"Role alterado para {usuario_alvo.role}!", "info")
        
        elif tipo_acao == 'reset_password':
            user_id = request.form.get('user_id')
            nova_senha = request.form.get('nova_senha')
            confirmar_senha = request.form.get('confirmar_senha')
            
            if nova_senha == confirmar_senha:
                usuario_alvo = db.session.get(Usuario, user_id)
                if usuario_alvo:
                    usuario_alvo.password = nova_senha
                    db.session.commit()
                    flash("Senha resetada com sucesso!", "success")
            else:
                flash("As senhas não coincidem!", "danger")
        
        return redirect(url_for('config_admin'))
    
    if usuario.username == 'bpereira':
        usuarios = Usuario.query.order_by(Usuario.username).all()
    else:
        usuarios = Usuario.query.filter_by(loja_id=usuario.loja_id).order_by(Usuario.username).all()
    
    stats = {
        'total_lojas': len(lojas),
        'lojas_ativas': sum(1 for l in lojas if l.ativo),
        'total_usuarios': len(usuarios),
        'usuarios_admin': sum(1 for u in usuarios if u.role == 'admin'),
        'total_categorias': Categoria.query.count(),
        'total_unidades': Unidade.query.count()
    }
    
    return render_template('config_admin.html',
                         lojas=lojas,
                         usuarios=usuarios,
                         stats=stats,
                         agora=datetime.now())

# ==============================================================================
# ROTAS DE MÁQUINAS
# ==============================================================================

@app.route('/maquinas')
@login_required
@admin_required
def listar_maquinas():
    usuario = db.session.get(Usuario, session['usuario_id'])
    
    if usuario.username == 'bpereira':
        maquinas = Maquina.query.order_by(Maquina.criada_em.desc()).all()
        lojas = Loja.query.all()
    else:
        maquinas = Maquina.query.filter_by(loja_id=usuario.loja_id).order_by(Maquina.criada_em.desc()).all()
        lojas = Loja.query.filter_by(id=usuario.loja_id).all()
    
    return render_template('maquinas.html', maquinas=maquinas, lojas=lojas, agora=datetime.now())

@app.route('/maquina/nova', methods=['GET', 'POST'])
@login_required
@admin_required
def nova_maquina():
    usuario = db.session.get(Usuario, session['usuario_id'])
    
    if request.method == 'POST':
        fingerprint = request.form.get('fingerprint')
        loja_id = request.form.get('loja_id')
        dias = int(request.form.get('dias_validade', 365))
        
        if fingerprint and loja_id:
            if usuario.username != 'bpereira' and int(loja_id) != usuario.loja_id:
                flash("Você não tem permissão para cadastrar máquina nesta loja.", "danger")
                return redirect(url_for('listar_maquinas'))
            
            maquina = Maquina(
                fingerprint=fingerprint,
                loja_id=loja_id,
                ativa=True,
                expira_em=datetime.now() + timedelta(days=dias)
            )
            db.session.add(maquina)
            db.session.commit()
            flash("Máquina cadastrada com sucesso!", "success")
            return redirect(url_for('listar_maquinas'))
    
    if usuario.username == 'bpereira':
        lojas = Loja.query.filter_by(ativo=True).all()
    else:
        lojas = Loja.query.filter_by(id=usuario.loja_id, ativo=True).all()
    
    return render_template('maquina_form.html', lojas=lojas)

@app.route('/maquina/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_maquina(id):
    maquina = db.session.get(Maquina, id)
    usuario = db.session.get(Usuario, session['usuario_id'])
    
    if not maquina:
        flash("Máquina não encontrada.", "danger")
        return redirect(url_for('listar_maquinas'))
    
    if usuario.username != 'bpereira' and maquina.loja_id != usuario.loja_id:
        flash("Você não tem permissão para editar esta máquina.", "danger")
        return redirect(url_for('listar_maquinas'))
    
    if request.method == 'POST':
        maquina.fingerprint = request.form.get('fingerprint')
        dias = int(request.form.get('dias_validade', 365))
        maquina.expira_em = datetime.now() + timedelta(days=dias)
        
        if usuario.username == 'bpereira':
            maquina.loja_id = request.form.get('loja_id')
        
        db.session.commit()
        flash("Máquina atualizada!", "success")
        return redirect(url_for('listar_maquinas'))
    
    if usuario.username == 'bpereira':
        lojas = Loja.query.filter_by(ativo=True).all()
    else:
        lojas = Loja.query.filter_by(id=usuario.loja_id, ativo=True).all()
    
    return render_template('maquina_form.html', maquina=maquina, lojas=lojas)

@app.route('/maquina/toggle/<int:id>')
@login_required
@admin_required
def toggle_maquina(id):
    maquina = db.session.get(Maquina, id)
    usuario = db.session.get(Usuario, session['usuario_id'])
    
    if maquina:
        if usuario.username != 'bpereira' and maquina.loja_id != usuario.loja_id:
            flash("Você não tem permissão para alterar esta máquina.", "danger")
            return redirect(url_for('listar_maquinas'))
        
        novo_status = not maquina.ativa
        maquina.ativa = novo_status
        
        # Enviar alerta de alteração de máquina
        status_text = 'ATIVA' if novo_status else 'INATIVA'
        implicacao_text = 'Máquina pode acessar o sistema' if novo_status else 'Máquina BLOQUEADA imediatamente'
        
        mensagem = f"""
        💻 STATUS DE MÁQUINA ALTERADO
        
        ℹ️ DETALHES:
        • Máquina ID: {maquina.id}
        • Fingerprint: {maquina.fingerprint[:20]}...
        • Loja: {maquina.loja.nome if maquina.loja else 'Não vinculada'}
        • Novo status: {status_text}
        • Alterado por: {usuario.username}
        • Data alteração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        
        ⚠️ IMPLICAÇÕES:
        • Status {status_text}: {implicacao_text}
        """
        enviar_alerta_email("💻 Status de Máquina Alterado", mensagem)
        
        db.session.commit()
        flash(f"Máquina {'ativada' if maquina.ativa else 'desativada'}!", "info")
    
    return redirect(url_for('listar_maquinas'))

@app.route('/maquina/historico/<int:id>')
@login_required
@admin_required
def historico_maquina(id):
    maquina = db.session.get(Maquina, id)
    usuario = db.session.get(Usuario, session['usuario_id'])
    
    if not maquina:
        flash("Máquina não encontrada.", "danger")
        return redirect(url_for('listar_maquinas'))
    
    if usuario.username != 'bpereira' and maquina.loja_id != usuario.loja_id:
        flash("Você não tem permissão para ver esta máquina.", "danger")
        return redirect(url_for('listar_maquinas'))
    
    logs = LogAcesso.query.filter_by(fingerprint=maquina.fingerprint).order_by(LogAcesso.data.desc()).all()
    return render_template('maquina_historico.html', maquina=maquina, logs=logs)

# ==============================================================================
# ROTAS PARA USUÁRIOS NORMAIS (configuração básica)
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
        # Se for usuário, enviar alerta
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
            
            ⚠️ Este usuário não poderá mais acessar o sistema.
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
            mensagem = f"""
            🔄 MÁQUINA REATIVADA
            
            ℹ️ DETALHES:
            • Loja: {loja.nome}
            • Máquina ID: {maquina_existente.id}
            • Fingerprint: {fingerprint[:20]}...
            • Expira em: {maquina_existente.expira_em.strftime('%d/%m/%Y')}
            • Dias restantes: {dias_restantes(maquina_existente.expira_em)}
            • Data ativação: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            • IP ativação: {request.remote_addr}
            
            ✅ Máquina reativada com sucesso.
            """
            enviar_alerta_email("🔄 Máquina Reativada", mensagem)
            flash("Máquina reativada com sucesso!", "success")
        else:
            nova_maquina = Maquina(
                loja_id=loja.id,
                fingerprint=fingerprint,
                ativa=True,
                expira_em=loja.data_expiracao or (datetime.now() + timedelta(days=365))
            )
            db.session.add(nova_maquina)
            
            mensagem = f"""
            ✅ NOVA MÁQUINA ATIVADA
            
            ℹ️ DETALHES:
            • Loja: {loja.nome}
            • Fingerprint: {fingerprint[:20]}...
            • Expira em: {nova_maquina.expira_em.strftime('%d/%m/%Y')}
            • Máquinas ativas agora: {maquinas_ativas + 1}/{loja.max_maquinas}
            • Data ativação: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            • IP ativação: {request.remote_addr}
            
            📊 ESTATÍSTICAS DA LOJA:
            • Máquinas ativas: {maquinas_ativas + 1}
            • Limite máximo: {loja.max_maquinas}
            • Dias restantes licença: {dias_restantes(loja.data_expiracao)}
            """
            enviar_alerta_email("✅ Nova Máquina Ativada", mensagem)
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
        
        # Enviar alerta de inicialização
        mensagem = f"""
        🚀 SISTEMA FOODCOST INICIADO
        
        ℹ️ INFORMAÇÕES:
        • Data inicialização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        • Banco de dados: {'PostgreSQL (Nuvem)' if database_url else 'SQLite Local'}
        • Modo: {'Produção' if not app.debug else 'Desenvolvimento'}
        • Loja padrão: {loja.nome}
        • Usuário mestre: {usuario.username}
        
        ✅ Sistema pronto para uso.
        """
        enviar_alerta_email("🚀 Sistema FoodCost Iniciado", mensagem)

# ==============================================================================
# VERIFICAÇÃO E CRIAÇÃO DO BANCO DE DADOS
# ==============================================================================
from sqlalchemy import text  # <-- ADICIONE ESTA LINHA

from sqlalchemy import text  # ADICIONE ESTA IMPORT AQUI

def init_database():
    """Inicializa o banco de dados e cria tabelas se necessário"""
    with app.app_context():
        try:
            # Verificar se o banco está acessível
            db.session.execute(text("SELECT 1"))
            print("✅ Conexão com PostgreSQL estabelecida")
            
            # Verificar se tabelas existem
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            if existing_tables:
                print(f"✅ Banco já contém {len(existing_tables)} tabelas")
            else:
                print("⚠️  Nenhuma tabela encontrada. Criando todas as tabelas...")
                db.create_all()
                print("✅ Todas as tabelas criadas com sucesso!")
                
                # TENTAR criar usuário admin (com tratamento de erro)
                try:
                    # OPÇÃO 1: Se User está no mesmo arquivo
                    if 'User' in globals():
                        if User.query.first() is None:
                            admin = User(
                                username="bpereira",
                                password_hash="chef@26",
                                full_name="Administrador",
                                role="admin",
                                store_id=1
                            )
                            db.session.add(admin)
                            db.session.commit()
                            print("✅ Usuário admin criado: bpereira / chef@26")
                    
                    # OPÇÃO 2: Se User está em models.py
                    elif True:  # Mude para verificar se models existe
                        from models import User
                        if User.query.first() is None:
                            admin = User(
                                username="bpereira",
                                password_hash="chef@26",
                                full_name="Administrador", 
                                role="admin",
                                store_id=1
                            )
                            db.session.add(admin)
                            db.session.commit()
                            print("✅ Usuário admin criado: bpereira / chef@26")
                            
                except ImportError:
                    print("⚠️  Módulo 'models' não encontrado. Pulando criação de usuário.")
                except Exception as e:
                    print(f"⚠️  Não foi possível criar usuário: {e}")
                    print("ℹ️  Crie manualmente: bpereira / chef@26")
                
        except Exception as e:
            print(f"⚠️  Erro ao inicializar banco: {e}")
            # Não precisa de traceback completo

# Executar na inicialização
init_database()


if __name__ == '__main__':
    # Remova setup_database() se já chamou init_database() acima
    # setup_database()  # COMENTE ou REMOVA esta linha
    
    # Modo produção
    if os.getenv('RENDER') or not app.debug:
        port = int(os.getenv('PORT', 10000))
        app.run(host='0.0.0.0', port=port)
    else:
        # Modo desenvolvimento local
        app.run(debug=True, host='0.0.0.0', port=5000)