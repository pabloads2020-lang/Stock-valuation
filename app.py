import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import math
from deep_translator import GoogleTranslator
import requests
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# CONFIGURAÇÃO DE SESSÃO COM RETRY E BACKOFF
# ============================================================

def criar_sessao_com_retry():
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    return session

CACHE_TICKERS = {}

st.set_page_config(
    page_title="Multi-Valuation - Graham, Bazin, Gordon & DCF",
    page_icon="📊",
    layout="wide"
)

# ============================================================
# CSS PERSONALIZADO
# ============================================================

st.markdown("""
<style>
    .main { background-color: #F5F6F8; }
    .stApp { background-color: #F5F6F8; }
    .metric-card {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        text-align: center;
        border: 1px solid #E8E9EC;
        height: 100%;
    }
    .metric-label {
        color: #4A5568;
        font-size: 11px;
        letter-spacing: 1px;
        margin-bottom: 5px;
    }
    .metric-value {
        color: #0B1C3F;
        font-size: 22px;
        font-weight: bold;
    }
    .model-title {
        font-size: 18px;
        font-weight: bold;
        color: #0B1C3F;
        margin-bottom: 10px;
        text-align: center;
    }
    .recomendacao {
        text-align: center;
        padding: 8px;
        border-radius: 8px;
        margin-top: 10px;
        font-weight: bold;
        font-size: 14px;
    }
    .recomendacao-COMPRAR { background-color: #2E7D32; color: white; }
    .recomendacao-COMPRA-PARCIAL { background-color: #C9A03D; color: white; }
    .recomendacao-NEUTRO { background-color: #4A5568; color: white; }
    .recomendacao-EVITAR { background-color: #C62828; color: white; }
    .card-container {
        display: flex;
        gap: 20px;
        margin-bottom: 30px;
    }
    h1, h2, h3 { color: #0B1C3F; }
    hr {
        margin: 20px 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #C9A03D, transparent);
    }
    .param-card {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# FUNÇÕES DE VALUATION
# ============================================================

def calcular_graham(lpa, vpa):
    """Método Benjamin Graham: √(22,5 × LPA × VPA)"""
    if lpa and vpa and lpa > 0 and vpa > 0:
        return math.sqrt(22.5 * lpa * vpa)
    return None

def calcular_bazin(dividendos_anuais):
    """Método Bazin: (Dividendo anual × 100) / 6"""
    if dividendos_anuais and dividendos_anuais > 0:
        return (dividendos_anuais * 100) / 6
    return None

def calcular_gordon(dividendos_anuais, taxa_crescimento=0.04, taxa_desconto=0.10):
    """Método Gordon: D0 × (1+g) / (k - g)"""
    if dividendos_anuais and dividendos_anuais > 0:
        return (dividendos_anuais * (1 + taxa_crescimento)) / (taxa_desconto - taxa_crescimento)
    return None

def calcular_dcf(ebit, capex, depreciacao, divida_liquida, num_acoes, 
                 taxa_ir=0.34, crescimento_inicial=0.10, crescimento_terminal=0.06,
                 wacc=0.11, crescimento_perpetuo=0.03, anos=5):
    """
    Método DCF (Fluxo de Caixa Descontado)
    Valor da Empresa = Σ FCFt/(1+WACC)^t + Valor Residual
    """
    if not ebit or ebit <= 0:
        return None
    
    # Fluxo de caixa livre atual
    fcf_atual = ebit * (1 - taxa_ir) + depreciacao - capex
    
    if fcf_atual <= 0:
        return None
    
    # 1. Projetar fluxos de caixa
    fluxos_presentes = []
    for ano in range(1, anos + 1):
        if ano <= 3:
            taxa = crescimento_inicial
        else:
            taxa = crescimento_terminal
        
        fcf_ano = fcf_atual * (1 + taxa) ** ano
        fcf_presente = fcf_ano / ((1 + wacc) ** ano)
        fluxos_presentes.append(fcf_presente)
    
    # 2. Valor presente dos fluxos
    valor_presente_fluxos = sum(fluxos_presentes)
    
    # 3. Valor residual (perpetuidade)
    fcf_ultimo = fcf_atual * (1 + crescimento_terminal) ** anos
    valor_residual = fcf_ultimo * (1 + crescimento_perpetuo) / (wacc - crescimento_perpetuo)
    valor_presente_residual = valor_residual / ((1 + wacc) ** anos)
    
    # 4. Valor da empresa
    valor_empresa = valor_presente_fluxos + valor_presente_residual
    
    # 5. Valor da ação
    valor_acao = (valor_empresa - divida_liquida) / num_acoes
    
    return valor_acao

def calcular_margem_seguranca(cotacao, valor_justo):
    if cotacao and valor_justo and cotacao > 0 and valor_justo:
        return ((valor_justo - cotacao) / valor_justo) * 100
    return None

def calcular_recomendacao(margem):
    if margem is None:
        return "NEUTRO", "⚠️ Dados Insuficientes"
    if margem >= 30:
        return "COMPRAR", "Ótima oportunidade!"
    elif margem >= 15:
        return "COMPRA PARCIAL", "Boa oportunidade"
    elif margem >= 0:
        return "NEUTRO", "Preço justo"
    else:
        return "EVITAR", "Ação cara"

# ============================================================
# VELOCÍMETRO GENÉRICO
# ============================================================

def criar_velocimetro(margem, titulo, cor_verde="#2E7D32", cor_amarela="#C9A03D", cor_vermelha="#C62828"):
    if margem is None:
        margem = 0
    
    if margem < 0:
        cor_marcador = cor_vermelha
    elif margem < 20:
        cor_marcador = cor_amarela
    else:
        cor_marcador = cor_verde
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=margem,
        number={
            'suffix': "%", 
            'font': {'size': 36, 'color': "black", 'family': "Arial", 'weight': "bold"},
            'valueformat': '.1f'
        },
        title={
            'text': titulo, 
            'font': {'size': 11, 'color': "gray", 'family': "Arial"}
        },
        gauge={
            'axis': {
                'range': [-100, 100],
                'tickwidth': 1,
                'tickcolor': "black",
                'ticklen': 8,
                'tickfont': {'size': 9, 'color': "black"},
                'ticks': 'outside',
                'tickvals': [-100, -50, 0, 50, 100],
                'ticktext': ['-100', '-50', '0', '50', '100']
            },
            'bar': {'color': "black", 'thickness': 0.03},
            'bgcolor': "white",
            'borderwidth': 0,
            'steps': [
                {'range': [-100, 0], 'color': cor_vermelha, 'thickness': 0.5},
                {'range': [0, 20], 'color': cor_amarela, 'thickness': 0.5},
                {'range': [20, 100], 'color': cor_verde, 'thickness': 0.5}
            ],
            'threshold': {
                'line': {'color': cor_marcador, 'width': 3},
                'thickness': 0.6,
                'value': margem
            }
        }
    ))
    
    fig.update_layout(
        height=220,
        margin=dict(l=30, r=30, t=50, b=20),
        paper_bgcolor="white"
    )
    
    return fig

# ============================================================
# BUSCA DE DADOS (otimizada)
# ============================================================

def buscar_resumo_status_invest(ticker):
    ticker_clean = ticker.upper().replace('.SA', '')
    cache_key = f"resumo_{ticker_clean}"
    if cache_key in CACHE_TICKERS:
        return CACHE_TICKERS[cache_key]
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        url = f"https://statusinvest.com.br/acao/companyinfo?code={ticker_clean}"
        session = criar_sessao_com_retry()
        response = session.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            dados = response.json()
            resumo = dados.get('description') or dados.get('businessDescription')
            if resumo and len(resumo) > 50:
                CACHE_TICKERS[cache_key] = resumo
                return resumo
    except:
        pass
    
    CACHE_TICKERS[cache_key] = None
    return None

def traduzir_para_portugues(texto_ingles):
    if not texto_ingles:
        return "Informação não disponível"
    try:
        tradutor = GoogleTranslator(source='auto', target='pt')
        return tradutor.translate(texto_ingles)
    except:
        return texto_ingles

def buscar_dados(ticker_input):
    ticker_input = ticker_input.strip().upper()
    
    if ticker_input in CACHE_TICKERS:
        return CACHE_TICKERS[ticker_input]
    
    ticker_yahoo = f"{ticker_input}.SA" if not ticker_input.endswith('.SA') else ticker_input
    
    try:
        time.sleep(random.uniform(1.0, 2.0))
        
        stock = yf.Ticker(ticker_yahoo)
        info = stock.info
        
        if not info:
            return None
        
        cotacao = info.get('currentPrice') or info.get('regularMarketPrice')
        lpa = info.get('trailingEps')
        vpa = info.get('bookValue')
        pl = info.get('trailingPE')
        roe = info.get('returnOnEquity')
        nome = info.get('longName') or ticker_input
        
        # Dados para DCF
        ebit = info.get('ebitda') or info.get('operatingIncome')
        capex = info.get('capitalExpenditures') or info.get('capitalExpenditure', 0)
        depreciacao = info.get('depreciation', ebit * 0.1 if ebit else 0)
        divida_bruta = info.get('totalDebt', 0)
        caixa = info.get('totalCash', 0)
        divida_liquida = divida_bruta - caixa
        num_acoes = info.get('sharesOutstanding', 0)
        
        if capex == 0:
            capex = ebit * 0.15 if ebit else 0
        
        # Dividendos (para Bazin e Gordon)
        dividendos = info.get('dividendRate', 0)
        if not dividendos or dividendos == 0:
            dividendos = info.get('totalCashPerShare', 0)
        
        if roe:
            roe = roe * 100
        
        if not lpa and pl and cotacao:
            lpa = cotacao / pl if pl > 0 else None
        
        # Cálculo dos 4 modelos
        valor_justo_graham = calcular_graham(lpa, vpa)
        valor_justo_bazin = calcular_bazin(dividendos)
        valor_justo_gordon = calcular_gordon(dividendos)
        
        # DCF será calculado na interface com parâmetros ajustáveis
        # Por enquanto, apenas preparamos os dados
        
        margem_graham = calcular_margem_seguranca(cotacao, valor_justo_graham)
        margem_bazin = calcular_margem_seguranca(cotacao, valor_justo_bazin)
        margem_gordon = calcular_margem_seguranca(cotacao, valor_justo_gordon)
        
        # Resumo
        resumo = buscar_resumo_status_invest(ticker_input)
        if not resumo:
            resumo_en = info.get('longBusinessSummary', '')
            resumo = traduzir_para_portugues(resumo_en) if resumo_en else "Informações não disponíveis"
        
        resultado = {
            "ticker": ticker_input,
            "nome": nome,
            "cotacao": cotacao,
            "lpa": lpa,
            "vpa": vpa,
            "pl": pl,
            "roe": roe,
            "dividendos": dividendos,
            "ebit": ebit,
            "capex": capex,
            "depreciacao": depreciacao,
            "divida_liquida": divida_liquida,
            "num_acoes": num_acoes,
            "valor_justo_graham": valor_justo_graham,
            "valor_justo_bazin": valor_justo_bazin,
            "valor_justo_gordon": valor_justo_gordon,
            "margem_graham": margem_graham,
            "margem_bazin": margem_bazin,
            "margem_gordon": margem_gordon,
            "resumo": resumo,
            "setor": info.get('sector', 'N/D'),
            "segmento": info.get('industry', 'N/D')
        }
        
        CACHE_TICKERS[ticker_input] = resultado
        return resultado
        
    except Exception as e:
        st.error(f"Erro ao buscar dados: {str(e)}")
        return None

# ============================================================
# INTERFACE PRINCIPAL
# ============================================================

st.title("📊 MULTI-VALUATION SYSTEM")
st.markdown("*Graham • Bazin • Gordon • DCF*")
st.markdown("---")

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/investment.png", width=80)
    st.markdown("## 🔍 Análise de Investimentos")
    st.markdown("### 4 Modelos de Valuation")
    st.markdown("---")
    
    ticker = st.text_input("📈 Ticker da Ação", value="ITSA4", help="Ex: ITSA4, PETR4, VALE3")
    
    col1, col2 = st.columns(2)
    with col1:
        analisar = st.button("🔍 ANALISAR", use_container_width=True)
    with col2:
        limpar = st.button("🗑️ LIMPAR", use_container_width=True)
    
    st.markdown("---")
    st.markdown("### 📋 Sobre os Modelos")
    st.markdown("**Graham:** √(22,5 × LPA × VPA)")
    st.markdown("**Bazin:** (Dividendo × 100) / 6")
    st.markdown("**Gordon:** D0 × (1+g) / (k-g)")
    st.markdown("**DCF:** Fluxo de Caixa Descontado")
    st.markdown("---")
    st.markdown("### 📋 Exemplos")
    st.markdown("- ITSA4 (Itaúsa)")
    st.markdown("- PETR4 (Petrobras)")
    st.markdown("- VALE3 (Vale)")
    st.markdown("- BBAS3 (Banco do Brasil)")
    st.markdown("---")
    st.markdown("### ℹ️ Sobre")
    st.markdown("Valuation baseada em 4 metodologias")
    st.markdown("Fonte: Yahoo Finance")

if limpar:
    CACHE_TICKERS.clear()
    st.rerun()

if analisar:
    with st.spinner("🔄 Buscando dados..."):
        dados = buscar_dados(ticker)
    
    if dados:
        # Cabeçalho
        st.markdown(f"## {dados['ticker']} - {dados['nome']}")
        st.caption(f"Setor: {dados['setor']} | Segmento: {dados['segmento']} | Cotação atual: R$ {dados['cotacao']:.2f}")
        st.markdown("---")
        
        # ==================== SELETOR COM ABAS ====================
        st.markdown("## 📊 MODELOS DE VALUATION")
        
        # Criar abas para cada modelo
        tab1, tab2, tab3, tab4 = st.tabs(["📘 BENJAMIN GRAHAM", "💰 BAZIN (6%)", "📈 GORDON (GGM)", "📉 DCF (Fluxo de Caixa)"])
        
        # ==================== ABA 1 - GRAHAM ====================
        with tab1:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.markdown("### 📊 Valuation Graham")
                if dados['valor_justo_graham']:
                    st.metric("Valor Justo", f"R$ {dados['valor_justo_graham']:.2f}")
                    st.metric("Cotação Atual", f"R$ {dados['cotacao']:.2f}")
                    st.metric("Margem de Segurança", f"{dados['margem_graham']:+.1f}%")
                    recomendacao_graham, _ = calcular_recomendacao(dados['margem_graham'])
                    if recomendacao_graham == "COMPRAR":
                        st.success(f"✅ {recomendacao_graham}")
                    elif recomendacao_graham == "COMPRA PARCIAL":
                        st.warning(f"⚠️ {recomendacao_graham}")
                    elif recomendacao_graham == "NEUTRO":
                        st.info(f"⚖️ {recomendacao_graham}")
                    else:
                        st.error(f"❌ {recomendacao_graham}")
                else:
                    st.warning("Dados insuficientes para calcular o modelo Graham")
            
            with col2:
                if dados['margem_graham']:
                    fig_graham = criar_velocimetro(dados['margem_graham'], "MARGEM GRAHAM")
                    st.plotly_chart(fig_graham, use_container_width=True)
                else:
                    st.info("Velocímetro indisponível")
        
        # ==================== ABA 2 - BAZIN ====================
        with tab2:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.markdown("### 💰 Valuation Bazin")
                if dados['valor_justo_bazin']:
                    st.metric("Valor Justo", f"R$ {dados['valor_justo_bazin']:.2f}")
                    st.metric("Cotação Atual", f"R$ {dados['cotacao']:.2f}")
                    st.metric("Dividendo Anual", f"R$ {dados['dividendos']:.2f}" if dados['dividendos'] else "N/D")
                    st.metric("Margem de Segurança", f"{dados['margem_bazin']:+.1f}%")
                    recomendacao_bazin, _ = calcular_recomendacao(dados['margem_bazin'])
                    if recomendacao_bazin == "COMPRAR":
                        st.success(f"✅ {recomendacao_bazin}")
                    elif recomendacao_bazin == "COMPRA PARCIAL":
                        st.warning(f"⚠️ {recomendacao_bazin}")
                    elif recomendacao_bazin == "NEUTRO":
                        st.info(f"⚖️ {recomendacao_bazin}")
                    else:
                        st.error(f"❌ {recomendacao_bazin}")
                else:
                    st.warning("Dados insuficientes para calcular o modelo Bazin")
            
            with col2:
                if dados['margem_bazin']:
                    fig_bazin = criar_velocimetro(dados['margem_bazin'], "MARGEM BAZIN")
                    st.plotly_chart(fig_bazin, use_container_width=True)
                else:
                    st.info("Velocímetro indisponível")
        
        # ==================== ABA 3 - GORDON ====================
        with tab3:
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.markdown("### 📈 Valuation Gordon (GGM)")
                if dados['valor_justo_gordon']:
                    st.metric("Valor Justo", f"R$ {dados['valor_justo_gordon']:.2f}")
                    st.metric("Cotação Atual", f"R$ {dados['cotacao']:.2f}")
                    st.metric("Dividendo Anual", f"R$ {dados['dividendos']:.2f}" if dados['dividendos'] else "N/D")
                    st.metric("Margem de Segurança", f"{dados['margem_gordon']:+.1f}%")
                    recomendacao_gordon, _ = calcular_recomendacao(dados['margem_gordon'])
                    if recomendacao_gordon == "COMPRAR":
                        st.success(f"✅ {recomendacao_gordon}")
                    elif recomendacao_gordon == "COMPRA PARCIAL":
                        st.warning(f"⚠️ {recomendacao_gordon}")
                    elif recomendacao_gordon == "NEUTRO":
                        st.info(f"⚖️ {recomendacao_gordon}")
                    else:
                        st.error(f"❌ {recomendacao_gordon}")
                else:
                    st.warning("Dados insuficientes para calcular o modelo Gordon")
            
            with col2:
                if dados['margem_gordon']:
                    fig_gordon = criar_velocimetro(dados['margem_gordon'], "MARGEM GORDON")
                    st.plotly_chart(fig_gordon, use_container_width=True)
                else:
                    st.info("Velocímetro indisponível")
        
        # ==================== ABA 4 - DCF ====================
        with tab4:
            st.markdown("### 📉 Valuation por Fluxo de Caixa Descontado (DCF)")
            
            # Verificar se há dados suficientes
            if dados['ebit'] and dados['ebit'] > 0 and dados['num_acoes'] and dados['num_acoes'] > 0:
                
                # Parâmetros ajustáveis
                st.markdown("#### ⚙️ Parâmetros do Modelo")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    crescimento_inicial = st.slider(
                        "Crescimento inicial (anos 1-3)", 
                        min_value=0.0, max_value=0.30, value=0.10, step=0.01,
                        format="%.0f%%", help="Taxa de crescimento do FCF nos primeiros 3 anos"
                    )
                    
                    crescimento_terminal = st.slider(
                        "Crescimento terminal (anos 4-5)", 
                        min_value=0.0, max_value=0.20, value=0.06, step=0.01,
                        format="%.0f%%", help="Taxa de crescimento do FCF nos anos 4 e 5"
                    )
                
                with col2:
                    wacc = st.slider(
                        "WACC (Custo de Capital)", 
                        min_value=0.05, max_value=0.20, value=0.11, step=0.01,
                        format="%.0f%%", help="Custo médio ponderado de capital"
                    )
                    
                    crescimento_perpetuo = st.slider(
                        "Crescimento perpétuo (g)", 
                        min_value=0.0, max_value=0.05, value=0.03, step=0.005,
                        format="%.1f%%", help="Taxa de crescimento para perpetuidade"
                    )
                
                with col3:
                    taxa_ir = st.slider(
                        "Alíquota de IR", 
                        min_value=0.20, max_value=0.40, value=0.34, step=0.01,
                        format="%.0f%%", help="Alíquota de imposto de renda"
                    )
                    
                    anos = st.selectbox(
                        "Anos de projeção", 
                        options=[3, 5, 7, 10], index=1,
                        help="Horizonte de projeção dos fluxos"
                    )
                
                # Calcular DCF com os parâmetros atuais
                valor_dcf = calcular_dcf(
                    ebit=dados['ebit'],
                    capex=dados['capex'],
                    depreciacao=dados['depreciacao'],
                    divida_liquida=dados['divida_liquida'],
                    num_acoes=dados['num_acoes'],
                    taxa_ir=taxa_ir,
                    crescimento_inicial=crescimento_inicial,
                    crescimento_terminal=crescimento_terminal,
                    wacc=wacc,
                    crescimento_perpetuo=crescimento_perpetuo,
                    anos=anos
                )
                
                margem_dcf = calcular_margem_seguranca(dados['cotacao'], valor_dcf)
                
                st.markdown("---")
                
                # Resultados
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.markdown("#### 📊 Resultado DCF")
                    if valor_dcf:
                        st.metric("Valor Justo", f"R$ {valor_dcf:.2f}")
                        st.metric("Cotação Atual", f"R$ {dados['cotacao']:.2f}")
                        st.metric("Margem de Segurança", f"{margem_dcf:+.1f}%")
                        recomendacao_dcf, mensagem_dcf = calcular_recomendacao(margem_dcf)
                        if recomendacao_dcf == "COMPRAR":
                            st.success(f"✅ {recomendacao_dcf} - {mensagem_dcf}")
                        elif recomendacao_dcf == "COMPRA PARCIAL":
                            st.warning(f"⚠️ {recomendacao_dcf} - {mensagem_dcf}")
                        elif recomendacao_dcf == "NEUTRO":
                            st.info(f"⚖️ {recomendacao_dcf} - {mensagem_dcf}")
                        else:
                            st.error(f"❌ {recomendacao_dcf} - {mensagem_dcf}")
                    else:
                        st.warning("Não foi possível calcular o DCF com os parâmetros atuais. Verifique se o FCF é positivo.")
                
                with col2:
                    if margem_dcf:
                        fig_dcf = criar_velocimetro(margem_dcf, "MARGEM DCF")
                        st.plotly_chart(fig_dcf, use_container_width=True)
                    else:
                        st.info("Velocímetro indisponível")
                
                # Dados utilizados
                with st.expander("📋 Dados utilizados no cálculo DCF"):
                    st.markdown(f"""
                    - **EBIT (Lucro Operacional):** R$ {dados['ebit']:,.2f}
                    - **CAPEX (Investimentos):** R$ {dados['capex']:,.2f}
                    - **Depreciação:** R$ {dados['depreciacao']:,.2f}
                    - **Dívida Líquida:** R$ {dados['divida_liquida']:,.2f}
                    - **Número de Ações:** {dados['num_acoes']:,.0f}
                    """)
                    
            else:
                st.warning("⚠️ Dados insuficientes para calcular o DCF. O Yahoo Finance não forneceu EBIT ou número de ações para esta empresa.")
                st.info("O modelo DCF funciona melhor para empresas com dados financeiros completos (ex: PETR4, VALE3, ITUB4).")
        
        st.markdown("---")
        
        # ==================== MÉDIA E RECOMENDAÇÃO FINAL ====================
        st.markdown("## 🎯 SÍNTESE DA ANÁLISE")
        
        # Coletar valores justos disponíveis
        valores_justos = []
        modelos_nomes = []
        
        if dados['valor_justo_graham']:
            valores_justos.append(dados['valor_justo_graham'])
            modelos_nomes.append("Graham")
        if dados['valor_justo_bazin']:
            valores_justos.append(dados['valor_justo_bazin'])
            modelos_nomes.append("Bazin")
        if dados['valor_justo_gordon']:
            valores_justos.append(dados['valor_justo_gordon'])
            modelos_nomes.append("Gordon")
        
        # Adicionar DCF se disponível
        if 'valor_dcf' in locals() and valor_dcf:
            valores_justos.append(valor_dcf)
            modelos_nomes.append("DCF")
        
        if valores_justos:
            media_valor_justo = sum(valores_justos) / len(valores_justos)
            margem_media = ((media_valor_justo - dados['cotacao']) / media_valor_justo) * 100
            recomendacao_final, mensagem = calcular_recomendacao(margem_media)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Média dos Modelos", f"R$ {media_valor_justo:.2f}")
                st.caption(f"Baseado em: {', '.join(modelos_nomes)}")
            with col2:
                st.metric("📈 Upside médio", f"{(media_valor_justo/dados['cotacao'] - 1)*100:+.1f}%")
            with col3:
                if recomendacao_final == "COMPRAR":
                    st.success(f"✅ RECOMENDAÇÃO: {recomendacao_final}")
                elif recomendacao_final == "COMPRA PARCIAL":
                    st.warning(f"⚠️ RECOMENDAÇÃO: {recomendacao_final}")
                elif recomendacao_final == "NEUTRO":
                    st.info(f"⚖️ RECOMENDAÇÃO: {recomendacao_final}")
                else:
                    st.error(f"❌ RECOMENDAÇÃO: {recomendacao_final}")
                st.caption(mensagem)
        else:
            st.warning("⚠️ Dados insuficientes para calcular a média dos modelos")
        
        # ==================== SOBRE A EMPRESA ====================
        st.markdown("---")
        st.markdown("## 🏢 SOBRE A EMPRESA")
        st.info(dados['resumo'])
        
        # ==================== INDICADORES ====================
        st.markdown("---")
        st.markdown("## 📊 INDICADORES FUNDAMENTALISTAS")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("LPA (Lucro por Ação)", f"R$ {dados['lpa']:.2f}" if dados['lpa'] else "N/D")
            st.metric("VPA (Valor Patrimonial)", f"R$ {dados['vpa']:.2f}" if dados['vpa'] else "N/D")
        
        with col2:
            if dados['pl']:
                cor_pl = "🟢" if dados['pl'] < 15 else "🔴"
                st.metric("P/L (Preço/Lucro)", f"{cor_pl} {dados['pl']:.1f}")
            else:
                st.metric("P/L (Preço/Lucro)", "N/D")
            
            if dados['roe']:
                cor_roe = "🟢" if dados['roe'] > 15 else "🟡"
                st.metric("ROE (Retorno s/ PL)", f"{cor_roe} {dados['roe']:.1f}%")
            else:
                st.metric("ROE (Retorno s/ PL)", "N/D")
        
        with col3:
            if dados['cotacao'] and dados['vpa'] and dados['vpa'] > 0:
                pvp = dados['cotacao'] / dados['vpa']
                cor_pvp = "🟢" if pvp < 1.5 else "🔴"
                st.metric("P/VP (Preço/Valor)", f"{cor_pvp} {pvp:.2f}")
            else:
                st.metric("P/VP (Preço/Valor)", "N/D")
            
            if dados['dividendos'] and dados['dividendos'] > 0:
                dy = (dados['dividendos'] / dados['cotacao']) * 100
                st.metric("Dividend Yield", f"{dy:.2f}%")
            else:
                st.metric("Dividend Yield", "N/D")
        
        # ==================== DISCLAIMER ====================
        st.markdown("---")
        st.caption("""
        ⚠️ **DISCLAIMER:** Este relatório é gerado automaticamente com base em dados públicos. 
        Os modelos de valuation (Graham, Bazin, Gordon e DCF) são ferramentas auxiliares de análise.
        O modelo DCF é altamente sensível às premissas adotadas (crescimento, WACC, perpetuidade).
        Não constitui recomendação de investimento personalizada. O investidor é o único responsável 
        por suas decisões de alocação. Rentabilidade passada não representa garantia de retornos futuros.
        """)
        
        # ==================== DOWNLOAD ====================
        st.markdown("---")
        
        # Preparar dados para download
        dados_download = {
            "Modelo": ["Graham", "Bazin", "Gordon"],
            "Valor Justo (R$)": [
                f"{dados['valor_justo_graham']:.2f}" if dados['valor_justo_graham'] else "N/D",
                f"{dados['valor_justo_bazin']:.2f}" if dados['valor_justo_bazin'] else "N/D",
                f"{dados['valor_justo_gordon']:.2f}" if dados['valor_justo_gordon'] else "N/D"
            ],
            "Margem (%)": [
                f"{dados['margem_graham']:.1f}" if dados['margem_graham'] else "N/D",
                f"{dados['margem_bazin']:.1f}" if dados['margem_bazin'] else "N/D",
                f"{dados['margem_gordon']:.1f}" if dados['margem_gordon'] else "N/D"
            ]
        }
        
        # Adicionar DCF se disponível
        if 'valor_dcf' in locals() and valor_dcf:
            dados_download["Modelo"].append("DCF")
            dados_download["Valor Justo (R$)"].append(f"{valor_dcf:.2f}")
            dados_download["Margem (%)"].append(f"{margem_dcf:.1f}" if margem_dcf else "N/D")
            dados_download["Modelo"].append("Média")
            dados_download["Valor Justo (R$)"].append(f"{media_valor_justo:.2f}" if valores_justos else "N/D")
            dados_download["Margem (%)"].append(f"{margem_media:.1f}" if valores_justos else "N/D")
        
        df = pd.DataFrame(dados_download)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Exportar para CSV",
            data=csv,
            file_name=f"multi_valuation_{dados['ticker']}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
    else:
        st.error(f"❌ Não foi possível encontrar dados para {ticker}")
        st.info("Verifique se o ticker está correto (ex: ITSA4, PETR4, VALE3)")

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #8A8D91; font-size: 12px;'>"
    "© Multi-Valuation System • Graham • Bazin • Gordon • DCF • Métodos de Benjamin Graham"
    "</div>",
    unsafe_allow_html=True
)