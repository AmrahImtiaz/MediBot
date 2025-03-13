import streamlit as st
import google.generativeai as genai
import folium
import requests
import json
from streamlit_folium import folium_static

# Configure API key
def configure_genai(api_key):
    genai.configure(api_key=api_key)

# Generate response using Gemini API
def get_ai_response(user_input, conversation_history, model):
    # Create prompt with medical context
    full_prompt = f"""
    You are an AI medical assistant. You can provide general medical information and suggestions, 
    but you should always clarify that you're not a licensed medical professional and your advice 
    should not replace professional medical consultation.
    
    Based on the following symptoms, provide:
    1. Possible causes
    2. Recommended next steps
    3. When they should seek immediate medical attention
    
    User's symptoms: {user_input}
    
    Previous conversation for context:
    {conversation_history}
    """
    
    try:
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"Error generating response: {str(e)}"

# Get nearby hospitals using OpenStreetMap API
def get_nearby_hospitals(latitude, longitude, radius=5000):
    overpass_url = "https://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    node["amenity"="hospital"](around:{radius},{latitude},{longitude});
    out body;
    """
    
    try:
        response = requests.post(overpass_url, data=overpass_query)
        data = response.json()
        hospitals = []
        
        for element in data.get("elements", []):
            if "tags" in element and "name" in element["tags"]:
                hospitals.append({
                    "name": element["tags"].get("name", "Unnamed Hospital"),
                    "phone": element["tags"].get("phone", "N/A"),
                    "lat": element["lat"],
                    "lon": element["lon"],
                    "address": element["tags"].get("addr:full", "Address not available")
                })
        
        return hospitals
    except Exception as e:
        st.error(f"Error fetching hospital data: {str(e)}")
        return []

# Function to get available models
def list_available_models():
    try:
        models = genai.list_models()
        model_names = [model.name for model in models]
        return model_names
    except Exception as e:
        return [f"Error listing models: {str(e)}"]

# Main function
def main():
    st.set_page_config(page_title="AI Doctor Assistant", page_icon="🏥", layout="wide")
    
    st.title("AI Doctor Assistant")
    st.markdown("Describe your symptoms and get potential information about your condition.")
    
    # Sidebar for API configuration
    with st.sidebar:
        st.header("Configuration")
        api_key = st.text_input("Enter your Gemini API Key", type="password")
        
        # Model selection
        model_name = st.selectbox(
            "Select Gemini Model", 
            ["gemini-1.0-pro", "gemini-1.5-pro", "gemini-1.5-flash"]
        )
        
        st.markdown("---")
        st.header("Disclaimer")
        st.info("""This app provides general health information and is not a substitute for 
                professional medical advice, diagnosis, or treatment. Always seek the advice 
                of your physician or other qualified health provider.""")
        
        # User location for hospital search
        st.header("Find Nearby Hospitals")
        latitude = st.number_input("Latitude", value=37.7749, format="%.6f")
        longitude = st.number_input("Longitude", value=-122.4194, format="%.6f")
        radius = st.slider("Search Radius (meters)", 1000, 10000, 5000)
        
        # Debug section
        if api_key:
            if st.button("List Available Models"):
                configure_genai(api_key)
                available_models = list_available_models()
                st.write("Available models:")
                for m in available_models:
                    st.write(f"- {m}")
    
    # Initialize or get conversation history from session state
    if "conversation" not in st.session_state:
        st.session_state.conversation = []
    
    # Display conversation history
    for i, (role, message) in enumerate(st.session_state.conversation):
        if role == "user":
            st.markdown(f"<div style='background-color: #E8F0FE; padding: 10px; border-radius: 10px; margin-bottom: 10px;'><b>You:</b> {message}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='background-color: #F0F2F5; padding: 10px; border-radius: 10px; margin-bottom: 10px;'><b>AI Doctor:</b> {message}</div>", unsafe_allow_html=True)
    
    # Input for new messages
    user_input = st.text_area("Describe your symptoms:", height=100)
    
    # Process input when user submits
    if st.button("Send"):
        if not api_key:
            st.error("Please enter your Gemini API Key in the sidebar.")
            return
        
        if user_input:
            # Add user message to conversation
            st.session_state.conversation.append(("user", user_input))
            
            try:
                # Configure Gemini API
                configure_genai(api_key)
                
                # Create model with selected name
                model = genai.GenerativeModel(model_name)
                
                # Format conversation history for context
                conversation_context = "\n".join([f"{'User' if role == 'user' else 'AI'}: {msg}" for role, msg in st.session_state.conversation[:-1]])
                
                # Get AI response
                response = get_ai_response(user_input, conversation_context, model)
                
                # Add AI response to conversation
                st.session_state.conversation.append(("ai", response))
                
                # Use st.rerun() instead of experimental_rerun
                st.rerun()
                
            except Exception as e:
                error_message = f"Error: {str(e)}"
                st.session_state.conversation.append(("ai", error_message))
                st.error(error_message)
    
    # Hospital finder section
    st.markdown("---")
    st.header("Nearby Hospitals")
    
    if st.button("Find Nearby Hospitals"):
        if latitude and longitude:
            hospitals = get_nearby_hospitals(latitude, longitude, radius)
            
            if hospitals:
                # Create map
                m = folium.Map(location=[latitude, longitude], zoom_start=13)
                folium.Marker([latitude, longitude], tooltip="Your Location").add_to(m)
                
                # Add hospital markers
                for hospital in hospitals:
                    folium.Marker(
                        [hospital["lat"], hospital["lon"]],
                        popup=f"""
                        <b>{hospital['name']}</b><br>
                        Phone: {hospital['phone']}<br>
                        Address: {hospital['address']}
                        """,
                        tooltip=hospital["name"],
                        icon=folium.Icon(color="red", icon="plus")
                    ).add_to(m)
                
                # Display map
                folium_static(m)
                
                # Display hospital list
                st.subheader("Hospital List")
                for i, hospital in enumerate(hospitals):
                    st.markdown(f"""
                    **{i+1}. {hospital['name']}**  
                    📞 {hospital['phone']}  
                    📍 {hospital['address']}  
                    """)
                    if hospital["phone"] != "N/A":
                        st.markdown(f"[Call Hospital](tel:{hospital['phone']})")
                    st.markdown("---")
            else:
                st.info("No hospitals found in the selected area. Try increasing the radius.")
        else:
            st.error("Please enter valid latitude and longitude.")

if __name__ == "__main__":
    main()