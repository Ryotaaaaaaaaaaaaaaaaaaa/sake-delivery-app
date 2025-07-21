import streamlit as st
import pandas as pd
import googlemaps
import folium
from streamlit_folium import st_folium
from googlemaps import convert
import datetime
import urllib.parse

# --- アプリの基本設定 ---
st.set_page_config(page_title="最適配達ルート計算アプリ", layout="wide")
st.title("最適配達ルート計算アプリ 🚚")

# --- セッション管理の初期化 ---
if 'map_figure' not in st.session_state:
    st.session_state.map_figure = None
if 'route_text' not in st.session_state:
    st.session_state.route_text = None
if 'Maps_url' not in st.session_state:
    st.session_state.Maps_url = None

# --- APIキーの設定 ---
try:
    API_KEY = st.secrets["Maps_API_KEY"]
except (FileNotFoundError, KeyError):
    API_KEY = st.sidebar.text_input("Google Maps APIキー", type="password")

# --- ファイルアップロード機能 ---
st.header("1. 顧客リストをアップロード")
uploaded_file = st.file_uploader(
    "座標付きの顧客リスト（customers_with_coords.csv）を選択してください", 
    type=['csv']
)

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
    except Exception as e:
        st.error(f"ファイルの読み込みに失敗しました: {e}")
        st.stop()

    with st.form(key='customer_selection_form'):
        st.header("2. 今日の配達先を選択")
        selected_customers = []
        for customer in df['name'].tolist():
            if st.checkbox(customer, key=customer):
                selected_customers.append(customer)
        
        st.header("3. ルートを計算")
        start_address = st.text_input("出発地の住所", "京都府京都市左京区田中野神町６−１７")
        
        submit_button = st.form_submit_button(label="最適ルートを計算する")

    if submit_button:
        if not API_KEY:
            st.warning("APIキーを入力してください。")
        elif not selected_customers:
            st.warning("配達先を1つ以上選択してください。")
        else:
            with st.spinner("ルートを計算中です..."):
                try:
                    gmaps = googlemaps.Client(key=API_KEY)
                    
                    df_selected = df[df['name'].isin(selected_customers)].copy()
                    df_selected['coords_tuple'] = df_selected['coords'].apply(lambda x: tuple(map(float, x.split(','))))

                    start_geocode = gmaps.geocode(start_address)[0]
                    start_coords = (start_geocode['geometry']['location']['lat'], start_geocode['geometry']['location']['lng'])
                    
                    waypoints = list(df_selected['coords_tuple'])

                    directions_result = gmaps.directions(
                        origin=start_coords,
                        destination=start_coords,
                        waypoints=waypoints,
                        optimize_waypoints=True,
                        departure_time=datetime.datetime.now()
                    )
                    
                    if directions_result:
                        st.success("ルート計算が完了しました！")
                        
                        m = folium.Map(location=start_coords, zoom_start=12)
                        encoded_polyline = directions_result[0]['overview_polyline']['points']
                        decoded_points = convert.decode_polyline(encoded_polyline)
                        route_path = [(p['lat'], p['lng']) for p in decoded_points]
                        folium.PolyLine(locations=route_path, color='blue', weight=5, opacity=0.7).add_to(m)

                        optimized_order = directions_result[0]['waypoint_order']
                        
                        folium.Marker(location=start_coords, popup='<b>出発点</b>', icon=folium.Icon(color='red', icon='home')).add_to(m)
                        
                        route_text_list = ["出発点"]
                        # ★★★ GoogleマップURL用の経由地リストを作成 ★★★
                        waypoints_for_url = []
                        for i, idx in enumerate(optimized_order):
                            customer = df_selected.iloc[idx]
                            folium.Marker(
                                location=customer['coords_tuple'],
                                popup=f"<b>{i+1}. {customer['name']}</b><br>{customer['address']}",
                                icon=folium.Icon(color='blue', icon='info-sign')
                            ).add_to(m)
                            route_text_list.append(f"**{i+1}. {customer['name']}**")
                            # 経由地の座標をリストに追加
                            waypoints_for_url.append(f"{customer['coords_tuple'][0]},{customer['coords_tuple'][1]}")
                        
                        route_text_list.append("帰着")
                        
                        # ★★★ GoogleマップのURLを生成 ★★★
                        base_url = "https://www.google.com/maps/dir/?api=1"
                        origin_param = f"&origin={start_coords[0]},{start_coords[1]}"
                        destination_param = f"&destination={start_coords[0]},{start_coords[1]}"
                        waypoints_param = "&waypoints=" + "|".join(waypoints_for_url)
                        Maps_url = base_url + origin_param + destination_param + waypoints_param
                        
                        # 計算結果をセッションに保存
                        st.session_state.route_text = " → ".join(route_text_list)
                        st.session_state.map_figure = m
                        st.session_state.Maps_url = Maps_url

                    else:
                        st.error("ルートが見つかりませんでした。")
                        st.session_state.Maps_url = None

                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
                    st.session_state.Maps_url = None

# --- セッションに保存された結果を表示 ---
if st.session_state.get('map_figure'):
    st.header("計算結果")
    st.subheader("最適な訪問順")
    st.markdown(st.session_state.route_text)
    
    # ★★★ Googleマップへのリンクを表示 ★★★
    if st.session_state.get('Maps_url'):
        st.markdown(f"### [🗺️ Googleマップでナビゲーションを開始する]({st.session_state.Maps_url})")
        st.info("スマートフォンで上のリンクをタップすると、Googleマップアプリでルートが開きます。")

    st.subheader("ルートマップ")
    st_folium(st.session_state.map_figure, width=1200, height=600, returned_objects=[])