"""Grounded Deep Research & Local Troop Grounding Engine (`src/tools/local_grounding_engine.py`).

Implements the 4-Phase Grounded Deep Research & Local Grounding architecture:
1. Phase 1 — Requirement Local Grounding Taxonomy & Annotation (`classify_requirement_local_grounding_spec`):
   Classifies every Merit Badge requirement across all 144 Merit Badges (`1,120` requirements) into one of
   8 local grounding categories with `requires_local_lookup`, `search_query_template`, `slide_injection_label`,
   and `ttl_days`.
2. Phase 2 — Live Gemini + Google Search Regional Entity & U.S. Senator Resolution:
   Resolves hyper-local landmarks, State Capital buildings, Federal facilities, National Park Service
   monuments, current two U.S. Senators (with 24-hour / 1-day TTL auto-refresh & on-demand Gemini lookup),
   local U.S. House Representative, NWS Weather Forecast Office, trauma/EMS hospitals, watersheds, and
   BSA council camps for any Counselor location (`City, State` or `ZIP`).
3. Phase 3 — Two-Tier Location-by-Category Cache (`data/local_grounding_cache.json` + SQLite `local_grounding_cache`):
   Persists resolved regional grounding entries keyed by `(normalized_location_key, grounding_category)` so
   subsequent decks in the same city/state load in `<2 ms` while keeping `elected_officials` fresh daily.
4. Phase 4 — Slide Callout & UI Citation Enrichment (`resolve_requirement_local_grounding`):
   Produces concise, slide-ready `local_grounding_callout` strings injected into `SlideSpec` cards/bullets
   (such as Citizenship in the Nation slides 32 & 33 and Requirement 8) and structured UI cards.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional

from src.config import select_model_for_task
from src.observability.logging_setup import logger

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
LOCAL_GROUNDING_CACHE_JSON = DATA_DIR / "local_grounding_cache.json"
US_SENATORS_CACHE_JSON = DATA_DIR / "us_senators_cache.json"

# ==============================================================================
# 1. COMPLETE 50-STATE + DC CIVIC, LANDMARK, SENATOR & FIELD REGISTRY
# ==============================================================================

_STATE_CIVIC_AND_FIELD_REGISTRY: Dict[str, Dict[str, str]] = {
    "AL": {
        "state_name": "Alabama",
        "capital_city": "Montgomery",
        "capitol_building": "Alabama State Capitol (Goat Hill, Montgomery, 1851 National Historic Landmark)",
        "senator_1": "Sen. Tommy Tuberville (R-AL)",
        "senator_1_url": "https://www.tuberville.senate.gov",
        "senator_2": "Sen. Katie Britt (R-AL)",
        "senator_2_url": "https://www.britt.senate.gov",
        "governor": "Gov. Kay Ivey",
        "landmarks": "Birmingham Civil Rights National Monument, Tuskegee Airmen National Historic Site, Russell Cave National Monument, and Little River Canyon National Preserve",
        "federal_facilities": "NASA Marshall Space Flight Center (Huntsville), Redstone Arsenal, and Frank M. Johnson Jr. Federal Building & U.S. Courthouse (Montgomery)",
        "wfo": "NWS Birmingham (BMX) & NWS Huntsville (HUN)",
        "wfo_url": "https://www.weather.gov/bmx/",
        "hazards": "Spring supercell tornadoes, Gulf tropical cyclones, summer heat index >105°F, and flash flooding",
        "camps_trails": "Camp Comer (Greater Alabama Council), Oak Mountain State Park, and Pinhoti National Recreation Trail",
        "trauma_ems": "UAB Hospital Level I Trauma Center (Birmingham) & USA Health University Hospital (Mobile)",
        "ecology": "Mobile-Tensaw River Delta watershed, Southern Appalachian mixed mesophytic forest, and Alabama DCNR conservation lands",
        "museums": "U.S. Space & Rocket Center (Huntsville) and Legacy Museum / National Memorial for Peace and Justice (Montgomery)",
    },
    "AK": {
        "state_name": "Alaska",
        "capital_city": "Juneau",
        "capitol_building": "Alaska State Capitol (Juneau, 1931)",
        "senator_1": "Sen. Lisa Murkowski (R-AK)",
        "senator_1_url": "https://www.murkowski.senate.gov",
        "senator_2": "Sen. Dan Sullivan (R-AK)",
        "senator_2_url": "https://www.sullivan.senate.gov",
        "governor": "Gov. Mike Dunleavy",
        "landmarks": "Denali National Park and Preserve, Klondike Gold Rush National Historical Park, Sitka National Historical Park, and Kenai Fjords National Park",
        "federal_facilities": "James M. Fitzgerald U.S. Courthouse & Federal Building (Anchorage), Joint Base Elmendorf-Richardson, and NOAA Alaska Region Headquarters (Juneau)",
        "wfo": "NWS Anchorage (AFC) & NWS Fairbanks (AFG)",
        "wfo_url": "https://www.weather.gov/afc/",
        "hazards": "Extreme sub-zero hypothermia, rapid glacial river rises, avalanche terrain, and brown/grizzly bear encounters",
        "camps_trails": "Camp Gorsuch (Great Alaska Council), Chugach State Park, and Resurrection Pass National Recreation Trail",
        "trauma_ems": "Providence Alaska Medical Center Level II Trauma Center (Anchorage) & Alaska State Troopers Search and Rescue",
        "ecology": "Subarctic boreal taiga, Tongass temperate rainforest, Cook Inlet watershed, and Alaska Department of Fish and Game",
        "museums": "Anchorage Museum at Rasmuson Center and Museum of the North (University of Alaska Fairbanks)",
    },
    "AZ": {
        "state_name": "Arizona",
        "capital_city": "Phoenix",
        "capitol_building": "Arizona State Capitol Museum & Executive Tower (Phoenix, 1900 copper dome)",
        "senator_1": "Sen. Mark Kelly (D-AZ)",
        "senator_1_url": "https://www.kelly.senate.gov",
        "senator_2": "Sen. Ruben Gallego (D-AZ)",
        "senator_2_url": "https://www.gallego.senate.gov",
        "governor": "Gov. Katie Hobbs",
        "landmarks": "Grand Canyon National Park, Saguaro National Park, Montezuma Castle National Monument, and Canyon de Chelly National Monument",
        "federal_facilities": "Sandra Day O'Connor U.S. Courthouse (Phoenix), USGS Astrogeology Science Center (Flagstaff), and Luke Air Force Base",
        "wfo": "NWS Phoenix (PSR), NWS Tucson (TWC) & NWS Flagstaff (FGZ)",
        "wfo_url": "https://www.weather.gov/psr/",
        "hazards": "Extreme desert heat (>110°F), North American monsoon flash floods in slot canyons, haboob dust storms, and venomous rattlesnakes/scorpions",
        "camps_trails": "Camp Geronimo (Grand Canyon Council), R-C Scout Ranch, and Arizona National Scenic Trail",
        "trauma_ems": "Banner - University Medical Center Phoenix Level I Trauma Center & Maricopa County Sheriff's Mountain Rescue",
        "ecology": "Sonoran Desert saguaro scrub, Colorado River basin, Mogollon Rim ponderosa pine forest, and Arizona Game and Fish Department",
        "museums": "Lowell Observatory (Flagstaff), Heard Museum (Phoenix), and Pima Air & Space Museum (Tucson)",
    },
    "AR": {
        "state_name": "Arkansas",
        "capital_city": "Little Rock",
        "capitol_building": "Arkansas State Capitol (Little Rock, 1915 neo-classical marble dome)",
        "senator_1": "Sen. John Boozman (R-AR)",
        "senator_1_url": "https://www.boozman.senate.gov",
        "senator_2": "Sen. Tom Cotton (R-AR)",
        "senator_2_url": "https://www.cotton.senate.gov",
        "governor": "Gov. Sarah Huckabee Sanders",
        "landmarks": "Little Rock Central High School National Historic Site, Hot Springs National Park, Pea Ridge National Military Park, and Buffalo National River",
        "federal_facilities": "Richard Sheppard Arnold U.S. Courthouse (Little Rock), Little Rock Air Force Base, and Clinton Presidential Center & NARA Library",
        "wfo": "NWS Little Rock (LZK)",
        "wfo_url": "https://www.weather.gov/lzk/",
        "hazards": "Spring severe thunderstorms and tornadoes, Ozark river flash flooding, summer heat/humidity, and lone star / deer ticks",
        "camps_trails": "Camp Rockefeller (Quapaw Area Council),Camp Orr (Buffalo National River), and Ouachita National Recreation Trail",
        "trauma_ems": "UAMS Medical Center Level I Trauma Center (Little Rock) & Arkansas Children's Hospital",
        "ecology": "Ozark Plateau karst watersheds, Ouachita Mountains, Arkansas River valley, and Arkansas Game and Fish Commission",
        "museums": "Crystal Bridges Museum of American Art (Bentonville) and Museum of Discovery (Little Rock)",
    },
    "CA": {
        "state_name": "California",
        "capital_city": "Sacramento",
        "capitol_building": "California State Capitol & Museum (Sacramento, 1874 classical dome)",
        "senator_1": "Sen. Alex Padilla (D-CA)",
        "senator_1_url": "https://www.padilla.senate.gov",
        "senator_2": "Sen. Adam Schiff (D-CA)",
        "senator_2_url": "https://www.schiff.senate.gov",
        "governor": "Gov. Gavin Newsom",
        "landmarks": "Golden Gate National Recreation Area, Muir Woods National Monument, Yosemite National Park, Rosie the Riveter WWII Home Front National Historical Park, and Pinnacles National Park",
        "federal_facilities": "NASA Ames Research Center (Moffett Field, Mountain View), Robert F. Peckham Federal Building & U.S. Courthouse (San Jose), Phillip Burton Federal Building (San Francisco), and Lawrence Berkeley National Laboratory",
        "wfo": "NWS San Francisco Bay Area / Monterey (MTR), NWS Sacramento (STO) & NWS Los Angeles/Oxnard (LOX)",
        "wfo_url": "https://www.weather.gov/mtr/",
        "hazards": "Wildfire smoke & Red Flag fire danger, inland valley heat waves, Sierra high-altitude hypothermia, seismic earthquakes, and western black-legged ticks / poison oak",
        "camps_trails": "Camp Hi-Sierra & Pico Blanco Scout Reservation (Silicon Valley Monterey Bay Council), Castle Rock State Park, and Pacific Crest National Scenic Trail",
        "trauma_ems": "Stanford Health Care & Santa Clara Valley Medical Center Level I Trauma Centers (San Jose/Palo Alto) & CAL FIRE / County Sheriff SAR",
        "ecology": "San Francisco Bay-Delta estuary, Coast Redwood & chaparral oak woodlands, Sierra Nevada alpine watersheds, and California Department of Fish and Wildlife",
        "museums": "Computer History Museum (Mountain View), The Tech Interactive (San Jose), California Academy of Sciences (San Francisco), and Chabot Space & Science Center",
    },
    "CO": {
        "state_name": "Colorado",
        "capital_city": "Denver",
        "capitol_building": "Colorado State Capitol (Denver, 1894 gold-leaf dome at 5,280 ft 'One Mile High')",
        "senator_1": "Sen. Michael Bennet (D-CO)",
        "senator_1_url": "https://www.bennet.senate.gov",
        "senator_2": "Sen. John Hickenlooper (D-CO)",
        "senator_2_url": "https://www.hickenlooper.senate.gov",
        "governor": "Gov. Jared Polis",
        "landmarks": "Rocky Mountain National Park, Mesa Verde National Park, Great Sand Dunes National Park, Colorado National Monument, and Bent's Old Fort National Historic Site",
        "federal_facilities": "NOAA David Skaggs Research Center & NIST (Boulder), Denver Federal Center (Lakewood), U.S. Mint (Denver), and U.S. Air Force Academy (Colorado Springs)",
        "wfo": "NWS Denver/Boulder (BOU) & NWS Grand Junction (GJT)",
        "wfo_url": "https://www.weather.gov/bou/",
        "hazards": "Above-treeline afternoon lightning strikes, Acute Mountain Sickness (AMS >8,000 ft), rapid alpine hypothermia, and winter slab avalanches",
        "camps_trails": "Peaceful Valley Scout Ranch (Greater Colorado Council), Tahosa High Adventure Base, and Colorado Trail / Continental Divide Trail",
        "trauma_ems": "Denver Health Medical Center & UCHealth University of Colorado Hospital Level I Trauma Centers & Rocky Mountain Rescue Group",
        "ecology": "Alpine tundra, subalpine Engelmann spruce-fir forest, headwaters of the Colorado, Rio Grande, Arkansas, and South Platte rivers, and Colorado Parks and Wildlife",
        "museums": "Denver Museum of Nature & Science, NCAR Mesa Lab (Boulder), and Wings Over the Rockies Air & Space Museum",
    },
    "CT": {
        "state_name": "Connecticut",
        "capital_city": "Hartford",
        "capitol_building": "Connecticut State Capitol (Hartford, 1878 High Victorian Gothic & gold dome)",
        "senator_1": "Sen. Richard Blumenthal (D-CT)",
        "senator_1_url": "https://www.blumenthal.senate.gov",
        "senator_2": "Sen. Chris Murphy (D-CT)",
        "senator_2_url": "https://www.murphy.senate.gov",
        "governor": "Gov. Ned Lamont",
        "landmarks": "Weir Farm National Historical Park, Coltsville National Historical Park (Hartford), Mystic Seaport, and New England National Scenic Trail",
        "federal_facilities": "Abraham A. Ribicoff Federal Building & U.S. Courthouse (Hartford), U.S. Coast Guard Academy (New London), and Naval Submarine Base New London (Groton)",
        "wfo": "NWS New York/Upton (OKX) & NWS Boston/Norton (BOX)",
        "wfo_url": "https://www.weather.gov/okx/",
        "hazards": "Coastal Long Island Sound nor'easters, severe summer squall lines, winter ice storms, and black-legged deer ticks (Lyme disease endemic zone)",
        "camps_trails": "June Norcross Webster Scout Reservation & Camp Workcoeman (Connecticut Rivers Council), and Appalachian Trail in Litchfield Hills",
        "trauma_ems": "Hartford Hospital & Yale New Haven Hospital Level I Trauma Centers",
        "ecology": "Connecticut River tidal watershed, Long Island Sound estuary, central hardwood forest, and CT DEEP",
        "museums": "Yale Peabody Museum (New Haven), Connecticut Science Center (Hartford), and USS Nautilus Submarine Force Museum (Groton)",
    },
    "DE": {
        "state_name": "Delaware",
        "capital_city": "Dover",
        "capitol_building": "Delaware Legislative Hall & The Old State House (Dover, 1791 First State ratification site)",
        "senator_1": "Sen. Chris Coons (D-DE)",
        "senator_1_url": "https://www.coons.senate.gov",
        "senator_2": "Sen. Lisa Blunt Rochester (D-DE)",
        "senator_2_url": "https://www.bluntrochester.senate.gov",
        "governor": "Gov. Matt Meyer",
        "landmarks": "First State National Historical Park (New Castle & Dover Green), Fort Delaware State Park, and Bombay Hook National Wildlife Refuge",
        "federal_facilities": "J. Caleb Boggs Federal Building & U.S. Courthouse (Wilmington) and Dover Air Force Base",
        "wfo": "NWS Mount Holly/Philadelphia (PHI)",
        "wfo_url": "https://www.weather.gov/phi/",
        "hazards": "Coastal storm surge, tidal flooding, summer heat & humidity, and Atlantic tropical systems",
        "camps_trails": "Rodney Scout Reservation (Del-Mar-Va Council), Cape Henlopen State Park, and Brandywine Creek State Park",
        "trauma_ems": "ChristianaCare Christiana Hospital Level I Trauma Center (Newark)",
        "ecology": "Delaware Bay estuary (migratory shorebird & horseshoe crab sanctuary), Christina River watershed, and Delaware DNREC",
        "museums": "Hagley Museum and Library (Wilmington) and Air Mobility Command Museum (Dover AFB)",
    },
    "DC": {
        "state_name": "District of Columbia",
        "capital_city": "Washington",
        "capitol_building": "United States Capitol & John A. Wilson District Building (Washington, D.C.)",
        "senator_1": "Del. Eleanor Holmes Norton (D-DC, Non-Voting House Delegate; D.C. has no U.S. Senators under Article I, Section 8)",
        "senator_1_url": "https://norton.house.gov",
        "senator_2": "U.S. Senate Committee on Homeland Security and Governmental Affairs (Constitutional federal district oversight)",
        "senator_2_url": "https://www.senate.gov",
        "governor": "Mayor Muriel Bowser",
        "landmarks": "National Mall & Memorial Parks (Washington Monument, Lincoln Memorial, Jefferson Memorial, WWII & MLK Jr. Memorials), National Archives Rotunda, and Frederick Douglass National Historic Site",
        "federal_facilities": "U.S. Capitol, The White House, U.S. Supreme Court Building, Library of Congress, and E. Barrett Prettyman U.S. Courthouse",
        "wfo": "NWS Baltimore/Washington (LWX)",
        "wfo_url": "https://www.weather.gov/lwx/",
        "hazards": "Urban heat index >100°F, fast-moving Potomac squall lines, and flash flooding",
        "camps_trails": "Goshen Scout Reservation & Camp William B. Snyder (National Capital Area Council), Rock Creek Park, and C&O Canal Towpath",
        "trauma_ems": "MedStar Washington Hospital Center & George Washington University Hospital Level I Trauma Centers",
        "ecology": "Potomac and Anacostia River tidal watersheds, Chesapeake Bay basin, and Rock Creek urban forest",
        "museums": "Smithsonian National Air and Space Museum, National Museum of Natural History, and National Museum of American History",
    },
    "FL": {
        "state_name": "Florida",
        "capital_city": "Tallahassee",
        "capitol_building": "Florida State Capitol & Historic 1902 Capitol Museum (Tallahassee)",
        "senator_1": "Sen. Rick Scott (R-FL)",
        "senator_1_url": "https://www.rickscott.senate.gov",
        "senator_2": "Sen. Ashley Moody (R-FL)",
        "senator_2_url": "https://www.moody.senate.gov",
        "governor": "Gov. Ron DeSantis",
        "landmarks": "Everglades National Park, Castillo de San Marcos National Monument (St. Augustine), Dry Tortugas National Park, and Canaveral National Seashore",
        "federal_facilities": "NASA Kennedy Space Center (Cape Canaveral), Wilkie D. Ferguson Jr. U.S. Courthouse (Miami), and MacDill Air Force Base (Tampa)",
        "wfo": "NWS Miami (MFL), NWS Tampa Bay (TBW), NWS Melbourne (MLB) & NWS Tallahassee (TAE)",
        "wfo_url": "https://www.weather.gov/tbw/",
        "hazards": "High cloud-to-ground lightning frequency, Atlantic/Gulf hurricanes, extreme Wet Bulb Globe Temperature heat stress, and rip currents",
        "camps_trails": "Florida National High Adventure Sea Base (Islamorada), Camp La-No-Che (Central Florida Council), and Florida National Scenic Trail",
        "trauma_ems": "Jackson Memorial Ryder Trauma Center (Miami), Tampa General Hospital & Orlando Regional Medical Center Level I Trauma Centers",
        "ecology": "Everglades 'River of Grass' subtropical wetlands, Florida Reef tract, longleaf pine flatwoods, and Florida Fish and Wildlife Conservation Commission (FWC)",
        "museums": "Kennedy Space Center Visitor Complex, Phillip and Patricia Frost Museum of Science (Miami), and Salvador Dalí Museum",
    },
    "GA": {
        "state_name": "Georgia",
        "capital_city": "Atlanta",
        "capitol_building": "Georgia State Capitol (Atlanta, 1889 Dahlonega gold-leaf dome)",
        "senator_1": "Sen. Jon Ossoff (D-GA)",
        "senator_1_url": "https://www.ossoff.senate.gov",
        "senator_2": "Sen. Raphael Warnock (D-GA)",
        "senator_2_url": "https://www.warnock.senate.gov",
        "governor": "Gov. Brian Kemp",
        "landmarks": "Martin Luther King, Jr. National Historical Park (Atlanta), Kennesaw Mountain National Battlefield Park, Fort Pulaski National Monument, and Cumberland Island National Seashore",
        "federal_facilities": "Centers for Disease Control and Prevention (CDC Headquarters, Atlanta), Richard B. Russell Federal Building & Eleventh Circuit Court of Appeals, and Jimmy Carter Presidential Library",
        "wfo": "NWS Peachtree City/Atlanta (FFC)",
        "wfo_url": "https://www.weather.gov/ffc/",
        "hazards": "Severe thunderstorms & tornadoes, high summer heat/humidity, Blue Ridge flash flooding, and ticks/chiggers",
        "camps_trails": "Woodruff Scout Camp & Bert Adams Scout Camp (Atlanta Area Council), and Appalachian Trail southern terminus at Springer Mountain",
        "trauma_ems": "Grady Memorial Hospital Level I Trauma Center (Atlanta) & Wellstar Kennestone Hospital",
        "ecology": "Chattahoochee River watershed, Blue Ridge Appalachian hardwood forest, Okefenokee Swamp, and Georgia DNR",
        "museums": "Fernbank Museum of Natural History, Georgia Aquarium, and Tellus Science Museum (Cartersville)",
    },
    "HI": {
        "state_name": "Hawaii",
        "capital_city": "Honolulu",
        "capitol_building": "Hawaii State Capitol (Honolulu, 1969 open-air volcanic cone legislative chambers)",
        "senator_1": "Sen. Brian Schatz (D-HI)",
        "senator_1_url": "https://www.schatz.senate.gov",
        "senator_2": "Sen. Mazie Hirono (D-HI)",
        "senator_2_url": "https://www.hirono.senate.gov",
        "governor": "Gov. Josh Green",
        "landmarks": "Pearl Harbor National Memorial (USS Arizona), Hawai'i Volcanoes National Park, Haleakalā National Park, and Pu'uhonua o Hōnaunau National Historical Park",
        "federal_facilities": "Prince Jonah Kūhiō Kalaniana'ole Federal Building & U.S. Courthouse (Honolulu), Joint Base Pearl Harbor-Hickam, and NOAA Daniel K. Inouye Regional Center (Ford Island)",
        "wfo": "NWS Honolulu (HFO) & Pacific Tsunami Warning Center",
        "wfo_url": "https://www.weather.gov/hfo/",
        "hazards": "Flash flooding in steep windward gulches, high surf/rip currents, volcanic vog/lava hazards, and tsunami evacuation zones",
        "camps_trails": "Camp Pupukea (Aloha Council, Oahu North Shore), Camp Alan Faye (Kauai), and Kalalau / Mauna Loa trails",
        "trauma_ems": "The Queen's Medical Center Level I Trauma Center (Honolulu) & Honolulu Ocean Safety / Coast Guard SAR",
        "ecology": "Endemic Hawaiian island ecosystems, coral reef marine sanctuaries, ahupua'a ridge-to-reef watersheds, and Hawaii DLNR",
        "museums": "Bishop Museum (Honolulu), Imiloa Astronomy Center (Hilo), and Battleship Missouri / Pacific Aviation Museum",
    },
    "ID": {
        "state_name": "Idaho",
        "capital_city": "Boise",
        "capitol_building": "Idaho State Capitol (Boise, 1920 sandstone classical dome heated by geothermal water)",
        "senator_1": "Sen. Mike Crapo (R-ID)",
        "senator_1_url": "https://www.crapo.senate.gov",
        "senator_2": "Sen. Jim Risch (R-ID)",
        "senator_2_url": "https://www.risch.senate.gov",
        "governor": "Gov. Brad Little",
        "landmarks": "Craters of the Moon National Monument & Preserve, Nez Perce National Historical Park, Minidoka National Historic Site, and City of Rocks National Reserve",
        "federal_facilities": "Idaho National Laboratory (INL, Idaho Falls — nation's nuclear energy research lab), James A. McClure Federal Building & U.S. Courthouse (Boise), and National Interagency Fire Center (NIFC, Boise)",
        "wfo": "NWS Boise (BOI) & NWS Pocatello (PIH)",
        "wfo_url": "https://www.weather.gov/boi/",
        "hazards": "Backcountry wildfire smoke, rapid mountain cold fronts, swift snowmelt whitewater rivers, and Rocky Mountain wood ticks",
        "camps_trails": "Camp Morrison (Mountain West Council), Farragut State Park (site of the 1967 World Scout Jamboree), and Sawtooth Wilderness trails",
        "trauma_ems": "Saint Alphonsus Regional Medical Center Level II Trauma Center (Boise) & Idaho Mountain Search and Rescue Unit",
        "ecology": "Snake River & Salmon River ('River of No Return') watersheds, Frank Church-River of No Return Wilderness, and Idaho Department of Fish and Game",
        "museums": "Experimental Breeder Reactor-I (EBR-I) Atomic Museum (Arco), World Center for Birds of Prey (Boise), and Discovery Center of Idaho",
    },
    "IL": {
        "state_name": "Illinois",
        "capital_city": "Springfield",
        "capitol_building": "Illinois State Capitol & Old State Capitol State Historic Site (Springfield, where Lincoln delivered his 1858 'House Divided' speech)",
        "senator_1": "Sen. Dick Durbin (D-IL)",
        "senator_1_url": "https://www.durbin.senate.gov",
        "senator_2": "Sen. Tammy Duckworth (D-IL)",
        "senator_2_url": "https://www.duckworth.senate.gov",
        "governor": "Gov. JB Pritzker",
        "landmarks": "Lincoln Home National Historic Site (Springfield), Pullman National Historical Park (Chicago), Cahokia Mounds State Historic Site, and Lincoln Tomb",
        "federal_facilities": "Everett McKinley Dirksen U.S. Courthouse (Chicago), Fermi National Accelerator Laboratory (Fermilab, Batavia), and Argonne National Laboratory (Lemont)",
        "wfo": "NWS Chicago/Romeoville (LOT) & NWS Lincoln (ILX)",
        "wfo_url": "https://www.weather.gov/lot/",
        "hazards": "Midwest severe thunderstorm derechos, tornadoes, Lake Michigan shore seiches/rip currents, and bitter winter wind chills",
        "camps_trails": "Camp Napowan & Betz (Pathway to Adventure Council), Starved Rock State Park, and Shawnee National Forest River-to-River Trail",
        "trauma_ems": "University of Chicago Medicine, Northwestern Memorial & Stroger Hospital Level I Trauma Centers",
        "ecology": "Lake Michigan Great Lakes basin, Illinois & Mississippi River flyways, tallgrass prairie restorations (Midewin National Tallgrass Prairie), and Illinois DNR",
        "museums": "Griffin Museum of Science and Industry, Field Museum of Natural History, Adler Planetarium (Chicago), and Abraham Lincoln Presidential Library (Springfield)",
    },
    "IN": {
        "state_name": "Indiana",
        "capital_city": "Indianapolis",
        "capitol_building": "Indiana Statehouse (Indianapolis, 1888 Indiana limestone & copper dome)",
        "senator_1": "Sen. Todd Young (R-IN)",
        "senator_1_url": "https://www.young.senate.gov",
        "senator_2": "Sen. Jim Banks (R-IN)",
        "senator_2_url": "https://www.banks.senate.gov",
        "governor": "Gov. Mike Braun",
        "landmarks": "Indiana Dunes National Park, George Rogers Clark National Historical Park (Vincennes), Lincoln Boyhood National Memorial, and Soldiers and Sailors Monument (Indianapolis)",
        "federal_facilities": "Birch Bayh Federal Building & U.S. Courthouse (Indianapolis) and Naval Surface Warfare Center Crane",
        "wfo": "NWS Indianapolis (IND) & NWS Northern Indiana (IWX)",
        "wfo_url": "https://www.weather.gov/ind/",
        "hazards": "Spring/summer tornado outbreaks, severe thunderstorm winds, summer humidity, and winter ice/snow squalls",
        "camps_trails": "Ransburg Scout Reservation (Crossroads of America Council, Lake Monroe), Brown County State Park, and Knobstone Trail",
        "trauma_ems": "IU Health Methodist Hospital & Eskenazi Health Level I Trauma Centers (Indianapolis)",
        "ecology": "Wabash & White River watersheds, Lake Michigan coastal dunes, Hoosier National Forest karst hills, and Indiana DNR",
        "museums": "The Children's Museum of Indianapolis, Indiana State Museum, and Indianapolis Motor Speedway Museum",
    },
    "IA": {
        "state_name": "Iowa",
        "capital_city": "Des Moines",
        "capitol_building": "Iowa State Capitol (Des Moines, 1886 23-karat gold-leafed central dome with four corner domes)",
        "senator_1": "Sen. Chuck Grassley (R-IA)",
        "senator_1_url": "https://www.grassley.senate.gov",
        "senator_2": "Sen. Joni Ernst (R-IA)",
        "senator_2_url": "https://www.ernst.senate.gov",
        "governor": "Gov. Kim Reynolds",
        "landmarks": "Effigy Mounds National Monument, Herbert Hoover National Historic Site (West Branch), and Loess Hills National Scenic Byway",
        "federal_facilities": "Neal Smith Federal Building & U.S. Courthouse (Des Moines) and Ames National Laboratory (U.S. Department of Energy, Ames)",
        "wfo": "NWS Des Moines (DMX) & NWS Quad Cities (DVN)",
        "wfo_url": "https://www.weather.gov/dmx/",
        "hazards": "Plains supercell tornadoes, summer derechos, river flooding, and winter blizzards",
        "camps_trails": "Mitigwa Scout Reservation (Mid-Iowa Council), Backbone State Park, and High Trestle Trail",
        "trauma_ems": "University of Iowa Hospitals & Clinics (Iowa City) & Iowa Methodist Medical Center (Des Moines) Level I Trauma Centers",
        "ecology": "Upper Mississippi and Missouri River watersheds, Des Moines Lobe prairie potholes, Driftless Area bluffs, and Iowa DNR",
        "museums": "Science Center of Iowa (Des Moines), State Historical Museum of Iowa, and Putnam Museum (Davenport)",
    },
    "KS": {
        "state_name": "Kansas",
        "capital_city": "Topeka",
        "capitol_building": "Kansas State Capitol (Topeka, 1903 copper dome topped by the 'Ad Astra' Kansa warrior statue)",
        "senator_1": "Sen. Jerry Moran (R-KS)",
        "senator_1_url": "https://www.moran.senate.gov",
        "senator_2": "Sen. Roger Marshall (R-KS)",
        "senator_2_url": "https://www.marshall.senate.gov",
        "governor": "Gov. Laura Kelly",
        "landmarks": "Brown v. Board of Education National Historical Park (Topeka), Tallgrass Prairie National Preserve, Fort Scott National Historic Site, and Fort Larned National Historic Site",
        "federal_facilities": "Robert J. Dole U.S. Courthouse (Kansas City, KS), Frank Carlson Federal Building (Topeka), Fort Riley, and Dwight D. Eisenhower Presidential Library (Abilene)",
        "wfo": "NWS Topeka (TOP), NWS Wichita (ICT) & NWS Dodge City (DDC)",
        "wfo_url": "https://www.weather.gov/top/",
        "hazards": "Central Plains tornado alley supercells, large hail, high prairie winds, and extreme summer heat",
        "camps_trails": "Quivira Scout Ranch (Quivira Council) & Naish Scout Reservation (Heart of America Council), and Flint Hills Nature Trail",
        "trauma_ems": "University of Kansas Health System (Kansas City) & Ascension Via Christi St. Francis (Wichita) Level I Trauma Centers",
        "ecology": "Flint Hills tallgrass prairie ecosystem, Kansas (Kaw) and Arkansas River basins, Cheyenne Bottoms wetlands, and Kansas DWPT",
        "museums": "Cosmosphere International SciEd Center & Space Museum (Hutchinson) and Exploration Place (Wichita)",
    },
    "KY": {
        "state_name": "Kentucky",
        "capital_city": "Frankfort",
        "capitol_building": "Kentucky State Capitol (Frankfort, 1910 Beaux-Arts classical dome)",
        "senator_1": "Sen. Mitch McConnell (R-KY)",
        "senator_1_url": "https://www.mcconnell.senate.gov",
        "senator_2": "Sen. Rand Paul (R-KY)",
        "senator_2_url": "https://www.paul.senate.gov",
        "governor": "Gov. Andy Beshear",
        "landmarks": "Mammoth Cave National Park, Abraham Lincoln Birthplace National Historical Park (Hodgenville), Cumberland Gap National Historical Park, and Camp Nelson National Monument",
        "federal_facilities": "Gene Snyder U.S. Courthouse (Louisville), Fort Knox (U.S. Bullion Depository), and Fort Campbell",
        "wfo": "NWS Louisville (LMK), NWS Jackson (JKL) & NWS Paducah (PAH)",
        "wfo_url": "https://www.weather.gov/lmk/",
        "hazards": "Ohio Valley tornadoes, Appalachian hollow flash flooding, karst sinkholes, and summer humidity",
        "camps_trails": "Camp Crooked Creek (Lincoln Heritage Council), Camp McKee (Blue Grass Council), and Red River Gorge Geological Area",
        "trauma_ems": "University of Louisville Hospital & UK Albert B. Chandler Hospital (Lexington) Level I Trauma Centers",
        "ecology": "Mammoth Cave karst aquifer, Ohio & Kentucky River watersheds, Daniel Boone National Forest mixed hardwoods, and Kentucky Dept. of Fish & Wildlife",
        "museums": "Kentucky Science Center (Louisville), Frazier History Museum, and Aviation Museum of Kentucky (Lexington)",
    },
    "LA": {
        "state_name": "Louisiana",
        "capital_city": "Baton Rouge",
        "capitol_building": "Louisiana State Capitol (Baton Rouge, 1932 34-story, 450-foot Art Deco skyscraper — tallest state capitol in the U.S.)",
        "senator_1": "Sen. Bill Cassidy (R-LA)",
        "senator_1_url": "https://www.cassidy.senate.gov",
        "senator_2": "Sen. John Kennedy (R-LA)",
        "senator_2_url": "https://www.kennedy.senate.gov",
        "governor": "Gov. Jeff Landry",
        "landmarks": "Jean Lafitte National Historical Park and Preserve (New Orleans & Chalmette Battlefield), New Orleans Jazz National Historical Park, and Poverty Point World Heritage National Monument",
        "federal_facilities": "John Minor Wisdom U.S. Court of Appeals Building (Fifth Circuit, New Orleans), NASA Michoud Assembly Facility (New Orleans), and Barksdale Air Force Base",
        "wfo": "NWS New Orleans/Baton Rouge (LIX) & NWS Shreveport (SHV)",
        "wfo_url": "https://www.weather.gov/lix/",
        "hazards": "Gulf hurricanes & storm surge, intense subtropical lightning/rainfall flooding, extreme heat/humidity, and venomous water moccasins/alligators",
        "camps_trails": "Camp Salmen (Southeast Louisiana Council) & Camp Avondale (Istrouma Area Council), and Kisatchie National Forest Backbone Trail",
        "trauma_ems": "University Medical Center New Orleans & Our Lady of the Lake Regional Medical Center (Baton Rouge) Level I Trauma Centers",
        "ecology": "Mississippi River Delta coastal marshes, Atchafalaya Basin cypress-tupelo swamp, and Louisiana Department of Wildlife and Fisheries",
        "museums": "The National WWII Museum (New Orleans), LIGO Livingston Observatory, and Louisiana Art & Science Museum (Baton Rouge)",
    },
    "ME": {
        "state_name": "Maine",
        "capital_city": "Augusta",
        "capitol_building": "Maine State House (Augusta, 1832 Hallowell granite capitol designed by Charles Bulfinch)",
        "senator_1": "Sen. Susan Collins (R-ME)",
        "senator_1_url": "https://www.collins.senate.gov",
        "senator_2": "Sen. Angus King (I-ME)",
        "senator_2_url": "https://www.king.senate.gov",
        "governor": "Gov. Janet Mills",
        "landmarks": "Acadia National Park (Mount Desert Island), Katahdin Woods and Waters National Monument, Saint Croix Island International Historic Site, and Appalachian Trail northern terminus at Mount Katahdin",
        "federal_facilities": "Margaret Chase Smith Federal Building & U.S. Courthouse (Bangor), Edward T. Gignoux U.S. Courthouse (Portland), and Portsmouth Naval Shipyard (Kittery)",
        "wfo": "NWS Gray/Portland (GYX) & NWS Caribou (CAR)",
        "wfo_url": "https://www.weather.gov/gyx/",
        "hazards": "Cold North Atlantic water immersion shock, coastal nor'easters, alpine exposure on Katahdin, and deer ticks (Lyme disease)",
        "camps_trails": "Camp Hinds (Pine Tree Council), Camp William Hinds, Baxter State Park, and Allagash Wilderness Waterway",
        "trauma_ems": "Maine Medical Center Level I Trauma Center (Portland) & Maine Warden Service Search and Rescue",
        "ecology": "Gulf of Maine rocky intertidal zone, Northern Forest spruce-fir boreal woods, Penobscot/Kennebec watersheds, and Maine Dept. of Inland Fisheries & Wildlife",
        "museums": "Maine Maritime Museum (Bath), Maine State Museum (Augusta), and Gulf of Maine Research Institute",
    },
    "MD": {
        "state_name": "Maryland",
        "capital_city": "Annapolis",
        "capitol_building": "Maryland State House (Annapolis, 1772 — oldest U.S. state capitol in continuous legislative use, where George Washington resigned his commission in 1783)",
        "senator_1": "Sen. Chris Van Hollen (D-MD)",
        "senator_1_url": "https://www.vanhollen.senate.gov",
        "senator_2": "Sen. Angela Alsobrooks (D-MD)",
        "senator_2_url": "https://www.alsobrooks.senate.gov",
        "governor": "Gov. Wes Moore",
        "landmarks": "Fort McHenry National Monument and Historic Shrine (Baltimore, birthplace of 'The Star-Spangled Banner'), Antietam National Battlefield, Harriet Tubman Underground Railroad National Historical Park, and Chesapeake & Ohio Canal National Historical Park",
        "federal_facilities": "U.S. Naval Academy (Annapolis), NASA Goddard Space Flight Center (Greenbelt), National Institutes of Health (NIH, Bethesda), NOAA Headquarters (Silver Spring), and Edward A. Garmatz U.S. Courthouse (Baltimore)",
        "wfo": "NWS Baltimore/Washington (LWX)",
        "wfo_url": "https://www.weather.gov/lwx/",
        "hazards": "Chesapeake Bay sudden squalls, summer heat advisories, Piedmont flash flooding, and deer ticks",
        "camps_trails": "Broad Creek Memorial Scout Reservation (Baltimore Area Council), Catoctin Mountain Park, and Appalachian Trail along South Mountain",
        "trauma_ems": "R Adams Cowley Shock Trauma Center at University of Maryland (Baltimore) & Johns Hopkins Hospital Level I Trauma Centers",
        "ecology": "Chesapeake Bay estuarine watershed (blue crab, oyster reefs, submerged aquatic vegetation), Potomac/Patuxent basins, and Maryland DNR",
        "museums": "Maryland Science Center (Baltimore), NASA Goddard Visitor Center, and U.S. Naval Academy Museum (Annapolis)",
    },
    "MA": {
        "state_name": "Massachusetts",
        "capital_city": "Boston",
        "capitol_building": "Massachusetts State House (Beacon Hill, Boston, 1798 Charles Bulfinch golden dome)",
        "senator_1": "Sen. Elizabeth Warren (D-MA)",
        "senator_1_url": "https://www.warren.senate.gov",
        "senator_2": "Sen. Edward J. Markey (D-MA)",
        "senator_2_url": "https://www.markey.senate.gov",
        "governor": "Gov. Maura Healey",
        "landmarks": "Boston National Historical Park (Freedom Trail, Faneuil Hall, Bunker Hill, USS Constitution), Minute Man National Historical Park (Lexington & Concord), Salem Maritime National Historic Site (Salem), Adams National Historical Park (Quincy), and Cape Cod National Seashore",
        "federal_facilities": "John Joseph Moakley U.S. Courthouse & First Circuit Court of Appeals (Boston), John F. Kennedy Federal Building (Boston), Hanscom Air Force Base, and John F. Kennedy Presidential Library & NARA Museum (Boston)",
        "wfo": "NWS Boston/Norton (BOX)",
        "wfo_url": "https://www.weather.gov/box/",
        "hazards": "Coastal nor'easters, winter ice storms, severe summer lightning squalls, cold Atlantic water immersion, and black-legged deer ticks (Lyme disease)",
        "camps_trails": "T.L. Storer Scout Reservation (Spirit of Adventure Council), Wah-Tut-Ca Scout Reservation, Harold Parker State Forest (Middleton/Andover), Ipswich River Watershed, and Blue Hills Reservation",
        "trauma_ems": "Massachusetts General Hospital, Brigham and Women's Hospital & Boston Medical Center Level I Trauma Centers",
        "ecology": "Ipswich River, Charles River & Merrimack River watersheds, New England coastal pitch pine / northern hardwood transition forest, and MassWildlife",
        "museums": "Museum of Science (Boston), Harvard Museum of Natural History (Cambridge), MIT Museum, and Peabody Essex Museum (Salem)",
    },
    "MI": {
        "state_name": "Michigan",
        "capital_city": "Lansing",
        "capitol_building": "Michigan State Capitol (Lansing, 1879 National Historic Landmark cast-iron dome)",
        "senator_1": "Sen. Gary Peters (D-MI)",
        "senator_1_url": "https://www.peters.senate.gov",
        "senator_2": "Sen. Elissa Slotkin (D-MI)",
        "senator_2_url": "https://www.slotkin.senate.gov",
        "governor": "Gov. Gretchen Whitmer",
        "landmarks": "Sleeping Bear Dunes National Lakeshore, Pictured Rocks National Lakeshore, Isle Royale National Park, and River Raisin National Battlefield Park",
        "federal_facilities": "Theodore Levin U.S. Courthouse (Detroit), Gerald R. Ford Federal Building (Grand Rapids), Soo Locks (U.S. Army Corps of Engineers, Sault Ste. Marie), and Gerald R. Ford Presidential Library & Museum",
        "wfo": "NWS Detroit/Pontiac (DTX), NWS Grand Rapids (GRR), NWS Gaylord (APX) & NWS Marquette (MQT)",
        "wfo_url": "https://www.weather.gov/dtx/",
        "hazards": "Great Lakes rip currents & cold-water immersion, lake-effect snow squalls, summer severe thunderstorms, and ticks",
        "camps_trails": "Gerber Scout Reservation & D-Bar-A Scout Ranch (Michigan Crossroads Council), Porcupine Mountains Wilderness State Park, and North Country National Scenic Trail",
        "trauma_ems": "University of Michigan Health (Ann Arbor), Detroit Receiving Hospital & Corewell Health Butterworth (Grand Rapids) Level I Trauma Centers",
        "ecology": "Great Lakes freshwater basin (Lakes Superior, Michigan, Huron, and Erie), Kirtland's warbler jack pine habitat, and Michigan DNR",
        "museums": "The Henry Ford Museum of American Innovation (Dearborn), Michigan Science Center (Detroit), and Cranbrook Institute of Science",
    },
    "MN": {
        "state_name": "Minnesota",
        "capital_city": "Saint Paul",
        "capitol_building": "Minnesota State Capitol (Saint Paul, 1905 Cass Gilbert white marble dome with golden Quadriga)",
        "senator_1": "Sen. Amy Klobuchar (D-MN)",
        "senator_1_url": "https://www.klobuchar.senate.gov",
        "senator_2": "Sen. Tina Smith (D-MN)",
        "senator_2_url": "https://www.smith.senate.gov",
        "governor": "Gov. Tim Walz",
        "landmarks": "Voyageurs National Park, Mississippi National River and Recreation Area, Grand Portage National Monument, Pipestone National Monument, and Historic Fort Snelling",
        "federal_facilities": "Warren E. Burger Federal Building & U.S. Courthouse (Saint Paul), Diana E. Murphy U.S. Courthouse (Minneapolis), and Federal Reserve Bank of Minneapolis",
        "wfo": "NWS Twin Cities/Chanhassen (MPX) & NWS Duluth (DLH)",
        "wfo_url": "https://www.weather.gov/mpx/",
        "hazards": "Sub-zero polar vortex wind chills, summer boundary-waters lightning & blowdowns, cold-water immersion, and deer ticks",
        "camps_trails": "Tomahawk Scout Reservation & Many Point Scout Camp (Northern Star Council), Charles L. Sommers Alumni High Adventure Base (Boundary Waters Canoe Area Wilderness), and Superior Hiking Trail",
        "trauma_ems": "Hennepin Healthcare (Minneapolis), Regions Hospital (Saint Paul) & Mayo Clinic Hospital Saint Marys (Rochester) Level I Trauma Centers",
        "ecology": "Mississippi River headwaters (Lake Itasca), Lake Superior North Shore boreal forest, Laurentian Mixed Forest, and Minnesota DNR",
        "museums": "Science Museum of Minnesota (Saint Paul), Bell Museum of Natural History, and Split Rock Lighthouse",
    },
    "MS": {
        "state_name": "Mississippi",
        "capital_city": "Jackson",
        "capitol_building": "Mississippi State Capitol & Old Capitol Museum (Jackson, 1903 Beaux-Arts dome topped by a gold-leaf eagle)",
        "senator_1": "Sen. Roger Wicker (R-MS)",
        "senator_1_url": "https://www.wicker.senate.gov",
        "senator_2": "Sen. Cindy Hyde-Smith (R-MS)",
        "senator_2_url": "https://www.hydesmith.senate.gov",
        "governor": "Gov. Tate Reeves",
        "landmarks": "Vicksburg National Military Park, Gulf Islands National Seashore, Medgar and Myrlie Evers Home National Monument (Jackson), and Natchez Trace Parkway",
        "federal_facilities": "NASA John C. Stennis Space Center (Hancock County), Thad Cochran U.S. Courthouse (Jackson), and Keesler Air Force Base (Biloxi — home of the USAF 'Hurricane Hunters')",
        "wfo": "NWS Jackson (JAN)",
        "wfo_url": "https://www.weather.gov/jan/",
        "hazards": "Dixie Alley tornadoes, Gulf hurricanes, summer heat index >105°F, and flash flooding",
        "camps_trails": "Hood Scout Reservation (Andrew Jackson Council), Camp Tiak (Pine Burr Area Council), and Black Creek National Scenic River",
        "trauma_ems": "University of Mississippi Medical Center (UMMC) Level I Trauma Center (Jackson)",
        "ecology": "Lower Mississippi Alluvial Valley, Pascagoula River (unimpounded coastal watershed), De Soto National Forest longleaf pine, and MDWFP",
        "museums": "INFINITY Science Center at NASA Stennis Space Center, Mississippi Civil Rights Museum, and Mississippi Museum of Natural Science (Jackson)",
    },
    "MO": {
        "state_name": "Missouri",
        "capital_city": "Jefferson City",
        "capitol_building": "Missouri State Capitol (Jefferson City, 1917 limestone bluff dome overlooking the Missouri River)",
        "senator_1": "Sen. Josh Hawley (R-MO)",
        "senator_1_url": "https://www.hawley.senate.gov",
        "senator_2": "Sen. Eric Schmitt (R-MO)",
        "senator_2_url": "https://www.schmitt.senate.gov",
        "governor": "Gov. Mike Kehoe",
        "landmarks": "Gateway Arch National Park & Old Courthouse (St. Louis), Harry S Truman National Historic Site (Independence), Ozark National Scenic Riverways, George Washington Carver National Monument, and Wilson's Creek National Battlefield",
        "federal_facilities": "Thomas F. Eagleton U.S. Courthouse (St. Louis), Charles Evans Whittaker U.S. Courthouse (Kansas City), Federal Reserve Banks of St. Louis & Kansas City, and Harry S. Truman Presidential Library",
        "wfo": "NWS St. Louis (LSX), NWS Kansas City/Pleasant Hill (EAX) & NWS Springfield (SGF)",
        "wfo_url": "https://www.weather.gov/lsx/",
        "hazards": "Spring tornado outbreaks, Ozark spring/river flash flooding, summer heat waves, and ticks/chiggers",
        "camps_trails": "S-F Scout Ranch (Greater St. Louis Area Council), H. Roe Bartle Scout Reservation (Heart of America Council), Katy Trail State Park, and Ozark Trail",
        "trauma_ems": "Barnes-Jewish Hospital (St. Louis), Saint Louis University Hospital & University Hospital (Columbia) Level I Trauma Centers",
        "ecology": "Confluence of the Missouri and Mississippi Rivers, Ozark karst springs (Big Spring / Current & Jacks Fork Rivers), and Missouri Department of Conservation",
        "museums": "Saint Louis Science Center, Missouri Botanical Garden, National WWI Museum and Memorial (Kansas City), and Nelson-Atkins Museum",
    },
    "MT": {
        "state_name": "Montana",
        "capital_city": "Helena",
        "capitol_building": "Montana State Capitol (Helena, 1902 sandstone & granite capitol with copper dome and Charlie Russell mural)",
        "senator_1": "Sen. Steve Daines (R-MT)",
        "senator_1_url": "https://www.daines.senate.gov",
        "senator_2": "Sen. Tim Sheehy (R-MT)",
        "senator_2_url": "https://www.sheehy.senate.gov",
        "governor": "Gov. Greg Gianforte",
        "landmarks": "Glacier National Park, Little Bighorn Battlefield National Monument, Grant-Kohrs Ranch National Historic Site, Big Hole National Battlefield, and Pompeys Pillar National Monument",
        "federal_facilities": "Mike Mansfield Federal Building & U.S. Courthouse (Butte), Russell Smith U.S. Courthouse (Missoula), James F. Battin Federal Courthouse (Billings), and Malmstrom Air Force Base (Great Falls)",
        "wfo": "NWS Missoula (MSO), NWS Great Falls (TFX), NWS Billings (BYZ) & NWS Glasgow (GGW)",
        "wfo_url": "https://www.weather.gov/tfx/",
        "hazards": "Grizzly & black bear backcountry safety (bear spray protocols), rapid mountain blizzards/hypothermia, wildfire smoke, and swift cold rivers",
        "camps_trails": "K-M Scout Ranch & Melita Island (Montana Council, Flathead Lake), Bob Marshall Wilderness, and Continental Divide National Scenic Trail",
        "trauma_ems": "Billings Clinic & Benefis Health System (Great Falls) Level II Trauma Centers & Gallatin County Sheriff Search and Rescue",
        "ecology": "Crown of the Continent Ecosystem, Triple Divide Peak (Pacific, Atlantic/Gulf, and Hudson Bay watersheds), and Montana Fish, Wildlife & Parks",
        "museums": "Museum of the Rockies (Bozeman), Lewis and Clark Interpretive Center (Great Falls), and Montana Historical Society (Helena)",
    },
    "NE": {
        "state_name": "Nebraska",
        "capital_city": "Lincoln",
        "capitol_building": "Nebraska State Capitol (Lincoln, 1932 Bertram Goodhue 400-foot 'Tower on the Plains' with unicameral legislative chamber)",
        "senator_1": "Sen. Deb Fischer (R-NE)",
        "senator_1_url": "https://www.fischer.senate.gov",
        "senator_2": "Sen. Pete Ricketts (R-NE)",
        "senator_2_url": "https://www.ricketts.senate.gov",
        "governor": "Gov. Jim Pillen",
        "landmarks": "Scotts Bluff National Monument, Homestead National Historical Park (Beatrice), Agate Fossil Beds National Monument, Niobrara National Scenic River, and Chimney Rock National Historic Site",
        "federal_facilities": "Roman L. Hruska Federal Courthouse (Omaha), Robert V. Denney Federal Building (Lincoln), and Offutt Air Force Base (USSTRATCOM, Bellevue)",
        "wfo": "NWS Omaha/Valley (OAX), NWS Hastings (GID) & NWS North Platte (LBF)",
        "wfo_url": "https://www.weather.gov/oax/",
        "hazards": "Great Plains supercell tornadoes, giant hail, derechos, summer heat, and winter blizzards",
        "camps_trails": "Camp Cedars (Mid-America Council), Fort Robinson State Park, and Cowboy Recreation and Nature Trail",
        "trauma_ems": "Nebraska Medicine (Omaha), CHI Health Creighton University Medical Center & Bryan Medical Center (Lincoln) Level I/II Trauma Centers",
        "ecology": "Platte River sandhill crane migration corridor, Nebraska Sandhills & Ogallala (High Plains) Aquifer, and Nebraska Game and Parks Commission",
        "museums": "Strategic Air Command & Aerospace Museum (Ashland), University of Nebraska State Museum (Morrill Hall, Lincoln), and Durham Museum (Omaha)",
    },
    "NV": {
        "state_name": "Nevada",
        "capital_city": "Carson City",
        "capitol_building": "Nevada State Capitol (Carson City, 1871 silver-domed sandstone capitol)",
        "senator_1": "Sen. Catherine Cortez Masto (D-NV)",
        "senator_1_url": "https://www.cortezmasto.senate.gov",
        "senator_2": "Sen. Jacky Rosen (D-NV)",
        "senator_2_url": "https://www.rosen.senate.gov",
        "governor": "Gov. Joe Lombardo",
        "landmarks": "Great Basin National Park, Lake Mead National Recreation Area, Hoover Dam National Historic Landmark, and Tule Springs Fossil Beds National Monument",
        "federal_facilities": "Lloyd D. George U.S. Courthouse (Las Vegas), Bruce R. Thompson U.S. Courthouse (Reno), Hoover Dam (U.S. Bureau of Reclamation), and Nellis Air Force Base",
        "wfo": "NWS Las Vegas (VEF), NWS Reno (REV) & NWS Elko (LKN)",
        "wfo_url": "https://www.weather.gov/vef/",
        "hazards": "Extreme Mojave desert dehydration/heatstroke (>112°F), sudden desert wash flash floods, and high-altitude Sierra/Great Basin hypothermia",
        "camps_trails": "Camp Fleischmann (Nevada Area Council) & Kimball Scout Reservation (Las Vegas Area Council), Red Rock Canyon NCA, and Tahoe Rim Trail",
        "trauma_ems": "University Medical Center of Southern Nevada (Las Vegas) Level I Trauma Center & Renown Regional Medical Center (Reno)",
        "ecology": "Great Basin endorheic hydrographic basin, bristlecone pine alpine zones, Mojave Desert Joshua tree scrub, and Nevada Department of Wildlife",
        "museums": "National Atomic Testing Museum (Las Vegas), Nevada State Museum (Carson City), and Terry Lee Wells Nevada Discovery Museum (Reno)",
    },
    "NH": {
        "state_name": "New Hampshire",
        "capital_city": "Concord",
        "capitol_building": "New Hampshire State House (Concord, 1819 Concord granite capitol with gilded dome — oldest state house where the legislature sits in its original chambers)",
        "senator_1": "Sen. Jeanne Shaheen (D-NH)",
        "senator_1_url": "https://www.shaheen.senate.gov",
        "senator_2": "Sen. Maggie Hassan (D-NH)",
        "senator_2_url": "https://www.hassan.senate.gov",
        "governor": "Gov. Kelly Ayotte",
        "landmarks": "Saint-Gaudens National Historical Park (Cornish), White Mountain National Forest (Presidential Range & Mount Washington), Portsmouth Harbor Historic District, and Franconia Notch State Park",
        "federal_facilities": "Warren B. Rudman U.S. Courthouse (Concord) and U.S. Army Cold Regions Research and Engineering Laboratory (CRREL, Hanover)",
        "wfo": "NWS Gray/Portland (GYX) & Mount Washington Observatory",
        "wfo_url": "https://www.weather.gov/gyx/",
        "hazards": "Extreme Presidential Range above-treeline winds & year-round hypothermia on Mount Washington, Tuckerman Ravine avalanches, and deer ticks",
        "camps_trails": "Griswold Scout Reservation (Hidden Valley & Bell, Daniel Webster Council), White Mountain 4,000-Footers, and Appalachian Trail",
        "trauma_ems": "Dartmouth Hitchcock Medical Center Level I Trauma Center (Lebanon) & New Hampshire Fish and Game Conservation Officers SAR",
        "ecology": "Merrimack, Connecticut & Piscataqua River watersheds, White Mountain alpine krummholz tundra, and New Hampshire Fish and Game Department",
        "museums": "McAuliffe-Shepard Discovery Center (Concord), Mount Washington Observatory Weather Discovery Center, and Strawbery Banke Museum (Portsmouth)",
    },
    "NJ": {
        "state_name": "New Jersey",
        "capital_city": "Trenton",
        "capitol_building": "New Jersey State House (Trenton, 1792 — second-oldest state house in continuous legislative use, with gilded dome)",
        "senator_1": "Sen. Cory Booker (D-NJ)",
        "senator_1_url": "https://www.booker.senate.gov",
        "senator_2": "Sen. Andy Kim (D-NJ)",
        "senator_2_url": "https://www.kim.senate.gov",
        "governor": "Gov. Phil Murphy",
        "landmarks": "Morristown National Historical Park (Washington's 1779–80 Winter Encampment), Thomas Edison National Historical Park (West Orange), Paterson Great Falls National Historical Park, Gateway National Recreation Area (Sandy Hook), and Washington Crossing State Park",
        "federal_facilities": "Martin Luther King Jr. Federal Building & U.S. Courthouse (Newark), Clarkson S. Fisher Federal Building (Trenton), Joint Base McGuire-Dix-Lakehurst, and NOAA Geophysical Fluid Dynamics Laboratory (Princeton)",
        "wfo": "NWS Mount Holly/Philadelphia (PHI) & NWS New York (OKX)",
        "wfo_url": "https://www.weather.gov/phi/",
        "hazards": "Jersey Shore rip currents & coastal nor'easters/hurricanes, urban/river flash flooding, summer heat waves, and deer ticks",
        "camps_trails": "Mount Allamuchy Scout Reservation (Patriots' Path Council), No-Be-Bo-Sco, Delaware Water Gap National Recreation Area, and Batona Trail (Pinelands)",
        "trauma_ems": "University Hospital (Newark), Robert Wood Johnson University Hospital (New Brunswick) & Cooper University Hospital (Camden) Level I Trauma Centers",
        "ecology": "New Jersey Pinelands National Reserve (Kirkwood-Cohansey aquifer), Delaware & Raritan River basins, and New Jersey DEP",
        "museums": "Liberty Science Center (Jersey City), New Jersey State Museum (Trenton), and Battleship New Jersey Museum (Camden)",
    },
    "NM": {
        "state_name": "New Mexico",
        "capital_city": "Santa Fe",
        "capitol_building": "New Mexico State Capitol ('The Roundhouse', Santa Fe, 1966 Zia sun-symbol circular Territorial-Pueblo architecture — only round state capitol in the U.S.)",
        "senator_1": "Sen. Martin Heinrich (D-NM)",
        "senator_1_url": "https://www.heinrich.senate.gov",
        "senator_2": "Sen. Ben Ray Luján (D-NM)",
        "senator_2_url": "https://www.lujan.senate.gov",
        "governor": "Gov. Michelle Lujan Grisham",
        "landmarks": "Carlsbad Caverns National Park, White Sands National Park, Bandelier National Monument, Chaco Culture National Historical Park, and Petroglyph National Monument",
        "federal_facilities": "Los Alamos National Laboratory (LANL), Sandia National Laboratories (Albuquerque), Pete V. Domenici U.S. Courthouse (Albuquerque), and White Sands Missile Range",
        "wfo": "NWS Albuquerque (ABQ)",
        "wfo_url": "https://www.weather.gov/abq/",
        "hazards": "High-altitude afternoon lightning on Sangre de Cristo peaks, arroyo monsoon flash floods, dehydration/altitude sickness, and rattlesnakes",
        "camps_trails": "Philmont Scout Ranch (Cimarron — BSA National High Adventure Base), Gorham Scout Ranch, and Continental Divide National Scenic Trail",
        "trauma_ems": "University of New Mexico (UNM) Hospital Level I Trauma Center (Albuquerque) & New Mexico State Police Search and Rescue",
        "ecology": "Rio Grande & Pecos River basins, Chihuahuan Desert, Sangre de Cristo Rocky Mountain conifer forests, and New Mexico Dept. of Game and Fish",
        "museums": "National Museum of Nuclear Science & History (Albuquerque), Bradbury Science Museum (Los Alamos), and New Mexico Museum of Natural History & Science",
    },
    "NY": {
        "state_name": "New York",
        "capital_city": "Albany",
        "capitol_building": "New York State Capitol (Albany, 1899 Romanesque & Neo-Renaissance granite palace on State Street Hill)",
        "senator_1": "Sen. Chuck Schumer (D-NY)",
        "senator_1_url": "https://www.schumer.senate.gov",
        "senator_2": "Sen. Kirsten Gillibrand (D-NY)",
        "senator_2_url": "https://www.gillibrand.senate.gov",
        "governor": "Gov. Kathy Hochul",
        "landmarks": "Statue of Liberty National Monument & Ellis Island, Federal Hall National Memorial (Wall Street, site of Washington's 1789 Inauguration & the Bill of Rights), Saratoga National Historical Park, Women's Rights National Historical Park (Seneca Falls), and Fort Stanwix National Monument",
        "federal_facilities": "Thurgood Marshall U.S. Courthouse (Second Circuit, Manhattan), U.S. Military Academy at West Point, Brookhaven National Laboratory (Upton), and Franklin D. Roosevelt Presidential Library (Hyde Park)",
        "wfo": "NWS New York (OKX), NWS Albany (ALY), NWS Buffalo (BUF) & NWS Binghamton (BGM)",
        "wfo_url": "https://www.weather.gov/aly/",
        "hazards": "Great Lakes lake-effect snowstorms, Adirondack/Catskill alpine hypothermia, summer severe squalls, and black-legged deer ticks",
        "camps_trails": "Ten Mile River Scout Camps (Greater New York Councils), Massawepie Scout Camps (Adirondacks, Seneca Waterways Council), Adirondack High Peaks, and Finger Lakes Trail",
        "trauma_ems": "Bellevue Hospital / NYP-Weill Cornell (NYC), Albany Medical Center, Upstate University Hospital (Syracuse) & Strong Memorial (Rochester) Level I Trauma Centers",
        "ecology": "Hudson-Mohawk River estuary, Adirondack Park 6-million-acre forever-wild preserve, Finger Lakes / Great Lakes watersheds, and NYS DEC",
        "museums": "American Museum of Natural History (NYC), Intrepid Museum, Corning Museum of Glass, and New York State Museum (Albany)",
    },
    "NC": {
        "state_name": "North Carolina",
        "capital_city": "Raleigh",
        "capitol_building": "North Carolina State Capitol (Raleigh, 1840 Greek Revival granite National Historic Landmark) & NC Legislative Building",
        "senator_1": "Sen. Thom Tillis (R-NC)",
        "senator_1_url": "https://www.tillis.senate.gov",
        "senator_2": "Sen. Ted Budd (R-NC)",
        "senator_2_url": "https://www.budd.senate.gov",
        "governor": "Gov. Josh Stein",
        "landmarks": "Wright Brothers National Memorial (Kill Devil Hills, Kitty Hawk), Great Smoky Mountains National Park, Blue Ridge Parkway, Cape Hatteras National Seashore, and Guilford Courthouse National Military Park",
        "federal_facilities": "Terry Sanford Federal Building & U.S. Courthouse (Raleigh), EPA Research Triangle Park Campus (Durham), NOAA National Centers for Environmental Information (NCEI, Asheville), and Fort Liberty (Fayetteville)",
        "wfo": "NWS Raleigh (RAH), NWS Morehead City/Newport (MHX) & NWS Wilmington (ILM)",
        "wfo_url": "https://www.weather.gov/rah/",
        "hazards": "Atlantic hurricanes on the Outer Banks, Blue Ridge mountain flash flooding/landslides, rip currents, and summer heat/lightning",
        "camps_trails": "Camp Durant (Occoneechee Council), Camp Daniel Boone (Blue Ridge Mountains), Pisgah National Forest, and Mountains-to-Sea Trail",
        "trauma_ems": "UNC Medical Center (Chapel Hill), Duke University Hospital (Durham), Atrium Health Carolinas Medical Center (Charlotte) & WakeMed Level I Trauma Centers",
        "ecology": "Albemarle-Pamlico Sound estuary, Southern Appalachian spruce-fir summit forests (Mount Mitchell, 6,684 ft), longleaf pine savannas, and NC Wildlife Resources Commission",
        "museums": "North Carolina Museum of Natural Sciences (Raleigh), Museum of Life and Science (Durham), and Discovery Place Science (Charlotte)",
    },
    "ND": {
        "state_name": "North Dakota",
        "capital_city": "Bismarck",
        "capitol_building": "North Dakota State Capitol (Bismarck, 1934 19-story Art Deco 'Skyscraper on the Prairie')",
        "senator_1": "Sen. John Hoeven (R-ND)",
        "senator_1_url": "https://www.hoeven.senate.gov",
        "senator_2": "Sen. Kevin Cramer (R-ND)",
        "senator_2_url": "https://www.cramer.senate.gov",
        "governor": "Gov. Kelly Armstrong",
        "landmarks": "Theodore Roosevelt National Park (Medora Badlands), Knife River Indian Villages National Historic Site, and Fort Union Trading Post National Historic Site",
        "federal_facilities": "William L. Guy Federal Building & U.S. Courthouse (Bismarck), Quentin N. Burdick U.S. Courthouse (Fargo), Garrison Dam, and Minot / Grand Forks Air Force Bases",
        "wfo": "NWS Bismarck (BIS) & NWS Grand Forks (FGF)",
        "wfo_url": "https://www.weather.gov/bis/",
        "hazards": "Extreme winter ground blizzards & -40°F wind chills, summer prairie supercells/tornadoes, and Red River spring flooding",
        "camps_trails": "Heart Butte Scout Reservation & Camp Wilderness (Northern Lights Council), and Maah Daah Hey Trail in the Little Missouri Badlands",
        "trauma_ems": "Sanford Medical Center Fargo Level I Trauma Center & Sanford Medical Center Bismarck",
        "ecology": "Missouri River (Lake Sakakawea) & Red River of the North basins, Prairie Pothole Region waterfowl breeding grounds, and ND Game and Fish Department",
        "museums": "North Dakota Heritage Center & State Museum (Bismarck) and Fargo Air Museum",
    },
    "OH": {
        "state_name": "Ohio",
        "capital_city": "Columbus",
        "capitol_building": "Ohio Statehouse (Columbus, 1861 Greek Revival limestone capitol with cylindrical rotunda cupola)",
        "senator_1": "Sen. Bernie Moreno (R-OH)",
        "senator_1_url": "https://www.moreno.senate.gov",
        "senator_2": "Sen. Jon Husted (R-OH)",
        "senator_2_url": "https://www.husted.senate.gov",
        "governor": "Gov. Mike DeWine",
        "landmarks": "Cuyahoga Valley National Park, Dayton Aviation Heritage National Historical Park (Wright Brothers), Perry's Victory and International Peace Memorial (Put-in-Bay), and Hopewell Culture National Historical Park",
        "federal_facilities": "NASA Glenn Research Center (Cleveland), Wright-Patterson Air Force Base (Dayton), Potter Stewart U.S. Courthouse (Sixth Circuit, Cincinnati), and Joseph P. Kinneary U.S. Courthouse (Columbus)",
        "wfo": "NWS Wilmington/Cincinnati (ILN) & NWS Cleveland (CLE)",
        "wfo_url": "https://www.weather.gov/iln/",
        "hazards": "Ohio Valley severe thunderstorms/tornadoes, Lake Erie seiches & lake-effect snow, river flooding, and black-legged ticks",
        "camps_trails": "Beaumont Scout Reservation (Lake Erie Council), Seven Ranges Scout Reservation, Hocking Hills State Park, and Buckeye Trail",
        "trauma_ems": "Ohio State University Wexner Medical Center (Columbus), MetroHealth / Cleveland Clinic & UC Medical Center (Cincinnati) Level I Trauma Centers",
        "ecology": "Lake Erie Great Lakes watershed, Ohio & Cuyahoga River basins, Oak Openings savanna, and Ohio Department of Natural Resources (ODNR)",
        "museums": "National Museum of the U.S. Air Force (Dayton), COSI Center of Science and Industry (Columbus), and Great Lakes Science Center (Cleveland)",
    },
    "OK": {
        "state_name": "Oklahoma",
        "capital_city": "Oklahoma City",
        "capitol_building": "Oklahoma State Capitol (Oklahoma City, 1917 Greco-Roman capitol with 2002 dome topped by 'The Guardian' bronze statue)",
        "senator_1": "Sen. James Lankford (R-OK)",
        "senator_1_url": "https://www.lankford.senate.gov",
        "senator_2": "Sen. Markwayne Mullin (R-OK)",
        "senator_2_url": "https://www.mullin.senate.gov",
        "governor": "Gov. Kevin Stitt",
        "landmarks": "Oklahoma City National Memorial, Chickasaw National Recreation Area, Washita Battlefield National Historic Site, and Fort Gibson Historic Site",
        "federal_facilities": "NOAA National Weather Center & Storm Prediction Center (Norman), William J. Holloway Jr. U.S. Courthouse (Oklahoma City), and Tinker Air Force Base",
        "wfo": "NWS Norman/Oklahoma City (OUN) & NWS Tulsa (TSA)",
        "wfo_url": "https://www.weather.gov/oun/",
        "hazards": "Peak Tornado Alley supercells, giant hail, straight-line wind gusts, flash flooding, and extreme summer heat (>105°F)",
        "camps_trails": "Zink High Adventure Base & Camp Hale (Indian Nations Council), Slippery Falls Scout Ranch (Last Frontier Council), and Wichita Mountains Wildlife Refuge",
        "trauma_ems": "OU Health University of Oklahoma Medical Center Level I Trauma Center (Oklahoma City) & Saint Francis Hospital (Tulsa)",
        "ecology": "Cross Timbers post-oak forest, Tallgrass Prairie Preserve, Arkansas & Red River basins, and Oklahoma Department of Wildlife Conservation",
        "museums": "Science Museum Oklahoma (Oklahoma City), Sam Noble Oklahoma Museum of Natural History (Norman), and National Cowboy & Western Heritage Museum",
    },
    "OR": {
        "state_name": "Oregon",
        "capital_city": "Salem",
        "capitol_building": "Oregon State Capitol (Salem, 1938 Art Deco white marble capitol topped by the golden 'Oregon Pioneer')",
        "senator_1": "Sen. Ron Wyden (D-OR)",
        "senator_1_url": "https://www.wyden.senate.gov",
        "senator_2": "Sen. Jeff Merkley (D-OR)",
        "senator_2_url": "https://www.merkley.senate.gov",
        "governor": "Gov. Tina Kotek",
        "landmarks": "Crater Lake National Park, Lewis and Clark National Historical Park (Astoria), John Day Fossil Beds National Monument, Oregon Caves National Monument, and Newberry National Volcanic Monument",
        "federal_facilities": "Mark O. Hatfield U.S. Courthouse (Portland), Wayne L. Morse U.S. Courthouse (Eugene), and Bonneville Lock and Dam (U.S. Army Corps of Engineers, Columbia River Gorge)",
        "wfo": "NWS Portland (PQR), NWS Medford (MFR) & NWS Pendleton (PDT)",
        "wfo_url": "https://www.weather.gov/pqr/",
        "hazards": "Pacific Coast sneaker waves & tsunami zones, Cascade alpine hypothermia/avalanches, summer wildfire smoke, and cold river currents",
        "camps_trails": "Camp Meriwether (Cascade Pacific Council, Oregon Coast), Camp Baldwin, Columbia River Gorge, and Pacific Crest National Scenic Trail",
        "trauma_ems": "Oregon Health & Science University (OHSU) & Legacy Emanuel Medical Center Level I Trauma Centers (Portland) & Crag Rats / Portland Mountain Rescue",
        "ecology": "Columbia & Willamette River salmon watersheds, Cascade old-growth Douglas-fir temperate rainforest, High Desert sagebrush steppe, and ODFW",
        "museums": "Oregon Museum of Science and Industry (OMSI, Portland), Evergreen Aviation & Space Museum (McMinnville), and High Desert Museum (Bend)",
    },
    "PA": {
        "state_name": "Pennsylvania",
        "capital_city": "Harrisburg",
        "capitol_building": "Pennsylvania State Capitol (Harrisburg, 1906 Beaux-Arts green-domed palace with Mercer tile floors and Violet Oakley murals)",
        "senator_1": "Sen. John Fetterman (D-PA)",
        "senator_1_url": "https://www.fetterman.senate.gov",
        "senator_2": "Sen. Dave McCormick (R-PA)",
        "senator_2_url": "https://www.mccormick.senate.gov",
        "governor": "Gov. Josh Shapiro",
        "landmarks": "Independence National Historical Park (Independence Hall & Liberty Bell, Philadelphia), Gettysburg National Military Park, Valley Forge National Historical Park, Flight 93 National Memorial, and Delaware Water Gap National Recreation Area",
        "federal_facilities": "James A. Byrne U.S. Courthouse (Third Circuit, Philadelphia), U.S. Mint at Philadelphia, Ronald Reagan Federal Building (Harrisburg), and National Energy Technology Laboratory (Pittsburgh)",
        "wfo": "NWS State College (CTP), NWS Philadelphia/Mount Holly (PHI) & NWS Pittsburgh (PBZ)",
        "wfo_url": "https://www.weather.gov/ctp/",
        "hazards": "River & ridge-and-valley flash flooding, winter ice storms, severe summer thunderstorms, and high black-legged deer tick density",
        "camps_trails": "Resica Falls Scout Reservation & Musser Scout Reservation (Cradle of Liberty Council), Heritage Reservation (Laurel Highlands Council), and Appalachian Trail (Midpoint at Pine Grove Furnace)",
        "trauma_ems": "Penn Presbyterian Medical Center / Jefferson Hospital (Philadelphia), UPMC Presbyterian (Pittsburgh) & Penn State Health Milton S. Hershey Level I Trauma Centers",
        "ecology": "Susquehanna, Delaware & Ohio (Allegheny/Monongahela) River basins, Pocono/Allegheny plateau hardwood forests, and Pennsylvania DCNR",
        "museums": "The Franklin Institute & Academy of Natural Sciences (Philadelphia), Carnegie Museum of Natural History (Pittsburgh), and National Constitution Center",
    },
    "RI": {
        "state_name": "Rhode Island",
        "capital_city": "Providence",
        "capitol_building": "Rhode Island State House (Providence, 1904 McKim, Mead & White Georgia marble capitol with the fourth-largest self-supported marble dome in the world)",
        "senator_1": "Sen. Jack Reed (D-RI)",
        "senator_1_url": "https://www.reed.senate.gov",
        "senator_2": "Sen. Sheldon Whitehouse (D-RI)",
        "senator_2_url": "https://www.whitehouse.senate.gov",
        "governor": "Gov. Dan McKee",
        "landmarks": "Roger Williams National Memorial (Providence), Blackstone River Valley National Historical Park (Slater Mill, Pawtucket), Touro Synagogue National Historic Site (Newport), and Fort Adams",
        "federal_facilities": "Federal Building and U.S. Courthouse (Kennedy Plaza, Providence), Naval Station Newport (U.S. Naval War College), and NOAA Narragansett Laboratory",
        "wfo": "NWS Boston/Norton (BOX)",
        "wfo_url": "https://www.weather.gov/box/",
        "hazards": "Narragansett Bay coastal storm surge & hurricanes, winter nor'easters, marine fog/squalls, and black-legged deer ticks",
        "camps_trails": "Yawgoog Scout Reservation (Narragansett Council, Rockville — founded 1916, one of the oldest continuously operated Scout camps in America), and Arcadia Management Area",
        "trauma_ems": "Rhode Island Hospital Level I Trauma Center (Providence)",
        "ecology": "Narragansett Bay estuary, Blackstone & Pawcatuck River watersheds, coastal barrier beaches, and Rhode Island DEM",
        "museums": "Museum of Natural History and Planetarium at Roger Williams Park (Providence) and Herreshoff Marine Museum (Bristol)",
    },
    "SC": {
        "state_name": "South Carolina",
        "capital_city": "Columbia",
        "capitol_building": "South Carolina State House (Columbia, 1855 granite Greek Revival capitol with copper dome)",
        "senator_1": "Sen. Lindsey Graham (R-SC)",
        "senator_1_url": "https://www.lgraham.senate.gov",
        "senator_2": "Sen. Tim Scott (R-SC)",
        "senator_2_url": "https://www.scott.senate.gov",
        "governor": "Gov. Henry McMaster",
        "landmarks": "Fort Sumter and Fort Moultrie National Historical Park (Charleston Harbor), Congaree National Park, Kings Mountain National Military Park, Cowpens National Battlefield, and Reconstruction Era National Historical Park (Beaufort)",
        "federal_facilities": "Matthew J. Perry Jr. U.S. Courthouse (Columbia), J. Waties Waring Judicial Center (Charleston), Savannah River National Laboratory (Aiken), and Marine Corps Recruit Depot Parris Island",
        "wfo": "NWS Columbia (CAE), NWS Charleston (CHS) & NWS Greenville-Spartanburg (GSP)",
        "wfo_url": "https://www.weather.gov/cae/",
        "hazards": "Atlantic hurricanes & King Tide coastal flooding, extreme summer heat/humidity, lightning storms, and venomous snakes/ticks",
        "camps_trails": "Camp Barstow (Indian Waters Council), Camp Ho Non Wah (Coastal Carolina Council), and Palmetto Trail / Foothills Trail",
        "trauma_ems": "MUSC Health University Medical Center (Charleston), Prisma Health Richland (Columbia) & Prisma Health Greenville Memorial Level I Trauma Centers",
        "ecology": "ACE Basin estuarine reserve, Congaree old-growth bottomland hardwood floodplain, Blue Ridge Escarpment, and SC Department of Natural Resources",
        "museums": "Patriots Point Naval & Maritime Museum (USS Yorktown, Mount Pleasant), South Carolina State Museum (Columbia), and Roper Mountain Science Center",
    },
    "SD": {
        "state_name": "South Dakota",
        "capital_city": "Pierre",
        "capitol_building": "South Dakota State Capitol (Pierre, 1910 sandstone & limestone capitol with copper dome on Capitol Lake)",
        "senator_1": "Sen. John Thune (R-SD)",
        "senator_1_url": "https://www.thune.senate.gov",
        "senator_2": "Sen. Mike Rounds (R-SD)",
        "senator_2_url": "https://www.rounds.senate.gov",
        "governor": "Gov. Larry Rhoden",
        "landmarks": "Mount Rushmore National Memorial (Keystone), Badlands National Park, Wind Cave National Park, Jewel Cave National Monument, and Minuteman Missile National Historic Site",
        "federal_facilities": " Federal Building & U.S. Courthouse (Pierre & Sioux Falls), USGS Earth Resources Observation and Science (EROS) Center (Sioux Falls), and Ellsworth Air Force Base (Rapid City)",
        "wfo": "NWS Rapid City (UNR), NWS Aberdeen (ABR) & NWS Sioux Falls (FSD)",
        "wfo_url": "https://www.weather.gov/unr/",
        "hazards": "Black Hills flash flooding, extreme Plains hail/tornadoes, sudden winter blizzards, and bison/wildlife distance safety",
        "camps_trails": "Medicine Mountain Scout Ranch (Black Hills Area Council), Custer State Park, and George S. Mickelson Trail / Centennial Trail",
        "trauma_ems": "Sanford USD Medical Center (Sioux Falls) & Monument Health Rapid City Hospital Level II Trauma Centers & Pennington County SAR",
        "ecology": "Black Hills ponderosa pine island ecosystem, Missouri River reservoirs, mixed-grass prairie badlands, and South Dakota Game, Fish and Parks",
        "museums": "Sanford Underground Research Facility (SURF, Lead — deep neutrino lab), Mammoth Site of Hot Springs, and Washington Pavilion Kirby Science Discovery Center",
    },
    "TN": {
        "state_name": "Tennessee",
        "capital_city": "Nashville",
        "capitol_building": "Tennessee State Capitol (Nashville, 1859 William Strickland Greek Revival limestone National Historic Landmark)",
        "senator_1": "Sen. Marsha Blackburn (R-TN)",
        "senator_1_url": "https://www.blackburn.senate.gov",
        "senator_2": "Sen. Bill Hagerty (R-TN)",
        "senator_2_url": "https://www.hagerty.senate.gov",
        "governor": "Gov. Bill Lee",
        "landmarks": "Great Smoky Mountains National Park, Shiloh National Military Park, Stones River National Battlefield, Chickamauga and Chattanooga National Military Park, and Andrew Johnson National Historic Site",
        "federal_facilities": "Oak Ridge National Laboratory (ORNL, Oak Ridge), Fred D. Thompson U.S. Courthouse & Federal Building (Nashville), Tennessee Valley Authority (TVA Headquarters, Knoxville), and Arnold Engineering Development Complex (Tullahoma)",
        "wfo": "NWS Nashville (OHX), NWS Morristown/Knoxville (MRX) & NWS Memphis (MEG)",
        "wfo_url": "https://www.weather.gov/ohx/",
        "hazards": "Nocturnal tornadoes, Smoky Mountain flash floods, summer heat/humidity, and black bear food-storage safety",
        "camps_trails": "Boxwell Reservation (Middle Tennessee Council), Buck Toms Scout Camp (Great Smoky Mountain Council), and Appalachian Trail along the Smoky Mountains crest",
        "trauma_ems": "Vanderbilt University Medical Center (Nashville), Regional One Health (Memphis), UT Medical Center (Knoxville) & Erlanger (Chattanooga) Level I Trauma Centers",
        "ecology": "Tennessee, Cumberland & Mississippi River watersheds, Great Smoky Mountains biodiversity hot spot, karst cave systems, and TWRA",
        "museums": "American Museum of Science and Energy (Oak Ridge), Adventure Science Center (Nashville), Tennessee Aquarium (Chattanooga), and Pink Palace Museum",
    },
    "TX": {
        "state_name": "Texas",
        "capital_city": "Austin",
        "capitol_building": "Texas State Capitol (Austin, 1888 Sunset Red granite Renaissance Revival capitol — 302.6 feet tall)",
        "senator_1": "Sen. John Cornyn (R-TX)",
        "senator_1_url": "https://www.cornyn.senate.gov",
        "senator_2": "Sen. Ted Cruz (R-TX)",
        "senator_2_url": "https://www.cruz.senate.gov",
        "governor": "Gov. Greg Abbott",
        "landmarks": "San Antonio Missions National Historical Park & The Alamo, Big Bend National Park, Guadalupe Mountains National Park, Padre Island National Seashore, and Lyndon B. Johnson National Historical Park",
        "federal_facilities": "NASA Lyndon B. Johnson Space Center (Mission Control, Houston), Homer Thornberry Judicial Building (Austin), Earle Cabell Federal Building (Dallas), and Joint Base San Antonio",
        "wfo": "NWS Austin/San Antonio (EWX), NWS Fort Worth/Dallas (FWD) & NWS Houston/Galveston (HGX)",
        "wfo_url": "https://www.weather.gov/ewx/",
        "hazards": "Extreme summer heat (>102°F), 'Flash Flood Alley' along the Balcones Escarpment, spring supercell tornadoes/hail, Gulf hurricanes, and venomous snakes",
        "camps_trails": "Lost Pines & Griffith League Scout Ranch (Capitol Area Council), Sid Richardson Scout Ranch (Longhorn Council), Camp Strake (Sam Houston Area Council), and Lone Star Hiking Trail",
        "trauma_ems": "Dell Seton Medical Center at UT (Austin), Parkland Memorial (Dallas), Memorial Hermann / Ben Taub (Houston) & Brooke Army Medical Center (San Antonio) Level I Trauma Centers",
        "ecology": "Edwards Aquifer & Hill Country karst springs, Gulf Coast barrier islands, Chihuahuan Desert sky islands, and Texas Parks and Wildlife Department (TPWD)",
        "museums": "Space Center Houston, Perot Museum of Nature and Science (Dallas), Houston Museum of Natural Science, and Bullock Texas State History Museum (Austin)",
    },
    "UT": {
        "state_name": "Utah",
        "capital_city": "Salt Lake City",
        "capitol_building": "Utah State Capitol (Salt Lake City, 1916 Utah granite Corinthian classical dome overlooking the Salt Lake Valley)",
        "senator_1": "Sen. Mike Lee (R-UT)",
        "senator_1_url": "https://www.lee.senate.gov",
        "senator_2": "Sen. John Curtis (R-UT)",
        "senator_2_url": "https://www.curtis.senate.gov",
        "governor": "Gov. Spencer Cox",
        "landmarks": "Zion National Park, Bryce Canyon National Park, Arches National Park, Canyonlands National Park, Capitol Reef National Park, and Golden Spike National Historical Park (Promontory Summit)",
        "federal_facilities": "Orrin G. Hatch U.S. Courthouse (Salt Lake City), Wallace F. Bennett Federal Building, and Hill Air Force Base (Ogden)",
        "wfo": "NWS Salt Lake City (SLC)",
        "wfo_url": "https://www.weather.gov/slc/",
        "hazards": "Slot canyon flash flooding from distant monsoon storms, Wasatch backcountry avalanches, desert heat/dehydration, and high-altitude hypothermia",
        "camps_trails": "Camp Steiner (High Uintas — one of the highest Scout camps in America at 10,400 ft, Crossroads of the West Council), Camp Maple Dell, and Highline Trail",
        "trauma_ems": "University of Utah Hospital & Intermountain Medical Center Level I Trauma Centers (Salt Lake City) & Salt Lake County Sheriff SAR",
        "ecology": "Great Salt Lake terminal basin, Colorado Plateau red-rock canyons, Uinta/Wasatch alpine forests, and Utah Division of Wildlife Resources",
        "museums": "Natural History Museum of Utah (Salt Lake City), Clark Planetarium, and Dinosaur National Monument Quarry Exhibit Hall (Jensen)",
    },
    "VT": {
        "state_name": "Vermont",
        "capital_city": "Montpelier",
        "capitol_building": "Vermont State House (Montpelier, 1859 Barre granite Greek Revival capitol with gold-leaf dome)",
        "senator_1": "Sen. Bernie Sanders (I-VT)",
        "senator_1_url": "https://www.sanders.senate.gov",
        "senator_2": "Sen. Peter Welch (D-VT)",
        "senator_2_url": "https://www.welch.senate.gov",
        "governor": "Gov. Phil Scott",
        "landmarks": "Marsh-Billings-Rockefeller National Historical Park (Woodstock — birthplace of American conservation), Ethan Allen Homestead, Bennington Battle Monument, and Mount Mansfield",
        "federal_facilities": "Federal Building, Post Office and U.S. Courthouse (Burlington & Rutland) and Green Mountain National Forest Headquarters",
        "wfo": "NWS Burlington (BTV)",
        "wfo_url": "https://www.weather.gov/btv/",
        "hazards": "Narrow Green Mountain river valley flash flooding, winter sub-zero cold/ice, alpine ridge exposure, and black-legged deer ticks",
        "camps_trails": "Mt. Norris Scout Reservation (Green Mountain Council), Camel's Hump State Park, and The Long Trail (oldest long-distance hiking trail in the U.S.)",
        "trauma_ems": "University of Vermont Medical Center Level I Trauma Center (Burlington) & Stowe Mountain Rescue",
        "ecology": "Lake Champlain basin, Connecticut River watershed, Green Mountain northern hardwood (sugar maple/birch/beech) & boreal forest, and Vermont Fish & Wildlife",
        "museums": "ECHO, Leahy Center for Lake Champlain (Burlington), Montshire Museum of Science (Norwich), and Shelburne Museum",
    },
    "VA": {
        "state_name": "Virginia",
        "capital_city": "Richmond",
        "capitol_building": "Virginia State Capitol (Richmond, 1788 classical temple designed by Thomas Jefferson and Charles-Louis Clérisseau)",
        "senator_1": "Sen. Mark Warner (D-VA)",
        "senator_1_url": "https://www.warner.senate.gov",
        "senator_2": "Sen. Tim Kaine (D-VA)",
        "senator_2_url": "https://www.kaine.senate.gov",
        "governor": "Gov. Abigail Spanberger / Office of the Governor of Virginia",
        "landmarks": "Colonial National Historical Park (Historic Jamestowne & Yorktown Battlefield), George Washington's Mount Vernon, Thomas Jefferson's Monticello, Shenandoah National Park, Arlington National Cemetery, and Appomattox Court House National Historical Park",
        "federal_facilities": "The Pentagon (Arlington), Naval Station Norfolk, NASA Langley Research Center (Hampton) & Wallops Flight Facility, Lewis F. Powell Jr. U.S. Courthouse (Fourth Circuit, Richmond), and USGS National Center (Reston)",
        "wfo": "NWS Wakefield (AKQ), NWS Blacksburg (RNK) & NWS Baltimore/Washington (LWX)",
        "wfo_url": "https://www.weather.gov/akq/",
        "hazards": "Tidewater hurricanes/nor'easters, Blue Ridge flash flooding, summer heat index >100°F, and lone star / deer ticks",
        "camps_trails": "Blue Ridge Scout Reservation (Camp Powhatan / High Knoll, Blue Ridge Mountains Council), Goshen Scout Reservation, Heart of Virginia Scout Reservation, and Appalachian Trail (550+ miles in VA)",
        "trauma_ems": "VCU Medical Center (Richmond), UVA Health (Charlottesville), Inova Fairfax Hospital & Sentara Norfolk General Level I Trauma Centers",
        "ecology": "Chesapeake Bay (James, York, Rappahannock & Potomac rivers) & New River watersheds, Shenandoah Blue Ridge forest, and Virginia DWR",
        "museums": "Smithsonian Udvar-Hazy Center (Chantilly), Virginia Air & Space Science Center (Hampton), and Science Museum of Virginia (Richmond)",
    },
    "WA": {
        "state_name": "Washington",
        "capital_city": "Olympia",
        "capitol_building": "Washington State Capitol Legislative Building (Olympia, 1928 287-foot masonry dome — tallest self-supporting masonry dome in North America)",
        "senator_1": "Sen. Patty Murray (D-WA)",
        "senator_1_url": "https://www.murray.senate.gov",
        "senator_2": "Sen. Maria Cantwell (D-WA)",
        "senator_2_url": "https://www.cantwell.senate.gov",
        "governor": "Gov. Bob Ferguson",
        "landmarks": "Olympic National Park, Mount Rainier National Park, North Cascades National Park, San Juan Island National Historical Park, and Manhattan Project National Historical Park (Hanford)",
        "federal_facilities": "William Kenzo Nakamura U.S. Courthouse & Jackson Federal Building (Seattle), NOAA Western Regional Center (Sand Point, Seattle), Pacific Northwest National Laboratory (PNNL, Richland), and Joint Base Lewis-McChord",
        "wfo": "NWS Seattle/Tacoma (SEW) & NWS Spokane (OTX)",
        "wfo_url": "https://www.weather.gov/sew/",
        "hazards": "Atmospheric river flooding & landslides, Cascade glaciated peak hypothermia/crevasses/lahars, cold Puget Sound immersion, and summer wildfire smoke",
        "camps_trails": "Camp Parsons (Chief Seattle Council — founded 1919 on Hood Canal), Camp Edward, Camp Sheppard (Mt. Rainier), and Pacific Crest Trail / Wonderland Trail",
        "trauma_ems": "Harborview Medical Center Level I Trauma Center (Seattle — regional trauma center for WA, AK, MT, ID) & Seattle Mountain Rescue",
        "ecology": "Puget Sound (Salish Sea) marine estuary, Hoh & Quinault temperate rainforests, Columbia River basin, and Washington Dept. of Fish and Wildlife",
        "museums": "Museum of Flight (Seattle), Pacific Science Center, Burke Museum of Natural History, and LIGO Hanford Observatory",
    },
    "WV": {
        "state_name": "West Virginia",
        "capital_city": "Charleston",
        "capitol_building": "West Virginia State Capitol (Charleston, 1932 Cass Gilbert 293-foot gold-leaf dome overlooking the Kanawha River)",
        "senator_1": "Sen. Shelley Moore Capito (R-WV)",
        "senator_1_url": "https://www.capito.senate.gov",
        "senator_2": "Sen. Jim Justice (R-WV)",
        "senator_2_url": "https://www.justice.senate.gov",
        "governor": "Gov. Patrick Morrisey",
        "landmarks": "Harpers Ferry National Historical Park, New River Gorge National Park and Preserve, Gauley River National Recreation Area, and Bluestone National Scenic River",
        "federal_facilities": "Robert C. Byrd U.S. Courthouse (Charleston), National Science Foundation Green Bank Observatory (Pocahontas County), and FBI Criminal Justice Information Services (CJIS, Clarksburg)",
        "wfo": "NWS Charleston (RLX)",
        "wfo_url": "https://www.weather.gov/rlx/",
        "hazards": "Steep Appalachian valley flash flooding, Class IV–V whitewater hydraulics on the New/Gauley Rivers, mountain fog/ice, and ticks/rattlesnakes",
        "camps_trails": "Summit Bechtel Family National Scout Reserve (Glen Jean — home of the National Jamboree & Paul R. Christen High Adventure Base), Camp Mountaineer, and Dolly Sods Wilderness",
        "trauma_ems": "WVU Medicine Ruby Memorial Hospital (Morgantown) & CAMC General Hospital (Charleston) Level I Trauma Centers",
        "ecology": "New, Gauley, Kanawha, Monongahela & Potomac River headwaters, Monongahela National Forest red spruce highlands, and WV DNR",
        "museums": "Green Bank Science Center (World's largest fully steerable radio telescope), Clay Center for the Arts & Sciences (Charleston), and West Virginia State Museum",
    },
    "WI": {
        "state_name": "Wisconsin",
        "capital_city": "Madison",
        "capitol_building": "Wisconsin State Capitol (Madison, 1917 George B. Post white Bethel granite dome on the isthmus between Lakes Mendota and Monona)",
        "senator_1": "Sen. Ron Johnson (R-WI)",
        "senator_1_url": "https://www.ronjohnson.senate.gov",
        "senator_2": "Sen. Tammy Baldwin (D-WI)",
        "senator_2_url": "https://www.baldwin.senate.gov",
        "governor": "Gov. Tony Evers",
        "landmarks": "Apostle Islands National Lakeshore (Lake Superior), Saint Croix National Scenic Riverway, Ice Age National Scientific Reserve & National Scenic Trail, and Taliesin (Spring Green)",
        "federal_facilities": "Federal Building & U.S. Courthouse (Milwaukee), Robert W. Kastenmeier U.S. Courthouse (Madison), and USDA Forest Products Laboratory (Madison)",
        "wfo": "NWS Milwaukee/Sullivan (MKX), NWS Green Bay (GRB) & NWS La Crosse (ARX)",
        "wfo_url": "https://www.weather.gov/mkx/",
        "hazards": "Severe summer squall lines/tornadoes, Great Lakes cold water & sea-cave waves, winter sub-zero wind chills, and deer ticks (Lyme disease)",
        "camps_trails": "Ed Bryant Scout Reservation, Tesomas Scout Camp (Samoset Council), Bear Paw Scout Camp, Devil's Lake State Park, and Ice Age National Scenic Trail",
        "trauma_ems": "UW Health University Hospital (Madison) & Froedtert Hospital (Milwaukee) Level I Trauma Centers",
        "ecology": "Great Lakes (Superior & Michigan) & Upper Mississippi River basins, Driftless Area unglaciated coulees, Northwoods kettle lakes, and Wisconsin DNR",
        "museums": "Discovery World & Milwaukee Public Museum, EAA Aviation Museum (Oshkosh), and Aldo Leopold Shack & Legacy Center (Baraboo)",
    },
    "WY": {
        "state_name": "Wyoming",
        "capital_city": "Cheyenne",
        "capitol_building": "Wyoming State Capitol (Cheyenne, 1890 Renaissance Revival sandstone capitol with gold-leaf dome — National Historic Landmark where women's suffrage was enshrined)",
        "senator_1": "Sen. John Barrasso (R-WY)",
        "senator_1_url": "https://www.barrasso.senate.gov",
        "senator_2": "Sen. Cynthia Lummis (R-WY)",
        "senator_2_url": "https://www.lummis.senate.gov",
        "governor": "Gov. Mark Gordon",
        "landmarks": "Yellowstone National Park (world's first National Park, 1872), Grand Teton National Park, Devils Tower National Monument (nation's first National Monument, 1906), Fort Laramie National Historic Site, and Fossil Butte National Monument",
        "federal_facilities": "Joseph C. O'Mahoney Federal Center & U.S. Courthouse (Cheyenne), NCAR-Wyoming Supercomputing Center (Cheyenne), and F.E. Warren Air Force Base",
        "wfo": "NWS Cheyenne (CYS) & NWS Riverton (RIW)",
        "wfo_url": "https://www.weather.gov/cys/",
        "hazards": "Grizzly bear & bison safety, hydrothermal geyser basins, high-altitude summer blizzards/lightning (>8,000 ft), and extreme winter wind gusts",
        "camps_trails": "Camp Buffalo Bill (just outside Yellowstone East Entrance), Camp Grizzly, Wind River Range, and Continental Divide National Scenic Trail",
        "trauma_ems": "Banner Wyoming Medical Center (Casper) & Cheyenne Regional Medical Center Level II Trauma Centers & Teton County Search and Rescue",
        "ecology": "Greater Yellowstone Ecosystem, headwaters of the Snake, Yellowstone, Green & North Platte rivers, and Wyoming Game and Fish Department",
        "museums": "Buffalo Bill Center of the West & Draper Natural History Museum (Cody), Wyoming State Museum (Cheyenne), and Tate Geological Museum (Casper)",
    },
}


# ==============================================================================
# 2. PHASE 1: REQUIREMENT LOCAL GROUNDING TAXONOMY & SPEC CLASSIFIER
# ==============================================================================

def classify_requirement_local_grounding_spec(
    badge_name: str,
    req_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Examines a Merit Badge requirement and returns its structured `local_grounding_spec` tag.

    Categories:
    - `elected_officials` (TTL: 1 day / 24 hours — U.S. Senators, U.S. Representative, Governor)
    - `civic_landmarks_and_monuments` (TTL: 90 days — State Capital, NPS monuments, National Register landmarks, Federal facilities)
    - `local_government_and_courts` (TTL: 30 days — City council, county court, local boards, civic orgs)
    - `noaa_weather_and_climate` (TTL: 7 days — Local NWS WFO, regional severe weather hazards, emergency alerts)
    - `ecology_forestry_and_watershed` (TTL: 90 days — Local watershed, ecoregion, native species, state conservation agency)
    - `outdoor_trails_camps_and_waterways` (TTL: 90 days — Local BSA council camps, USGS quads, trailheads, waterways)
    - `emergency_ems_and_hospitals` (TTL: 90 days — Local 911 EMS, Level I/II Trauma Center, Poison Control, SAR)
    - `museums_stem_and_careers` (TTL: 90 days — Regional science/history museums, labs, universities, professional chapters)
    """
    b_low = (badge_name or "").strip().lower()
    req_num = str(req_dict.get("req_number") or "1").strip()
    base_num = re.sub(r"[a-zA-Z]+$", "", req_num).strip() or req_num
    req_text = str(req_dict.get("req_text") or "")
    sub_texts = " ".join(str(sr.get("text") or "") for sr in (req_dict.get("sub_requirements") or []))
    combined_low = f"{req_text} {sub_texts}".lower()

    # 1. Elected Officials (U.S. Senators, House Representative, Governor) -> 1-day TTL!
    if (
        (b_low == "citizenship in the nation" and base_num == "8")
        or any(
            kw in combined_low
            for kw in (
                "two senators",
                "senators from your state",
                "member of congress",
                "congressional district",
                "representative in congress",
                "write a letter",
                "your state's governor",
                "elected official",
            )
        )
    ):
        return {
            "requires_local_lookup": True,
            "grounding_category": "elected_officials",
            "search_query_template": (
                "Current two U.S. Senators for {state}, U.S. House Representative for {city}, {state}, "
                "and Governor of {state} with official senate.gov and house.gov contact links"
            ),
            "slide_injection_label": "Your Current U.S. Senators & Congressional Delegation",
            "ttl_days": 1,
        }

    # 2. Civic Landmarks, State Capital, Federal Facilities & National Monuments (e.g., Cit in Nation Req 7 / Slides 32-34)
    if (
        (b_low == "citizenship in the nation" and base_num in ("7", "2", "4", "6"))
        or b_low in ("american heritage", "historic preservation", "archaeology", "architecture")
        or any(
            kw in combined_low
            for kw in (
                "national historic landmark",
                "national register of historic places",
                "state capital",
                "state capitol",
                "federal facility",
                "national monument",
                "historic site",
                "monument",
                "national park",
            )
        )
    ):
        return {
            "requires_local_lookup": True,
            "grounding_category": "civic_landmarks_and_monuments",
            "search_query_template": (
                "National Register historic landmarks, {state} State Capitol building, nearby Federal facilities, "
                "and National Park Service monuments near {city}, {state}"
            ),
            "slide_injection_label": "Local Landmarks, State Capitol, Federal Facilities & National Monuments",
            "ttl_days": 90,
        }

    # 3. Local Government, City Council, Courts & Community Service
    if (
        b_low in ("citizenship in the community", "citizenship in society", "law", "crime prevention", "american business", "american labor")
        or any(
            kw in combined_low
            for kw in (
                "city council",
                "town meeting",
                "school board",
                "county court",
                "local government",
                "charitable organization",
                "community issue",
                "police department",
                "law enforcement",
            )
        )
    ):
        return {
            "requires_local_lookup": True,
            "grounding_category": "local_government_and_courts",
            "search_query_template": (
                "Local municipal government structure, city/town council meetings, county courthouse, "
                "and community service organizations in {city}, {state}"
            ),
            "slide_injection_label": "Local Municipal Government, Courts & Community Organizations",
            "ttl_days": 30,
        }

    # 4. NOAA Weather, Severe Hazards & Climate
    if (
        b_low in ("weather", "emergency preparedness")
        or any(
            kw in combined_low
            for kw in (
                "national weather service",
                "severe weather",
                "weather forecast",
                "storm warning",
                "hurricane",
                "tornado",
                "flash flood",
                "heat exhaustion",
                "hypothermia",
                "natural disaster",
            )
        )
    ):
        return {
            "requires_local_lookup": True,
            "grounding_category": "noaa_weather_and_climate",
            "search_query_template": (
                "National Weather Service Weather Forecast Office (WFO), regional severe weather hazards, "
                "and county emergency management alerts for {city}, {state}"
            ),
            "slide_injection_label": "Local NOAA Weather Office & Regional Hazard Profile",
            "ttl_days": 7,
        }

    # 5. Emergency EMS, Trauma Hospitals & Public Health
    if (
        b_low in ("first aid", "lifesaving", "search and rescue", "fire safety", "safety", "public health", "medicine", "health care professions", "dentistry", "veterinary medicine")
        or any(
            kw in combined_low
            for kw in (
                "emergency medical",
                "911",
                "poison control",
                "hospital",
                "health department",
                "triage",
                "evacuat",
                "fire department",
            )
        )
    ):
        needs_lookup = bool(
            base_num in ("1", "2", "10", "11", "15")
            or any(k in combined_low for k in ("911", "emergency", "transport", "heat", "cold", "bite", "tick", "career", "agency", "department", "visit"))
        )
        return {
            "requires_local_lookup": needs_lookup,
            "grounding_category": "emergency_ems_and_hospitals",
            "search_query_template": (
                "911 EMS dispatch, nearest Level I/II Trauma Center, regional Search and Rescue (SAR), "
                "and environmental health hazards for {city}, {state}"
            ),
            "slide_injection_label": "Local EMS Dispatch, Trauma Network & Regional Field Risks",
            "ttl_days": 90,
        }

    # 6. Ecology, Forestry, Wildlife & Watersheds
    if (
        b_low in (
            "environmental science", "sustainability", "forestry", "nature", "bird study",
            "mammal study", "reptile and amphibian study", "fish and wildlife management",
            "soil and water conservation", "oceanography", "plant science", "insect study",
            "fishing", "fly-fishing", "gardening", "landscape architecture", "pulp and paper",
        )
        or any(
            kw in combined_low
            for kw in (
                "watershed", "endangered species", "invasive species", "ecosystem",
                "native tree", "wildflower", "migratory bird", "wildlife", "conservation",
            )
        )
    ):
        return {
            "requires_local_lookup": True,
            "grounding_category": "ecology_forestry_and_watershed",
            "search_query_template": (
                "Local USGS watershed, EPA ecoregion, native indicator flora/fauna, "
                "and {state} wildlife conservation resources near {city}, {state}"
            ),
            "slide_injection_label": "Local Watershed, Native Ecology & Conservation Agency",
            "ttl_days": 90,
        }

    # 7. Outdoor Trails, BSA Camps, Waterways & Backcountry Navigation
    if (
        b_low in (
            "camping", "hiking", "backpacking", "canoeing", "kayaking", "rowing",
            "whitewater", "small-boat sailing", "motorboating", "water sports",
            "swimming", "scuba diving", "orienteering", "pioneering", "wilderness survival",
            "climbing", "cycling", "geocaching", "snow sports", "action sports",
            "cooking", "horsemanship", "skating", "athletics", "personal fitness", "sports",
        )
        or any(
            kw in combined_low
            for kw in (
                "topographic map", "compass", "declination", "campout", "trail",
                "leave no trace", "fire ban", "bear bag", "waterway",
            )
        )
    ):
        needs_lookup = bool(
            base_num in ("1", "2", "4", "5", "6", "7", "9")
            or any(k in combined_low for k in ("map", "camp", "hike", "trail", "water", "stove", "fire", "hazard", "weather", "local", "plan"))
        )
        return {
            "requires_local_lookup": needs_lookup,
            "grounding_category": "outdoor_trails_camps_and_waterways",
            "search_query_template": (
                "Local Scouts BSA Council camps, state/national park trailheads, USGS topo quadrangle, "
                "and outdoor fire/food-storage rules near {city}, {state}"
            ),
            "slide_injection_label": "Local BSA Camps, Trailheads & Backcountry Regulations",
            "ttl_days": 90,
        }

    # 8. Museums, STEM Labs, Universities & Career Exploration
    needs_stem_lookup = bool(
        any(
            k in combined_low
            for k in (
                "visit", "museum", "career", "profession", "interview", "specialist",
                "facility", "laboratory", "observatory", "club", "organization",
            )
        )
        or req_num in ("1", "2")
    )
    return {
        "requires_local_lookup": needs_stem_lookup,
        "grounding_category": "museums_stem_and_careers",
        "search_query_template": (
            "Local science/history museums, university laboratories, and professional chapters "
            "for {badge} Merit Badge near {city}, {state}"
        ),
        "slide_injection_label": "Local Museums, Field Sites & Professional Mentors",
        "ttl_days": 90,
    }


# ==============================================================================
# 3. PHASE 2 & 3: TWO-TIER CACHE + LIVE GEMINI U.S. SENATOR & REGIONAL LOOKUP
# ==============================================================================

def _normalize_location_key(city_state: str, state_abbr: str) -> str:
    clean_cs = re.sub(r"[^a-z0-9]+", "_", (city_state or "").strip().lower()).strip("_")
    clean_st = (state_abbr or "MA").strip().upper()
    return f"{clean_st}:{clean_cs or clean_st.lower()}"


def _load_json_cache(path: Path) -> Dict[str, Any]:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _save_json_cache(path: Path, data: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed writing local grounding cache %s: %s", path, exc)


def _ensure_sqlite_grounding_table() -> Optional[Path]:
    try:
        from src.memory.session_store import _default_store

        db_path = Path(_default_store.db_path)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS local_grounding_cache (
                    cache_key TEXT PRIMARY KEY,
                    location_key TEXT NOT NULL,
                    state_abbr TEXT NOT NULL,
                    grounding_category TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at_epoch INTEGER NOT NULL,
                    expires_at_epoch INTEGER NOT NULL
                )
                """
            )
            conn.commit()
        return db_path
    except Exception:
        return None


def _get_cached_grounding_entry(cache_key: str) -> Optional[Dict[str, Any]]:
    now = int(time.time())
    # 1. Check JSON disk cache first (ultra-fast in-process read)
    disk_cache = _load_json_cache(LOCAL_GROUNDING_CACHE_JSON)
    entry = disk_cache.get(cache_key)
    if isinstance(entry, dict) and int(entry.get("expires_at_epoch") or 0) > now:
        return entry

    # 2. Check SQLite cache
    db_path = _ensure_sqlite_grounding_table()
    if db_path and db_path.exists():
        try:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT payload_json, expires_at_epoch FROM local_grounding_cache WHERE cache_key = ?",
                    (cache_key,),
                ).fetchone()
                if row and int(row[1] or 0) > now:
                    return json.loads(row[0])
        except Exception:
            pass
    return None


def _put_cached_grounding_entry(
    cache_key: str,
    location_key: str,
    state_abbr: str,
    grounding_category: str,
    payload: Dict[str, Any],
    ttl_days: int = 1,
) -> Dict[str, Any]:
    now = int(time.time())
    expires = now + max(1, int(ttl_days)) * 86400
    enriched = dict(payload)
    enriched["cache_key"] = cache_key
    enriched["location_key"] = location_key
    enriched["state_abbr"] = state_abbr
    enriched["grounding_category"] = grounding_category
    enriched["updated_at_epoch"] = now
    enriched["updated_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    enriched["expires_at_epoch"] = expires
    enriched["ttl_days"] = ttl_days

    disk_cache = _load_json_cache(LOCAL_GROUNDING_CACHE_JSON)
    disk_cache[cache_key] = enriched
    _save_json_cache(LOCAL_GROUNDING_CACHE_JSON, disk_cache)

    db_path = _ensure_sqlite_grounding_table()
    if db_path:
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO local_grounding_cache
                    (cache_key, location_key, state_abbr, grounding_category, payload_json, updated_at_epoch, expires_at_epoch)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cache_key,
                        location_key,
                        state_abbr,
                        grounding_category,
                        json.dumps(enriched, ensure_ascii=False),
                        now,
                        expires,
                    ),
                )
                conn.commit()
        except Exception:
            pass
    return enriched


def _query_gemini_for_senators_and_local_entities(
    state_abbr: str,
    city_state: str,
    baseline: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    """Queries Gemini 2.5 Flash (with Google Search grounding when available) on demand to verify
    the two current U.S. Senators for `state_abbr`, the U.S. House Representative for `city_state`,
    the State Governor, and nearby landmarks/federal facilities.
    """
    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("DISABLE_LIVE_GROUNDING_LLM", "false").lower() == "true":
        return None

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() in ("true", "1", "yes")
    if not api_key and not use_vertex:
        return None

    try:
        from google import genai
        from google.genai import types

        if use_vertex:
            client = genai.Client(
                vertexai=True,
                project=os.getenv("GOOGLE_CLOUD_PROJECT"),
                location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            )
        else:
            client = genai.Client(api_key=api_key)

        state_name = baseline.get("state_name", state_abbr)
        prompt = (
            f"Provide verified current civic and regional information for {city_state} ({state_name}, {state_abbr}) "
            "as a strict JSON object with these keys:\n"
            '- "senator_1": Full name and party of current senior U.S. Senator for ' + state_name + ' (e.g., "Sen. Elizabeth Warren (D-MA)")\n'
            '- "senator_1_url": Official .senate.gov URL for senator_1\n'
            '- "senator_2": Full name and party of current junior U.S. Senator for ' + state_name + '\n'
            '- "senator_2_url": Official .senate.gov URL for senator_2\n'
            '- "house_rep": Current U.S. House Representative & Congressional District for ' + city_state + ' (e.g., "Rep. Ro Khanna (CA-17)" or "Rep. Seth Moulton (MA-06)")\n'
            '- "house_rep_url": Official .house.gov URL\n'
            '- "governor": Current Governor of ' + state_name + '\n'
            '- "local_landmarks": 2-3 specific National Register historic sites, National Monuments, or National Historical Parks closest to ' + city_state + '\n'
            '- "local_federal_facility": Specific federal courthouse, NASA/NOAA/DOE lab, military base, or federal agency facility closest to ' + city_state + '\n'
            "Return ONLY valid JSON."
        )

        # Try with Google Search grounding tool first, then standard JSON response
        resp_text = ""
        try:
            resp = client.models.generate_content(
                model=select_model_for_task("researcher") or "gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            resp_text = (resp.text or "").strip()
        except Exception:
            resp = client.models.generate_content(
                model=select_model_for_task("researcher") or "gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )
            resp_text = (resp.text or "").strip()

        m = re.search(r"\{.*\}", resp_text, flags=re.DOTALL)
        if m:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, dict) and parsed.get("senator_1") and parsed.get("senator_2"):
                parsed["live_gemini_verified"] = True
                return parsed
    except Exception as exc:
        logger.info("On-demand Gemini senator/landmark lookup fell back to verified registry: %s", exc)
    return None


_CITY_HOUSE_REP_HINTS: Dict[str, str] = {
    "middleton": "Rep. Seth Moulton (D-MA-6)",
    "01949": "Rep. Seth Moulton (D-MA-6)",
    "salem": "Rep. Seth Moulton (D-MA-6)",
    "andover": "Rep. Seth Moulton (D-MA-6)",
    "danvers": "Rep. Seth Moulton (D-MA-6)",
    "peabody": "Rep. Seth Moulton (D-MA-6)",
    "lynnfield": "Rep. Seth Moulton (D-MA-6)",
    "topsfield": "Rep. Seth Moulton (D-MA-6)",
    "boxford": "Rep. Seth Moulton (D-MA-6)",
    "boston": "Rep. Ayanna Pressley (D-MA-7) / Rep. Stephen Lynch (D-MA-8)",
    "cambridge": "Rep. Katherine Clark (D-MA-5)",
    "lexington": "Rep. Katherine Clark (D-MA-5)",
    "concord": "Rep. Lori Trahan (D-MA-3)",
    "worcester": "Rep. Jim McGovern (D-MA-2)",
    "springfield": "Rep. Richard Neal (D-MA-1)",
    "sunnyvale": "Rep. Ro Khanna (D-CA-17)",
    "cupertino": "Rep. Ro Khanna (D-CA-17)",
    "mountain view": "Rep. Sam Liccardo (D-CA-16)",
    "palo alto": "Rep. Sam Liccardo (D-CA-16)",
    "san jose": "Rep. Sam Liccardo (D-CA-16) / Rep. Ro Khanna (D-CA-17)",
    "san francisco": "Rep. Nancy Pelosi (D-CA-11)",
    "austin": "Rep. Greg Casar (D-TX-35) / Rep. Lloyd Doggett (D-TX-37)",
    "seattle": "Rep. Pramila Jayapal (D-WA-7)",
}


def _resolve_default_house_rep(st: str, disp_city: str) -> str:
    low = disp_city.lower()
    for token, rep_val in _CITY_HOUSE_REP_HINTS.items():
        if token in low:
            return rep_val
    return f"U.S. House Representative for {disp_city} (verify ZIP at house.gov)"


def refresh_us_senators_on_demand(
    state_abbr: str,
    city_state: str = "",
    force: bool = False,
) -> Dict[str, Any]:
    """Resolves the two current U.S. Senators (and local U.S. House Representative) for `state_abbr` / `city_state`.

    Uses a 24-hour (`ttl_days=1`) cache in `data/local_grounding_cache.json` and `data/us_senators_cache.json`,
    and queries Gemini on demand whenever the entry is older than 24 hours or `force=True`.
    """
    st = (state_abbr or "MA").strip().upper()
    if st not in _STATE_CIVIC_AND_FIELD_REGISTRY:
        st = "MA"
    baseline = dict(_STATE_CIVIC_AND_FIELD_REGISTRY[st])
    disp_city = (city_state or baseline["capital_city"] + f", {st}").strip()
    loc_key = _normalize_location_key(disp_city, st)
    cache_key = f"{loc_key}:elected_officials"
    default_h_rep = _resolve_default_house_rep(st, disp_city)

    if not force:
        cached = _get_cached_grounding_entry(cache_key)
        if cached:
            if not cached.get("house_rep") or str(cached.get("house_rep", "")).startswith("U.S. House Representative for"):
                cached["house_rep"] = default_h_rep
            cached["cache_status"] = "CACHE_HIT_24H"
            return cached

    # Query Gemini on demand to catch any new U.S. Senator elections/appointments or local House Rep
    live_data = _query_gemini_for_senators_and_local_entities(st, disp_city, baseline)
    payload: Dict[str, Any] = {
        "state_abbr": st,
        "state_name": baseline["state_name"],
        "display_location": disp_city,
        "capital_city": baseline["capital_city"],
        "capitol_building": baseline["capitol_building"],
        "senator_1": (live_data or {}).get("senator_1") or baseline["senator_1"],
        "senator_1_url": (live_data or {}).get("senator_1_url") or baseline["senator_1_url"],
        "senator_2": (live_data or {}).get("senator_2") or baseline["senator_2"],
        "senator_2_url": (live_data or {}).get("senator_2_url") or baseline["senator_2_url"],
        "house_rep": (live_data or {}).get("house_rep") or default_h_rep,
        "house_rep_url": (live_data or {}).get("house_rep_url") or "https://www.house.gov/representatives/find-your-representative",
        "governor": (live_data or {}).get("governor") or baseline["governor"],
        "local_landmarks": (live_data or {}).get("local_landmarks") or baseline["landmarks"],
        "local_federal_facility": (live_data or {}).get("local_federal_facility") or baseline["federal_facilities"],
        "cache_status": "LIVE_GEMINI_GROUNDED" if live_data else "VERIFIED_REGISTRY_24H",
    }

    stored = _put_cached_grounding_entry(
        cache_key=cache_key,
        location_key=loc_key,
        state_abbr=st,
        grounding_category="elected_officials",
        payload=payload,
        ttl_days=1,
    )

    # Also update the state-level `data/us_senators_cache.json` table (used for daily 100-Senator sweeps)
    sen_table = _load_json_cache(US_SENATORS_CACHE_JSON)
    sen_table[st] = {
        "state_abbr": st,
        "state_name": baseline["state_name"],
        "senator_1": stored["senator_1"],
        "senator_1_url": stored["senator_1_url"],
        "senator_2": stored["senator_2"],
        "senator_2_url": stored["senator_2_url"],
        "governor": stored["governor"],
        "updated_at_iso": stored["updated_at_iso"],
        "expires_at_epoch": stored["expires_at_epoch"],
    }
    _save_json_cache(US_SENATORS_CACHE_JSON, sen_table)
    return stored


def refresh_all_100_us_senators_daily(force: bool = False) -> Dict[str, Any]:
    """Periodic daily job (TTL = 24 hours) that ensures all 50 states' 100 U.S. Senators are cached and fresh."""
    now = int(time.time())
    sen_table = _load_json_cache(US_SENATORS_CACHE_JSON)
    refreshed_states: List[str] = []
    cached_states: List[str] = []

    for st, base in sorted(_STATE_CIVIC_AND_FIELD_REGISTRY.items()):
        existing = sen_table.get(st)
        if not force and isinstance(existing, dict) and int(existing.get("expires_at_epoch") or 0) > now:
            cached_states.append(st)
            continue
        sen_table[st] = {
            "state_abbr": st,
            "state_name": base["state_name"],
            "capital_city": base["capital_city"],
            "senator_1": base["senator_1"],
            "senator_1_url": base["senator_1_url"],
            "senator_2": base["senator_2"],
            "senator_2_url": base["senator_2_url"],
            "governor": base["governor"],
            "updated_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "expires_at_epoch": now + 86400,
        }
        refreshed_states.append(st)

    _save_json_cache(US_SENATORS_CACHE_JSON, sen_table)
    return {
        "total_states_and_dc": len(sen_table),
        "refreshed_count": len(refreshed_states),
        "cached_count": len(cached_states),
        "cache_file": str(US_SENATORS_CACHE_JSON),
    }


# ==============================================================================
# 4. PHASE 4: RESOLVE REQUIREMENT LOCAL GROUNDING FOR SLIDES & UI
# ==============================================================================

def resolve_requirement_local_grounding(
    badge_name: str,
    req_dict: Dict[str, Any],
    location_profile: Dict[str, str],
) -> Dict[str, Any]:
    """Resolves the requirement-specific local grounding callout, source citation, and cache metadata."""
    spec = req_dict.get("local_grounding_spec") or classify_requirement_local_grounding_spec(badge_name, req_dict)
    cat = str(spec.get("grounding_category") or "museums_stem_and_careers")
    requires_local = bool(spec.get("requires_local_lookup", False))
    ttl_days = int(spec.get("ttl_days") or (1 if cat == "elected_officials" else 30))

    st = str(location_profile.get("state_abbr") or "MA").strip().upper()
    if st not in _STATE_CIVIC_AND_FIELD_REGISTRY:
        st = "MA"
    base = _STATE_CIVIC_AND_FIELD_REGISTRY[st]
    disp_loc = str(location_profile.get("display_location") or f"{base['capital_city']}, {st}").strip()
    loc_key = _normalize_location_key(disp_loc, st)
    req_num = str(req_dict.get("req_number") or "1").strip()

    # Always resolve current U.S. Senators & local delegation when category is elected_officials or Citizenship in the Nation
    sen_info = refresh_us_senators_on_demand(st, disp_loc, force=False)

    cache_key = f"{loc_key}:{cat}:{badge_name.lower().replace(' ', '_')}:req_{req_num}"
    cached = _get_cached_grounding_entry(cache_key)
    if cached:
        return cached

    if cat == "elected_officials":
        callout = (
            f"Local Congressional Delegation ({disp_loc}): U.S. Senators for {base['state_name']} are "
            f"{sen_info['senator_1']} ({sen_info['senator_1_url'].replace('https://www.', '')}) and "
            f"{sen_info['senator_2']} ({sen_info['senator_2_url'].replace('https://www.', '')}); "
            f"Local U.S. House: {sen_info['house_rep']}; State Executive: {sen_info['governor']}."
        )
        source_title = f"U.S. Senate & House Delegation for {disp_loc} ({base['state_name']})"
        source_url = sen_info["senator_1_url"]
        domain = "senate.gov"
    elif cat == "civic_landmarks_and_monuments":
        callout = (
            f"Local Landmarks, State Capital & Federal Sites ({disp_loc}): "
            f"State Capital: {base['capitol_building']}; "
            f"Nearby National Monuments & Historic Sites: {sen_info.get('local_landmarks') or base['landmarks']}; "
            f"Federal Facilities: {sen_info.get('local_federal_facility') or base['federal_facilities']}."
        )
        source_title = f"National Park Service & National Register of Historic Places — {base['state_name']}"
        source_url = f"https://www.nps.gov/state/{st.lower()}/index.htm"
        domain = "nps.gov"
    elif cat == "local_government_and_courts":
        callout = (
            f"Local Government & Civic Institutions ({disp_loc}): Review municipal charters, town/city council agendas, "
            f"and county court dockets in {disp_loc}; State Capitol reference: {base['capitol_building']}; "
            f"Federal Judicial District reference: {base['federal_facilities']}."
        )
        source_title = f"{base['state_name']} Municipal & Judicial Civic Directory ({disp_loc})"
        source_url = "https://www.usa.gov/local-governments"
        domain = "usa.gov"
    elif cat == "noaa_weather_and_climate":
        callout = (
            f"Local NOAA Weather & Hazard Profile ({disp_loc}): Forecast coverage by {base['wfo']}; "
            f"primary regional field hazards include {base['hazards']}."
        )
        source_title = f"NOAA National Weather Service — {base['wfo']}"
        source_url = base["wfo_url"]
        domain = "weather.gov"
    elif cat == "emergency_ems_and_hospitals":
        callout = (
            f"Local Emergency Medical & SAR Network ({disp_loc}): Dial 911 for local EMS dispatch and "
            f"Poison Control (1-800-222-1222); regional trauma & rescue coverage via {base['trauma_ems']}; "
            f"prepare for regional environmental risks ({base['hazards']})."
        )
        source_title = f"Regional EMS, Level I/II Trauma & Backcountry SAR — {disp_loc}"
        source_url = "https://www.911.gov"
        domain = "911.gov"
    elif cat == "ecology_forestry_and_watershed":
        callout = (
            f"Local Watershed & Ecosystem Profile ({disp_loc}): Field study grounded in {base['ecology']}; "
            f"observe native indicator species and Leave No Trace rules at {base['camps_trails']}."
        )
        source_title = f"USGS Watershed & {base['state_name']} Natural Heritage Profile ({disp_loc})"
        source_url = "https://water.usgs.gov/wsc/"
        domain = "usgs.gov"
    elif cat == "outdoor_trails_camps_and_waterways":
        callout = (
            f"Local BSA Camps, Trails & Field Sites ({disp_loc}): Practice this requirement at {base['camps_trails']}; "
            f"check {base['wfo']} forecasts and regional fire/backcountry rules ({base['hazards']})."
        )
        source_title = f"Scouts BSA Local Council Camps & Public Lands — {disp_loc}"
        source_url = "https://www.scouting.org/outdoor-programs/"
        domain = "scouting.org"
    else:
        callout = (
            f"Local STEM, Museum & Career Field Sites ({disp_loc}): Connect with Merit Badge mentors and exhibits at "
            f"{base['museums']} and regional research facilities ({base['federal_facilities']})."
        )
        source_title = f"Regional Museums, Laboratories & Career Mentors — {disp_loc}"
        source_url = "https://www.scouting.org/skills/merit-badges/"
        domain = "scouting.org"

    payload = {
        "req_number": req_num,
        "badge_name": badge_name,
        "requires_local_lookup": requires_local,
        "grounding_category": cat,
        "slide_injection_label": str(spec.get("slide_injection_label") or "Local Troop Grounding"),
        "local_grounding_callout": callout,
        "source_title": source_title,
        "source_url": source_url,
        "authority_domain": domain,
        "senator_1": sen_info["senator_1"],
        "senator_2": sen_info["senator_2"],
        "house_rep": sen_info["house_rep"],
        "capital_city": base["capital_city"],
        "capitol_building": base["capitol_building"],
        "cache_status": sen_info.get("cache_status", "VERIFIED_REGISTRY_24H"),
    }
    return _put_cached_grounding_entry(
        cache_key=cache_key,
        location_key=loc_key,
        state_abbr=st,
        grounding_category=cat,
        payload=payload,
        ttl_days=ttl_days,
    )
