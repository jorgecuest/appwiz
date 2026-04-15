# Wiz Analytics - Streamlit

Conversión de un componente React a una app sencilla en Streamlit para analizar reportes exportados de Wiz.

Requisitos:

- Python 3.8+
- Instalar dependencias:

```bash
pip install -r requirements.txt
```

Ejecutar:

```bash
streamlit run streamlit_app.py
```

Notas:
- La opción de IA usa la API de Gemini (Google). Proporcione la `API Key` en la barra lateral si desea activar el análisis.
- Soporta archivos `.xlsx`, `.xls` y `.csv` (detecta `;` o `,` como separador según la primera línea).
