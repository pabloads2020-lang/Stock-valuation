import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import math
from deep_translator import GoogleTranslator
import requests
import time
import random

# ============================================================
# CACHE PERSISTENTE (evita múltiplas buscas)
# ============================================================

# Cache simples em memória
CACHE_TICKERS = {}
CACHE_TTL = timedelta(minutes=10)  # Cache por 10 minutos

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
    page_title="Multi-Valuation System",
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
    }
    .metric-value { font-size: 22px; font-weight: bold; color: #0B1C3F; }
    .metric-label { font-size: 11px; color: #4A5568; }
    .recomendacao-COMPRAR { background-color: #2E7D32; color: white; padding: 8px; border-radius: 8px; }
    .recomendacao-COMPRA-PARCIAL { background-color: #C9A03D; color: white; padding: 8px; border-radius: 8px; }
    .recomendacao-NEUTRO { background-color: #4A5568; color: white; padding: 8px; border-radius: 8px; }
    .recomendacao-EVITAR { background-color: #C62828; color: white; padding: 8px; border-radius: 8px; }
    h1, h2, h3 { color: #0B1C3F; }
    hr { margin: 20px 0; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# FUNÇÕES
# ============================================================

def calcular_graham(lpa, vpa):
    if lpa and vpa and lpa > 0 and vpa > 0:
        return math.sqrt(22.5 * lpa * vpa)
    return None

def calcular_bazin(dividendos):
    if dividendos and dividendos > 0:
        return (dividendos * 100) / 6
    return None

def calcular_gordon(dividendos, g=0.04, k=0.10):
    if dividendos and dividendos > 0:
        return (dividendos * (1 + g)) / (k - g)
    return None

def calcular_margem(cotacao, valor_justo):
    if cotacao and valor_justo and cotacao > 0:
        return ((valor_justo - cotacao) / valor_justo) * 100
    return None

def criar_velocimetro(margem, titulo):
    if margem is None:
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
    """Busca dados do Yahoo Finance com cache inteligente"""
    ticker_input = ticker_input.strip().upper()
    
    # Verifica cache primeiro
    cached = get_cache(ticker_input)
    if cached:
        return cached
    
    ticker_yahoo = f"{ticker_input}.SA"
    
    try:
        # Delay mínimo apenas para não sobrecarregar
        time.sleep(random.uniform(0.5, 1.0))
        
        stock = yf.Ticker(ticker_yahoo)
        info = stock.info
        
        if not info or len(info) < 10:
            return None
        
        cotacao = info.get('currentPrice') or info.get('regularMarketPrice')
        lpa = info.get('trailingEps')
        vpa = info.get('bookValue')
        pl = info.get('trailingPE')
        roe = info.get('returnOnEquity')
        nome = info.get('longName') or ticker_input
        dividendos = info.get('dividendRate', 0) or info.get('totalCashPerShare', 0)
        
        if roe:
            roe = roe * 100
        
        if not lpa and pl and cotacao:
            lpa = cotacao / pl if pl > 0 else None
        
        resultado = {
            "ticker": ticker_input,
            "nome": nome,
            "cotacao": cotacao,
            "lpa": lpa,
            "vpa": vpa,
            "pl": pl,
            "roe": roe,
            "dividendos": dividendos,
            "valor_graham": calcular_graham(lpa, vpa),
            "valor_bazin": calcular_bazin(dividendos),
            "valor_gordon": calcular_gordon(dividendos),
            "margem_graham": calcular_margem(cotacao, calcular_graham(lpa, vpa)),
            "margem_bazin": calcular_margem(cotacao, calcular_bazin(dividendos)),
            "margem_gordon": calcular_margem(cotacao, calcular_gordon(dividendos)),
            "setor": info.get('sector', 'N/D'),
            "segmento": info.get('industry', 'N/D')
        }
        
        # Salva no cache
        set_cache(ticker_input, resultado)
        return resultado
        
    except Exception as e:
        error_msg = str(e)
        if "rate" in error_msg.lower() or "429" in error_msg:
            st.warning("⚠️ Limite do Yahoo Finance. O cache vai ajudar nas próximas tentativas.")
        return None

# ============================================================
# INTERFACE
# ============================================================

st.title("📊 MULTI-VALUATION SYSTEM")
st.markdown("*Graham • Bazin • Gordon*")
st.markdown("---")

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/investment.png", width=80)
    ticker = st.text_input("📈 Ticker", value="ITSA4", help="Ex: ITSA4, PETR4, VALE3")
    
    col1, col2 = st.columns(2)
    with col1:
        analisar = st.button("🔍 ANALISAR", use_container_width=True)
    with col2:
        limpar = st.button("🗑️ LIMPAR", use_container_width=True)
    
    st.markdown("---")
    st.info("💡 Dados ficam em cache por 10 minutos. Consultas repetidas são instantâneas.")

if limpar:
    CACHE_TICKERS.clear()
    st.rerun()

if analisar:
    with st.spinner("📡 Buscando dados..."):
        dados = buscar_dados(ticker)
    
    if dados:
        st.markdown(f"## {dados['ticker']} - {dados['nome']}")
        st.caption(f"Setor: {dados['setor']} | Segmento: {dados['segmento']} | Cotação: R$ {dados['cotacao']:.2f}")
        st.markdown("---")
        
        # 3 cards lado a lado
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
                st.markdown("Dados insuficientes")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown("### 💰 BAZIN")
            if dados['valor_bazin']:
                st.markdown(f'<div class="metric-value">R$ {dados["valor_bazin"]:.2f}</div>', unsafe_allow_html=True)
                st.markdown(f'Margem: {dados["margem_bazin"]:+.1f}%')
                st.caption(f"Dividendo: R$ {dados['dividendos']:.2f}")
                if dados['margem_bazin'] >= 30:
                    st.markdown('<div class="recomendacao-COMPRAR">✅ COMPRAR</div>', unsafe_allow_html=True)
                elif dados['margem_bazin'] >= 15:
                    st.markdown('<div class="recomendacao-COMPRA-PARCIAL">⚠️ COMPRA PARCIAL</div>', unsafe_allow_html=True)
                elif dados['margem_bazin'] >= 0:
                    st.markdown('<div class="recomendacao-NEUTRO">⚖️ NEUTRO</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="recomendacao-EVITAR">❌ EVITAR</div>', unsafe_allow_html=True)
            else:
                st.markdown("Dados insuficientes")
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
                st.markdown("Dados insuficientes")
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Velocímetros lado a lado
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if dados['margem_graham']:
                st.plotly_chart(criar_velocimetro(dados['margem_graham'], "GRAHAM"), use_container_width=True)
        
        with col2:
            if dados['margem_bazin']:
                st.plotly_chart(criar_velocimetro(dados['margem_bazin'], "BAZIN"), use_container_width=True)
        
        with col3:
            if dados['margem_gordon']:
                st.plotly_chart(criar_velocimetro(dados['margem_gordon'], "GORDON"), use_container_width=True)
        
        st.markdown("---")
        
        # Indicadores
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
            st.metric("P/VP", f"{(dados['cotacao']/dados['vpa']):.2f}" if dados['vpa'] else "N/D")
        
        st.markdown("---")
        st.caption("⚠️ Fonte: Yahoo Finance. Cache ativo por 10 minutos.")
        
    else:
        st.error(f"❌ Erro ao buscar {ticker}")
        st.info("Aguarde 30 segundos e tente novamente. O Yahoo Finance tem limites temporários.")

st.markdown("---")
st.markdown("© Multi-Valuation System")