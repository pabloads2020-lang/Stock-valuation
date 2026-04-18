import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import math
from deep_translator import GoogleTranslator
import requests
import re

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Graham Valuation System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CSS PERSONALIZADO
# ============================================================

st.markdown("""
<style>
    /* Estilo Investment Bank */
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
# FUNÇÕES AUXILIARES
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
    ticker_clean = ticker.upper().replace('.SA', '')
    try:
        url = f"https://statusinvest.com.br/acao/companyinfo?code={ticker_clean}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            dados = response.json()
            resumo = dados.get('description') or dados.get('businessDescription')
            if resumo and len(resumo) > 50:
                return resumo
    except:
        pass
    return None

def calcular_graham(lpa, vpa):
    if lpa and vpa and lpa > 0 and vpa > 0:
        return math.sqrt(22.5 * lpa * vpa)
    return None

def calcular_margem_seguranca(cotacao, valor_justo):
    if cotacao and valor_justo and cotacao > 0:
        return ((valor_justo - cotacao) / valor_justo) * 100
    return None

def calcular_upside(cotacao, valor_justo):
    if cotacao and valor_justo and cotacao > 0:
        return ((valor_justo - cotacao) / cotacao) * 100
    return None

def buscar_dados(ticker_input):
    ticker_input = ticker_input.strip().upper()
    ticker_yahoo = f"{ticker_input}.SA" if not ticker_input.endswith('.SA') else ticker_input
    
    try:
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
        
        if roe:
            roe = roe * 100
        
        if not lpa and pl and cotacao:
            lpa = cotacao / pl if pl > 0 else None
        
        valor_justo = calcular_graham(lpa, vpa)
        margem_seguranca = calcular_margem_seguranca(cotacao, valor_justo)
        upside = calcular_upside(cotacao, valor_justo)
        
        resumo = buscar_resumo_status_invest(ticker_input)
        if not resumo:
            resumo_en = info.get('longBusinessSummary', '')
            resumo = traduzir_para_portugues(resumo_en) if resumo_en else "Informações não disponíveis"
        
        return {
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
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        return None

# ============================================================
# INTERFACE PRINCIPAL
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
        
        # ==================== RESULTADO ====================
        st.markdown("---")
        st.markdown("## 📈 RESULTADO DA VALUATION")
        
        # Recomendação
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
            # Cálculo do P/VP
            if dados['cotacao'] and dados['vpa'] and dados['vpa'] > 0:
                pvp = dados['cotacao'] / dados['vpa']
                cor_pvp = "🟢" if pvp < 1.5 else "🔴"
                st.metric("P/VP (Preço/Valor)", f"{cor_pvp} {pvp:.2f}")
            else:
                st.metric("P/VP (Preço/Valor)", "N/D")
        
        # ==================== GRÁFICO DE GAUGE ====================
        if dados['margem_seguranca']:
            st.markdown("---")
            st.markdown("## 📊 ANÁLISE DE MARGEM DE SEGURANÇA")
            
            # Gauge chart
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=dados['margem_seguranca'],
                title={"text": "Margem de Segurança (%)"},
                domain={'x': [0, 1], 'y': [0, 1]},
                gauge={
                    'axis': {'range': [-100, 100]},
                    'bar': {'color': "#C9A03D"},
                    'steps': [
                        {'range': [-100, 0], 'color': '#C62828'},
                        {'range': [0, 15], 'color': '#F5F6F8'},
                        {'range': [15, 30], 'color': '#E8F1FA'},
                        {'range': [30, 100], 'color': '#E8F5EE'}
                    ],
                    'threshold': {
                        'line': {'color': "black", 'width': 4},
                        'thickness': 0.75,
                        'value': dados['margem_seguranca']
                    }
                }
            ))
            
            fig.update_layout(
                height=300,
                margin=dict(l=50, r=50, t=50, b=50),
                paper_bgcolor="#F5F6F8",
                font=dict(color="#0B1C3F")
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # ==================== DISCLAIMER ====================
        st.markdown("---")
        st.caption("""
        ⚠️ **DISCLAIMER:** Este relatório é gerado automaticamente com base em dados públicos. 
        Não constitui recomendação de investimento personalizada. O investidor é o único responsável 
        por suas decisões de alocação. Rentabilidade passada não representa garantia de retornos futuros.
        """)
        
        # ==================== DOWNLOAD ====================
        st.markdown("---")
        
        # Criar DataFrame para download
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