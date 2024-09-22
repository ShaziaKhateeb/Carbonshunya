import streamlit as st
import ee
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import requests
from PIL import Image
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

ee.Initialize(project="ee-ad8176178")

st.set_page_config(page_title="Carbon शून्य", layout="wide")

st.title("🍃 Carbon शून्य :  Carbon Emission Analyzer")

with st.sidebar:
    st.header("User Input")
    location = st.text_input("📍 Enter your location:")
    radius = st.slider("Select radius (in km):", 1, 10, 5)

def fetch_carbon_emission(lat, lon, api_key):
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={api_key}"
    try:
        response = requests.get(url)
        data = response.json()
        if data.get('status') == 'ok':
            aqi = data['data']['aqi']
            return aqi
        else:
            return 0
    except Exception as e:
        st.error(f"Error fetching carbon emission data: {e}")
        return 0

if location:
    geolocator = Nominatim(user_agent="geoapi")
    loc = geolocator.geocode(location)
    
    if loc:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📍 Location Details")
            st.write(f"**Latitude:** {loc.latitude}")
            st.write(f"**Longitude:** {loc.longitude}")
        
        with col2:
            st.subheader("🕹️ Analysis Radius")
            st.write(f"**Radius:** {radius} km")
        
        st.markdown("---")
        st.subheader("🗺️ Map View of the Selected Area")

        m = folium.Map(location=[loc.latitude, loc.longitude], zoom_start=12)
        
        folium.Circle(
            location=[loc.latitude, loc.longitude],
            radius=radius * 1000,
            color='blue',
            fill=True,
            fill_opacity=0.2
        ).add_to(m)
        
        st_data = st_folium(m, width=700, height=500)

        def get_ndvi_image(lat, lon, radius_km):
            point = ee.Geometry.Point(lon, lat)
            buffer = point.buffer(radius_km * 1000)
            
            image = ee.ImageCollection('COPERNICUS/S2') \
                        .filterBounds(buffer) \
                        .filterDate('2023-01-01', '2023-12-31') \
                        .sort('CLOUDY_PIXEL_PERCENTAGE') \
                        .first()
            
            ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
            ndvi_clip = ndvi.clip(buffer)
            
            return ndvi_clip

        ndvi_image = get_ndvi_image(loc.latitude, loc.longitude, radius)

        ndvi_params = {
            'min': 0, 'max': 1,
            'dimensions': 512,
            'region': ndvi_image.geometry(),
            'format': 'png',
            'palette': ['white', 'lightgreen', 'green']
        }
        ndvi_url = ndvi_image.getThumbURL(ndvi_params)

        response = requests.get(ndvi_url)
        img = Image.open(BytesIO(response.content))

        st.markdown("---")
        st.subheader("🌳 NDVI Image of the Selected Area")
        st.write("The NDVI (Normalized Difference Vegetation Index) shows the health of vegetation in the region, with green representing healthy vegetation.")
        st.image(img, caption="NDVI Image", use_column_width=True)

        def get_tree_cover(lat, lon, radius_km):
            point = ee.Geometry.Point(lon, lat)
            buffer = point.buffer(radius_km * 1000)

            dataset = ee.ImageCollection('MODIS/006/MOD44B').select('Percent_Tree_Cover').first()
            tree_cover = dataset.clip(buffer)

            stats = tree_cover.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffer,
                scale=250,
                maxPixels=1e9
            )
            return stats.getInfo()

        tree_cover_data = get_tree_cover(loc.latitude, loc.longitude, radius)
        tree_cover_percentage = tree_cover_data.get('Percent_Tree_Cover', 0)

        st.markdown("---")
        st.subheader("🌲 Tree Cover Data")
        st.write(f"The tree cover percentage for the selected area is approximately **{tree_cover_percentage:.2f}%**.")

        api_key = '9cfe2efc8f363de323a83be47767974df1135754'
        carbon_emission = fetch_carbon_emission(loc.latitude, loc.longitude, api_key)

        st.markdown("---")
        st.subheader("📊 Carbon Emission Data")
        st.write(f"Carbon emission (AQI): {carbon_emission}")

        def calculate_carbon_score(tree_cover, carbon_emission):
            CO2_SEQUESTER_PER_PERCENT_TREE_COVER = 0.015
            AQI_TO_CO2_CONVERSION_FACTOR = 0.001

            carbon_sequestration = tree_cover * CO2_SEQUESTER_PER_PERCENT_TREE_COVER
            carbon_emission_tonnes = carbon_emission * AQI_TO_CO2_CONVERSION_FACTOR
            
            score = carbon_sequestration - carbon_emission_tonnes
            return score
        
        

        carbon_score = calculate_carbon_score(tree_cover_percentage, carbon_emission)

        st.markdown("---")
        st.subheader("📊 Carbon Emission Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Emissions (tonnes CO2)", f"{carbon_emission * 0.001:.2f}")
        with col2:
            st.metric("Tree Cover (%)", f"{tree_cover_percentage:.2f}")
        
        st.subheader(f"🌍 Carbon Credit Score: {carbon_score:.2f} tonnes CO2")

        st.markdown("---")
        st.subheader("📈 Visualizations")

        df = pd.DataFrame({
            'Category': ['Carbon Sequestration', 'Carbon Emission'],
            'Value': [carbon_score + carbon_emission * 0.001, carbon_emission * 0.001]
        })
        fig = px.bar(df, x='Category', y='Value', title='Carbon Sequestration vs. Carbon Emission', labels={'Value': 'Tonnes CO2'})
        st.plotly_chart(fig)

        st.markdown("---")
        st.subheader("🍰 Carbon Sources and Sinks")

        sources_and_sinks = {
            'Carbon Sequestration': carbon_score + carbon_emission * 0.001,
            'Carbon Emission': carbon_emission * 0.001
        }
        pie_df = pd.DataFrame(list(sources_and_sinks.items()), columns=['Category', 'Value'])
        fig_pie = px.pie(pie_df, names='Category', values='Value', title='Carbon Sources and Sinks')
        st.plotly_chart(fig_pie)

        st.markdown("---")
        st.subheader("📆 NDVI and Tree Cover Over Time")

        dates = pd.date_range(start='2023-01-01', periods=12, freq='ME')
        ndvi_values = [0.3 + 0.01 * i for i in range(12)]
        tree_cover_values = [tree_cover_percentage + 0.2 * i for i in range(12)]

        df_time_series = pd.DataFrame({
            'Date': dates,
            'NDVI': ndvi_values,
            'Tree Cover (%)': tree_cover_values
        })

        fig_time_series = go.Figure()
        fig_time_series.add_trace(go.Scatter(x=df_time_series['Date'], y=df_time_series['NDVI'], mode='lines+markers', name='NDVI'))
        fig_time_series.add_trace(go.Scatter(x=df_time_series['Date'], y=df_time_series['Tree Cover (%)'], mode='lines+markers', name='Tree Cover (%)'))
        fig_time_series.update_layout(title='NDVI and Tree Cover Over Time', xaxis_title='Date', yaxis_title='Value', template='plotly_white')
        st.plotly_chart(fig_time_series)

        st.markdown("---")
        st.subheader("💡 Recommendations")

        if carbon_score > 0:
            st.write("### 🌿 Your region is a carbon sink! Continue to preserve and enhance the forest cover to maintain or increase your carbon credit score.")
        else:
            st.write("### ⚠️ Your region is a carbon source. Consider the following actions to lower the carbon footprint:")
            st.write("- **Increase Tree Planting:** Consider planting more trees to increase the carbon sequestration capacity.")
            st.write("- **Improve Forest Management:** Enhance forest health and management practices to boost carbon storage.")
            st.write("- **Adopt Sustainable Practices:** Reduce emissions through sustainable agriculture, waste management, and energy practices.")
            st.write("- **Engage with Local Communities:** Educate and involve local communities in conservation efforts and sustainability practices.")
