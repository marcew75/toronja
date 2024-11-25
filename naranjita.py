import streamlit as st
from streamlit_folium import st_folium
import folium
import googlemaps
import requests
from urllib.parse import urlparse
import re
from concurrent.futures import ThreadPoolExecutor
import pandas as pd


# Funciones de utilidad
def is_valid_url(url):
    """Valida si una URL es válida y cumple con ciertos criterios."""
    try:
        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            return False
        excluded_domains = ['facebook.com', 'twitter.com', 'instagram.com']
        if any(domain in parsed.netloc for domain in excluded_domains):
            return False
        return True
    except Exception:
        return False

def extract_emails(text):
    """Extrae correos electrónicos de un texto usando expresiones regulares."""
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return list(set(re.findall(email_pattern, text)))

def scrape_page(url):
    """Extrae el contenido HTML de una página web."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        st.warning(f"Error al acceder a {url}: {str(e)}")
        return ""

def scrape_emails_from_urls(urls, max_workers=5):
    """Extrae correos electrónicos de una lista de URLs usando múltiples hilos."""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        html_contents = list(executor.map(scrape_page, urls))
        
    for url, html_content in zip(urls, html_contents):
        if html_content:
            emails = extract_emails(html_content)
            for email in emails:
                results.append([url, email])
    
    return results

# Configuración de la aplicación
st.title("Mapa Interactivo con Extracción de Correos")

# Configuración inicial del mapa
default_lat = 40.4168  # Latitud inicial (Madrid)
default_lng = -3.7038  # Longitud inicial (Madrid)

# Inicializar API de Google Maps (requiere agregar tu API Key en secrets.toml)
api_key = st.secrets["google_maps_api_key"]
gmaps = googlemaps.Client(key=api_key)

# Crear un mapa centrado en la ubicación inicial
m = folium.Map(location=[default_lat, default_lng], zoom_start=12)

# Habilitar que los usuarios puedan hacer clic en el mapa
folium.ClickForMarker().add_to(m)

# Renderizar el mapa con streamlit-folium
map_data = st_folium(m, width=700, height=500)

# Verificar si el usuario hizo clic en el mapa
if map_data and "last_clicked" in map_data:
    lat = map_data["last_clicked"]["lat"]
    lng = map_data["last_clicked"]["lng"]

    # Mostrar las coordenadas seleccionadas
    st.write(f"Coordenadas seleccionadas: Latitud {lat:.6f}, Longitud {lng:.6f}")

    # Obtener la dirección de las coordenadas usando Google Maps API
    geocode_result = gmaps.reverse_geocode((lat, lng))
    if geocode_result:
        address = geocode_result[0]['formatted_address']
        st.write(f"Dirección aproximada: {address}")

        # Buscar lugares cercanos con Google Places API
        categoria = st.selectbox(
            "Selecciona una categoría para buscar lugares cercanos",
            ["restaurant", "hotel", "store", "cafe", "bar", "hospital", "park"]
        )

        if st.button("Buscar lugares"):
            with st.spinner("Buscando lugares..."):
                places_result = gmaps.places_nearby(
                    location=(lat, lng),
                    radius=5000,
                    type=categoria
                )

                if places_result.get('results'):
                    st.write(f"Lugares cercanos encontrados en la categoría '{categoria}':")
                    urls = []  # Lista de URLs para análisis
                    for place in places_result['results']:
                        name = place.get('name', 'Sin nombre')
                        vicinity = place.get('vicinity', 'Sin dirección')
                        place_details = gmaps.place(
                            place_id=place['place_id'],
                            fields=['name', 'website']
                        )
                        website = place_details.get('result', {}).get('website')

                        st.write(f"📍 {name}")
                        st.write(f"Dirección: {vicinity}")
                        if website:
                            st.write(f"🌐 Sitio web: {website}")
                            if is_valid_url(website):
                                urls.append(website)
                        st.write("---")

                    # Extraer correos electrónicos de las URLs obtenidas
                    if urls:
                        st.write("Extrayendo correos electrónicos de los sitios web encontrados...")
                        emails = scrape_emails_from_urls(urls)
                        if emails:
                            st.write("Correos electrónicos encontrados:")
                            for url, email in emails:
                                st.write(f"📧 {email} (extraído de {url})")


                            df = pd.DataFrame(emails, columns=["sitios", "correos"])
                            csv = df.to_csv(index=False).encode("utf-8")
                            st.download_button("Descargar CSV", csv, "emails.csv", "text/csv")    
                        else:
                            st.info("No se encontraron correos electrónicos en los sitios analizados.")
                    else:
                        st.info("No se encontraron sitios web válidos para analizar.")
else:
    st.write("Haz clic en el mapa para seleccionar un punto.")
