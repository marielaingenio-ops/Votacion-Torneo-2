import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- Configuración de página ---
st.set_page_config(page_title="Votación SICAH", page_icon="🏑", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# 1. Leer los Votos (EN VIVO con ttl=0)
try:
    df_votos = conn.read(worksheet="Votos", usecols=[0, 1, 2], ttl=0)
    df_votos = df_votos.dropna(how="all") 
except Exception:
    df_votos = pd.DataFrame(columns=["Identificador_Votante", "Categoria", "Candidato_Elegido"])

jefes_que_votaron = set(df_votos["Identificador_Votante"].dropna().unique()) if not df_votos.empty else set()

# 2. Leer el Padrón (EN VIVO con ttl=0)
try:
    df_padron = conn.read(worksheet="Padron", usecols=[0, 1, 2], ttl=0)
    df_padron = df_padron.dropna(how="all")
except Exception:
    df_padron = pd.DataFrame(columns=["Equipo", "Tipo", "Nombre"])

# --- CONSTRUIR LOS DATOS DESDE LA NUBE ---
datos = {}
arqueros_config = []

if not df_padron.empty and "Equipo" in df_padron.columns:
    for _, fila in df_padron.iterrows():
        eq = str(fila["Equipo"]).strip()
        if eq not in datos:
            datos[eq] = {"jugadores": [], "jefes": []}
            
        if fila["Tipo"] in ["Jugador", "Arquero"]:
            datos[eq]["jugadores"].append(fila["Nombre"])
            if fila["Tipo"] == "Arquero":
                arqueros_config.append(f'{fila["Nombre"]} ({eq})')
        elif fila["Tipo"] == "Jefe":
            datos[eq]["jefes"].append(fila["Nombre"])
            
    for k in datos:
        datos[k]["jugadores"].sort()
        datos[k]["jefes"].sort()

# --- PROCESADOR DE ARCHIVO .DAT A PRUEBA DE ERRORES SICAH ---
def procesar_texto_dat(contenido):
    torneo_data = {}
    equipos_temp = {}
    lineas = contenido.splitlines()
    
    seccion_actual = None
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith("/*"): continue
        if linea.startswith("["): 
            seccion_actual = linea
            continue
            
        # MAGIA: Limpiamos espacios invisibles de todas las partes al mismo tiempo
        partes = [p.strip() for p in linea.split(",")]
        
        if seccion_actual == "[Equipos]" and len(partes) >= 3:
            id_equipo = partes[0]
            nombre_eq = partes[2]
            equipos_temp[id_equipo] = nombre_eq
            torneo_data[nombre_eq] = {"jugadores": [], "jefes": []}
            
        elif seccion_actual == "[Jugadores]" and len(partes) >= 5:
            id_equipo = partes[1]
            if id_equipo in equipos_temp:
                nombre_eq = equipos_temp[id_equipo]
                jugador = f"{partes[3]}, {partes[4]} (N° {partes[2]})"
                torneo_data[nombre_eq]["jugadores"].append(jugador)
                
        elif seccion_actual == "[Delegacion]" and len(partes) >= 4:
            id_equipo = partes[1]
            id_funcion = partes[2]
            nombre_jefe = partes[3]
            if id_funcion == "4" and nombre_jefe and id_equipo in equipos_temp:
                nombre_eq = equipos_temp[id_equipo]
                torneo_data[nombre_eq]["jefes"].append(nombre_jefe)
                
    return {k: v for k, v in torneo_data.items() if v["jugadores"]}

# --- ACCESO Y MENÚ SECRETO ---
param_admin = st.query_params.get("admin", "no")

if param_admin == "si":
    st.sidebar.image("logo.png", width=150)
    st.sidebar.title("Menú del Director/a")
    vista = st.sidebar.radio("Navegación:", ["🏆 Votación Pública", "⚙️ Director de Torneo"])
else:
    vista = "🏆 Votación Pública"

# ==========================================
# VISTA: DIRECTOR DE TORNEO (ADMINISTRADOR)
# ==========================================
if vista == "⚙️ Director de Torneo":
    st.title("Panel de Administración")
    password = st.text_input("Ingrese contraseña de Director/a de Torneo:", type="password")
    
    if password == "admin123":
        st.success("Acceso autorizado al Director/a de Torneo.")
        
        # 1. CARGA DE NUEVO PADRÓN
        st.divider()
        st.subheader("📁 1. Cargar Torneo (.dat)")
        st.markdown("Sube el archivo `.dat` del torneo aquí. Esto guardará todos los equipos directamente en la nube.")
        archivo_subido = st.file_uploader("Arrastra aquí el archivo .dat", type=["dat"])
        
        if archivo_subido is not None:
            if st.button("🚀 Procesar y subir a Google Sheets", type="primary"):
                contenido = archivo_subido.getvalue().decode("utf-8", errors="ignore")
                nuevo_torneo_data = procesar_texto_dat(contenido)
                
                registros = []
                for eq, eq_data in nuevo_torneo_data.items():
                    for jug in eq_data["jugadores"]:
                        registros.append({"Equipo": eq, "Tipo": "Jugador", "Nombre": jug})
                    for jefe in eq_data["jefes"]:
                        registros.append({"Equipo": eq, "Tipo": "Jefe", "Nombre": jefe})
                        
               # --- INICIO DEL TRUCO DE LIMPIEZA ---
                # Agregamos 500 filas nulas al final para sobreescribir y "borrar" cualquier equipo viejo que haya quedado abajo
                filas_sobrantes = 500 - len(registros)
                if filas_sobrantes > 0:
                    for _ in range(filas_sobrantes):
                        registros.append({"Equipo": None, "Tipo": None, "Nombre": None})
                        
                nuevo_df = pd.DataFrame(registros)
                if not nuevo_df.empty:
                    # Actualizamos Google Sheets con los datos nuevos + las filas vacías al final
                    conn.update(worksheet="Padron", data=nuevo_df)
                    st.cache_data.clear()
                    st.success("¡Equipos anteriores borrados y nuevo padrón guardado exitosamente!")
                    st.rerun()
                else:
                    st.error("El archivo no contenía información válida.")
                # --- FIN DEL TRUCO DE LIMPIEZA ---
                    
        # 2. CONFIGURACIÓN DE ARQUEROS
        if datos:
            st.divider()
            st.subheader("🛡️ 2. Separar arqueros")
            st.markdown("Selecciona quiénes son los arqueros. Esta configuración quedará protegida en la nube.")
            
            nuevos_arqueros = []
            with st.expander("Desplegar lista de equipos para marcar arqueros"):
                for eq in sorted(datos.keys()):
                    jugs_eq = [f"{j} ({eq})" for j in datos[eq]["jugadores"]]
                    seleccion = st.multiselect(
                        f"Arqueros de {eq}:", 
                        options=jugs_eq, 
                        default=[j for j in jugs_eq if j in arqueros_config]
                    )
                    nuevos_arqueros.extend(seleccion)
                
                if st.button("💾 Guardar configuración de arqueros en la nube", type="primary"):
                    for index, row in df_padron.iterrows():
                        if row["Tipo"] == "Jefe": continue
                        unico = f'{row["Nombre"]} ({row["Equipo"]})'
                        if unico in nuevos_arqueros:
                            df_padron.at[index, "Tipo"] = "Arquero"
                        else:
                            df_padron.at[index, "Tipo"] = "Jugador"
                            
                    conn.update(worksheet="Padron", data=df_padron)
                    st.cache_data.clear()
                    st.success("¡Arqueros actualizados con éxito en Google Sheets!")
                    st.rerun()
                    
        # 3. RESULTADOS EN VIVO
        st.divider()
        st.subheader("📊 3. Resultados en vivo")
        
        if not df_votos.empty:
            col_rank1, col_rank2 = st.columns(2)
            with col_rank1:
                st.markdown("##### 🥇 Ranking de Jugadores")
                votos_j = df_votos[df_votos["Categoria"] == "Jugador de Campo"]["Candidato_Elegido"].value_counts().reset_index()
                st.dataframe(votos_j, hide_index=True)
                
            with col_rank2:
                st.markdown("##### 🧤 Ranking de Arqueros")
                votos_a = df_votos[df_votos["Categoria"] == "Arquero"]["Candidato_Elegido"].value_counts().reset_index()
                st.dataframe(votos_a, hide_index=True)
                
            st.markdown("##### ✔️ Equipos que ya votaron:")
            for jefe in jefes_que_votaron:
                st.write(f"- {jefe}")
        else:
            st.info("Aún no hay votos registrados.")
            
        # 4. GANADORES DEFINITIVOS
        st.divider()
        st.subheader("🏆 Ganadores Finales")
        
        if not df_votos.empty:
            votos_jc = df_votos[df_votos["Categoria"] == "Jugador de Campo"]["Candidato_Elegido"]
            votos_arq = df_votos[df_votos["Categoria"] == "Arquero"]["Candidato_Elegido"]
            
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                if not votos_jc.empty:
                    st.success(f"🏑 **Jugador más votado:**\n\n{votos_jc.value_counts().idxmax()} ({votos_jc.value_counts().max()} votos)")
                else:
                    st.info("Sin votos para jugadores.")
            with col_res2:
                if not votos_arq.empty:
                    st.info(f"🧤 **Arquero más votado:**\n\n{votos_arq.value_counts().idxmax()} ({votos_arq.value_counts().max()} votos)")
                else:
                    st.info("Sin votos para arqueros.")
        else:
            st.warning("No hay votos para calcular a los ganadores.")

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
        st.warning("⏳ La Dirección del Torneo aún no ha cargado los equipos.")
    else:
        lista_equipos = ["-- Seleccionar --"] + sorted(list(datos.keys()))
        
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
                    st.error("🚨 El voto de tu equipo ya fue registrado.")
                else:
                    st.divider()
                    st.subheader("Selección de candidatos")
                    
                    def elegir_candidato(titulo, key, es_arquero=False):
                        eq = st.selectbox(f"Club del {titulo}:", lista_equipos, key=f"eq_{key}")
                        if eq != "-- Seleccionar --":
                            jugs_crudos = datos[eq]["jugadores"]
                            jugs_formateados = [f"{j} ({eq})" for j in jugs_crudos]
                            
                            if es_arquero:
                                opciones = [j for j in jugs_formateados if j in arqueros_config]
                                if not opciones:
                                    st.warning(f"Aún no hay arqueros asignados para {eq}.")
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
                    if st.button("🗳️ Enviar votos al Director/a de Torneo", type="primary", use_container_width=True):
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
                            
                            df_actualizado = pd.concat([df_votos, nuevos_votos], ignore_index=True)
                            conn.update(worksheet="Votos", data=df_actualizado)
                            st.cache_data.clear()
                            
                            st.balloons()
                            st.success("✅ Tus votos han sido enviados.")

# --- FIRMA (Siempre visible al final) ---
st.divider()
st.markdown("<div style='text-align: center; color: gray;'><small>Desarrollado con 💻 por <b>Mariela Rosales</b></small></div>", unsafe_allow_html=True)
