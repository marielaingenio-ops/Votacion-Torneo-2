import streamlit as st
import pandas as pd
import os
import json
from streamlit_gsheets import GSheetsConnection

# --- Configuración de página ---
st.set_page_config(page_title="Votación SICAH", page_icon="🏑", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_votos = conn.read(usecols=[0, 1, 2])
    df_votos = df_votos.dropna(how="all") 
except Exception:
    df_votos = pd.DataFrame(columns=["Identificador_Votante", "Categoria", "Candidato_Elegido"])

jefes_que_votaron = set(df_votos["Identificador_Votante"].dropna().unique())

# --- MANEJO DE ARQUEROS ---
ARCHIVO_ARQUEROS = "arqueros.json"

def cargar_arqueros():
    if os.path.exists(ARCHIVO_ARQUEROS):
        with open(ARCHIVO_ARQUEROS, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def guardar_arqueros(lista):
    with open(ARCHIVO_ARQUEROS, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False)

# --- PROCESAMIENTO DEL ARCHIVO LOCAL ---
@st.cache_data
def procesar_dat(ruta_archivo):
    if not os.path.exists(ruta_archivo):
        return None
        
    torneo_data = {}
    equipos_temp = {}
    
    with open(ruta_archivo, 'r', encoding='utf-8', errors='ignore') as f:
        lineas = f.readlines()
        
    seccion_actual = None
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith("/*"): continue
        if linea.startswith("["): 
            seccion_actual = linea
            continue
            
        partes = linea.split(",")
        if seccion_actual == "[Equipos]" and len(partes) >= 3:
            nombre_eq = partes[2].strip()
            equipos_temp[partes[0]] = nombre_eq
            torneo_data[nombre_eq] = {"jugadores": [], "jefes": []}
            
        elif seccion_actual == "[Jugadores]" and len(partes) >= 5:
            id_equipo = partes[1]
            if id_equipo in equipos_temp:
                nombre_eq = equipos_temp[id_equipo]
                jugador = f"{partes[3]}, {partes[4]} (N° {partes[2]})"
                torneo_data[nombre_eq]["jugadores"].append(jugador)
                
        elif seccion_actual == "[Delegacion]" and len(partes) >= 4:
            id_funcion = partes[2]
            nombre_jefe = partes[3].strip()
            id_equipo = partes[1]
            if id_funcion == "4" and nombre_jefe and id_equipo in equipos_temp:
                nombre_eq = equipos_temp[id_equipo]
                torneo_data[nombre_eq]["jefes"].append(nombre_jefe)
                
    torneo_data = {k: v for k, v in torneo_data.items() if v["jugadores"]}
    for k in torneo_data:
        torneo_data[k]["jugadores"].sort()
        torneo_data[k]["jefes"].sort()
        
    return torneo_data

datos = procesar_dat("torneo.dat")

# --- BARRA LATERAL ---
st.sidebar.image("logo.png", width=150)
st.sidebar.title("Menú del Torneo")

param_vista = st.query_params.get("vista", "menu")

if param_vista == "votante":
    vista = "🏆 Votación Pública"
else:
    vista = st.sidebar.radio("Navegación:", ["🏆 Votación Pública", "⚙️ Director de Torneo"])

# ==========================================
# VISTA: DIRECTOR DE TORNEO (ADMINISTRADOR)
# ==========================================
if vista == "⚙️ Director de Torneo":
    st.title("Panel de Administración")
    password = st.text_input("Ingrese contraseña de Director/a de Torneo:", type="password")
    
    if password == "admin123":
        st.success("Acceso autorizado.")
        if not datos:
            st.error("❌ No se encontró el archivo 'torneo.dat' en la carpeta. Cópialo allí para activar la app.")
        else:
            st.success("✅ Archivo 'torneo.dat' leído correctamente.")
            
            st.divider()
            st.subheader("1. Separar arqueros")
            st.markdown("Selecciona los arqueros de cada equipo para que no aparezcan en la lista de jugadores de campo.")
            
            arqueros_actuales = cargar_arqueros()
            nuevos_arqueros = []
            
            # Crear un expansor para no ocupar toda la pantalla
            with st.expander("Desplegar lista de equipos para marcar arqueros"):
                for eq in sorted(datos.keys()):
                    jugs_eq = [f"{j} ({eq})" for j in datos[eq]["jugadores"]]
                    # Mostrar multiselect pre-cargado con los arqueros ya guardados
                    seleccion = st.multiselect(
                        f"Arqueros de {eq}:", 
                        options=jugs_eq, 
                        default=[j for j in jugs_eq if j in arqueros_actuales]
                    )
                    nuevos_arqueros.extend(seleccion)
                
                if st.button("💾 Guardar configuración de arqueros", type="primary"):
                    guardar_arqueros(nuevos_arqueros)
                    st.success("¡Listas actualizadas y separadas con éxito!")
                    st.rerun()
            
            st.divider()
            st.subheader("2. Resultados en vivo (Desde Google Sheets)")
            
            if not df_votos.empty:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("##### 🥇 Ranking jugadores de campo")
                    votos_j = df_votos[df_votos["Categoria"] == "Jugador de Campo"]["Candidato_Elegido"].value_counts().reset_index()
                    st.dataframe(votos_j, hide_index=True)
                    
                with col2:
                    st.markdown("##### 🧤 Ranking arqueros")
                    votos_a = df_votos[df_votos["Categoria"] == "Arquero"]["Candidato_Elegido"].value_counts().reset_index()
                    st.dataframe(votos_a, hide_index=True)
                    
                st.markdown("##### ✔️ Equipos que ya votaron:")
                for jefe in jefes_que_votaron:
                    st.write(f"- {jefe}")
            else:
                st.info("Aún no hay votos registrados en la planilla.")
                
            # --- RESULTADOS FINALES DENTRO DEL PANEL DEL DIRECTOR ---
            st.divider()
            st.subheader("🏆 Resultados Finales")
            
            if not df_votos.empty:
                # Filtramos los votos por categoría para calcular correctamente
                votos_jc = df_votos[df_votos["Categoria"] == "Jugador de Campo"]["Candidato_Elegido"]
                votos_arq = df_votos[df_votos["Categoria"] == "Arquero"]["Candidato_Elegido"]
                
                col_res1, col_res2 = st.columns(2)
                
                with col_res1:
                    if not votos_jc.empty:
                        jugador_ganador = votos_jc.value_counts().idxmax()
                        votos_jugador = votos_jc.value_counts().max()
                        st.success(f"🏑 **Jugador más votado:**\n\n{jugador_ganador} ({votos_jugador} votos)")
                    else:
                        st.info("Aún no hay votos para jugadores.")
                        
                with col_res2:
                    if not votos_arq.empty:
                        arquero_ganador = votos_arq.value_counts().idxmax()
                        votos_arquero = votos_arq.value_counts().max()
                        st.info(f"🧤 **Arquero más votado:**\n\n{arquero_ganador} ({votos_arquero} votos)")
                    else:
                        st.info("Aún no hay votos para arqueros.")
            else:
                st.warning("Aún no se han recibido votos para calcular a los ganadores.")

# ==========================================
# VISTA: VOTACIÓN PÚBLICA (JEFES DE EQUIPO)
# ==========================================
elif vista == "🏆 Votación Pública":
    col_logo, col_texto = st.columns([1, 5])
    with col_logo:
        st.image("logo.png", use_container_width=True)
    with col_texto:
        st.title("Elección de los mejores del Torneo")
        
    if not datos:
        st.warning("⏳ El Director de Torneo está configurando el sistema.")
    else:
        lista_equipos = ["-- Seleccionar --"] + sorted(list(datos.keys()))
        arqueros_config = cargar_arqueros()
        
        st.subheader("Identificación del Votante")
        colA, colB = st.columns(2)
        
        with colA:
            equipo_votante = st.selectbox("1. ¿A qué equipo representas?", lista_equipos)
        
        if equipo_votante != "-- Seleccionar --":
            jefes_equipo = ["-- Seleccionar --"] + datos[equipo_votante]["jefes"]
            
            with colB:
                if len(jefes_equipo) == 1:
                    st.error("No figuras cargado como Jefe de Equipo (Función 4).")
                    jefe_votante = "-- Seleccionar --"
                else:
                    jefe_votante = st.selectbox("2. Selecciona tu nombre:", jefes_equipo)
            
            if jefe_votante != "-- Seleccionar --":
                identificador_unico = f"{equipo_votante} - {jefe_votante}"
                
                if identificador_unico in jefes_que_votaron:
                    st.error("🚨 El voto de tu equipo ya fue registrado por el Director.")
                else:
                    st.divider()
                    st.subheader("Selección de candidatos")
                    
                    def elegir_candidato(titulo, key, es_arquero=False):
                        eq = st.selectbox(f"Club del {titulo}:", lista_equipos, key=f"eq_{key}")
                        if eq != "-- Seleccionar --":
                            jugs_crudos = datos[eq]["jugadores"]
                            jugs_formateados = [f"{j} ({eq})" for j in jugs_crudos]
                            
                            # Filtro Mágico: Separa según lo que configuró la Mesa de Control
                            if es_arquero:
                                opciones = [j for j in jugs_formateados if j in arqueros_config]
                                if not opciones:
                                    st.warning(f"La mesa de control aún no asignó arqueros para {eq}.")
                            else:
                                opciones = [j for j in jugs_formateados if j not in arqueros_config]
                                
                            opciones_mostrar = ["-- Seleccionar --"] + opciones
                            jug = st.selectbox(f"Nombre del {titulo}:", opciones_mostrar, key=f"jug_{key}")
                            if jug != "-- Seleccionar --":
                                return jug
                        return None

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("#### 🏑 Jugadores de campo")
                        jc1 = elegir_candidato("Jugador 1", "jc1", es_arquero=False)
                        jc2 = elegir_candidato("Jugador 2", "jc2", es_arquero=False)
                        
                    with col2:
                        st.markdown("#### 🧤 Arqueros")
                        arq1 = elegir_candidato("Arquero 1", "arq1", es_arquero=True)
                        arq2 = elegir_candidato("Arquero 2", "arq2", es_arquero=True)
                        
                    st.divider()
                    if st.button("🗳️ Enviar votos al Director", type="primary", use_container_width=True):
                        selecciones = [jc1, jc2, arq1, arq2]
                        
                        if None in selecciones:
                            st.error("⚠️ Elige a los 4 candidatos.")
                        elif len(set(selecciones)) != 4:
                            st.error("⚠️ No puedes repetir al mismo jugador.")
                        else:
                            nuevos_votos = pd.DataFrame([
                                {"Identificador_Votante": identificador_unico, "Categoria": "Jugador de Campo", "Candidato_Elegido": jc1},
                                {"Identificador_Votante": identificador_unico, "Categoria": "Jugador de Campo", "Candidato_Elegido": jc2},
                                {"Identificador_Votante": identificador_unico, "Categoria": "Arquero", "Candidato_Elegido": arq1},
                                {"Identificador_Votante": identificador_unico, "Categoria": "Arquero", "Candidato_Elegido": arq2},
                            ])
                            
                            # Actualizamos la planilla
                            df_actualizado = pd.concat([df_votos, nuevos_votos], ignore_index=True)
                            conn.update(data=df_actualizado)
                            
                            st.balloons()
                            st.success("✅ Tus votos han sido enviados. Puedes cerrar esta ventana.")
