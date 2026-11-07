import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time

# Configuración de página
st.set_page_config(
    page_title="Centro de Control de Moderación",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inyección de CSS personalizado para UI/UX profesional
st.markdown("""
<style>
    /* Fondo principal y fuentes */
    .stApp {
        background-color: #0e1117;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Contenedores de Tarjetas (KPIs) */
    div[data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 18px 22px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    
    div[data-testid="stMetric"]:hover {
        border-color: #58a6ff;
        transform: translateY(-2px);
    }

    div[data-testid="stMetricLabel"] {
        color: #8b949e !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    div[data-testid="stMetricValue"] {
        color: #f0f6fc !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
    }

    /* Títulos y separadores */
    h1 {
        color: #f0f6fc !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px;
    }

    .stMarkdown p {
        color: #8b949e;
    }

    hr {
        border-color: #30363d !important;
        margin: 2rem 0;
    }

    /* Formato de la tabla */
    div[data-testid="stDataFrame"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 8px;
    }

    /* Ocultar barra superior predeterminada de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Encabezado del Dashboard
st.title("🛡️ Centro de Control de Moderación")
st.markdown("Monitoreo continuo de salud del chat grupal, auditoría de toxicidad y prevención de crisis.")

def cargar_datos():
    try:
        conn = sqlite3.connect("moderacion_bot.db")
        df = pd.read_sql_query("SELECT * FROM registros_moderacion ORDER BY id DESC", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

df = cargar_datos()

if not df.empty:
    # -------------------------------------------------------------
    # 1. TARJETAS DE MÉTRICAS (KPIs)
    # -------------------------------------------------------------
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    total_mensajes = len(df)
    toxicos = len(df[df['categoria'] == 'TOXICO'])
    crisis = len(df[df['categoria'] == 'CRISIS'])
    usuarios = df['usuario_id'].nunique()

    kpi1.metric("Mensajes Analizados", f"{total_mensajes:,}")
    kpi2.metric("Incidentes Tóxicos", toxicos, delta=f"{(toxicos/total_mensajes)*100:.1f}% del total" if total_mensajes > 0 else "0%", delta_color="inverse")
    kpi3.metric("Alertas de Crisis", crisis, delta="Intervención Silenciosa", delta_color="normal")
    kpi4.metric("Usuarios Evaluados", usuarios)

    st.markdown("---")

    # -------------------------------------------------------------
    # 2. GRÁFICOS PERSONALIZADOS (Plotly Dark Style)
    # -------------------------------------------------------------
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Distribución de Clasificación")
        cat_counts = df['categoria'].value_counts().reset_index()
        cat_counts.columns = ['categoria', 'total']
        
        # Paleta de colores sobria
        color_map = {'NORMAL': '#2ea043', 'TOXICO': '#da3633', 'CRISIS': '#1f6feb'}
        
        fig_donut = px.pie(
            cat_counts, 
            values='total', 
            names='categoria',
            color='categoria',
            color_discrete_map=color_map,
            hole=0.65
        )
        fig_donut.update_traces(textposition='outside', textinfo='percent+label')
        fig_donut.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#8b949e'),
            showlegend=False,
            margin=dict(t=20, b=20, l=20, r=20)
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with c2:
        st.subheader("Top Infractores (Faltas Acumuladas)")
        top_infractores = df[df['categoria'] == 'TOXICO']['usuario_nombre'].value_counts().head(5).reset_index()
        top_infractores.columns = ['Usuario', 'Faltas']
        
        fig_bar = px.bar(
            top_infractores, 
            x='Faltas', 
            y='Usuario', 
            orientation='h',
            color_discrete_sequence=['#da3633']
        )
        fig_bar.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#8b949e'),
            xaxis=dict(showgrid=True, gridcolor='#30363d', title="Faltas"),
            yaxis=dict(showgrid=False, title="", autorange="reversed"),
            margin=dict(t=20, b=20, l=20, r=20)
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # -------------------------------------------------------------
    # 3. TABLA DE REGISTROS CORPORATIVA
    # -------------------------------------------------------------
    st.subheader("Historial de Moderación en Vivo")
    
    # Formatear DataFrame para exhibición
    df_display = df[['fecha_hora', 'usuario_nombre', 'categoria', 'mensaje_texto']].copy()
    df_display.columns = ['Fecha/Hora', 'Usuario', 'Categoría', 'Mensaje Detectado']
    
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True
    )

else:
    st.info("Esperando inicialización de datos desde el servicio de moderación de Telegram...")

# Recarga automática de 5 segundos
time.sleep(5)
st.rerun()