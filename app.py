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
from functools import lru_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# CONFIGURAÇÃO DE SESSÃO COM RETRY E BACKOFF
# ============================================================

def criar_sessao_com_retry():
    """Cria uma sessão requests com retry automático e backoff exponencial"""
    session = requests.Session()
    
    # Estratégia de retry: espera 1s, 2s, 4s, 8s... até 5 tentativas
    retry_strategy = Retry(
        total=5,
        backoff_factor=2,  # 1s, 2s, 4s, 8s, 16s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # User-Agent realista para não ser bloqueado
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    return session

# Cache em memória para não repetir buscas na mesma sessão
CACHE_TICKERS = {}

def buscar_com_rate_limit(func, *args, **kwargs):
    """Wrapper que adiciona delay entre chamadas para evitar rate limit"""
    time.sleep(random.uniform(1.5, 3.5))  # Delay aleatório de 1.5 a 3.5 segundos
    return func(*args, **kwargs)

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Graham Valuation - Método de Graham para Ações",
    page_icon="📊",
    layout="wide"
)

# ============================================================
# CSS PERSONALIZADO (mantido igual)
# ============================================================

st.markdown("""
<style>
    .main {
        background-color: #F5F6F8;
    }
    .stApp {
        background-color: #F5F6F8;
    }
    .metric-card {
        background-color: white;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        text-align: center;
        border: 1px solid #E8E9EC;
    }
    .metric-label {
        color: #4A5568;
        font-size: 12px;
        letter-spacing: 1px;
        margin-bottom: 10px;
    }
    .metric-value {
        color: #0B1C3F;
        font-size: 28px;
        font-weight: bold;
    }
    .valor-justo-card {
        background-color: #0B1C3F;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        color: white;
    }
    .valor-justo-value {
        color: #C9A03D;
        font-size: 32px;
        font-weight: bold;
    }
    .recomendacao {
        text-align: center;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .recomendacao-COMPRAR {
        background-color: #2E7D32;
        color: white;
    }
    .recomendacao-COMPRA-PARCIAL {
        background-color: #C9A03D;
        color: white;
    }
    .recomendacao-NEUTRO {
        background-color: #4A5568;
        color: white;
    }
    .recomendacao-EVITAR {
        background-color: #C62828;
        color: white;
    }
    h1, h2, h3 {
        color: #0B1C3F;
    }
    hr {
        margin: 20px 0;
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #C9A03D, transparent);
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# FUNÇÃO PARA CRIAR O VELOCÍMETRO (mantida igual)
# ============================================================

def criar_velocimetro_simples(margem):
    if margem is None:
        margem = 0
    
    if margem < 0:
        cor_marcador = "#C62828"
    elif margem < 20:
        cor_marcador = "#F5A623"
    else:
        cor_marcador = "#2E7D32"
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=margem,
        number={
            'suffix': "%", 
            'font': {'size': 48, 'color': "black", 'family': "Arial", 'weight': "bold"},
            'valueformat': '.1f'
        },
        title={
            'text': "MARGEM DE SEGURANÇA", 
            'font': {'size': 14, 'color': "gray", 'family': "Arial"}
        },
        gauge={
            'axis': {
                'range': [-100, 100],
                'tickwidth': 2,
                'tickcolor': "black",
                'ticklen': 10,
                'tickfont': {'size': 11, 'color': "black", 'family': "Arial"},
                'ticks': 'outside',
                'tickvals': [-100, -75, -50, -25, 0, 25, 50, 75, 100],
                'ticktext': ['-100', '', '-50', '', '0', '', '50', '', '100']
            },
            'bar': {'color': "black", 'thickness': 0.03, 'line': {'color': "black", 'width': 1}},
            'bgcolor': "white",
            'borderwidth': 0,
            'steps': [
                {'range': [-100, 0], 'color': "#E53935", 'thickness': 0.6},
                {'range': [0, 20], 'color': "#FDD835", 'thickness': 0.6},
                {'range': [20, 100], 'color': "#43A047", 'thickness': 0.6}
            ],
            'threshold': {
                'line': {'color': cor_marcador, 'width': 4},
                'thickness': 0.8,
                'value': margem
            }
        }
    ))
    
    fig.update_layout(
        height=300,
        margin=dict(l=40, r=40, t=70, b=30),
        paper_bgcolor="white",
        font=dict(color="black", family="Arial")
    )
    
    return fig

# ============================================================
# FUNÇÕES AUXILIARES (com melhorias)
# ============================================================

def traduzir_para_portugues(texto_ingles):
    if not texto_ingles:
        return "Informação não disponível"
    try:
        tradutor = GoogleTranslator(source='auto', target='pt')
        return tradutor.translate(texto_ingles)
    except:
        return texto_ingles

def buscar_resumo_status_invest(ticker):
    """Versão melhorada com retry e tratamento de erro específico"""
    ticker_clean = ticker.upper().replace('.SA', '')
    
    # Verifica cache primeiro
    cache_key = f"resumo_{ticker_clean}"
    if cache_key in CACHE_TICKERS:
        return CACHE_TICKERS[cache_key]
    
    try:
        # Usa sessão com retry
        session = criar_sessao_com_retry()
        url = f"https://statusinvest.com.br/acao/companyinfo?code={ticker_clean}"
        
        response = session.get(url, timeout=15)
        
        if response.status_code == 200:
            dados = response.json()
            resumo = dados.get('description') or dados.get('businessDescription')
            if resumo and len(resumo) > 50:
                CACHE_TICKERS[cache_key] = resumo
                return resumo
        elif response.status_code == 429:
            # Rate limit específico do Status Invest
            st.warning("⏳ Status Invest está com limite de requisições. Tentando novamente em alguns segundos...")
            time.sleep(5)
            return buscar_resumo_status_invest(ticker)  # Tenta recursivamente
    except requests.exceptions.RequestException as e:
        # Falha silenciosa, não quebra o app
        pass
    
    CACHE_TICKERS[cache_key] = None
    return None

def calcular_graham(lpa, vpa):
    if lpa and vpa and lpa > 0 and vpa > 0:
        return math.sqrt(22.5 * lpa * vpa)
    return None

def calcular_margem_seguranca(cotacao, valor_justo):
    if cotacao and valor_justo and cotacao > 0 and valor_justo:
        return ((valor_justo - cotacao) / valor_justo) * 100
    return None

def calcular_upside(cotacao, valor_justo):
    if cotacao and valor_justo and cotacao > 0 and valor_justo:
        return ((valor_justo - cotacao) / cotacao) * 100
    return None

def buscar_dados(ticker_input):
    """Versão principal com cache, retry e delay"""
    ticker_input = ticker_input.strip().upper()
    
    # Verifica cache primeiro
    if ticker_input in CACHE_TICKERS:
        return CACHE_TICKERS[ticker_input]
    
    ticker_yahoo = f"{ticker_input}.SA" if not ticker_input.endswith('.SA') else ticker_input
    
    try:
        # Delay antes da chamada Yahoo Finance
        time.sleep(random.uniform(1.0, 2.5))
        
        stock = yf.Ticker(ticker_yahoo)
        
        # Tentativa com retry manual para Yahoo Finance
        info = None
        for tentativa in range(3):
            try:
                info = stock.info
                if info:
                    break
            except Exception as e:
                if "Rate limited" in str(e) or "429" in str(e):
                    wait_time = (tentativa + 1) * 2
                    st.warning(f"⏳ Yahoo Finance com limite de requisições. Aguardando {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise e
        
        if not info:
            CACHE_TICKERS[ticker_input] = None
            return None
        
        cotacao = info.get('currentPrice') or info.get('regularMarketPrice')
        lpa = info.get('trailingEps')
        vpa = info.get('bookValue')
        pl = info.get('trailingPE')
        roe = info.get('returnOnEquity')
        nome = info.get('longName') or ticker_input
        
        if roe:
            roe = roe * 100
        
        if not lpa and pl and cotacao:
            lpa = cotacao / pl if pl > 0 else None
        
        valor_justo = calcular_graham(lpa, vpa)
        margem_seguranca = calcular_margem_seguranca(cotacao, valor_justo)
        upside = calcular_upside(cotacao, valor_justo)
        
        # Busca resumo (já tem cache interno)
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
            "valor_justo": valor_justo,
            "margem_seguranca": margem_seguranca,
            "upside": upside,
            "resumo": resumo,
            "setor": info.get('sector', 'N/D'),
            "segmento": info.get('industry', 'N/D')
        }
        
        # Armazena em cache
        CACHE_TICKERS[ticker_input] = resultado
        return resultado
        
    except Exception as e:
        error_msg = str(e)
        if "Rate limited" in error_msg or "429" in error_msg:
            st.error("⏳ Limite de requisições atingido. Aguarde 30 segundos e tente novamente.")
        else:
            st.error(f"Erro ao buscar dados: {error_msg}")
        CACHE_TICKERS[ticker_input] = None
        return None

# ============================================================
# INTERFACE PRINCIPAL (mantida igual)
# ============================================================

st.title("📊 GRAHAM VALUATION SYSTEM")
st.markdown("*Investment Banking Edition*")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/investment.png", width=80)
    st.markdown("## 🔍 Análise de Investimentos")
    st.markdown("### Método Benjamin Graham")
    st.markdown("---")
    
    ticker = st.text_input("📈 Ticker da Ação", value="ITSA4", help="Ex: ITSA4, PETR4, VALE3")
    
    col1, col2 = st.columns(2)
    with col1:
        analisar = st.button("🔍 ANALISAR", use_container_width=True)
    with col2:
        limpar = st.button("🗑️ LIMPAR", use_container_width=True)
    
    st.markdown("---")
    st.markdown("### 📋 Exemplos")
    st.markdown("- ITSA4 (Itaúsa)")
    st.markdown("- PETR4 (Petrobras)")
    st.markdown("- VALE3 (Vale)")
    st.markdown("- WEGE3 (WEG)")
    st.markdown("- BOVA11 (ETF)")
    st.markdown("---")
    st.markdown("### ℹ️ Sobre")
    st.markdown("Valuation baseada no método de Graham")
    st.markdown("Fonte: Yahoo Finance + Status Invest")

if limpar:
    CACHE_TICKERS.clear()  # Limpa cache também
    st.rerun()

if analisar:
    with st.spinner("🔄 Buscando dados..."):
        dados = buscar_dados(ticker)
    
    if dados:
        # ==================== CABEÇALHO ====================
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.markdown(f"## {dados['ticker']}")
            st.markdown(f"### {dados['nome']}")
            st.caption(f"Setor: {dados['setor']} | Segmento: {dados['segmento']}")
        
        # ==================== CARDS ====================
        st.markdown("---")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">COTAÇÃO ATUAL</div>
                <div class="metric-value">R$ {dados['cotacao']:.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            if dados['valor_justo']:
                cor_upside = "#2E7D32" if dados['upside'] >= 0 else "#C62828"
                st.markdown(f"""
                <div class="valor-justo-card">
                    <div class="metric-label">VALOR JUSTO (GRAHAM)</div>
                    <div class="valor-justo-value">R$ {dados['valor_justo']:.2f}</div>
                    <div style="color: {cor_upside}; font-size: 14px; margin-top: 8px;">
                        {dados['upside']:+.1f}% {'▲' if dados['upside'] >= 0 else '▼'}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">VALOR JUSTO</div>
                    <div class="metric-value">N/D</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col3:
            if dados['margem_seguranca']:
                if dados['margem_seguranca'] >= 30:
                    cor_margem = "#2E7D32"
                elif dados['margem_seguranca'] >= 15:
                    cor_margem = "#C9A03D"
                elif dados['margem_seguranca'] >= 0:
                    cor_margem = "#4A5568"
                else:
                    cor_margem = "#C62828"
                
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">MARGEM DE SEGURANÇA</div>
                    <div class="metric-value" style="color: {cor_margem};">{dados['margem_seguranca']:+.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">MARGEM DE SEGURANÇA</div>
                    <div class="metric-value">N/D</div>
                </div>
                """, unsafe_allow_html=True)
        
        # ==================== VELOCÍMETRO ====================
        st.markdown("---")
        st.markdown("## 📊 ANÁLISE DE MARGEM DE SEGURANÇA")
        
        if dados['margem_seguranca']:
            fig = criar_velocimetro_simples(dados['margem_seguranca'])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📊 Dados insuficientes para calcular a margem de segurança")
        
        # ==================== RESULTADO ====================
        st.markdown("---")
        st.markdown("## 📈 RESULTADO DA VALUATION")
        
        if dados['margem_seguranca']:
            if dados['margem_seguranca'] >= 30:
                recomendacao = "COMPRAR"
                classe = "recomendacao-COMPRAR"
            elif dados['margem_seguranca'] >= 15:
                recomendacao = "COMPRA PARCIAL"
                classe = "recomendacao-COMPRA-PARCIAL"
            elif dados['margem_seguranca'] >= 0:
                recomendacao = "NEUTRO"
                classe = "recomendacao-NEUTRO"
            else:
                recomendacao = "EVITAR"
                classe = "recomendacao-EVITAR"
            
            st.markdown(f"""
            <div class="recomendacao {classe}">
                <h2 style="margin:0; color:white;">{recomendacao}</h2>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            > **Margem de Segurança:** {dados['margem_seguranca']:.1f}%  
            > **Valor Justo:** R$ {dados['valor_justo']:.2f} | **Cotação:** R$ {dados['cotacao']:.2f}  
            > **Upside Potencial:** {dados['upside']:+.1f}%
            """)
        else:
            st.warning("⚠️ Dados insuficientes para calcular o valor justo")
        
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
                st.metric("P/L (Preço/Lucro)", f"{cor_pl} {dados['pl']:.1f}" if dados['pl'] else "N/D")
            else:
                st.metric("P/L (Preço/Lucro)", "N/D")
            
            if dados['roe']:
                cor_roe = "🟢" if dados['roe'] > 15 else "🟡"
                st.metric("ROE (Retorno s/ PL)", f"{cor_roe} {dados['roe']:.1f}%" if dados['roe'] else "N/D")
            else:
                st.metric("ROE (Retorno s/ PL)", "N/D")
        
        with col3:
            if dados['cotacao'] and dados['vpa'] and dados['vpa'] > 0:
                pvp = dados['cotacao'] / dados['vpa']
                cor_pvp = "🟢" if pvp < 1.5 else "🔴"
                st.metric("P/VP (Preço/Valor)", f"{cor_pvp} {pvp:.2f}")
            else:
                st.metric("P/VP (Preço/Valor)", "N/D")
        
        # ==================== DISCLAIMER ====================
        st.markdown("---")
        st.caption("""
        ⚠️ **DISCLAIMER:** Este relatório é gerado automaticamente com base em dados públicos. 
        Não constitui recomendação de investimento personalizada. O investidor é o único responsável 
        por suas decisões de alocação. Rentabilidade passada não representa garantia de retornos futuros.
        """)
        
        # ==================== DOWNLOAD ====================
        st.markdown("---")
        
        df = pd.DataFrame({
            "Indicador": ["Cotação", "Valor Justo", "Margem de Segurança", "Upside", "LPA", "VPA", "P/L", "ROE"],
            "Valor": [
                f"R$ {dados['cotacao']:.2f}" if dados['cotacao'] else "N/D",
                f"R$ {dados['valor_justo']:.2f}" if dados['valor_justo'] else "N/D",
                f"{dados['margem_seguranca']:.1f}%" if dados['margem_seguranca'] else "N/D",
                f"{dados['upside']:.1f}%" if dados['upside'] else "N/D",
                f"R$ {dados['lpa']:.2f}" if dados['lpa'] else "N/D",
                f"R$ {dados['vpa']:.2f}" if dados['vpa'] else "N/D",
                f"{dados['pl']:.1f}" if dados['pl'] else "N/D",
                f"{dados['roe']:.1f}%" if dados['roe'] else "N/D",
            ]
        })
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Exportar para CSV",
            data=csv,
            file_name=f"valuation_{dados['ticker']}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
    else:
        st.error(f"❌ Não foi possível encontrar dados para {ticker}")
        st.info("Verifique se o ticker está correto (ex: ITSA4, PETR4, VALE3)")

# ==================== RODAPÉ ====================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #8A8D91; font-size: 12px;'>"
    "© Graham Valuation System • Investment Banking Edition • Método Benjamin Graham"
    "</div>",
    unsafe_allow_html=True
)