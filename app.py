import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import math
import time
import random

# ============================================================
# CACHE PERSISTENTE
# ============================================================

CACHE_TICKERS = {}
CACHE_TTL = timedelta(minutes=10)

def get_cache(ticker):
    if ticker in CACHE_TICKERS:
        data, timestamp = CACHE_TICKERS[ticker]
        if datetime.now() - timestamp < CACHE_TTL:
            return data
        else:
            del CACHE_TICKERS[ticker]
    return None

def set_cache(ticker, data):
    CACHE_TICKERS[ticker] = (data, datetime.now())

st.set_page_config(
    page_title="Multi-Valuation System - Análise Completa",
    page_icon="📊",
    layout="wide"
)

# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>
    .main { background-color: #F5F6F8; }
    .metric-card {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        text-align: center;
        border: 1px solid #E8E9EC;
        margin: 5px 0;
    }
    .metric-value { font-size: 24px; font-weight: bold; color: #0B1C3F; }
    .metric-label { font-size: 12px; color: #4A5568; font-weight: 500; }
    .metric-helper { font-size: 10px; color: #8A8D91; margin-top: 5px; }
    .good { color: #2E7D32; }
    .bad { color: #C62828; }
    .neutral { color: #C9A03D; }
    .recomendacao-COMPRAR { background-color: #2E7D32; color: white; padding: 8px; border-radius: 8px; text-align: center; font-weight: bold; }
    .recomendacao-COMPRA-PARCIAL { background-color: #C9A03D; color: white; padding: 8px; border-radius: 8px; text-align: center; font-weight: bold; }
    .recomendacao-NEUTRO { background-color: #4A5568; color: white; padding: 8px; border-radius: 8px; text-align: center; font-weight: bold; }
    .recomendacao-EVITAR { background-color: #C62828; color: white; padding: 8px; border-radius: 8px; text-align: center; font-weight: bold; }
    h1, h2, h3 { color: #0B1C3F; }
    hr { margin: 20px 0; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# FUNÇÕES DE VALUATION
# ============================================================

def safe_format(value, format_str="{:.2f}", default="N/D"):
    """Formata um valor com segurança, retornando default se for None"""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    try:
        return format_str.format(value)
    except:
        return default

def calcular_graham(lpa, vpa):
    if lpa and vpa and lpa > 0 and vpa > 0:
        return math.sqrt(22.5 * lpa * vpa)
    return None

def calcular_bazin(dividendos):
    if dividendos and dividendos > 0:
        return (dividendos * 100) / 6
    return None

def calcular_gordon(dividendos, g=0.04, k=0.10):
    if dividendos and dividendos > 0 and k > g:
        return (dividendos * (1 + g)) / (k - g)
    return None

def calcular_margem_seguranca(cotacao, valor_justo):
    if cotacao and valor_justo and cotacao > 0 and valor_justo > 0:
        return ((valor_justo - cotacao) / valor_justo) * 100
    return None

def classificar_indicador(valor, tipo):
    """Classifica o indicador como bom, neutro ou ruim"""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "neutral", "N/D"
    
    if tipo == "pl":
        if valor < 10:
            return "good", "Muito barato"
        elif valor < 15:
            return "good", "Barato"
        elif valor < 20:
            return "neutral", "Justo"
        elif valor < 30:
            return "bad", "Caro"
        else:
            return "bad", "Muito caro"
    
    elif tipo == "pvp":
        if valor < 1:
            return "good", "Abaixo do patrimônio"
        elif valor < 1.5:
            return "good", "Barato"
        elif valor < 2:
            return "neutral", "Justo"
        elif valor < 3:
            return "bad", "Caro"
        else:
            return "bad", "Muito caro"
    
    elif tipo == "roe":
        if valor > 20:
            return "good", "Excelente"
        elif valor > 15:
            return "good", "Bom"
        elif valor > 10:
            return "neutral", "Regular"
        elif valor > 5:
            return "bad", "Baixo"
        else:
            return "bad", "Muito baixo"
    
    elif tipo == "dy":
        if valor > 8:
            return "good", "Excelente"
        elif valor > 6:
            return "good", "Bom"
        elif valor > 4:
            return "neutral", "Regular"
        elif valor > 2:
            return "bad", "Baixo"
        else:
            return "bad", "Muito baixo"
    
    elif tipo == "divida_ebitda":
        if valor < 1:
            return "good", "Baixa dívida"
        elif valor < 2:
            return "good", "Controlada"
        elif valor < 3:
            return "neutral", "Atenção"
        elif valor < 4:
            return "bad", "Alta"
        else:
            return "bad", "Muito alta"
    
    elif tipo == "margem_liquida":
        if valor > 20:
            return "good", "Excelente"
        elif valor > 15:
            return "good", "Boa"
        elif valor > 10:
            return "neutral", "Regular"
        elif valor > 5:
            return "bad", "Baixa"
        else:
            return "bad", "Muito baixa"
    
    elif tipo == "liquidez":
        if valor > 2:
            return "good", "Folgada"
        elif valor > 1.5:
            return "good", "Confortável"
        elif valor > 1:
            return "neutral", "Adequada"
        else:
            return "bad", "Preocupante"
    
    return "neutral", ""

def criar_velocimetro(margem, titulo):
    if margem is None or (isinstance(margem, float) and math.isnan(margem)):
        margem = 0
    
    if margem < 0:
        cor = "#C62828"
    elif margem < 20:
        cor = "#C9A03D"
    else:
        cor = "#2E7D32"
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=margem,
        number={'suffix': "%", 'font': {'size': 28}, 'valueformat': '.1f'},
        title={'text': titulo, 'font': {'size': 10}},
        gauge={
            'axis': {'range': [-100, 100], 'tickvals': [-100, -50, 0, 50, 100]},
            'bar': {'color': "black", 'thickness': 0.03},
            'steps': [
                {'range': [-100, 0], 'color': "#C62828", 'thickness': 0.5},
                {'range': [0, 20], 'color': "#C9A03D", 'thickness': 0.5},
                {'range': [20, 100], 'color': "#2E7D32", 'thickness': 0.5}
            ],
            'threshold': {'line': {'color': cor, 'width': 3}, 'thickness': 0.6, 'value': margem}
        }
    ))
    fig.update_layout(height=200, margin=dict(l=30, r=30, t=40, b=20))
    return fig

def buscar_dados(ticker_input):
    """Busca dados completos do Yahoo Finance"""
    ticker_input = ticker_input.strip().upper()
    
    cached = get_cache(ticker_input)
    if cached:
        return cached
    
    ticker_yahoo = f"{ticker_input}.SA"
    
    try:
        time.sleep(random.uniform(0.5, 1.0))
        
        stock = yf.Ticker(ticker_yahoo)
        info = stock.info
        
        if not info or len(info) < 10:
            return None
        
        # Dados básicos
        cotacao = info.get('currentPrice') or info.get('regularMarketPrice')
        lpa = info.get('trailingEps')
        vpa = info.get('bookValue')
        nome = info.get('longName') or ticker_input
        
        # Múltiplos
        pl = info.get('trailingPE')
        pvp = cotacao / vpa if cotacao and vpa and vpa > 0 else None
        
        # Rentabilidade
        roe = info.get('returnOnEquity')
        if roe:
            roe = roe * 100
        
        roic = info.get('returnOnInvestedCapital')
        if roic:
            roic = roic * 100
        
        margem_liquida = info.get('profitMargins')
        if margem_liquida:
            margem_liquida = margem_liquida * 100
        
        margem_ebitda = info.get('ebitdaMargins')
        if margem_ebitda:
            margem_ebitda = margem_ebitda * 100
        
        # Dividendos
        dividendos = info.get('dividendRate', 0)
        if not dividendos or dividendos == 0:
            dividendos = info.get('totalCashPerShare', 0)
        
        dy = (dividendos / cotacao * 100) if cotacao and dividendos and dividendos > 0 else None
        
        # Endividamento
        divida_bruta = info.get('totalDebt', 0)
        caixa = info.get('totalCash', 0)
        divida_liquida = divida_bruta - caixa if divida_bruta and caixa else None
        
        ebitda = info.get('ebitda', 0)
        divida_ebitda = divida_liquida / ebitda if ebitda and ebitda > 0 and divida_liquida else None
        
        # Liquidez
        ativo_circulante = info.get('currentAssets', 0)
        passivo_circulante = info.get('currentLiabilities', 0)
        liquidez_corrente = ativo_circulante / passivo_circulante if passivo_circulante and passivo_circulante > 0 else None
        
        # Número de ações (para EV/EBITDA)
        num_acoes = info.get('sharesOutstanding', 0)
        
        # Valuation
        valor_graham = calcular_graham(lpa, vpa)
        valor_bazin = calcular_bazin(dividendos)
        valor_gordon = calcular_gordon(dividendos)
        
        margem_graham = calcular_margem_seguranca(cotacao, valor_graham)
        margem_bazin = calcular_margem_seguranca(cotacao, valor_bazin)
        margem_gordon = calcular_margem_seguranca(cotacao, valor_gordon)
        
        resultado = {
            "ticker": ticker_input,
            "nome": nome,
            "cotacao": cotacao,
            "lpa": lpa,
            "vpa": vpa,
            "pl": pl,
            "pvp": pvp,
            "roe": roe,
            "roic": roic,
            "dividendos": dividendos,
            "dy": dy,
            "ebitda": ebitda,
            "num_acoes": num_acoes,
            "divida_liquida": divida_liquida,
            "divida_ebitda": divida_ebitda,
            "margem_liquida": margem_liquida,
            "margem_ebitda": margem_ebitda,
            "liquidez_corrente": liquidez_corrente,
            "valor_graham": valor_graham,
            "valor_bazin": valor_bazin,
            "valor_gordon": valor_gordon,
            "margem_graham": margem_graham,
            "margem_bazin": margem_bazin,
            "margem_gordon": margem_gordon,
            "setor": info.get('sector', 'N/D'),
            "segmento": info.get('industry', 'N/D'),
            "site": info.get('website', 'N/D'),
        }
        
        set_cache(ticker_input, resultado)
        return resultado
        
    except Exception as e:
        return None

# ============================================================
# INTERFACE PRINCIPAL
# ============================================================

st.title("📊 MULTI-VALUATION SYSTEM")
st.markdown("*Graham • Bazin • Gordon • Análise Fundamentalista Completa*")
st.markdown("---")

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/investment.png", width=80)
    ticker = st.text_input("📈 Ticker da Ação", value="ITSA4", help="Ex: ITSA4, PETR4, VALE3, BBAS3")
    
    col1, col2 = st.columns(2)
    with col1:
        analisar = st.button("🔍 ANALISAR", use_container_width=True)
    with col2:
        limpar = st.button("🗑️ LIMPAR", use_container_width=True)
    
    st.markdown("---")
    st.markdown("### 📊 Indicadores disponíveis")
    st.markdown("""
    - P/L, P/VP, P/Ativo
    - ROE, ROIC
    - Margem Líquida, Margem EBITDA
    - Dividend Yield
    - Dívida Líquida/EBITDA
    - Liquidez Corrente
    - EV/EBITDA
    """)
    st.markdown("---")
    st.info("💡 Cache ativo por 10 minutos")

if limpar:
    CACHE_TICKERS.clear()
    st.rerun()

if analisar:
    with st.spinner("📡 Buscando dados..."):
        dados = buscar_dados(ticker)
    
    if dados:
        # Cabeçalho
        st.markdown(f"## {dados['ticker']} - {dados['nome']}")
        st.caption(f"Setor: {dados['setor']} | Segmento: {dados['segmento']} | Cotação: R$ {safe_format(dados['cotacao'], 'R$ {:.2f}')}")
        st.markdown("---")
        
        # ==================== VALUATION MODELS ====================
        st.markdown("## 📈 MODELOS DE VALUATION")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown("### 📘 GRAHAM")
            if dados['valor_graham']:
                st.markdown(f'<div class="metric-value">R$ {dados["valor_graham"]:.2f}</div>', unsafe_allow_html=True)
                st.markdown(f'Margem: {dados["margem_graham"]:+.1f}%')
                if dados['margem_graham'] >= 30:
                    st.markdown('<div class="recomendacao-COMPRAR">✅ COMPRAR</div>', unsafe_allow_html=True)
                elif dados['margem_graham'] >= 15:
                    st.markdown('<div class="recomendacao-COMPRA-PARCIAL">⚠️ COMPRA PARCIAL</div>', unsafe_allow_html=True)
                elif dados['margem_graham'] >= 0:
                    st.markdown('<div class="recomendacao-NEUTRO">⚖️ NEUTRO</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="recomendacao-EVITAR">❌ EVITAR</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="metric-value">Dados insuficientes</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown("### 💰 BAZIN")
            if dados['valor_bazin']:
                st.markdown(f'<div class="metric-value">R$ {dados["valor_bazin"]:.2f}</div>', unsafe_allow_html=True)
                st.markdown(f'Margem: {dados["margem_bazin"]:+.1f}%')
                st.caption(f"Dividendo: R$ {dados['dividendos']:.2f}" if dados['dividendos'] else "Sem dividendos")
                if dados['margem_bazin'] >= 30:
                    st.markdown('<div class="recomendacao-COMPRAR">✅ COMPRAR</div>', unsafe_allow_html=True)
                elif dados['margem_bazin'] >= 15:
                    st.markdown('<div class="recomendacao-COMPRA-PARCIAL">⚠️ COMPRA PARCIAL</div>', unsafe_allow_html=True)
                elif dados['margem_bazin'] >= 0:
                    st.markdown('<div class="recomendacao-NEUTRO">⚖️ NEUTRO</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="recomendacao-EVITAR">❌ EVITAR</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="metric-value">Dados insuficientes</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown("### 📈 GORDON")
            if dados['valor_gordon']:
                st.markdown(f'<div class="metric-value">R$ {dados["valor_gordon"]:.2f}</div>', unsafe_allow_html=True)
                st.markdown(f'Margem: {dados["margem_gordon"]:+.1f}%')
                st.caption("g=4% | k=10%")
                if dados['margem_gordon'] >= 30:
                    st.markdown('<div class="recomendacao-COMPRAR">✅ COMPRAR</div>', unsafe_allow_html=True)
                elif dados['margem_gordon'] >= 15:
                    st.markdown('<div class="recomendacao-COMPRA-PARCIAL">⚠️ COMPRA PARCIAL</div>', unsafe_allow_html=True)
                elif dados['margem_gordon'] >= 0:
                    st.markdown('<div class="recomendacao-NEUTRO">⚖️ NEUTRO</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="recomendacao-EVITAR">❌ EVITAR</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="metric-value">Dados insuficientes</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # ==================== VELOCÍMETROS ====================
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if dados['margem_graham']:
                st.plotly_chart(criar_velocimetro(dados['margem_graham'], "MARGEM GRAHAM"), use_container_width=True)
        
        with col2:
            if dados['margem_bazin']:
                st.plotly_chart(criar_velocimetro(dados['margem_bazin'], "MARGEM BAZIN"), use_container_width=True)
        
        with col3:
            if dados['margem_gordon']:
                st.plotly_chart(criar_velocimetro(dados['margem_gordon'], "MARGEM GORDON"), use_container_width=True)
        
        st.markdown("---")
        
        # ==================== MÚLTIPLOS ====================
        st.markdown("## 💹 MÚLTIPLOS DE MERCADO")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if dados['pl']:
                classe, texto = classificar_indicador(dados['pl'], "pl")
                cor = classe
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">P/L (Preço/Lucro)</div>
                    <div class="metric-value">{dados['pl']:.1f}</div>
                    <div class="metric-helper {cor}">{texto}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">P/L (Preço/Lucro)</div>
                    <div class="metric-value">N/D</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            if dados['pvp']:
                classe, texto = classificar_indicador(dados['pvp'], "pvp")
                cor = classe
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">P/VP (Preço/Valor Patrimonial)</div>
                    <div class="metric-value">{dados['pvp']:.2f}</div>
                    <div class="metric-helper {cor}">{texto}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">P/VP</div>
                    <div class="metric-value">N/D</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col3:
            if dados['vpa'] and dados['cotacao']:
                p_ativo = dados['cotacao'] / dados['vpa']
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">P/Ativo</div>
                    <div class="metric-value">{p_ativo:.2f}</div>
                    <div class="metric-helper">Valor de mercado / Ativo</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">P/Ativo</div>
                    <div class="metric-value">N/D</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col4:
            if dados['ebitda'] and dados['cotacao'] and dados['num_acoes']:
                valor_mercado = dados['cotacao'] * dados['num_acoes']
                divida_liquida = dados['divida_liquida'] if dados['divida_liquida'] else 0
                ev = valor_mercado + divida_liquida
                ev_ebitda = ev / dados['ebitda']
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">EV/EBITDA</div>
                    <div class="metric-value">{ev_ebitda:.1f}</div>
                    <div class="metric-helper">Valor da empresa / EBITDA</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">EV/EBITDA</div>
                    <div class="metric-value">N/D</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # ==================== RENTABILIDADE ====================
        st.markdown("## 📊 RENTABILIDADE")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if dados['roe']:
                classe, texto = classificar_indicador(dados['roe'], "roe")
                cor = classe
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">ROE (Retorno s/ PL)</div>
                    <div class="metric-value">{dados['roe']:.1f}%</div>
                    <div class="metric-helper {cor}">{texto}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">ROE</div>
                    <div class="metric-value">N/D</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            if dados['roic']:
                classe, texto = classificar_indicador(dados['roic'], "roe")
                cor = classe
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">ROIC (Retorno s/ Capital)</div>
                    <div class="metric-value">{dados['roic']:.1f}%</div>
                    <div class="metric-helper {cor}">{texto}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">ROIC</div>
                    <div class="metric-value">N/D</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col3:
            if dados['margem_liquida']:
                classe, texto = classificar_indicador(dados['margem_liquida'], "margem_liquida")
                cor = classe
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Margem Líquida</div>
                    <div class="metric-value">{dados['margem_liquida']:.1f}%</div>
                    <div class="metric-helper {cor}">{texto}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">Margem Líquida</div>
                    <div class="metric-value">N/D</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col4:
            if dados['margem_ebitda']:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Margem EBITDA</div>
                    <div class="metric-value">{dados['margem_ebitda']:.1f}%</div>
                    <div class="metric-helper">Geração de caixa operacional</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">Margem EBITDA</div>
                    <div class="metric-value">N/D</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # ==================== DIVIDENDOS E ENDIVIDAMENTO ====================
        st.markdown("## 💰 DIVIDENDOS E SAÚDE FINANCEIRA")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if dados['dy']:
                classe, texto = classificar_indicador(dados['dy'], "dy")
                cor = classe
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Dividend Yield</div>
                    <div class="metric-value">{dados['dy']:.2f}%</div>
                    <div class="metric-helper {cor}">{texto}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">Dividend Yield</div>
                    <div class="metric-value">N/D</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            if dados['divida_ebitda']:
                classe, texto = classificar_indicador(dados['divida_ebitda'], "divida_ebitda")
                cor = classe
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Dívida Líquida / EBITDA</div>
                    <div class="metric-value">{dados['divida_ebitda']:.1f}x</div>
                    <div class="metric-helper {cor}">{texto}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">Dívida Líquida / EBITDA</div>
                    <div class="metric-value">N/D</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col3:
            if dados['liquidez_corrente']:
                classe, texto = classificar_indicador(dados['liquidez_corrente'], "liquidez")
                cor = classe
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Liquidez Corrente</div>
                    <div class="metric-value">{dados['liquidez_corrente']:.2f}</div>
                    <div class="metric-helper {cor}">{texto}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">Liquidez Corrente</div>
                    <div class="metric-value">N/D</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col4:
            if dados['divida_liquida']:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Dívida Líquida</div>
                    <div class="metric-value">R$ {dados['divida_liquida']/1e9:.2f}B</div>
                    <div class="metric-helper">Dívida Bruta - Caixa</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="metric-card">
                    <div class="metric-label">Dívida Líquida</div>
                    <div class="metric-value">N/D</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # ==================== RESUMO EXECUTIVO ====================
        st.markdown("## 📋 RESUMO EXECUTIVO")
        
        # Calcular pontuação geral
        pontuacao = 0
        total_indicadores = 0
        
        for ind, tipo in [('pl', 'pl'), ('pvp', 'pvp'), ('roe', 'roe'), ('dy', 'dy'), ('divida_ebitda', 'divida_ebitda')]:
            valor = dados.get(ind)
            if valor and not (isinstance(valor, float) and math.isnan(valor)):
                total_indicadores += 1
                classe, _ = classificar_indicador(valor, tipo)
                if classe == 'good':
                    pontuacao += 1
                elif classe == 'bad':
                    pontuacao -= 1
        
        if total_indicadores > 0:
            score_percent = (pontuacao / total_indicadores) * 100
            
            if score_percent >= 50:
                st.success(f"### ✅ QUALIDADE: BOA ({score_percent:.0f}%)")
                st.markdown("A empresa apresenta indicadores fundamentalistas sólidos na maioria das métricas analisadas.")
            elif score_percent >= 0:
                st.warning(f"### ⚠️ QUALIDADE: REGULAR ({score_percent:.0f}%)")
                st.markdown("A empresa tem indicadores mistos. Recomenda-se análise mais aprofundada antes de investir.")
            else:
                st.error(f"### ❌ QUALIDADE: FRACA ({score_percent:.0f}%)")
                st.markdown("A maioria dos indicadores está abaixo do ideal. Empresa com riscos fundamentalistas.")
        else:
            st.info("Dados insuficientes para calcular a pontuação de qualidade.")
        
        # ==================== DISCLAIMER ====================
        st.markdown("---")
        st.caption("""
        ⚠️ **DISCLAIMER:** Este relatório é gerado automaticamente com base em dados públicos do Yahoo Finance.
        Os indicadores e valuations são ferramentas auxiliares de análise. Não constitui recomendação de investimento.
        O investidor é o único responsável por suas decisões de alocação.
        """)
        
    else:
        st.error(f"❌ Não foi possível encontrar dados para {ticker}")
        st.info("Verifique o ticker e tente novamente. Exemplos: ITSA4, PETR4, VALE3, BBAS3")

st.markdown("---")
st.markdown("© Multi-Valuation System • Dados: Yahoo Finance")