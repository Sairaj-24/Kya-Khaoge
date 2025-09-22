import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
from datetime import datetime
from zoneinfo import ZoneInfo

# --- Page & AI Configuration ---
st.set_page_config(page_title="FoodFinder", page_icon="🍴")

# --- Custom CSS for Chat Bubbles ---
st.markdown("""
<style>
    /* Main container styling */
    .stApp {
        background-color: #F8F0E5; /* Beige background */
    }

    /* --- NEW ---: This creates the chat container box */
    [data-testid="stVerticalBlock"] {
        background-color: white;
        border: 1px solid #EAEAEA;
        border-radius: 20px;
        padding: 2rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    /* ----------- */        
    
    /* Chat bubble styling */
    [data-testid="stChatMessage"] {
        border-radius: 20px;
        padding: 1rem;
        margin-bottom: 1rem;
        overflow-wrap: break-word;
    }

    /* Assistant (bot) message styling */
    [data-testid="stChatMessage"]:has(span[class*="assistant-avatar"]) {
        background-color: #FF6B6B; /* Coral color for bot */
        color: white;
    }

    /* User message styling */
    /* Streamlit uses a different structure for user messages, we target it differently */
    div.st-emotion-cache-1c7y2kd.e154624p4 {
        background-color: #FFFFFF; /* White for user */
        border: 1px solid #EAEAEA;
    }
</style>
""", unsafe_allow_html=True)


try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
except Exception as e:
    st.error("💥 Oops! It seems there's an issue with the AI model configuration. Please check the API key.")
    st.stop()

# --- Helper Functions ---
@st.cache_data
def load_data():
    """Loads food data from the public Google Sheet."""
    try:
        sheet_url = st.secrets["SHEET_URL"]
        df = pd.read_csv(sheet_url)
        return df
    except Exception as e:
        st.error(f"💥 Oops! Having trouble reading the food database. Please check the Google Sheet URL. Error: {e}")
        return pd.DataFrame() # Return empty dataframe on error

def extract_user_info(user_message):
    """Step 1: Extracts structured data from the user's message using Gemini."""
    prompt = f"""
    Extract location, budget (in INR), and food craving from the user's message.
    Respond ONLY with a valid JSON object like {{"location": "...", "budget": ..., "craving": "..."}}.

    RULES:
    - The 'location' is mandatory. If you cannot find a location, set its value to null.
    - **If the user does not mention a 'budget', assume it is 100 INR.**
    - **If the user does not mention a specific 'craving', set the craving to "anything".**

    USER MESSAGE: "{user_message}"
    """
    try:
        response = model.generate_content(prompt)
        # Clean up the response to ensure it's valid JSON
        json_str = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(json_str)
    except (json.JSONDecodeError, Exception) as e:
        st.error(f"Sorry, I had trouble understanding that. Could you be a bit more specific? (Error: {e})")
        return None

def get_recommendations(location, budget, craving, food_data,current_time_str):
    if food_data.empty:
        return "Sorry, the food database is currently unavailable."
    
    # Convert the DataFrame to a clean JSON string. This is much more reliable.
    database_json = food_data.to_json(orient='records', indent=2)

    # --- NEW DYNAMIC INSTRUCTION ---
    if craving.lower() == 'anything':
        craving_instruction = "The user is open to anything, so recommend your most popular, iconic, or must-try dishes suitable for the location and time."
    else:
        craving_instruction = f"The user is in the mood for '{craving}'."
    # -----------------------------
    
    prompt = f"""
    You are 'Food Dost,' a local Mumbaikar friend who knows all the best khau gallis. 
    Your tone should be friendly, casual, and use some Hinglish or Mumbai slang (like 'boss', 'mast', 'ekdum', 'paisa vasool').
    Keep your answers short because the user is hungry.

    A user is near '{location}' with a budget of ₹{budget}.
    It is currently {current_time_str} in Mumbai.
    {craving_instruction}. Use this time context to make your recommendations more relevant (e.g., suggest breakfast in the morning, dinner spots in the evening, or late-night snacks after 10 PM).

    From the JSON DATABASE below, recommend up to 3 of the best options.

    Your goal is to give variety. If the user's budget allows, strongly prioritize recommending dishes from DIFFERENT stalls.

    Respond ONLY with a list. For each recommendation, you MUST use the following format exactly, pulling the real link from the 'gmaps_link' field in the JSON:

    **1. [Dish Name] at [Stall Name]**
    * **Price:** ₹[Price]
    * **Address:** [Landmark], [Location Area]
    * **Why it's Mast:** [A very short, 1-sentence reason why it's a great choice for their specific craving and situation.]
    * **Maps Link:** [Google Maps Link]

    --- JSON DATABASE ---
    {database_json}
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Sorry, boss! Couldn't get a recommendation right now. Error: {e}"
    
    
# --- Main App Logic ---
st.title("Kya Khaoge? Mei bataun?😋")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": "Hello! I'm your Mumbai Food Compass. Tell me your location, budget, and what you're craving, and I'll find the perfect meal for you!"
    }]

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("e.g., I'm near CST, have ₹200 and want something cheesy!"):
    # Add user message to history and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Process user's message
    with st.spinner("Finding your perfect meal..."):
        user_info = extract_user_info(prompt)
        # --- MODIFIED CONDITION: Only location is now mandatory ---
        if user_info and user_info.get("location"):
            now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
            hour = int(now_ist.strftime("%I"))
            time_rest = now_ist.strftime(":%M %p on a %A")
            current_time_str = f"{hour}{time_rest}"

            food_data = load_data()
            recommendation = get_recommendations(
                user_info["location"],
                user_info["budget"],
                user_info["craving"],
                food_data,
                current_time_str
            )
            response_message = recommendation
        else:
            # Updated error message
            response_message = "I'm sorry, I couldn't understand your location. Could you please tell me where you are in Mumbai?"

    # Add assistant response to history and display it
    st.session_state.messages.append({"role": "assistant", "content": response_message})
    with st.chat_message("assistant"):
        st.markdown(response_message)
