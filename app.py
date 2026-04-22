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
    page_title="Multi-Valuation - Graham, Bazin & Gordon",
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
        
        # Dividendos (para Bazin e Gordon)
        dividendos = info.get('dividendRate', 0)
        if not dividendos or dividendos == 0:
            dividendos = info.get('totalCashPerShare', 0)
        
        if roe:
            roe = roe * 100
        
        if not lpa and pl and cotacao:
            lpa = cotacao / pl if pl > 0 else None
        
        # Cálculo dos 3 modelos
        valor_justo_graham = calcular_graham(lpa, vpa)
        valor_justo_bazin = calcular_bazin(dividendos)
        valor_justo_gordon = calcular_gordon(dividendos)
        
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
st.markdown("*Graham • Bazin • Gordon*")
st.markdown("---")

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/investment.png", width=80)
    st.markdown("## 🔍 Análise de Investimentos")
    st.markdown("### 3 Modelos de Valuation")
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
    st.markdown("---")
    st.markdown("### 📋 Exemplos")
    st.markdown("- ITSA4 (Itaúsa)")
    st.markdown("- PETR4 (Petrobras)")
    st.markdown("- VALE3 (Vale)")
    st.markdown("- BBAS3 (Banco do Brasil)")
    st.markdown("---")
    st.markdown("### ℹ️ Sobre")
    st.markdown("Valuation baseada em 3 metodologias")
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
        
        # ==================== CARDS DOS 3 MODELOS ====================
        col1, col2, col3 = st.columns(3)
        
        # Card Graham
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown('<div class="model-title">📘 BENJAMIN GRAHAM</div>', unsafe_allow_html=True)
            if dados['valor_justo_graham']:
                st.markdown(f'<div class="metric-value">R$ {dados["valor_justo_graham"]:.2f}</div>', unsafe_allow_html=True)
                recomendacao, _ = calcular_recomendacao(dados['margem_graham'])
                cor_classe = f"recomendacao-{recomendacao}"
                st.markdown(f'<div class="recomendacao {cor_classe}">{recomendacao}</div>', unsafe_allow_html=True)
                st.caption(f"Margem: {dados['margem_graham']:+.1f}%")
            else:
                st.markdown('<div class="metric-value">Dados insuficientes</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Card Bazin
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown('<div class="model-title">💰 BAZIN (6%)</div>', unsafe_allow_html=True)
            if dados['valor_justo_bazin']:
                st.markdown(f'<div class="metric-value">R$ {dados["valor_justo_bazin"]:.2f}</div>', unsafe_allow_html=True)
                recomendacao, _ = calcular_recomendacao(dados['margem_bazin'])
                cor_classe = f"recomendacao-{recomendacao}"
                st.markdown(f'<div class="recomendacao {cor_classe}">{recomendacao}</div>', unsafe_allow_html=True)
                st.caption(f"Dividendo anual: R$ {dados['dividendos']:.2f}" if dados['dividendos'] else "Sem dividendos")
            else:
                st.markdown('<div class="metric-value">Dados insuficientes</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Card Gordon
        with col3:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown('<div class="model-title">📈 GORDON (GGM)</div>', unsafe_allow_html=True)
            if dados['valor_justo_gordon']:
                st.markdown(f'<div class="metric-value">R$ {dados["valor_justo_gordon"]:.2f}</div>', unsafe_allow_html=True)
                recomendacao, _ = calcular_recomendacao(dados['margem_gordon'])
                cor_classe = f"recomendacao-{recomendacao}"
                st.markdown(f'<div class="recomendacao {cor_classe}">{recomendacao}</div>', unsafe_allow_html=True)
                st.caption("Crescimento: 4% | Retorno: 10%")
            else:
                st.markdown('<div class="metric-value">Dados insuficientes</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # ==================== VELOCÍMETROS ====================
        st.markdown("## 📊 MARGEM DE SEGURANÇA")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            fig_graham = criar_velocimetro(dados['margem_graham'], "GRAHAM")
            st.plotly_chart(fig_graham, use_container_width=True)
        
        with col2:
            fig_bazin = criar_velocimetro(dados['margem_bazin'], "BAZIN")
            st.plotly_chart(fig_bazin, use_container_width=True)
        
        with col3:
            fig_gordon = criar_velocimetro(dados['margem_gordon'], "GORDON")
            st.plotly_chart(fig_gordon, use_container_width=True)
        
        st.markdown("---")
        
        # ==================== MÉDIA E RECOMENDAÇÃO FINAL ====================
        st.markdown("## 🎯 SÍNTESE DA ANÁLISE")
        
        # Calcula média dos valores justos (ignorando None)
        valores_validos = []
        if dados['valor_justo_graham']:
            valores_validos.append(dados['valor_justo_graham'])
        if dados['valor_justo_bazin']:
            valores_validos.append(dados['valor_justo_bazin'])
        if dados['valor_justo_gordon']:
            valores_validos.append(dados['valor_justo_gordon'])
        
        if valores_validos:
            media_valor_justo = sum(valores_validos) / len(valores_validos)
            margem_media = ((media_valor_justo - dados['cotacao']) / media_valor_justo) * 100
            recomendacao_final, mensagem = calcular_recomendacao(margem_media)
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.metric("📊 Média dos 3 Modelos", f"R$ {media_valor_justo:.2f}")
                st.metric("📈 Upside médio", f"{(media_valor_justo/dados['cotacao'] - 1)*100:+.1f}%")
            with col2:
                cor_classe = f"recomendacao-{recomendacao_final}"
                st.markdown(f'<div class="recomendacao {cor_classe}" style="padding:20px;">'
                           f'<h2 style="margin:0;">{recomendacao_final}</h2>'
                           f'<p style="margin:5px 0 0 0;">{mensagem}</p></div>', unsafe_allow_html=True)
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
        Os modelos de valuation (Graham, Bazin e Gordon) são ferramentas auxiliares de análise.
        Não constitui recomendação de investimento personalizada. O investidor é o único responsável 
        por suas decisões de alocação. Rentabilidade passada não representa garantia de retornos futuros.
        """)
        
        # ==================== DOWNLOAD ====================
        st.markdown("---")
        
        df = pd.DataFrame({
            "Modelo": ["Graham", "Bazin", "Gordon", "Média"],
            "Valor Justo (R$)": [
                f"{dados['valor_justo_graham']:.2f}" if dados['valor_justo_graham'] else "N/D",
                f"{dados['valor_justo_bazin']:.2f}" if dados['valor_justo_bazin'] else "N/D",
                f"{dados['valor_justo_gordon']:.2f}" if dados['valor_justo_gordon'] else "N/D",
                f"{media_valor_justo:.2f}" if valores_validos else "N/D"
            ],
            "Margem (%)": [
                f"{dados['margem_graham']:.1f}" if dados['margem_graham'] else "N/D",
                f"{dados['margem_bazin']:.1f}" if dados['margem_bazin'] else "N/D",
                f"{dados['margem_gordon']:.1f}" if dados['margem_gordon'] else "N/D",
                f"{margem_media:.1f}" if valores_validos else "N/D"
            ]
        })
        
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
    "© Multi-Valuation System • Graham • Bazin • Gordon • Métodos de Benjamin Graham"
    "</div>",
    unsafe_allow_html=True
)