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
# CONFIGURAÇÃO DE SESSÃO COM RETRY E BACKOFF AGRESSIVO
# ============================================================

def criar_sessao_com_retry():
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=3,  # AUMENTADO: 3s, 6s, 12s, 24s, 48s
        status_forcelist=[429, 500, 502, 503, 504, 400, 401, 403],
        allowed_methods=["GET", "POST"],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        'Cache-Control': 'no-cache'
    })
    return session

# Cache global com TTL (time to live)
CACHE_TICKERS = {}
CACHE_TTL = 300  # Cache por 5 minutos

def cache_valido(timestamp):
    return (datetime.now() - timestamp).seconds < CACHE_TTL

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
    h1, h2, h3 { color: #0B1C3F; }
    hr {
        margin: 20px 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #C9A03D, transparent);
    }
    .warning-box {
        background-color: #FFF3CD;
        border-left: 4px solid #FFC107;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# FUNÇÕES DE VALUATION
# ============================================================

def calcular_graham(lpa, vpa):
    if lpa and vpa and lpa > 0 and vpa > 0:
        return math.sqrt(22.5 * lpa * vpa)
    return None

def calcular_bazin(dividendos_anuais):
    if dividendos_anuais and dividendos_anuais > 0:
        return (dividendos_anuais * 100) / 6
    return None

def calcular_gordon(dividendos_anuais, taxa_crescimento=0.04, taxa_desconto=0.10):
    if dividendos_anuais and dividendos_anuais > 0:
        return (dividendos_anuais * (1 + taxa_crescimento)) / (taxa_desconto - taxa_crescimento)
    return None

def calcular_dcf(ebit, capex, depreciacao, divida_liquida, num_acoes, 
                 taxa_ir=0.34, crescimento_inicial=0.10, crescimento_terminal=0.06,
                 wacc=0.11, crescimento_perpetuo=0.03, anos=5):
    if not ebit or ebit <= 0:
        return None
    
    fcf_atual = ebit * (1 - taxa_ir) + depreciacao - capex
    
    if fcf_atual <= 0:
        return None
    
    fluxos_presentes = []
    for ano in range(1, anos + 1):
        if ano <= 3:
            taxa = crescimento_inicial
        else:
            taxa = crescimento_terminal
        
        fcf_ano = fcf_atual * (1 + taxa) ** ano
        fcf_presente = fcf_ano / ((1 + wacc) ** ano)
        fluxos_presentes.append(fcf_presente)
    
    valor_presente_fluxos = sum(fluxos_presentes)
    
    fcf_ultimo = fcf_atual * (1 + crescimento_terminal) ** anos
    valor_residual = fcf_ultimo * (1 + crescimento_perpetuo) / (wacc - crescimento_perpetuo)
    valor_presente_residual = valor_residual / ((1 + wacc) ** anos)
    
    valor_empresa = valor_presente_fluxos + valor_presente_residual
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
# VELOCÍMETRO
# ============================================================

def criar_velocimetro(margem, titulo):
    if margem is None:
        margem = 0
    
    if margem < 0:
        cor_marcador = "#C62828"
    elif margem < 20:
        cor_marcador = "#C9A03D"
    else:
        cor_marcador = "#2E7D32"
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=margem,
        number={'suffix': "%", 'font': {'size': 30, 'color': "black"}, 'valueformat': '.1f'},
        title={'text': titulo, 'font': {'size': 11}},
        gauge={
            'axis': {'range': [-100, 100], 'tickvals': [-100, -50, 0, 50, 100]},
            'bar': {'color': "black", 'thickness': 0.03},
            'bgcolor': "white",
            'steps': [
                {'range': [-100, 0], 'color': "#C62828", 'thickness': 0.5},
                {'range': [0, 20], 'color': "#C9A03D", 'thickness': 0.5},
                {'range': [20, 100], 'color': "#2E7D32", 'thickness': 0.5}
            ],
            'threshold': {'line': {'color': cor_marcador, 'width': 3}, 'thickness': 0.6, 'value': margem}
        }
    ))
    fig.update_layout(height=220, margin=dict(l=30, r=30, t=50, b=20), paper_bgcolor="white")
    return fig

# ============================================================
# BUSCA DE DADOS COM YAHOO FINANCE (OTIMIZADA)
# ============================================================

def buscar_resumo_status_invest(ticker):
    ticker_clean = ticker.upper().replace('.SA', '')
    cache_key = f"resumo_{ticker_clean}"
    
    if cache_key in CACHE_TICKERS:
        cache_time, cache_value = CACHE_TICKERS[cache_key]
        if cache_valido(cache_time):
            return cache_value
    
    try:
        time.sleep(random.uniform(2, 4))
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        url = f"https://statusinvest.com.br/acao/companyinfo?code={ticker_clean}"
        session = criar_sessao_com_retry()
        response = session.get(url, headers=headers, timeout=20)
        
        if response.status_code == 200:
            dados = response.json()
            resumo = dados.get('description') or dados.get('businessDescription')
            if resumo and len(resumo) > 50:
                CACHE_TICKERS[cache_key] = (datetime.now(), resumo)
                return resumo
    except:
        pass
    
    CACHE_TICKERS[cache_key] = (datetime.now(), None)
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
    
    # Verificar cache válido
    if ticker_input in CACHE_TICKERS:
        cache_time, cache_value = CACHE_TICKERS[ticker_input]
        if cache_valido(cache_time):
            return cache_value
    
    ticker_yahoo = f"{ticker_input}.SA" if not ticker_input.endswith('.SA') else ticker_input
    
    # Delay inicial maior
    time.sleep(random.uniform(2, 4))
    
    try:
        stock = yf.Ticker(ticker_yahoo)
        
        # Múltiplas tentativas com backoff
        info = None
        for tentativa in range(5):
            try:
                info = stock.info
                if info and len(info) > 5:
                    break
            except Exception as e:
                error_msg = str(e).lower()
                if "rate" in error_msg or "429" in error_msg:
                    wait_time = (tentativa + 1) * 5
                    st.warning(f"⏳ Yahoo Finance com limite. Aguardando {wait_time}s... (tentativa {tentativa+1}/5)")
                    time.sleep(wait_time)
                elif tentativa == 4:
                    raise
                else:
                    time.sleep(3)
        
        if not info or len(info) <= 5:
            CACHE_TICKERS[ticker_input] = (datetime.now(), None)
            return None
        
        cotacao = info.get('currentPrice') or info.get('regularMarketPrice')
        lpa = info.get('trailingEps')
        vpa = info.get('bookValue')
        pl = info.get('trailingPE')
        roe = info.get('returnOnEquity')
        nome = info.get('longName') or ticker_input
        
        dividendos = info.get('dividendRate', 0)
        if not dividendos or dividendos == 0:
            dividendos = info.get('totalCashPerShare', 0)
        
        # Dados para DCF
        ebit = info.get('ebitda') or info.get('operatingIncome')
        capex = info.get('capitalExpenditures', 0)
        depreciacao = info.get('depreciation', ebit * 0.1 if ebit else 0)
        divida_bruta = info.get('totalDebt', 0)
        caixa = info.get('totalCash', 0)
        divida_liquida = divida_bruta - caixa
        num_acoes = info.get('sharesOutstanding', 0)
        
        if capex == 0 and ebit:
            capex = ebit * 0.15
        
        if roe:
            roe = roe * 100
        
        if not lpa and pl and cotacao:
            lpa = cotacao / pl if pl > 0 else None
        
        valor_justo_graham = calcular_graham(lpa, vpa)
        valor_justo_bazin = calcular_bazin(dividendos)
        valor_justo_gordon = calcular_gordon(dividendos)
        
        margem_graham = calcular_margem_seguranca(cotacao, valor_justo_graham)
        margem_bazin = calcular_margem_seguranca(cotacao, valor_justo_bazin)
        margem_gordon = calcular_margem_seguranca(cotacao, valor_justo_gordon)
        
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
        
        CACHE_TICKERS[ticker_input] = (datetime.now(), resultado)
        return resultado
        
    except Exception as e:
        error_msg = str(e)
        if "rate" in error_msg.lower() or "429" in error_msg:
            st.error("⏳ Yahoo Finance está com limite de requisições. Aguarde 1-2 minutos e tente novamente.")
        else:
            st.error(f"Erro ao buscar dados: {error_msg[:100]}")
        CACHE_TICKERS[ticker_input] = (datetime.now(), None)
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
    st.markdown("### ⚠️ Importante")
    st.info("O Yahoo Finance tem limites de requisições. Se der erro, aguarde 1-2 minutos e tente novamente.")
    st.markdown("---")
    st.markdown("### 📋 Exemplos")
    st.markdown("- ITSA4, PETR4, VALE3, BBAS3, WEGE3")

if limpar:
    CACHE_TICKERS.clear()
    st.rerun()

if analisar:
    with st.spinner("🔄 Buscando dados... (pode levar 10-15 segundos)"):
        dados = buscar_dados(ticker)
    
    if dados:
        st.markdown(f"## {dados['ticker']} - {dados['nome']}")
        st.caption(f"Setor: {dados['setor']} | Segmento: {dados['segmento']} | Cotação: R$ {dados['cotacao']:.2f}")
        st.markdown("---")
        
        tab1, tab2, tab3, tab4 = st.tabs(["📘 GRAHAM", "💰 BAZIN", "📈 GORDON", "📉 DCF"])
        
        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Valor Justo Graham", f"R$ {dados['valor_justo_graham']:.2f}" if dados['valor_justo_graham'] else "N/D")
                st.metric("Margem", f"{dados['margem_graham']:+.1f}%" if dados['margem_graham'] else "N/D")
                rec, _ = calcular_recomendacao(dados['margem_graham'])
                if rec == "COMPRAR":
                    st.success(f"✅ {rec}")
                elif rec == "COMPRA PARCIAL":
                    st.warning(f"⚠️ {rec}")
                elif rec == "NEUTRO":
                    st.info(f"⚖️ {rec}")
                else:
                    st.error(f"❌ {rec}")
            with col2:
                if dados['margem_graham']:
                    st.plotly_chart(criar_velocimetro(dados['margem_graham'], "GRAHAM"), use_container_width=True)
        
        with tab2:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Valor Justo Bazin", f"R$ {dados['valor_justo_bazin']:.2f}" if dados['valor_justo_bazin'] else "N/D")
                st.metric("Dividendo Anual", f"R$ {dados['dividendos']:.2f}" if dados['dividendos'] else "N/D")
                st.metric("Margem", f"{dados['margem_bazin']:+.1f}%" if dados['margem_bazin'] else "N/D")
                rec, _ = calcular_recomendacao(dados['margem_bazin'])
                if rec == "COMPRAR":
                    st.success(f"✅ {rec}")
                elif rec == "COMPRA PARCIAL":
                    st.warning(f"⚠️ {rec}")
                elif rec == "NEUTRO":
                    st.info(f"⚖️ {rec}")
                else:
                    st.error(f"❌ {rec}")
            with col2:
                if dados['margem_bazin']:
                    st.plotly_chart(criar_velocimetro(dados['margem_bazin'], "BAZIN"), use_container_width=True)
        
        with tab3:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Valor Justo Gordon", f"R$ {dados['valor_justo_gordon']:.2f}" if dados['valor_justo_gordon'] else "N/D")
                st.metric("Dividendo Anual", f"R$ {dados['dividendos']:.2f}" if dados['dividendos'] else "N/D")
                st.metric("Margem", f"{dados['margem_gordon']:+.1f}%" if dados['margem_gordon'] else "N/D")
                rec, _ = calcular_recomendacao(dados['margem_gordon'])
                if rec == "COMPRAR":
                    st.success(f"✅ {rec}")
                elif rec == "COMPRA PARCIAL":
                    st.warning(f"⚠️ {rec}")
                elif rec == "NEUTRO":
                    st.info(f"⚖️ {rec}")
                else:
                    st.error(f"❌ {rec}")
            with col2:
                if dados['margem_gordon']:
                    st.plotly_chart(criar_velocimetro(dados['margem_gordon'], "GORDON"), use_container_width=True)
        
        with tab4:
            st.markdown("### 📉 Valuation DCF")
            if dados['ebit'] and dados['ebit'] > 0 and dados['num_acoes'] and dados['num_acoes'] > 0:
                col1, col2 = st.columns(2)
                with col1:
                    crescimento_inicial = st.slider("Crescimento inicial", 0.0, 0.30, 0.10, 0.01, format="%.0f%%")
                    crescimento_terminal = st.slider("Crescimento terminal", 0.0, 0.20, 0.06, 0.01, format="%.0f%%")
                    wacc = st.slider("WACC", 0.05, 0.20, 0.11, 0.01, format="%.0f%%")
                
                with col2:
                    crescimento_perpetuo = st.slider("Crescimento perpétuo", 0.0, 0.05, 0.03, 0.005, format="%.1f%%")
                    taxa_ir = st.slider("Alíquota IR", 0.20, 0.40, 0.34, 0.01, format="%.0f%%")
                    anos = st.selectbox("Anos de projeção", [3, 5, 7, 10], index=1)
                
                valor_dcf = calcular_dcf(
                    ebit=dados['ebit'], capex=dados['capex'], depreciacao=dados['depreciacao'],
                    divida_liquida=dados['divida_liquida'], num_acoes=dados['num_acoes'],
                    taxa_ir=taxa_ir, crescimento_inicial=crescimento_inicial,
                    crescimento_terminal=crescimento_terminal, wacc=wacc,
                    crescimento_perpetuo=crescimento_perpetuo, anos=anos
                )
                
                margem_dcf = calcular_margem_seguranca(dados['cotacao'], valor_dcf)
                
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Valor Justo DCF", f"R$ {valor_dcf:.2f}" if valor_dcf else "N/D")
                    st.metric("Margem", f"{margem_dcf:+.1f}%" if margem_dcf else "N/D")
                    rec, _ = calcular_recomendacao(margem_dcf)
                    if rec == "COMPRAR":
                        st.success(f"✅ {rec}")
                    elif rec == "COMPRA PARCIAL":
                        st.warning(f"⚠️ {rec}")
                    elif rec == "NEUTRO":
                        st.info(f"⚖️ {rec}")
                    else:
                        st.error(f"❌ {rec}")
                with col2:
                    if margem_dcf:
                        st.plotly_chart(criar_velocimetro(margem_dcf, "DCF"), use_container_width=True)
            else:
                st.warning("Dados insuficientes para o modelo DCF")
        
        st.markdown("---")
        st.markdown("## 🏢 SOBRE A EMPRESA")
        st.info(dados['resumo'])
        
        st.markdown("---")
        st.markdown("## 📊 INDICADORES")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("LPA", f"R$ {dados['lpa']:.2f}" if dados['lpa'] else "N/D")
            st.metric("VPA", f"R$ {dados['vpa']:.2f}" if dados['vpa'] else "N/D")
        with col2:
            st.metric("P/L", f"{dados['pl']:.1f}" if dados['pl'] else "N/D")
            st.metric("ROE", f"{dados['roe']:.1f}%" if dados['roe'] else "N/D")
        with col3:
            if dados['dividendos'] and dados['cotacao']:
                dy = (dados['dividendos'] / dados['cotacao']) * 100
                st.metric("Dividend Yield", f"{dy:.2f}%")
            st.metric("P/VP", f"{(dados['cotacao']/dados['vpa']):.2f}" if dados['vpa'] and dados['cotacao'] else "N/D")
        
        st.markdown("---")
        st.caption("⚠️ Fonte: Yahoo Finance. Limite de requisições pode ocorrer. Aguarde e tente novamente.")
        
    else:
        st.error(f"❌ Não foi possível encontrar dados para {ticker}")
        st.info("Verifique o ticker e tente novamente em 1-2 minutos.")

st.markdown("---")
st.markdown("© Multi-Valuation System • Yahoo Finance API")