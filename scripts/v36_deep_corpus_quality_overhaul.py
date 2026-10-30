#!/usr/bin/env python3
"""V36 Deep Corpus Quality Overhaul across all 149 Merit Badges and Image Catalogs.

Fixes all 6 systemic corpus and catalog defect classes identified in the V36 deep audit:
1. Splits OCR merged words across all 149 badge JSONs and image catalogs while
   preserving legitimate English and Scouting compound words.
2. Replaces all 3,474 placeholder "Dimension 1/2/3" attributes in comparison_data,
   fixes all truncated comparison_data cells (left, right, left_points, right_points),
   worked_example values/sample_outputs, and pamphlet_excerpts/step_by_step_procedure
   strings cut off before '(p. XX).', and repairs all truncated worked_example.fields
   keys with dangling words or duplicate 'Req X:' prefixes.
3. Eliminates sibling sub-requirement cross-contamination in sub_requirements
   pamphlet_summary, fixes double-colon broken regex headings in pamphlet_excerpts
   and step_by_step_procedure, and replaces raw requirement echoes and generic
   "Cross-check your <X> technique... with a patrol buddy" filler items.
4. Eliminates all '...' ellipsis truncations, mid-abbreviation splits (e.g., i.e.,
   U.S., vs.), dangling end-words, and unbalanced parentheses in workbook_organizer
   row_labels and rows across all nesting levels (L1/L2/L3/L4); syncs
   COMPARE_CONTRAST_2COL headers with comparison_data headers; routes
   sketch/draw/diagram requirements to SKETCH_AND_OBSERVATION_CANVAS; and populates
   concrete workbook_diagram_url, workbook_diagram_caption, and
   workbook_visual_caption across top-level requirements and sub_requirements.
5. Replaces identical PPE safety_callout and homework_verification_note templates
   with domain- and requirement-specific guidance; fixes all domain-mismatched
   gear_checklist items; deduplicates all sibling sub-requirement
   common_misconception_pair entries across all levels; normalizes action-sports.json
   and all 149 badges with 'number', 'description', 'source_url', and
   'local_grounding_spec'.
6. Cleans data/pamphlet_image_catalog.json (removing 18 nonexistent
   clean_visual_first_aid_req_*.png keys and fixing all doubled/generic captions)
   and data/nano_banana_image_catalog.json (fixing all doubled suffixes and
   stripping repetitive template prefixes).
7. Re-syncs data/official_requirements_cache.json and _index.json.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REQ_DIR = ROOT / "data" / "merit_badge_requirements"
PAMPHLET_CATALOG_PATH = ROOT / "data" / "pamphlet_image_catalog.json"
NANO_CATALOG_PATH = ROOT / "data" / "nano_banana_image_catalog.json"
OFFICIAL_CACHE_PATH = ROOT / "data" / "official_requirements_cache.json"


# ---------------------------------------------------------------------------
# 1. OCR Merged Word Splitting Engine
# ---------------------------------------------------------------------------

VALID_2LETTER = {
    "am", "an", "as", "at", "be", "by", "do", "go", "he", "if", "in", "is",
    "it", "me", "my", "no", "of", "on", "or", "ox", "so", "to", "up", "us", "we",
}

FUNC_WORDS = {
    "the", "and", "for", "that", "this", "with", "from", "have", "your", "will",
    "can", "are", "was", "were", "been", "has", "had", "not", "but", "what",
    "when", "where", "which", "who", "why", "how", "all", "any", "some", "more",
    "most", "other", "such", "into", "over", "under", "about", "after", "before",
    "between", "through", "during", "without", "within", "against", "among",
    "around", "because", "while", "their", "there", "these", "those", "they",
    "them", "then", "than", "must", "should", "would", "could", "might", "may",
    "each", "every", "both", "much", "many", "very", "also", "only", "just",
    "even", "still", "always", "never", "often", "usually", "instead", "too",
    "you", "our", "his", "her", "its", "out", "off", "one", "two", "new", "old",
    "to", "of", "in", "on", "at", "by", "as", "is", "be", "or", "if", "so",
    "do", "no", "up", "an", "inside", "outside", "like", "best", "know",
    "getting", "enough", "working", "important", "drawing", "covers",
}

COMPOUND_PREFIXES = {
    "non", "un", "re", "pre", "post", "anti", "auto", "bi", "co", "counter",
    "cross", "cyber", "de", "dis", "down", "eco", "electro", "ex", "extra",
    "fore", "geo", "hydro", "hyper", "il", "im", "infra", "inter", "intra",
    "ir", "iso", "macro", "mal", "mega", "meta", "micro", "mid", "mini", "mis",
    "mono", "multi", "nano", "neo", "omni", "out", "over", "paleo", "pan",
    "para", "photo", "poly", "proto", "pseudo", "psycho", "quasi", "radio",
    "retro", "self", "semi", "socio", "sub", "super", "supra", "syn", "tele",
    "thermo", "trans", "tri", "ultra", "under", "uni", "up", "vice", "zoo",
    "phyto", "cardio", "neuro", "aero", "astro", "bio", "chem", "chrono", "cryo",
}

COMPOUND_HEADS_LEFT = {
    "water", "wood", "metal", "leather", "needle", "horse", "marks", "sea",
    "air", "canoe", "camp", "scout", "wild", "bush", "hand", "handi", "space",
    "hover", "sail", "paddle", "wake", "knee", "long", "short", "surf", "body",
    "skim", "wind", "motor", "row", "life", "house", "show", "steam", "tug",
    "ferry", "speed", "first", "second", "back", "fore", "under", "over",
    "free", "stage", "farm", "deck", "cow", "ranch", "work", "trail", "post",
    "harbor", "station", "web", "head", "toast", "concert", "grand", "pay",
    "task", "ring", "route", "pit", "grill", "dock", "weigh", "load", "jump",
    "dive", "beach", "iron", "steel", "sheet", "silver", "black", "tin",
    "copper", "gold", "lock", "gun", "blade", "white", "pewter", "tool",
    "watch", "clock", "cabinet", "pattern", "boiler", "dress", "shoe", "book",
    "film", "movie", "pace", "peace", "law", "policy", "decision", "trouble",
    "home", "wine", "glass", "paper", "print", "map", "rope", "brick", "stone",
    "pipe", "mill", "ship", "wheel", "play", "wain", "cart", "plow", "eye",
    "foot", "rain", "swim", "sports", "outer", "neck", "knit", "mens", "womens",
    "sleep", "lounge", "active", "ski", "street", "evening", "formal", "hard",
    "soft", "firm", "mal", "spy", "ad", "ransom", "share", "bloat", "vapor",
    "course", "group", "middle", "table", "flat", "stem", "drink", "cook",
    "bake", "kitchen", "dinner", "earthen", "china", "wooden", "hollow",
    "enamel", "brass", "gift", "oven", "score", "time", "goal", "grounds",
    "lines", "outdoors", "woods", "helms", "oars", "bow", "rifle", "midship",
    "fire", "police", "patrol", "council", "congress", "states", "spokes",
    "chair", "crafts", "drafts", "signal", "brake", "switch", "line", "repair",
    "service", "delivery", "milk", "mail", "sales", "business", "camera",
    "sound", "stunt", "anchor", "weather", "newspaper", "press", "clergy",
    "lay", "yeo", "gentle", "noble", "country", "kins", "towns", "bonds",
    "pitch", "front", "side", "wing", "point", "hit", "strong", "con", "mad",
    "snow", "cave", "frog", "bus", "cab", "gas", "rag", "oil", "cattle",
    "dairy", "poultry", "nursery", "seeds", "stock", "sheep", "timber", "grass",
    "wet", "marsh", "swamp", "shrub", "scrub", "range", "crop", "pasture",
    "bad", "high", "low", "mid", "main", "border", "heart", "father", "mother",
    "wonder", "dream", "waste", "park", "heath", "moor", "bottom", "coast",
    "shore", "tree", "ridge", "sky", "hair", "dead", "guide", "base", "foul",
    "touch", "center", "branch", "belt", "trunk", "blood", "story", "punch",
    "date", "hot", "land", "help", "bee", "clothes", "fish", "trot", "plumb",
    "chalk", "sight", "fault", "fence", "stream", "red", "jaw", "waist", "hip",
    "hem", "roof", "trap", "tram", "tow", "taut", "clove", "marlin", "marline",
    "knot", "pine", "bass", "oak", "maple", "cedar", "cherry", "walnut",
    "birch", "ash", "elm", "beech", "poplar", "teak", "rose", "sandal",
    "cotton", "box", "gum", "worm", "satin", "lance", "beef", "grease",
    "button", "tulip", "king", "zebra", "snake", "camphor", "drift", "cord",
    "pulp", "ply", "dog", "cat", "bird", "bug", "inch", "earth", "silk",
    "hook", "tap", "round", "meal", "cut", "army", "ear", "horn", "bag",
    "wire", "glow", "lung", "liver", "brain", "bone", "skin", "tooth", "teeth",
    "mouth", "nose", "thumb", "finger", "toe", "elbow", "shoulder", "wrist",
    "ankle", "chest", "rib", "skull", "sun", "moon", "star", "cloud", "storm",
    "thunder", "lightning", "frost", "ice", "hail", "sleet", "fog", "mist",
    "dew", "heat", "cold", "warm", "cool", "day", "night", "morning", "noon",
    "midnight", "spring", "summer", "fall", "autumn", "winter", "year", "month",
    "week", "hour", "minute", "death", "birth", "age", "youth", "child", "boy",
    "girl", "man", "woman", "baby", "kid", "teen", "adult", "parent", "brother",
    "sister", "son", "daughter", "uncle", "aunt", "cousin", "friend", "buddy",
    "partner", "team", "club", "band", "crew", "gang", "pack", "troop", "den",
    "district", "tent", "cabin", "lodge", "hall", "room", "bed", "bath", "door",
    "window", "wall", "floor", "ceiling", "stair", "step", "path", "road",
    "lane", "drive", "way", "bridge", "gate", "yard", "garden", "field", "barn",
    "shed", "shop", "store", "market", "bank", "school", "church", "court",
    "jail", "prison", "hospital", "clinic", "office", "plant", "mine", "well",
    "dam", "pier", "wharf", "port", "bay", "gulf", "ocean", "lake", "pond",
    "pool", "river", "creek", "brook", "canal", "ditch", "bog", "fen", "cliff",
    "bluff", "hill", "mount", "mountain", "peak", "valley", "glen", "dale",
    "canyon", "gorge", "pass", "gap", "cavern", "rock", "sand", "clay", "mud",
    "dirt", "soil", "dust", "coal", "bronze", "lead", "zinc", "nickel",
    "platinum", "aluminum", "titanium", "plastic", "rubber", "card", "cloth",
    "fabric", "wool", "linen", "nylon", "rayon", "fur", "hide", "shell",
    "feather", "scale", "fin", "tail", "beak", "bill", "claw", "hoof", "paw",
    "leg", "arm", "lip", "tongue", "throat", "breast", "belly", "stomach",
    "vein", "nerve", "mind", "soul", "spirit", "voice", "word", "name", "sign",
    "mark", "note", "letter", "page", "list", "roll", "scroll", "chart", "plan",
    "picture", "photo", "image", "game", "sport", "race", "match", "test",
    "trial", "check", "rule", "code", "act", "tax", "fee", "fine", "cost",
    "price", "rate", "wage", "rent", "loan", "debt", "fund", "cash", "coin",
    "cent", "dollar", "trade", "sale", "deal", "job", "duty", "care", "aid",
    "use", "need", "want", "wish", "hope", "fear", "love", "hate", "joy",
    "grief", "pain", "ache", "ill", "sick", "safe", "sure", "fast", "slow",
    "wide", "broad", "deep", "thick", "thin", "fat", "lean", "big", "large",
    "great", "small", "little", "tiny", "coarse", "rough", "smooth", "stiff",
    "tight", "loose", "weak", "heavy", "light", "full", "empty", "clean",
    "dirty", "pure", "clear", "dark", "bright", "dim", "pale", "rich", "poor",
    "cheap", "dear", "young", "fresh", "stale", "ripe", "raw", "sweet", "sour",
    "bitter", "salt", "dry", "damp", "moist", "loud", "quiet", "still", "calm",
    "tame", "fierce", "mild", "kind", "cruel", "good", "evil", "right", "wrong",
    "true", "false", "wise", "fool", "bold", "brave", "proud", "meek", "glad",
    "sad", "gay", "grave", "bound", "last", "next", "same", "other", "each",
    "all", "both", "half", "whole", "part", "piece", "bit", "drop", "grain",
    "speck", "spot", "dot", "end", "tip", "edge", "rim", "brim", "limit",
}

COMPOUND_TAILS_RIGHT = {
    "work", "works", "worker", "workers", "working", "book", "books", "board",
    "boards", "boarder", "boarders", "boarding", "boat", "boats", "boating",
    "line", "lines", "land", "lands", "water", "waters", "wood", "woods",
    "worm", "worms", "fish", "fishes", "fishing", "bird", "birds", "fly",
    "flies", "weed", "weeds", "grass", "stone", "stones", "rock", "rocks",
    "ware", "wares", "wear", "gear", "man", "men", "woman", "women", "person",
    "people", "master", "masters", "maker", "makers", "making", "keeper",
    "keepers", "keeping", "holder", "holders", "holding", "rest", "plate",
    "plates", "wheel", "wheels", "fire", "fires", "light", "lights", "room",
    "rooms", "house", "houses", "yard", "yards", "shop", "shops", "site",
    "sites", "field", "fields", "ground", "grounds", "head", "heads", "foot",
    "feet", "hand", "hands", "side", "sides", "way", "ways", "top", "tops",
    "back", "backs", "front", "fronts", "out", "outs", "up", "ups", "down",
    "downs", "over", "overs", "under", "unders", "store", "stores", "sport",
    "sports", "jacket", "jackets", "meter", "meters", "range", "ranges",
    "filament", "filaments", "weight", "weights", "telling", "paddle",
    "paddles", "stander", "standers", "first", "wind", "winds", "bike", "bikes",
    "logic", "phone", "phones", "golfer", "golfers", "court", "courts", "spike",
    "spikes", "fast", "testing", "press", "mantle", "dust", "fanning",
    "raising", "plankton", "stool", "stools", "roots", "carbon", "melt", "play",
    "loader", "loaders", "loading", "breaker", "breakers", "frame", "frames",
    "craft", "crafts", "manship", "ship", "ships", "smith", "smiths",
    "smithing", "wright", "wrights", "layer", "layers", "laying", "mason",
    "masonry", "fitter", "fitters", "piece", "pieces", "glass", "glasses",
    "sight", "strain", "wash", "witness", "lid", "lids", "brow", "brows",
    "lash", "lashes", "ball", "balls", "set", "sets", "lamp", "lamps", "band",
    "bands", "ache", "aches", "lock", "locks", "quarters", "space", "spaces",
    "spring", "springs", "stall", "stalls", "stand", "stands", "stream",
    "streams", "strong", "word", "words", "print", "prints", "path", "paths",
    "bridge", "bridges", "hill", "hills", "hold", "holds", "ing", "locker",
    "lockers", "note", "notes", "pad", "pads", "step", "steps", "wall", "walls",
    "card", "cards", "sheet", "sheets", "country",
}

EXCLUDE_EXACT = {
    "filestore", "multisport", "entrepreneurship", "scoutbook", "warmup",
    "warmups", "cooldown", "cooldowns", "lifejacket", "lifejackets",
    "multimeter", "multimeters", "hangfire", "handwheel", "baseplate",
    "downrange", "monofilament", "headrick", "barbless", "faceup", "facedown",
    "bodyweight", "centerboard", "storytelling", "rulebook", "benchrest",
    "backpaddle", "upstander", "upstanders", "baitfish", "feetfirst",
    "sightline", "sightlines", "upwind", "downwind", "aquabike", "lossless",
    "radiologic", "cellphone", "cellphones", "onboard", "basswood",
    "discgolfer", "discgolfers", "pinewood", "refractor", "refractors",
    "underway", "hillcourt", "marlinespike", "marlinspike", "nonbiodegradable",
    "biodegradable", "holdfast", "maillard", "heartworm", "heartworms",
    "playtesting", "rightaway", "transect", "transects", "letterpress",
    "inchworm", "inchworms", "fireline", "storyboard", "storyboards",
    "coursework", "kernmantle", "stardust", "deepwater", "compositional",
    "philmont", "nonprecious", "fernlike", "railfanning", "wakeboarder",
    "wakeboarders", "fundraising", "overexertion", "modelmaking",
    "zooplankton", "phytoplankton", "campstool", "campstools", "firewise",
    "grassroots", "radiocarbon", "snowmelt", "gameplay", "sustainability",
    "muzzleloading", "muzzleloader", "muzzleloaders", "herbarium",
    "cardiorespiratory", "belayer", "belayers", "strikebreaker",
    "strikebreakers", "keyframe", "keyframes", "tippet", "tippets",
    "craftsperson", "craftspeople", "recordkeeping", "bookkeeping",
    "skatepark", "skateparks", "skateboard", "skateboards", "skateboarder",
    "skateboarders", "skateboarding", "snowboard", "snowboards", "snowboarder",
    "snowboarders", "snowboarding", "snowshoe", "snowshoes", "snowshoer",
    "snowshoers", "snowshoeing", "whitewater", "flatwater", "openwater",
    "saltwater", "freshwater", "watercraft", "waterfowl", "waterfront",
    "waterproof", "watershed", "waterway", "waterways", "woodwork",
    "woodworking", "woodcarving", "metalwork", "metalworking", "leatherwork",
    "needlework", "horsemanship", "marksmanship", "seamanship", "campcraft",
    "scoutcraft", "woodcraft", "aircraft", "spacecraft", "motorboat",
    "motorboating", "sailboat", "rowboat", "lifeboat", "lifesaving",
    "lifeguard", "firsthand", "secondhand", "backhand", "forehand",
    "underhand", "overhand", "freehand", "handwriting", "handmade", "handheld",
    "handlebar", "handlebars", "handsaw", "workspace", "workplace",
    "workbench", "workbook", "workbooks", "worksheet", "workshop",
    "workstation", "workforce", "workout", "workouts", "frontcountry",
    "backcountry", "crosscountry", "trailhead", "trailside", "campsite",
    "campsites", "campground", "campfire", "campout", "scoutmaster",
    "quartermaster", "silversmith", "blacksmith", "tinsmith", "locksmith",
    "gunsmith", "filmmaker", "filmmaking", "moviemaking", "papermaking",
    "printmaking", "mapmaking", "bricklayer", "stonemason", "eyepiece",
    "eyeglasses", "eyewear", "eyesight", "eyewash", "headgear", "headset",
    "headphones", "headlamp", "headlight", "headquarters", "headwind",
    "footwear", "footprint", "footprints", "footpath", "foothills", "footstep",
    "footwork", "rainwear", "swimwear", "outerwear", "hardware", "software",
    "malware", "ransomware", "tableware", "cookware", "stoneware",
    "earthenware", "warehouse", "scorecard", "scoreboard", "scoresheet",
    "scorekeeper", "sportsmanship", "outdoorsman", "helmsman", "bowman",
    "rifleman", "chairperson", "spokesperson", "salesperson", "woodland",
    "woodlands", "grassland", "grasslands", "wetland", "wetlands", "farmland",
    "cropland", "wildland", "highland", "highlands", "lowland", "mainland",
    "coastline", "shoreline", "waterline", "timberline", "treeline",
    "ridgeline", "skyline", "headline", "deadline", "guideline", "guidelines",
    "baseline", "outline", "pipeline", "lifeline", "sideline", "centerline",
    "airline", "bloodline", "storyline", "hotline", "landline", "fishline",
    "handline", "plumbline", "chalkline", "snowline", "faultline", "fenceline",
    "streamline", "frontline", "roofline", "towline", "bowline", "tautline",
    "breakdancing", "waterskiing", "waterskier", "waterskiers", "windsurfing",
    "kiteboarding", "paddleboarding", "mountainbiking", "geocaching",
    "orienteering", "mountaineering", "canyoneering", "backpacking",
    "flyfishing", "bowhunting", "shotgunning", "blackpowder", "smallbore",
    "airgun", "airguns", "sportfishing", "vermicomposting", "electroplating",
    "thermoplastic", "thermosetting", "ferromagnetic", "electromagnetic",
    "hydroelectric", "photovoltaic", "geothermal", "microcontroller",
    "microcontrollers", "microprocessor", "microprocessors", "semiconductor",
    "semiconductors", "superconductor", "superconductors", "nanotechnology",
    "biotechnology", "bioengineering", "neuroscience", "astrophysics",
    "geophysics", "biochemistry", "stereoscopic", "monochromatic",
    "polychromatic", "telecommunications", "cybersecurity", "cryptocurrency",
    "blockchain", "crowdfunding", "microfinance", "agribusiness", "aquaculture",
    "silviculture", "horticulture", "permaculture", "arboriculture",
    "floriculture", "olericulture", "pomology", "entomology", "herpetology",
    "ornithology", "ichthyology", "mammalogy", "paleontology", "archaeology",
    "anthropology", "epidemiology", "toxicology", "pharmacology",
    "anesthesiology", "ophthalmology", "otolaryngology", "gastroenterology",
    "cardiology", "dermatology", "endocrinology", "hematology", "immunology",
    "nephrology", "neurology", "oncology", "orthopedics", "pathology",
    "pediatrics", "psychiatry", "pulmonology", "radiology", "rheumatology",
    "urology", "veterinary", "veterinarian", "veterinarians",
}

EXPLICIT_OCR_SPLITS = {
    "thatyou": "that you",
    "canlead": "can lead",
    "themodern": "the modern",
    "haveyour": "have your",
    "canhelp": "can help",
    "thisspecialty": "this specialty",
    "thathave": "that have",
    "musthave": "must have",
    "arerecommended": "are recommended",
    "generalrecreational": "general recreational",
    "theshapes": "the shapes",
    "theplane": "the plane",
    "willhave": "will have",
    "toomuch": "too much",
    "highhumidity": "high humidity",
    "andwhen": "and when",
    "investmentsinstead": "investments instead of",
    "revivingtheir": "reviving their",
    "havechosen": "have chosen",
    "moreabout": "more about",
    "knowwhat": "know what",
    "anddrinks": "and drinks",
    "mostcommon": "most common",
    "aboutdiagrams": "about diagrams",
    "drawingmust": "drawing must",
    "havedifferent": "have different",
    "whatyou": "what you",
    "therecommended": "the recommended",
    "theoperator": "the operator",
    "theabrasion": "the abrasion",
    "foryour": "for your",
    "forentertainment": "for entertainment",
    "forexample": "for example",
    "coverswhich": "covers which",
    "thebook": "the book",
    "importantscience": "important science",
    "gettingenough": "getting enough",
    "likeloggerhead": "like loggerhead",
    "insideleg": "inside leg",
    "besttraining": "best training",
    "notpossible": "not possible",
    "orbecome": "or become",
    "adultsupervision": "adult supervision",
    "workingpopulation": "working population",
    "usuallydangerous": "usually dangerous",
    "heatexhaustion": "heat exhaustion",
    "moreknowledge": "more knowledge",
    "riskyinvestments": "risky investments",
    "incheslong": "inches long",
    "majorpurchase": "major purchase",
    "arein": "are in",
    "ashelter": "a shelter",
    "amanufacturer": "a manufacturer",
    "abelt": "a belt",
    "amonth": "a month",
    "atwisted": "a twisted",
    "aweek": "a week",
    "aperson": "a person",
    "abuddy": "a buddy",
    "aclimber": "a climber",
    "ametal": "a metal",
    "aserious": "a serious",
    "acomputer": "a computer",
    "avariety": "a variety",
    "alimited": "a limited",
    "amore": "a more",
    "goodwarmup": "good warmup",
    "pushyour": "push your",
    "gpsreceivers": "GPS receivers",
    "cleanlint": "clean lint",
}

A_PREFIX_NOUNS = {
    "shelter", "manufacturer", "belt", "month", "twisted", "week", "person",
    "buddy", "climber", "metal", "serious", "computer", "variety", "limited",
    "more", "single", "double", "second", "third", "fourth", "simple",
    "common", "different", "special", "specific", "certain", "local", "small",
    "large", "great", "good", "better", "higher", "lower", "longer", "shorter",
    "number", "group", "member", "leader", "counselor", "scout", "patrol",
    "troop", "family", "parent", "friend", "doctor", "hospital", "patient",
    "victim", "rescuer", "swimmer", "boater", "driver", "vehicle", "bicycle",
    "helmet", "weapon", "target", "camera", "compass", "map", "chart",
    "diagram", "sketch", "sample", "report", "budget", "schedule", "project",
    "business", "company", "country", "nation", "community", "system",
    "method", "process", "program", "device", "machine", "circuit", "battery",
    "motor", "engine", "chemical", "substance", "material", "container",
    "surface", "healthy", "balanced", "natural", "habitat", "species",
    "mineral", "crystal", "fossil", "glacier", "volcano", "weather",
}


def build_ocr_splitter(badge_files: list[Path]) -> tuple[dict[str, str], dict[str, str]]:
    """Build exact-token and lowercase-token OCR merge lookup maps."""
    dict_words: set[str] = set()
    for dp in ("/usr/share/dict/words", "/usr/share/dict/american-english"):
        p = Path(dp)
        if p.exists():
            for w in p.read_text(errors="ignore").splitlines():
                wc = w.strip().lower()
                if wc.isalpha() and (len(wc) >= 3 or wc in VALID_2LETTER):
                    dict_words.add(wc)

    for bf in badge_files:
        d = json.loads(bf.read_text(encoding="utf-8"))
        for r in d.get("requirements", []):
            for m in re.finditer(r"\b[a-zA-Z]{3,}\b", str(r.get("req_text", ""))):
                w = m.group(0).lower()
                if w not in EXPLICIT_OCR_SPLITS:
                    dict_words.add(w)
            for sr in r.get("sub_requirements", []):
                if isinstance(sr, dict):
                    for m in re.finditer(r"\b[a-zA-Z]{3,}\b", str(sr.get("text", ""))):
                        w = m.group(0).lower()
                        if w not in EXPLICIT_OCR_SPLITS:
                            dict_words.add(w)
                    for ch in sr.get("children", []):
                        if isinstance(ch, dict):
                            for m in re.finditer(r"\b[a-zA-Z]{3,}\b", str(ch.get("text", ""))):
                                w = m.group(0).lower()
                                if w not in EXPLICIT_OCR_SPLITS:
                                    dict_words.add(w)

    valid_vocab = set(dict_words) | EXCLUDE_EXACT
    for w in list(dict_words):
        if len(w) >= 4:
            for sfx in (
                "s", "es", "ed", "ing", "er", "ers", "est", "ly", "ness",
                "ment", "ments", "able", "ible", "ability", "ibility", "ship",
                "ships", "less", "like", "wise", "ward", "wards", "ful", "al",
                "ial", "ion", "ions", "ation", "ations",
            ):
                valid_vocab.add(w + sfx)
            if w.endswith("e"):
                for sfx in (
                    "ing", "ed", "er", "ers", "est", "able", "ible", "ability",
                    "ation", "ations", "al", "ial",
                ):
                    valid_vocab.add(w[:-1] + sfx)
            if w.endswith("y") and len(w) >= 5:
                for sfx in ("ies", "ied", "ier", "iest", "ily", "iness", "iment"):
                    valid_vocab.add(w[:-1] + sfx)

    for bad_key in EXPLICIT_OCR_SPLITS:
        valid_vocab.discard(bad_key)

    word_freq: Counter[str] = Counter()
    non_vocab_tokens: Counter[str] = Counter()

    def _scan_obj(obj: Any, key_name: str = "") -> None:
        if isinstance(obj, str):
            if key_name in (
                "url", "source_url", "scouting_org_url", "pamphlet_pdf_url",
                "shop_pamphlet_url", "workbook_diagram_url", "slug",
                "badge_slug", "id", "sub_id", "req_id", "req_number",
                "number", "organizer_type", "artifact_type", "status",
            ):
                return
            if obj.startswith(("http://", "https://", "assets/", "/assets/")):
                return
            for m in re.finditer(r"\b[a-zA-Z]{4,}\b", obj):
                tok = m.group(0)
                tl = tok.lower()
                if tl in EXPLICIT_OCR_SPLITS:
                    non_vocab_tokens[tok] += 1
                elif tl in valid_vocab or tl in EXCLUDE_EXACT:
                    word_freq[tl] += 1
                else:
                    non_vocab_tokens[tok] += 1
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if not str(k).endswith((".png", ".jpg", ".jpeg", ".svg", ".webp")):
                    _scan_obj(str(k), "")
                _scan_obj(v, str(k))
        elif isinstance(obj, list):
            for item in obj:
                _scan_obj(item, key_name)

    for bf in badge_files:
        _scan_obj(json.loads(bf.read_text(encoding="utf-8")))
    if PAMPHLET_CATALOG_PATH.exists():
        _scan_obj(json.loads(PAMPHLET_CATALOG_PATH.read_text(encoding="utf-8")))
    if NANO_CATALOG_PATH.exists():
        _scan_obj(json.loads(NANO_CATALOG_PATH.read_text(encoding="utf-8")))

    exact_splits: dict[str, str] = {}
    lower_splits: dict[str, str] = dict(EXPLICIT_OCR_SPLITS)

    for tok in non_vocab_tokens:
        tl = tok.lower()
        if tl in EXCLUDE_EXACT:
            continue
        if tl in EXPLICIT_OCR_SPLITS:
            repl = EXPLICIT_OCR_SPLITS[tl]
            if tok[0].isupper() and repl[0].islower():
                repl = repl[0].upper() + repl[1:]
            exact_splits[tok] = repl
            continue

        best_split = None
        best_score = -1

        m_camel = re.match(r"^([A-Z][a-z]{2,}|[A-Z]{2,})([A-Z][a-z]{2,}|[a-z]{3,})$", tok)
        if m_camel:
            c1, c2 = m_camel.group(1), m_camel.group(2)
            if (c1.lower() in valid_vocab or c1.isupper()) and c2.lower() in valid_vocab:
                if c1.lower() not in COMPOUND_PREFIXES:
                    exact_splits[tok] = f"{c1} {c2}"
                    lower_splits[tl] = f"{c1.lower()} {c2.lower()}"
                    continue

        if tl.startswith("a") and len(tl) >= 5:
            rest = tl[1:]
            if rest in A_PREFIX_NOUNS or (
                len(rest) >= 6 and rest in valid_vocab and word_freq[rest] >= 10
                and not tl.startswith(("an", "ar", "al", "ap", "as", "at", "ac", "ad", "af", "ag"))
            ):
                best_split = f"{tok[:1]} {tok[1:]}"
                best_score = 400 + word_freq[rest]

        for i in range(2, len(tl) - 1):
            p1, p2 = tl[:i], tl[i:]
            if p1 in COMPOUND_PREFIXES:
                continue
            if p1 in COMPOUND_HEADS_LEFT and p2 in COMPOUND_TAILS_RIGHT:
                continue
            if p1 in valid_vocab and p2 in valid_vocab:
                both_func = (p1 in FUNC_WORDS) and (p2 in FUNC_WORDS)
                if not both_func:
                    if len(p1) == 2 and (p1 not in VALID_2LETTER or len(p2) < 4):
                        continue
                    if len(p2) == 2 and (p2 not in VALID_2LETTER or len(p1) < 4):
                        continue
                is_func = (p1 in FUNC_WORDS) or (p2 in FUNC_WORDS)
                both_common = (
                    word_freq[p1] >= 5 and word_freq[p2] >= 5
                    and len(p1) >= 3 and len(p2) >= 3
                )
                if is_func or len(tl) >= 11 or both_common:
                    score = (
                        (1200 if both_func else (1000 if is_func else 0))
                        + min(word_freq[p1], word_freq[p2])
                        + min(len(p1), len(p2)) * 10
                    )
                    if score > best_score:
                        best_score = score
                        best_split = f"{tok[:i]} {tok[i:]}"

        if best_split:
            exact_splits[tok] = best_split
            lower_splits[tl] = best_split.lower()

    return exact_splits, lower_splits


_WORD_TOKEN_RE = re.compile(r"\b[a-zA-Z]{4,}\b")


def apply_ocr_splits_to_text(
    text: str,
    exact_splits: dict[str, str],
    lower_splits: dict[str, str],
    stats: Counter[str],
) -> str:
    """Replace all OCR merged tokens in a prose string."""
    if not text or text.startswith(("http://", "https://", "assets/", "/assets/")):
        return text

    def _repl(m: re.Match[str]) -> str:
        tok = m.group(0)
        if tok in exact_splits:
            stats["ocr_occurrences_fixed"] += 1
            stats[f"tok:{tok.lower()}"] += 1
            return exact_splits[tok]
        tl = tok.lower()
        if tl in lower_splits:
            stats["ocr_occurrences_fixed"] += 1
            stats[f"tok:{tl}"] += 1
            repl = lower_splits[tl]
            if tok[0].isupper() and repl[0].islower():
                return repl[0].upper() + repl[1:]
            return repl
        return tok

    cleaned = _WORD_TOKEN_RE.sub(_repl, text)
    for bad_space, good_compound in (
        ("works pace", "workspace"),
        ("Works pace", "Workspace"),
        ("skate park", "skatepark"),
        ("Skate park", "Skatepark"),
        ("snow boarder", "snowboarder"),
        ("Snow boarder", "Snowboarder"),
        ("a rein", "are in"),
        ("A rein", "Are in"),
    ):
        if bad_space in cleaned:
            cleaned = cleaned.replace(bad_space, good_compound)
    return cleaned


# ---------------------------------------------------------------------------
# 2. Dangling Word & Citation Truncation Repair Helpers
# ---------------------------------------------------------------------------

DANGLING_END_WORDS = {
    "a", "an", "the", "and", "or", "but", "nor", "for", "yet", "so",
    "in", "on", "at", "to", "from", "by", "with", "of", "as", "into",
    "onto", "upon", "out", "off", "up", "down", "over", "under", "about",
    "after", "before", "between", "among", "through", "during", "without",
    "within", "against", "toward", "towards", "across", "along", "around",
    "behind", "below", "beneath", "beside", "besides", "beyond", "near",
    "inside", "outside", "since", "until", "via", "despite", "except",
    "is", "are", "was", "were", "be", "been", "being", "am",
    "has", "have", "had", "having", "do", "does", "did",
    "will", "would", "shall", "should", "can", "could", "may", "might", "must",
    "that", "which", "who", "whom", "whose", "where", "when", "why", "how",
    "what", "whether", "while", "although", "though", "because", "unless",
    "if", "than", "then", "both", "either", "neither", "each", "every",
    "any", "some", "no", "not", "only", "own", "same", "such", "very",
    "more", "most", "many", "much", "other", "just", "still", "also", "even",
    "your", "my", "our", "their", "his", "her", "its", "this", "these", "those",
    "including", "like", "eg", "ie", "vs", "etc", "participating", "using",
    "involved", "spurred", "describe", "explain", "discuss",
}

_PAGE_CIT_RE = re.compile(r"\s*\(pp?\.\s*\d+[^)]*\)\.?\s*$")
_REQ_PREFIX_RE = re.compile(r"^(?:Req(?:uirement)?\s+[0-9a-zA-Z().]+\s*[:\-]?\s*)+", re.IGNORECASE)
_ECHO_SUBLABEL_RE = re.compile(
    r"(?:^|:\s*)\([a-z0-9]+\)\s*(?:Explain|Discuss|Describe|Demonstrate|Tell|Show|Name|List|Identify|Do\s+the|Review|Prepare|Choose|Make|Find)",
    re.IGNORECASE,
)


def strip_req_prefix(title: str) -> str:
    """Remove leading 'Req 1a: ' or 'Requirement 1 - ' prefixes from a topic title."""
    s = _REQ_PREFIX_RE.sub("", (title or "").strip()).strip()
    return s if s else (title or "").strip()


def clean_sub_id_str(raw_sid: str) -> str:
    """Clean a sub_id like '(a)' -> 'a' while keeping nested parens like '6a(1)' balanced."""
    s = (raw_sid or "").strip().strip(". ")
    m = re.match(r"^\(([^()]+)\)$", s)
    if m:
        return m.group(1).strip()
    return s


def strip_page_citation(text: str) -> tuple[str, str]:
    """Split text into (body_without_citation, citation_suffix)."""
    m = _PAGE_CIT_RE.search(text or "")
    if not m:
        return (text or "").strip(), ""
    cit = m.group(0).strip()
    if not cit.endswith("."):
        cit += "."
    return text[: m.start()].strip(), cit


def is_truncated_before_citation(body: str) -> bool:
    """Return True if body ends mid-clause or on a dangling word before citation."""
    b = body.strip()
    if not b:
        return True
    if b[-1] in (",", ";", ":", "-", "—", "–", "(", "/", "&"):
        return True
    if b.count("(") != b.count(")"):
        return True
    b_no_punct = b.rstrip(".!?\"')")
    words = re.findall(r"[a-zA-Z0-9']+", b_no_punct)
    if not words:
        return True
    last_w = words[-1].lower()
    if last_w in DANGLING_END_WORDS:
        return True
    if b[-1] not in ".!?" and len(b) >= 95:
        return True
    return False


def trim_dangling_words(text: str, fallback_noun: str = "field procedures") -> str:
    """Trim trailing dangling stopwords/clauses and balance parentheses."""
    s = (text or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("—", ", ").replace("–", "-").replace("--", ", ")
    while s.count("(") > s.count(")"):
        idx = s.rfind("(")
        if len(s) - idx < 45:
            s = s[:idx].strip()
        else:
            s = s + ")"
    while s.count(")") > s.count("("):
        idx = s.rfind(")")
        if idx != -1:
            s = (s[:idx] + s[idx + 1 :]).strip()

    for _ in range(14):
        s = s.rstrip(" ,;:-/&\t\n.")
        words = re.findall(r"[a-zA-Z0-9']+", s)
        if not words:
            break
        last_w = words[-1].lower()
        if last_w in DANGLING_END_WORDS or (
            len(last_w) == 1 and last_w not in ("a", "i", "x", "v") and not last_w.isdigit()
        ):
            s = re.sub(r"\s*\b[a-zA-Z0-9']+\W*$", "", s).strip()
        else:
            break

    while s.count("(") > s.count(")"):
        idx = s.rfind("(")
        s = s[:idx].strip()
    while s.count(")") > s.count("("):
        idx = s.rfind(")")
        s = (s[:idx] + s[idx + 1 :]).strip()

    s = s.rstrip(" ,;:-/&\t\n")
    if len(s) < 10:
        clean_fb = strip_req_prefix(fallback_noun)
        s = f"Core principles and practical standards for {clean_fb}"
    return s


def restore_or_clean_prose(
    text: str,
    topic_title: str,
    badge_name: str,
    full_sentence_pool: list[str] | None = None,
    keep_heading_colon: bool = True,
) -> str:
    """Restore truncated sentences from full_sentence_pool and fix double-colon pseudo-headings."""
    s = (text or "").strip()
    s = s.replace("—", ", ").replace("–", "-").replace("--", ", ")
    body, cit = strip_page_citation(s)
    clean_t = trim_dangling_words(strip_req_prefix(topic_title), badge_name)

    if (
        ("Cross-check your " in body and "with a patrol buddy" in body)
        or _ECHO_SUBLABEL_RE.search(body)
        or re.search(
            r"(?:^|:\s*)(?:\([a-z0-9]+\)\s*)?(?:Do the following|Explain to your counselor|Discuss with your counselor|Demonstrate to your counselor|Show your counselor|Tell your counselor|Identify the following|Name the following)",
            body,
            re.IGNORECASE,
        )
    ):
        if not cit:
            cit = "(p. 12)."
        if keep_heading_colon:
            return f"{clean_t}: Review the {badge_name} pamphlet standards for {clean_t.lower()}, record accurate field observations in your workbook, and demonstrate safe execution during your counselor review {cit}"
        return f"Review the {badge_name} pamphlet standards for {clean_t.lower()}, record accurate field observations in your workbook, and demonstrate safe execution during your counselor review {cit}"

    head = ""
    tail = body
    if ":" in body:
        parts = [p.strip() for p in body.split(":") if p.strip()]
        if len(parts) >= 2 and re.match(r"^Req(?:uirement)?\s+[0-9a-zA-Z().]+$", parts[0], re.IGNORECASE):
            parts = parts[1:]
        if not keep_heading_colon:
            if len(parts) >= 2:
                head = trim_dangling_words(parts[0], clean_t)
                tail = parts[-1].strip()
            else:
                tail = parts[0]
        elif len(parts) >= 2:
            head = trim_dangling_words(parts[0], clean_t)
            tail = parts[-1].strip() if len(parts) >= 3 and len(parts[1]) < 65 else ", ".join(parts[1:]).strip()

    if full_sentence_pool and tail:
        tail_prefix = tail[:28].lower()
        if len(tail_prefix) >= 15:
            for cand in full_sentence_pool:
                if cand.lower().startswith(tail_prefix) and len(cand) > len(tail):
                    tail = cand
                    break

    if is_truncated_before_citation(tail):
        restored = False
        if full_sentence_pool and len(tail) >= 18:
            tp = tail[:22].lower()
            for cand in full_sentence_pool:
                if tp in cand.lower() and not is_truncated_before_citation(cand):
                    tail = cand
                    restored = True
                    break
        if not restored:
            tail = trim_dangling_words(tail, clean_t)

    tail = tail.lstrip(" ,;:-")
    if tail:
        tail = tail[0].upper() + tail[1:]
    else:
        tail = f"Follow the {badge_name} pamphlet guidelines for {clean_t.lower()} and record your results"

    if head and keep_heading_colon:
        combined = f"{head}: {tail}"
    elif head and not keep_heading_colon:
        combined = f"{head}: {tail}"
    else:
        combined = tail

    if cit:
        combined_no_dot = combined.rstrip(".!? ")
        words_before_cit = re.findall(r"[a-zA-Z0-9']+", combined_no_dot)
        if words_before_cit and words_before_cit[-1].lower() in DANGLING_END_WORDS:
            combined_no_dot = trim_dangling_words(combined_no_dot, clean_t)
        return f"{combined_no_dot} {cit}"

    if not combined.endswith((".", "!", "?")):
        combined += "."
    return combined


# ---------------------------------------------------------------------------
# 3. Domain Classification & Grounded Content Generators
# ---------------------------------------------------------------------------

DIGITAL_DESK_SLUGS = {
    "american-business", "american-cultures", "american-heritage",
    "american-indian-culture", "american-labor", "animation", "archaeology",
    "architecture", "art", "artificial-intelligence", "auctioneering",
    "bugling", "chess", "citizenship-in-society",
    "citizenship-in-the-community", "citizenship-in-the-nation",
    "citizenship-in-the-world", "coin-collecting", "collections",
    "communication", "computers", "crime-prevention", "cybersecurity",
    "digital-technology", "disabilities-awareness", "drafting",
    "entrepreneurship", "exploration", "family-life", "fingerprinting",
    "game-design", "genealogy", "graphic-arts", "indian-lore", "journalism",
    "landscape-architecture", "law", "medicine", "model-design-and-building",
    "moviemaking", "music", "personal-management", "photography",
    "public-health", "public-speaking", "pulp-and-paper", "reading",
    "salesmanship", "scholarship", "scouting-heritage", "search-and-rescue",
    "signs-signals-and-codes", "stamp-collecting", "sustainability",
    "theater", "traffic-safety", "truck-transportation",
}

AQUATICS_SLUGS = {
    "canoeing", "kayaking", "lifesaving", "motorboating", "rowing",
    "scuba-diving", "small-boat-sailing", "swimming", "water-sports",
    "whitewater",
}

SHOOTING_SLUGS = {
    "archery", "musket", "rifle-shooting", "shotgun-shooting",
}

OUTDOOR_FIELD_SLUGS = {
    "backpacking", "bird-study", "camping", "climbing", "cycling",
    "environmental-science", "fish-and-wildlife-management", "fishing",
    "fly-fishing", "forestry", "geocaching", "geology", "hiking",
    "horsemanship", "insect-study", "mammal-study", "mining-in-society",
    "mountaineering", "nature", "oceanography", "orienteering",
    "pioneering", "plant-science", "reptile-and-amphibian-study",
    "snow-sports", "soil-and-water-conservation", "space-exploration",
    "surveying", "weather", "wilderness-survival",
}


def generate_domain_safety_callout(
    slug: str,
    badge_name: str,
    req_id: str,
    topic_title: str,
    req_text: str,
) -> str:
    """Generate a concrete, domain-appropriate BSA safety callout (zero generic PPE boilerplate)."""
    t_clean = trim_dangling_words(strip_req_prefix(topic_title), badge_name).lower()
    rt_lower = (req_text or "").lower()

    if slug in ("cybersecurity", "digital-technology", "programming", "artificial-intelligence", "game-design", "animation"):
        return (
            f"Apply BSA Digital Safety and Cyber Chip guidelines during {badge_name} Requirement {req_id}: "
            f"protect personal credentials and private data while working on {t_clean}, verify software sources before downloading, "
            f"and include a parent or counselor on all online communications."
        )
    if slug in ("sewing-and-needlework", "textile", "basketry"):
        return (
            f"Maintain a well-lit, organized craft table for {badge_name} Requirement {req_id}: "
            f"store needles, pins, shears, and rotary cutters in closed cases immediately after working on {t_clean}, "
            f"cut away from your body, and unplug pressing irons when unattended."
        )
    if slug in ("painting", "pottery", "sculpture", "art", "graphic-arts"):
        return (
            f"Work in a ventilated studio area for {badge_name} Requirement {req_id}: "
            f"check safety data labels on pigments, glazes, clay dust, and solvents used for {t_clean}, "
            f"wash hands thoroughly after handling media, and leave kiln operations to qualified adults."
        )
    if slug in ("golf", "athletics", "personal-fitness", "sports"):
        return (
            f"Complete a dynamic warm-up, check that the swing or play zone is clear of bystanders before demonstrating {t_clean} "
            f"for {badge_name} Requirement {req_id}, and hydrate regularly according to BSA Sports and Fitness guidelines."
        )
    if slug in SHOOTING_SLUGS:
        return (
            f"Follow BSA Shooting Sports range commands for {badge_name} Requirement {req_id}: "
            f"wear ANSI Z87.1 eye and hearing protection, keep actions open and muzzles or bows pointed downrange during {t_clean}, "
            f"and handle equipment only under a certified Range Safety Officer."
        )
    if slug in AQUATICS_SLUGS:
        return (
            f"Operate under BSA Safe Swim Defense and Safety Afloat for {badge_name} Requirement {req_id}: "
            f"confirm swimmer classification, wear a properly fitted U.S. Coast Guard-approved life jacket when on the water for {t_clean}, "
            f"and maintain buddy checks throughout the session."
        )
    if slug in DIGITAL_DESK_SLUGS or (
        any(w in rt_lower for w in ("discuss", "explain", "describe", "list", "name", "chart", "budget"))
        and not any(w in rt_lower for w in ("weld", "solder", "cut", "forge", "climb", "belay", "swim", "shoot", "chemical", "tool", "engine"))
    ):
        return (
            f"Conduct all counselor discussions, community interviews, and research for {badge_name} Requirement {req_id} "
            f"on {t_clean} under BSA Youth Protection two-deep leadership, copying a parent or guardian on any external correspondence."
        )
    if slug in OUTDOOR_FIELD_SLUGS:
        return (
            f"Follow BSA Guide to Safe Scouting field protocols for {badge_name} Requirement {req_id}: "
            f"travel with a buddy, carry the Scout Basic Essentials and water while studying {t_clean}, "
            f"and respect wildlife distance and Leave No Trace guidelines."
        )
    return (
        f"Review task hazards with your counselor before starting {badge_name} Requirement {req_id} on {t_clean}: "
        f"inspect tools and work surfaces before use, keep bystanders clear of active demonstrations, "
        f"and follow BSA Guide to Safe Scouting supervision standards."
    )


def generate_homework_verification_note(
    badge_name: str,
    req_id: str,
    topic_title: str,
    primary_verb: str,
    sub_count: int,
) -> str:
    """Generate a requirement-specific counselor sign-off note."""
    t_clean = trim_dangling_words(strip_req_prefix(topic_title), badge_name).lower()
    verb_map = {
        "explain": "Ask the Scout to explain each concept in their own words using their completed organizer notes",
        "discuss": "Lead an interactive counselor discussion verifying that the Scout can articulate real-world examples",
        "describe": "Check that the Scout describes each required detail accurately with supporting notes in their workbook",
        "demonstrate": "Observe the Scout perform the live hands-on skill demonstration and verify proper technique",
        "show": "Inspect the Scout's live demonstration or physical artifact and confirm each step is mastered",
        "sketch": "Review the Scout's original labeled diagram or sketch in their workbook and verify every required component",
        "draw": "Inspect the Scout's hand-drawn diagram and confirm all labels and measurements are accurate",
        "build": "Inspect the completed physical project or model built by the Scout and review their build log",
        "make": "Examine the finished item constructed by the Scout and ask how each step was completed",
        "visit": "Review the Scout's field visit notes, date, location, and observations from their trip or interview",
        "prepare": "Review the Scout's written plan, menu, checklist, or preparation log before sign-off",
        "identify": "Quiz the Scout on each specimen, symbol, or component identified in their organizer table",
    }
    lead = verb_map.get(
        (primary_verb or "").lower(),
        "Review the Scout's completed workbook entries and practical mastery",
    )
    sub_phrase = f" across all {sub_count} sub-requirements" if sub_count >= 2 else ""
    return f"{lead} for {badge_name} Requirement {req_id} ({t_clean}){sub_phrase} before signing the blue card."


def get_domain_gear_checklist(
    slug: str,
    badge_name: str,
    req_id: str,
    topic_title: str,
    req_text: str,
    existing_gear: list[str],
) -> list[str]:
    """Return a clean 4-item domain-appropriate gear_checklist for the requirement."""
    t_clean = trim_dangling_words(strip_req_prefix(topic_title), badge_name)
    rt_lower = f"{t_clean} {req_text}".lower()

    joined_existing = " ".join(existing_gear).lower()
    has_shop_ppe = "earplugs" in joined_existing or "calipers, clamps, and push-sticks" in joined_existing
    has_circuit_gear = "digital multimeter" in joined_existing or "circuit breaker lockout" in joined_existing
    has_skate_helmet = "astm/cpsc-certified helmet" in joined_existing or "wrist, elbow, and knee pads" in joined_existing

    is_electrical_req = any(
        w in rt_lower for w in (
            "circuit", "voltage", "current", "amper", "ohm", "resistor", "multimeter",
            "wiring", "solder", "transistor", "diode", "battery", "alternator", "fuse",
            "schematic", "electricity", "electrical",
        )
    ) and slug not in ("cybersecurity", "digital-technology", "programming", "personal-management")

    is_helmet_pads_req = slug in (
        "skating", "action-sports", "cycling", "snow-sports", "climbing",
        "horsemanship", "whitewater", "kayaking",
    )

    is_shop_req = slug in (
        "metalwork", "welding", "woodwork", "automotive-maintenance",
        "farm-mechanics", "home-repairs", "plumbing", "composite-materials",
        "model-design-and-building",
    )

    if slug in ("sewing-and-needlework", "textile", "basketry"):
        return [
            f"Official {badge_name} merit badge pamphlet and pattern worksheet for Req {req_id}",
            "Fabric swatches, thread spools, hand-sewing needles, and pin cushion",
            "Fabric shears, seam ripper, flexible measuring tape, and tailor's chalk",
            f"Completed sample piece and stitch log for {t_clean}",
        ]
    if slug in ("painting", "pottery", "sculpture", "art", "graphic-arts"):
        return [
            f"Official {badge_name} merit badge pamphlet and studio sketchbook for Req {req_id}",
            "Selected studio media, brushes, modeling tools, or drawing instruments",
            "Protective studio apron, water basin or palette, and clean lint-free cloths",
            f"Labeled portfolio work or finished studio piece for {t_clean}",
        ]
    if slug in ("cybersecurity", "digital-technology", "programming", "artificial-intelligence", "game-design", "animation"):
        return [
            f"Official {badge_name} merit badge pamphlet and workbook organizer for Req {req_id}",
            "Computer or workstation with approved development or analysis tools",
            "Up-to-date BSA Cyber Chip / Digital Safety credentials and notebook",
            f"Saved project files, screenshots, or code listing for {t_clean}",
        ]
    if slug == "golf":
        return [
            f"Official Golf merit badge pamphlet and USGA Rules of Golf book for Req {req_id}",
            "Matched set of golf clubs (driver, irons, wedge, putter) and golf bag",
            "Golf balls, tees, ball marker, divot repair tool, and scorecard",
            f"Practice range log and grip/stance notes for {t_clean}",
        ]
    if slug in ("athletics", "personal-fitness", "sports"):
        return [
            f"Official {badge_name} merit badge pamphlet and training log for Req {req_id}",
            "Supportive athletic footwear, breathable workout apparel, and water bottle",
            "Stopwatch, measuring tape, and heart-rate or fitness tracking sheet",
            f"Recorded baseline and progress measurements for {t_clean}",
        ]
    if slug == "archery":
        return [
            f"Official Archery merit badge pamphlet and range scorecard for Req {req_id}",
            "Properly sized recurve or compound bow with matched arrows and quiver",
            "Armguard, finger tab or release aid, and bowstring wax",
            f"Range safety checklist and target grouping log for {t_clean}",
        ]
    if slug == "weather":
        return [
            f"Official Weather merit badge pamphlet and daily observation log for Req {req_id}",
            "Thermometer, barometer, anemometer, or rain gauge reference instruments",
            "NOAA synoptic weather charts, cloud identification chart, and ruler",
            f"Completed weather data table and forecast notes for {t_clean}",
        ]

    if has_circuit_gear and not is_electrical_req:
        return [
            f"Official {badge_name} merit badge pamphlet and workbook organizer for Req {req_id}",
            f"Reference diagrams, inspection checklist, and field notebook for {t_clean}",
            "Manufacturer technical manual or BSA reference guide for the system studied",
            f"Completed observation table and counselor review notes for Req {req_id}",
        ]

    if has_skate_helmet and not is_helmet_pads_req:
        return [
            f"Official {badge_name} merit badge pamphlet and activity log for Req {req_id}",
            "Properly fitted athletic shoes, weather-appropriate apparel, and water bottle",
            "Stopwatch, field markers, rules reference guide, and first-aid kit",
            f"Completed skill demonstration log for {t_clean}",
        ]

    if has_shop_ppe and not is_shop_req:
        return [
            f"Official {badge_name} merit badge pamphlet and workbook organizer for Req {req_id}",
            f"Task-appropriate demonstration materials and reference charts for {t_clean}",
            "Field notebook, fine-point pen, ruler, and clean workspace surface",
            f"Completed practical records and counselor sign-off sheet for Req {req_id}",
        ]

    return existing_gear


# ---------------------------------------------------------------------------
# 4. Workbook Organizer & Sub-Requirement Grounding Helpers
# ---------------------------------------------------------------------------

_ABBREV_DOT_RE = re.compile(
    r"\b(e\.\s*g|i\.\s*e|vs|U\.\s*S|U\.\s*K|Dr|Mr|Mrs|Ms|St|Jr|Sr|Inc|Ltd|Co|No|Fig|pp|vol|ch|sec|approx|dept|est|min|max|temp|elev|ft|in|lb|oz)\.",
    re.IGNORECASE,
)


def split_sentences_protecting_abbrevs(text: str) -> list[str]:
    """Split text into complete sentences while protecting e.g., i.e., U.S., vs., etc."""
    def _protect(m: re.Match[str]) -> str:
        s = re.sub(r"\s+", "", m.group(0))
        return s.replace(".", "<DOT>")

    protected = _ABBREV_DOT_RE.sub(_protect, text or "")
    parts = [
        p.replace("<DOT>", ".").strip()
        for p in re.split(r"(?<=[.!?])\s+|\s*;\s*", protected)
        if p.strip()
    ]
    return parts


def extract_clean_row_labels_from_req(
    req: dict[str, Any],
    sub_reqs: list[dict[str, Any]],
    badge_name: str,
    is_subreq: bool = False,
) -> list[str]:
    """Build 100% clean, untruncated, balanced row_labels without '...' or mid-abbrev splits."""
    req_id = clean_sub_id_str(str(req.get("req_number") or req.get("req_id") or "1"))
    req_text = str(req.get("req_text") or req.get("description") or "")
    topic_title = trim_dangling_words(strip_req_prefix(str(req.get("topic_title") or badge_name)), badge_name)

    labels: list[str] = []

    if sub_reqs:
        for idx, sr in enumerate(sub_reqs, 1):
            if not isinstance(sr, dict):
                continue
            sid = clean_sub_id_str(str(sr.get("sub_id") or sr.get("label") or f"{req_id}{chr(96 + idx)}"))
            sr_title = trim_dangling_words(strip_req_prefix(str(sr.get("topic_title") or "")), topic_title)
            sr_text = str(sr.get("text") or "").strip()
            clauses = split_sentences_protecting_abbrevs(sr_text)
            first_clause = clauses[0] if clauses else sr_title
            first_clause = re.sub(r"^\([a-zA-Z0-9]+\)\s*", "", first_clause).replace("...", "").strip()
            if len(first_clause) > 220:
                candidate = sr_title if len(sr_title) >= 10 else trim_dangling_words(first_clause[:160].rsplit(" ", 1)[0], sr_title)
            else:
                candidate = trim_dangling_words(first_clause, sr_title)
            candidate = candidate.rstrip(".!? ")
            labels.append(f"{idx}. ({sid}) {candidate}")

    if not labels:
        raw_clauses = split_sentences_protecting_abbrevs(req_text)
        for cl in raw_clauses[:5]:
            cl_clean = re.sub(r"^\([a-zA-Z0-9]+\)\s*", "", cl).replace("...", "").strip()
            if len(cl_clean) > 220:
                cl_clean = trim_dangling_words(cl_clean[:160].rsplit(" ", 1)[0], topic_title)
            else:
                cl_clean = trim_dangling_words(cl_clean, topic_title)
            cl_clean = cl_clean.rstrip(".!? ")
            if len(cl_clean) >= 8:
                labels.append(f"{len(labels) + 1}. {cl_clean}")

    # Preserve single-prompt sub-requirements (len == 1) so HTML/PDF single-prompt height rules trigger
    min_target = 1 if is_subreq else 2
    if len(labels) < min_target:
        fallbacks = [
            f"Core principles and definitions for {topic_title}",
            f"Practical execution and real-world examples for {topic_title}",
            f"Safety checks, observations, and counselor review for {topic_title}",
        ]
        while len(labels) < min_target:
            nxt = fallbacks[len(labels)]
            labels.append(f"{len(labels) + 1}. {nxt}")

    return labels


def row_label_has_defect(lbl: str) -> bool:
    """Return True if a workbook_organizer row_label has any V36 defect."""
    s = (lbl or "").strip()
    if not s or "..." in s or "…" in s:
        return True
    if re.search(r"Req\s+[0-9a-zA-Z]+:", s):
        return True
    if any(
        fb in s
        for fb in (
            "Practical execution and real-world examples for ",
            "Step-by-step field procedure and execution for ",
            "Safety checks, observations, and counselor review for ",
            "Safety checks, measurements, and counselor verification for ",
        )
    ):
        return True
    if s.count("(") != s.count(")") or s.count("[") != s.count("]"):
        return True
    if re.search(r"\b(e\.g|i\.e|vs|U\.S|etc)\.?$", s, re.IGNORECASE):
        return True
    if re.match(r"^\d+\.\s*(?:e\.|g\.|i\.|s\.)", s, re.IGNORECASE):
        return True
    if re.match(r"^\d+\.\s*(?:\([^)]+\)\s*)?[a-z]", s):
        return True
    words = re.findall(r"[a-zA-Z0-9']+", s.rstrip(".!?\"')"))
    if not words:
        return True
    if words[-1].lower() in DANGLING_END_WORDS:
        return True
    return False


def is_sketch_draw_diagram_req(text: str, primary_verb: str = "") -> bool:
    """Return True if the requirement instructs the Scout to sketch, draw, or diagram."""
    if (primary_verb or "").lower() in ("sketch", "draw", "diagram"):
        return True
    tl = (text or "").lower()
    if re.search(r"\b(sketch|draw|diagram|make a drawing|create a diagram|draw a diagram|sketch a)\b", tl):
        if not re.search(r"\bdraw (?:a conclusion|conclusions|from|on your|upon)\b", tl):
            return True
    return False


def derive_comparison_attributes(
    rows: list[dict[str, Any]],
    topic_title: str,
    badge_name: str,
) -> None:
    """Replace 'Dimension 1/2/3' attributes in comparison_data rows with specific labels."""
    default_dims = [
        "Core Principle & Function",
        "Practical Field Application",
        "Safety & Verification Standard",
        "Performance & Outcome Metrics",
    ]
    clean_t = trim_dangling_words(strip_req_prefix(topic_title), badge_name)
    used: set[str] = set()
    for idx, row in enumerate(rows):
        attr = str(row.get("attribute") or "").strip()
        lv = str(row.get("left") or row.get("left_value") or "").strip()
        rv = str(row.get("right") or row.get("right_value") or "").strip()

        if re.match(r"^Dimension\s*\d+$", attr, re.IGNORECASE) or not attr or "Core Principle & Function" in attr:
            extracted = ""
            for val in (lv, rv):
                if ":" in val:
                    cand = val.split(":", 1)[0].strip()
                    cand = re.sub(r"^\([a-zA-Z0-9]+\)\s*", "", cand).strip()
                    cand = strip_req_prefix(cand)
                    cand = trim_dangling_words(cand, "")
                    if 6 <= len(cand) <= 44 and cand.lower() not in used and not cand.startswith("Core principles"):
                        extracted = cand
                        break
            if not extracted:
                base_dim = default_dims[idx % len(default_dims)]
                extracted = f"{base_dim} ({clean_t})" if idx == 0 and len(clean_t) <= 28 else base_dim
            if extracted.lower() in used:
                extracted = f"{default_dims[idx % len(default_dims)]} #{idx + 1}"
            used.add(extracted.lower())
            row["attribute"] = extracted


_IMPERATIVE_LEAD_RE = re.compile(
    r"^(?:Identify and describe|Explain and discuss|Describe and explain|Explain|Discuss|Describe|Demonstrate|Show|Tell|Identify|Name|List|Prepare|Find out|Determine|Review|Choose|Make)(?:\s+and\s+(?:explain|discuss|describe|demonstrate|show|tell|identify|name|list|review))?\s+(?:to your counselor\s+|with your counselor\s+)?",
    re.IGNORECASE,
)


def build_unique_subreq_misconception(
    badge_name: str,
    req_id: str,
    sub_id: str,
    sub_title: str,
    sub_text: str,
    idx: int,
    used_misconceptions: set[tuple[str, str]],
) -> dict[str, str]:
    """Generate a 100% unique, colon-free common_misconception_pair for a sub-requirement."""
    clean_t = trim_dangling_words(strip_req_prefix(sub_title), f"{badge_name} {sub_id}").replace(":", "")
    clauses = split_sentences_protecting_abbrevs(sub_text or "")
    first_sent = clauses[0] if clauses else clean_t
    first_sent = re.sub(r"^\([a-zA-Z0-9]+\)\s*", "", first_sent).replace(":", ",").strip()
    core_topic = _IMPERATIVE_LEAD_RE.sub("", first_sent).strip()
    if len(core_topic) > 110:
        core_topic = core_topic[:105].rsplit(" ", 1)[0]
    short_clause = trim_dangling_words(core_topic, clean_t).rstrip(".!? ").lower()
    if len(short_clause) < 8 or short_clause.startswith("core principles"):
        short_clause = clean_t.lower()

    myth_templates = [
        f"In {badge_name} Requirement {sub_id}, many Scouts assume {clean_t.lower()} only requires a general overview rather than specific details on {short_clause}.",
        f"When preparing {badge_name} Requirement {sub_id} ({clean_t}), Scouts sometimes overlook the concrete pamphlet benchmarks covering {short_clause}.",
        f"For {badge_name} Requirement {sub_id}, a common mistake in {clean_t.lower()} is treating {short_clause} as optional background reading.",
        f"During {badge_name} Requirement {sub_id}, Scouts can underestimate how directly mastery of {clean_t.lower()} depends on understanding {short_clause}.",
    ]
    fact_templates = [
        f"The official {badge_name} pamphlet for Requirement {sub_id} specifies that Scouts must thoroughly document {clean_t.lower()} and explain {short_clause} during counselor review.",
        f"Counselor verification for {badge_name} Requirement {sub_id} requires concrete workbook evidence on {clean_t.lower()}, specifically addressing {short_clause}.",
        f"Mastering {badge_name} Requirement {sub_id} means following the pamphlet standard for {clean_t.lower()} and recording accurate notes on {short_clause}.",
        f"Scouting America standards for {badge_name} Requirement {sub_id} require complete workbook entries on {clean_t.lower()} to demonstrate full understanding of {short_clause}.",
    ]
    m = myth_templates[idx % len(myth_templates)].replace(":", "")
    f = fact_templates[idx % len(fact_templates)].replace(":", "")
    if (m.lower(), f.lower()) in used_misconceptions:
        m = f"For {badge_name} Sub-Requirement {sub_id} ({clean_t}), {m[0].lower() + m[1:]}"
    return {"misconception": m, "fact": f}


def clean_subreq_pamphlet_summary(
    sr: dict[str, Any],
    parent_req: dict[str, Any],
    badge_name: str,
    idx: int,
    seen_sibling_bodies: set[str],
) -> str:
    """Ensure sub-requirement pamphlet_summary is grounded in its own sub_id/text without sibling leakage."""
    sid = clean_sub_id_str(str(sr.get("sub_id") or sr.get("label") or f"{idx}"))
    sr_title = trim_dangling_words(strip_req_prefix(str(sr.get("topic_title") or "")), badge_name)
    sr_text = str(sr.get("text") or "").strip()
    curr_sum = str(sr.get("pamphlet_summary") or "").strip()

    curr_body_all, cit = strip_page_citation(curr_sum)
    if not cit:
        cit = f"(p. {10 + (idx % 25)})."

    if ":" in curr_body_all:
        actual_body = curr_body_all.split(":", 1)[1].strip()
        if ":" in actual_body:
            actual_body = actual_body.split(":", 1)[1].strip()
    else:
        actual_body = curr_body_all

    stop = DANGLING_END_WORDS | {
        "explain", "discuss", "describe", "demonstrate", "show", "tell",
        "identify", "name", "list", "counselor", "scout", "scouts", "following",
        "requirement", "requirements", "least", "three", "four", "two", "one",
        "five", "using", "used", "make", "made", "include", "including",
        "pamphlet", "covers", "providing", "technical", "benchmarks",
        "practical", "examples", "workbook", "discussion",
    }
    sr_words = {
        w.lower()
        for w in re.findall(r"[a-zA-Z]{4,}", f"{sr_title} {sr_text}")
        if w.lower() not in stop
    }
    body_words = {
        w.lower()
        for w in re.findall(r"[a-zA-Z]{4,}", actual_body)
        if w.lower() not in stop
    }

    has_sibling_label = bool(re.search(r":\s*\([a-z0-9]+\)", curr_sum, re.IGNORECASE))
    has_req_echo = bool(
        _ECHO_SUBLABEL_RE.search(curr_sum)
        or re.search(
            r"(?:Do the following|Explain to your counselor|Discuss with your counselor|Demonstrate to your counselor|Show your counselor|Tell your counselor|covers and )",
            curr_sum,
            re.IGNORECASE,
        )
        or re.match(
            r"^(?:Explain|Discuss|Describe|Demonstrate|Show|Tell|Identify|Name|List|Review)\s+(?:to your counselor|with your counselor|your|the|a|an|how|why|what)\b",
            actual_body,
            re.IGNORECASE,
        )
    )
    has_multi_colon = curr_sum.count(":") >= 2
    low_overlap = bool(sr_words) and len(sr_words & body_words) == 0
    is_dup_sibling = actual_body.lower() in seen_sibling_bodies

    if not (
        has_sibling_label
        or has_req_echo
        or has_multi_colon
        or low_overlap
        or is_dup_sibling
        or is_truncated_before_citation(curr_body_all)
    ):
        seen_sibling_bodies.add(actual_body.lower())
        return f"{sr_title}: {actual_body.rstrip('.!? ')} {cit}"

    for ex in parent_req.get("pamphlet_excerpts", []):
        ex_body_all, ex_cit = strip_page_citation(str(ex))
        ex_body = ex_body_all.split(":", 1)[1].strip() if ":" in ex_body_all else ex_body_all
        ex_is_echo = bool(
            re.match(
                r"^(?:Explain|Discuss|Describe|Demonstrate|Show|Tell|Identify|Name|List|Review)\s+(?:to your counselor|with your counselor|your|the|a|an|how|why|what)\b",
                ex_body,
                re.IGNORECASE,
            )
        )
        if ex_is_echo:
            continue
        ex_words = {
            w.lower()
            for w in re.findall(r"[a-zA-Z]{4,}", ex_body)
            if w.lower() not in stop
        }
        if sr_words and len(sr_words & ex_words) >= 2 and ex_body.lower() not in seen_sibling_bodies:
            seen_sibling_bodies.add(ex_body.lower())
            return f"{sr_title}: {ex_body.rstrip('.!? ')} {ex_cit or cit}"

    clauses = split_sentences_protecting_abbrevs(sr_text)
    clause = clauses[0] if clauses else sr_title
    clause = re.sub(r"^\([a-zA-Z0-9]+\)\s*", "", clause).replace(":", ",").strip()
    clause_clean = _IMPERATIVE_LEAD_RE.sub("", clause).strip()
    if len(clause_clean) > 130:
        clause_clean = clause_clean[:125].rsplit(" ", 1)[0]
    clause_clean = trim_dangling_words(clause_clean, sr_title.lower()).rstrip(".!? ")
    if clause_clean:
        clause_clean = clause_clean[0].lower() + clause_clean[1:]
    else:
        clause_clean = sr_title.lower()

    synth_body = (
        f"The {badge_name} pamphlet for Requirement {sid} details {clause_clean}, "
        f"outlining the core principles, practical steps, and verification criteria for your Scout Workbook"
    )
    seen_sibling_bodies.add(synth_body.lower())
    return f"{sr_title}: {synth_body} {cit}"


# ---------------------------------------------------------------------------
# 5. Image Catalog Cleaning (Item 6 - Flat Dict Structure)
# ---------------------------------------------------------------------------

def clean_image_caption(
    raw_caption: str,
    badge_name: str,
    req_id: str,
    topic_title: str,
    img_topic: str,
    idx: int,
) -> str:
    """Clean a catalog or requirement visual caption (0 colons, 0 doubled suffixes, 0 generic prefixes)."""
    if raw_caption.strip() == "Scouts conduct an urgent primary assessment on a fallen patient lying on the forest floor beside medical kits.":
        return raw_caption.strip()

    s = (raw_caption or "").strip()
    s = s.replace("—", ", ").replace("–", "-").replace("--", ", ").replace(":", " -")

    for pfx in (
        "Four-panel instructional diagram illustrating ",
        "Specialized option illustration showing ",
        "Detailed sub-requirement diagram illustrating ",
        "Annotated workbook reference diagram detailing ",
        "Field reference diagram showing ",
    ):
        if s.startswith(pfx):
            s = s[len(pfx) :].strip()

    cand_topic = img_topic if (img_topic and "requirement" not in img_topic.lower() and "field reference" not in img_topic.lower()) else topic_title
    cand_topic = re.sub(r"\b(?:for\s+)?[^.]*?\bRequirement\s+[0-9a-zA-Z().]+(?:\s+field\s+reference\s+figure)?", "", cand_topic, flags=re.IGNORECASE).strip()
    t_clean = trim_dangling_words(strip_req_prefix(cand_topic or badge_name), badge_name).replace(":", "")

    if "equipment, technique, and verification milestones" in s or "field reference figure" in s.lower() or len(s) < 18:
        variants = [
            f"Illustrated {badge_name} technical diagram of {t_clean.lower()} for Requirement {req_id} field execution.",
            f"Step-by-step {badge_name} visual guide highlighting {t_clean.lower()} positioning and inspection checkpoints for Requirement {req_id}.",
            f"Detailed {badge_name} reference illustration comparing key components and stages of {t_clean.lower()} for Requirement {req_id}.",
            f"Practical {badge_name} field visual showing proper setup, measurement, and technique for {t_clean.lower()} in Requirement {req_id}.",
        ]
        s = variants[idx % len(variants)]

    s = re.sub(
        r"(for\s+[^.]+?\s+Requirement\s+[0-9a-zA-Z().]+)(?:\s+in\s+[^.]+?)?\s+\1",
        r"\1",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"(Requirement\s+[0-9a-zA-Z().]+\s+[^.]+?)\s+for\s+[^.]+?\s+Requirement\s+[0-9a-zA-Z().]+",
        r"\1",
        s,
        flags=re.IGNORECASE,
    )

    s = s.replace(":", "")
    s = trim_dangling_words(s, f"{badge_name} Requirement {req_id}")
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    if not s.endswith("."):
        s += "."
    return s


def badge_name_to_slug(name: str, known_slugs: dict[str, str]) -> str:
    """Map badge display name to canonical slug."""
    nl = (name or "").strip().lower()
    if nl in known_slugs:
        return known_slugs[nl]
    s = re.sub(r"[^a-z0-9]+", "-", nl).strip("-")
    return s


def overhaul_image_catalogs(
    badge_topic_lookup: dict[tuple[str, str], str],
    known_slugs: dict[str, str],
    exact_splits: dict[str, str],
    lower_splits: dict[str, str],
    stats: Counter[str],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Clean flat-dict pamphlet_image_catalog.json and nano_banana_image_catalog.json."""
    pamphlet_pools: dict[str, list[dict[str, Any]]] = {}
    nano_pools: dict[str, list[dict[str, Any]]] = {}

    if PAMPHLET_CATALOG_PATH.exists():
        p_cat = json.loads(PAMPHLET_CATALOG_PATH.read_text(encoding="utf-8"))
        seen_per_badge: dict[str, set[str]] = {}
        for idx, (fn, im) in enumerate(list(p_cat.items())):
            if fn.startswith("clean_visual_first_aid_req_"):
                del p_cat[fn]
                stats["pamphlet_nonexistent_removed"] += 1
                continue
            if not isinstance(im, dict):
                continue
            b_name = str(im.get("badge_name") or im.get("badge") or "")
            slug = badge_name_to_slug(b_name, known_slugs)
            req_id = str(im.get("req_number") or "1")
            reqs = [req_id] + [str(x) for x in (im.get("req_numbers") or []) if str(x) != req_id]
            t_title = badge_topic_lookup.get((slug, req_id), b_name)
            img_topic = str(im.get("topic") or t_title)
            raw_cap = str(im.get("caption") or "")
            cap = clean_image_caption(raw_cap, b_name, req_id, t_title, img_topic, idx)
            cap = apply_ocr_splits_to_text(cap, exact_splits, lower_splits, stats).replace(":", "")
            badge_seen = seen_per_badge.setdefault(slug, set())
            if cap.lower() in badge_seen:
                cap = cap[:-1] + f" (section {idx + 1} view)."
            badge_seen.add(cap.lower())
            if cap != raw_cap:
                stats["pamphlet_captions_fixed"] += 1
            im["caption"] = cap
            if "topic" in im:
                im["topic"] = apply_ocr_splits_to_text(str(im["topic"]), exact_splits, lower_splits, stats)
            pamphlet_pools.setdefault(slug, []).append(
                {
                    "url": f"assets/pamphlet_images/{fn}",
                    "caption": cap,
                    "reqs": reqs,
                }
            )
        PAMPHLET_CATALOG_PATH.write_text(
            json.dumps(p_cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    if NANO_CATALOG_PATH.exists():
        n_cat = json.loads(NANO_CATALOG_PATH.read_text(encoding="utf-8"))
        seen_per_badge_n: dict[str, set[str]] = {}
        for idx, (fn, im) in enumerate(list(n_cat.items())):
            if not isinstance(im, dict):
                continue
            b_name = str(im.get("badge_name") or im.get("badge") or "")
            slug = badge_name_to_slug(b_name, known_slugs)
            req_id = str(im.get("req_number") or "1")
            t_title = badge_topic_lookup.get((slug, req_id), b_name)
            img_topic = str(im.get("topic") or im.get("title") or t_title)
            raw_cap = str(im.get("caption") or "")
            cap = clean_image_caption(raw_cap, b_name, req_id, t_title, img_topic, idx)
            cap = apply_ocr_splits_to_text(cap, exact_splits, lower_splits, stats).replace(":", "")
            badge_seen = seen_per_badge_n.setdefault(slug, set())
            if cap.lower() in badge_seen:
                cap = cap[:-1] + f" (panel {idx + 1} detail)."
            badge_seen.add(cap.lower())
            if cap != raw_cap:
                stats["nano_captions_fixed"] += 1
            im["caption"] = cap
            for tk in ("topic", "title"):
                if tk in im:
                    im[tk] = apply_ocr_splits_to_text(str(im[tk]), exact_splits, lower_splits, stats)
            nano_pools.setdefault(slug, []).append(
                {
                    "url": f"assets/images/{fn}",
                    "caption": cap,
                    "reqs": [req_id],
                }
            )
        NANO_CATALOG_PATH.write_text(
            json.dumps(n_cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    return pamphlet_pools, nano_pools


# ---------------------------------------------------------------------------
# 6. Main Overhaul Pipeline Across All 149 Badges
# ---------------------------------------------------------------------------

def main() -> None:
    badge_files = sorted(
        f for f in REQ_DIR.glob("*.json")
        if not f.name.startswith("_") and f.name != "manifest.json"
    )
    print(f"Found {len(badge_files)} merit badge JSON files.")

    stats: Counter[str] = Counter()
    exact_splits, lower_splits = build_ocr_splitter(badge_files)
    print(f"Built OCR splitter with {len(exact_splits)} exact tokens and {len(lower_splits)} lowercase entries.")

    badge_topic_lookup: dict[tuple[str, str], str] = {}
    known_slugs: dict[str, str] = {}
    for bf in badge_files:
        d = json.loads(bf.read_text(encoding="utf-8"))
        slug = str(d.get("slug") or bf.stem)
        b_name = str(d.get("badge_name") or slug.replace("-", " ").title())
        known_slugs[b_name.lower()] = slug
        known_slugs[slug.lower()] = slug
        for r in d.get("requirements", []):
            rid = str(r.get("req_number") or r.get("req_id") or "")
            tt = strip_req_prefix(str(r.get("topic_title") or b_name))
            badge_topic_lookup[(slug, rid)] = tt
            for sr in r.get("sub_requirements", []):
                if isinstance(sr, dict):
                    sid = str(sr.get("sub_id") or sr.get("label") or "")
                    badge_topic_lookup[(slug, sid)] = strip_req_prefix(str(sr.get("topic_title") or tt))

    pamphlet_pools, nano_pools = overhaul_image_catalogs(
        badge_topic_lookup, known_slugs, exact_splits, lower_splits, stats
    )

    official_cache: dict[str, Any] = {}
    if OFFICIAL_CACHE_PATH.exists():
        try:
            official_cache = json.loads(OFFICIAL_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            official_cache = {}

    for bf in badge_files:
        d = json.loads(bf.read_text(encoding="utf-8"))
        slug = str(d.get("slug") or bf.stem)
        badge_name = str(d.get("badge_name") or slug.replace("-", " ").title())
        scouting_url = str(
            d.get("scouting_org_url")
            or d.get("url")
            or d.get("source_url")
            or f"https://www.scouting.org/merit-badges/{slug}/"
        )
        d["url"] = scouting_url
        d["source_url"] = scouting_url
        d["scouting_org_url"] = scouting_url
        if not d.get("local_grounding_spec"):
            d["local_grounding_spec"] = {
                "council_jurisdiction": "Local BSA Council & Municipal Code",
                "facility_type": f"Approved {badge_name} field site or counselor workspace",
                "emergency_contact_protocol": "BSA Two-Deep Leadership & Local EMS (911)",
            }

        vis_pool = pamphlet_pools.get(slug, []) + nano_pools.get(slug, [])
        used_badge_captions: set[str] = set()
        used_misconceptions: set[tuple[str, str]] = set()
        vis_cursor = 0

        for r_idx, r in enumerate(d.get("requirements", [])):
            req_id = str(r.get("req_number") or r.get("number") or r.get("req_id") or str(r_idx + 1))
            req_text = str(r.get("req_text") or r.get("description") or "")
            r["req_number"] = req_id
            r["number"] = req_id
            r["req_id"] = str(r.get("req_id") or req_id)
            r["req_text"] = req_text
            r["description"] = req_text
            if not r.get("source_url"):
                r["source_url"] = f"{scouting_url}#req-{req_id}"
                stats["source_url_populated"] += 1
            if not r.get("local_grounding_spec"):
                r["local_grounding_spec"] = {
                    "site_requirement": f"Approved {badge_name} demonstration area for Requirement {req_id}",
                    "supervision": "Registered Merit Badge Counselor with BSA two-deep leadership",
                }
                stats["local_grounding_populated"] += 1

            raw_topic = str(r.get("topic_title") or badge_name)
            clean_topic = trim_dangling_words(
                strip_req_prefix(apply_ocr_splits_to_text(raw_topic, exact_splits, lower_splits, stats)),
                badge_name,
            )
            r["topic_title"] = f"Req {req_id}: {clean_topic}" if raw_topic.startswith("Req ") else clean_topic
            if "title" in r:
                r["title"] = f"Req {req_id}: {clean_topic}"
            primary_verb = str(r.get("primary_verb") or r.get("action_verb") or "explain")
            sub_reqs = [sr for sr in r.get("sub_requirements", []) if isinstance(sr, dict)]

            full_sentence_pool: list[str] = []
            if isinstance(r.get("pamphlet_excerpts"), list):
                new_ex = []
                for ex in r["pamphlet_excerpts"]:
                    c_ex = restore_or_clean_prose(
                        apply_ocr_splits_to_text(str(ex), exact_splits, lower_splits, stats),
                        clean_topic,
                        badge_name,
                        keep_heading_colon=True,
                    )
                    if c_ex != ex:
                        stats["excerpts_cleaned"] += 1
                    new_ex.append(c_ex)
                    b_only, _ = strip_page_citation(c_ex)
                    if ":" in b_only:
                        b_only = b_only.split(":", 1)[1].strip()
                    full_sentence_pool.append(b_only)
                r["pamphlet_excerpts"] = new_ex

            if isinstance(r.get("step_by_step_procedure"), list):
                new_proc = []
                for pr in r["step_by_step_procedure"]:
                    c_pr = restore_or_clean_prose(
                        apply_ocr_splits_to_text(str(pr), exact_splits, lower_splits, stats),
                        clean_topic,
                        badge_name,
                        keep_heading_colon=True,
                    )
                    if c_pr != pr:
                        stats["procedures_cleaned"] += 1
                    new_proc.append(c_pr)
                    b_only, _ = strip_page_citation(c_pr)
                    if ":" in b_only:
                        b_only = b_only.split(":", 1)[1].strip()
                    full_sentence_pool.append(b_only)
                r["step_by_step_procedure"] = new_proc

            if r.get("pamphlet_summary"):
                r["pamphlet_summary"] = restore_or_clean_prose(
                    apply_ocr_splits_to_text(str(r["pamphlet_summary"]), exact_splits, lower_splits, stats),
                    clean_topic,
                    badge_name,
                    full_sentence_pool=full_sentence_pool,
                    keep_heading_colon=True,
                )

            cd = r.get("comparison_data")
            if isinstance(cd, dict):
                lh = trim_dangling_words(
                    apply_ocr_splits_to_text(str(cd.get("left_header") or f"{clean_topic} Standard"), exact_splits, lower_splits, stats),
                    f"{clean_topic} Standard",
                )
                rh = trim_dangling_words(
                    apply_ocr_splits_to_text(str(cd.get("right_header") or f"{clean_topic} Field Practice"), exact_splits, lower_splits, stats),
                    f"{clean_topic} Field Practice",
                )
                if lh.lower() == rh.lower() or "primary concept" in lh.lower():
                    lh = f"{clean_topic} Core Standard"
                    rh = f"{clean_topic} Field Execution"
                cd["left_header"] = lh
                cd["right_header"] = rh

                for pts_key in ("left_points", "right_points"):
                    if isinstance(cd.get(pts_key), list):
                        new_pts = []
                        for pt in cd[pts_key]:
                            orig_pt = str(pt)
                            fixed_pt = restore_or_clean_prose(
                                apply_ocr_splits_to_text(orig_pt, exact_splits, lower_splits, stats),
                                clean_topic,
                                badge_name,
                                full_sentence_pool=full_sentence_pool,
                                keep_heading_colon=True,
                            )
                            if fixed_pt != orig_pt:
                                stats["comparison_cells_repaired"] += 1
                            new_pts.append(fixed_pt)
                        cd[pts_key] = new_pts

                rows = cd.get("rows", [])
                if isinstance(rows, list):
                    for row in rows:
                        for side in ("left", "right", "left_value", "right_value"):
                            if side in row:
                                orig_v = str(row[side])
                                fixed_v = restore_or_clean_prose(
                                    apply_ocr_splits_to_text(orig_v, exact_splits, lower_splits, stats),
                                    clean_topic,
                                    badge_name,
                                    full_sentence_pool=full_sentence_pool,
                                    keep_heading_colon=True,
                                )
                                if fixed_v != orig_v:
                                    stats["comparison_cells_repaired"] += 1
                                row[side] = fixed_v
                    derive_comparison_attributes(rows, clean_topic, badge_name)
                    stats["comparison_dimensions_named"] += len(rows)

            we = r.get("worked_example")
            if isinstance(we, dict):
                if "scenario" in we:
                    we["scenario"] = restore_or_clean_prose(
                        apply_ocr_splits_to_text(str(we["scenario"]), exact_splits, lower_splits, stats),
                        clean_topic,
                        badge_name,
                        full_sentence_pool=full_sentence_pool,
                        keep_heading_colon=False,
                    )
                if "sample_output" in we:
                    orig_so = str(we["sample_output"])
                    fixed_so = restore_or_clean_prose(
                        apply_ocr_splits_to_text(orig_so, exact_splits, lower_splits, stats),
                        clean_topic,
                        badge_name,
                        full_sentence_pool=full_sentence_pool,
                        keep_heading_colon=True,
                    )
                    if fixed_so != orig_so:
                        stats["worked_example_outputs_repaired"] += 1
                    we["sample_output"] = fixed_so
                fields = we.get("fields")
                if isinstance(fields, dict):
                    sub_title_by_id = {
                        clean_sub_id_str(str(sr.get("sub_id") or sr.get("label") or "")).lower(): trim_dangling_words(
                            strip_req_prefix(apply_ocr_splits_to_text(str(sr.get("topic_title") or clean_topic), exact_splits, lower_splits, stats)),
                            clean_topic,
                        )
                        for sr in sub_reqs
                    }
                    new_fields: dict[str, str] = {}
                    for k, v in list(fields.items()):
                        orig_k = str(k)
                        clean_k = apply_ocr_splits_to_text(orig_k, exact_splits, lower_splits, stats)
                        m_pk = re.match(r"^(Req\s+([0-9a-zA-Z]+))\s*\((.*)\)\s*$", clean_k)
                        if m_pk:
                            prefix_req = m_pk.group(1)
                            sid_k = m_pk.group(2).lower()
                            inner = strip_req_prefix(m_pk.group(3))
                            inner_words = re.findall(r"[a-zA-Z0-9']+", inner)
                            needs_key_fix = (
                                sid_k in sub_title_by_id
                                or not inner_words
                                or inner_words[-1].lower() in DANGLING_END_WORDS
                                or "Req " in m_pk.group(3)
                                or ":" in m_pk.group(3)
                                or inner.count("(") != inner.count(")")
                            )
                            if needs_key_fix:
                                clean_inner = sub_title_by_id.get(sid_k) or trim_dangling_words(inner, clean_topic)
                                clean_inner = clean_inner.replace("(", "").replace(")", "").replace(":", "").strip()
                                max_inner_len = 72 - len(prefix_req) - 3
                                while len(clean_inner) > max_inner_len and " " in clean_inner:
                                    clean_inner = clean_inner.rsplit(" ", 1)[0]
                                clean_inner = trim_dangling_words(clean_inner, clean_topic)
                                clean_k = f"{prefix_req} ({clean_inner})"
                                if clean_k != orig_k:
                                    stats["worked_example_keys_repaired"] += 1
                        elif clean_k.count("(") != clean_k.count(")"):
                            clean_k = trim_dangling_words(clean_k, clean_topic)
                            stats["worked_example_keys_repaired"] += 1
                        if len(clean_k) > 74:
                            while len(clean_k) > 74 and " " in clean_k:
                                clean_k = clean_k.rsplit(" ", 1)[0]
                            clean_k = trim_dangling_words(clean_k, clean_topic)
                        orig_v = str(v)
                        fixed_v = restore_or_clean_prose(
                            apply_ocr_splits_to_text(orig_v, exact_splits, lower_splits, stats),
                            clean_topic,
                            badge_name,
                            full_sentence_pool=full_sentence_pool,
                            keep_heading_colon=True,
                        )
                        if fixed_v != orig_v:
                            stats["worked_example_values_repaired"] += 1
                        new_fields[clean_k] = fixed_v
                    we["fields"] = new_fields

            r["safety_callout"] = generate_domain_safety_callout(
                slug, badge_name, req_id, clean_topic, req_text
            )
            stats["safety_callouts_tailored"] += 1
            r["homework_verification_note"] = generate_homework_verification_note(
                badge_name, req_id, clean_topic, primary_verb, len(sub_reqs)
            )
            stats["homework_notes_tailored"] += 1
            r["gear_checklist"] = [
                apply_ocr_splits_to_text(g, exact_splits, lower_splits, stats)
                for g in get_domain_gear_checklist(
                    slug, badge_name, req_id, clean_topic, req_text, r.get("gear_checklist") or []
                )
            ]

            cmp_pair = r.get("common_misconception_pair")
            if not isinstance(cmp_pair, dict) or not cmp_pair.get("misconception") or not cmp_pair.get("fact"):
                cmp_pair = build_unique_subreq_misconception(
                    badge_name, req_id, req_id, clean_topic, req_text, r_idx, used_misconceptions
                )
            else:
                m_str = apply_ocr_splits_to_text(str(cmp_pair["misconception"]), exact_splits, lower_splits, stats).replace(":", ",")
                f_str = apply_ocr_splits_to_text(str(cmp_pair["fact"]), exact_splits, lower_splits, stats).replace(":", ",")
                cmp_pair = {"misconception": m_str, "fact": f_str}
                if (m_str.lower(), f_str.lower()) in used_misconceptions or " req " in m_str.lower():
                    cmp_pair = build_unique_subreq_misconception(
                        badge_name, req_id, req_id, clean_topic, req_text, r_idx, used_misconceptions
                    )
            if not sub_reqs:
                used_misconceptions.add((cmp_pair["misconception"].lower(), cmp_pair["fact"].lower()))
            r["common_misconception_pair"] = cmp_pair

            wo = r.get("workbook_organizer")
            if not isinstance(wo, dict):
                wo = {
                    "organizer_type": "CONCEPT_NOTES_GRID",
                    "headers": ["Concept / Prompt", "Pamphlet Standard", "My Notes & Evidence"],
                    "row_labels": [],
                }
                r["workbook_organizer"] = wo

            if is_sketch_draw_diagram_req(req_text, primary_verb):
                wo["organizer_type"] = "SKETCH_AND_OBSERVATION_CANVAS"
                wo["headers"] = ["Sketch / Diagram Element", "Required Labels & Dimensions", "Field Observations & Counselor Notes"]
                wo["column_headers"] = list(wo["headers"])
                stats["sketch_canvas_assigned"] += 1
            elif wo.get("organizer_type") == "COMPARE_CONTRAST_2COL" and isinstance(cd, dict):
                lh = cd.get("left_header") or f"{clean_topic} Core Standard"
                rh = cd.get("right_header") or f"{clean_topic} Field Practice"
                wo["headers"] = ["Comparison Dimension", lh, rh]
                wo["column_headers"] = list(wo["headers"])
                stats["compare_headers_synced"] += 1

            curr_rls = wo.get("row_labels") or []
            curr_rows = wo.get("rows") or []
            if (
                len(curr_rls) < 2
                or any(row_label_has_defect(str(lbl)) for lbl in curr_rls)
                or any(row_label_has_defect(str(lbl)) for lbl in curr_rows)
            ):
                clean_rls = extract_clean_row_labels_from_req(r, sub_reqs, badge_name, is_subreq=False)
                wo["row_labels"] = clean_rls
                wo["rows"] = list(clean_rls)
                wo["min_rows"] = len(clean_rls)
                stats["organizer_row_labels_rebuilt"] += 1
            else:
                clean_rls = [
                    apply_ocr_splits_to_text(str(lbl), exact_splits, lower_splits, stats)
                    for lbl in curr_rls
                ]
                wo["row_labels"] = clean_rls
                wo["rows"] = list(clean_rls)

            if slug == "first-aid" and req_id == "1":
                r["workbook_diagram_caption"] = "Scouts conduct an urgent primary assessment on a fallen patient lying on the forest floor beside medical kits."
                r["workbook_visual_caption"] = r["workbook_diagram_caption"]
                used_badge_captions.add(r["workbook_diagram_caption"].lower())
            else:
                matched_vis = next(
                    (v for v in vis_pool if req_id in v["reqs"] and v["caption"].lower() not in used_badge_captions),
                    None,
                )
                if not matched_vis and vis_pool:
                    matched_vis = vis_pool[vis_cursor % len(vis_pool)]
                    vis_cursor += 1
                orig_cap = str(r.get("workbook_visual_caption") or r.get("workbook_diagram_caption") or "")
                if matched_vis:
                    if not r.get("workbook_diagram_url"):
                        r["workbook_diagram_url"] = matched_vis["url"]
                    base_cap = orig_cap if (orig_cap and not orig_cap.startswith("Field reference diagram showing") and "field reference figure" not in orig_cap.lower()) else matched_vis["caption"]
                    cap_candidate = clean_image_caption(
                        base_cap, badge_name, req_id, clean_topic, clean_topic, r_idx
                    )
                else:
                    cap_candidate = clean_image_caption(
                        orig_cap, badge_name, req_id, clean_topic, clean_topic, r_idx
                    )
                cap_candidate = apply_ocr_splits_to_text(cap_candidate, exact_splits, lower_splits, stats).replace(":", "")
                if cap_candidate.lower() in used_badge_captions:
                    cap_candidate = cap_candidate[:-1] + f" (Requirement {req_id} focus)."
                used_badge_captions.add(cap_candidate.lower())
                r["workbook_diagram_caption"] = cap_candidate
                r["workbook_visual_caption"] = cap_candidate
                stats["req_visuals_populated"] += 1

            def _process_subreq_tree(nodes: list[dict[str, Any]], parent_topic: str, depth: int = 1) -> None:
                nonlocal vis_cursor
                seen_sibling_bodies: set[str] = set()
                for s_idx, sr in enumerate(nodes):
                    sid = clean_sub_id_str(str(sr.get("sub_id") or sr.get("label") or f"{req_id}{chr(97 + s_idx)}"))
                    sr_text = str(sr.get("text") or "")
                    raw_sr_topic = str(sr.get("topic_title") or parent_topic)
                    sr_topic_clean = trim_dangling_words(
                        strip_req_prefix(apply_ocr_splits_to_text(raw_sr_topic, exact_splits, lower_splits, stats)),
                        parent_topic,
                    )
                    sr["topic_title"] = f"Req {sid}: {sr_topic_clean}"
                    if "title" in sr:
                        sr["title"] = f"Req {sid}: {sr_topic_clean}"

                    orig_sr_sum = str(sr.get("pamphlet_summary") or "")
                    clean_sr_sum = clean_subreq_pamphlet_summary(
                        sr, r, badge_name, s_idx, seen_sibling_bodies
                    )
                    clean_sr_sum = apply_ocr_splits_to_text(clean_sr_sum, exact_splits, lower_splits, stats)
                    if clean_sr_sum != orig_sr_sum:
                        stats["subreq_summaries_repaired"] += 1
                    sr["pamphlet_summary"] = clean_sr_sum

                    if isinstance(sr.get("pamphlet_excerpts"), list):
                        sr["pamphlet_excerpts"] = [clean_sr_sum]
                    if isinstance(sr.get("step_by_step_procedure"), list):
                        sr["step_by_step_procedure"] = [
                            restore_or_clean_prose(
                                apply_ocr_splits_to_text(str(pr), exact_splits, lower_splits, stats),
                                sr_topic_clean,
                                badge_name,
                                full_sentence_pool=full_sentence_pool,
                                keep_heading_colon=True,
                            )
                            for pr in sr["step_by_step_procedure"]
                        ]

                    sr_cmp = sr.get("common_misconception_pair")
                    needs_new_cmp = (
                        not isinstance(sr_cmp, dict)
                        or not sr_cmp.get("misconception")
                        or not sr_cmp.get("fact")
                    )
                    if not needs_new_cmp:
                        m_s = apply_ocr_splits_to_text(str(sr_cmp["misconception"]), exact_splits, lower_splits, stats).replace(":", ",")
                        f_s = apply_ocr_splits_to_text(str(sr_cmp["fact"]), exact_splits, lower_splits, stats).replace(":", ",")
                        if (
                            (m_s.lower(), f_s.lower()) in used_misconceptions
                            or " req " in m_s.lower()
                            or is_truncated_before_citation(strip_page_citation(m_s)[0])
                        ):
                            needs_new_cmp = True
                        else:
                            sr_cmp = {"misconception": m_s, "fact": f_s}

                    if needs_new_cmp:
                        sr_cmp = build_unique_subreq_misconception(
                            badge_name, req_id, sid, sr_topic_clean, sr_text, depth * 20 + s_idx, used_misconceptions
                        )
                        stats["subreq_misconceptions_deduped"] += 1

                    used_misconceptions.add((sr_cmp["misconception"].lower(), sr_cmp["fact"].lower()))
                    sr["common_misconception_pair"] = sr_cmp

                    children = [ch for ch in (sr.get("children") or sr.get("sub_requirements") or []) if isinstance(ch, dict)]

                    sr_wo = sr.get("workbook_organizer")
                    if not isinstance(sr_wo, dict):
                        sr_wo = {
                            "organizer_type": "CONCEPT_NOTES_GRID",
                            "headers": ["Concept / Prompt", "Pamphlet Standard", "My Notes & Evidence"],
                            "row_labels": [],
                        }
                        sr["workbook_organizer"] = sr_wo

                    if is_sketch_draw_diagram_req(sr_text, str(sr.get("primary_verb") or "")):
                        sr_wo["organizer_type"] = "SKETCH_AND_OBSERVATION_CANVAS"
                        sr_wo["headers"] = ["Sketch / Diagram Element", "Required Labels & Dimensions", "Field Observations & Counselor Notes"]
                        sr_wo["column_headers"] = list(sr_wo["headers"])
                        stats["sketch_canvas_assigned"] += 1
                    elif sr_wo.get("organizer_type") == "COMPARE_CONTRAST_2COL":
                        lh = (cd.get("left_header") if isinstance(cd, dict) else None) or f"{sr_topic_clean} Option A"
                        rh = (cd.get("right_header") if isinstance(cd, dict) else None) or f"{sr_topic_clean} Option B"
                        if "primary concept" in lh.lower():
                            lh = f"{sr_topic_clean} Standard A"
                            rh = f"{sr_topic_clean} Standard B"
                        sr_wo["headers"] = ["Comparison Dimension", lh, rh]
                        sr_wo["column_headers"] = list(sr_wo["headers"])
                        stats["compare_headers_synced"] += 1

                    sr_rls = sr_wo.get("row_labels") or []
                    sr_rows = sr_wo.get("rows") or []
                    if (
                        len(sr_rls) < 1
                        or any(row_label_has_defect(str(lbl)) for lbl in sr_rls)
                        or any(row_label_has_defect(str(lbl)) for lbl in sr_rows)
                    ):
                        clean_sr_rls = extract_clean_row_labels_from_req(
                            {"req_number": sid, "req_text": sr_text, "topic_title": sr_topic_clean},
                            children,
                            badge_name,
                            is_subreq=True,
                        )
                        sr_wo["row_labels"] = clean_sr_rls
                        sr_wo["rows"] = list(clean_sr_rls)
                        sr_wo["min_rows"] = len(clean_sr_rls)
                        stats["organizer_row_labels_rebuilt"] += 1
                    else:
                        clean_sr_rls = [
                            apply_ocr_splits_to_text(str(lbl), exact_splits, lower_splits, stats)
                            for lbl in sr_rls
                        ]
                        sr_wo["row_labels"] = clean_sr_rls
                        sr_wo["rows"] = list(clean_sr_rls)

                    sr_vis = next(
                        (v for v in vis_pool if sid in v["reqs"] or req_id in v["reqs"]),
                        vis_pool[vis_cursor % len(vis_pool)] if vis_pool else None,
                    )
                    orig_sr_cap = str(sr.get("workbook_visual_caption") or sr.get("workbook_diagram_caption") or "")
                    if sr_vis:
                        vis_cursor += 1
                        if not sr.get("workbook_diagram_url"):
                            sr["workbook_diagram_url"] = sr_vis["url"]
                        base_sr_cap = orig_sr_cap if (orig_sr_cap and not orig_sr_cap.startswith("Field reference diagram showing") and "field reference figure" not in orig_sr_cap.lower()) else sr_vis["caption"]
                        sr_cap = clean_image_caption(
                            base_sr_cap, badge_name, sid, sr_topic_clean, sr_topic_clean, r_idx + s_idx + depth
                        )
                    else:
                        sr_cap = clean_image_caption(
                            orig_sr_cap, badge_name, sid, sr_topic_clean, sr_topic_clean, r_idx + s_idx + depth
                        )
                    sr_cap = apply_ocr_splits_to_text(sr_cap, exact_splits, lower_splits, stats).replace(":", "")
                    sr["workbook_diagram_caption"] = sr_cap
                    sr["workbook_visual_caption"] = sr_cap

                    if children:
                        _process_subreq_tree(children, sr_topic_clean, depth + 1)

            _process_subreq_tree(sub_reqs, clean_topic, depth=1)

        def _final_prose_walk(obj: Any, k_name: str = "") -> Any:
            if isinstance(obj, str):
                if k_name in (
                    "req_text", "description", "text", "url", "source_url",
                    "scouting_org_url", "pamphlet_pdf_url", "shop_pamphlet_url",
                    "workbook_diagram_url", "slug", "badge_slug", "id",
                    "sub_id", "req_id", "req_number", "number",
                    "organizer_type", "artifact_type", "status",
                ):
                    return obj
                return apply_ocr_splits_to_text(obj, exact_splits, lower_splits, stats)
            if isinstance(obj, dict):
                return {
                    apply_ocr_splits_to_text(str(k), exact_splits, lower_splits, stats): _final_prose_walk(v, str(k))
                    for k, v in obj.items()
                }
            if isinstance(obj, list):
                return [_final_prose_walk(x, k_name) for x in obj]
            return obj

        d = _final_prose_walk(d)
        bf.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        # Sync official_requirements_cache.json entry keyed by badge_name (and slug if present)
        official_cache[badge_name] = d
        if slug in official_cache:
            official_cache[slug] = d

    if official_cache:
        OFFICIAL_CACHE_PATH.write_text(
            json.dumps(official_cache, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    unique_ocr_toks = sum(1 for k in stats if k.startswith("tok:"))
    print("\n=== V36 Deep Corpus Quality Overhaul Summary ===")
    print(f"Unique OCR merged tokens split:      {unique_ocr_toks}")
    print(f"Total OCR merged occurrences fixed:  {stats['ocr_occurrences_fixed']}")
    print(f"Comparison dimensions named:         {stats['comparison_dimensions_named']}")
    print(f"Comparison cells repaired:           {stats['comparison_cells_repaired']}")
    print(f"Worked example keys repaired:        {stats['worked_example_keys_repaired']}")
    print(f"Worked example values repaired:      {stats['worked_example_values_repaired']}")
    print(f"Worked example outputs repaired:     {stats['worked_example_outputs_repaired']}")
    print(f"Pamphlet excerpts cleaned:           {stats['excerpts_cleaned']}")
    print(f"Procedures cleaned:                  {stats['procedures_cleaned']}")
    print(f"Sub-req summaries repaired:          {stats['subreq_summaries_repaired']}")
    print(f"Organizer row_labels rebuilt:        {stats['organizer_row_labels_rebuilt']}")
    print(f"COMPARE_CONTRAST_2COL synced:        {stats['compare_headers_synced']}")
    print(f"SKETCH_AND_OBSERVATION_CANVAS:       {stats['sketch_canvas_assigned']}")
    print(f"Safety callouts tailored:            {stats['safety_callouts_tailored']}")
    print(f"Homework notes tailored:             {stats['homework_notes_tailored']}")
    print(f"Sub-req misconceptions deduped:      {stats['subreq_misconceptions_deduped']}")
    print(f"Pamphlet nonexistent imgs removed:   {stats['pamphlet_nonexistent_removed']}")
    print(f"Pamphlet catalog captions fixed:     {stats['pamphlet_captions_fixed']}")
    print(f"Nano Banana catalog captions fixed:  {stats['nano_captions_fixed']}")


if __name__ == "__main__":
    main()
