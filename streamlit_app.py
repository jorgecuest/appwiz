import io
import time
import requests
import pandas as pd
import streamlit as st
import plotly.express as px


def parse_csv_content(text: str) -> pd.DataFrame:
    text = text.strip()
    if not text:
        return pd.DataFrame()
    first_line = text.splitlines()[0]
    delimiter = ';' if ';' in first_line else ','
    return pd.read_csv(io.StringIO(text), sep=delimiter)


def read_uploaded_file(uploaded) -> pd.DataFrame:
    if uploaded is None:
        return pd.DataFrame()
    name = uploaded.name.lower()
    try:
        if name.endswith(('.xls', '.xlsx')):
            return pd.read_excel(uploaded)
        else:
            content = uploaded.getvalue().decode('utf-8', errors='replace')
            return parse_csv_content(content)
    except Exception:
        # Fallback: try pandas auto-detection
        try:
            return pd.read_csv(uploaded)
        except Exception:
            return pd.DataFrame()


def compute_insights(df: pd.DataFrame):
    if df.empty:
        return {}, None
    df = df.fillna("")
    # Normalizar nombres de columnas esperadas
    cols = {c.upper(): c for c in df.columns}
    def col_lookup(name: str):
        return cols.get(name.upper())

    sev_col = col_lookup('SEVERITY') or 'Severity'
    estado_col = col_lookup('ESTADO') or 'ESTADO'
    resp_col = col_lookup('RESPONSIBLE') or 'RESPONSIBLE'
    sys_col = col_lookup('SYSTEM') or 'SYSTEM'

    # Asignar columnas normalizadas de forma segura
    df['Severity'] = df[sev_col] if sev_col in df.columns else df.get('Severity', '')
    df['ESTADO'] = df[estado_col] if estado_col in df.columns else df.get('ESTADO', '')
    df['RESPONSIBLE'] = df[resp_col] if resp_col in df.columns else df.get('RESPONSIBLE', '')
    df['SYSTEM'] = df[sys_col] if sys_col in df.columns else df.get('SYSTEM', '')

    state_counts = df['ESTADO'].replace('', 'UNKNOWN').value_counts().reset_index()
    state_counts.columns = ['name', 'value']

    resp_counts = df['RESPONSIBLE'].replace('', 'Sin Asignar').value_counts().reset_index()
    resp_counts.columns = ['name', 'total']

    sys_counts = df['SYSTEM'].replace('', 'Desconocido').value_counts().reset_index()
    sys_counts.columns = ['name', 'total']

    # Severity by state
    sev_state = (df.groupby(['ESTADO', 'Severity']).size().unstack(fill_value=0).reset_index())

    stats = {
        'crit': int(((df['Severity'] == 'Critical') & (df['ESTADO'] == 'PENDING')).sum()),
        'high': int(((df['Severity'] == 'High') & (df['ESTADO'] == 'PENDING')).sum()),
        'total': len(df)
    }

    return {
        'states': state_counts,
        'responsibles': resp_counts.head(10),
        'systems': sys_counts.head(10),
        'severity_by_state': sev_state
    }, stats


def call_gemini(prompt: str, api_key: str, system_prompt: str = "Eres un experto en ciberseguridad y analista de riesgos.") -> str:
    if not api_key:
        return "No API key provided."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]}
    }
    max_retries = 4
    delay = 1.0
    for i in range(max_retries):
        try:
            r = requests.post(url, json=payload, timeout=30)
            r.raise_for_status()
            res = r.json()
            return res.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        except Exception as e:
            if i == max_retries - 1:
                return f"Error calling Gemini: {e}"
            time.sleep(delay)
            delay *= 2


def main():
    st.set_page_config(page_title='Wiz Analytics - Streamlit', layout='wide')
    st.title('Wiz Analytics — Streamlit')

    with st.sidebar:
        st.header('Cargar datos')
        uploaded = st.file_uploader('CSV / Excel', type=['csv', 'xlsx', 'xls'])
        external_url = st.text_input('Cargar desde URL (CSV)')
        api_key = st.text_input('API Key Gemini (opcional)', type='password')

    df = read_uploaded_file(uploaded) if uploaded else pd.DataFrame()
    if external_url and df.empty:
        try:
            r = requests.get(external_url, timeout=15)
            r.raise_for_status()
            df = parse_csv_content(r.text)
        except Exception:
            st.sidebar.error('No se pudo cargar la URL')

    if df.empty:
        st.markdown('Arrastra o selecciona un archivo Excel/CSV en la barra lateral, o pega una URL.')
        st.stop()

    insights, stats = compute_insights(df)

    col1, col2 = st.columns(2)
    col1.metric('Críticos Pendientes', stats['crit'])
    col2.metric('Altos Pendientes', stats['high'])

    st.markdown('---')

    left, right = st.columns([3, 1])

    with left:
        st.subheader('Distribución de Estados')
        fig_states = px.bar(insights['states'], x='name', y='value', labels={'name': 'Estado', 'value': 'Cantidad'})
        st.plotly_chart(fig_states, use_container_width=True)

        st.subheader('Top Responsables')
        fig_resp = px.bar(insights['responsibles'], x='total', y='name', orientation='h', labels={'name': 'Responsable', 'total': 'Hallazgos'})
        st.plotly_chart(fig_resp, use_container_width=True)

        st.subheader('Sistemas con más hallazgos')
        fig_sys = px.bar(insights['systems'], x='name', y='total', labels={'name': 'Sistema', 'total': 'Hallazgos'})
        st.plotly_chart(fig_sys, use_container_width=True)

        st.subheader('Severidad por Estado')
        try:
            fig_sev = px.bar(insights['severity_by_state'], x='ESTADO', y=[c for c in insights['severity_by_state'].columns if c != 'ESTADO'])
            st.plotly_chart(fig_sev, use_container_width=True)
        except Exception:
            st.write(insights['severity_by_state'])

    with right:
        st.subheader('Analista IA (opcional)')
        if st.button('Generar Análisis IA'):
            summary = df.head(200).apply(lambda r: f"{r.get('Severity','')},{r.get('SYSTEM','')},{r.get('RESPONSIBLE','')},{r.get('ESTADO','')}", axis=1).str.cat(sep='\n')
            prompt = f"Analiza estos datos de vulnerabilidades ({len(df)} hallazgos):\n{summary}\nProporciona resumen ejecutivo, riesgos y prioridades en español."
            with st.spinner('Solicitando IA...'):
                result = call_gemini(prompt, api_key)
            st.text_area('Resultado IA', value=result, height=300)

        st.subheader('Explorador de datos')
        st.dataframe(df.head(200))


if __name__ == '__main__':
    main()
