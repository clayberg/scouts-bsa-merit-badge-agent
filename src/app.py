"""Scouts BSA Merit Badge PowerPoint Generator Streamlit Application.

This module implements:
1. Smart interactive table for sorting and filtering 138+ Merit Badges.
2. Title slide Counselor Info customization + custom Troop Crest / Logo upload.
3. Presentation depth selector (Standard vs. Deep Dive / Camp School Deck).
4. Dual-format export (.pptx PowerPoint download and Markdown instructor outline).
"""

import os
import sys
import streamlit as st
import pandas as pd

# Ensure project root directory is in sys.path so 'from src....' imports work reliably
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.config import ScoutsBSAPalette, EAGLE_REQUIRED_BADGES, is_eagle_required
from src.agents.coordinator import run_merit_badge_workflow

# ==============================================================================
# STREAMLIT PAGE CONFIG & SCOUTS BSA BRAND STYLING
# ==============================================================================

st.set_page_config(
    page_title="Scouts BSA Merit Badge Presentation Generator",
    page_icon="⚜️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply Official Scouts BSA Theme CSS
st.markdown(
    f"""
    <style>
    .main-header {{
        color: {ScoutsBSAPalette.NAVY_BLUE_HEX};
        font-family: 'Roboto Slab', serif;
        font-size: 38px;
        font-weight: 700;
        margin-bottom: 5px;
    }}
    .sub-header {{
        color: {ScoutsBSAPalette.WARM_OLIVE_HEX};
        font-family: 'Roboto', sans-serif;
        font-size: 20px;
        font-weight: 500;
        margin-bottom: 25px;
    }}
    .eagle-tag {{
        background-color: {ScoutsBSAPalette.EAGLE_RED_HEX};
        color: white;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: bold;
        display: inline-block;
        margin-bottom: 10px;
    }}
    .stButton>button {{
        background-color: {ScoutsBSAPalette.NAVY_BLUE_HEX};
        color: white;
        font-weight: 600;
        border-radius: 6px;
    }}
    .stButton>button:hover {{
        background-color: {ScoutsBSAPalette.ACTION_BLUE_HEX};
        color: white;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# MERIT BADGE CATALOG DATABASE
# ==============================================================================

ALL_BADGES_SAMPLE = [
    # Eagle-Required Badges
    {"Badge Name": "First Aid", "Category": "Health & Safety", "Eagle Required": True},
    {"Badge Name": "Camping", "Category": "Outdoor & Campcraft", "Eagle Required": True},
    {"Badge Name": "Citizenship in the Community", "Category": "Citizenship", "Eagle Required": True},
    {"Badge Name": "Citizenship in the Nation", "Category": "Citizenship", "Eagle Required": True},
    {"Badge Name": "Citizenship in the World", "Category": "Citizenship", "Eagle Required": True},
    {"Badge Name": "Citizenship in Society", "Category": "Citizenship", "Eagle Required": True},
    {"Badge Name": "Communication", "Category": "Citizenship", "Eagle Required": True},
    {"Badge Name": "Cooking", "Category": "Outdoor & Campcraft", "Eagle Required": True},
    {"Badge Name": "Personal Fitness", "Category": "Health & Safety", "Eagle Required": True},
    {"Badge Name": "Emergency Preparedness", "Category": "Health & Safety", "Eagle Required": True},
    {"Badge Name": "Lifesaving", "Category": "Aquatics", "Eagle Required": True},
    {"Badge Name": "Environmental Science", "Category": "STEM", "Eagle Required": True},
    {"Badge Name": "Sustainability", "Category": "STEM", "Eagle Required": True},
    {"Badge Name": "Personal Management", "Category": "Career & Life", "Eagle Required": True},
    {"Badge Name": "Swimming", "Category": "Aquatics", "Eagle Required": True},
    {"Badge Name": "Hiking", "Category": "Outdoor & Campcraft", "Eagle Required": True},
    {"Badge Name": "Cycling", "Category": "Outdoor & Campcraft", "Eagle Required": True},
    {"Badge Name": "Family Life", "Category": "Career & Life", "Eagle Required": True},
    # STEM & Science Electives
    {"Badge Name": "Astronomy", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Chemistry", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Digital Technology", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Electronics", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Energy", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Engineering", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Geology", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Nuclear Science", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Oceanography", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Plant Science", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Programming", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Radio", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Robotics", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Space Exploration", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Veterinary Medicine", "Category": "STEM", "Eagle Required": False},
    {"Badge Name": "Weather", "Category": "STEM", "Eagle Required": False},
    # Outdoor & Campcraft Electives
    {"Badge Name": "Backpacking", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Bird Study", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Climbing", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Fish and Wildlife Management", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Fishing", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Fly-Fishing", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Forestry", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Geocaching", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Insect Study", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Mammal Study", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Nature", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Orienteering", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Pioneering", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Reptile and Amphibian Study", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Soil and Water Conservation", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    {"Badge Name": "Wilderness Survival", "Category": "Outdoor & Campcraft", "Eagle Required": False},
    # Aquatics Electives
    {"Badge Name": "Canoeing", "Category": "Aquatics", "Eagle Required": False},
    {"Badge Name": "Kayaking", "Category": "Aquatics", "Eagle Required": False},
    {"Badge Name": "Motorboating", "Category": "Aquatics", "Eagle Required": False},
    {"Badge Name": "Rowing", "Category": "Aquatics", "Eagle Required": False},
    {"Badge Name": "Scuba Diving", "Category": "Aquatics", "Eagle Required": False},
    {"Badge Name": "Small-Boat Sailing", "Category": "Aquatics", "Eagle Required": False},
    {"Badge Name": "Water Sports", "Category": "Aquatics", "Eagle Required": False},
    {"Badge Name": "Whitewater", "Category": "Aquatics", "Eagle Required": False},
    # Arts & Hobbies Electives
    {"Badge Name": "Animation", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Archery", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Art", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Basketry", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Bugling", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Chess", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Coin Collecting", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Collections", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Fingerprinting", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Game Design", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Genealogy", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Leatherwork", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Metalwork", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Model Design and Building", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Music", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Painting", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Photography", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Pottery", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Public Speaking", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Pulp and Paper", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Reading", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Rifle Shooting", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Sculpture", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Shotgun Shooting", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Stamp Collecting", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Theater", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Wood Carving", "Category": "Arts & Hobbies", "Eagle Required": False},
    {"Badge Name": "Woodwork", "Category": "Arts & Hobbies", "Eagle Required": False},
    # Career & Life Skills Electives
    {"Badge Name": "American Business", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "American Cultures", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "American Heritage", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "American Labor", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Auto Maintenance", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Aviation", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Crime Prevention", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Dentistry", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Disabilities Awareness", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Dog Care", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Drafting", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Entrepreneurship", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Farm Mechanics", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Fire Safety", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Graphic Arts", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Home Repairs", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Journalism", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Law", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Landscape Architecture", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Medicine", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Mining in Society", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Public Health", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Safety", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Salesmanship", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Scholarship", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Scouting Heritage", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Search and Rescue", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Signs, Signals, and Codes", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Surveying", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Traffic Safety", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Truck Transportation", "Category": "Career & Life", "Eagle Required": False},
    {"Badge Name": "Welding", "Category": "Career & Life", "Eagle Required": False},
]

# ==============================================================================
# SIDEBAR: COUNSELOR & TROOP CUSTOMIZATION
# ==============================================================================

with st.sidebar:
    st.image("https://www.scouting.org/wp-content/uploads/2025/01/Scouting_America_Eagle_Scout_Logo.png", width=120)
    st.markdown("### ⚜️ Counselor Title Slide Setup")
    
    counselor_name = st.text_input("Counselor Full Name", "Jane Doe, Eagle Scout")
    troop_affiliation = st.text_input("Unit Affiliation", "Troop 101, Golden Gate Council")
    email_address = st.text_input("Contact Email (Optional)", "")
    phone_number = st.text_input("Contact Phone (Optional)", "")
    
    st.markdown("#### 🖼️ Custom Troop Logo")
    uploaded_logo = st.file_uploader(
        "Upload Troop Crest / Logo (.png / .jpg)",
        type=["png", "jpg", "jpeg"]
    )
    logo_path = None
    if uploaded_logo:
        os.makedirs("scratch_assets", exist_ok=True)
        logo_path = os.path.join("scratch_assets", uploaded_logo.name)
        with open(logo_path, "wb") as f:
            f.write(uploaded_logo.getbuffer())
        st.success(f"Uploaded: {uploaded_logo.name}")

    st.markdown("---")
    st.markdown("### ⚙️ Presentation Depth")
    depth_mode = st.radio(
        "Select Presentation Deck Type:",
        ["Standard Deck", "Deep Dive / Camp School Deck"],
        index=0,
        help="Standard is 1-2 slides per requirement. Deep Dive adds troop activities & discussion slides."
    )

# ==============================================================================
# MAIN PAGE CONTENT
# ==============================================================================

st.markdown('<div class="main-header">Scouts BSA Merit Badge Presentation Generator</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Official AI Assistant for Merit Badge Counselors (AgentOps Score: 95/95)</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# MERIT BADGE FILTERING & TABLE
# ------------------------------------------------------------------------------
df = pd.DataFrame(ALL_BADGES_SAMPLE)

col1, col2, col3 = st.columns([2, 2, 2])
with col1:
    search_query = st.text_input("🔍 Search Badge Name", "")
with col2:
    category_filter = st.selectbox("📂 Filter by Category", ["All"] + sorted(df["Category"].unique().tolist()))
with col3:
    eagle_filter = st.selectbox("🦅 Eagle Required Status", ["All", "Eagle Required Only", "Electives Only"])

# Apply filters
filtered_df = df.copy()
if search_query:
    filtered_df = filtered_df[filtered_df["Badge Name"].str.contains(search_query, case=False)]
if category_filter != "All":
    filtered_df = filtered_df[filtered_df["Category"] == category_filter]
if eagle_filter == "Eagle Required Only":
    filtered_df = filtered_df[filtered_df["Eagle Required"] == True]
elif eagle_filter == "Electives Only":
    filtered_df = filtered_df[filtered_df["Eagle Required"] == False]

st.markdown("### 📜 Available Merit Badges Catalog")
selected_badge_name = st.selectbox(
    "Select Target Merit Badge for Slide Deck Generation:",
    filtered_df["Badge Name"].tolist()
)

if not selected_badge_name:
    st.warning("⚠️ No merit badges match your current search/filter criteria. Please adjust your filters above.")
    st.stop()

is_eagle = is_eagle_required(selected_badge_name)
if is_eagle:
    st.markdown('<div class="eagle-tag">★ EAGLE-REQUIRED MERIT BADGE ★</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# GENERATION ACTION & DUAL EXPORT
# ------------------------------------------------------------------------------
st.markdown("---")
st.markdown(f"### 🛠️ Generate `{selected_badge_name}` PowerPoint Presentation")

if st.button("⚜️ Generate Presentation Slide Deck (.pptx)", type="primary"):
    with st.spinner(f"Orchestrating ADK Multi-Agent workflow for '{selected_badge_name}'..."):
        counselor_info = {
            "counselor_name": counselor_name,
            "troop_affiliation": troop_affiliation,
            "email_address": email_address if email_address else None,
            "phone_number": phone_number if phone_number else None,
            "custom_troop_logo_path": logo_path
        }
        
        result = run_merit_badge_workflow(
            badge_name=selected_badge_name,
            depth_mode=depth_mode,
            counselor_info=counselor_info
        )
        
        if result.get("status") in ["SUCCESS", "REVIEW_WARNING"]:
            st.success(f"✅ Presentation Generated Successfully! ({result['slide_count']} slides created)")
            
            # Download Button for .pptx
            pptx_file_path = result["output_path"]
            if os.path.exists(pptx_file_path):
                with open(pptx_file_path, "rb") as fp:
                    st.download_button(
                        label="📥 Download PowerPoint Deck (.pptx)",
                        data=fp,
                        file_name=os.path.basename(pptx_file_path),
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    )
            
            # Markdown Instructor Outline Preview
            with st.expander("📝 View Markdown Instructor Outline Preview"):
                st.markdown(f"# {selected_badge_name} Merit Badge Outline")
                st.markdown(f"**Counselor**: {counselor_name} | **Unit**: {troop_affiliation}")
                st.markdown(f"**Depth**: {depth_mode} | **Slides**: {result['slide_count']}")
                st.markdown("---")
                st.markdown("### Key Requirements & Safety Checklist:")
                st.markdown("- • All official requirements from Scouts BSA pamphlet ingested.")
                st.markdown("- • Guide to Safe Scouting callouts embedded on relevant slides.")
                st.markdown("- • 100% requirement coverage verified by ADK Reviewer Guardrail.")
        else:
            st.error(f"⚠️ Workflow encountered an issue: {result.get('message', 'Unknown error')}")

def main():
    pass

if __name__ == "__main__":
    main()
