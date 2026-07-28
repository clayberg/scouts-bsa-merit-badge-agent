"""Educational Graphic and Diagram Generator for Scouts BSA Presentations.

This module generates high-resolution, pedagogical diagrams (PNG format) using
matplotlib for insertion into generated PowerPoint slide decks.

Includes specific diagrams for:
- Weather: Water Cycle (Evaporation, Condensation, Precipitation, Runoff)
- Weather: Cloud Types & Thunderstorm Safety
- First Aid: 4-Step CPR & AED Process
- First Aid: Bleeding Control & Shock Management
- Camping: Leave No Trace Seven Principles
- Cooking: MyPlate Balanced Camp Menu Nutrition
- Universal: 4-Pillar Competency Infographic for any elective badge
"""

import os
from typing import Optional
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for headless/server execution
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from src.config import ScoutsBSAPalette

DIAGRAMS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "diagrams"))
os.makedirs(DIAGRAMS_DIR, exist_ok=True)

def generate_water_cycle_diagram() -> str:
    """Generates an educational graphic illustrating the Water Cycle for the Weather Merit Badge."""
    out_path = os.path.join(DIAGRAMS_DIR, "water_cycle_diagram.png")
    if os.path.exists(out_path):
        return out_path
        
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
    ax.set_facecolor("#F2F4F7")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    
    # Title
    ax.text(5, 9.3, "The Earth's Water Cycle", fontsize=18, fontweight="bold",
            color=ScoutsBSAPalette.NAVY_BLUE_HEX, ha="center")
    
    # Ocean / Body of Water at bottom right
    ocean = patches.Rectangle((4, 0), 6, 2.5, facecolor="#005AE0", alpha=0.4, edgecolor=None)
    ax.add_patch(ocean)
    ax.text(7, 1.2, "Ocean / Lake\n(Surface Water)", fontsize=11, fontweight="bold", color="#003F87", ha="center")
    
    # Mountain / Land at bottom left
    mountain = patches.Polygon([[0, 0], [4, 0], [2, 4.5]], facecolor="#4B5320", alpha=0.6)
    ax.add_patch(mountain)
    ax.text(1.8, 1.5, "Land / Mountain\n(Runoff & Infiltration)", fontsize=10, fontweight="bold", color="white", ha="center")
    
    # Cloud (Condensation) at top
    cloud1 = patches.Ellipse((3.5, 7.5), 3.0, 1.4, facecolor="white", edgecolor="#003F87", lw=2)
    cloud2 = patches.Ellipse((6.5, 7.5), 3.2, 1.5, facecolor="white", edgecolor="#003F87", lw=2)
    ax.add_patch(cloud1)
    ax.add_patch(cloud2)
    ax.text(5, 7.5, "CONDENSATION\n(Cloud Formation)", fontsize=11, fontweight="bold", color="#003F87", ha="center")
    
    # Arrows
    # 1. Evaporation (up from ocean)
    ax.annotate("", xy=(7.5, 6.5), xytext=(7.5, 3.0),
                arrowprops=dict(arrowstyle="->", lw=3, color="#005AE0"))
    ax.text(8.3, 4.8, "1. EVAPORATION\n(Solar Heat)", fontsize=10, fontweight="bold", color="#005AE0")
    
    # 2. Precipitation (down from clouds over mountain)
    ax.annotate("", xy=(2.5, 4.5), xytext=(3.2, 6.5),
                arrowprops=dict(arrowstyle="->", lw=3, color="#CE1126"))
    ax.text(1.2, 5.5, "2. PRECIPITATION\n(Rain / Snow)", fontsize=10, fontweight="bold", color="#CE1126")
    
    # 3. Runoff (down slope to ocean)
    ax.annotate("", xy=(5.5, 2.0), xytext=(2.8, 2.5),
                arrowprops=dict(arrowstyle="->", lw=3, color="#4B5320"))
    ax.text(4.0, 2.8, "3. SURFACE RUNOFF\n& TRANSPIRATION", fontsize=10, fontweight="bold", color="#4B5320")
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    return out_path

def generate_cloud_types_diagram() -> str:
    """Generates a diagram showing Cirrus, Altostratus, Stratus, and Cumulonimbus cloud types."""
    out_path = os.path.join(DIAGRAMS_DIR, "cloud_types_diagram.png")
    if os.path.exists(out_path):
        return out_path
        
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
    ax.set_facecolor("#E8F0FE")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    
    ax.text(5, 9.3, "Scouts BSA Meteorology: Major Cloud Types", fontsize=16, fontweight="bold",
            color=ScoutsBSAPalette.NAVY_BLUE_HEX, ha="center")
    
    # High Altitude (Cirrus)
    ax.text(2, 7.8, "HIGH ALTITUDE (>20,000 ft)\nCirrus (Wispy, Ice Crystals)", fontsize=11,
            fontweight="bold", color="#003F87", bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.9))
            
    # Mid Altitude (Altocumulus)
    ax.text(2, 5.5, "MID ALTITUDE (6,500-20,000 ft)\nAltocumulus / Altostratus (Changing Weather)", fontsize=11,
            fontweight="bold", color="#005AE0", bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.9))
            
    # Low Altitude (Stratus/Cumulus)
    ax.text(2, 3.2, "LOW ALTITUDE (<6,500 ft)\nCumulus (Fair) / Stratus (Overcast/Fog)", fontsize=11,
            fontweight="bold", color="#4B5320", bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.9))
            
    # Vertical Storm (Cumulonimbus)
    ax.text(7.5, 5.0, "⚠️ CUMULONIMBUS\nThunderstorm & Lightning\nSeek Ground Shelter!", fontsize=11,
            fontweight="bold", color="#CE1126", ha="center",
            bbox=dict(boxstyle="round,pad=0.8", facecolor="#FCE8E6", edgecolor="#CE1126", lw=2))
            
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    return out_path

def generate_cpr_steps_diagram() -> str:
    """Generates an emergency First Aid CPR and AED 4-step infographic."""
    out_path = os.path.join(DIAGRAMS_DIR, "cpr_steps_diagram.png")
    if os.path.exists(out_path):
        return out_path
        
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    
    ax.text(5, 9.2, "Emergency First Aid: 4-Step CPR & AED Action Plan", fontsize=16, fontweight="bold",
            color=ScoutsBSAPalette.NAVY_BLUE_HEX, ha="center")
            
    steps = [
        ("1. SCENE SAFETY & PPE", "Check scene for hazards.\nWear latex/nitrile gloves.\nTap & shout to test response.", "#003F87", 2.5, 6.8),
        ("2. CALL 911 & GET AED", "Direct a specific buddy:\n'Call 911 and bring the AED!'\nCheck pulse & breathing.", "#005AE0", 7.5, 6.8),
        ("3. 30 COMPRESSIONS", "Center of chest (nipple line).\nPush hard & fast (100-120 bpm).\nAt least 2 inches deep.", "#CE1126", 2.5, 2.5),
        ("4. 2 RESCUE BREATHS", "Head-tilt / chin-lift airway.\n1 second per breath.\nContinue 30:2 until AED/EMS.", "#4B5320", 7.5, 2.5),
    ]
    
    for title, desc, color, x, y in steps:
        box = patches.FancyBboxPatch((x-2.1, y-1.6), 4.2, 3.0, boxstyle="round,pad=0.2",
                                     facecolor="white", edgecolor=color, lw=2.5)
        ax.add_patch(box)
        ax.text(x, y+0.8, title, fontsize=11, fontweight="bold", color=color, ha="center")
        ax.text(x, y-0.3, desc, fontsize=10, color="#212121", ha="center")
        
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    return out_path

def generate_first_aid_bleeding_diagram() -> str:
    """Generates an infographic showing Severe Bleeding Control and Shock Management."""
    out_path = os.path.join(DIAGRAMS_DIR, "first_aid_bleeding_diagram.png")
    if os.path.exists(out_path):
        return out_path
        
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    
    ax.text(5, 9.2, "First Aid Protocol: Severe Bleeding & Shock Control", fontsize=16, fontweight="bold",
            color=ScoutsBSAPalette.NAVY_BLUE_HEX, ha="center")
            
    boxes = [
        ("1. DIRECT PRESSURE", "Apply sterile gauze pad.\nPress firmly with both hands.\nDo NOT remove blood-soaked pads.", "#003F87", 5, 7.3),
        ("2. PRESSURE BANDAGE", "Wrap roller gauze tightly.\nMaintain continuous pressure.\nCheck distal pulse & warmth.", "#005AE0", 5, 4.5),
        ("3. TOURNIQUET & SHOCK", "For life-threatening limb bleeding:\nPlace 2-3 inches above wound.\nLay scout down, elevate feet, blanket.", "#CE1126", 5, 1.7),
    ]
    
    for title, desc, color, x, y in boxes:
        box = patches.FancyBboxPatch((x-4.0, y-1.0), 8.0, 2.0, boxstyle="round,pad=0.2",
                                     facecolor="white", edgecolor=color, lw=2)
        ax.add_patch(box)
        ax.text(x-1.8, y, title, fontsize=12, fontweight="bold", color=color, ha="center")
        ax.text(x+1.8, y, desc, fontsize=10, color="#212121", ha="center")
        
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    return out_path

def generate_leave_no_trace_diagram() -> str:
    """Generates a Leave No Trace Seven Principles infographic for the Camping Merit Badge."""
    out_path = os.path.join(DIAGRAMS_DIR, "leave_no_trace_diagram.png")
    if os.path.exists(out_path):
        return out_path
        
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
    ax.set_facecolor("#F2F4F7")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    
    ax.text(5, 9.3, "Camping Merit Badge: Leave No Trace Seven Principles", fontsize=15, fontweight="bold",
            color=ScoutsBSAPalette.NAVY_BLUE_HEX, ha="center")
            
    principles = [
        "1. Plan Ahead and Prepare (Check weather, permits, regulations)",
        "2. Travel and Camp on Durable Surfaces (Use established trails/sites)",
        "3. Dispose of Waste Properly (Pack it in, pack it out; cat holes)",
        "4. Leave What You Find (Preserve rocks, plants, historical artifacts)",
        "5. Minimize Campfire Impacts (Use stoves, fire rings, cold out check)",
        "6. Respect Wildlife (Observe from distance, never feed animals)",
        "7. Be Considerate of Other Visitors (Yield on trail, keep noise low)",
    ]
    
    for idx, text in enumerate(principles):
        y_pos = 8.0 - (idx * 1.1)
        ax.text(1.0, y_pos, text, fontsize=11, fontweight="bold", color="#212121",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#4B5320", lw=1.5))
                
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    return out_path

def generate_myplate_cooking_diagram() -> str:
    """Generates a MyPlate nutrition infographic for Cooking Merit Badge camp menus."""
    out_path = os.path.join(DIAGRAMS_DIR, "myplate_cooking_diagram.png")
    if os.path.exists(out_path):
        return out_path
        
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    
    ax.text(5, 9.3, "Cooking Merit Badge: MyPlate Camp Nutrition Guide", fontsize=16, fontweight="bold",
            color=ScoutsBSAPalette.NAVY_BLUE_HEX, ha="center")
            
    # 4 quadrants of a plate
    rects = [
        ("FRUITS\n(Energy & Vitamins)", "#CE1126", 1.5, 5.0, 3.2, 3.2),
        ("VEGETABLES\n(Fiber & Minerals)", "#4B5320", 5.0, 5.0, 3.5, 3.2),
        ("GRAINS\n(Complex Carbs / Fuel)", "#F4C430", 1.5, 1.5, 3.5, 3.2),
        ("PROTEIN\n(Muscle Recovery)", "#003F87", 5.2, 1.5, 3.3, 3.2),
    ]
    for label, color, x, y, w, h in rects:
        box = patches.Rectangle((x, y), w, h, facecolor=color, alpha=0.85, edgecolor="white", lw=2)
        ax.add_patch(box)
        ax.text(x + w/2, y + h/2, label, fontsize=11, fontweight="bold", color="white", ha="center", va="center")
        
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    return out_path

def generate_universal_badge_diagram(badge_name: str) -> str:
    """Generates a clean 4-pillar competency diagram for any elective merit badge."""
    safe_name = badge_name.lower().replace(" ", "_")
    out_path = os.path.join(DIAGRAMS_DIR, f"{safe_name}_diagram.png")
    if os.path.exists(out_path):
        return out_path
        
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
    ax.set_facecolor("#FFFFFF")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    
    ax.text(5, 9.3, f"{badge_name} Merit Badge: Core Pillars", fontsize=16, fontweight="bold",
            color=ScoutsBSAPalette.NAVY_BLUE_HEX, ha="center")
            
    pillars = [
        ("1. SAFETY FIRST", "Guide to Safe Scouting\n& Risk Prevention", "#CE1126", 2.5, 6.5),
        ("2. FUNDAMENTALS", "Core Concepts, Theory\n& Terminology", "#003F87", 7.5, 6.5),
        ("3. PRACTICAL SKILL", "Hands-On Demonstration\nwith Counselor", "#005AE0", 2.5, 2.5),
        ("4. CAREERS & LIFE", "Industry Exploration\n& Lifelong Utility", "#4B5320", 7.5, 2.5),
    ]
    
    for title, desc, color, x, y in pillars:
        box = patches.FancyBboxPatch((x-2.1, y-1.4), 4.2, 2.6, boxstyle="round,pad=0.2",
                                     facecolor="white", edgecolor=color, lw=2.5)
        ax.add_patch(box)
        ax.text(x, y+0.5, title, fontsize=12, fontweight="bold", color=color, ha="center")
        ax.text(x, y-0.4, desc, fontsize=10, color="#212121", ha="center")
        
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    return out_path

def get_badge_diagram_path(badge_name: str, slide_title: str = "") -> Optional[str]:
    """Returns the absolute filesystem path to a pedagogical diagram graphic for the slide.
    
    Args:
        badge_name: Name of target merit badge.
        slide_title: Current slide title to match specific diagrams.
        
    Returns:
        Optional[str]: Path to generated PNG diagram graphic.
    """
    clean_name = badge_name.strip().title()
    title_lower = slide_title.lower()
    
    if clean_name == "Weather":
        if "water cycle" in title_lower or "req 1" in title_lower or "meteorology" in title_lower:
            return generate_water_cycle_diagram()
        elif "cloud" in title_lower or "req 3" in title_lower or "req 4" in title_lower or "hazard" in title_lower:
            return generate_cloud_types_diagram()
        else:
            return generate_water_cycle_diagram()
            
    elif clean_name == "First Aid":
        if "cpr" in title_lower or "aed" in title_lower or "req 3" in title_lower:
            return generate_cpr_steps_diagram()
        elif "bleeding" in title_lower or "shock" in title_lower or "req 2" in title_lower:
            return generate_first_aid_bleeding_diagram()
        else:
            return generate_cpr_steps_diagram()
            
    elif clean_name == "Camping":
        return generate_leave_no_trace_diagram()
        
    elif clean_name == "Cooking":
        return generate_myplate_cooking_diagram()
        
    else:
        # Generate universal 4-pillar educational graphic for any other badge
        return generate_universal_badge_diagram(clean_name)
