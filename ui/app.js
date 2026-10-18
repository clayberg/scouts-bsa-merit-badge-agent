/**
 * Scouts BSA Merit Badge Counselor Workbench Client (`ui/app.js`)
 *
 * Provides:
 * - Full 144-Badge Catalog search, category filter, and Eagle-Required / Elective filter
 * - Clean research & slide deck generation progress via SSE (`/api/workflow/stream`)
 * - Interactive Slide Deck Preview (including Cover Slide 1 with badge patch & pamphlet cover,
 *   plus all requirement & topic teaching slides)
 * - Direct links to the Official BSA Merit Badge Pamphlet & Digital Resource Guide
 * - One-click downloads for PowerPoint (`.pptx`) and Scout Workbook (`.md`)
 */

const COUNSELOR_STORAGE_KEY = "scouts_bsa_counselor_profile_v1";
const BLUECARD_STORAGE_PREFIX = "scouts_bsa_bluecard_roster_v1_";

const state = {
  badges: [],
  filteredBadges: [],
  categories: [],
  currentBadge: "First Aid",
  currentResult: null,
  customLogoPath: null,
  customLogoUrl: null,
  // activeSlideIdx: -1 represents Slide 1 (Cover Slide), 0..N-1 represent storyboard.slides[0..N-1]
  activeSlideIdx: -1,
  combinedSlideImages: [],
  constructionConcept: "iso_heavy",
  constructionFrameIdx: 0,
  constructionPlaying: true,
  constructionTimerId: null,
  constructionManualPreview: false,
  filmstripQuery: "",
  deckConfigDirty: false,
  activeUnderstageTab: "notes",
  presenterFontScale: 0.90,
  revealedQuizSlides: new Set(),
  checkedGearItems: new Set(),
};

const CONSTRUCTION_ANIM_CONCEPTS = {
  iso_heavy: {
    label: "3D Isometric Heavy Equipment Crew",
    frames: [
      {
        src: "/assets/construction_anim/iso_heavy_1_blueprint.jpg",
        title: "Step 1: Unrolling the 16:9 Slide Blueprint & Clearing the Foundation",
        desc: "Miniature Scouts inspect the 12-archetype slide blueprint on sawhorses while the yellow mini-bulldozer levels the platform and the Merit Badge emblem rests on the ground.",
        emblemSlot: {
          left: "55.5%",
          top: "76.5%",
          width: "8.4%",
          imgTransform: "scaleY(0.57) rotate(-28deg)",
          imgFilter: "drop-shadow(0 2px 0 rgba(148, 120, 80, 0.85)) drop-shadow(0 4px 6px rgba(15, 23, 42, 0.28))",
        },
      },
      {
        src: "/assets/construction_anim/iso_heavy_2_header_crane.jpg",
        title: "Step 2: Mobile Tower Crane Hoisting the Navy & Gold Header Beam",
        desc: "A Scout crane operator hoists the glossy Scouts BSA navy-and-gold title header bar onto the upright 16:9 frame while the badge emblem waits in the staging area.",
        emblemSlot: {
          left: "84.5%",
          top: "62.0%",
          width: "8.4%",
          imgTransform: "scaleY(0.57) rotate(-28deg)",
          imgFilter: "drop-shadow(0 2px 0 rgba(148, 120, 80, 0.85)) drop-shadow(0 4px 6px rgba(15, 23, 42, 0.28))",
        },
      },
      {
        src: "/assets/construction_anim/iso_heavy_3_forklift_cards.jpg",
        title: "Step 3: Mini-Forklift & Scissor-Lift Stacking Rounded Teaching Cards",
        desc: "Scouts drive a yellow mini-forklift and scissor-lift to mount rounded-corner teaching cards while the badge emblem waits on the ground for airlift.",
        emblemSlot: {
          left: "78.5%",
          top: "73.5%",
          width: "8.4%",
          imgTransform: "scaleY(0.57) rotate(-28deg)",
          imgFilter: "drop-shadow(0 2px 0 rgba(148, 120, 80, 0.85)) drop-shadow(0 4px 6px rgba(15, 23, 42, 0.28))",
        },
      },
      {
        src: "/assets/construction_anim/iso_heavy_4_helicopter_emblem.jpg",
        title: "Step 4: Twin-Rotor Cargo Helicopter Hoisting the Merit Badge Emblem",
        desc: "A yellow Scout cargo helicopter hoists the transparent Merit Badge emblem in a horizontal golden ring toward the upper-right header slot, guided by signal batons.",
        emblemSlot: {
          left: "75.2%",
          top: "51.1%",
          width: "6.9%",
          imgTransform: "scaleY(0.44) rotate(-16deg)",
          imgFilter: "drop-shadow(0 1.5px 0 rgba(180, 140, 45, 0.85)) drop-shadow(0 3px 5px rgba(15, 23, 42, 0.26))",
          floating: true,
        },
      },
      {
        src: "/assets/construction_anim/iso_heavy_5_scaffold_paint.jpg",
        title: "Step 5: Emblem Mounted in Place & Scaffolding Crew Airbrushing Hero Art",
        desc: "With the Merit Badge emblem now mounted in the isometric header ring, Scout artists on timber scaffolding airbrush the outdoor hero graphic into the right visual card.",
        emblemSlot: {
          left: "64.5%",
          top: "13.95%",
          width: "5.1%",
          imgTransform: "skewY(-12deg) scaleX(0.83)",
          imgFilter: "drop-shadow(-1.5px 1.5px 2px rgba(15, 23, 42, 0.32))",
        },
      },
      {
        src: "/assets/construction_anim/iso_heavy_6_inspect_reveal.jpg",
        title: "Step 6: Senior Patrol Leader Conformance Inspection & Spotlight Reveal",
        desc: "A Scout Inspector with a brass magnifying glass and green checkmark clipboard verifies zero text overlaps as camp spotlights reveal the finished slide!",
        emblemSlot: {
          left: "71.65%",
          top: "15.4%",
          width: "6.7%",
          imgTransform: "none",
          imgFilter: "drop-shadow(0 3px 8px rgba(15, 23, 42, 0.28))",
        },
      },
    ],
  },
  camp_pioneer: {
    label: "2D Camp Pioneering & Timber Rig",
    frames: [
      {
        src: "/assets/construction_anim/camp_pioneer_1_lashings.jpg",
        title: "Step 1: Tying Square & Diagonal Hemp Lashings on the 16:9 Timber Frame",
        desc: "At a pine forest campsite, the patrol ties authentic square and diagonal hemp rope lashings on pine spars to erect the 16:9 slide frame.",
        emblemSlot: { left: "87.12%", top: "22.58%", width: "12.2%" },
      },
      {
        src: "/assets/construction_anim/camp_pioneer_2_pulley_hoist.jpg",
        title: "Step 2: Block-and-Tackle Pulley Hoisting the Canvas Screen & Cards",
        desc: "Scouts haul hemp ropes through an A-frame pulley rig to hoist the crisp canvas projection screen and carved wooden teaching cards.",
        emblemSlot: { left: "87.12%", top: "22.58%", width: "12.2%" },
      },
      {
        src: "/assets/construction_anim/camp_pioneer_3_field_sketch.jpg",
        title: "Step 3: Ladder Scaffold Field Sketching & Laurel Medallion Mounting",
        desc: "A Scout artist on a lashed ladder paints the outdoor landscape on the canvas screen while another Scout secures the upper-right badge medallion.",
        emblemSlot: { left: "87.12%", top: "22.58%", width: "12.2%" },
      },
      {
        src: "/assets/construction_anim/camp_pioneer_4_campfire_premiere.jpg",
        title: "Step 4: Campfire Twilight Premiere with Brass Camp-Lantern Projector",
        desc: "As twilight falls, a brass camp-lantern projector illuminates the completed timber-framed slide deck while the patrol salutes around the campfire.",
        emblemSlot: { left: "87.12%", top: "22.50%", width: "12.1%" },
      },
    ],
  },
  clay_workshop: {
    label: "3D Claymation 'Slide-O-Matic' Lodge Workshop",
    frames: [
      {
        src: "/assets/construction_anim/clay_workshop_1_pamphlet_feed.jpg",
        title: "Step 1: Feeding Official Pamphlets into the Brass Slide-O-Matic Hopper",
        desc: "Inside a cozy log-cabin workshop, claymation Scouts feed official Merit Badge pamphlets and compasses into the brass-and-oak Slide-O-Matic machine.",
        emblemSlot: { left: "85.5%", top: "18.4%", width: "11.2%" },
      },
      {
        src: "/assets/construction_anim/clay_workshop_2_card_stamper.jpg",
        title: "Step 2: Articulated Wooden Arms Stamping Rounded Teaching Cards",
        desc: "Mechanical wooden arms stamp colorful felt-and-wood teaching cards onto a brass conveyor belt and arrange them into the slide grid.",
        emblemSlot: { left: "85.5%", top: "18.4%", width: "11.2%" },
      },
      {
        src: "/assets/construction_anim/clay_workshop_3_nano_banana_dome.jpg",
        title: "Step 3: Glowing Nano Banana Energy Dome Projecting the Hero Scene",
        desc: "A glass dome powered by a glowing golden Nano Banana core projects a 3D outdoor diorama onto the right half of the slide board.",
        emblemSlot: { left: "85.5%", top: "18.4%", width: "11.2%" },
      },
      {
        src: "/assets/construction_anim/clay_workshop_4_ribbon_cut.jpg",
        title: "Step 4: Giant Brass Scissors Ceremonial Red-Ribbon Cutting",
        desc: "Claymation Scouts in campaign hats cut a ceremonial red ribbon across the finished 16:9 slide deck with giant brass scissors amidst confetti!",
        emblemSlot: { left: "85.5%", top: "18.4%", width: "11.2%" },
      },
    ],
  },
};

function badgeNameToEmblemSlug(badgeName) {
  return String(badgeName || "First Aid")
    .trim()
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function updateConstructionBadgeEmblem(badgeName) {
  const cleanName = badgeName || state.currentBadge || "First Aid";
  const slug = badgeNameToEmblemSlug(cleanName);
  const emblemUrl = `/assets/badge_emblems/${slug}.png?v=20261016c`;
  const overlayImg = document.getElementById("construction-badge-emblem-overlay");
  const workorderImg = document.getElementById("construction-workorder-emblem");
  const workorderTitle = document.getElementById("construction-workorder-title");
  const stageHeading = document.getElementById("construction-stage-heading");
  if (overlayImg) {
    overlayImg.src = emblemUrl;
    overlayImg.alt = `${cleanName} Merit Badge Emblem`;
  }
  if (workorderImg) {
    workorderImg.src = emblemUrl;
    workorderImg.alt = `${cleanName} Merit Badge Emblem`;
  }
  if (workorderTitle) {
    workorderTitle.textContent = `${cleanName} Merit Badge`;
  }
  if (stageHeading) {
    stageHeading.textContent = state.constructionManualPreview
      ? `Scout Slide Construction Showcase — ${cleanName} Merit Badge`
      : `Building ${cleanName} Merit Badge Slide Deck...`;
  }
}

const CONSTRUCTION_CONCEPT_ORDER = ["iso_heavy", "camp_pioneer", "clay_workshop"];
const CONSTRUCTION_PRELOADED_IMAGES = new Map();

function preloadConstructionAnimationFrames() {
  for (const conceptKey of CONSTRUCTION_CONCEPT_ORDER) {
    const concept = CONSTRUCTION_ANIM_CONCEPTS[conceptKey];
    if (!concept || !Array.isArray(concept.frames)) continue;
    for (const frame of concept.frames) {
      if (!frame.src || CONSTRUCTION_PRELOADED_IMAGES.has(frame.src)) continue;
      const preImg = new Image();
      preImg.decoding = "async";
      preImg.loading = "eager";
      preImg.src = frame.src;
      if (typeof preImg.decode === "function") {
        preImg.decode().catch(() => {});
      }
      CONSTRUCTION_PRELOADED_IMAGES.set(frame.src, preImg);
    }
  }
}

// Kick off proactive frame preloading immediately upon script evaluation
preloadConstructionAnimationFrames();

function syncConstructionConceptButtons(activeConcept) {
  document.querySelectorAll(".m3-construction-concept-btn").forEach((b) => {
    b.classList.toggle("active", b.getAttribute("data-concept") === activeConcept);
  });
}

function renderConstructionFrame(frameIdx, autoCycleConcept = true) {
  let currentConceptKey = state.constructionConcept || "iso_heavy";
  let conceptObj = CONSTRUCTION_ANIM_CONCEPTS[currentConceptKey] || CONSTRUCTION_ANIM_CONCEPTS.iso_heavy;
  let frames = conceptObj.frames;
  let safeIdx = frameIdx;

  if (autoCycleConcept && (frameIdx >= frames.length || frameIdx < 0)) {
    const curConceptIdx = Math.max(0, CONSTRUCTION_CONCEPT_ORDER.indexOf(currentConceptKey));
    if (frameIdx >= frames.length) {
      const nextConceptIdx = (curConceptIdx + 1) % CONSTRUCTION_CONCEPT_ORDER.length;
      currentConceptKey = CONSTRUCTION_CONCEPT_ORDER[nextConceptIdx];
      state.constructionConcept = currentConceptKey;
      conceptObj = CONSTRUCTION_ANIM_CONCEPTS[currentConceptKey];
      frames = conceptObj.frames;
      safeIdx = 0;
      syncConstructionConceptButtons(currentConceptKey);
    } else if (frameIdx < 0) {
      const prevConceptIdx = (curConceptIdx - 1 + CONSTRUCTION_CONCEPT_ORDER.length) % CONSTRUCTION_CONCEPT_ORDER.length;
      currentConceptKey = CONSTRUCTION_CONCEPT_ORDER[prevConceptIdx];
      state.constructionConcept = currentConceptKey;
      conceptObj = CONSTRUCTION_ANIM_CONCEPTS[currentConceptKey];
      frames = conceptObj.frames;
      safeIdx = frames.length - 1;
      syncConstructionConceptButtons(currentConceptKey);
    }
  } else {
    safeIdx = ((frameIdx % frames.length) + frames.length) % frames.length;
  }

  state.constructionFrameIdx = safeIdx;
  const frame = frames[safeIdx];

  const imgEl = document.getElementById("construction-frame-img");
  const slotEl = document.getElementById("construction-emblem-slot");
  const overlayImgEl = document.getElementById("construction-badge-emblem-overlay");
  const fgCableEl = document.getElementById("construction-foreground-cable-overlay");
  const titleEl = document.getElementById("construction-step-title");
  const descEl = document.getElementById("construction-step-desc");
  const counterEl = document.getElementById("construction-frame-counter");
  const dotsEl = document.getElementById("construction-frame-dots");

  const applyFrameAndEmblem = () => {
    if (imgEl && imgEl.getAttribute("src") !== frame.src) {
      imgEl.src = frame.src;
    }
    if (slotEl && frame.emblemSlot) {
      slotEl.style.left = frame.emblemSlot.left;
      slotEl.style.top = frame.emblemSlot.top;
      slotEl.style.width = frame.emblemSlot.width;
      if (overlayImgEl) {
        overlayImgEl.style.transform = frame.emblemSlot.imgTransform || "none";
        overlayImgEl.style.filter = frame.emblemSlot.imgFilter || "";
      }
    }
    if (fgCableEl) {
      const isHelicopterHoistFrame =
        currentConceptKey === "iso_heavy" &&
        (safeIdx === 3 || String(frame.src || "").includes("iso_heavy_4_helicopter_emblem"));
      fgCableEl.classList.toggle("hidden", !isHelicopterHoistFrame);
    }
    imgEl?.classList.remove("fade-step");
  };

  let preloaded = CONSTRUCTION_PRELOADED_IMAGES.get(frame.src);
  if (!preloaded) {
    preloaded = new Image();
    preloaded.src = frame.src;
    CONSTRUCTION_PRELOADED_IMAGES.set(frame.src, preloaded);
  }

  if (imgEl && imgEl.getAttribute("src") !== frame.src) {
    if (preloaded.complete && preloaded.naturalWidth > 0) {
      applyFrameAndEmblem();
    } else {
      preloaded.addEventListener("load", applyFrameAndEmblem, { once: true });
      preloaded.addEventListener("error", applyFrameAndEmblem, { once: true });
    }
  } else {
    applyFrameAndEmblem();
  }

  if (titleEl) titleEl.textContent = frame.title;
  if (descEl) descEl.textContent = frame.desc;
  if (counterEl) {
    const animNum = CONSTRUCTION_CONCEPT_ORDER.indexOf(currentConceptKey) + 1;
    counterEl.textContent = `Animation ${animNum}/${CONSTRUCTION_CONCEPT_ORDER.length} • Frame ${safeIdx + 1}/${frames.length} (Auto-Cycle)`;
  }

  if (dotsEl) {
    dotsEl.innerHTML = "";
    frames.forEach((_f, idx) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `m3-construction-dot${idx === safeIdx ? " active" : ""}`;
      btn.textContent = String(idx + 1);
      btn.title = `Jump to Frame ${idx + 1}`;
      btn.addEventListener("click", () => {
        renderConstructionFrame(idx, false);
      });
      dotsEl.appendChild(btn);
    });
  }
}

function startConstructionAnimationTimer() {
  if (state.constructionTimerId) {
    clearInterval(state.constructionTimerId);
    state.constructionTimerId = null;
  }
  if (!state.constructionPlaying) return;
  state.constructionTimerId = setInterval(() => {
    const stageEl = document.getElementById("slide-construction-stage");
    if (!stageEl || stageEl.classList.contains("hidden")) return;
    renderConstructionFrame(state.constructionFrameIdx + 1);
  }, 2100);
}

function showConstructionAnimationStage(badgeName, isManualPreview = false) {
  state.constructionManualPreview = Boolean(isManualPreview);
  updateConstructionBadgeEmblem(badgeName || state.currentBadge);
  const animStage = document.getElementById("slide-construction-stage");
  const closeBtn = document.getElementById("btn-close-construction-anim");
  const statusPill = document.getElementById("construction-status-pill");
  const toolbarEl = document.getElementById("slide-stage-toolbar");
  const reqJumpEl = document.getElementById("req-quick-jump-bar");
  const slideStageEl = document.getElementById("widescreen-slide-stage");
  const understageDrawerEl = document.getElementById("understage-drawer");
  const codesignEl = document.getElementById("slide-codesign-bar");
  const notesCardEl = document.getElementById("slide-speaker-notes-card");
  const filmstripToolbarEl = document.getElementById("filmstrip-toolbar");

  animStage?.classList.remove("hidden");
  if (closeBtn) {
    closeBtn.classList.toggle("hidden", !isManualPreview && !state.currentResult);
  }
  if (statusPill) {
    statusPill.textContent = isManualPreview ? "🎬 INTERACTIVE ANIMATION SHOWCASE" : "🏗️ SCOUT SLIDE CREW AT WORK";
  }
  toolbarEl?.classList.add("hidden");
  reqJumpEl?.classList.add("hidden");
  slideStageEl?.classList.add("hidden");
  understageDrawerEl?.classList.add("hidden");
  codesignEl?.classList.add("hidden");
  notesCardEl?.classList.add("hidden");
  filmstripToolbarEl?.classList.add("hidden");

  renderConstructionFrame(state.constructionFrameIdx);
  startConstructionAnimationTimer();
}

function hideConstructionAnimationStage() {
  state.constructionManualPreview = false;
  const animStage = document.getElementById("slide-construction-stage");
  const toolbarEl = document.getElementById("slide-stage-toolbar");
  const reqJumpEl = document.getElementById("req-quick-jump-bar");
  const slideStageEl = document.getElementById("widescreen-slide-stage");
  const understageDrawerEl = document.getElementById("understage-drawer");
  const notesCardEl = document.getElementById("slide-speaker-notes-card");
  const filmstripToolbarEl = document.getElementById("filmstrip-toolbar");

  animStage?.classList.add("hidden");
  toolbarEl?.classList.remove("hidden");
  reqJumpEl?.classList.remove("hidden");
  slideStageEl?.classList.remove("hidden");
  understageDrawerEl?.classList.remove("hidden");
  notesCardEl?.classList.remove("hidden");
  filmstripToolbarEl?.classList.remove("hidden");
  syncUnderstageDrawerVisibility(state.activeSlideIdx);
  if (state.constructionTimerId) {
    clearInterval(state.constructionTimerId);
    state.constructionTimerId = null;
  }
}

function syncUnderstageDrawerVisibility(slideIdx = state.activeSlideIdx) {
  const activeTab = state.activeUnderstageTab || "notes";
  const notesCard = document.getElementById("slide-speaker-notes-card");
  const codesignCard = document.getElementById("slide-codesign-bar");
  const quickeditCard = document.getElementById("slide-quick-edit-card");

  document.querySelectorAll("[data-understage-tab]").forEach((btn) => {
    const t = btn.getAttribute("data-understage-tab");
    btn.classList.toggle("active", t === activeTab);
  });

  notesCard?.classList.toggle("hidden", activeTab !== "notes");
  // On Cover Slide (-1), if Customize or Quick Edit is selected, still allow viewing or hide if cover
  if (slideIdx === -1 && activeTab !== "notes") {
    codesignCard?.classList.toggle("hidden", activeTab !== "codesign");
    quickeditCard?.classList.toggle("hidden", activeTab !== "quickedit");
  } else {
    codesignCard?.classList.toggle("hidden", activeTab !== "codesign");
    quickeditCard?.classList.toggle("hidden", activeTab !== "quickedit");
  }
}

function syncCounselorProfileSummary() {
  const cName = (document.getElementById("input-counselor-name")?.value || "Scoutmaster Bob").trim();
  const tName = (document.getElementById("input-troop-name")?.value || "Troop 123, My Council").trim();
  const summaryText = `${cName} • ${tName}`;
  const sidebarSumEl = document.getElementById("sidebar-profile-summary-text");
  const topChipEl = document.getElementById("top-counselor-chip-text");
  if (sidebarSumEl) sidebarSumEl.textContent = summaryText;
  if (topChipEl) topChipEl.textContent = summaryText;
}

function formatSlideThemeLabel(tierCode) {
  const upper = String(tierCode || "BEAUTIFIED").toUpperCase();
  if (upper === "STANDARD" || upper === "CRISP_WHITE" || upper === "CRISP WHITE") return "Crisp White";
  if (upper === "STUDIO" || upper === "DARK_SLATE" || upper === "DARK SLATE") return "Dark Slate";
  return "Warm Cream";
}

function markDeckConfigDirty() {
  state.deckConfigDirty = true;
  const dirtyBanner = document.getElementById("deck-dirty-banner");
  const genBtn = document.getElementById("btn-generate-deck");
  dirtyBanner?.classList.remove("hidden");
  if (genBtn && !genBtn.disabled) {
    genBtn.classList.add("m3-btn-dirty-pulse");
    genBtn.innerHTML = '<span class="material-symbols-outlined">autorenew</span> Update Slide Deck &amp; Workbook';
  }
  // Live-update Visual Polish & Asset Mode preview in sidebar before running
  const tierVal = document.getElementById("beautification-select")?.value || "BEAUTIFIED";
  const depthVal = document.getElementById("depth-select")?.value || "Deep Dive / Camp School Deck";
  const isDeep = depthVal.toLowerCase().includes("deep");
  const finopsUsdEl = document.getElementById("finops-cost-usd");
  const finopsMetaEl = document.getElementById("finops-cost-meta");
  if (finopsUsdEl) {
    finopsUsdEl.innerHTML =
      tierVal === "STANDARD"
        ? `<strong>Visual Assets:</strong> Pamphlet Figures Only (Lightweight)`
        : `<strong>Visual Assets:</strong> 100% Pre-Cached (8-Bit PNG)`;
  }
  if (finopsMetaEl) {
    finopsMetaEl.textContent = `${formatSlideThemeLabel(tierVal)} • ${isDeep ? "Deep Dive" : "Standard"}`;
  }
}

function clearDeckConfigDirty() {
  state.deckConfigDirty = false;
  const dirtyBanner = document.getElementById("deck-dirty-banner");
  const genBtn = document.getElementById("btn-generate-deck");
  dirtyBanner?.classList.add("hidden");
  genBtn?.classList.remove("m3-btn-dirty-pulse");
}

function bindConstructionAnimationControls() {
  document.querySelectorAll(".m3-construction-concept-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const concept = btn.getAttribute("data-concept") || "iso_heavy";
      state.constructionConcept = concept;
      state.constructionFrameIdx = 0;
      document.querySelectorAll(".m3-construction-concept-btn").forEach((b) => {
        b.classList.toggle("active", b.getAttribute("data-concept") === concept);
      });
      renderConstructionFrame(0);
      startConstructionAnimationTimer();
    });
  });

  document.getElementById("btn-construction-prev")?.addEventListener("click", () => {
    renderConstructionFrame(state.constructionFrameIdx - 1);
  });

  document.getElementById("btn-construction-next")?.addEventListener("click", () => {
    renderConstructionFrame(state.constructionFrameIdx + 1);
  });

  const playPauseBtn = document.getElementById("btn-construction-playpause");
  playPauseBtn?.addEventListener("click", () => {
    state.constructionPlaying = !state.constructionPlaying;
    playPauseBtn.textContent = state.constructionPlaying ? "⏸" : "▶";
    if (state.constructionPlaying) {
      startConstructionAnimationTimer();
    } else if (state.constructionTimerId) {
      clearInterval(state.constructionTimerId);
      state.constructionTimerId = null;
    }
  });

  document.getElementById("btn-toggle-construction-anim")?.addEventListener("click", () => {
    showConstructionAnimationStage(state.currentBadge, true);
  });

  document.getElementById("btn-close-construction-anim")?.addEventListener("click", () => {
    if (state.currentResult) {
      hideConstructionAnimationStage();
      renderActiveSlide(state.activeSlideIdx);
    }
  });

  renderConstructionFrame(0);
  startConstructionAnimationTimer();
}

document.addEventListener("DOMContentLoaded", async () => {
  bindNavigationTabs();
  bindConstructionAnimationControls();
  await loadCachedCounselorProfile();
  syncCounselorProfileSummary();
  bindFilterAndSlideControls();
  bindImageStudioModal();
  bindEnhancedWorkbenchAndAdminFeatures();
  await loadBadgesCatalog();
  await executeStreamingWorkflow("First Aid");
});

async function loadCachedCounselorProfile() {
  let prof = null;
  try {
    const raw = window.localStorage.getItem(COUNSELOR_STORAGE_KEY);
    if (raw) {
      prof = JSON.parse(raw);
    }
  } catch (_e) {
    // ignore storage read error
  }
  try {
    const serverProf = await fetch("/api/counselor-profile").then((r) => r.json());
    if (serverProf && serverProf.cached_locally) {
      prof = { ...(prof || {}), ...serverProf };
    }
  } catch (_e) {
    // ignore offline
  }
  if (!prof) return;
  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el && typeof val === "string") el.value = val;
  };
  setVal("input-counselor-name", prof.counselor_name || "Scoutmaster Bob");
  setVal("input-troop-name", prof.troop_affiliation || "Troop 123, My Council");
  setVal("input-counselor-location", prof.location_or_zip || "");
  setVal("input-counselor-email", prof.email_address || "counselor@troop123.org");
  setVal("input-counselor-phone", prof.phone_number || "(000) 555-1234");
  if (prof.custom_troop_logo_path) {
    state.customLogoPath = prof.custom_troop_logo_path;
  }
  syncCounselorProfileSummary();
}

async function saveCachedCounselorProfile() {
  syncCounselorProfileSummary();
  const payload = {
    counselor_name: document.getElementById("input-counselor-name")?.value || "Scoutmaster Bob",
    troop_affiliation: document.getElementById("input-troop-name")?.value || "Troop 123, My Council",
    location_or_zip: document.getElementById("input-counselor-location")?.value || "",
    email_address: document.getElementById("input-counselor-email")?.value || "",
    phone_number: document.getElementById("input-counselor-phone")?.value || "",
    custom_troop_logo_path: state.customLogoPath || null,
  };
  try {
    window.localStorage.setItem(COUNSELOR_STORAGE_KEY, JSON.stringify(payload));
  } catch (_e) {
    // ignore storage write error
  }
  try {
    await fetch("/api/counselor-profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (_e) {
    // ignore network error
  }
}

async function resetCachedCounselorProfile() {
  try {
    window.localStorage.removeItem(COUNSELOR_STORAGE_KEY);
  } catch (_e) {
    // ignore
  }
  try {
    await fetch("/api/counselor-profile", { method: "DELETE" });
  } catch (_e) {
    // ignore
  }
  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val;
  };
  setVal("input-counselor-name", "Scoutmaster Bob");
  setVal("input-troop-name", "Troop 123, My Council");
  setVal("input-counselor-location", "");
  setVal("input-counselor-email", "counselor@troop123.org");
  setVal("input-counselor-phone", "(000) 555-1234");
  state.customLogoPath = null;
  state.customLogoUrl = null;
  const logoStatus = document.getElementById("troop-logo-status");
  if (logoStatus) logoStatus.style.display = "none";
  syncCounselorProfileSummary();
  if (state.currentResult) {
    renderActiveSlide(state.activeSlideIdx);
    renderStudioKitAndParentLetter(state.currentResult);
  }
}

function switchMainTab(targetPanelId) {
  const tabBtns = document.querySelectorAll(".m3-tab-btn[data-panel]");
  const panels = ["panel-storyboard", "panel-triage", "panel-workbook", "panel-studiokit", "panel-admin"];
  tabBtns.forEach((b) => {
    b.classList.toggle("active", b.getAttribute("data-panel") === targetPanelId);
  });
  panels.forEach((pId) => {
    const el = document.getElementById(pId);
    if (el) {
      el.classList.toggle("hidden", pId !== targetPanelId);
    }
  });
  if (targetPanelId === "panel-admin") {
    loadAdminConsoleData();
  }
}

function bindNavigationTabs() {
  const tabBtns = document.querySelectorAll(".m3-tab-btn[data-panel]");
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.getAttribute("data-panel");
      if (target) switchMainTab(target);
    });
  });

  // Under-Stage 3-Tab Drawer (Teaching Notes | Customize Slide | Quick Edit)
  document.querySelectorAll("[data-understage-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabKey = btn.getAttribute("data-understage-tab") || "notes";
      state.activeUnderstageTab = tabKey;
      syncUnderstageDrawerVisibility(state.activeSlideIdx);
    });
  });
}

function bindFilterAndSlideControls() {
  const searchInput = document.getElementById("filter-search-input");
  const catSelect = document.getElementById("filter-category-select");
  const eagleSelect = document.getElementById("filter-eagle-select");

  searchInput?.addEventListener("input", () => applyBadgeFilters(false));
  catSelect?.addEventListener("change", () => applyBadgeFilters(false));
  eagleSelect?.addEventListener("change", () => applyBadgeFilters(false));

  // Collapsible Left Setup Sidebar toggle (updates label between "Hide Setup" and "Show Setup")
  const sidebarToggleBtn = document.getElementById("btn-toggle-sidebar");
  const sidebarToggleLabel = document.getElementById("label-toggle-sidebar");
  const sidebarToggleIcon = document.getElementById("icon-toggle-sidebar");
  const workbenchGrid = document.getElementById("main-workbench-grid");
  const syncSidebarToggleUi = (isCollapsed) => {
    if (sidebarToggleLabel) {
      sidebarToggleLabel.textContent = isCollapsed ? "Show Setup" : "Hide Setup";
    }
    if (sidebarToggleIcon) {
      sidebarToggleIcon.textContent = isCollapsed ? "left_panel_open" : "left_panel_close";
    }
    if (sidebarToggleBtn) {
      sidebarToggleBtn.title = isCollapsed
        ? "Show Setup Sidebar"
        : "Hide Setup Sidebar to Maximize Slide Stage";
    }
  };
  sidebarToggleBtn?.addEventListener("click", () => {
    if (!workbenchGrid) return;
    const isCollapsed = workbenchGrid.classList.toggle("sidebar-collapsed");
    syncSidebarToggleUi(isCollapsed);
    requestAnimationFrame(() => fitActiveSlideToStage());
  });

  // Collapsible Storyboard Filmstrip Outline toggle
  const filmstripToggleBtn = document.getElementById("btn-toggle-filmstrip");
  const storyboardLayout = document.getElementById("panel-storyboard");
  filmstripToggleBtn?.addEventListener("click", () => {
    if (!storyboardLayout) return;
    const isCollapsed = storyboardLayout.classList.toggle("filmstrip-collapsed");
    filmstripToggleBtn.textContent = isCollapsed ? "▶ Show Outline" : "◀ Hide Outline";
    requestAnimationFrame(() => fitActiveSlideToStage());
  });

  // Top-bar Counselor Profile Chip opens the sidebar Counselor Profile Accordion
  const topProfileChip = document.getElementById("top-counselor-profile-chip");
  const profileAccordion = document.getElementById("counselor-profile-accordion");
  const profileChevron = document.getElementById("profile-accordion-chevron");
  topProfileChip?.addEventListener("click", () => {
    workbenchGrid?.classList.remove("sidebar-collapsed");
    syncSidebarToggleUi(false);
    if (profileAccordion) {
      profileAccordion.open = true;
      profileAccordion.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });
  profileAccordion?.addEventListener("toggle", () => {
    if (profileChevron) {
      profileChevron.textContent = profileAccordion.open ? "Close ▴" : "Edit ▾";
    }
  });

  // Collapsible Progress Trace Details toggle
  const traceHeaderToggle = document.getElementById("trace-card-header-toggle");
  const traceToggleBtn = document.getElementById("btn-toggle-trace-details");
  const traceListEl = document.getElementById("agent-trace-list");
  traceHeaderToggle?.addEventListener("click", () => {
    if (!traceListEl) return;
    const isHidden = traceListEl.classList.toggle("hidden");
    if (traceToggleBtn) {
      traceToggleBtn.textContent = isHidden ? "Details ▾" : "Hide ▴";
    }
  });

  // Filmstrip keyword search filter
  const filmstripSearchInput = document.getElementById("filmstrip-search-input");
  filmstripSearchInput?.addEventListener("input", () => {
    state.filmstripQuery = (filmstripSearchInput.value || "").trim().toLowerCase();
    const slides = state.currentResult?.storyboard?.slides || [];
    renderFilmstrip(slides);
  });

  // Live-update Active Slide, Parent Letter, Local Troop Grounding & Cache whenever counselor contact inputs change
  ["input-counselor-name", "input-troop-name", "input-counselor-location", "input-counselor-email", "input-counselor-phone"].forEach((id) => {
    document.getElementById(id)?.addEventListener("input", () => {
      saveCachedCounselorProfile();
      if (state.currentResult) {
        renderActiveSlide(state.activeSlideIdx);
        renderStudioKitAndParentLetter(state.currentResult);
      }
    });
  });

  document.getElementById("btn-reset-counselor-cache")?.addEventListener("click", async () => {
    await resetCachedCounselorProfile();
  });

  document.getElementById("input-counselor-location")?.addEventListener("change", async () => {
    await saveCachedCounselorProfile();
    markDeckConfigDirty();
  });

  // Upload Optional Troop Custom Logo and live-render on Slide 1
  const logoInput = document.getElementById("input-troop-logo");
  const logoStatus = document.getElementById("troop-logo-status");
  logoInput?.addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    if (!file) {
      state.customLogoPath = null;
      state.customLogoUrl = null;
      if (logoStatus) logoStatus.style.display = "none";
      saveCachedCounselorProfile();
      if (state.activeSlideIdx === -1 && state.currentResult) {
        renderActiveSlide(-1);
      }
      return;
    }
    const reader = new FileReader();
    reader.onload = async () => {
      const dataUrl = String(reader.result || "");
      state.customLogoUrl = dataUrl;
      if (state.activeSlideIdx === -1 && state.currentResult) {
        renderActiveSlide(-1);
      }
      try {
        const resp = await fetch("/api/upload-logo", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filename: file.name, data_url: dataUrl }),
        }).then((r) => r.json());
        if (resp.status === "SUCCESS") {
          state.customLogoPath = resp.logo_path;
          state.customLogoUrl = resp.logo_url || dataUrl;
          await saveCachedCounselorProfile();
          if (logoStatus) {
            logoStatus.style.display = "flex";
            logoStatus.textContent = `✓ Uploaded: ${resp.filename || file.name}`;
          }
          if (state.activeSlideIdx === -1 && state.currentResult) {
            renderActiveSlide(-1);
          }
        }
      } catch (_err) {
        // Keep dataUrl preview active even if offline
      }
    };
    reader.readAsDataURL(file);
  });

  document.getElementById("btn-generate-deck")?.addEventListener("click", async () => {
    const badge = document.getElementById("badge-select")?.value || state.currentBadge;
    if (badge) {
      clearDeckConfigDirty();
      await executeStreamingWorkflow(badge);
    }
  });

  // Prevent accidental full-deck regeneration on dropdown changes; mark dirty & update FinOps preview
  ["depth-select", "beautification-select", "audience-select", "deep-research-checkbox"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", () => {
      markDeckConfigDirty();
    });
  });

  // Quick-Edit Slide Text & Notes Save Handler (rebuilds .pptx on disk)
  document.getElementById("btn-save-quickedit")?.addEventListener("click", async () => {
    if (!state.currentResult || state.activeSlideIdx < 0) return;
    const slides = state.currentResult.storyboard?.slides || [];
    const slide = slides[state.activeSlideIdx];
    if (!slide) return;

    const newTitle = (document.getElementById("quickedit-slide-title")?.value || "").trim();
    const newCaption = (document.getElementById("quickedit-slide-caption")?.value || "").trim();
    const rawBullets = (document.getElementById("quickedit-slide-bullets")?.value || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    const newNotes = (document.getElementById("quickedit-slide-notes")?.value || "").trim();

    if (newTitle) slide.title = newTitle;
    if (newCaption) slide.visual_caption = newCaption;
    if (rawBullets.length > 0) {
      slide.bullet_points = rawBullets;
      slide.full_bullet_points = rawBullets.slice();
    }
    slide.presenter_notes = newNotes;

    const saveBtn = document.getElementById("btn-save-quickedit");
    const statusEl = document.getElementById("quickedit-status-msg") || document.getElementById("quickedit-save-status");
    try {
      if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = "⏳ Saving & Rebuilding .pptx...";
      }
      const resp = await fetch("/api/slide/regenerate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: state.currentResult.badge_name,
          slide_index: state.activeSlideIdx,
          new_archetype: slide.archetype || "SPLIT_VISUAL_EXPLAINER",
          new_visual_theme: slide.visual_theme || "NUMBERED_STEP_CARDS",
          new_accent_palette: slide.accent_palette_key || "NAVY_GOLD",
          visual_source_mode: "keep_current",
          slide_data: slide,
          storyboard_slides: slides,
          counselor_info: state.currentResult.counselor_info || {},
          output_path: state.currentResult.output_path || "",
        }),
      }).then((r) => r.json());

      if (resp.pptx_download_url) {
        state.currentResult.pptx_download_url = resp.pptx_download_url;
        const pptxBtn = document.getElementById("btn-download-pptx");
        if (pptxBtn) pptxBtn.href = `${resp.pptx_download_url}?v=${Date.now()}`;
      }
      renderFilmstrip(slides);
      renderActiveSlide(state.activeSlideIdx);
      if (statusEl) {
        statusEl.textContent = "✅ Saved & Updated .pptx on Disk!";
        setTimeout(() => {
          statusEl.textContent = "";
        }, 3500);
      }
    } finally {
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.textContent = "💾 Save Slide Edits & Rebuild .PPTX";
      }
    }
  });

  const stageWrapper = document.getElementById("slide-stage-wrapper");
  const fsHud = document.getElementById("fullscreen-hud-bar");

  const setPresentationFullscreenMode = async (enable) => {
    if (!stageWrapper) return;
    hideConstructionAnimationStage();
    document.getElementById("widescreen-slide-stage")?.classList.remove("hidden");
    stageWrapper.classList.toggle("is-presenting-fullscreen", enable);
    fsHud?.classList.toggle("hidden", !enable);
    const fsBtn = document.getElementById("btn-present-fullscreen");
    if (fsBtn) {
      fsBtn.textContent = enable ? "✕ Exit Fullscreen" : "🖥️ Present Fullscreen";
    }
    // Use the deterministic full-viewport CSS theatre overlay (.is-presenting-fullscreen)
    // and exit native OS fullscreen if active so macOS Spaces never hijack Presenter View into a separate fullscreen space
    if (!enable) {
      try {
        if (document.fullscreenElement && document.exitFullscreen) {
          await document.exitFullscreen();
        }
      } catch (_e) {}
    }
    fitActiveSlideToStage();
    setTimeout(() => fitActiveSlideToStage(), 40);
  };

  document.getElementById("btn-present-fullscreen")?.addEventListener("click", async () => {
    const isNowActive = !stageWrapper?.classList.contains("is-presenting-fullscreen");
    await setPresentationFullscreenMode(isNowActive);
  });

  document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement && stageWrapper?.classList.contains("is-presenting-fullscreen")) {
      const openingPopupRecently =
        (presenterPopupWin && !presenterPopupWin.closed) ||
        Date.now() - (state._openingSecondMonitorPopupAt || 0) < 2500;
      if (openingPopupRecently) {
        // Keep CSS .is-presenting-fullscreen theatre mode active when 2nd Monitor popup opens
        return;
      }
      stageWrapper.classList.remove("is-presenting-fullscreen");
      fsHud?.classList.add("hidden");
      const fsBtn = document.getElementById("btn-present-fullscreen");
      if (fsBtn) fsBtn.textContent = "🖥️ Present Fullscreen";
    }
  });

  document.getElementById("btn-fs-prev")?.addEventListener("click", () => {
    document.getElementById("btn-prev-slide")?.click();
  });
  document.getElementById("btn-fs-next")?.addEventListener("click", () => {
    document.getElementById("btn-next-slide")?.click();
  });
  document.getElementById("btn-fs-exit")?.addEventListener("click", async () => {
    await setPresentationFullscreenMode(false);
  });

  // Keyboard Arrow Navigation (Left / Right / F for Fullscreen / Escape to exit)
  document.addEventListener("keydown", (ev) => {
    const tag = (ev.target?.tagName || "").toUpperCase();
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || ev.target?.isContentEditable) {
      return;
    }
    const modal = document.getElementById("image-studio-modal");
    if (modal && modal.classList.contains("open")) return;
    const storyboardPanel = document.getElementById("panel-storyboard");
    if (storyboardPanel && storyboardPanel.classList.contains("hidden")) return;

    if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      document.getElementById("btn-prev-slide")?.click();
    } else if (ev.key === "ArrowRight") {
      ev.preventDefault();
      document.getElementById("btn-next-slide")?.click();
    } else if (ev.key === "Escape" && stageWrapper?.classList.contains("is-presenting-fullscreen")) {
      ev.preventDefault();
      setPresentationFullscreenMode(false);
    } else if ((ev.key === "f" || ev.key === "F") && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
      ev.preventDefault();
      document.getElementById("btn-present-fullscreen")?.click();
    }
  });

  // F3, F4, F5, F6 Action Buttons (Copy, Email, Gmail, Print, Schedule Selector, Gear Multiplier, Blue Card)
  bindCounselorToolkitActions();

  document.getElementById("btn-apply-codesign")?.addEventListener("click", async () => {
    if (!state.currentResult || state.activeSlideIdx < 0) return;
    const slides = state.currentResult.storyboard?.slides || [];
    const slide = slides[state.activeSlideIdx];
    if (!slide) return;

    const newArch = document.getElementById("codesign-archetype-select")?.value || slide.archetype || "SPLIT_VISUAL_EXPLAINER";
    const newTheme = document.getElementById("codesign-theme-select")?.value || slide.visual_theme || "NUMBERED_STEP_CARDS";
    const newPalette = document.getElementById("codesign-palette-select")?.value || slide.accent_palette_key || "NAVY_GOLD";
    const rawSourceVal = document.getElementById("codesign-source-select")?.value || "keep_current";
    const visSourceMode =
      rawSourceVal === "none" || (newArch === "CONCEPT_TEXT_SLIDE" && rawSourceVal === "keep_current")
        ? "none"
        : rawSourceVal;
    const applyBtn = document.getElementById("btn-apply-codesign");

    try {
      if (applyBtn) {
        applyBtn.disabled = true;
        applyBtn.textContent = "⏳ Applying...";
      }
      const resp = await fetch("/api/slide/regenerate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: state.currentResult.badge_name,
          slide_index: state.activeSlideIdx,
          new_archetype: newArch,
          new_visual_theme: newTheme,
          new_accent_palette: newPalette,
          visual_source_mode: visSourceMode,
          slide_data: slide,
          storyboard_slides: slides,
          counselor_info: state.currentResult.counselor_info || {},
          output_path: state.currentResult.output_path || "",
        }),
      }).then((r) => r.json());

      slide.archetype = resp.new_archetype || (visSourceMode === "none" ? "CONCEPT_TEXT_SLIDE" : newArch);
      slide.visual_theme = newTheme;
      slide.accent_palette_key = newPalette;
      slide.beautification_tier =
        visSourceMode === "ai_hero"
          ? "STUDIO"
          : state.currentResult.beautification_tier === "STANDARD"
          ? "BEAUTIFIED"
          : state.currentResult.beautification_tier;

      if (visSourceMode === "none") {
        slide.diagram_url = null;
        slide.diagram_path = null;
        slide.ai_hero_image_path = null;
        slide.visual_source_label = "None (Full-Width Text Layout)";
        slide.callout_badge_text = `📄 ${newTheme.replace(/_/g, " ")} • ${newPalette} • Full-Width Text`;
        if (slide.full_bullet_points) {
          slide.bullet_points = slide.full_bullet_points.slice();
        }
      } else if (visSourceMode === "restore_original") {
        slide.diagram_url = resp.diagram_url || slide.original_diagram_url || null;
        slide.diagram_path = resp.diagram_path || slide.original_diagram_path || null;
        slide.ai_hero_image_path = null;
        slide.visual_caption = resp.visual_caption || slide.original_visual_caption || slide.title;
        slide.visual_source_label = resp.visual_source_label || slide.original_visual_source_label || "Official BSA Pamphlet / Wikimedia Figure";
        slide.callout_badge_text = `📐 ${newTheme.replace(/_/g, " ")} • ${newPalette} • Restored Original`;
      } else {
        if (resp.diagram_url) {
          slide.diagram_url = `${resp.diagram_url}${resp.diagram_url.includes("?") ? "&" : "?"}t=${Date.now()}`;
        }
        if (resp.diagram_path) {
          slide.diagram_path = resp.diagram_path;
        }
        if (visSourceMode === "ai_hero") {
          slide.ai_hero_image_path = resp.diagram_path || resp.diagram_url || "ai_hero";
          slide.visual_source_label = "EDGE Skill Concept Map (SlideBeautifierAgent)";
          slide.callout_badge_text = `✨ ${newTheme.replace(/_/g, " ")} • ${newPalette} • EDGE Concept Map`;
        } else {
          slide.ai_hero_image_path = null;
          slide.visual_source_label = resp.visual_source_label || slide.visual_source_label || "Official BSA Pamphlet / Wikimedia Figure";
          slide.callout_badge_text = `📐 ${newTheme.replace(/_/g, " ")} • ${newPalette}`;
        }
      }

      if (resp.updated_presenter_notes) {
        slide.presenter_notes = resp.updated_presenter_notes;
      }

      if (resp.pptx_download_url) {
        state.currentResult.pptx_download_url = resp.pptx_download_url;
        const pptxBtn = document.getElementById("btn-download-pptx");
        if (pptxBtn) pptxBtn.href = `${resp.pptx_download_url}?v=${Date.now()}`;
      }
      renderFilmstrip(slides);
      renderActiveSlide(state.activeSlideIdx);
    } finally {
      if (applyBtn) {
        applyBtn.disabled = false;
        applyBtn.textContent = "✨ Apply to Slide";
      }
    }
  });

  // Plan 6 Option C Layer 2: 1-Click AI Polish Script & Copy Script buttons
  document.getElementById("btn-copy-slide-notes")?.addEventListener("click", (ev) => {
    const btn = ev.currentTarget;
    const slides = state.currentResult?.storyboard?.slides || [];
    const activeNotes =
      state.activeSlideIdx === -1
        ? document.getElementById("stage-presenter-notes")?.innerText || ""
        : slides[state.activeSlideIdx]?.presenter_notes || "";
    copyTextWithFeedback(btn, activeNotes, "✅ Script Copied!");
  });

  function syncNotesPolishProvenancePill({
    isPolished = false,
    polishSource = "",
    cacheHit = false,
    fallbackReason = "",
    batchSuffix = "",
  } = {}) {
    const statusPill = document.getElementById("notes-polish-status-pill");
    const restoreBtn = document.getElementById("btn-restore-default-notes");
    if (restoreBtn) {
      restoreBtn.classList.toggle("hidden", !isPolished);
    }
    if (!statusPill) return;
    statusPill.classList.remove("is-gemini-flash", "is-studio-narrative");
    if (!isPolished) {
      statusPill.textContent = "⚡ Procedural Script • Stage Cues";
      statusPill.title = "Default Layer 1 procedural first-person script with stage cues ($0.00)";
      return;
    }
    const isGemini =
      polishSource === "GEMINI_FLASH" ||
      polishSource === "GEMINI_2_5_FLASH" ||
      polishSource === "gemini-flash";
    if (isGemini) {
      statusPill.classList.add("is-gemini-flash");
      const cacheTag = cacheHit ? " (Cached)" : "";
      statusPill.textContent = `🤖 AI Polished • Gemini Flash${cacheTag}${batchSuffix}`;
      statusPill.title = "Polished by live Gemini Flash LLM and saved to SQLite cache";
    } else {
      statusPill.classList.add("is-studio-narrative");
      statusPill.textContent = `✨ Studio Narrative Polish • Offline Fallback${batchSuffix}`;
      statusPill.title = fallbackReason
        ? `Used Studio Narrative Fallback (${fallbackReason})`
        : "Polished with archetype-aware Studio Narrative Synthesizer (offline mode)";
    }
  }
  window.syncNotesPolishProvenancePill = syncNotesPolishProvenancePill;

  document.getElementById("btn-restore-default-notes")?.addEventListener("click", () => {
    if (!state.currentResult) return;
    const slides = state.currentResult.storyboard?.slides || [];
    const isCover = state.activeSlideIdx === -1;
    if (isCover) {
      delete state.currentResult._polishedCoverNotes;
      delete state.currentResult._coverPolishSource;
      delete state.currentResult._coverPolishFallbackReason;
    } else {
      const slide = slides[state.activeSlideIdx];
      if (!slide) return;
      if (slide._originalProceduralNotes) {
        slide.presenter_notes = slide._originalProceduralNotes;
      }
      slide._isPolishedNotes = false;
      delete slide._polishSource;
      delete slide._polishFallbackReason;
    }
    renderActiveSlide(state.activeSlideIdx);
  });

  const executePolishSingleSlide = async (forceRefreshOverride = null) => {
    const btn = document.getElementById("btn-ai-polish-notes");
    if (!btn || !state.currentResult) return;
    const slides = state.currentResult.storyboard?.slides || [];
    const isCover = state.activeSlideIdx === -1;
    if (!isCover && (state.activeSlideIdx < 0 || !slides[state.activeSlideIdx])) return;
    const slide = isCover
      ? {
          title: `${state.currentResult.badge_name || "First Aid"} Merit Badge - Cover Slide`,
          req_number: "Cover",
          archetype: "TITLE_COVER_HERO",
          presenter_notes: document.getElementById("stage-presenter-notes")?.innerText || "",
        }
      : slides[state.activeSlideIdx];
    const alreadyPolished = isCover
      ? Boolean(state.currentResult._polishedCoverNotes)
      : Boolean(slide._isPolishedNotes);
    const shouldForceRefresh =
      typeof forceRefreshOverride === "boolean" ? forceRefreshOverride : alreadyPolished;
    if (!isCover && !slide._originalProceduralNotes && slide.presenter_notes) {
      slide._originalProceduralNotes = slide.presenter_notes;
    }
    const nextSeed = shouldForceRefresh
      ? ((isCover ? state.currentResult._coverPolishSeed : slide._polishVariationSeed) || 0) + 1
      : 0;
    if (isCover) {
      state.currentResult._coverPolishSeed = nextSeed;
    } else {
      slide._polishVariationSeed = nextSeed;
    }
    const statusPill = document.getElementById("notes-polish-status-pill");
    const origText = btn.textContent;
    btn.disabled = true;
    btn.textContent = "⏳ Polishing Slide...";
    if (statusPill) {
      statusPill.textContent = "⏳ Calling Gemini Flash to polish slide script...";
    }
    try {
      const resp = await fetch("/api/v1/slide/polish-notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: state.currentResult.badge_name || "First Aid",
          slide_index: state.activeSlideIdx,
          slide_data: slide,
          audience_level:
            document.getElementById("audience-select")?.value ||
            slide.audience_level ||
            "All Scouts (Ages 11-17)",
          storyboard_slides: slides,
          counselor_info: state.currentResult.counselor_info || {},
          output_path: state.currentResult.output_path || "",
          force_refresh: shouldForceRefresh,
          variation_seed: nextSeed,
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        const src =
          data.polish_source ||
          (data.polish_engine === "gemini-flash" ? "GEMINI_FLASH" : "PROCEDURAL_STUDIO_POLISH");
        if (data.presenter_notes) {
          if (isCover) {
            state.currentResult._polishedCoverNotes = data.presenter_notes;
            state.currentResult._coverPolishSource = src;
            state.currentResult._coverPolishCacheHit = Boolean(data.cache_hit);
            state.currentResult._coverPolishFallbackReason = data.fallback_reason || "";
          } else {
            slide.presenter_notes = data.presenter_notes;
            slide._isPolishedNotes = true;
            slide._polishSource = src;
            slide._polishCacheHit = Boolean(data.cache_hit);
            slide._polishFallbackReason = data.fallback_reason || "";
          }
        }
        if (data.pptx_download_url) {
          state.currentResult.pptx_download_url = data.pptx_download_url;
          const pptxBtn = document.getElementById("btn-download-pptx");
          if (pptxBtn && state.preferredExportMode !== "gslides") {
            pptxBtn.href = `${data.pptx_download_url}?v=${Date.now()}`;
          }
        }
        renderActiveSlide(state.activeSlideIdx);
      }
    } catch (err) {
      console.warn("Could not polish slide notes:", err);
    } finally {
      btn.disabled = false;
      btn.textContent = origText;
    }
  };

  const executePolishEntireDeck = async (forceRefreshOverride = false) => {
    const btn = document.getElementById("btn-ai-polish-deck");
    if (!btn || !state.currentResult) return;
    const slides = state.currentResult.storyboard?.slides || [];
    if (!slides.length) return;
    const totalSlides = slides.length;
    const badgeName = state.currentResult.badge_name || "First Aid";
    const audienceLevel = document.getElementById("audience-select")?.value || "All Scouts (Ages 11-17)";
    const statusPill = document.getElementById("notes-polish-status-pill");
    const origText = btn.textContent;
    const shouldForceRefresh = Boolean(forceRefreshOverride);
    const t0 = performance.now();
    let completedCount = 0;
    let geminiCount = 0;
    let cacheHits = 0;
    let lastFallbackReason = "";

    const updateBatchCounterUi = (doneCount) => {
      const counterTag = `[${doneCount}/${totalSlides}]`;
      btn.textContent = `⏳ Polishing ${totalSlides} Slides ${counterTag}...`;
      if (statusPill) {
        statusPill.className = "m3-notes-provenance-pill";
        statusPill.textContent = `⏳ Batch-polishing all ${totalSlides} slides across deck ${counterTag}...`;
      }
    };

    btn.disabled = true;
    updateBatchCounterUi(0);

    try {
      const activeIdx = state.activeSlideIdx;
      const orderedIndices = [];
      if (activeIdx >= 0 && activeIdx < totalSlides) {
        orderedIndices.push(activeIdx);
      }
      for (let i = 0; i < totalSlides; i++) {
        if (i !== activeIdx) orderedIndices.push(i);
      }

      const coverPromise = fetch("/api/v1/slide/polish-notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: badgeName,
          slide_index: -1,
          slide_data: {
            title: `${badgeName} Merit Badge - Cover Slide`,
            req_number: "Cover",
            archetype: "TITLE_COVER_HERO",
          },
          audience_level: audienceLevel,
          storyboard_slides: [],
          force_refresh: shouldForceRefresh,
          variation_seed: shouldForceRefresh ? 1 : 0,
        }),
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((cData) => {
          if (cData && cData.presenter_notes) {
            const cSrc =
              cData.polish_source ||
              (cData.polish_engine === "gemini-flash" ? "GEMINI_FLASH" : "PROCEDURAL_STUDIO_POLISH");
            state.currentResult._polishedCoverNotes = cData.presenter_notes;
            state.currentResult._coverPolishSource = cSrc;
            state.currentResult._coverPolishFallbackReason = cData.fallback_reason || "";
            if (state.activeSlideIdx === -1) {
              renderActiveSlide(-1);
              updateBatchCounterUi(completedCount);
            }
          }
        })
        .catch(() => {});

      let cursor = 0;
      const CONCURRENCY = 6;
      const runWorker = async () => {
        while (cursor < orderedIndices.length) {
          const idx = orderedIndices[cursor++];
          const sObj = slides[idx];
          if (!sObj) continue;
          if (!sObj._originalProceduralNotes && sObj.presenter_notes) {
            sObj._originalProceduralNotes = sObj.presenter_notes;
          }
          try {
            const sResp = await fetch("/api/v1/slide/polish-notes", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                badge_name: badgeName,
                slide_index: idx,
                slide_data: sObj,
                audience_level: audienceLevel,
                storyboard_slides: [],
                force_refresh: shouldForceRefresh,
                variation_seed: shouldForceRefresh ? (idx % 5) + 1 : 0,
              }),
            });
            if (sResp.ok) {
              const sData = await sResp.json();
              const src =
                sData.polish_source ||
                (sData.polish_engine === "gemini-flash" ? "GEMINI_FLASH" : "PROCEDURAL_STUDIO_POLISH");
              if (sData.presenter_notes) {
                sObj.presenter_notes = sData.presenter_notes;
                sObj._isPolishedNotes = true;
                sObj._polishSource = src;
                sObj._polishCacheHit = Boolean(sData.cache_hit);
                sObj._polishFallbackReason = sData.fallback_reason || "";
              }
              if (src === "GEMINI_FLASH") {
                geminiCount++;
              } else if (sData.fallback_reason && !lastFallbackReason) {
                lastFallbackReason = sData.fallback_reason;
              }
              if (sData.cache_hit) cacheHits++;
            }
          } catch (slideErr) {
            console.warn(`Could not polish slide ${idx}:`, slideErr);
          } finally {
            completedCount++;
            if (idx === state.activeSlideIdx) {
              renderActiveSlide(state.activeSlideIdx);
            }
            updateBatchCounterUi(completedCount);
          }
        }
      };

      const workers = Array.from({ length: Math.min(CONCURRENCY, orderedIndices.length) }, () => runWorker());
      await Promise.all([coverPromise, ...workers]);

      const batchResp = await fetch("/api/v1/slide/polish-notes-batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: badgeName,
          storyboard_slides: slides,
          audience_level: audienceLevel,
          counselor_info: state.currentResult.counselor_info || {},
          output_path: state.currentResult.output_path || "",
          force_refresh: false,
        }),
      });
      if (batchResp.ok) {
        const batchData = await batchResp.json();
        if (batchData.pptx_download_url) {
          state.currentResult.pptx_download_url = batchData.pptx_download_url;
          const pptxBtn = document.getElementById("btn-download-pptx");
          if (pptxBtn && state.preferredExportMode !== "gslides") {
            pptxBtn.href = `${batchData.pptx_download_url}?v=${Date.now()}`;
          }
        }
      }

      const finalSource = geminiCount > 0 ? "GEMINI_FLASH" : "PROCEDURAL_STUDIO_POLISH";
      const elapsedMs = Math.round(performance.now() - t0);
      renderActiveSlide(state.activeSlideIdx);
      syncNotesPolishProvenancePill({
        isPolished: true,
        polishSource: finalSource,
        cacheHit: cacheHits > 0,
        fallbackReason: finalSource === "GEMINI_FLASH" ? "" : lastFallbackReason,
        batchSuffix: ` • All ${totalSlides} Slides (${elapsedMs}ms)`,
      });
    } catch (err) {
      console.warn("Could not batch-polish deck speaker notes:", err);
    } finally {
      btn.disabled = false;
      btn.textContent = origText;
    }
  };

  const openAiPolishFinopsGateModal = async (requestedMode = "single") => {
    const modal = document.getElementById("ai-polish-finops-modal");
    if (!modal || !state.currentResult) return;
    const slides = state.currentResult.storyboard?.slides || [];
    const totalSlides = slides.length + 1;
    const isCover = state.activeSlideIdx === -1;
    const activeSlide = isCover
      ? { title: `${state.currentResult.badge_name || "First Aid"} Merit Badge - Cover Slide`, req_number: "Cover" }
      : slides[Math.max(0, state.activeSlideIdx)] || {};

    const singleCard = document.getElementById("finops-card-single-slide");
    const deckCard = document.getElementById("finops-card-entire-deck");
    const singleBadge = document.getElementById("finops-single-cache-badge");
    const singleCostEl = document.getElementById("finops-single-cost-value");
    const singleMetaEl = document.getElementById("finops-single-token-meta");
    const deckCountBadge = document.getElementById("finops-deck-slide-count-badge");
    const deckOptionKicker = document.getElementById("finops-deck-option-kicker");
    const deckCostEl = document.getElementById("finops-deck-cost-value");
    const deckMetaEl = document.getElementById("finops-deck-token-meta");
    const leadCountEl = document.getElementById("finops-lead-slide-count");
    const leadBadgeEl = document.getElementById("finops-lead-badge-name");
    const forceChk = document.getElementById("chk-finops-force-repolish");
    const btnSingle = document.getElementById("btn-confirm-polish-single-slide");
    const btnDeck = document.getElementById("btn-confirm-polish-entire-deck");

    if (singleCard) {
      singleCard.style.borderColor = requestedMode === "single" ? "#4F46E5" : "#C7D2FE";
      singleCard.style.boxShadow =
        requestedMode === "single" ? "0 0 0 3px rgba(79, 70, 229, 0.16)" : "none";
    }
    if (deckCard) {
      deckCard.style.borderColor = requestedMode === "deck" ? "#D97706" : "#FCD34D";
      deckCard.style.boxShadow =
        requestedMode === "deck" ? "0 0 0 3px rgba(217, 119, 6, 0.18)" : "none";
    }

    let estimate = {
      single_slide_cached: false,
      single_slide_input_tokens: 450,
      single_slide_output_tokens: 280,
      single_slide_cost_usd: 0.000835,
      total_slides: totalSlides,
      cached_slides_count: 0,
      uncached_slides_count: totalSlides,
      deck_uncached_cost_usd: Number((totalSlides * 0.000835).toFixed(4)),
      deck_full_repolish_cost_usd: Number((totalSlides * 0.000835).toFixed(4)),
    };

    const renderEstimateUi = () => {
      const force = Boolean(forceChk?.checked);
      const slideNumLabel = isCover ? "Cover Slide" : `Slide #${state.activeSlideIdx + 2}`;
      const singleCached = estimate.single_slide_cached && !force;
      const singleUsd = singleCached ? 0 : estimate.single_slide_cost_usd || 0.000835;
      if (leadBadgeEl) {
        leadBadgeEl.textContent = `${state.currentResult.badge_name || "First Aid"} Merit Badge`;
      }
      if (singleBadge) {
        singleBadge.textContent = singleCached ? `${slideNumLabel} • Cached ($0)` : slideNumLabel;
      }
      if (singleCostEl) {
        singleCostEl.innerHTML = singleCached
          ? `$0.0000 <span style="font-size:0.78rem; font-weight:700; color:#15803D;">(Cached in SQLite • ~$0.0008 if re-polished)</span>`
          : `~$${singleUsd.toFixed(4)} <span style="font-size:0.78rem; font-weight:700; color:#475569;">(&lt; $0.001 / slide)</span>`;
      }
      if (singleMetaEl) {
        singleMetaEl.innerHTML = `~${estimate.single_slide_input_tokens} input tokens + ~${estimate.single_slide_output_tokens} output tokens<br/>Latency: ~1.5 seconds • Cached in SQLite (${singleCached ? "Already cached: $0.00" : "$0.00 on repeat"})`;
      }

      const nTotal = estimate.total_slides || totalSlides;
      const nCached = estimate.cached_slides_count || 0;
      const nUncached = force ? nTotal : estimate.uncached_slides_count ?? nTotal;
      const deckUsd = force
        ? estimate.deck_full_repolish_cost_usd || nTotal * 0.000835
        : estimate.deck_uncached_cost_usd ?? nUncached * 0.000835;

      if (leadCountEl) {
        leadCountEl.textContent = `${nTotal}-slide`;
      }
      if (deckOptionKicker) {
        deckOptionKicker.textContent = `OPTION 2 • ENTIRE ${nTotal}-SLIDE DECK`;
      }
      if (deckCountBadge) {
        deckCountBadge.textContent =
          nCached > 0 && !force
            ? `${nTotal} Slides (${nCached} Cached)`
            : `${nTotal} Slides`;
      }
      if (deckCostEl) {
        deckCostEl.innerHTML = `~$${Number(deckUsd).toFixed(4)} <span style="font-size:0.78rem; font-weight:700; color:#92400E;">(${nTotal} slides × $0.0008)</span>`;
      }
      if (deckMetaEl) {
        deckMetaEl.innerHTML =
          nCached > 0 && !force
            ? `~${(nUncached * 450).toLocaleString()} input + ~${(nUncached * 280).toLocaleString()} output tokens (${nCached} already cached at $0.00)<br/>Parallel 6x worker pool • Live <code>[1/${nTotal}]</code> progress counter`
            : `~${(nTotal * 450).toLocaleString()} input tokens + ~${(nTotal * 280).toLocaleString()} output tokens<br/>Parallel 6x worker pool • Live <code>[1/${nTotal}]</code> progress counter`;
      }
      if (btnSingle) {
        btnSingle.textContent = `✨ Polish This Slide (~$${singleUsd > 0 ? singleUsd.toFixed(4) : "0.0008"})`;
      }
      if (btnDeck) {
        btnDeck.textContent = `✨ Polish All ${nTotal} Slides (~$${Number(deckUsd).toFixed(4)})`;
      }
    };

    renderEstimateUi();
    modal.classList.remove("hidden");
    modal.classList.add("open");

    try {
      const resp = await fetch("/api/v1/slide/estimate-polish-cost", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: state.currentResult.badge_name || "First Aid",
          slide_index: state.activeSlideIdx,
          slide_data: activeSlide,
          storyboard_slides: slides,
          audience_level:
            document.getElementById("audience-select")?.value || "All Scouts (Ages 11-17)",
        }),
      });
      if (resp.ok) {
        const serverEst = await resp.json();
        estimate = { ...estimate, ...serverEst };
        renderEstimateUi();
      }
    } catch (_e) {}

    if (forceChk) {
      forceChk.onchange = () => renderEstimateUi();
    }
  };

  document.getElementById("btn-close-ai-polish-finops")?.addEventListener("click", () => {
    const m = document.getElementById("ai-polish-finops-modal");
    m?.classList.remove("open");
    m?.classList.add("hidden");
  });
  document.getElementById("btn-cancel-ai-polish-finops")?.addEventListener("click", () => {
    const m = document.getElementById("ai-polish-finops-modal");
    m?.classList.remove("open");
    m?.classList.add("hidden");
  });
  document.getElementById("btn-confirm-polish-single-slide")?.addEventListener("click", async () => {
    const m = document.getElementById("ai-polish-finops-modal");
    const force = Boolean(document.getElementById("chk-finops-force-repolish")?.checked);
    const dontAsk = Boolean(document.getElementById("chk-finops-dont-ask-session")?.checked);
    if (dontAsk) {
      try {
        window.sessionStorage.setItem("bsa_ai_polish_finops_ack_v1", "1");
      } catch (_e) {}
    }
    m?.classList.remove("open");
    m?.classList.add("hidden");
    await executePolishSingleSlide(force ? true : null);
  });
  document.getElementById("btn-confirm-polish-entire-deck")?.addEventListener("click", async () => {
    const m = document.getElementById("ai-polish-finops-modal");
    const force = Boolean(document.getElementById("chk-finops-force-repolish")?.checked);
    const dontAsk = Boolean(document.getElementById("chk-finops-dont-ask-session")?.checked);
    if (dontAsk) {
      try {
        window.sessionStorage.setItem("bsa_ai_polish_finops_ack_v1", "1");
      } catch (_e) {}
    }
    m?.classList.remove("open");
    m?.classList.add("hidden");
    await executePolishEntireDeck(force);
  });

  document.getElementById("btn-ai-polish-notes")?.addEventListener("click", async () => {
    if (!state.currentResult) return;
    let acked = false;
    try {
      acked = window.sessionStorage.getItem("bsa_ai_polish_finops_ack_v1") === "1";
    } catch (_e) {}
    if (!acked) {
      await openAiPolishFinopsGateModal("single");
      return;
    }
    await executePolishSingleSlide(null);
  });

  document.getElementById("btn-ai-polish-deck")?.addEventListener("click", async () => {
    if (!state.currentResult) return;
    let acked = false;
    try {
      acked = window.sessionStorage.getItem("bsa_ai_polish_finops_ack_v1") === "1";
    } catch (_e) {}
    if (!acked) {
      await openAiPolishFinopsGateModal("deck");
      return;
    }
    await executePolishEntireDeck(false);
  });

  // Quick-Switch Slide Image button
  document.getElementById("btn-quick-switch-image")?.addEventListener("click", async () => {
    const sel = document.getElementById("codesign-quick-image-select");
    if (!sel || !state.combinedSlideImages.length) return;
    const idx = parseInt(sel.value, 10);
    if (isNaN(idx) || idx < 0 || idx >= state.combinedSlideImages.length) return;
    await applyCatalogImageToActiveSlide(state.combinedSlideImages[idx]);
  });

  document.querySelectorAll(".m3-badge-pill").forEach((pill) => {
    pill.addEventListener("click", async () => {
      const badge = pill.getAttribute("data-badge");
      if (!badge) return;
      if (!state.filteredBadges.some((b) => b.badge_name === badge)) {
        if (searchInput) searchInput.value = "";
        if (catSelect) catSelect.value = "ALL";
        if (eagleSelect) eagleSelect.value = "ALL";
        applyBadgeFilters(false);
      }
      document.querySelectorAll(".m3-badge-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      const select = document.getElementById("badge-select");
      if (select) {
        select.value = badge;
      }
      await executeStreamingWorkflow(badge);
    });
  });

  document.getElementById("badge-select")?.addEventListener("change", async (e) => {
    const badge = e.target.value;
    if (!badge) return;
    document.querySelectorAll(".m3-badge-pill").forEach((p) => {
      p.classList.toggle("active", p.getAttribute("data-badge") === badge);
    });
    await executeStreamingWorkflow(badge);
  });

  document.getElementById("btn-prev-slide")?.addEventListener("click", () => {
    const slides = state.currentResult?.storyboard?.slides || [];
    if (state.activeSlideIdx > -1) {
      state.activeSlideIdx -= 1;
      renderFilmstrip(slides);
      renderActiveSlide(state.activeSlideIdx);
    }
  });

  document.getElementById("btn-next-slide")?.addEventListener("click", () => {
    const slides = state.currentResult?.storyboard?.slides || [];
    if (state.activeSlideIdx < slides.length - 1) {
      state.activeSlideIdx += 1;
      renderFilmstrip(slides);
      renderActiveSlide(state.activeSlideIdx);
    }
  });

  document.getElementById("btn-download-agenda-md")?.addEventListener("click", () => {
    const md = state.currentResult?.session_agenda?.agenda_markdown || "# Session Lesson Plan";
    const badgeSlug = (state.currentResult?.badge_name || "Merit_Badge").replace(/\s+/g, "_");
    triggerMarkdownDownload(`${badgeSlug}_Session_Agenda.md`, md);
  });

  document.getElementById("btn-download-letter-md")?.addEventListener("click", () => {
    const md = getLiveParentLetterMarkdown(state.currentResult);
    const badgeSlug = (state.currentResult?.badge_name || "Merit_Badge").replace(/\s+/g, "_");
    triggerMarkdownDownload(`${badgeSlug}_Parent_Prerequisite_Letter.md`, md);
  });
}

function triggerMarkdownDownload(filename, content) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function loadBadgesCatalog() {
  const data = await fetch("/api/badges").then((r) => r.json());
  state.badges = data.badges || [];
  state.categories = data.categories || [];

  const totalCount = state.badges.length;
  const eagleCount = state.badges.filter((b) => b.is_eagle_required).length;
  const electiveCount = totalCount - eagleCount;

  const searchInput = document.getElementById("filter-search-input");
  if (searchInput && totalCount > 0) {
    searchInput.placeholder = `Search all ${totalCount} badges (e.g., Weather, First Aid, Kayaking)...`;
  }

  const eagleSelect = document.getElementById("filter-eagle-select");
  if (eagleSelect && totalCount > 0) {
    const prevEagleVal = eagleSelect.value || "ALL";
    eagleSelect.innerHTML = `
      <option value="ALL">All Badges (${totalCount})</option>
      <option value="EAGLE">Eagle-Required (${eagleCount})</option>
      <option value="ELECTIVE">Electives (${electiveCount})</option>
    `;
    eagleSelect.value = prevEagleVal;
  }

  const catSelect = document.getElementById("filter-category-select");
  if (catSelect) {
    catSelect.innerHTML = '<option value="ALL">All Categories</option>';
    state.categories.forEach((cat) => {
      const opt = document.createElement("option");
      opt.value = cat;
      opt.textContent = cat;
      catSelect.appendChild(opt);
    });
  }

  applyBadgeFilters(true);
  populateAdminBadgeSelector();
}

function applyBadgeFilters(initialLoad = false) {
  const query = (document.getElementById("filter-search-input")?.value || "").trim().toLowerCase();
  const category = document.getElementById("filter-category-select")?.value || "ALL";
  const eagleMode = document.getElementById("filter-eagle-select")?.value || "ALL";

  const favSet = new Set((state.favoriteBadges || []).map((x) => String(x).toLowerCase()));
  state.filteredBadges = state.badges.filter((b) => {
    if (query && !b.badge_name.toLowerCase().includes(query) && !(b.category || "").toLowerCase().includes(query)) {
      return false;
    }
    if (category !== "ALL" && b.category !== category) {
      return false;
    }
    if (eagleMode === "FAVORITES" && !favSet.has(b.badge_name.toLowerCase())) {
      return false;
    }
    if (eagleMode === "EAGLE" && !b.is_eagle_required) {
      return false;
    }
    if (eagleMode === "ELECTIVE" && b.is_eagle_required) {
      return false;
    }
    return true;
  });

  const countChip = document.getElementById("badge-filter-count-chip");
  if (countChip) {
    countChip.textContent = `${state.filteredBadges.length} of ${state.badges.length} Badges`;
  }

  const select = document.getElementById("badge-select");
  if (!select) return;
  const prevValue = initialLoad ? "First Aid" : select.value || state.currentBadge;
  select.innerHTML = "";

  if (state.filteredBadges.length === 0) {
    const emptyOpt = document.createElement("option");
    emptyOpt.value = "";
    emptyOpt.textContent = "No matching Merit Badges — adjust filters";
    select.appendChild(emptyOpt);
    return;
  }

  state.filteredBadges.forEach((b) => {
    const opt = document.createElement("option");
    opt.value = b.badge_name;
    const isFav = favSet.has(b.badge_name.toLowerCase());
    opt.textContent = `${isFav ? "⭐ " : ""}${b.is_eagle_required ? "★ " : ""}${b.badge_name} (${b.category})`;
    select.appendChild(opt);
  });

  if (state.filteredBadges.some((b) => b.badge_name === prevValue)) {
    select.value = prevValue;
  } else {
    select.value = state.filteredBadges[0].badge_name;
  }
  if (typeof window.syncActiveBadgeStarButton === "function") {
    window.syncActiveBadgeStarButton();
  }
}

function friendlyStepLabel(agentName) {
  const map = {
    PamphletResearchAgent: "1. Pamphlet & Requirements Research",
    DeepResearchEnrichmentAgent: "2. Grounded Web & Local Troop Research",
    SlideContentPlannerAgent: "3. Slide Deck Outline & Teaching Plan",
    FastMCPConfirmationGate: "4. Curriculum Verification",
    SlideBeautifierAgent: "5. AI Slide Beautification & Visual Blueprint",
    PowerPointBuilderAgent: "6. PowerPoint, Workbook & StudioKit Builder",
    BSABrandAndSafetyReviewAgent: "7. Final Slide & FinOps Quality Check",
  };
  return map[agentName] || agentName;
}

function inferBrowserLocationHint() {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    const tzMap = {
      "America/New_York": "Boston, MA",
      "America/Detroit": "Detroit, MI",
      "America/Chicago": "Chicago, IL",
      "America/Denver": "Denver, CO",
      "America/Phoenix": "Phoenix, AZ",
      "America/Los_Angeles": "San Francisco, CA",
      "America/Anchorage": "Anchorage, AK",
      "Pacific/Honolulu": "Honolulu, HI",
    };
    return tzMap[tz] || "";
  } catch (_e) {
    return "";
  }
}

async function executeStreamingWorkflow(badgeName) {
  state.currentBadge = badgeName;
  clearDeckConfigDirty();
  state.revealedQuizSlides = new Set();
  state.checkedGearItems = new Set();
  const depthMode = document.getElementById("depth-select")?.value || "Deep Dive / Camp School Deck";
  const beautificationTier = document.getElementById("beautification-select")?.value || "BEAUTIFIED";
  const audienceLevel = document.getElementById("audience-select")?.value || "All Scouts (Ages 11–17)";
  const enableDeepResearch = document.getElementById("deep-research-checkbox")?.checked ?? true;
  const counselorName = document.getElementById("input-counselor-name")?.value || "Scoutmaster Bob";
  const troopName = document.getElementById("input-troop-name")?.value || "Troop 123, My Council";
  const rawLocationInput = (document.getElementById("input-counselor-location")?.value || "").trim();
  const locationOrZip =
    rawLocationInput ||
    (troopName === "Troop 123, My Council" ? inferBrowserLocationHint() : "");
  const email = document.getElementById("input-counselor-email")?.value ?? "counselor@troop123.org";
  const phone = document.getElementById("input-counselor-phone")?.value ?? "(000) 555-1234";
  const customLogoPath = state.customLogoPath || "";

  const progressFill = document.getElementById("trace-progress-fill");
  const progressLabel = document.getElementById("trace-progress-label");
  const traceList = document.getElementById("agent-trace-list");
  const traceToggleBtn = document.getElementById("btn-toggle-trace-details");
  const genBtn = document.getElementById("btn-generate-deck");
  const filmstripEl = document.getElementById("slide-filmstrip-list");

  // Hide the slide list while new slides are being generated so Research & Generation Progress occupies the top of the column
  if (filmstripEl) {
    filmstripEl.classList.add("hidden");
  }
  traceList?.classList.remove("hidden");
  if (traceToggleBtn) traceToggleBtn.textContent = "Hide ▴";
  showConstructionAnimationStage(badgeName, false);

  if (genBtn) {
    genBtn.disabled = true;
    genBtn.innerHTML = '<span class="material-symbols-outlined">hourglass_top</span> Generating Deck &amp; Workbook...';
  }

  if (progressFill) progressFill.style.width = "10%";
  if (progressLabel) progressLabel.textContent = "10%";
  if (traceList) {
    traceList.innerHTML = `
      <div class="m3-trace-item">
        <div class="m3-trace-top"><span>Starting Generation</span><span class="m3-trace-meta">In Progress</span></div>
        <div class="m3-trace-desc">Researching official ${escapeHtml(badgeName)} Merit Badge requirements and applying ${escapeHtml(formatSlideThemeLabel(beautificationTier))} theme...</div>
      </div>
    `;
  }

  const paramsObj = {
    badge_name: badgeName,
    depth_mode: depthMode,
    beautification_tier: beautificationTier,
    audience_level: audienceLevel,
    enable_deep_research: String(enableDeepResearch),
    counselor_name: counselorName,
    troop_affiliation: troopName,
    location_or_zip: locationOrZip,
    email_address: email,
    phone_number: phone,
  };
  if (customLogoPath) {
    paramsObj.custom_troop_logo_path = customLogoPath;
  }
  const params = new URLSearchParams(paramsObj);

  return new Promise((resolve) => {
    const es = new EventSource(`/api/workflow/stream?${params.toString()}`);

    es.onmessage = (evt) => {
      const payload = JSON.parse(evt.data);
      const pct = payload.progress_pct || 50;
      if (progressFill) progressFill.style.width = `${pct}%`;
      if (progressLabel) progressLabel.textContent = pct >= 100 ? "Complete" : `${pct}%`;

      if (payload.event === "workflow_complete" && payload.result) {
        es.close();
        if (genBtn) {
          genBtn.disabled = false;
          genBtn.innerHTML = '<span class="material-symbols-outlined">auto_awesome</span> Generate Slide Deck &amp; Workbook';
        }
        hydrateWorkbench(payload.result);
        resolve(payload.result);
      } else if (payload.event === "workflow_error") {
        es.close();
        if (genBtn) {
          genBtn.disabled = false;
          genBtn.innerHTML = '<span class="material-symbols-outlined">auto_awesome</span> Generate Slide Deck &amp; Workbook';
        }
        resolve(null);
      } else if (payload.agent && traceList) {
        const kickerEl = document.getElementById("construction-workorder-kicker");
        if (kickerEl) {
          kickerEl.textContent = `${friendlyStepLabel(payload.agent).toUpperCase()} (${pct}%)`;
        }
        const item = document.createElement("div");
        item.className = "m3-trace-item";
        item.innerHTML = `
          <div class="m3-trace-top">
            <span>${escapeHtml(friendlyStepLabel(payload.agent))}</span>
            <span class="m3-trace-meta">Done</span>
          </div>
          <div class="m3-trace-desc">${escapeHtml(payload.message || "")}</div>
        `;
        traceList.appendChild(item);
      }
    };

    es.onerror = async () => {
      es.close();
      try {
        const res = await fetch("/api/workflow/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            badge_name: badgeName,
            depth_mode: depthMode,
            beautification_tier: beautificationTier,
            audience_level: audienceLevel,
            enable_deep_research: enableDeepResearch,
            counselor_name: counselorName,
            troop_affiliation: troopName,
            location_or_zip: locationOrZip,
            email_address: email,
            phone_number: phone,
            custom_troop_logo_path: customLogoPath || null,
          }),
        }).then((r) => r.json());
        hydrateWorkbench(res);
        resolve(res);
      } finally {
        if (genBtn) {
          genBtn.disabled = false;
          genBtn.innerHTML = '<span class="material-symbols-outlined">auto_awesome</span> Generate Slide Deck &amp; Workbook';
        }
      }
    };
  });
}

function hydrateWorkbench(rawResult) {
  const result = rawResult?.result && rawResult.result.storyboard ? rawResult.result : rawResult;
  if (!result || result.status === "ERROR" || !result.badge_name || !result.storyboard) return;
  state.currentResult = result;
  state.activeSlideIdx = -1;
  clearDeckConfigDirty();

  const slides = result.storyboard?.slides || [];
  const reqs = result.research_artifact?.requirements || [];
  const finops = result.finops_cost_estimate || {};
  const resolvedLoc = result.deep_research_enrichment?.resolved_location || {};

  // Update Location inference hint so counselor sees the resolved region & NOAA office
  const locHintEl = document.getElementById("location-infer-hint");
  if (locHintEl && resolvedLoc.region_label) {
    locHintEl.innerHTML = `Resolved Local Context: <strong>${escapeHtml(resolvedLoc.region_label)}</strong> &bull; ${escapeHtml(resolvedLoc.nws_office || "NOAA NWS")}`;
  }

  // Update Visual Polish & Pre-Cached Assets Pill in Sidebar
  const finopsUsdEl = document.getElementById("finops-cost-usd");
  const finopsMetaEl = document.getElementById("finops-cost-meta");
  const tierNow = finops.beautification_tier || result.beautification_tier || "BEAUTIFIED";
  if (finopsUsdEl) {
    finopsUsdEl.innerHTML =
      tierNow === "STANDARD"
        ? `<strong>Visual Assets:</strong> Pamphlet Figures Only (Lightweight)`
        : `<strong>Visual Assets:</strong> 100% Pre-Cached (8-Bit PNG)`;
  }
  if (finopsMetaEl) {
    finopsMetaEl.textContent = `${formatSlideThemeLabel(tierNow)} • Instant Load`;
  }

  // 1. Update Hero Banner, Patch Image & Resource Links
  document.getElementById("hero-badge-title").textContent = `${result.badge_name} Merit Badge`;
  const categoryLabel = result.category ? ` • ${result.category.toUpperCase()}` : "";
  document.getElementById("hero-eagle-kicker").innerHTML = result.is_eagle_required
    ? `<span class="material-symbols-outlined" style="font-size:16px;">stars</span><span>★ EAGLE-REQUIRED MERIT BADGE${escapeHtml(categoryLabel)}</span>`
    : `<span class="material-symbols-outlined" style="font-size:16px;">verified</span><span>SCOUTS BSA ELECTIVE MERIT BADGE${escapeHtml(categoryLabel)}</span>`;

  const activeTier = result.beautification_tier || document.getElementById("beautification-select")?.value || "BEAUTIFIED";
  const activeThemeLabel = formatSlideThemeLabel(activeTier);
  const activeAudience = result.audience_level || document.getElementById("audience-select")?.value || "All Scouts (Ages 11–17)";
  const depthDesc = (result.depth_mode || "").toLowerCase().includes("deep")
    ? "Detailed Deep-Dive Teaching Deck"
    : "Standard Troop Meeting Deck (1–3 Slides per Requirement)";
  document.getElementById("hero-badge-subtitle").textContent = `${depthDesc} • ${activeThemeLabel} Theme • ${activeAudience}`;

  const patchImg = document.getElementById("hero-badge-patch-img");
  if (patchImg && result.patch_url) {
    patchImg.src = `${result.patch_url}${result.patch_url.includes("?") ? "&" : "?"}v=20261016c`;
    patchImg.alt = `${result.badge_name} Merit Badge Patch`;
  }

  document.getElementById("kpi-slide-count").textContent = String(result.slide_count || slides.length + 1);
  document.getElementById("kpi-subreq-count").textContent = String(reqs.length);
  const kpiPolishEl = document.getElementById("kpi-polish-tier");
  if (kpiPolishEl) kpiPolishEl.textContent = activeThemeLabel;

  // Download & Resource buttons (respect sticky .PPTX vs Google Slides export preference)
  syncDeckExportSplitButtonUi(state.preferredExportMode || "pptx");
  const wbBtn = document.getElementById("btn-download-workbook");
  const wbBtnTop = document.getElementById("btn-download-workbook-top");
  if (result.workbook_download_url) {
    if (wbBtn) wbBtn.href = `${result.workbook_download_url}?v=${Date.now()}`;
    if (wbBtnTop) wbBtnTop.href = `${result.workbook_download_url}?v=${Date.now()}`;
  }

  const pamphletUrl = result.pamphlet_pdf_url || result.research_artifact?.pamphlet_pdf_url || "#";
  const drgUrl = result.drg_url || result.research_artifact?.drg_url || "https://www.scouting.org/skills/merit-badges/";
  const topPamphlet = document.getElementById("link-top-pamphlet");
  const topDrg = document.getElementById("link-top-drg");
  if (topPamphlet) topPamphlet.href = pamphletUrl;
  if (topDrg) topDrg.href = drgUrl;

  // 2. Render Clean Generation Summary & Auto-Collapse Trace Details so Slide Outline has full vertical room
  const traceList = document.getElementById("agent-trace-list");
  const traceToggleBtn = document.getElementById("btn-toggle-trace-details");
  if (traceList) {
    const drCount = (result.deep_research_enrichment?.grounded_citations || []).length;
    const liveTroop = document.getElementById("input-troop-name")?.value || "Troop 123, My Council";
    const locLabel = resolvedLoc.region_label ? ` • ${resolvedLoc.region_label}` : "";
    traceList.innerHTML = `
      <div class="m3-trace-item">
        <div class="m3-trace-top"><span>1. Official Requirements &amp; Pamphlet</span><span class="m3-trace-meta">Loaded</span></div>
        <div class="m3-trace-desc">Extracted ${reqs.length} official requirements + ${drCount} grounded citations for ${escapeHtml(result.badge_name)} (${escapeHtml(liveTroop)}${escapeHtml(locLabel)}).</div>
      </div>
      <div class="m3-trace-item">
        <div class="m3-trace-top"><span>2. Teaching Slides &amp; Visual Theme</span><span class="m3-trace-meta">${result.slide_count} Slides (${escapeHtml(activeThemeLabel)})</span></div>
        <div class="m3-trace-desc">Applied ${escapeHtml(activeThemeLabel)} theme styling, ${escapeHtml(activeAudience)} coaching, and Hero Graphics &amp; EDGE Skill Maps.</div>
      </div>
      <div class="m3-trace-item">
        <div class="m3-trace-top"><span>3. PowerPoint, Workbook &amp; StudioKit</span><span class="m3-trace-meta">$${(finops.estimated_cost_usd || 0.14).toFixed(2)}</span></div>
        <div class="m3-trace-desc">Ready to preview and download (.pptx slide deck, .md workbook, lesson plan &amp; parent letter).</div>
      </div>
    `;
    traceList.classList.add("hidden");
    if (traceToggleBtn) traceToggleBtn.textContent = "Details ▾";
  }

  // 3. Reveal Slide Stage and Render Storyboard Filmstrip, Requirement Quick-Jump Bar & Active Slide
  updateConstructionBadgeEmblem(result.badge_name);
  hideConstructionAnimationStage();
  renderFilmstrip(slides);
  renderActiveSlide(-1);

  // 4. Render Official Requirements, Click-to-Jump Cards & Blue Card Tracker
  renderTriageMatrix(result.research_artifact || {}, pamphletUrl, drgUrl);
  renderBlueCardTracker(result);

  // 5. Render Printable Workbook as styled wrapped Markdown
  const wbPreview = document.getElementById("workbook-markdown-preview");
  if (wbPreview) {
    wbPreview.innerHTML = renderMarkdownToStyledHtml(
      result.workbook_markdown || "# Counselor Workbook Generated"
    );
  }

  // 6. Render Counselor StudioKit (Lesson Plan, Parent Letter, Gear Checklist, Citations & FinOps)
  renderStudioKitAndParentLetter(result);
  renderQuartermasterGearChecklist(result);
  renderBuddyStationRotator(result);
  renderPrereqReadinessChecklist(result);
  syncPresenterViewWindow();
  if (typeof window.syncActiveBadgeStarButton === "function") {
    window.syncActiveBadgeStarButton();
  }
  if (typeof window.onWorkbenchDeckHydrated === "function") {
    window.onWorkbenchDeckHydrated(result);
  }
}

function getLiveParentLetterMarkdown(result) {
  if (!result) return "# Parent Prerequisite Letter";
  const counselorName = document.getElementById("input-counselor-name")?.value || "Scoutmaster Bob";
  const troopName = document.getElementById("input-troop-name")?.value || "Troop 123, My Council";
  const email = document.getElementById("input-counselor-email")?.value || "counselor@troop123.org";
  const phone = document.getElementById("input-counselor-phone")?.value || "(000) 555-1234";
  const storedCounselor = result.counselor_info?.counselor_name || "Scoutmaster Bob";
  const storedTroop = result.counselor_info?.troop_affiliation || "Troop 123, My Council";
  const storedEmail = result.counselor_info?.email_address || "counselor@troop123.org";
  const storedPhone = result.counselor_info?.phone_number || "(000) 555-1234";
  let rawLetter = result.prerequisite_parent_letter?.letter_markdown || "# Parent Prerequisite Letter";
  return rawLetter
    .split(storedCounselor).join(counselorName)
    .split("Scoutmaster Bob").join(counselorName)
    .split(storedTroop).join(troopName)
    .split("Troop 123, My Council").join(troopName)
    .split(storedEmail).join(email)
    .split("counselor@troop123.org").join(email)
    .split(storedPhone).join(phone)
    .split("(000) 555-1234").join(phone);
}

function renderStudioKitAndParentLetter(result) {
  if (!result) return;
  const finops = result.finops_cost_estimate || {};
  const troopName = document.getElementById("input-troop-name")?.value || "Troop 123, My Council";

  const agendaPreview = document.getElementById("studiokit-agenda-preview");
  if (agendaPreview) {
    agendaPreview.innerHTML = renderMarkdownToStyledHtml(
      result.session_agenda?.agenda_markdown || "# Session Lesson Plan"
    );
  }

  // Dynamically update Prerequisite Parent Letter with live Counselor inputs so it never reverts to defaults
  const letterPreview = document.getElementById("studiokit-letter-preview");
  if (letterPreview) {
    letterPreview.innerHTML = renderMarkdownToStyledHtml(getLiveParentLetterMarkdown(result));
  }

  const citList = document.getElementById("studiokit-citations-list");
  if (citList) {
    const storedTroop = result.deep_research_enrichment?.troop_affiliation || "Troop 123, My Council";
    const resolvedLoc = result.deep_research_enrichment?.resolved_location || {};
    const citations = result.deep_research_enrichment?.grounded_citations || [];
    if (citations.length === 0) {
      citList.innerHTML = `<div class="m3-req-node-card">Local Regional Grounding was disabled for this run. Enable the checkbox in the left sidebar to resolve local NOAA Weather Forecast Office &amp; regional field study sites for <strong>${escapeHtml(troopName)}</strong>.</div>`;
    } else {
      const senLine =
        resolvedLoc.senator_1 && resolvedLoc.senator_2
          ? `<br/><strong>Current U.S. Senators (${escapeHtml(resolvedLoc.state_code || "MA")}):</strong> ${escapeHtml(resolvedLoc.senator_1)} &amp; ${escapeHtml(resolvedLoc.senator_2)} <span class="m3-chip m3-chip-secondary" style="font-size:0.65rem; padding:1px 6px; margin-left:4px;">🔄 24h Daily + On-Demand Gemini Verified</span>`
          : "";
      const civicLine = resolvedLoc.state_capitol
        ? `<br/><strong>State Capitol &amp; Landmarks:</strong> ${escapeHtml(resolvedLoc.state_capitol)} &bull; ${escapeHtml(resolvedLoc.national_landmarks || "")}`
        : "";
      const locHeader = resolvedLoc.region_label
        ? `<div class="m3-req-node-card" style="background:#EFF6FF; border-left:5px solid #003F87;">
             <div style="font-weight:800; color:#003F87;">📍 Resolved Local Region: ${escapeHtml(resolvedLoc.region_label)} (${escapeHtml(resolvedLoc.nws_office || "NOAA NWS")})</div>
             <div style="font-size:0.80rem; color:#1E293B; margin-top:4px;"><strong>Regional Hazards:</strong> ${escapeHtml(resolvedLoc.terrain_and_hazards || "")}<br/><strong>Field Study Sites:</strong> ${escapeHtml(resolvedLoc.field_site_examples || "")}${civicLine}${senLine}</div>
           </div>`
        : "";
      citList.innerHTML =
        locHeader +
        citations
          .map((c) => {
            const liveFact = String(c.local_grounding_callout || c.supplemental_fact || "")
              .split(storedTroop).join(troopName)
              .split("Troop 123, My Council").join(troopName);
            const catPill = c.grounding_category
              ? `<span class="m3-chip m3-chip-secondary" style="font-size:0.65rem; padding:2px 6px; margin-left:4px;">${escapeHtml(String(c.grounding_category).replace(/_/g, " "))}</span>`
              : "";
            const localBadge = c.requires_local_lookup
              ? `<span class="m3-chip m3-chip-gold" style="font-size:0.65rem; padding:2px 6px; margin-left:4px;">📍 Local Slide Callout</span>`
              : "";
            return `
              <div class="m3-req-node-card">
                <div style="font-weight:700; color:var(--md-sys-color-primary); display:flex; align-items:center; flex-wrap:wrap; gap:4px;">
                  <a href="${escapeHtml(c.source_url)}" target="_blank" rel="noopener noreferrer" style="color:var(--md-sys-color-primary); text-decoration:none;">${escapeHtml(c.source_title)}</a>
                  <span class="m3-chip m3-chip-primary" style="font-size:0.68rem; padding:2px 6px;">${escapeHtml(c.authority_domain || "")} &bull; Req ${escapeHtml(c.req_number || "")}</span>
                  ${catPill}${localBadge}
                </div>
                <div style="font-size:0.80rem; color:var(--md-sys-color-on-surface-variant); margin-top:4px;">${escapeHtml(liveFact)}</div>
              </div>
            `;
          })
          .join("");
    }
  }

  const finopsPreview = document.getElementById("studiokit-finops-preview");
  if (finopsPreview) {
    finopsPreview.innerHTML = renderFinopsTableHtml(finops);
  }
  const adminFinopsPreview = document.getElementById("admin-finops-ledger-preview");
  if (adminFinopsPreview) {
    adminFinopsPreview.innerHTML = renderFinopsTableHtml(finops);
  }

  const schemaChip = document.getElementById("feedback-schema-version-chip");
  if (schemaChip) {
    const schemaVer = result.schema_version || "1.2.0";
    schemaChip.textContent = `Schema v${schemaVer} • HITL Flywheel`;
  }
  const fbBanner = document.getElementById("feedback-status-banner");
  if (fbBanner) {
    fbBanner.classList.add("hidden");
    fbBanner.innerHTML = "";
  }
}

function scrollActiveFilmstripThumbIntoView(alignToTop = true) {
  const list = document.getElementById("slide-filmstrip-list");
  if (!list) return;
  const activeThumb = list.querySelector(".m3-slide-thumb.active");
  if (!activeThumb) return;
  if (alignToTop) {
    const listRect = list.getBoundingClientRect();
    const thumbRect = activeThumb.getBoundingClientRect();
    const offsetInContainer = thumbRect.top - listRect.top;
    list.scrollTo({
      top: Math.max(0, list.scrollTop + offsetInContainer - 8),
      behavior: "smooth",
    });
  } else {
    activeThumb.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function renderRequirementJumpBar(slides) {
  const bar = document.getElementById("req-quick-jump-bar");
  if (!bar) return;
  bar.innerHTML = `<span class="m3-req-jump-label">Jump to:</span>`;

  const activeReq =
    state.activeSlideIdx === -1
      ? "__COVER__"
      : String(slides[state.activeSlideIdx]?.req_number || "");

  const addJumpPill = (label, targetSlideIdx, isActive) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `m3-req-jump-pill${isActive ? " active" : ""}`;
    btn.textContent = label;
    btn.addEventListener("click", () => {
      hideConstructionAnimationStage();
      state.activeSlideIdx = targetSlideIdx;
      renderFilmstrip(slides);
      renderActiveSlide(targetSlideIdx);
      scrollActiveFilmstripThumbIntoView(true);
    });
    bar.appendChild(btn);
  };

  addJumpPill("Cover", -1, activeReq === "__COVER__");

  const seenReqs = new Map();
  slides.forEach((s, idx) => {
    const reqKey = String(s.req_number || "").trim();
    if (!reqKey || seenReqs.has(reqKey)) return;
    seenReqs.set(reqKey, idx);
  });

  seenReqs.forEach((slideIdx, reqKey) => {
    const pillLabel =
      reqKey === "Overview" || reqKey === "Sources" ? reqKey : `Req ${reqKey}`;
    addJumpPill(pillLabel, slideIdx, activeReq === reqKey);
  });
}

function renderFilmstrip(slides) {
  const list = document.getElementById("slide-filmstrip-list");
  if (!list) return;
  list.classList.remove("hidden");
  list.innerHTML = "";
  renderRequirementJumpBar(slides);

  const q = (state.filmstripQuery || "").trim().toLowerCase();
  const quizOnly = Boolean(state.filterQuizSlidesOnly);

  // Slide 1: Cover Slide item
  if (!quizOnly && (!q || "slide 1 cover title badge".includes(q) || (state.currentResult?.badge_name || "").toLowerCase().includes(q))) {
    const coverThumb = document.createElement("div");
    coverThumb.className = `m3-slide-thumb ${state.activeSlideIdx === -1 ? "active" : ""}`;
    const coverImgUrl = state.currentResult?.pamphlet_cover_url || state.currentResult?.badge_emblem_url || "";
    coverThumb.innerHTML = `
      <div class="m3-thumb-top">
        <span>Slide 1 &bull; Cover</span>
        <span class="m3-thumb-archetype">Title &amp; Badge</span>
      </div>
      <div class="m3-thumb-row-flex">
        <div class="m3-thumb-title" style="flex:1; min-width:0;">${escapeHtml(state.currentResult?.badge_name || "")} Merit Badge</div>
        ${coverImgUrl ? `<img class="m3-thumb-mini-img" src="${escapeHtml(coverImgUrl)}" alt="Cover" loading="lazy" />` : ""}
      </div>
    `;
    coverThumb.addEventListener("click", () => {
      hideConstructionAnimationStage();
      state.activeSlideIdx = -1;
      renderFilmstrip(slides);
      renderActiveSlide(-1);
    });
    list.appendChild(coverThumb);
  }

  slides.forEach((s, idx) => {
    const arch = String(s.archetype || "");
    const isQuiz = arch === "SOCRATIC_CHECKPOINT_QUIZ" || /quiz|checkpoint|scenario/i.test(s.title || "");
    if (quizOnly && !isQuiz) return;

    const hasReqDef = Boolean(s.verbatim_requirement_text && s.verbatim_requirement_text.trim());
    const hasImg = Boolean(s.diagram_url);
    const hasHero = Boolean(s.ai_hero_image_path);
    const isHidden = Boolean(s.hidden);
    const isCustom = Boolean(s.is_custom_slide);
    const kindLabel =
      s.req_number === "Overview" || s.req_number === "Sources"
        ? s.req_number
        : isCustom
        ? "Custom"
        : isQuiz
        ? "Patrol Quiz"
        : hasReqDef
        ? "Req Intro"
        : hasImg
        ? "Diagram"
        : "Teaching";
    if (q) {
      const haystack = `slide ${idx + 2} req ${s.req_number || ""} ${kindLabel} ${arch} ${s.title || ""}`.toLowerCase();
      if (!haystack.includes(q)) return;
    }

    let archBadgeText = "";
    if (isHidden) archBadgeText = "👁️‍🗨️ Hidden";
    else if (isCustom) archBadgeText = "📍 Custom";
    else if (isQuiz) archBadgeText = "❓ Quiz";
    else if (arch === "WORKED_EXAMPLE_TEMPLATE") archBadgeText = "📋 Worked Example";
    else if (s.safety_warning) archBadgeText = "⚠️ Safety";
    else if (hasImg) archBadgeText = "📐 Diagram";

    const choices = typeof getSlideSpecificImageChoices === "function" ? getSlideSpecificImageChoices(s) : [];
    const activeChoicePos = choices.length >= 2
      ? Math.max(1, choices.findIndex((c) => (c.image_path && c.image_path === s.diagram_path) || (c.image_url && c.image_url === s.diagram_url)) + 1)
      : 1;
    const choicePillHtml = choices.length >= 2
      ? `<span class="m3-thumb-imgcount-pill" title="${choices.length} curated visuals available for this slide">🖼️ ${activeChoicePos}/${choices.length}</span>`
      : "";

    const thumb = document.createElement("div");
    thumb.className = `m3-slide-thumb ${idx === state.activeSlideIdx ? "active" : ""} ${isHidden ? "hidden-slide" : ""}`;
    const badgeFlags = `${hasHero ? " ✨" : ""}`;
    thumb.innerHTML = `
      <div class="m3-thumb-top">
        <span>Slide ${idx + 2} &bull; ${s.req_number === "Overview" || s.req_number === "Sources" ? escapeHtml(s.req_number) : "Req " + escapeHtml(s.req_number || "")}</span>
        <span class="m3-thumb-archetype">${escapeHtml(kindLabel)}${badgeFlags}</span>
      </div>
      <div class="m3-thumb-row-flex">
        <div style="flex:1; min-width:0;">
          <div class="m3-thumb-title">${escapeHtml(s.title || "")}</div>
          <div class="m3-thumb-badges-row">
            ${archBadgeText ? `<span class="m3-thumb-arch-pill">${archBadgeText}</span>` : ""}
            ${choicePillHtml}
          </div>
        </div>
        ${hasImg ? `<img class="m3-thumb-mini-img" src="${escapeHtml(s.diagram_url)}" alt="" loading="lazy" />` : ""}
      </div>
    `;
    thumb.addEventListener("click", () => {
      hideConstructionAnimationStage();
      state.activeSlideIdx = idx;
      renderFilmstrip(slides);
      renderActiveSlide(idx);
    });
    list.appendChild(thumb);
  });
}

function resolveSlidePaletteTokens(slide, deckTier) {
  const tier = String(slide?.beautification_tier || deckTier || "BEAUTIFIED").toUpperCase();
  if (tier === "STANDARD") {
    return {
      tier: "STANDARD",
      isBeautified: false,
      isStudio: false,
      stageBg: "#FFFFFF",
      textFg: "#0F172A",
      subTextFg: "#334155",
      primaryHex: "#003F87",
      accentHex: "#CBD5E1",
      cardBg: "#F1F5F9",
      badgeBg: "#E2E8F0",
      badgeFg: "#334155",
      stageBorder: "2px solid #CBD5E1",
      headerBg: "transparent",
      footerColor: "#64748B",
    };
  }
  const paletteKey = String(slide?.accent_palette_key || "NAVY_GOLD").toUpperCase();
  const tplProf = state.activeTemplateProfile;
  if (paletteKey === "MATCH_TEMPLATE" && tplProf && tplProf.template_id !== "default_workbench") {
    if (tier === "STUDIO") {
      return {
        tier: "STUDIO",
        isBeautified: true,
        isStudio: true,
        stageBg: "#0F172A",
        textFg: "#F8FAFC",
        subTextFg: "#E2E8F0",
        primaryHex: "#38BDF8",
        accentHex: tplProf.accent_hex || "#F4C430",
        cardBg: "#1E293B",
        badgeBg: "#1E293B",
        badgeFg: tplProf.accent_hex || "#F4C430",
        stageBorder: `3px solid ${tplProf.accent_hex || "#F4C430"}`,
        headerBg: "linear-gradient(90deg, rgba(30,41,59,0.92) 0%, rgba(15,23,42,0.92) 100%)",
        footerColor: "#94A3B8",
      };
    }
    return {
      tier: "BEAUTIFIED",
      isBeautified: true,
      isStudio: false,
      stageBg: "#FAF8F5",
      textFg: "#0F172A",
      subTextFg: "#334155",
      primaryHex: tplProf.primary_hex || "#003F87",
      accentHex: tplProf.accent_hex || "#D4AF37",
      cardBg: tplProf.card_bg_hex || "#EFF6FF",
      badgeBg: "#FEF3C7",
      badgeFg: "#92400E",
      stageBorder: `2.5px solid ${tplProf.accent_hex || "#D4AF37"}`,
      headerBg: "linear-gradient(90deg, rgba(7,86,151,0.07) 0%, rgba(212,175,55,0.12) 100%)",
      footerColor: "#64748B",
    };
  }
  if (tier === "STUDIO") {
    const studioAccents = {
      NAVY_GOLD: { primaryHex: "#38BDF8", accentHex: "#F4C430" },
      OLIVE_FOREST: { primaryHex: "#4ADE80", accentHex: "#A3E635" },
      EAGLE_CRIMSON: { primaryHex: "#FB7185", accentHex: "#F4C430" },
      SLATE_ACTION: { primaryHex: "#60A5FA", accentHex: "#38BDF8" },
    };
    const st = studioAccents[paletteKey] || studioAccents.NAVY_GOLD;
    return {
      tier: "STUDIO",
      isBeautified: true,
      isStudio: true,
      stageBg: "#0F172A",
      textFg: "#F8FAFC",
      subTextFg: "#E2E8F0",
      primaryHex: st.primaryHex,
      accentHex: st.accentHex,
      cardBg: "#1E293B",
      badgeBg: "#1E293B",
      badgeFg: st.accentHex,
      stageBorder: `3px solid ${st.accentHex}`,
      headerBg: "linear-gradient(90deg, rgba(30,41,59,0.92) 0%, rgba(15,23,42,0.92) 100%)",
      footerColor: "#94A3B8",
    };
  }
  const map = {
    NAVY_GOLD: {
      primaryHex: "#003F87",
      accentHex: "#D4AF37",
      cardBg: "#EFF6FF",
      badgeBg: "#FEF3C7",
      badgeFg: "#92400E",
      headerBg: "linear-gradient(90deg, rgba(0,63,135,0.06) 0%, rgba(212,175,55,0.12) 100%)",
    },
    OLIVE_FOREST: {
      primaryHex: "#2E4600",
      accentHex: "#4B5320",
      cardBg: "#F1F8E9",
      badgeBg: "#DCFCE7",
      badgeFg: "#166534",
      headerBg: "linear-gradient(90deg, rgba(46,70,0,0.06) 0%, rgba(75,83,32,0.12) 100%)",
    },
    EAGLE_CRIMSON: {
      primaryHex: "#8B0000",
      accentHex: "#CE1126",
      cardBg: "#FFF5F5",
      badgeBg: "#FEE2E2",
      badgeFg: "#991B1B",
      headerBg: "linear-gradient(90deg, rgba(139,0,0,0.06) 0%, rgba(206,17,38,0.12) 100%)",
    },
    SLATE_ACTION: {
      primaryHex: "#0F172A",
      accentHex: "#005AE0",
      cardBg: "#F0F9FF",
      badgeBg: "#DBEAFE",
      badgeFg: "#1E40AF",
      headerBg: "linear-gradient(90deg, rgba(15,23,42,0.06) 0%, rgba(0,90,224,0.12) 100%)",
    },
  };
  const chosen = map[paletteKey] || map.NAVY_GOLD;
  return {
    tier: "BEAUTIFIED",
    isBeautified: true,
    isStudio: false,
    stageBg: "#FAF8F5",
    textFg: "#0F172A",
    subTextFg: "#334155",
    primaryHex: chosen.primaryHex,
    accentHex: chosen.accentHex,
    cardBg: chosen.cardBg,
    badgeBg: chosen.badgeBg,
    badgeFg: chosen.badgeFg,
    stageBorder: `2.5px solid ${chosen.accentHex}`,
    headerBg: chosen.headerBg,
    footerColor: "#64748B",
  };
}

const DANGLING_TAIL_WORDS_JS = new Set([
  "and", "or", "with", "to", "for", "in", "on", "of", "by", "the", "a", "an",
  "that", "which", "while", "when", "if", "from", "into", "at", "as", "such",
  "including", "through", "during", "before", "after", "under", "over", "between",
]);

function conciseCardBody(bodyText, maxWords = 24, maxChars = 150) {
  const cleaned = String(bodyText || "").trim();
  if (!cleaned) return "";
  const words = cleaned.split(/\s+/);
  if (words.length <= maxWords && cleaned.length <= maxChars) {
    return cleaned;
  }
  const seps = [
    ". ",
    "; ",
    " — ",
    " – ",
    ", which ",
    ", while ",
    ", ensuring ",
    ", allowing ",
    ", including ",
    ", such as ",
    ", especially ",
    " so that ",
    " in order to ",
  ];
  for (const sep of seps) {
    if (cleaned.includes(sep)) {
      const head = cleaned.split(sep)[0].trim().replace(/[,;:\-]+$/, "");
      const headWords = head.split(/\s+/);
      if (headWords.length >= 6 && headWords.length <= maxWords && head.length <= maxChars) {
        return /[.!?]$/.test(head) ? head : `${head}.`;
      }
    }
  }
  const capped = words.slice(0, maxWords);
  while (capped.length > 6 && capped.join(" ").length > maxChars) {
    capped.pop();
  }
  while (
    capped.length > 6 &&
    DANGLING_TAIL_WORDS_JS.has(capped[capped.length - 1].toLowerCase().replace(/^[,;:\-.()]+|[,;:\-.()]+$/g, ""))
  ) {
    capped.pop();
  }
  let res = capped.join(" ").replace(/[,;:\-(]+$/, "");
  const openParens = (res.match(/\(/g) || []).length;
  const closeParens = (res.match(/\)/g) || []).length;
  if (openParens > closeParens && res.lastIndexOf("(") > 0) {
    res = res.slice(0, res.lastIndexOf("(")).trim().replace(/[,;:\-]+$/, "");
  }
  if (res && !/[.!?]$/.test(res)) {
    res += ".";
  }
  return res;
}

function renderActiveSlide(idx) {
  const res = state.currentResult;
  if (!res) return;
  state.activeSlideIdx = idx;
  const slides = res.storyboard?.slides || [];
  const totalSlides = slides.length + 1;
  const deckTier = String(res.beautification_tier || document.getElementById("beautification-select")?.value || "BEAUTIFIED").toUpperCase();
  const audienceLevel = res.audience_level || document.getElementById("audience-select")?.value || "All Scouts (Ages 11–17)";

  const stageEl = document.getElementById("widescreen-slide-stage");
  const headerBand = document.getElementById("stage-header-band");
  const magBadge = document.getElementById("stage-magazine-badge");
  const reqStripBox = document.getElementById("stage-req-strip-box");
  const leftZone = document.getElementById("stage-left-cards");
  const rightZone = document.getElementById("stage-right-visual");
  const visSourceBadge = document.getElementById("stage-visual-source-badge");
  const splitContainer = document.getElementById("stage-body-split");
  const imgEl = document.getElementById("stage-diagram-img");
  const capEl = document.getElementById("stage-diagram-caption");
  const safetyBar = document.getElementById("stage-safety-bar");
  const safetyText = document.getElementById("stage-safety-text");
  const notesEl = document.getElementById("stage-presenter-notes");
  const codesignBar = document.getElementById("slide-codesign-bar");
  const themeChip = document.getElementById("active-slide-theme-chip");
  const audienceChip = document.getElementById("active-slide-audience-chip");
  const groundedChip = document.getElementById("active-slide-grounded-chip");
  const footerLeft = document.getElementById("stage-footer-left");
  const footerRight = document.getElementById("stage-footer-right");

  if (audienceChip) {
    audienceChip.textContent = `👥 ${audienceLevel}`;
  }

  const counselorName = document.getElementById("input-counselor-name")?.value || "Scoutmaster Bob";
  const troopName = document.getElementById("input-troop-name")?.value || "Troop 123, My Council";
  const locationOrZip =
    (document.getElementById("input-counselor-location")?.value || "").trim() ||
    res.counselor_info?.location_or_zip ||
    res.deep_research_enrichment?.resolved_location?.region_label ||
    "";
  const email = document.getElementById("input-counselor-email")?.value || "";
  const phone = document.getElementById("input-counselor-phone")?.value || "";

  // Case A: Slide 1 (Cover Slide with Badge Emblem, Centered Title, Pamphlet Cover, and Counselor Info — No Boxes!)
  const fsCounterEl =
    document.getElementById("fullscreen-hud-status") ||
    document.getElementById("fullscreen-hud-counter");
  if (idx === -1) {
    const coverTokens = resolveSlidePaletteTokens(null, deckTier);
    document.getElementById("active-slide-index-chip").textContent = `Slide 1 of ${totalSlides}`;
    document.getElementById("active-slide-req-chip").textContent = "Cover Slide";
    if (fsCounterEl) fsCounterEl.textContent = `Slide 1 of ${totalSlides} • Cover Slide`;
    if (themeChip) themeChip.textContent = `🎨 ${formatSlideThemeLabel(deckTier)}`;
    groundedChip?.classList.add("hidden");
    magBadge?.classList.add("hidden");
    visSourceBadge?.classList.add("hidden");
    document.getElementById("stage-visual-pill-popover")?.classList.add("hidden");
    syncUnderstageDrawerVisibility(-1);
    if (stageEl) {
      stageEl.style.background = coverTokens.stageBg;
      stageEl.style.border = coverTokens.stageBorder;
    }
    if (headerBand) {
      headerBand.style.borderTop = "none";
      headerBand.style.background = "transparent";
    }

    document.getElementById("stage-slide-title").textContent = "";
    const reqNumChip = document.getElementById("stage-req-number");
    if (reqNumChip) reqNumChip.style.display = "none";
    if (footerLeft) {
      footerLeft.textContent = `Scouts BSA ${res.badge_name} Merit Badge`;
      footerLeft.style.color = coverTokens.footerColor;
    }
    if (footerRight) {
      footerRight.textContent = `${totalSlides} Slides`;
      footerRight.style.color = coverTokens.footerColor;
    }

    if (reqStripBox) reqStripBox.style.display = "none";
    safetyBar?.classList.add("hidden");

    const customLogoUrl = state.customLogoUrl || res.custom_troop_logo_url || "";
    const titleColor = coverTokens.isStudio ? "#F8FAFC" : "#003F87";
    const subColor = coverTokens.isStudio ? (res.is_eagle_required ? "#F4C430" : "#4ADE80") : (res.is_eagle_required ? "#CE1126" : "#4B5320");
    const labelColor = coverTokens.isStudio ? "#38BDF8" : "#003F87";
    const unitLabelColor = coverTokens.isStudio ? "#F4C430" : "#4B5320";
    const bodyTextColor = coverTokens.textFg;

    if (leftZone) {
      leftZone.style.display = "flex";
      leftZone.style.justifyContent = "space-between";
      leftZone.innerHTML = `
        <div style="display:flex; align-items:center; gap:24px; padding:12px 8px;">
          ${
            res.patch_url
              ? `<img src="${escapeHtml(`${res.patch_url}${res.patch_url.includes("?") ? "&" : "?"}v=20261016c`)}" alt="Badge Emblem" style="width:116px; height:116px; object-fit:contain; flex-shrink:0;" />`
              : ""
          }
          <div style="flex:1; text-align:center;">
            <div style="font-size:2.1rem; font-weight:800; color:${titleColor}; line-height:1.15;">${escapeHtml(res.badge_name)}</div>
            <div style="font-size:1.15rem; font-weight:700; margin-top:6px; color:${subColor};">
              ${res.is_eagle_required ? "Eagle-Required Merit Badge" : "Scouts BSA Merit Badge"}
            </div>
          </div>
        </div>
        <div style="display:flex; align-items:center; justify-content:space-between; gap:18px; padding:16px 8px; text-align:left;">
          <div style="flex:1;">
            <div style="font-size:1.22rem; font-weight:800; color:${labelColor}; margin-bottom:6px;">Counselor: ${escapeHtml(counselorName)}</div>
            <div style="font-size:1.05rem; color:${bodyTextColor}; margin-bottom:5px;"><strong style="color:${unitLabelColor};">Unit / Council:</strong> ${escapeHtml(troopName)}</div>
            ${locationOrZip ? `<div style="font-size:0.98rem; color:${bodyTextColor}; margin-bottom:4px;"><strong style="color:${unitLabelColor};">Location:</strong> ${escapeHtml(locationOrZip)}</div>` : ""}
            ${email ? `<div style="font-size:0.98rem; color:${bodyTextColor}; margin-bottom:4px;"><strong style="color:${labelColor};">Email:</strong> ${escapeHtml(email)}</div>` : ""}
            ${phone ? `<div style="font-size:0.98rem; color:${bodyTextColor};"><strong style="color:${labelColor};">Phone:</strong> ${escapeHtml(phone)}</div>` : ""}
          </div>
          ${
            customLogoUrl
              ? `<img src="${escapeHtml(customLogoUrl)}" alt="Troop Custom Logo" style="width:92px; height:92px; object-fit:contain; flex-shrink:0;" />`
              : ""
          }
        </div>
      `;
    }

    if (rightZone && res.cover_url) {
      rightZone.style.display = "flex";
      rightZone.style.border = "none";
      rightZone.style.background = "transparent";
      if (splitContainer) splitContainer.style.gridTemplateColumns = "1.2fr 0.8fr";
      if (imgEl) {
        imgEl.src = res.cover_url;
        imgEl.alt = `${res.badge_name} Official Pamphlet Cover`;
        imgEl.style.maxHeight = "340px";
      }
      if (capEl) {
        capEl.textContent = "";
      }
    } else if (rightZone) {
      rightZone.style.display = "none";
      if (splitContainer) splitContainer.style.gridTemplateColumns = "1fr";
    }

    if (notesEl) {
      const eagleNote = res.is_eagle_required
        ? `As an Eagle-Required Merit Badge, ${res.badge_name} builds lifelong citizenship, safety, and outdoor leadership skills you will use on every troop outing.`
        : `The ${res.badge_name} Merit Badge gives our patrol a great chance to explore a hands-on field through practical exercises and real-world observation.`;
      const defaultCoverNotes = `[SAY] Welcome to our ${res.badge_name} Merit Badge session, Scouts! [Point to the Counselor Contact card on screen] My name is ${counselorName} with ${troopName}, and when you reach out by email (${email || "via unit leadership"}) or phone with questions or workbook logs, remember our BSA Youth Protection and Two-Deep Leadership rule: always copy a parent, guardian, or another registered adult leader. ${eagleNote} [Hold up a Blue Card and sample ${res.badge_name} Workbook] Today we will work through the official requirements together using these slides, hands-on skill stations, and your printable ${res.badge_name} Merit Badge Workbook.`;
      const coverNotes = res._polishedCoverNotes || defaultCoverNotes;
      const coverNotesHtml = formatSpeakerNotesHtml(coverNotes);
      notesEl.innerHTML = coverNotesHtml;
      const fsTeleContent = document.getElementById("fullscreen-teleprompter-content");
      if (fsTeleContent) fsTeleContent.innerHTML = coverNotesHtml;
      if (typeof window.syncNotesPolishProvenancePill === "function") {
        window.syncNotesPolishProvenancePill({
          isPolished: Boolean(res._polishedCoverNotes),
          polishSource: res._coverPolishSource || "",
          cacheHit: Boolean(res._coverPolishCacheHit),
          fallbackReason: res._coverPolishFallbackReason || "",
        });
      }
    }
    document.getElementById("stage-patrol-scoreboard")?.classList.add("hidden");
    if (typeof window.renderSlideTemplateOverlay === "function") {
      window.renderSlideTemplateOverlay(true, null);
    }
    syncPresenterViewWindow();
    fitActiveSlideToStage();
    return;
  }

  // Case B: Content Slides (idx = 0 .. slides.length - 1)
  const slide = slides[idx];
  if (!slide) return;

  const archetype = slide.archetype || "SPLIT_VISUAL_EXPLAINER";
  const scoreboardEl = document.getElementById("stage-patrol-scoreboard");
  if (scoreboardEl) {
    const showScoreboard = archetype === "SOCRATIC_CHECKPOINT_QUIZ" || Boolean(state.patrolScoreboardVisible);
    scoreboardEl.classList.toggle("hidden", !showScoreboard);
  }
  const hideSlideBtn = document.getElementById("btn-toggle-hide-slide");
  if (hideSlideBtn) {
    hideSlideBtn.textContent = slide.hidden ? "👁️ Unhide Slide" : "👁️ Hide Slide";
  }
  const visTheme = slide.visual_theme || "NUMBERED_STEP_CARDS";
  const tokens = resolveSlidePaletteTokens(slide, deckTier);
  const reqLabel =
    slide.req_number === "Overview" || slide.req_number === "Sources"
      ? slide.req_number
      : `Requirement ${slide.req_number || idx + 1}`;

  document.getElementById("active-slide-index-chip").textContent = `Slide ${idx + 2} of ${totalSlides}`;
  document.getElementById("active-slide-req-chip").textContent = reqLabel;
  if (fsCounterEl) fsCounterEl.textContent = `Slide ${idx + 2} of ${totalSlides} • ${reqLabel}`;
  if (themeChip) themeChip.textContent = `🎨 ${formatSlideThemeLabel(tokens.tier)} • ${visTheme}`;
  groundedChip?.classList.add("hidden");

  // Sync Per-Slide Under-Stage Drawer & Quick-Edit fields
  syncUnderstageDrawerVisibility(idx);
  const qeTitle = document.getElementById("quickedit-slide-title");
  const qeCaption = document.getElementById("quickedit-slide-caption");
  const qeBullets = document.getElementById("quickedit-slide-bullets");
  const qeNotes = document.getElementById("quickedit-slide-notes");
  if (qeTitle) qeTitle.value = slide.title || "";
  if (qeCaption) qeCaption.value = slide.visual_caption || "";
  if (qeBullets) qeBullets.value = (slide.bullet_points || []).join("\n");
  if (qeNotes) qeNotes.value = slide.presenter_notes || "";

  const archSel = document.getElementById("codesign-archetype-select");
  const thmSel = document.getElementById("codesign-theme-select");
  const palSel = document.getElementById("codesign-palette-select");
  const srcSel = document.getElementById("codesign-source-select");
  const validArchs = [
    "SPLIT_VISUAL_EXPLAINER",
    "STEP_BY_STEP_PROCEDURE_4CARD",
    "DIFFERENTIAL_COMPARISON_2COL",
    "GEAR_CHECKLIST_GRID",
    "REQUIREMENTS_TRIAGE_MATRIX",
    "WORKED_EXAMPLE_TEMPLATE",
    "SOCRATIC_CHECKPOINT_QUIZ",
    "CONCEPT_TEXT_SLIDE",
    "FULL_BLEED_IMAGE_EXPLAINER",
    "REQUIREMENT_INTRO",
  ];
  const themeAliasMap = {
    NUMBERED_STEP_RIBBON: "NUMBERED_STEP_CARDS",
    THREE_PILLAR_ACCENT_CARDS: "THREE_PILLAR_BENTO",
    MAGAZINE_ASYMMETRIC_SPLIT: "THREE_PILLAR_BENTO",
    ANNOTATED_INFOGRAPHIC_STAGE: "EDITORIAL_CALLOUT_QUOTE",
    SAFETY_ALERT_SPOTLIGHT: "SAFETY_ALERT_SPLIT",
  };
  const normTheme = themeAliasMap[visTheme] || visTheme;
  if (archSel) archSel.value = validArchs.includes(archetype) ? archetype : "SPLIT_VISUAL_EXPLAINER";
  if (thmSel) thmSel.value = normTheme && thmSel.querySelector(`option[value="${normTheme}"]`) ? normTheme : "NUMBERED_STEP_CARDS";
  if (palSel) palSel.value = slide.accent_palette_key || "NAVY_GOLD";
  if (srcSel) {
    srcSel.value =
      archetype === "CONCEPT_TEXT_SLIDE" || (!slide.diagram_url && slide.visual_source_label?.includes("None"))
        ? "none"
        : slide.ai_hero_image_path
        ? "ai_hero"
        : "keep_current";
  }
  populateQuickImageSwitcher(slide);

  // Apply Layer-0 Magazine Vector Card Header, Stage Background & Border
  if (stageEl) {
    stageEl.style.background = tokens.stageBg;
    stageEl.style.border = tokens.stageBorder;
  }
  const titleEl = document.getElementById("stage-slide-title");
  if (titleEl) {
    titleEl.textContent = slide.title || "";
    titleEl.style.color = tokens.isStudio ? "#F8FAFC" : tokens.primaryHex;
  }
  if (headerBand) {
    headerBand.style.borderTop = tokens.isBeautified ? `6px solid ${tokens.accentHex}` : "none";
    headerBand.style.background = tokens.headerBg;
  }
  if (magBadge) {
    if (tokens.isBeautified) {
      magBadge.classList.remove("hidden");
      const badgeLabel = slide.callout_badge_text || visTheme;
      magBadge.innerHTML = `<span style="display:inline-block; background:${tokens.badgeBg}; color:${tokens.badgeFg}; border:1px solid ${tokens.accentHex}; font-size:0.72rem; font-weight:700; padding:2px 10px; border-radius:999px;">🎨 ${escapeHtml(formatSlideThemeLabel(tokens.tier).toUpperCase())} &bull; ${escapeHtml(badgeLabel)}</span>`;
    } else {
      magBadge.classList.add("hidden");
    }
  }

  const reqNumChip = document.getElementById("stage-req-number");
  if (reqNumChip) reqNumChip.style.display = "none";
  if (footerLeft) {
    footerLeft.textContent = `Scouts BSA ${res.badge_name} Merit Badge`;
    footerLeft.style.color = tokens.footerColor;
  }
  if (footerRight) {
    footerRight.textContent = `Slide ${idx + 2} of ${totalSlides} • ${reqLabel}`;
    footerRight.style.color = tokens.footerColor;
  }

  // Show the Requirement Definition strip when verbatim_requirement_text is non-empty
  const hasVerbatimReq = Boolean(slide.verbatim_requirement_text && slide.verbatim_requirement_text.trim());
  const reqHeaderLabel = slide.req_number === "Overview" ? "Curriculum & Local Context" : `Official ${reqLabel}`;
  if (reqStripBox) {
    if (hasVerbatimReq) {
      reqStripBox.style.display = "flex";
      reqStripBox.style.borderColor = tokens.accentHex;
      reqStripBox.style.background = tokens.isBeautified ? tokens.cardBg : "#FFFFFF";
      document.getElementById("stage-req-verbatim").innerHTML = `<strong style="color:${tokens.primaryHex};">${escapeHtml(reqHeaderLabel)}:</strong> <span style="color:${tokens.textFg};">${escapeHtml(slide.verbatim_requirement_text)}</span>`;
    } else {
      reqStripBox.style.display = "none";
    }
  }

  const hasVisual = Boolean(slide.diagram_url);
  const hideVisualForIntro =
    archetype === "CONCEPT_TEXT_SLIDE" ||
    archetype === "SOURCES_AND_REFERENCES" ||
    archetype === "REQUIREMENTS_TRIAGE_MATRIX" ||
    (archetype === "REQUIREMENT_INTRO" && !tokens.isBeautified);
  const isSplitWithReqBanner = hasVerbatimReq && hasVisual && !hideVisualForIntro;

  // Resolve per-card styling & prefix for all 6 Magazine Card Themes
  function getCardThemeSpec(bpIdx) {
    let style = tokens.isBeautified
      ? `background:${tokens.cardBg}; border:1.5px solid ${tokens.accentHex}; border-left:6px solid ${tokens.primaryHex}; color:${tokens.textFg}; box-shadow:0 3px 10px rgba(15,23,42,0.08);`
      : `background:#F1F5F9; border:1px solid #CBD5E1; color:#0F172A;`;
    let anchorColor = tokens.primaryHex;
    let bodyColor = tokens.subTextFg;
    let prefix = "";

    if (isSplitWithReqBanner) {
      style += " padding:9px 12px;";
    }

    if (!tokens.isBeautified) {
      return { style, anchorColor, bodyColor, prefix };
    }

    if (normTheme === "DARK_SLATE_SPOTLIGHT") {
      style = `background:#1E293B; border:1.5px solid #F4C430; border-left:6px solid #38BDF8; color:#F8FAFC; box-shadow:0 4px 12px rgba(15,23,42,0.22);${isSplitWithReqBanner ? " padding:9px 12px;" : ""}`;
      anchorColor = "#F4C430";
      bodyColor = "#E2E8F0";
      prefix = `<span style="color:#38BDF8; font-weight:900; margin-right:6px;">★</span>`;
    } else if (normTheme === "SAFETY_ALERT_SPLIT") {
      const sBg = tokens.isStudio ? "#311018" : "#FFF1F2";
      const sBorder = tokens.isStudio ? "#FB7185" : "#CE1126";
      style = `background:${sBg}; border:1.5px solid ${sBorder}; border-left:6px solid ${sBorder}; color:${tokens.textFg}; box-shadow:0 3px 10px rgba(206,17,38,0.10);${isSplitWithReqBanner ? " padding:9px 12px;" : ""}`;
      anchorColor = sBorder;
      prefix = `<span style="display:inline-block; background:${sBorder}; color:#FFFFFF; font-size:0.70rem; font-weight:800; padding:1px 6px; border-radius:5px; margin-right:6px;">⚠️ SAFETY</span>`;
    } else if (normTheme === "TIMELINE_CHEVRON_CARDS") {
      style = `background:${tokens.cardBg}; border:1.5px solid ${tokens.accentHex}; border-left:6px solid ${tokens.primaryHex}; color:${tokens.textFg};${isSplitWithReqBanner ? " padding:9px 12px;" : ""}`;
      prefix = `<span style="display:inline-block; background:${tokens.badgeBg}; color:${tokens.badgeFg}; border:1px solid ${tokens.accentHex}; font-family:'JetBrains Mono',monospace; font-size:0.71rem; font-weight:800; padding:1px 7px; border-radius:999px; margin-right:7px;">STEP ${bpIdx + 1} &#10140;</span>`;
    } else if (normTheme === "EDITORIAL_CALLOUT_QUOTE") {
      const qBg = tokens.isStudio ? "#1E293B" : "#FFFBEB";
      style = `background:${qBg}; border:1.5px solid #F59E0B; border-left:6px solid #D97706; color:${tokens.textFg};${isSplitWithReqBanner ? " padding:9px 12px;" : ""}`;
      anchorColor = tokens.isStudio ? "#FBBF24" : "#B45309";
      prefix = `<span style="color:${anchorColor}; font-size:1.05rem; font-weight:900; margin-right:6px;">&#10077;</span>`;
    } else if (normTheme === "THREE_PILLAR_BENTO") {
      style = `background:${tokens.cardBg}; border:1.5px solid ${tokens.accentHex}; border-top:5px solid ${tokens.primaryHex}; color:${tokens.textFg}; box-shadow:0 3px 10px rgba(15,23,42,0.08);${isSplitWithReqBanner ? " padding:9px 12px;" : ""}`;
      prefix = `<span style="color:${tokens.accentHex}; font-weight:900; margin-right:6px;">◆</span>`;
    } else {
      // NUMBERED_STEP_CARDS (default)
      const numFg = tokens.isStudio ? "#0F172A" : "#FFFFFF";
      prefix = `<span style="display:inline-block; background:${tokens.primaryHex}; color:${numFg}; font-family:'JetBrains Mono',monospace; font-size:0.73rem; font-weight:700; padding:1px 7px; border-radius:6px; margin-right:7px;">0${bpIdx + 1}</span>`;
    }
    return { style, anchorColor, bodyColor, prefix };
  }

  // Populate Teaching Points / Cards in Left Zone with 100% parity with pptx_builder.py
  leftZone.innerHTML = "";
  leftZone.style.justifyContent = "flex-start";
  const baseCardSpec = getCardThemeSpec(0);
  const rawBullets = slide.bullet_points || [];
  const bullets = isSplitWithReqBanner && rawBullets.length > 4 ? rawBullets.slice(0, 4) : rawBullets;

  if (archetype === "DIFFERENTIAL_COMPARISON_2COL") {
    const midIdx = Math.max(1, Math.ceil(bullets.length / 2));
    const cmp = slide.comparison_data || {
      left_header: "Primary Condition / Method A",
      left_points: bullets.slice(0, midIdx),
      right_header: "Contrast Condition / Method B",
      right_points: bullets.slice(midIdx).length ? bullets.slice(midIdx) : ["Compare key field differences and safety actions."],
    };
    const grid = document.createElement("div");
    grid.className = "m3-slide-2col-grid";
    const rightBg = tokens.isStudio ? "#311018" : "#FFF5F5";
    const rightAnchor = tokens.isStudio ? "#FB7185" : "#CE1126";
    grid.innerHTML = `
      <div class="m3-slide-card-item" style="border-top: 4px solid ${tokens.primaryHex}; background:${tokens.cardBg}; color:${tokens.textFg};">
        <div class="m3-slide-card-anchor" style="color:${tokens.primaryHex};">${escapeHtml(cmp.left_header || "Concept A")}</div>
        ${(cmp.left_points || []).map((pt) => `<div class="m3-slide-card-text" style="margin-top:4px; color:${tokens.subTextFg};">&bull; ${escapeHtml(pt)}</div>`).join("")}
      </div>
      <div class="m3-slide-card-item" style="border-top: 4px solid ${rightAnchor}; background:${rightBg}; color:${tokens.textFg};">
        <div class="m3-slide-card-anchor" style="color:${rightAnchor};">${escapeHtml(cmp.right_header || "Concept B")}</div>
        ${(cmp.right_points || []).map((pt) => `<div class="m3-slide-card-text" style="margin-top:4px; color:${tokens.subTextFg};">&bull; ${escapeHtml(pt)}</div>`).join("")}
      </div>
    `;
    leftZone.appendChild(grid);
  } else if (archetype === "REQUIREMENTS_TRIAGE_MATRIX") {
    function parseTriageColumnItems(rawStr, fallbackStr) {
      let s = String(rawStr || fallbackStr || "").trim();
      s = s.replace(/^(Knowledge & Concepts|Hands-On Field Skills|Field & Home Prerequisites)\s*\(\d+\)\s*:\s*/i, "");
      s = s.replace(/\.$/, "");
      const parts = s.includes(";")
        ? s.split(/\s*;\s*/)
        : s.split(/\)\s*,\s*(?=Req\s)/i);
      return parts
        .map((p) => {
          let item = p.trim();
          if (item.includes("(") && !item.endsWith(")") && !s.includes(";")) item += ")";
          const mParen = item.match(/^(Req\s+[0-9a-zA-Z]+)\s*\((.+)\)$/i);
          if (mParen) return { req: mParen[1], desc: mParen[2].trim() };
          const mDash = item.match(/^(Req\s+[0-9a-zA-Z]+)\s*[-:]\s*(.+)$/i);
          if (mDash) return { req: mDash[1], desc: mDash[2].trim() };
          return { req: "", desc: item };
        })
        .filter((it) => it.req || it.desc)
        .slice(0, 4);
    }
    const colSpecs = [
      {
        header: "Discussion & Core Theory",
        color: tokens.isStudio ? tokens.primaryHex : "#003F87",
        bg: tokens.isStudio ? tokens.cardBg : "#EDF4FF",
        items: parseTriageColumnItems(bullets[0], "Review core principles."),
      },
      {
        header: "Hands-On Skill Demonstrations",
        color: tokens.isStudio ? "#4ADE80" : "#4A5D23",
        bg: tokens.isStudio ? tokens.cardBg : "#F2F5EC",
        items: parseTriageColumnItems(bullets[1], "Practice hands-on demonstrations."),
      },
      {
        header: "Field & Home Prerequisites",
        color: tokens.isStudio ? "#F4C430" : "#CE1126",
        bg: tokens.isStudio ? tokens.cardBg : "#FFF5F5",
        items: parseTriageColumnItems(bullets[2], "Complete field logs and observations."),
      },
    ];
    const grid3 = document.createElement("div");
    grid3.style.cssText = "display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; width:100%;";
    grid3.innerHTML = colSpecs
      .map(
        (col) => `
        <div class="m3-slide-card-item" style="border:1.5px solid ${col.color}; border-top:5px solid ${col.color}; background:${col.bg}; color:${tokens.textFg};">
          <div class="m3-slide-card-anchor" style="color:${col.color}; margin-bottom:6px;">${escapeHtml(col.header)}</div>
          ${col.items
            .map((it) =>
              it.req
                ? `<div class="m3-slide-card-text" style="color:${tokens.subTextFg}; margin-top:3px;">&bull; <strong style="color:${tokens.textFg};">${escapeHtml(it.req)}</strong> - ${escapeHtml(it.desc)}</div>`
                : `<div class="m3-slide-card-text" style="color:${tokens.subTextFg}; margin-top:3px;">&bull; ${escapeHtml(it.desc)}</div>`
            )
            .join("")}
        </div>`
      )
      .join("");
    leftZone.appendChild(grid3);
    if (bullets[3]) {
      const localCard = document.createElement("div");
      localCard.className = "m3-slide-card-item";
      localCard.style.cssText = `${baseCardSpec.style} margin-top:8px;`;
      localCard.innerHTML = `<div class="m3-slide-card-text" style="color:${baseCardSpec.bodyColor};">📍 ${escapeHtml(bullets[3])}</div>`;
      leftZone.appendChild(localCard);
    }
  } else if (
    (archetype === "STEP_BY_STEP_PROCEDURE_4CARD" || archetype === "GEAR_CHECKLIST_GRID") &&
    bullets.length >= 2
  ) {
    const grid2x2 = document.createElement("div");
    grid2x2.className = "m3-slide-2col-grid";
    bullets.slice(0, 6).forEach((bp, bpIdx) => {
      const cSpec = getCardThemeSpec(bpIdx);
      const colonParts = String(bp).split(":");
      const badgeTag =
        archetype === "STEP_BY_STEP_PROCEDURE_4CARD"
          ? `<span style="display:inline-block; background:${cSpec.anchorColor}; color:${tokens.isStudio ? "#0F172A" : "#FFFFFF"}; font-family:'JetBrains Mono',monospace; font-size:0.72rem; font-weight:700; padding:1px 7px; border-radius:6px; margin-right:6px;">STEP ${bpIdx + 1}</span>`
          : `<span style="color:${cSpec.anchorColor}; font-weight:800; margin-right:6px;">[✓]</span>`;
      let inner = "";
      if (colonParts.length >= 3 && colonParts[1].trim().split(/\s+/).length <= 7) {
        const anchor = colonParts[1].trim();
        const body = conciseCardBody(colonParts.slice(2).join(":").trim());
        inner = `<div class="m3-slide-card-anchor" style="color:${cSpec.anchorColor};">${badgeTag}${escapeHtml(anchor)}</div>
                 <div class="m3-slide-card-text" style="color:${cSpec.bodyColor};">${escapeHtml(body)}</div>`;
      } else if (colonParts.length >= 2 && colonParts[0].trim().length <= 52) {
        const body = conciseCardBody(colonParts.slice(1).join(":").trim());
        inner = `<div class="m3-slide-card-anchor" style="color:${cSpec.anchorColor};">${badgeTag}${escapeHtml(colonParts[0].trim())}</div>
                 <div class="m3-slide-card-text" style="color:${cSpec.bodyColor};">${escapeHtml(body)}</div>`;
      } else {
        inner = `<div class="m3-slide-card-text" style="color:${cSpec.bodyColor};">${badgeTag}${escapeHtml(conciseCardBody(bp))}</div>`;
      }
      const itemEl = document.createElement("div");
      itemEl.className = "m3-slide-card-item";
      itemEl.style.cssText = cSpec.style;
      itemEl.innerHTML = inner;
      grid2x2.appendChild(itemEl);
    });
    leftZone.appendChild(grid2x2);
  } else if (archetype === "WORKED_EXAMPLE_TEMPLATE") {
    const fallbackFields = {};
    bullets.slice(0, 4).forEach((bp, i) => {
      const cIdx = bp.indexOf(":");
      if (cIdx > 0 && cIdx < 48) {
        fallbackFields[bp.slice(0, cIdx).trim()] = bp.slice(cIdx + 1).trim();
      } else {
        fallbackFields[`Step ${i + 1}`] = bp;
      }
    });
    const we = slide.worked_example || {
      title: `Worked Example — ${reqLabel}`,
      fields: fallbackFields,
      counselor_tip: "Bring your completed written notes or field log to your counselor review.",
    };
    const fieldsHtml = Object.entries(we.fields || fallbackFields)
      .map(
        ([k, v], i) => {
          const cSpec = getCardThemeSpec(i);
          return `
        <div class="m3-slide-card-item" style="padding:8px 12px; ${cSpec.style}">
          <span style="font-weight:700; color:${cSpec.anchorColor};">${cSpec.prefix}${escapeHtml(k)}:</span>
          <span class="m3-slide-card-text" style="color:${cSpec.bodyColor};"> ${escapeHtml(String(v))}</span>
        </div>`;
        }
      )
      .join("");
    leftZone.innerHTML = `
      <div class="m3-chip m3-chip-gold" style="align-self:flex-start;">📋 ${escapeHtml(we.title || "Worked Example & Counselor Pro-Tip")}</div>
      ${fieldsHtml}
    `;
  } else if (archetype === "SOCRATIC_CHECKPOINT_QUIZ") {
    const qz = slide.quiz_item || {
      scenario_prompt: bullets[0] || `How should your patrol apply ${reqLabel} safely in the field?`,
      options: bullets.slice(1, 4).length
        ? bullets.slice(1, 4)
        : [
            "Follow the step-by-step BSA pamphlet procedure and verify with your buddy.",
            "Rely on guesswork without checking field safety conditions.",
          ],
      correct_answer: "Option A — Follow official BSA pamphlet procedure",
      explanation: "Grounded in the official Scouts BSA Merit Badge Pamphlet and Guide to Safe Scouting.",
    };
    const isQuizRevealed = state.revealedQuizSlides.has(idx);
    const correctLetterMatch = String(qz.correct_answer || "Option A").match(/Option\s+([A-D])/i);
    const correctOptIdx = correctLetterMatch ? correctLetterMatch[1].toUpperCase().charCodeAt(0) - 65 : 0;

    leftZone.innerHTML = `
      <div class="m3-slide-card-item" style="background:${tokens.cardBg}; border:2px solid ${tokens.primaryHex}; color:${tokens.textFg};">
        <div class="m3-slide-card-anchor" style="color:${tokens.primaryHex}; justify-content:space-between;">
          <span>❓ Patrol Scenario Challenge</span>
          <span style="font-size:0.70rem; font-weight:700; opacity:0.85;">Click an option to test your patrol!</span>
        </div>
        <div class="m3-slide-card-text" style="color:${tokens.subTextFg};">${escapeHtml(qz.scenario_prompt || "")}</div>
      </div>
      ${(qz.options || [])
        .map((opt, i) => {
          const revealedClass = isQuizRevealed && i === correctOptIdx ? " quiz-selected-correct" : "";
          return `<div class="m3-slide-card-item m3-quiz-option-card${revealedClass}" data-quiz-opt-idx="${i}" style="${baseCardSpec.style}"><strong style="color:${baseCardSpec.anchorColor};">Option ${String.fromCharCode(65 + i)}:</strong> <span style="color:${baseCardSpec.bodyColor};">${escapeHtml(opt)}</span></div>`;
        })
        .join("")}
      <button type="button" class="m3-quiz-reveal-btn ${isQuizRevealed ? "hidden" : ""}" id="btn-reveal-quiz-answer">
        👁️ Reveal Verified Answer &amp; Explanation
      </button>
      <div class="m3-slide-card-item ${isQuizRevealed ? "" : "hidden"}" id="quiz-verified-answer-card" style="background:${tokens.isStudio ? "#064E3B" : "#DCFCE7"}; border:1.5px solid #15803D; color:${tokens.textFg};">
        <div class="m3-slide-card-anchor" style="color:${tokens.isStudio ? "#4ADE80" : "#15803D"};">✓ Verified Answer: ${escapeHtml(qz.correct_answer || "")}</div>
        <div class="m3-slide-card-text" style="color:${tokens.subTextFg};">${escapeHtml(qz.explanation || "")}</div>
      </div>
    `;

    const revealQuiz = (clickedIdx = -1) => {
      state.revealedQuizSlides.add(idx);
      document.getElementById("btn-reveal-quiz-answer")?.classList.add("hidden");
      document.getElementById("quiz-verified-answer-card")?.classList.remove("hidden");
      leftZone.querySelectorAll(".m3-quiz-option-card").forEach((cardEl) => {
        const optIdx = parseInt(cardEl.getAttribute("data-quiz-opt-idx") || "-1", 10);
        if (optIdx === correctOptIdx) {
          cardEl.classList.add("quiz-selected-correct");
        } else if (optIdx === clickedIdx) {
          cardEl.classList.add("quiz-selected-wrong");
        }
      });
      fitActiveSlideToStage();
    };

    document.getElementById("btn-reveal-quiz-answer")?.addEventListener("click", () => revealQuiz(-1));
    leftZone.querySelectorAll(".m3-quiz-option-card").forEach((cardEl) => {
      cardEl.addEventListener("click", () => {
        const optIdx = parseInt(cardEl.getAttribute("data-quiz-opt-idx") || "-1", 10);
        revealQuiz(optIdx);
      });
    });
  } else {
    bullets.forEach((bp, bpIdx) => {
      const cSpec = getCardThemeSpec(bpIdx);
      const card = document.createElement("div");
      card.className = "m3-slide-card-item";
      card.style.cssText = cSpec.style;
      const colonIdx = bp.indexOf(":");
      const isSourcesSlide = archetype === "SOURCES_AND_REFERENCES";
      if (colonIdx > 0 && colonIdx < 52) {
        const anchor = bp.slice(0, colonIdx);
        const rawRest = bp.slice(colonIdx + 1).trim();
        const rest = isSourcesSlide ? rawRest : conciseCardBody(rawRest);
        card.innerHTML = `
          <div class="m3-slide-card-anchor" style="color:${cSpec.anchorColor};">${cSpec.prefix}${escapeHtml(anchor)}</div>
          <div class="m3-slide-card-text" style="color:${cSpec.bodyColor};">${escapeHtml(rest)}</div>
        `;
      } else {
        const bodyTxt = isSourcesSlide ? bp : conciseCardBody(bp);
        card.innerHTML = `<div class="m3-slide-card-text" style="color:${cSpec.bodyColor};">${cSpec.prefix}${escapeHtml(bodyTxt)}</div>`;
      }
      leftZone.appendChild(card);
    });
  }

  // Right Zone Visual & Responsive Split / Full-Width / Full-Bleed Stage
  if (rightZone) {
    if (tokens.isStudio) {
      rightZone.style.background = "#1E293B";
      rightZone.style.border = `2px solid ${tokens.accentHex}`;
      if (capEl) capEl.style.color = "#E2E8F0";
    } else if (tokens.isBeautified) {
      rightZone.style.background = tokens.cardBg;
      rightZone.style.border = `1.5px solid ${tokens.accentHex}`;
      if (capEl) capEl.style.color = "#334155";
    } else {
      rightZone.style.background = "#F8FAFC";
      rightZone.style.border = "1px solid #CBD5E1";
      if (capEl) capEl.style.color = "#475569";
    }
  }

  renderStageVisualPillAndPopover(slide, tokens, hasVisual, hideVisualForIntro);
  document.getElementById("btn-stage-zoom-image")?.classList.toggle("hidden", !hasVisual || hideVisualForIntro);

  if (!hasVisual || hideVisualForIntro) {
    if (rightZone) rightZone.style.display = "none";
    if (leftZone) leftZone.style.display = "flex";
    if (splitContainer) splitContainer.style.gridTemplateColumns = "1fr";
  } else if (archetype === "FULL_BLEED_IMAGE_EXPLAINER") {
    if (leftZone) leftZone.style.display = "none";
    if (rightZone) rightZone.style.display = "flex";
    if (splitContainer) splitContainer.style.gridTemplateColumns = "1fr";
    if (imgEl) {
      imgEl.src = `${slide.diagram_url}${slide.diagram_url.includes("?") ? "&" : "?"}v=3`;
      imgEl.alt = slide.visual_caption || slide.title || "Merit Badge Diagram";
      imgEl.style.maxHeight = "310px";
    }
    if (capEl) {
      capEl.textContent = slide.visual_caption || (slide.bullet_points && slide.bullet_points[0]) || slide.title || "";
    }
  } else {
    if (leftZone) leftZone.style.display = "flex";
    if (rightZone) rightZone.style.display = "flex";
    if (splitContainer) splitContainer.style.gridTemplateColumns = "minmax(0, 1.15fr) minmax(0, 0.85fr)";
    if (imgEl) {
      imgEl.src = `${slide.diagram_url}${slide.diagram_url.includes("?") ? "&" : "?"}v=3`;
      imgEl.alt = slide.visual_caption || slide.title || "Merit Badge Diagram";
      imgEl.style.maxHeight = "250px";
    }
    if (capEl) {
      capEl.textContent = slide.visual_caption || slide.title || "";
    }
  }

  // Safety bar: show ONLY when the slide has an explicit safety warning
  if (slide.safety_warning) {
    safetyBar?.classList.remove("hidden");
    if (safetyText) safetyText.textContent = `Guide to Safe Scouting: ${slide.safety_warning}`;
  } else {
    safetyBar?.classList.add("hidden");
  }

  // Counselor Teaching Notes
  const formattedNotes = formatSpeakerNotesHtml(slide.presenter_notes || "");
  if (notesEl) {
    notesEl.innerHTML = formattedNotes;
  }
  if (typeof window.syncNotesPolishProvenancePill === "function") {
    window.syncNotesPolishProvenancePill({
      isPolished: Boolean(slide._isPolishedNotes),
      polishSource: slide._polishSource || "",
      cacheHit: Boolean(slide._polishCacheHit),
      fallbackReason: slide._polishFallbackReason || "",
    });
  }
  const fsTeleContent = document.getElementById("fullscreen-teleprompter-content");
  if (fsTeleContent) {
    fsTeleContent.innerHTML = formattedNotes || "<em>No speaker notes for this slide.</em>";
  }

  if (imgEl && !imgEl.dataset.fitBound) {
    imgEl.dataset.fitBound = "1";
    imgEl.addEventListener("load", () => fitActiveSlideToStage());
  }
  applyQuizRevealMaskIfEnabled(slide);
  syncArchetypeVisualPicker(slide.archetype);
  if (typeof window.renderSlideTemplateOverlay === "function") {
    window.renderSlideTemplateOverlay(false, tokens);
  }
  syncPresenterViewWindow();
  fitActiveSlideToStage();
}

function isSlideStageOverflowing(stageEl) {
  if (stageEl.scrollHeight > stageEl.clientHeight + 2) return true;
  const splitEl = stageEl.querySelector(".m3-slide-body-split");
  const leftEl = document.getElementById("stage-left-cards") || document.getElementById("slide-left-zone");
  const rightEl = document.getElementById("stage-right-visual") || document.getElementById("slide-right-visual");
  if (splitEl && splitEl.scrollHeight > splitEl.clientHeight + 2) return true;
  if (leftEl && leftEl.scrollHeight > leftEl.clientHeight + 2) return true;
  if (rightEl && !rightEl.classList.contains("hidden") && rightEl.scrollHeight > rightEl.clientHeight + 2) return true;

  const safetyBar = document.getElementById("stage-safety-bar") || document.getElementById("slide-safety-bar");
  const footerStrip = stageEl.querySelector(".m3-slide-footer-strip");
  const bottomBoundaryEl = (safetyBar && !safetyBar.classList.contains("hidden")) ? safetyBar : footerStrip;
  if (bottomBoundaryEl && splitEl) {
    const boundaryTop = bottomBoundaryEl.getBoundingClientRect().top;
    const splitBottom = splitEl.getBoundingClientRect().bottom;
    if (splitBottom > boundaryTop + 1) return true;
    if (leftEl && leftEl.lastElementChild) {
      const lastBottom = leftEl.lastElementChild.getBoundingClientRect().bottom;
      if (lastBottom > boundaryTop - 2) return true;
    }
  }
  return false;
}

function fitActiveSlideToStage() {
  const stageEl = document.getElementById("widescreen-slide-stage");
  if (!stageEl || stageEl.offsetParent === null) return;

  // Reset density classes and height overrides so we measure against the true 16:9 stage
  stageEl.classList.remove("slide-density-compact", "slide-density-ultra-compact");
  stageEl.style.aspectRatio = "16 / 9";
  stageEl.style.height = "auto";
  stageEl.style.minHeight = "410px";

  if (isSlideStageOverflowing(stageEl)) {
    stageEl.classList.add("slide-density-compact");
  }
  if (isSlideStageOverflowing(stageEl)) {
    stageEl.classList.add("slide-density-ultra-compact");
  }
  if (isSlideStageOverflowing(stageEl)) {
    // Guarantee zero vertical cropping on extra-dense slides or narrow laptop viewports
    const targetMinH = Math.max(410, Math.round(stageEl.clientWidth * (9 / 16)));
    stageEl.style.minHeight = `${targetMinH}px`;
    stageEl.style.aspectRatio = "auto";
    stageEl.style.height = "auto";
  }
}

window.addEventListener("resize", () => {
  fitActiveSlideToStage();
});

function formatSpeakerNotesHtml(rawNotes) {
  const lines = String(rawNotes || "")
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines
    .map((line) => {
      let decorated = escapeHtml(line)
        .replace(/\[SAY\]/g, '<span class="m3-cue-tag">[SAY]</span>')
        .replace(/\[DEMONSTRATE\]/g, '<span class="m3-cue-tag" style="background:#E2EDC8;color:#151E00;">[DEMONSTRATE]</span>')
        .replace(/\[ASK SCOUTS\]/g, '<span class="m3-cue-tag" style="background:#FEF3C7;color:#B45309;">[ASK SCOUTS]</span>');

      // Render Markdown bold (**term** as well as slightly mismatched *term** or **term*) as clean <strong> tags without asterisks
      decorated = decorated
        .replace(/\*{1,2}([^*\n]{2,110}?)\*{2}/g, "<strong>$1</strong>")
        .replace(/\*{2}([^*\n]{2,110}?)\*{1,2}/g, "<strong>$1</strong>");

      decorated = decorated.replace(
        /\[Expected Answer:\s*([^\]]+)\]/gi,
        '<div class="m3-expected-answer-box"><strong>✓ Expected Answer:</strong> $1</div>'
      );

      decorated = decorated.replace(
        /\[((?!SAY\]|DEMONSTRATE\]|ASK SCOUTS\])[^\]]{3,160})\]/g,
        '<span class="m3-stage-cue-pill">🎬 [$1]</span>'
      );

      return `<div style="margin-bottom:8px;">${decorated}</div>`;
    })
    .join("");
}

function renderTriageMatrix(research, pamphletUrl, drgUrl) {
  const reqs = research.requirements || [];
  const slides = state.currentResult?.storyboard?.slides || [];
  const pdfLink = document.getElementById("link-pamphlet-pdf");
  const drgLink = document.getElementById("link-drg-hub");
  if (pdfLink) pdfLink.href = pamphletUrl || "#";
  if (drgLink) drgLink.href = drgUrl || "https://www.scouting.org/skills/merit-badges/";

  const inClass = reqs.filter((r) => (r.execution_mode || "IN_CLASS_DISCUSSION") === "IN_CLASS_DISCUSSION");
  const handsOn = reqs.filter((r) => r.execution_mode === "HANDS_ON_SKILL_STATION");
  const prereq = reqs.filter((r) => r.execution_mode === "PREREQUISITE_CAMPOUT_HOME");

  document.getElementById("count-in-class").textContent = String(inClass.length);
  document.getElementById("count-hands-on").textContent = String(handsOn.length);
  document.getElementById("count-prereq").textContent = String(prereq.length);

  const renderReqCards = (items) =>
    items
      .map((r) => {
        const reqStr = String(r.req_number || "").trim();
        const matchingSlideIndices = [];
        slides.forEach((s, idx) => {
          if (String(s.req_number || "").trim() === reqStr) {
            matchingSlideIndices.push(idx);
          }
        });
        const firstSlideIdx = matchingSlideIndices.length > 0 ? matchingSlideIndices[0] : 0;
        const slideCount = matchingSlideIndices.length;
        const edgePhase = r.edge_phase || (r.execution_mode === "HANDS_ON_SKILL_STATION" ? "Guide / Enable" : "Explain");
        const signoffText = r.counselor_signoff_criteria || "";
        return `
      <div class="m3-req-node-card">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:6px; flex-wrap:wrap;">
          <span class="m3-chip m3-chip-primary" style="font-size:0.72rem; padding:2px 8px;">Requirement ${escapeHtml(r.req_number)}</span>
          <span class="m3-chip m3-chip-secondary" style="font-size:0.66rem; padding:2px 7px;">EDGE: ${escapeHtml(edgePhase)}</span>
        </div>
        <div style="font-size:0.84rem; font-weight:600; color:var(--md-sys-color-on-surface); margin-top:4px;">${escapeHtml(r.req_text)}</div>
        ${
          signoffText
            ? `<div style="font-size:0.74rem; color:#475569; margin-top:3px;"><strong>Sign-Off:</strong> ${escapeHtml(signoffText)}</div>`
            : ""
        }
        ${
          r.safety_callout
            ? `<div style="font-size:0.75rem; color:#CE1126; font-weight:600; margin-top:4px;">&#9888; ${escapeHtml(r.safety_callout)}</div>`
            : ""
        }
        <button type="button" class="m3-req-jump-action-btn" data-jump-slide-idx="${firstSlideIdx}">
          <span>▶ Jump to Teaching Slides</span>
          <span style="font-family:var(--font-mono); font-size:0.70rem;">Slide ${firstSlideIdx + 2}${slideCount > 1 ? ` (${slideCount} slides)` : ""}</span>
        </button>
      </div>
    `;
      })
      .join("");

  document.getElementById("triage-col-in-class").innerHTML = renderReqCards(inClass);
  document.getElementById("triage-col-hands-on").innerHTML = renderReqCards(handsOn);
  document.getElementById("triage-col-prereq").innerHTML = renderReqCards(prereq);

  document.querySelectorAll(".m3-req-jump-action-btn[data-jump-slide-idx]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetIdx = parseInt(btn.getAttribute("data-jump-slide-idx") || "0", 10);
      switchMainTab("panel-storyboard");
      hideConstructionAnimationStage();
      state.activeSlideIdx = isNaN(targetIdx) ? 0 : targetIdx;
      renderFilmstrip(slides);
      renderActiveSlide(state.activeSlideIdx);
      scrollActiveFilmstripThumbIntoView(true);
      document.getElementById("slide-stage-toolbar")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ---------------------------------------------------------------------------
// Styled Markdown Renderer & FinOps Table Formatter
// ---------------------------------------------------------------------------
function formatInlineMarkdown(text) {
  let s = escapeHtml(text);
  // Links [label](url)
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color:var(--md-sys-color-primary); font-weight:600;">$1</a>');
  // Bold **text** (non-greedy across any inner characters)
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Italic *text*
  s = s.replace(/(^|\s)\*([^*]+)\*/g, "$1<em>$2</em>");
  // Inline code `code`
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  return s;
}

function renderMarkdownToStyledHtml(md) {
  const lines = String(md || "").split(/\r?\n/);
  const out = [];
  let inList = false;
  let inTable = false;
  let tableHeaderDone = false;

  const closeList = () => {
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
  };
  const closeTable = () => {
    if (inTable) {
      out.push("</tbody></table>");
      inTable = false;
      tableHeaderDone = false;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const trimmed = raw.trim();

    if (!trimmed) {
      closeList();
      closeTable();
      continue;
    }

    // Markdown table row
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      closeList();
      const cells = trimmed
        .slice(1, -1)
        .split("|")
        .map((c) => c.trim());
      if (cells.every((c) => /^[-:\s]+$/.test(c))) {
        continue;
      }
      if (!inTable) {
        out.push("<table><thead><tr>");
        cells.forEach((c) => out.push(`<th>${formatInlineMarkdown(c)}</th>`));
        out.push("</tr></thead><tbody>");
        inTable = true;
        tableHeaderDone = true;
      } else {
        out.push("<tr>");
        cells.forEach((c) => out.push(`<td>${formatInlineMarkdown(c)}</td>`));
        out.push("</tr>");
      }
      continue;
    } else {
      closeTable();
    }

    if (/^---+$/.test(trimmed)) {
      closeList();
      out.push("<hr/>");
      continue;
    }
    if (trimmed.startsWith("### ")) {
      closeList();
      out.push(`<h3>${formatInlineMarkdown(trimmed.slice(4))}</h3>`);
      continue;
    }
    if (trimmed.startsWith("## ")) {
      closeList();
      out.push(`<h2>${formatInlineMarkdown(trimmed.slice(3))}</h2>`);
      continue;
    }
    if (trimmed.startsWith("# ")) {
      closeList();
      out.push(`<h1>${formatInlineMarkdown(trimmed.slice(2))}</h1>`);
      continue;
    }
    if (trimmed.startsWith("> ")) {
      closeList();
      out.push(`<blockquote>${formatInlineMarkdown(trimmed.slice(2))}</blockquote>`);
      continue;
    }
    if (/^[-*]\s+/.test(trimmed)) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${formatInlineMarkdown(trimmed.replace(/^[-*]\s+/, ""))}</li>`);
      continue;
    }
    closeList();
    out.push(`<p>${formatInlineMarkdown(trimmed)}</p>`);
  }

  closeList();
  closeTable();
  return out.join("\n");
}

function renderFinopsTableHtml(finops) {
  if (!finops || typeof finops !== "object" || Object.keys(finops).length === 0) {
    return '<div style="padding:12px; color:#64748B; font-size:0.82rem;">No FinOps telemetry recorded for this session.</div>';
  }
  const estCost = Number(finops.estimated_cost_usd ?? finops.estimated_cached_usd ?? 0.14);
  const maxCap = Number(finops.max_budget_usd ?? finops.budget_ceiling_usd ?? 1.0);
  const headroom = Math.max(0, maxCap - estCost);
  const rerunCost = Number(finops.cached_rerun_cost_usd ?? 0.02);
  const withinBudget = finops.within_budget !== undefined ? Boolean(finops.within_budget) : estCost <= maxCap;
  const inTok = Number(finops.estimated_input_tokens ?? finops.input_tokens ?? 18500);
  const outTok = Number(finops.estimated_output_tokens ?? finops.output_tokens ?? 6200);
  const totalTok = inTok + outTok;
  const plannedImgs = Number(finops.planned_ai_hero_images ?? 0);
  const tierLbl = escapeHtml(formatSlideThemeLabel(finops.beautification_tier || "BEAUTIFIED"));
  const depthLbl = escapeHtml(String(finops.depth_mode || "Deep Dive / Camp School Deck"));
  const drEnabled = finops.enable_deep_research !== undefined ? Boolean(finops.enable_deep_research) : true;

  const statusBadge = withinBudget
    ? '<span style="background:#DCFCE7; color:#15803D; padding:3px 10px; border-radius:999px; font-weight:700; font-size:0.76rem;">✓ Within $1.00 Cap</span>'
    : '<span style="background:#FEE2E2; color:#B91C1C; padding:3px 10px; border-radius:999px; font-size:0.76rem; font-weight:700;">⚠️ Over Cap</span>';

  const structuredRows = [
    ["Budget Status", statusBadge],
    [
      "Estimated Deck Cost",
      `<span style="font-family:'JetBrains Mono',monospace; font-weight:800; color:#003F87; font-size:0.92rem;">$${estCost.toFixed(2)} USD</span>`,
    ],
    [
      "Per-Deck Budget Ceiling",
      `<span style="font-family:'JetBrains Mono',monospace; font-weight:700;">$${maxCap.toFixed(2)} USD</span> <span style="color:#15803D; font-size:0.78rem; font-weight:600;">($${headroom.toFixed(2)} headroom)</span>`,
    ],
    [
      "Cached Rerun Cost",
      `<span style="font-family:'JetBrains Mono',monospace; font-weight:700; color:#15803D;">$${rerunCost.toFixed(2)} USD</span> (75% ADK prefix discount)`,
    ],
    ["Slide Theme & Visuals", `<code>${tierLbl}</code> (${plannedImgs} hero graphics)`],
    ["Deck Depth Mode", depthLbl],
    ["Input Context Tokens", `<span style="font-family:'JetBrains Mono',monospace; font-weight:600;">${inTok.toLocaleString()}</span> tokens`],
    ["Output Generation Tokens", `<span style="font-family:'JetBrains Mono',monospace; font-weight:600;">${outTok.toLocaleString()}</span> tokens`],
    ["Total Token Footprint", `<strong style="font-family:'JetBrains Mono',monospace;">${totalTok.toLocaleString()} tokens</strong>`],
    ["Local Regional Grounding", drEnabled ? "Enabled (NOAA / Terrain / Field Sites)" : "Disabled"],
    ["On-Demand AI Image Rate", `<span style="font-family:'JetBrains Mono',monospace; font-weight:700;">$0.08 USD</span> / image (Consent Gate + Prompt Verifier)`],
  ];

  const rowsHtml = structuredRows
    .map(
      ([label, valHtml]) => `
        <tr>
          <td>${escapeHtml(label)}</td>
          <td>${valHtml}</td>
        </tr>
      `
    )
    .join("");

  return `
    <table class="m3-finops-table">
      <thead>
        <tr>
          <th>FinOps Metric</th>
          <th>Value</th>
        </tr>
      </thead>
      <tbody>${rowsHtml}</tbody>
    </table>
  `;
}

// ---------------------------------------------------------------------------
// Quick Image Switcher (◀ / Dropdown / ▶) & Merit Badge Image Studio Modal
// ---------------------------------------------------------------------------
function normalizeCatalogEntry(rawItem, defaultReq = "") {
  if (!rawItem) return null;
  if (typeof rawItem === "string") {
    const baseName = rawItem.split("/").pop() || "Visual";
    return {
      image_id: baseName,
      image_path: rawItem,
      image_url: rawItem.startsWith("/assets/") ? rawItem : `/assets/diagrams/${baseName}`,
      title: baseName,
      description: `Slide visual asset (${baseName})`,
      source_type: "OFFICIAL_PAMPHLET_FIGURE",
      req_number: defaultReq,
    };
  }
  if (typeof rawItem === "object") {
    return rawItem;
  }
  return null;
}

function stripUrlQuery(u) {
  return String(u || "").split("?")[0];
}

function normalizeReqBase(rStr) {
  const m = String(rStr || "").trim().match(/^(\d+)/);
  return m ? m[1] : String(rStr || "").trim().toLowerCase();
}

function registerChoiceOnSlide(slide, rawEntry) {
  if (!slide || !rawEntry) return;
  const entry = normalizeCatalogEntry(rawEntry, slide.req_number || "");
  if (!entry) return;
  if (!Array.isArray(slide.slide_image_choices)) {
    slide.slide_image_choices = [];
  }
  const key = stripUrlQuery(entry.image_url) || entry.image_path || entry.image_id;
  if (!key) return;
  const exists = slide.slide_image_choices.some(
    (c) => (stripUrlQuery(c?.image_url) || c?.image_path || c?.image_id) === key
  );
  if (!exists) {
    slide.slide_image_choices.push(entry);
  }
}

function getSlideSpecificImageChoices(slide) {
  if (!slide || !state.currentResult) return [];
  const rawCatalog = state.currentResult.badge_image_catalog;
  const badgeCatalog = Array.isArray(rawCatalog)
    ? rawCatalog
    : Array.isArray(rawCatalog?.images)
    ? rawCatalog.images
    : [];

  const byKey = new Map();
  badgeCatalog.forEach((raw) => {
    const entry = normalizeCatalogEntry(raw, slide.req_number || "");
    if (!entry) return;
    const uKey = stripUrlQuery(entry.image_url);
    const pKey = String(entry.image_path || "");
    if (uKey) byKey.set(uKey, entry);
    if (pKey) byKey.set(pKey, entry);
  });

  const choices = [];
  const seen = new Set();
  const addChoice = (rawCandidate) => {
    const entry = normalizeCatalogEntry(rawCandidate, slide.req_number || "");
    if (!entry) return;
    const uKey = stripUrlQuery(entry.image_url);
    const pKey = String(entry.image_path || "");
    const canonical = (uKey && byKey.get(uKey)) || (pKey && byKey.get(pKey)) || entry;
    const dedupKey = stripUrlQuery(canonical.image_url) || canonical.image_path || canonical.image_id;
    if (!dedupKey || seen.has(dedupKey)) return;
    seen.add(dedupKey);
    choices.push(canonical);
  };

  // 1. Start with server-seeded slide_image_choices if present
  if (Array.isArray(slide.slide_image_choices) && slide.slide_image_choices.length > 0) {
    slide.slide_image_choices.forEach(addChoice);
  }

  // 2. Ensure the slide's active diagram is included
  if (slide.diagram_url || slide.diagram_path) {
    addChoice({
      image_id: (slide.diagram_path || slide.diagram_url || "").split("/").pop(),
      image_path: slide.diagram_path || "",
      image_url: slide.diagram_url || "",
      title: slide.title || "Slide Visual",
      caption: slide.visual_caption || slide.title || "",
      description: slide.visual_caption || slide.title || "",
      source_label: slide.visual_source_label || "Slide Visual",
      source_type:
        String(slide.diagram_url || slide.diagram_path || "").includes("ai_illustrations")
          ? "NANO_BANANA_HERO"
          : "OFFICIAL_PAMPHLET_FIGURE",
      req_number: slide.req_number || "",
    });
  }

  // 3. Fallback / live merge from badgeCatalog for matching requirement pamphlet alternates & slide-specific uploads/AI/web
  const slideReq = String(slide.req_number || "").trim();
  const slideBase = normalizeReqBase(slideReq);
  const slideTitleClean = String(slide.title || "").trim().toLowerCase();
  const isReqIntro =
    String(slide.archetype || "").toUpperCase() === "REQUIREMENT_INTRO" ||
    Boolean(slide.verbatim_requirement_text && String(slide.verbatim_requirement_text).trim());

  badgeCatalog.forEach((raw) => {
    const entry = normalizeCatalogEntry(raw, slideReq);
    if (!entry) return;
    const st = String(entry.source_type || "").toUpperCase();
    const eReq = String(entry.req_number || "").trim();
    const eBase = normalizeReqBase(eReq);
    const eSlideTitle = String(entry.slide_title || "").trim().toLowerCase();

    if (st === "OFFICIAL_PAMPHLET_FIGURE" && !isReqIntro && Boolean(entry.is_alternate || raw.is_alternate)) {
      const pamphletCount = choices.filter(
        (c) => String(c.source_type || "").toUpperCase() === "OFFICIAL_PAMPHLET_FIGURE"
      ).length;
      if (pamphletCount < 3 && ((eReq && eReq === slideReq) || (eBase && eBase === slideBase))) {
        addChoice(entry);
      }
    } else if (["USER_UPLOAD", "NANO_BANANA_AI", "WEB_IMAGE_SEARCH"].includes(st)) {
      if (slideTitleClean && eSlideTitle && eSlideTitle === slideTitleClean) {
        addChoice(entry);
      }
    }
  });

  slide.slide_image_choices = choices;
  return choices;
}

let pillPopoverOutsideBound = false;
function ensurePillPopoverOutsideListener() {
  if (pillPopoverOutsideBound) return;
  pillPopoverOutsideBound = true;
  document.addEventListener("click", (ev) => {
    const pop = document.getElementById("stage-visual-pill-popover");
    const pill = document.getElementById("stage-visual-source-badge");
    if (!pop || pop.classList.contains("hidden")) return;
    if (pop.contains(ev.target) || (pill && pill.contains(ev.target))) return;
    pop.classList.add("hidden");
    const mainBtn = document.getElementById("stage-pill-main");
    if (mainBtn) mainBtn.setAttribute("aria-expanded", "false");
  });
}

async function selectSlideImageChoice(targetEntry) {
  if (!state.currentResult || state.activeSlideIdx < 0 || !targetEntry) return;
  const slides = state.currentResult.storyboard?.slides || [];
  const slide = slides[state.activeSlideIdx];
  if (!slide) return;

  const pop = document.getElementById("stage-visual-pill-popover");
  if (pop) pop.classList.add("hidden");

  const prevDiagramId = String(slide.diagram_path || slide.diagram_url || "").split("/").pop() || "";
  // Optimistic instant stage update before background PPTX regeneration completes
  const resolvedCaption =
    targetEntry.caption || targetEntry.description || targetEntry.title || slide.visual_caption || slide.title || "";
  if (targetEntry.image_url) {
    slide.diagram_url = targetEntry.image_url;
  }
  if (targetEntry.image_path) {
    slide.diagram_path = targetEntry.image_path;
  }
  slide.visual_caption = resolvedCaption;
  if (targetEntry.source_label) {
    slide.visual_source_label = targetEntry.source_label;
  }
  registerChoiceOnSlide(slide, targetEntry);
  renderActiveSlide(state.activeSlideIdx);

  // Anonymous Zero-PII image swap telemetry event
  fetch("/api/v1/admin/telemetry/image-swap", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      badge_name: state.currentResult.badge_name || "First Aid",
      req_number: String(slide.req_number || "1"),
      event_type: "counselor_visual_swap",
      from_image_id: prevDiagramId,
      to_image_id: String(targetEntry.image_id || targetEntry.image_url || ""),
    }),
  }).catch(() => {});

  await applyCatalogImageToActiveSlide(targetEntry, "custom_image");
}

async function cycleSlideImageChoice(delta) {
  if (!state.currentResult || state.activeSlideIdx < 0) return;
  const slides = state.currentResult.storyboard?.slides || [];
  const slide = slides[state.activeSlideIdx];
  if (!slide) return;
  const choices = getSlideSpecificImageChoices(slide);
  if (choices.length < 2) return;

  const currUrlClean = stripUrlQuery(slide.diagram_url);
  const currPath = String(slide.diagram_path || "");
  let activeIdx = choices.findIndex(
    (c) =>
      (currUrlClean && stripUrlQuery(c.image_url) === currUrlClean) ||
      (currPath && c.image_path && String(c.image_path) === currPath)
  );
  if (activeIdx < 0) activeIdx = 0;
  const nextIdx = (activeIdx + delta + choices.length) % choices.length;
  const nextEntry = choices[nextIdx];
  if (nextEntry) {
    await selectSlideImageChoice(nextEntry);
  }
}

function renderStageVisualPillAndPopover(slide, tokens, hasVisual, hideVisualForIntro) {
  ensurePillPopoverOutsideListener();
  const visSourceBadge = document.getElementById("stage-visual-source-badge");
  const visPopover = document.getElementById("stage-visual-pill-popover");
  if (!visSourceBadge) return;

  if (visPopover) {
    visPopover.classList.add("hidden");
    visPopover.innerHTML = "";
  }

  if (!hasVisual || hideVisualForIntro) {
    visSourceBadge.classList.add("hidden");
    return;
  }

  visSourceBadge.classList.remove("hidden");
  visSourceBadge.style.background = tokens.badgeBg || "#EFF6FF";
  visSourceBadge.style.color = tokens.badgeFg || "#003F87";
  visSourceBadge.style.border = `1px solid ${tokens.accentHex || "#003F87"}`;

  const choices = getSlideSpecificImageChoices(slide);
  const currUrlClean = stripUrlQuery(slide.diagram_url);
  const currPath = String(slide.diagram_path || "");
  let activeChoiceIdx = choices.findIndex(
    (c) =>
      (currUrlClean && stripUrlQuery(c.image_url) === currUrlClean) ||
      (currPath && c.image_path && String(c.image_path) === currPath)
  );
  if (activeChoiceIdx < 0) activeChoiceIdx = 0;
  const activeEntry = choices[activeChoiceIdx] || null;

  const srcLbl = String(activeEntry?.source_label || slide.visual_source_label || "");
  const srcType = String(activeEntry?.source_type || "").toUpperCase();
  const diagRef = String(activeEntry?.image_url || slide.diagram_url || slide.diagram_path || "");
  const isNano =
    srcType.includes("NANO_BANANA") ||
    srcLbl.includes("Nano Banana") ||
    diagRef.includes("_nano_hero") ||
    diagRef.includes("ai_illustrations");
  const isAiHero = !isNano && (srcType === "EDGE_CONCEPT_MAP" || Boolean(slide.ai_hero_image_path) || srcLbl.includes("EDGE Skill"));
  const isWeb = srcType === "WEB_IMAGE_SEARCH" || srcLbl.includes("Web Image") || srcLbl.includes("Wikimedia");
  const isUpload = srcType === "USER_UPLOAD" || srcLbl.includes("Uploaded");

  const basePillLabel = isNano
    ? "🍌 NANO BANANA AI ILLUSTRATION"
    : isUpload
    ? "📁 UPLOADED LOCAL IMAGE"
    : isWeb
    ? "🌐 WEB IMAGE CATALOG"
    : isAiHero
    ? "✨ EDGE SKILL CONCEPT MAP"
    : "📐 OFFICIAL PAMPHLET VISUAL";

  // Static Pill when only 1 designated image exists for this slide (with Admin quick-edit button when unlocked)
  if (choices.length <= 1) {
    visSourceBadge.className = "m3-stage-visual-pill is-static";
    if (state.isAdminSession) {
      visSourceBadge.innerHTML = `
        <span>${escapeHtml(basePillLabel)}</span>
        <button type="button" id="stage-pill-static-admin-btn" style="margin-left:6px; border:1px solid #93C5FD; background:#EFF6FF; color:#003F87; border-radius:999px; padding:1px 7px; font-size:0.65rem; font-weight:800; cursor:pointer;" title="Edit Caption or Replace Asset in Admin Studio">✏️ Admin</button>
      `;
      document.getElementById("stage-pill-static-admin-btn")?.addEventListener("click", (ev) => {
        ev.stopPropagation();
        openAdminStudioForSlideVisual(
          activeEntry || {
            image_id: (slide.diagram_path || slide.diagram_url || "").split("/").pop(),
            image_url: slide.diagram_url,
            image_path: slide.diagram_path,
            req_number: slide.req_number,
            caption: slide.visual_caption,
            title: slide.title,
          }
        );
      });
    } else {
      visSourceBadge.textContent = basePillLabel;
    }
    return;
  }

  // Option C Hybrid Interactive Pill when 2+ image choices exist for this slide
  visSourceBadge.className = "m3-stage-visual-pill is-interactive";
  visSourceBadge.innerHTML = `
    <button type="button" class="m3-stage-pill-arrow" id="stage-pill-prev" title="Previous image choice for this slide (${choices.length} available)" aria-label="Previous slide image choice">◀</button>
    <button type="button" class="m3-stage-pill-label-btn" id="stage-pill-main" title="Click to compare ${choices.length} image choices &amp; captions for this slide" aria-expanded="false">
      <span>${escapeHtml(basePillLabel)}</span>
      <span class="m3-stage-pill-count">(${activeChoiceIdx + 1}/${choices.length}) ▾</span>
    </button>
    <button type="button" class="m3-stage-pill-arrow" id="stage-pill-next" title="Next image choice for this slide (${choices.length} available)" aria-label="Next slide image choice">▶</button>
  `;

  const prevArrow = document.getElementById("stage-pill-prev");
  const nextArrow = document.getElementById("stage-pill-next");
  const mainBtn = document.getElementById("stage-pill-main");

  prevArrow?.addEventListener("click", (ev) => {
    ev.stopPropagation();
    cycleSlideImageChoice(-1);
  });
  nextArrow?.addEventListener("click", (ev) => {
    ev.stopPropagation();
    cycleSlideImageChoice(1);
  });

  if (visPopover) {
    const itemsHtml = choices
      .map((c, i) => {
        const cType = String(c.source_type || "").toUpperCase();
        const roleLabel =
          cType === "OFFICIAL_PAMPHLET_FIGURE"
            ? c.is_alternate
              ? `📐 Pamphlet Alternate #${c.alternate_rank || i}`
              : "📐 Primary Pamphlet Figure"
            : cType.includes("NANO_BANANA")
            ? "🍌 Nano Banana AI Illustration"
            : cType === "USER_UPLOAD"
            ? "📁 Uploaded Custom Image"
            : cType === "WEB_IMAGE_SEARCH"
            ? "🌐 Web Image Catalog"
            : "🖼️ Slide Visual";
        const capPreview = c.caption || c.description || c.title || "Official Merit Badge visual";
        const isCurrent = i === activeChoiceIdx;
        return `
          <button type="button" class="m3-pill-popover-item ${isCurrent ? "active" : ""}" data-pill-choice-idx="${i}" role="option" aria-selected="${isCurrent ? "true" : "false"}">
            <img class="m3-pill-popover-thumb" src="${escapeHtml(c.image_url || "")}" alt="${escapeHtml(c.title || roleLabel)}" loading="lazy" />
            <div class="m3-pill-popover-meta">
              <div class="m3-pill-popover-role">
                <span>[${i + 1}/${choices.length}] ${escapeHtml(roleLabel)}</span>
                ${
                  isCurrent
                    ? '<span style="color:#15803D; font-weight:900;">✓ Active</span>'
                    : '<span style="color:#64748B; font-weight:600;">Select</span>'
                }
              </div>
              <div class="m3-pill-popover-caption">${escapeHtml(capPreview)}</div>
            </div>
          </button>
        `;
      })
      .join("");

    visPopover.innerHTML = `
      <div class="m3-pill-popover-header">
        <span>Slide Image Choices (${choices.length})</span>
        <span>Req ${escapeHtml(String(slide.req_number || ""))}</span>
      </div>
      ${
        state.isAdminSession
          ? `<div class="m3-popover-admin-sticky-bar">
               <button type="button" class="m3-pill-popover-footer-btn" id="stage-pill-open-admin-btn" style="margin:0; background:#EFF6FF; color:#003F87; border-color:#93C5FD; font-weight:800;">
                 ✏️ Admin: Edit Caption / Promote to Primary
               </button>
             </div>`
          : ""
      }
      ${itemsHtml}
      <button type="button" class="m3-pill-popover-footer-btn" id="stage-pill-open-studio-btn">
        + Upload / Add Custom Image for This Slide…
      </button>
    `;

    visPopover.querySelectorAll("[data-pill-choice-idx]").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const cIdx = parseInt(btn.getAttribute("data-pill-choice-idx"), 10);
        const chosen = choices[cIdx];
        if (chosen) {
          selectSlideImageChoice(chosen);
        }
      });
    });

    document.getElementById("stage-pill-open-studio-btn")?.addEventListener("click", (ev) => {
      ev.stopPropagation();
      visPopover.classList.add("hidden");
      mainBtn?.setAttribute("aria-expanded", "false");
      document.getElementById("btn-open-image-studio")?.click();
    });

    document.getElementById("stage-pill-open-admin-btn")?.addEventListener("click", (ev) => {
      ev.stopPropagation();
      visPopover.classList.add("hidden");
      mainBtn?.setAttribute("aria-expanded", "false");
      openAdminStudioForSlideVisual(activeEntry || choices[0]);
    });

    mainBtn?.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const isHidden = visPopover.classList.toggle("hidden");
      mainBtn.setAttribute("aria-expanded", isHidden ? "false" : "true");
    });
  }
}

function populateQuickImageSwitcher(slide) {
  const quickSel = document.getElementById("codesign-quick-image-select");
  const prevBtn = document.getElementById("btn-prev-slide-image");
  const nextBtn = document.getElementById("btn-next-slide-image");
  if (!quickSel || !state.currentResult) return;

  const rawCatalog = state.currentResult.badge_image_catalog;
  const badgeCatalog = Array.isArray(rawCatalog)
    ? rawCatalog
    : Array.isArray(rawCatalog?.images)
    ? rawCatalog.images
    : [];
  const slideAvail = Array.isArray(slide?.available_images) ? slide.available_images : [];
  const merged = [];
  const seen = new Set();

  [...slideAvail, ...badgeCatalog].forEach((raw) => {
    const entry = normalizeCatalogEntry(raw, slide?.req_number || "");
    if (!entry) return;
    const key = stripUrlQuery(entry.image_url) || entry.image_path || entry.image_id;
    if (key && !seen.has(key)) {
      seen.add(key);
      merged.push(entry);
    }
  });

  state.badgeCatalogCache = merged;
  quickSel.innerHTML = "";

  const isNoneActive =
    !slide?.diagram_url || slide?.archetype === "CONCEPT_TEXT_SLIDE";
  const currUrlClean = stripUrlQuery(slide?.diagram_url);
  let matchedIdx = -1;

  merged.forEach((entry, idx) => {
    const opt = document.createElement("option");
    opt.value = String(idx);
    const st = String(entry.source_type || entry.source_kind || "").toUpperCase();
    const kindTag =
      st.includes("NANO_BANANA")
        ? "🍌 AI"
        : st.includes("UPLOAD")
        ? "📁 Upload"
        : st.includes("WEB")
        ? "🌐 Web"
        : st.includes("EDGE")
        ? "✨ EDGE"
        : "📐 BSA";
    const reqTag = entry.req_number ? `Req ${entry.req_number}: ` : "";
    opt.textContent = `[${idx + 1}/${merged.length}] ${kindTag} • ${reqTag}${entry.title || `Image ${idx + 1}`}`;
    if (!isNoneActive && currUrlClean && stripUrlQuery(entry.image_url) === currUrlClean) {
      opt.selected = true;
      matchedIdx = idx;
    }
    quickSel.appendChild(opt);
  });

  const removeOpt = document.createElement("option");
  removeOpt.value = "__NONE__";
  removeOpt.textContent = "🚫 None (Remove Graphic & Expand Text to Full Width)";
  if (isNoneActive) {
    removeOpt.selected = true;
  } else if (matchedIdx === -1 && merged.length > 0) {
    quickSel.selectedIndex = 0;
  }
  quickSel.appendChild(removeOpt);

  const labelEl = document.getElementById("codesign-quick-image-label");
  if (labelEl) {
    labelEl.textContent = `🖼️ Quick-Switch Slide Image (${merged.length} cached for ${state.currentResult.badge_name} — Selects Immediately)`;
  }
  if (prevBtn) prevBtn.disabled = merged.length === 0;
  if (nextBtn) nextBtn.disabled = merged.length === 0;
}

async function applyCatalogImageToActiveSlide(entry, visualSourceOverride = "custom_image") {
  if (!state.currentResult || state.activeSlideIdx < 0) return;
  const slides = state.currentResult.storyboard?.slides || [];
  const slide = slides[state.activeSlideIdx];
  if (!slide) return;

  if (visualSourceOverride === "custom_image" && entry) {
    registerChoiceOnSlide(slide, entry);
  }

  const archSel = document.getElementById("codesign-archetype-select");
  const thmSel = document.getElementById("codesign-theme-select");
  const palSel = document.getElementById("codesign-palette-select");

  let targetArch = archSel?.value || slide.archetype || "SPLIT_VISUAL_EXPLAINER";
  if (visualSourceOverride === "none") {
    targetArch = "CONCEPT_TEXT_SLIDE";
  } else if (
    targetArch === "CONCEPT_TEXT_SLIDE" ||
    targetArch === "SOURCES_AND_REFERENCES" ||
    targetArch === "REQUIREMENTS_TRIAGE_MATRIX"
  ) {
    targetArch = "SPLIT_VISUAL_EXPLAINER";
  }

  const fullCaption = entry ? `${entry.caption || entry.description || entry.title || ""}` : "";

  try {
    const resp = await fetch("/api/slide/regenerate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        badge_name: state.currentResult.badge_name,
        slide_index: state.activeSlideIdx,
        new_archetype: targetArch,
        new_visual_theme: thmSel?.value || slide.visual_theme || "NUMBERED_STEP_CARDS",
        new_accent_palette: palSel?.value || slide.accent_palette_key || "NAVY_GOLD",
        visual_source_mode: visualSourceOverride,
        custom_image_path: entry?.image_path || "",
        custom_image_caption: fullCaption,
        custom_image_source_label: entry?.source_label || entry?.attribution || "Badge Image Catalog",
        slide_data: slide,
        storyboard_slides: slides,
        counselor_info: state.currentResult.counselor_info,
        output_path: state.currentResult.output_path,
      }),
    });
    if (resp.ok) {
      const data = await resp.json();
      slide.archetype = data.new_archetype || targetArch;
      slide.visual_theme = data.new_visual_theme || slide.visual_theme;
      slide.accent_palette_key = data.new_accent_palette || slide.accent_palette_key;
      slide.visual_source_label = data.visual_source_label || slide.visual_source_label;
      slide.visual_caption = data.visual_caption || fullCaption || slide.visual_caption;
      slide.diagram_url = data.diagram_url || (entry?.image_url || "");
      slide.diagram_path = data.diagram_path || (entry?.image_path || "");
      slide.ai_hero_image_path = data.visual_source_mode === "ai_hero" ? data.diagram_path : null;
      if (data.updated_presenter_notes) {
        slide.presenter_notes = data.updated_presenter_notes;
      }
      if (data.pptx_download_url) {
        const dlBtn = document.getElementById("btn-download-pptx");
        if (dlBtn) dlBtn.href = data.pptx_download_url;
      }
      renderFilmstrip(slides);
      renderActiveSlide(state.activeSlideIdx);
    }
  } catch (err) {
    console.warn("Could not apply catalog image to slide:", err);
  }
}

function cleanSlideTopicBoilerplate(rawTitle) {
  let s = String(rawTitle || "").trim();
  s = s.replace(/\bRequirement\s+[0-9a-zA-Z()]+\s*:?\s*/gi, "");
  s = s.replace(
    /(\s*[:\-–—]\s*(Core Concepts & Definitions|Step-by-Step[^,;]*|Practical Field[^,;]*|Field Execution[^,;]*|Key Principles[^,;]*|Overview))+|(\s*,\s*Illustrated\b)|(\s*\(Illustrated\))/gi,
    ""
  );
  if (s.includes("(") && !s.includes(")")) {
    s = s.replace("(", "- ");
  }
  return s.replace(/\s+/g, " ").replace(/^[,:;\-–—\s]+|[,:;\-–—\s]+$/g, "");
}

function resolveClientSideContentAwareConfig(badgeName, slide, customPrompt = "", styleVal = "Auto (Content-Aware Mix)", humansMode = "auto", includeSlideContext = true) {
  const cleanTitle = includeSlideContext ? cleanSlideTopicBoilerplate(slide?.title || "") : "";
  const bullets = includeSlideContext && Array.isArray(slide?.bullet_points) ? slide.bullet_points : [];
  const bulletText = bullets.slice(0, 4).map((b) => cleanSlideTopicBoilerplate(String(b))).join(" ");
  const titlePromptLower = `${cleanTitle} ${customPrompt || ""}`.toLowerCase().trim();
  const combinedLower = includeSlideContext
    ? `${badgeName || ""} ${titlePromptLower} ${bulletText}`.toLowerCase()
    : titlePromptLower;
  const reqClean = includeSlideContext ? String(slide?.req_number || "1").trim().toLowerCase() : "";

  const noHumansPhrases = [
    "no humans", "no people", "without humans", "without people", "zero humans",
    "flat-lay", "flat lay", "knolling", "equipment only", "gear only", "pure equipment"
  ];
  const gearOrEnvKeywords = [
    "first-aid kit", "first aid kit", "survival kit", "emergency kit", "mess kit",
    "ten essentials", "10 essentials", "gear list", "packing list", "clothing",
    "footwear", "camp stove", "tent anatomy", "water filter", "cloud",
    "warm front", "cold front", "occluded front", "barometer", "anemometer",
    "hygrometer", "rain gauge", "weather map", "isobar", "water cycle",
    "acid rain", "greenhouse", "telescope", "constellation", "star chart",
    "solar system", "moon phase", "eclipse", "light pollution", "spectrum",
    "sensor", "actuator", "servo", "drivetrain", "circuit", "schematic",
    "cad ", "flowchart", "subsystem", "food web", "ecosystem", "watershed",
    "soil profile", "compost", "carbon footprint", "budget", "ledger",
    "compound interest", "saving vs", "personal vs", "kit supplies", "kit contents"
  ];
  const conceptMapKeywords = [
    "triage", "hurry cases", "prerequisite", "safe swim defense", "safety afloat",
    "leave no trace", "outdoor code", "tread lightly", "rights and duties",
    "four-step", "4-tier", "branches of", "three branches", "principles of"
  ];
  const proceduralKeywords = [
    "tourniquet", "windlass", "bleeding", "hemorrhage", "bandage", "sling",
    "splint", "fracture", "sprain", "cpr", "aed", "resuscitation", "choking",
    "back blows", "heimlich", "five-and-five", "blister", "burn", "scald",
    "bite", "sting", "tick", "venom", "poison", "hypothermia", "frostbite",
    "heatstroke", "heat exhaustion", "dehydration", "knot", "lashing", "hitch",
    "splice", "compass", "azimuth", "topographic", "contour", "stroke",
    "rescue", "reach throw", "bowstring", "anchor point", "fletching"
  ];

  const hasExplicitNoHumans = noHumansPhrases.some((p) => titlePromptLower.includes(p));
  const hasGearOrEnv = gearOrEnvKeywords.some((k) => titlePromptLower.includes(k));

  let defaultIncludeHumans = true;
  let recommendedStyle = "Photorealistic Image";
  let categoryLabel = "Uniformed Field Action";

  if (hasExplicitNoHumans || hasGearOrEnv) {
    defaultIncludeHumans = false;
    if (["robotics", "sensor", "actuator", "drivetrain", "circuit", "cad", "versus", " vs "].some((k) => combinedLower.includes(k))) {
      recommendedStyle = "3D Isometric Illustration";
    } else if (["cloud", "front", "water cycle", "constellation", "eclipse", "ecosystem", "watershed"].some((k) => combinedLower.includes(k))) {
      recommendedStyle = "Watercolor Field Sketch";
    } else {
      recommendedStyle = "Photorealistic Image";
    }
    categoryLabel = "Pure Equipment / Kit Flat-Lay / Environment";
  } else if (["1", "1a", "overview"].includes(reqClean) || conceptMapKeywords.some((k) => titlePromptLower.includes(k))) {
    defaultIncludeHumans = true;
    recommendedStyle = "4-Quadrant Concept Map";
    categoryLabel = "4-Quadrant Concept Map Overview";
  } else if (proceduralKeywords.some((k) => titlePromptLower.includes(k))) {
    defaultIncludeHumans = true;
    recommendedStyle = (cleanTitle.length % 2 === 0) ? "Watercolor Field Sketch" : "Line Drawing";
    categoryLabel = "BSA Handbook Procedural Plate";
  }

  const isAutoStyle = !styleVal || styleVal.toLowerCase().startsWith("auto") || styleVal.toLowerCase().includes("content-aware");
  const effectiveStyle = isAutoStyle ? recommendedStyle : styleVal;

  if (!isAutoStyle && ["technical diagram", "3d isometric illustration"].includes(effectiveStyle.toLowerCase()) && hasGearOrEnv) {
    defaultIncludeHumans = false;
  }

  let resolvedHumans = defaultIncludeHumans;
  let humansSource = "Auto (Content-Aware)";
  if (humansMode === true || humansMode === "true") {
    resolvedHumans = true;
    humansSource = "Explicit Override";
  } else if (humansMode === false || humansMode === "false") {
    resolvedHumans = false;
    humansSource = "Explicit Override";
  }

  return {
    effectiveStyle,
    isAutoStyle,
    includeHumans: resolvedHumans,
    humansSource,
    categoryLabel,
  };
}

function buildDefaultVisualPromptForSlide(badgeName, slide) {
  const cleanTitle = cleanSlideTopicBoilerplate(slide?.title || "");
  const lower = `${cleanTitle} ${badgeName || ""}`.toLowerCase();
  if (lower.includes("five-and-five") || lower.includes("back blows") || lower.includes("choking")) {
    return "Emergency first aid responder performing five back blows and Heimlich maneuver abdominal thrusts on a choking person";
  }
  if (lower.includes("first-aid kit") || lower.includes("first aid kit") || lower.includes("personal first-aid")) {
    return "Overhead knolling flat-lay of open personal hiking first aid kit and troop trauma kit displaying sterile gauze pads, adhesive bandages, SAM splint, medical tape, trauma scissors, and nitrile gloves on a camp table with no people";
  }
  if (lower.includes("windlass") || lower.includes("tourniquet") || lower.includes("bleeding")) {
    return "First aid responder applying direct pressure and tightening a windlass tourniquet strap on an injured arm to stop severe bleeding";
  }
  if (lower.includes("splint") || lower.includes("fracture") || lower.includes("sprain")) {
    return "First aid responder immobilizing an injured forearm with a padded splint and triangular bandage arm sling";
  }
  if (lower.includes("cpr") || lower.includes("aed") || lower.includes("compressions")) {
    return "First aid responder performing CPR chest compressions and attaching an Automated External Defibrillator (AED) on a training manikin";
  }
  if (lower.includes("hurry cases") || lower.includes("triage")) {
    return "Wilderness first aid responders evaluating airway, breathing, and circulation on an injured hiker during field triage";
  }
  const bullets = Array.isArray(slide?.bullet_points) ? slide.bullet_points : [];
  const bpSummaries = bullets
    .slice(0, 3)
    .map((b) => {
      const cleaned = cleanSlideTopicBoilerplate(String(b));
      return cleaned.includes(":") ? cleaned.split(":")[0].trim() : cleaned.slice(0, 48).trim();
    })
    .filter(Boolean);
  const cfg = resolveClientSideContentAwareConfig(badgeName, slide, "", "Auto (Content-Aware Mix)", "auto");
  if (!cfg.includeHumans) {
    return `Detailed equipment flat-lay or scientific visual display of ${cleanTitle || badgeName}${bpSummaries.length ? ` (${bpSummaries.join(", ")})` : ""}, showing only physical gear, instruments, or natural phenomena with no humans`;
  }
  if (cleanTitle && bpSummaries.length > 0) {
    return `${badgeName} hands-on demonstration of ${cleanTitle}, illustrating ${bpSummaries.join(", ")}`;
  }
  return `${badgeName} hands-on outdoor demonstration of ${cleanTitle || badgeName}`;
}

function bindImageStudioModal() {
  const modal = document.getElementById("image-studio-modal");
  const openBtn = document.getElementById("btn-open-image-studio");
  const closeBtn = document.getElementById("btn-close-image-studio");
  const clearCacheBtn = document.getElementById("btn-studio-clear-cache");
  const quickSel = document.getElementById("codesign-quick-image-select");
  const prevImgBtn = document.getElementById("btn-prev-slide-image");
  const nextImgBtn = document.getElementById("btn-next-slide-image");
  const webSearchBtn = document.getElementById("btn-studio-web-search");
  const nanoGenBtn = document.getElementById("btn-studio-ai-generate");
  const consentCheck = document.getElementById("studio-ai-consent-checkbox");
  const styleSelectEl = document.getElementById("studio-ai-style-select");
  const humansSelectEl = document.getElementById("studio-ai-humans-select");
  const humansCheckboxEl = document.getElementById("studio-ai-include-humans-checkbox");
  const slideContextCheckboxEl = document.getElementById("studio-ai-include-slide-context-checkbox");
  const resolvedBadgeEl = document.getElementById("studio-ai-humans-resolved-badge");

  const closeModal = () => {
    modal?.classList.remove("open");
    modal?.classList.add("hidden");
  };

  const openModal = () => {
    modal?.classList.remove("hidden");
    modal?.classList.add("open");
  };

  // Immediate Quick Switcher dropdown change handler (no Switch Image button needed)
  quickSel?.addEventListener("change", async () => {
    const val = quickSel.value;
    if (val === "") return;
    if (val === "__NONE__") {
      await applyCatalogImageToActiveSlide(null, "none");
      return;
    }
    const idx = parseInt(val, 10);
    const entry = (state.badgeCatalogCache || [])[idx];
    if (entry) {
      await applyCatalogImageToActiveSlide(entry, "custom_image");
    }
  });

  // Left/Right cycle arrows next to Quick-Switch Slide Image
  prevImgBtn?.addEventListener("click", async () => {
    const list = state.badgeCatalogCache || [];
    if (!list.length) return;
    const currVal = quickSel?.value;
    const currIdx = currVal !== undefined && currVal !== "__NONE__" && currVal !== "" ? parseInt(currVal, 10) : 0;
    const prevIdx = ( (isNaN(currIdx) ? 0 : currIdx) - 1 + list.length ) % list.length;
    if (quickSel) quickSel.value = String(prevIdx);
    await applyCatalogImageToActiveSlide(list[prevIdx], "custom_image");
  });

  nextImgBtn?.addEventListener("click", async () => {
    const list = state.badgeCatalogCache || [];
    if (!list.length) return;
    const currVal = quickSel?.value;
    const currIdx = currVal !== undefined && currVal !== "__NONE__" && currVal !== "" ? parseInt(currVal, 10) : -1;
    const nextIdx = ( (isNaN(currIdx) ? -1 : currIdx) + 1 ) % list.length;
    if (quickSel) quickSel.value = String(nextIdx);
    await applyCatalogImageToActiveSlide(list[nextIdx], "custom_image");
  });

  // Tab switching inside modal (matches ui/index.html IDs: studio-tab-catalog, studio-tab-web, studio-tab-ai, studio-tab-upload)
  document.querySelectorAll("[data-studio-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-studio-tab");
      document.querySelectorAll("[data-studio-tab]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      ["studio-tab-catalog", "studio-tab-web", "studio-tab-ai", "studio-tab-upload"].forEach((id) => {
        const panel = document.getElementById(id);
        if (panel) {
          panel.classList.toggle("hidden", id !== targetId);
        }
      });
    });
  });

  const renderModalCatalogGrid = () => {
    const grid = document.getElementById("studio-catalog-grid");
    if (!grid || !state.currentResult) return;
    const slides = state.currentResult.storyboard?.slides || [];
    const activeSlide = slides[state.activeSlideIdx] || {};
    const entries = state.badgeCatalogCache || [];

    if (entries.length === 0) {
      grid.innerHTML = `<div style="padding:16px; color:#64748B;">No cached images found for this badge yet. Use the Web Image Search, Nano Banana AI, or File Upload tabs to add graphics!</div>`;
      return;
    }

    const activeClean = stripUrlQuery(activeSlide.diagram_url);
    grid.innerHTML = entries
      .map((entry, idx) => {
        const isCurrent = Boolean(activeClean && stripUrlQuery(entry.image_url) === activeClean);
        const st = String(entry.source_type || entry.source_kind || "").toUpperCase();
        const urlStr = String(entry.image_url || entry.image_path || "");
        const kindBadge =
          st === "NANO_BANANA_HERO" || urlStr.includes("_nano_hero.png")
            ? "🍌 Nano Banana Hero"
            : st.includes("NANO_BANANA")
            ? "🍌 Nano Banana AI"
            : st.includes("UPLOAD")
            ? "📁 Uploaded Local"
            : st.includes("WEB")
            ? "🌐 Web Search"
            : st.includes("EDGE")
            ? "✨ EDGE Concept Map"
            : "📐 Official BSA";
        return `
          <div class="m3-image-catalog-card ${isCurrent ? "active" : ""}">
            <div class="m3-catalog-img-zoom-wrap" data-zoom-catalog-idx="${idx}" title="Click image to view &amp; zoom in Lightbox (up to 500%)">
              <img src="${escapeHtml(entry.image_url)}" alt="${escapeHtml(entry.title)}" style="cursor:zoom-in;" />
              <button type="button" class="m3-catalog-zoom-pill" data-zoom-catalog-idx="${idx}" title="Click to open in Click-to-Zoom Lightbox (up to 500%)">🔍 Zoom</button>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; gap:6px;">
              <span class="m3-chip m3-chip-primary" style="font-size:0.66rem; padding:2px 7px;">${escapeHtml(kindBadge)}</span>
              ${isCurrent ? '<span style="font-size:0.70rem; font-weight:800; color:#166534;">✓ Active on Slide</span>' : ""}
            </div>
            <div style="font-size:0.84rem; font-weight:700; color:#0F172A;">${escapeHtml(entry.title || `Badge Graphic ${idx + 1}`)}</div>
            <div style="font-size:0.76rem; color:#475569; line-height:1.4;">${escapeHtml(entry.description || entry.caption || "")}</div>
            <button type="button" class="m3-btn ${isCurrent ? "m3-btn-outlined" : "m3-btn-tonal"}" data-apply-catalog-idx="${idx}" style="margin-top:auto; width:100%; font-size:0.76rem; padding:7px 10px;">
              ${isCurrent ? "✓ Currently Active on Slide" : `✅ Use on Slide ${state.activeSlideIdx + 2}`}
            </button>
          </div>
        `;
      })
      .join("");

    grid.querySelectorAll(".m3-catalog-img-zoom-wrap").forEach((wrapEl) => {
      wrapEl.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const idx = parseInt(wrapEl.getAttribute("data-zoom-catalog-idx") || "0", 10);
        const chosen = (state.badgeCatalogCache || [])[idx];
        if (chosen && chosen.image_url) {
          openImageZoomLightbox({
            src: chosen.image_url,
            title: chosen.title || `Badge Graphic ${idx + 1}`,
            caption: chosen.caption || chosen.description || chosen.title || "",
          });
        }
      });
    });

    grid.querySelectorAll("[data-apply-catalog-idx]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const idx = parseInt(btn.getAttribute("data-apply-catalog-idx"), 10);
        const chosen = (state.badgeCatalogCache || [])[idx];
        if (chosen) {
          await applyCatalogImageToActiveSlide(chosen, "custom_image");
          closeModal();
        }
      });
    });
  };

  // Clear Web/AI Cache button inside Tab 1 of Image Studio Modal
  clearCacheBtn?.addEventListener("click", async () => {
    if (!state.currentResult) return;
    const badgeName = state.currentResult.badge_name || "First Aid";
    const statusBanner = document.getElementById("studio-catalog-status");
    const origText = clearCacheBtn.textContent;
    clearCacheBtn.disabled = true;
    clearCacheBtn.textContent = "⏳ Clearing Cache...";
    const isHeroOrOfficialItem = (it) => {
      const st = String(it?.source_type || "").toUpperCase();
      const p = String(it?.image_url || it?.image_path || "");
      const id = String(it?.image_id || "");
      if (st === "NANO_BANANA_HERO" || p.includes("_nano_hero.png") || p.includes("ai_illustrations")) {
        return true;
      }
      if (st === "WEB_IMAGE_SEARCH" || st === "NANO_BANANA_AI" || id.startsWith("nanobanana_") || id.startsWith("wikimedia_")) {
        return false;
      }
      return true;
    };
    try {
      const delResp = await fetch(`/api/badge/images?badge_name=${encodeURIComponent(badgeName)}`, {
        method: "DELETE",
      });
      let removedCount = 0;
      if (delResp.ok) {
        const delData = await delResp.json();
        removedCount = delData.removed_files || 0;
      }
      // Refresh catalog from server so Hero, Official BSA, EDGE, and Uploaded files remain
      const catResp = await fetch(`/api/badge/images?badge_name=${encodeURIComponent(badgeName)}`);
      if (catResp.ok) {
        const catData = await catResp.json();
        const imgs = Array.isArray(catData.images) ? catData.images : [];
        state.currentResult.badge_image_catalog = imgs;
      } else {
        const existing = Array.isArray(state.currentResult.badge_image_catalog)
          ? state.currentResult.badge_image_catalog
          : [];
        state.currentResult.badge_image_catalog = existing.filter(isHeroOrOfficialItem);
      }
      const slides = state.currentResult.storyboard?.slides || [];
      slides.forEach((s) => {
        if (Array.isArray(s.available_images)) {
          s.available_images = s.available_images.filter(isHeroOrOfficialItem);
        }
        if (Array.isArray(s.slide_image_choices)) {
          s.slide_image_choices = s.slide_image_choices.filter(isHeroOrOfficialItem);
        }
      });
      const activeSlide = slides[state.activeSlideIdx] || {};
      populateQuickImageSwitcher(activeSlide);
      renderModalCatalogGrid();
      if (state.activeSlideIdx >= 0) {
        renderActiveSlide(state.activeSlideIdx);
      }
      const webResultsGrid = document.getElementById("studio-web-results-grid");
      if (webResultsGrid) webResultsGrid.innerHTML = "";
      if (statusBanner) {
        statusBanner.style.display = "block";
        statusBanner.textContent = `✅ Cleared ${removedCount} user-added Web Search & Nano Banana AI image(s) for ${badgeName}. Pre-generated/auto hero graphics, official pamphlet figures & uploaded files preserved.`;
      }
    } catch (err) {
      if (statusBanner) {
        statusBanner.style.display = "block";
        statusBanner.textContent = `Cache clear error: ${err.message}`;
      }
    } finally {
      clearCacheBtn.disabled = false;
      clearCacheBtn.textContent = origText;
    }
  });

  openBtn?.addEventListener("click", async () => {
    if (!state.currentResult) return;
    if (state.activeSlideIdx < 0) {
      state.activeSlideIdx = 0;
      renderActiveSlide(0);
    }
    const slides = state.currentResult.storyboard?.slides || [];
    const slide = slides[state.activeSlideIdx] || {};
    const statusBanner = document.getElementById("studio-catalog-status");
    if (statusBanner) statusBanner.style.display = "none";

    const subtitleEl = document.getElementById("image-studio-modal-subtitle");
    if (subtitleEl) {
      subtitleEl.textContent = `${state.currentResult.badge_name} Merit Badge • Slide ${state.activeSlideIdx + 2} (Req ${slide.req_number || state.activeSlideIdx + 1}): ${slide.title || ""}`;
    }
    const cleanTopic = cleanSlideTopicBoilerplate(slide.title || "");
    const wsInput = document.getElementById("studio-web-query-input");
    if (wsInput) {
      wsInput.value = `${state.currentResult.badge_name} ${cleanTopic}`.trim();
    }
    const aiPromptInput = document.getElementById("studio-ai-prompt-input");
    if (aiPromptInput) {
      aiPromptInput.value = buildDefaultVisualPromptForSlide(state.currentResult.badge_name, slide);
    }
    if (humansSelectEl) {
      humansSelectEl.value = "auto";
    }
    if (slideContextCheckboxEl) {
      slideContextCheckboxEl.checked = true;
    }
    updateNanoBananaContentAwareBanner();
    // Open popup modal immediately so the user gets instant visual feedback
    renderModalCatalogGrid();
    openModal();

    // Refresh badge image catalog from server in background
    try {
      const resp = await fetch(`/api/badge/images?badge_name=${encodeURIComponent(state.currentResult.badge_name)}`);
      if (resp.ok) {
        const data = await resp.json();
        const imgs = Array.isArray(data.images) ? data.images : Array.isArray(data) ? data : [];
        if (imgs.length > 0) {
          state.currentResult.badge_image_catalog = imgs;
          populateQuickImageSwitcher(slide);
          renderModalCatalogGrid();
        }
      }
    } catch (_) {}
  });

  const updateNanoBananaContentAwareBanner = () => {
    if (!state.currentResult || state.activeSlideIdx < 0) return;
    const slides = state.currentResult.storyboard?.slides || [];
    const slide = slides[state.activeSlideIdx] || {};
    const styleVal = styleSelectEl?.value || "Auto (Content-Aware Mix)";
    const humansMode = humansSelectEl?.value || "auto";
    const includeSlideCtx = slideContextCheckboxEl ? Boolean(slideContextCheckboxEl.checked) : true;
    const promptVal = document.getElementById("studio-ai-prompt-input")?.value || "";
    const cfg = resolveClientSideContentAwareConfig(
      state.currentResult.badge_name,
      slide,
      promptVal,
      styleVal,
      humansMode,
      includeSlideCtx
    );
    if (humansCheckboxEl) {
      humansCheckboxEl.checked = Boolean(cfg.includeHumans);
    }
    if (resolvedBadgeEl) {
      const directiveIcon = cfg.includeHumans ? "👕" : "🧰";
      const directiveText = cfg.includeHumans
        ? "Adult Scouts BSA Field Uniforms"
        : "Zero Humans (Pure Equipment / Environment)";
      const modeTag = cfg.humansSource === "Explicit Override" ? "Manual Override" : "Auto-Detected";
      const ctxTag = includeSlideCtx ? "Slide Context: Included" : "Slide Context: Omitted (Prompt Only)";
      resolvedBadgeEl.innerHTML = `🧠 <strong>${escapeHtml(modeTag)}:</strong> ${directiveIcon} <strong>${escapeHtml(directiveText)}</strong> • Effective Style: <strong>${escapeHtml(cfg.effectiveStyle)}</strong> • <strong>${escapeHtml(ctxTag)}</strong>`;
    }
  };

  styleSelectEl?.addEventListener("change", () => {
    updateNanoBananaContentAwareBanner();
  });

  humansSelectEl?.addEventListener("change", () => {
    updateNanoBananaContentAwareBanner();
  });

  humansCheckboxEl?.addEventListener("change", () => {
    if (humansSelectEl) {
      humansSelectEl.value = humansCheckboxEl.checked ? "true" : "false";
    }
    updateNanoBananaContentAwareBanner();
  });

  slideContextCheckboxEl?.addEventListener("change", () => {
    updateNanoBananaContentAwareBanner();
  });

  document.getElementById("studio-ai-prompt-input")?.addEventListener("input", () => {
    updateNanoBananaContentAwareBanner();
  });

  closeBtn?.addEventListener("click", () => {
    closeModal();
  });

  modal?.addEventListener("click", (ev) => {
    if (ev.target === modal) {
      closeModal();
    }
  });

  consentCheck?.addEventListener("change", () => {
    if (nanoGenBtn) {
      nanoGenBtn.disabled = !consentCheck.checked;
    }
  });

  webSearchBtn?.addEventListener("click", async () => {
    if (!state.currentResult || state.activeSlideIdx < 0) return;
    const slides = state.currentResult.storyboard?.slides || [];
    const slide = slides[state.activeSlideIdx] || {};
    const query = document.getElementById("studio-web-query-input")?.value || "";
    const resultsGrid = document.getElementById("studio-web-results-grid");
    const origLabel = webSearchBtn.textContent;
    webSearchBtn.disabled = true;
    webSearchBtn.textContent = "⏳ Searching Wikimedia & Wikipedia...";
    if (resultsGrid) {
      resultsGrid.innerHTML = `<div style="padding:12px; color:#003F87; font-weight:600;">🔍 WebImageSearchAgent is searching Wikimedia Commons &amp; Wikipedia for "${escapeHtml(query)}"...</div>`;
    }
    try {
      const resp = await fetch("/api/slide/search-web-images", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: state.currentResult.badge_name,
          req_number: String(slide.req_number || "Overview"),
          slide_title: slide.title || "",
          bullet_points: slide.bullet_points || [],
          search_query: query,
          max_results: 16,
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        const found = data.results || [];
        if (resultsGrid) {
          if (found.length === 0) {
            resultsGrid.innerHTML = `<div style="padding:12px; color:#92400E;">No Wikimedia Commons or Wikipedia images matched "${escapeHtml(query)}". Try broader keywords.</div>`;
          } else {
            resultsGrid.innerHTML = found
              .map(
                (entry, i) => `
                <div class="m3-image-catalog-card">
                  <div class="m3-catalog-img-zoom-wrap" data-zoom-ws-idx="${i}" title="Click image to view &amp; zoom in Lightbox (up to 500%)">
                    <img src="${escapeHtml(entry.image_url)}" alt="${escapeHtml(entry.title)}" style="cursor:zoom-in;" />
                    <button type="button" class="m3-catalog-zoom-pill" data-zoom-ws-idx="${i}" title="Click to open in Click-to-Zoom Lightbox (up to 500%)">🔍 Zoom</button>
                  </div>
                  <div style="font-size:0.84rem; font-weight:700; color:#0F172A;">${escapeHtml(entry.title)}</div>
                  <div style="font-size:0.76rem; color:#475569; line-height:1.4;">${escapeHtml(entry.description)}</div>
                  <button type="button" class="m3-btn m3-btn-tonal" data-apply-ws-idx="${i}" style="margin-top:auto; width:100%; font-size:0.76rem; padding:7px 10px;">
                    ✅ Apply &amp; Cache to Slide ${state.activeSlideIdx + 2}
                  </button>
                </div>
              `
              )
              .join("");
            resultsGrid.querySelectorAll(".m3-catalog-img-zoom-wrap").forEach((wrapEl) => {
              wrapEl.addEventListener("click", (ev) => {
                ev.stopPropagation();
                const chosen = found[parseInt(wrapEl.getAttribute("data-zoom-ws-idx") || "0", 10)];
                if (chosen && chosen.image_url) {
                  openImageZoomLightbox({
                    src: chosen.image_url,
                    title: chosen.title || "Web Search Image",
                    caption: chosen.caption || chosen.description || chosen.title || "",
                  });
                }
              });
            });
            resultsGrid.querySelectorAll("[data-apply-ws-idx]").forEach((b) => {
              b.addEventListener("click", async () => {
                const chosen = found[parseInt(b.getAttribute("data-apply-ws-idx"), 10)];
                if (chosen) {
                  const existingCat = Array.isArray(state.currentResult.badge_image_catalog)
                    ? state.currentResult.badge_image_catalog
                    : state.currentResult.badge_image_catalog?.images || [];
                  state.currentResult.badge_image_catalog = [chosen, ...existingCat];
                  populateQuickImageSwitcher(slide);
                  renderModalCatalogGrid();
                  await applyCatalogImageToActiveSlide(chosen, "custom_image");
                  closeModal();
                }
              });
            });
          }
        }
      }
    } catch (err) {
      if (resultsGrid) {
        resultsGrid.innerHTML = `<div style="padding:12px; color:#991B1B;">Web image search failed: ${escapeHtml(err.message)}</div>`;
      }
    } finally {
      webSearchBtn.disabled = false;
      webSearchBtn.textContent = origLabel;
    }
  });

  nanoGenBtn?.addEventListener("click", async () => {
    if (!state.currentResult || state.activeSlideIdx < 0) return;
    if (!consentCheck?.checked) return;
    const slides = state.currentResult.storyboard?.slides || [];
    const slide = slides[state.activeSlideIdx] || {};
    const styleVal = document.getElementById("studio-ai-style-select")?.value || "Auto (Content-Aware Mix)";
    const humansMode = document.getElementById("studio-ai-humans-select")?.value || "auto";
    const includeSlideCtx = slideContextCheckboxEl ? Boolean(slideContextCheckboxEl.checked) : true;
    const customPrompt = document.getElementById("studio-ai-prompt-input")?.value || "";
    const resolvedCfg = resolveClientSideContentAwareConfig(
      state.currentResult.badge_name,
      slide,
      customPrompt,
      styleVal,
      humansMode,
      includeSlideCtx
    );
    const includeHumansPayload = humansMode === "auto" ? "auto" : Boolean(resolvedCfg.includeHumans);
    const statusBox = document.getElementById("studio-ai-consent-msg");
    const origLabel = nanoGenBtn.textContent;
    nanoGenBtn.disabled = true;
    nanoGenBtn.textContent = "⏳ Generating & Verifying Nano Banana Graphic...";
    if (statusBox) {
      const dirDesc = resolvedCfg.includeHumans ? "Adult Scouts BSA Uniforms" : "Pure Equipment / Environment (Zero Humans)";
      statusBox.textContent = `🍌 NanoBananaImageAgent is synthesizing & verifying a ${resolvedCfg.effectiveStyle} (${dirDesc})...`;
    }
    try {
      const resp = await fetch("/api/slide/generate-nano-banana-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: state.currentResult.badge_name,
          req_number: String(slide.req_number || "Overview"),
          slide_title: slide.title || "",
          bullet_points: slide.bullet_points || [],
          custom_prompt: customPrompt,
          visual_style: styleVal,
          include_humans: includeHumansPayload,
          include_slide_context: includeSlideCtx,
          accent_palette_key: slide.accent_palette_key || "NAVY_GOLD",
          beautification_tier: state.currentResult.beautification_tier || "BEAUTIFIED",
          user_consented: true,
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        const createdEntry = data.image_entry || data.entry || data.image;
        if (data.status === "SUCCESS" && createdEntry) {
          const existingCat = Array.isArray(state.currentResult.badge_image_catalog)
            ? state.currentResult.badge_image_catalog
            : state.currentResult.badge_image_catalog?.images || [];
          state.currentResult.badge_image_catalog = [createdEntry, ...existingCat];
          await applyCatalogImageToActiveSlide(createdEntry, "custom_image");
          const alignSummary = data.prompt_alignment?.verification_summary || "Prompt alignment verified.";
          if (statusBox) {
            statusBox.innerHTML = `<span class="m3-studio-ai-success-msg" style="color:#166534; font-weight:700;">✅ Generated &amp; verified "${escapeHtml(createdEntry.title)}" ($${Number(data.cost_estimate?.estimated_cost_usd || 0.08).toFixed(2)} USD). ${escapeHtml(alignSummary)}</span>`;
          }
          setTimeout(() => closeModal(), 750);
        } else {
          if (statusBox) {
            if (data.error_code === "NANO_BANANA_PROMPT_BLOCKED" || data.status === "ERROR") {
              const codeLbl = escapeHtml(data.error_code || "NANO_BANANA_PROMPT_BLOCKED");
              const rawMsg = String(data.message || "Custom image prompt blocked by Youth Protection / Model Armor guardrail.");
              const rawRem = String(data.remediation || "Use safe, educational Scouting descriptions.");
              const msgLbl = escapeHtml(rawMsg);
              const remLbl = escapeHtml(
                rawRem === rawMsg || rawMsg.includes(rawRem)
                  ? "Revise the image prompt to describe a safe, Youth Protection-compliant Scouting activity with no personal contact info or inappropriate content."
                  : rawRem
              );
              statusBox.innerHTML = `
                <div class="m3-studio-ai-blocked-alert" style="background:#FEF2F2; border:1.5px solid #DC2626; border-radius:8px; padding:10px 12px; margin-top:6px; color:#991B1B;">
                  <div class="m3-studio-ai-blocked-title" style="font-weight:800; font-size:0.84rem;">🛑 [${codeLbl}] ${msgLbl}</div>
                  <div class="m3-studio-ai-blocked-rem" style="font-size:0.78rem; margin-top:4px; color:#7F1D1D;"><strong>Remediation:</strong> ${remLbl} (Zero image tokens billed: $0.00 USD)</div>
                </div>
              `;
            } else {
              statusBox.textContent = data.message || "Consent required before generating AI images.";
            }
          }
        }
      }
    } catch (err) {
      if (statusBox) {
        statusBox.textContent = `Generation error: ${err.message}`;
      }
    } finally {
      nanoGenBtn.disabled = !consentCheck?.checked;
      nanoGenBtn.textContent = origLabel;
    }
  });

  // Tab 4: Local File Upload handler
  const uploadFileInput = document.getElementById("studio-upload-file-input");
  const uploadTitleInput = document.getElementById("studio-upload-title-input");
  const uploadDescInput = document.getElementById("studio-upload-desc-input");
  const uploadPreviewWrap = document.getElementById("studio-upload-preview-wrap");
  const uploadPreviewImg = document.getElementById("studio-upload-preview-img");
  const uploadPreviewMeta = document.getElementById("studio-upload-preview-meta");
  const uploadStatusBox = document.getElementById("studio-upload-status");
  const uploadApplyBtn = document.getElementById("btn-studio-upload-apply");
  let pendingUploadDataUrl = "";
  let pendingUploadFilename = "";

  uploadFileInput?.addEventListener("change", () => {
    const file = uploadFileInput.files && uploadFileInput.files[0];
    if (!file) {
      pendingUploadDataUrl = "";
      pendingUploadFilename = "";
      uploadPreviewWrap?.classList.add("hidden");
      if (uploadApplyBtn) uploadApplyBtn.disabled = true;
      return;
    }
    pendingUploadFilename = file.name;
    const baseName = file.name.replace(/\.[^/.]+$/, "").replace(/[_-]+/g, " ").trim();
    if (uploadTitleInput && !uploadTitleInput.value.trim()) {
      uploadTitleInput.value = baseName;
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      pendingUploadDataUrl = String(ev.target?.result || "");
      if (uploadPreviewImg) uploadPreviewImg.src = pendingUploadDataUrl;
      if (uploadPreviewMeta) {
        const kb = Math.max(1, Math.round(file.size / 1024));
        uploadPreviewMeta.textContent = `${file.name} (${kb.toLocaleString()} KB)`;
      }
      uploadPreviewWrap?.classList.remove("hidden");
      if (uploadApplyBtn) uploadApplyBtn.disabled = false;
    };
    reader.readAsDataURL(file);
  });

  uploadApplyBtn?.addEventListener("click", async () => {
    if (!state.currentResult || state.activeSlideIdx < 0 || !pendingUploadDataUrl) return;
    const slides = state.currentResult.storyboard?.slides || [];
    const slide = slides[state.activeSlideIdx] || {};
    const origLabel = uploadApplyBtn.textContent;
    uploadApplyBtn.disabled = true;
    uploadApplyBtn.textContent = "⏳ Uploading & Caching Local Image...";
    if (uploadStatusBox) {
      uploadStatusBox.style.display = "block";
      uploadStatusBox.style.background = "#EFF6FF";
      uploadStatusBox.style.border = "1px solid #BFDBFE";
      uploadStatusBox.style.color = "#1E40AF";
      uploadStatusBox.textContent = "📁 Validating and caching local image into Merit Badge catalog...";
    }
    try {
      const resp = await fetch("/api/slide/upload-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: state.currentResult.badge_name,
          req_number: String(slide.req_number || "Overview"),
          slide_title: slide.title || "",
          filename: pendingUploadFilename || "uploaded_slide_image.png",
          data_url: pendingUploadDataUrl,
          title: uploadTitleInput?.value || "",
          description: uploadDescInput?.value || "",
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        const createdEntry = data.image_entry || data.entry;
        if (data.status === "SUCCESS" && createdEntry) {
          const existingCat = Array.isArray(state.currentResult.badge_image_catalog)
            ? state.currentResult.badge_image_catalog
            : state.currentResult.badge_image_catalog?.images || [];
          state.currentResult.badge_image_catalog = [createdEntry, ...existingCat];
          populateQuickImageSwitcher(slide);
          renderModalCatalogGrid();
          await applyCatalogImageToActiveSlide(createdEntry, "custom_image");
          if (uploadStatusBox) {
            uploadStatusBox.style.background = "#F0FDF4";
            uploadStatusBox.style.border = "1px solid #86EFAC";
            uploadStatusBox.style.color = "#166534";
            uploadStatusBox.textContent = `✅ Uploaded & applied "${createdEntry.title}" ($0.00 USD) to Slide ${state.activeSlideIdx + 2}!`;
          }
          setTimeout(() => closeModal(), 650);
        } else {
          if (uploadStatusBox) {
            uploadStatusBox.style.background = "#FEF2F2";
            uploadStatusBox.style.border = "1px solid #FCA5A5";
            uploadStatusBox.style.color = "#991B1B";
            uploadStatusBox.textContent = data.message || "Could not process uploaded image file.";
          }
        }
      }
    } catch (err) {
      if (uploadStatusBox) {
        uploadStatusBox.style.display = "block";
        uploadStatusBox.style.background = "#FEF2F2";
        uploadStatusBox.style.border = "1px solid #FCA5A5";
        uploadStatusBox.style.color = "#991B1B";
        uploadStatusBox.textContent = `Upload error: ${err.message}`;
      }
    } finally {
      uploadApplyBtn.disabled = !pendingUploadDataUrl;
      uploadApplyBtn.textContent = origLabel;
    }
  });

  // Panel 4: Counselor Rating & Continuous Learning Flywheel Sign-Off handler
  const submitFeedbackBtn = document.getElementById("btn-submit-counselor-feedback");
  submitFeedbackBtn?.addEventListener("click", async () => {
    if (!state.currentResult) return;
    const ratingVal = Number(document.getElementById("feedback-rating-select")?.value || 5);
    const reqVerified = Boolean(document.getElementById("feedback-req-verified-checkbox")?.checked);
    const commentsVal = document.getElementById("feedback-comments-input")?.value || "";
    const counselorName = document.getElementById("input-counselor-name")?.value || state.currentResult.counselor_info?.counselor_name || "Scoutmaster Bob";
    const reqCount = (state.currentResult.research_artifact?.requirements || []).length || 5;
    const sessionId = state.currentResult.session_id || `session-${(state.currentResult.badge_name || "badge").toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
    const fbBanner = document.getElementById("feedback-status-banner");
    const origLabel = submitFeedbackBtn.textContent;
    submitFeedbackBtn.disabled = true;
    submitFeedbackBtn.textContent = "⏳ Recording Rating & Updating Flywheel...";
    try {
      const resp = await fetch("/api/v1/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: state.currentResult.badge_name,
          counselor_name: counselorName,
          session_id: sessionId,
          requirement_count: reqCount,
          rating: ratingVal,
          requirement_accuracy_verified: reqVerified,
          comments: commentsVal,
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        const apiVer = resp.headers.get("X-API-Version") || data.schema_version || "1.2.0";
        if (fbBanner) {
          fbBanner.classList.remove("hidden");
          if (data.promoted_to_golden_dataset) {
            fbBanner.style.background = "#F0FDF4";
            fbBanner.style.border = "1.5px solid #22C55E";
            fbBanner.style.color = "#14532D";
            fbBanner.innerHTML = `✅ <strong>Promoted to Golden Evaluation Dataset!</strong> Recorded ${ratingVal}/5 rating by <strong>${escapeHtml(counselorName)}</strong> in SQLite (<code>hitl_feedback</code>) &amp; updated <code>${escapeHtml(data.golden_dataset_path || "tests/data/golden_extensions.json")}</code> (${Number(data.golden_extensions_count || 1)} verified extensions • API Schema <code>v${escapeHtml(apiVer)}</code>).`;
          } else {
            fbBanner.style.background = "#FFFBEB";
            fbBanner.style.border = "1.5px solid #F59E0B";
            fbBanner.style.color = "#78350F";
            fbBanner.innerHTML = `📝 <strong>Feedback Recorded in SQLite (<code>hitl_feedback</code>):</strong> ${ratingVal}/5 rating logged for <strong>${escapeHtml(state.currentResult.badge_name)}</strong>. (Golden Dataset promotion requires &ge; 4/5 Stars + Verified Requirement Accuracy).`;
          }
        }
      }
    } catch (err) {
      if (fbBanner) {
        fbBanner.classList.remove("hidden");
        fbBanner.style.background = "#FEF2F2";
        fbBanner.style.border = "1.5px solid #EF4444";
        fbBanner.style.color = "#991B1B";
        fbBanner.textContent = `Could not submit counselor rating: ${err.message}`;
      }
    } finally {
      submitFeedbackBtn.disabled = false;
      submitFeedbackBtn.textContent = origLabel;
    }
  });
}

// ===========================================================================
// PHASE 3 (F3–F6): COUNSELOR TOOLKIT — PACING, COPY/EMAIL/PRINT, GEAR, BLUE CARD
// ===========================================================================

async function copyTextWithFeedback(btnEl, text, copiedLabel = "✅ Copied!") {
  const str = String(text || "");
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(str);
    } else {
      const ta = document.createElement("textarea");
      ta.value = str;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    if (btnEl) {
      const orig = btnEl.getAttribute("data-orig-label") || btnEl.textContent;
      btnEl.setAttribute("data-orig-label", orig);
      btnEl.textContent = copiedLabel;
      setTimeout(() => {
        btnEl.textContent = orig;
      }, 2200);
    }
  } catch (_err) {
    // ignore clipboard error
  }
}

function printHtmlDocument(docTitle, subtitle, bodyHtml) {
  const printWin = window.open("", "_blank", "width=920,height=740");
  if (!printWin) {
    window.print();
    return;
  }
  printWin.document.write(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>${escapeHtml(docTitle)}</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: #0F172A;
      margin: 28px 36px;
      line-height: 1.55;
      font-size: 13.5px;
    }
    .doc-banner {
      border-bottom: 3px solid #003F87;
      padding-bottom: 10px;
      margin-bottom: 18px;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
    }
    .doc-banner h1 {
      margin: 0;
      font-size: 20px;
      color: #003F87;
    }
    .doc-banner .sub {
      font-size: 12px;
      color: #475569;
      margin-top: 3px;
    }
    h1, h2, h3 { color: #003F87; margin-top: 14px; margin-bottom: 6px; }
    table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 12.5px; }
    th, td { border: 1px solid #CBD5E1; padding: 6px 9px; text-align: left; }
    th { background: #EFF6FF; color: #003F87; font-weight: 700; }
    blockquote { background: #F8FAFC; border-left: 4px solid #003F87; padding: 8px 12px; margin: 10px 0; }
    @media print {
      body { margin: 12mm; }
    }
  </style>
</head>
<body>
  <div class="doc-banner">
    <div>
      <h1>${escapeHtml(docTitle)}</h1>
      <div class="sub">${escapeHtml(subtitle)}</div>
    </div>
    <div style="font-size:11px; color:#64748B;">Scouts BSA Merit Badge Counselor Workbench</div>
  </div>
  <div>${bodyHtml}</div>
</body>
</html>`);
  printWin.document.close();
  printWin.focus();
  setTimeout(() => {
    printWin.print();
  }, 250);
}

function getPlainEmailBodyFromMarkdown(md) {
  return String(md || "")
    .replace(/^#+\s+/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}

function bindCounselorToolkitActions() {
  // F3: Session Pacing Schedule Format Selector
  const scheduleSel = document.getElementById("studiokit-schedule-select");
  scheduleSel?.addEventListener("change", async () => {
    if (!state.currentResult) return;
    const scheduleFormat = scheduleSel.value || "3 Troop Meetings (60-Min)";
    const agendaPreview = document.getElementById("studiokit-agenda-preview");
    if (agendaPreview) {
      agendaPreview.innerHTML = `<div style="padding:16px; color:#003F87; font-weight:600;">⏳ Rebuilding Session Pacing Plan for <strong>${escapeHtml(scheduleFormat)}</strong>...</div>`;
    }
    try {
      const resp = await fetch("/api/studiokit/agenda", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: state.currentResult.badge_name,
          schedule_format: scheduleFormat,
          requirements: state.currentResult.research_artifact?.requirements || [],
          storyboard_slides: state.currentResult.storyboard?.slides || [],
          counselor_info: {
            counselor_name: document.getElementById("input-counselor-name")?.value || "Scoutmaster Bob",
            troop_affiliation: document.getElementById("input-troop-name")?.value || "Troop 123, My Council",
            location_or_zip: document.getElementById("input-counselor-location")?.value || "",
            email_address: document.getElementById("input-counselor-email")?.value || "counselor@troop123.org",
            phone_number: document.getElementById("input-counselor-phone")?.value || "(000) 555-1234",
          },
        }),
      }).then((r) => r.json());
      if (resp && resp.agenda_markdown) {
        state.currentResult.session_agenda = resp;
        if (agendaPreview) {
          agendaPreview.innerHTML = renderMarkdownToStyledHtml(resp.agenda_markdown);
        }
      }
    } catch (_err) {
      if (agendaPreview && state.currentResult.session_agenda?.agenda_markdown) {
        agendaPreview.innerHTML = renderMarkdownToStyledHtml(state.currentResult.session_agenda.agenda_markdown);
      }
    }
  });

  const triggerMarkdownDownload = (filename, content) => {
    const blob = new Blob([String(content || "")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // F4: Scout Workbook Copy & Print
  document.getElementById("btn-copy-workbook")?.addEventListener("click", (e) => {
    const md = state.currentResult?.workbook_markdown || "";
    copyTextWithFeedback(e.currentTarget, md, "✅ Copied Workbook!");
  });
  document.getElementById("btn-print-workbook")?.addEventListener("click", () => {
    const badge = state.currentResult?.badge_name || "Merit Badge";
    const troop = document.getElementById("input-troop-name")?.value || "Troop 123";
    const html = document.getElementById("workbook-markdown-preview")?.innerHTML || "";
    printHtmlDocument(`${badge} Merit Badge — Scout Workbook`, `Prepared for ${troop}`, html);
  });

  // F4: Session Agenda Copy, Print & .MD Download
  document.getElementById("btn-copy-agenda")?.addEventListener("click", (e) => {
    const md = state.currentResult?.session_agenda?.agenda_markdown || "";
    copyTextWithFeedback(e.currentTarget, md, "✅ Copied Agenda!");
  });
  document.getElementById("btn-print-agenda")?.addEventListener("click", () => {
    const badge = state.currentResult?.badge_name || "Merit Badge";
    const fmt = document.getElementById("studiokit-schedule-select")?.value || "Session Plan";
    const html = document.getElementById("studiokit-agenda-preview")?.innerHTML || "";
    printHtmlDocument(`${badge} Merit Badge — Counselor Teaching Plan`, fmt, html);
  });
  document.getElementById("btn-download-agenda-md")?.addEventListener("click", () => {
    const badge = (state.currentResult?.badge_name || "Merit_Badge").replace(/\s+/g, "_");
    const md = state.currentResult?.session_agenda?.agenda_markdown || "";
    triggerMarkdownDownload(`${badge}_Session_Agenda.md`, md);
  });

  // F4: Parent Prerequisite Letter Copy, mailto:, Gmail Compose, Print & .MD Download
  document.getElementById("btn-copy-letter")?.addEventListener("click", (e) => {
    const md = getLiveParentLetterMarkdown(state.currentResult);
    copyTextWithFeedback(e.currentTarget, md, "✅ Copied Letter!");
  });

  const handleMailtoLetter = (e) => {
    const btn = e.currentTarget;
    const badge = state.currentResult?.badge_name || "Merit Badge";
    const troop = document.getElementById("input-troop-name")?.value || "Troop 123";
    const counselorEmail = document.getElementById("input-counselor-email")?.value || "";
    const rawMd = getLiveParentLetterMarkdown(state.currentResult);
    const plainBody = getPlainEmailBodyFromMarkdown(rawMd);
    copyTextWithFeedback(btn, plainBody, "✅ Opening Email App (Copied!)");
    const subject = encodeURIComponent(`[${troop}] ${badge} Merit Badge — Parent Prerequisite & Safety Letter`);
    const body = encodeURIComponent(plainBody.slice(0, 1800));
    const mailtoHref = `mailto:?cc=${encodeURIComponent(counselorEmail)}&subject=${subject}&body=${body}`;
    const link = document.createElement("a");
    link.href = mailtoHref;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };
  document.getElementById("btn-mailto-letter")?.addEventListener("click", handleMailtoLetter);
  document.getElementById("btn-email-letter-mailto")?.addEventListener("click", handleMailtoLetter);

  const handleGmailLetter = (e) => {
    const btn = e.currentTarget;
    const badge = state.currentResult?.badge_name || "Merit Badge";
    const troop = document.getElementById("input-troop-name")?.value || "Troop 123";
    const counselorEmail = document.getElementById("input-counselor-email")?.value || "";
    const rawMd = getLiveParentLetterMarkdown(state.currentResult);
    const plainBody = getPlainEmailBodyFromMarkdown(rawMd);
    copyTextWithFeedback(btn, plainBody, "✅ Opening Gmail Tab...");
    const subject = encodeURIComponent(`[${troop}] ${badge} Merit Badge — Parent Prerequisite & Safety Letter`);
    const body = encodeURIComponent(plainBody.slice(0, 1800));
    const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&cc=${encodeURIComponent(counselorEmail)}&su=${subject}&body=${body}`;
    window.open(gmailUrl, "_blank", "noopener,noreferrer");
  };
  document.getElementById("btn-gmail-letter")?.addEventListener("click", handleGmailLetter);
  document.getElementById("btn-email-letter-gmail")?.addEventListener("click", handleGmailLetter);

  document.getElementById("btn-print-letter")?.addEventListener("click", () => {
    const badge = state.currentResult?.badge_name || "Merit Badge";
    const troop = document.getElementById("input-troop-name")?.value || "Troop 123";
    const html = document.getElementById("studiokit-letter-preview")?.innerHTML || "";
    printHtmlDocument(`${badge} Merit Badge — Parent Prerequisite & Youth Protection Letter`, troop, html);
  });
  document.getElementById("btn-download-letter-md")?.addEventListener("click", () => {
    const badge = (state.currentResult?.badge_name || "Merit_Badge").replace(/\s+/g, "_");
    const md = getLiveParentLetterMarkdown(state.currentResult);
    triggerMarkdownDownload(`${badge}_Parent_Prerequisite_Letter.md`, md);
  });

  // F5: Quartermaster Gear Patrol Size Multiplier, Copy & Print
  document.getElementById("gear-patrol-size-select")?.addEventListener("change", () => {
    if (state.currentResult) {
      renderQuartermasterGearChecklist(state.currentResult);
    }
  });
  const handleCopyGearList = (e) => {
    const text = buildQuartermasterGearMarkdown(state.currentResult);
    copyTextWithFeedback(e.currentTarget, text, "✅ Copied Packing List!");
  };
  document.getElementById("btn-copy-gear-list")?.addEventListener("click", handleCopyGearList);
  document.getElementById("btn-copy-gear-checklist")?.addEventListener("click", handleCopyGearList);

  const handlePrintGearList = () => {
    const badge = state.currentResult?.badge_name || "Merit Badge";
    const patrolSize = document.getElementById("gear-patrol-size-select")?.value || "8";
    const md = buildQuartermasterGearMarkdown(state.currentResult);
    printHtmlDocument(
      `${badge} Merit Badge — Master Quartermaster Gear & Station Packing Checklist`,
      `Scaled for Patrol of ${patrolSize} Scouts`,
      renderMarkdownToStyledHtml(md)
    );
  };
  document.getElementById("btn-print-gear-list")?.addEventListener("click", handlePrintGearList);
  document.getElementById("btn-print-gear-checklist")?.addEventListener("click", handlePrintGearList);

  // F6: Blue Card Roster Add / Reset / CSV Export / Print
  document.getElementById("btn-bluecard-add-scout")?.addEventListener("click", () => {
    const inputEl = document.getElementById("bluecard-scout-name-input");
    const rawName = (inputEl?.value || "").trim();
    if (!rawName || !state.currentResult) return;
    const roster = loadBadgeBlueCardRoster(state.currentResult.badge_name);
    if (!roster.scouts.some((s) => s.name.toLowerCase() === rawName.toLowerCase())) {
      roster.scouts.push({ name: rawName, completedReqs: [] });
      saveBadgeBlueCardRoster(state.currentResult.badge_name, roster);
    }
    if (inputEl) inputEl.value = "";
    renderBlueCardTracker(state.currentResult);
  });
  document.getElementById("bluecard-scout-name-input")?.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
      ev.preventDefault();
      document.getElementById("btn-bluecard-add-scout")?.click();
    }
  });
  document.getElementById("btn-bluecard-reset-roster")?.addEventListener("click", () => {
    if (!state.currentResult) return;
    const key = BLUECARD_STORAGE_PREFIX + badgeNameToEmblemSlug(state.currentResult.badge_name);
    try {
      window.localStorage.removeItem(key);
    } catch (_e) {}
    renderBlueCardTracker(state.currentResult);
  });
  document.getElementById("btn-bluecard-export-csv")?.addEventListener("click", () => {
    if (!state.currentResult) return;
    exportBlueCardCsv(state.currentResult);
  });
  document.getElementById("btn-bluecard-print")?.addEventListener("click", () => {
    if (!state.currentResult) return;
    printBlueCardSignOffSheet(state.currentResult);
  });
}

// ---------------------------------------------------------------------------
// F5: Master Quartermaster Gear & Skill Station Packing Checklist
// ---------------------------------------------------------------------------
function deriveGearGroupsForBadge(result) {
  const reqs = result?.research_artifact?.requirements || [];
  const badgeName = result?.badge_name || "Merit Badge";
  const groups = [];

  reqs.forEach((r) => {
    const rawGear = Array.isArray(r.gear_checklist) ? r.gear_checklist.filter(Boolean) : [];
    const mode = r.execution_mode || "IN_CLASS_DISCUSSION";
    let items = rawGear.slice();

    if (items.length === 0 && (mode === "HANDS_ON_SKILL_STATION" || mode === "PREREQUISITE_CAMPOUT_HOME")) {
      const txtLower = String(r.req_text || "").toLowerCase();
      if (txtLower.includes("kit") || txtLower.includes("first aid")) {
        items = [
          "Personal First-Aid Kit (adhesive bandages, sterile gauze pads, nitrile gloves, moleskin)",
          "Troop Trauma Station Kit (SAM splint, roller bandages, triangular cravat bandages)",
        ];
      } else if (txtLower.includes("cpr") || txtLower.includes("aed") || txtLower.includes("rescue")) {
        items = [
          "CPR Training Manikin & sanitizing wipes (1 per 2–4 Scouts)",
          "AED Trainer Unit with practice pads",
        ];
      } else if (txtLower.includes("splint") || txtLower.includes("bandage") || txtLower.includes("bleeding")) {
        items = [
          "Triangular cravat bandages & roller gauze (2 per Scout)",
          "Padded board splints / SAM splints & training windlass tourniquet",
        ];
      } else if (mode === "HANDS_ON_SKILL_STATION") {
        items = [
          `${badgeName} Hands-On Demonstration Station Equipment (Req ${r.req_number})`,
          `Printed Scout Skill Checklists & Buddy Practice Cards (Req ${r.req_number})`,
        ];
      } else {
        items = [
          `Scout Field Observation Log / Home Prerequisite Worksheet (Req ${r.req_number})`,
        ];
      }
    }

    if (items.length > 0) {
      groups.push({
        req_number: r.req_number,
        execution_mode: mode,
        edge_phase: r.edge_phase || "Demonstrate",
        items,
      });
    }
  });

  if (groups.length === 0) {
    groups.push({
      req_number: "All",
      execution_mode: "IN_CLASS_DISCUSSION",
      edge_phase: "Explain & Demonstrate",
      items: [
        `Official Scouts BSA ${badgeName} Merit Badge Pamphlet`,
        `Printable ${badgeName} Scout Workbook & Blue Cards (#34124)`,
        "Station Name Tents, Pencils & Guide to Safe Scouting Reference Sheet",
      ],
    });
  }
  return groups;
}

function scaleGearItemForPatrol(itemText, patrolSize) {
  const n = Number(patrolSize) || 8;
  const lower = String(itemText || "").toLowerCase();
  const isPerScout =
    lower.includes("personal") ||
    lower.includes("per scout") ||
    lower.includes("gauze") ||
    lower.includes("bandage") ||
    lower.includes("gloves") ||
    lower.includes("workbook") ||
    lower.includes("worksheet") ||
    lower.includes("log");
  if (isPerScout) {
    return `${itemText} — [Qty: ×${n} (${n === 1 ? "1 Scout" : `Patrol of ${n}`})]`;
  }
  const stationCount = Math.max(1, Math.ceil(n / 4));
  return `${itemText} — [Qty: ${stationCount} Station Set${stationCount > 1 ? "s" : ""}]`;
}

function buildQuartermasterGearMarkdown(result) {
  if (!result) return "# Master Quartermaster Gear Checklist";
  const patrolSize = Number(document.getElementById("gear-patrol-size-select")?.value || 8);
  const groups = deriveGearGroupsForBadge(result);
  const lines = [
    `# ${result.badge_name} Merit Badge — Master Quartermaster Gear & Station Packing Checklist`,
    `**Scaled for:** Patrol / Class of ${patrolSize} Scout${patrolSize === 1 ? "" : "s"}`,
    "",
  ];
  groups.forEach((g) => {
    lines.push(`### Requirement ${g.req_number} (${g.execution_mode.replace(/_/g, " ")})`);
    g.items.forEach((it) => {
      lines.push(`- [ ] ${scaleGearItemForPatrol(it, patrolSize)}`);
    });
    lines.push("");
  });
  return lines.join("\n");
}

function renderQuartermasterGearChecklist(result) {
  const container =
    document.getElementById("studiokit-gear-checklist-grid") ||
    document.getElementById("studiokit-gear-checklist-body");
  if (!container || !result) return;
  const patrolSize = Number(document.getElementById("gear-patrol-size-select")?.value || 8);
  const groups = deriveGearGroupsForBadge(result);

  container.innerHTML = groups
    .map((g, gIdx) => {
      const modeLabel =
        g.execution_mode === "HANDS_ON_SKILL_STATION"
          ? "🛠️ Hands-On Station"
          : g.execution_mode === "PREREQUISITE_CAMPOUT_HOME"
          ? "🏕️ Field / Home Prereq"
          : "💬 Classroom Discussion";
      const rowsHtml = g.items
        .map((itemText, iIdx) => {
          const itemKey = `${g.req_number}_${gIdx}_${iIdx}`;
          const isChecked = state.checkedGearItems.has(itemKey);
          const scaledText = scaleGearItemForPatrol(itemText, patrolSize);
          return `
            <label class="m3-gear-item-row ${isChecked ? "checked" : ""}" data-gear-key="${escapeHtml(itemKey)}">
              <input type="checkbox" ${isChecked ? "checked" : ""} />
              <span>${escapeHtml(scaledText)}</span>
            </label>
          `;
        })
        .join("");

      return `
        <div class="m3-gear-group-card">
          <div class="m3-gear-group-header">
            <span style="font-weight:800; font-size:0.84rem; color:#003F87;">Requirement ${escapeHtml(g.req_number)}</span>
            <span class="m3-chip m3-chip-secondary" style="font-size:0.68rem; padding:2px 8px;">${modeLabel}</span>
          </div>
          ${rowsHtml}
        </div>
      `;
    })
    .join("");

  container.querySelectorAll(".m3-gear-item-row").forEach((row) => {
    const cb = row.querySelector('input[type="checkbox"]');
    const key = row.getAttribute("data-gear-key") || "";
    cb?.addEventListener("change", () => {
      if (cb.checked) {
        state.checkedGearItems.add(key);
        row.classList.add("checked");
      } else {
        state.checkedGearItems.delete(key);
        row.classList.remove("checked");
      }
    });
  });
}

// ---------------------------------------------------------------------------
// F6: Patrol Blue Card (#34124) & Scoutbook Plus Requirement Sign-Off Tracker
// ---------------------------------------------------------------------------
function getBlueCardRosterStorageKey(badgeName) {
  if (state.activeWorkspaceId) {
    return `${BLUECARD_STORAGE_PREFIX}ws_${state.activeWorkspaceId}`;
  }
  return BLUECARD_STORAGE_PREFIX + badgeNameToEmblemSlug(badgeName);
}

function loadBadgeBlueCardRoster(badgeName) {
  const wsKey = getBlueCardRosterStorageKey(badgeName);
  const badgeKey = BLUECARD_STORAGE_PREFIX + badgeNameToEmblemSlug(badgeName);
  try {
    const raw = window.localStorage.getItem(wsKey) || window.localStorage.getItem(badgeKey);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && Array.isArray(parsed.scouts)) {
        return parsed;
      }
    }
  } catch (_e) {}
  return {
    scouts: [
      { name: "Alex Carter (Patrol Leader)", completedReqs: [] },
      { name: "Sam Rivera", completedReqs: [] },
      { name: "Jordan Patel", completedReqs: [] },
    ],
  };
}

function saveBadgeBlueCardRoster(badgeName, rosterObj) {
  const wsKey = getBlueCardRosterStorageKey(badgeName);
  const badgeKey = BLUECARD_STORAGE_PREFIX + badgeNameToEmblemSlug(badgeName);
  try {
    const serialized = JSON.stringify(rosterObj);
    window.localStorage.setItem(wsKey, serialized);
    window.localStorage.setItem(badgeKey, serialized);
  } catch (_e) {}
  if (typeof window.syncActiveWorkspaceBlueCardRoster === "function") {
    window.syncActiveWorkspaceBlueCardRoster(rosterObj);
  }
}

function renderBlueCardTracker(result) {
  const container = document.getElementById("bluecard-matrix-container");
  if (!container || !result) return;
  const badgeName = result.badge_name || "First Aid";
  const reqs = result.research_artifact?.requirements || [];
  const roster = loadBadgeBlueCardRoster(badgeName);

  if (reqs.length === 0) {
    container.innerHTML = `<div style="padding:14px; color:#64748B;">No requirements loaded for Blue Card tracking.</div>`;
    return;
  }

  const headerCols = reqs
    .map((r) => {
      const rNum = String(r.req_number);
      const allColChecked =
        roster.scouts.length > 0 &&
        roster.scouts.every((s) => (s.completedReqs || []).includes(rNum));
      return `<th title="${escapeHtml(r.req_text || "")}">
        <label style="display:inline-flex; align-items:center; gap:4px; cursor:pointer;">
          <input type="checkbox" class="m3-bluecard-col-check" data-bc-col-req="${escapeHtml(rNum)}" ${allColChecked ? "checked" : ""} style="accent-color:#003F87; width:14px; height:14px; cursor:pointer;" title="Toggle Requirement ${escapeHtml(rNum)} for entire patrol" />
          <span>Req ${escapeHtml(rNum)}</span>
        </label>
      </th>`;
    })
    .join("");

  const bodyRows = roster.scouts
    .map((scout, sIdx) => {
      const completedSet = new Set(scout.completedReqs || []);
      const doneCount = reqs.filter((r) => completedSet.has(String(r.req_number))).length;
      const isComplete = doneCount === reqs.length && reqs.length > 0;
      const statusPill = isComplete
        ? `<span class="m3-chip m3-chip-success" style="font-size:0.70rem; padding:2px 8px;">✓ COMPLETE (${doneCount}/${reqs.length})</span>`
        : `<span class="m3-chip m3-chip-gold" style="font-size:0.70rem; padding:2px 8px;">Partial (${doneCount}/${reqs.length})</span>`;

      const reqCells = reqs
        .map((r) => {
          const rNum = String(r.req_number);
          const checked = completedSet.has(rNum) ? "checked" : "";
          return `<td><input type="checkbox" data-bc-scout="${sIdx}" data-bc-req="${escapeHtml(rNum)}" ${checked} style="accent-color:#003F87; width:15px; height:15px; cursor:pointer;" /></td>`;
        })
        .join("");

      return `
        <tr>
          <td>
            <div style="display:flex; align-items:center; justify-content:space-between; gap:6px;">
              <span>${escapeHtml(scout.name)}</span>
              <button type="button" data-bc-remove-scout="${sIdx}" title="Remove Scout" style="border:none; background:transparent; color:#94A3B8; cursor:pointer; font-size:0.78rem;">✕</button>
            </div>
          </td>
          <td>${statusPill}</td>
          <td>
            <button type="button" class="m3-btn m3-btn-outlined" data-bc-toggle-all="${sIdx}" style="padding:2px 8px; font-size:0.68rem;">
              ${isComplete ? "Clear" : "All ✓"}
            </button>
          </td>
          ${reqCells}
        </tr>
      `;
    })
    .join("");

  container.innerHTML = `
    <table class="m3-bluecard-table">
      <thead>
        <tr>
          <th>Scout Name</th>
          <th>Blue Card Status</th>
          <th>Quick</th>
          ${headerCols}
        </tr>
      </thead>
      <tbody>
        ${bodyRows}
      </tbody>
    </table>
  `;

  container.querySelectorAll("input[data-bc-scout][data-bc-req]").forEach((cb) => {
    cb.addEventListener("change", () => {
      const sIdx = parseInt(cb.getAttribute("data-bc-scout") || "0", 10);
      const rNum = cb.getAttribute("data-bc-req") || "";
      const targetScout = roster.scouts[sIdx];
      if (!targetScout) return;
      const set = new Set(targetScout.completedReqs || []);
      if (cb.checked) {
        set.add(rNum);
      } else {
        set.delete(rNum);
      }
      targetScout.completedReqs = Array.from(set);
      saveBadgeBlueCardRoster(badgeName, roster);
      renderBlueCardTracker(result);
    });
  });

  container.querySelectorAll("button[data-bc-toggle-all]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sIdx = parseInt(btn.getAttribute("data-bc-toggle-all") || "0", 10);
      const targetScout = roster.scouts[sIdx];
      if (!targetScout) return;
      const allNums = reqs.map((r) => String(r.req_number));
      const allDone = allNums.every((n) => (targetScout.completedReqs || []).includes(n));
      targetScout.completedReqs = allDone ? [] : allNums;
      saveBadgeBlueCardRoster(badgeName, roster);
      renderBlueCardTracker(result);
    });
  });

  container.querySelectorAll("button[data-bc-remove-scout]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sIdx = parseInt(btn.getAttribute("data-bc-remove-scout") || "0", 10);
      roster.scouts.splice(sIdx, 1);
      saveBadgeBlueCardRoster(badgeName, roster);
      renderBlueCardTracker(result);
    });
  });

  container.querySelectorAll("input.m3-bluecard-col-check[data-bc-col-req]").forEach((colCb) => {
    colCb.addEventListener("change", () => {
      const rNum = colCb.getAttribute("data-bc-col-req") || "";
      if (!rNum) return;
      roster.scouts.forEach((scout) => {
        const set = new Set(scout.completedReqs || []);
        if (colCb.checked) {
          set.add(rNum);
        } else {
          set.delete(rNum);
        }
        scout.completedReqs = Array.from(set);
      });
      saveBadgeBlueCardRoster(badgeName, roster);
      renderBlueCardTracker(result);
    });
  });
}

function exportBlueCardCsv(result) {
  const badgeName = result.badge_name || "First Aid";
  const reqs = result.research_artifact?.requirements || [];
  const roster = loadBadgeBlueCardRoster(badgeName);
  const counselorName = document.getElementById("input-counselor-name")?.value || "Scoutmaster Bob";
  const troopName = document.getElementById("input-troop-name")?.value || "Troop 123, My Council";
  const customDate = document.getElementById("bluecard-signoff-date")?.value;
  const todayIso = customDate || new Date().toISOString().slice(0, 10);

  const csvRows = [
    ["Scout Name", "Unit", "Merit Badge", "Requirement", "Completed", "Date", "Counselor", "Overall Status"].join(","),
  ];

  roster.scouts.forEach((scout) => {
    const set = new Set(scout.completedReqs || []);
    const doneCount = reqs.filter((r) => set.has(String(r.req_number))).length;
    const statusStr = doneCount === reqs.length && reqs.length > 0 ? "COMPLETE" : `PARTIAL (${doneCount}/${reqs.length})`;
    reqs.forEach((r) => {
      const rNum = String(r.req_number);
      const isDone = set.has(rNum);
      const cells = [
        `"${String(scout.name).replace(/"/g, '""')}"`,
        `"${String(troopName).replace(/"/g, '""')}"`,
        `"${String(badgeName).replace(/"/g, '""')}"`,
        `"Req ${rNum}"`,
        isDone ? "YES" : "NO",
        isDone ? todayIso : "",
        `"${String(counselorName).replace(/"/g, '""')}"`,
        `"${statusStr}"`,
      ];
      csvRows.push(cells.join(","));
    });
  });

  const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${badgeName.replace(/\s+/g, "_")}_Scoutbook_BlueCard_Export.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function printBlueCardSignOffSheet(result) {
  const badgeName = result.badge_name || "First Aid";
  const counselorName = document.getElementById("input-counselor-name")?.value || "Scoutmaster Bob";
  const troopName = document.getElementById("input-troop-name")?.value || "Troop 123, My Council";
  const matrixHtml = document.getElementById("bluecard-matrix-container")?.innerHTML || "";
  const sigBlock = `
    <div style="margin-top:24px; padding-top:14px; border-top:2px solid #CBD5E1; display:flex; justify-content:space-between; font-size:12.5px;">
      <div><strong>Merit Badge Counselor:</strong> ${escapeHtml(counselorName)} (${escapeHtml(troopName)})</div>
      <div><strong>Counselor Signature:</strong> ___________________________ &nbsp;&nbsp; <strong>Date:</strong> ____________</div>
    </div>
  `;
  printHtmlDocument(
    `Application for Merit Badge (#34124) — ${badgeName} Patrol Sign-Off Record`,
    `Counselor: ${counselorName} • ${troopName}`,
    matrixHtml + sigBlock
  );
}

function importBlueCardCsvFile(file, result) {
  if (!file || !result) return;
  const badgeName = result.badge_name || "First Aid";
  const reader = new FileReader();
  reader.onload = (ev) => {
    const text = String(ev.target?.result || "");
    const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return;
    const roster = loadBadgeBlueCardRoster(badgeName);
    const byName = new Map();
    roster.scouts.forEach((s) => byName.set(s.name.toLowerCase(), s));

    lines.forEach((line, idx) => {
      const cols = line.split(",").map((c) => c.replace(/^"|"$/g, "").trim());
      if (idx === 0 && cols.some((c) => /scout|name|first|last|member/i.test(c))) {
        return;
      }
      const firstCol = cols[0] || "";
      const secondCol = cols[1] || "";
      let scoutName = firstCol;
      if (firstCol && secondCol && !/troop|pack|crew|unit|bsa|\d/i.test(secondCol) && cols.length >= 3) {
        scoutName = `${firstCol} ${secondCol}`.trim();
      }
      if (!scoutName) return;
      let scoutObj = byName.get(scoutName.toLowerCase());
      if (!scoutObj) {
        scoutObj = { name: scoutName, completedReqs: [] };
        roster.scouts.push(scoutObj);
        byName.set(scoutName.toLowerCase(), scoutObj);
      }
      // If CSV row includes requirement completion (e.g. Req 1, YES)
      const reqCol = cols.find((c) => /^req\s*\d+/i.test(c));
      const doneCol = cols.find((c) => /^(yes|true|complete|completed)$/i.test(c));
      if (reqCol && doneCol) {
        const reqNum = reqCol.replace(/^req\s*/i, "").trim();
        if (reqNum && !scoutObj.completedReqs.includes(reqNum)) {
          scoutObj.completedReqs.push(reqNum);
        }
      }
    });

    saveBadgeBlueCardRoster(badgeName, roster);
    renderBlueCardTracker(result);
  };
  reader.readAsText(file);
}

function printThreePanelBlueCards(result) {
  const res = result || state.currentResult;
  if (!res) return;
  const badgeName = res.badge_name || "First Aid";
  const reqs = res.research_artifact?.requirements || [];
  const roster = loadBadgeBlueCardRoster(badgeName);
  const counselorName = document.getElementById("input-counselor-name")?.value || "Scoutmaster Bob";
  const troopName = document.getElementById("input-troop-name")?.value || "Troop 123, My Council";
  const counselorPhone = document.getElementById("input-counselor-phone")?.value || "(000) 555-1234";
  const counselorEmail = document.getElementById("input-counselor-email")?.value || "counselor@troop123.org";
  const signDate = document.getElementById("bluecard-signoff-date")?.value || new Date().toISOString().slice(0, 10);

  const cardsHtml = roster.scouts
    .map((scout) => {
      const completedSet = new Set(scout.completedReqs || []);
      const doneCount = reqs.filter((r) => completedSet.has(String(r.req_number))).length;
      const isComplete = doneCount === reqs.length && reqs.length > 0;
      const reqGridHtml = reqs
        .map((r) => {
          const rNum = String(r.req_number);
          const isDone = completedSet.has(rNum);
          return `
            <div style="display:flex; justify-content:space-between; border-bottom:1px dotted #94A3B8; padding:2px 4px; font-size:10.5px;">
              <span><strong>Req ${escapeHtml(rNum)}</strong></span>
              <span>${isDone ? `✓ ${escapeHtml(signDate)} (${escapeHtml(counselorName.split(" ").map((n) => n[0]).join(""))})` : "____/____/____"}</span>
            </div>
          `;
        })
        .join("");

      return `
        <div style="border:2px solid #003F87; border-radius:10px; background:#F0F9FF; margin-bottom:18px; page-break-inside:avoid; display:grid; grid-template-columns:1fr 1.15fr 1fr;">
          <div style="padding:12px; border-right:2px dashed #003F87;">
            <div style="font-size:10px; font-weight:800; color:#003F87; text-transform:uppercase; letter-spacing:0.05em;">Panel 1 • Application for Merit Badge (#34124)</div>
            <div style="font-size:14px; font-weight:800; color:#0F172A; margin-top:4px;">${escapeHtml(scout.name)}</div>
            <div style="font-size:11.5px; color:#334155; margin-top:2px;"><strong>Unit:</strong> ${escapeHtml(troopName)}</div>
            <div style="font-size:12.5px; font-weight:800; color:#003F87; margin-top:6px;">Merit Badge: ${escapeHtml(badgeName)}</div>
            <div style="font-size:11px; margin-top:8px; padding:6px 8px; background:#FFFFFF; border:1px solid #93C5FD; border-radius:6px;">
              <strong>Status:</strong> ${isComplete ? `✓ COMPLETE (${doneCount}/${reqs.length})` : `PARTIAL (${doneCount}/${reqs.length} Reqs)`}<br/>
              <strong>Date:</strong> ${escapeHtml(signDate)}
            </div>
            <div style="font-size:10.5px; color:#475569; margin-top:10px;">
              <strong>Unit Leader Signature:</strong><br/>_______________________________
            </div>
          </div>
          <div style="padding:12px; border-right:2px dashed #003F87; background:#FFFFFF;">
            <div style="font-size:10px; font-weight:800; color:#003F87; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:4px;">Panel 2 • Counselor Requirement Record</div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:2px 10px;">
              ${reqGridHtml}
            </div>
            <div style="font-size:10.5px; color:#1E293B; margin-top:8px; padding-top:6px; border-top:1px solid #CBD5E1;">
              <strong>Counselor:</strong> ${escapeHtml(counselorName)} &bull; ${escapeHtml(counselorPhone)} &bull; ${escapeHtml(counselorEmail)}
            </div>
          </div>
          <div style="padding:12px;">
            <div style="font-size:10px; font-weight:800; color:#003F87; text-transform:uppercase; letter-spacing:0.05em;">Panel 3 • Applicant's Record &amp; Counselor Stub</div>
            <div style="font-size:12.5px; font-weight:800; color:#0F172A; margin-top:4px;">${escapeHtml(scout.name)}</div>
            <div style="font-size:11.5px; color:#003F87; font-weight:700; margin-top:2px;">${escapeHtml(badgeName)} Merit Badge</div>
            <div style="font-size:10.5px; color:#334155; margin-top:6px;">
              Completed: <strong>${doneCount} of ${reqs.length} Requirements</strong><br/>
              Date Verified: <strong>${escapeHtml(signDate)}</strong>
            </div>
            <div style="font-size:10.5px; color:#334155; margin-top:10px;">
              <strong>Counselor Signature:</strong><br/>_______________________________<br/>
              <span style="font-size:9.5px; color:#64748B;">${escapeHtml(counselorName)} (${escapeHtml(troopName)})</span>
            </div>
          </div>
        </div>
      `;
    })
    .join("");

  printHtmlDocument(
    `Printable 3-Panel Blue Cards (#34124) — ${badgeName} Merit Badge`,
    `${roster.scouts.length} Scout Blue Card Record(s) • Counselor: ${counselorName} (${troopName})`,
    cardsHtml
  );
}

// ISO/IEC 18004 Standard QR Code Encoder (Byte Mode, Error Correction Level M ~15% recovery, GF(256) Reed-Solomon)
// Version specs: [size, ecCwPerBlock, g1Blocks, g1DataCw, g2Blocks, g2DataCw, alignCenters]
const QR_VERSION_SPECS_M_JS = {
  1: [21, 10, 1, 16, 0, 0, []],
  2: [25, 16, 1, 28, 0, 0, [6, 18]],
  3: [29, 26, 1, 44, 0, 0, [6, 22]],
  4: [33, 18, 2, 32, 0, 0, [6, 26]],
  5: [37, 24, 2, 43, 0, 0, [6, 30]],
  6: [41, 16, 4, 27, 0, 0, [6, 34]],
  7: [45, 18, 4, 31, 0, 0, [6, 22, 38]],
  8: [49, 22, 2, 38, 2, 39, [6, 24, 42]],
  9: [53, 22, 3, 36, 2, 37, [6, 26, 46]],
  10: [57, 26, 4, 43, 1, 44, [6, 28, 50]],
};
const QR_FORMAT_BITS_M_JS = [
  0x5412, 0x5125, 0x5e7c, 0x5b4b, 0x45f9, 0x40ce, 0x4f97, 0x4aa0,
];
const QR_VERSION_BITS_JS = {
  7: 0x07c94,
  8: 0x085bc,
  9: 0x09a99,
  10: 0x0a4d3,
};

function encodeIsoQrMatrixJs(text) {
  const utf8Bytes = Array.from(new TextEncoder().encode(String(text || "https://www.scouting.org/")));
  let chosenVer = 10;
  for (let v = 1; v <= 10; v++) {
    const spec = QR_VERSION_SPECS_M_JS[v];
    const dataCap = spec[2] * spec[3] + spec[4] * spec[5];
    const lenBits = v <= 9 ? 8 : 16;
    const maxBytes = Math.floor((dataCap * 8 - 4 - lenBits) / 8);
    if (utf8Bytes.length <= maxBytes) {
      chosenVer = v;
      break;
    }
  }
  const [size, ecCwPerBlock, g1Blocks, g1Data, g2Blocks, g2Data, alignCenters] =
    QR_VERSION_SPECS_M_JS[chosenVer];
  const totalDataCw = g1Blocks * g1Data + g2Blocks * g2Data;
  const lenBits = chosenVer <= 9 ? 8 : 16;
  const maxBytes = Math.floor((totalDataCw * 8 - 4 - lenBits) / 8);
  const payload = utf8Bytes.slice(0, maxBytes);

  const bits = [];
  const pushBits = (val, len) => {
    for (let i = len - 1; i >= 0; i--) bits.push((val >> i) & 1);
  };
  pushBits(0b0100, 4);
  pushBits(payload.length, lenBits);
  payload.forEach((b) => pushBits(b, 8));
  const maxBits = totalDataCw * 8;
  const term = Math.min(4, maxBits - bits.length);
  for (let i = 0; i < term; i++) bits.push(0);
  while (bits.length % 8 !== 0) bits.push(0);

  const dataCodewords = [];
  for (let i = 0; i < bits.length; i += 8) {
    let byte = 0;
    for (let b = 0; b < 8; b++) byte = (byte << 1) | bits[i + b];
    dataCodewords.push(byte);
  }
  const padBytes = [0xec, 0x11];
  let padIdx = 0;
  while (dataCodewords.length < totalDataCw) {
    dataCodewords.push(padBytes[padIdx % 2]);
    padIdx++;
  }

  // GF(256) tables (primitive polynomial 0x11D)
  const gfExp = new Array(512).fill(0);
  const gfLog = new Array(256).fill(0);
  let xVal = 1;
  for (let i = 0; i < 255; i++) {
    gfExp[i] = xVal;
    gfLog[xVal] = i;
    xVal <<= 1;
    if (xVal & 0x100) xVal ^= 0x11d;
  }
  for (let i = 255; i < 512; i++) gfExp[i] = gfExp[i - 255];
  const gfMul = (a, b) => (a === 0 || b === 0 ? 0 : gfExp[gfLog[a] + gfLog[b]]);

  const polyMul = (p, q) => {
    const out = new Array(p.length + q.length - 1).fill(0);
    for (let i = 0; i < p.length; i++) {
      for (let j = 0; j < q.length; j++) {
        out[i + j] ^= gfMul(p[i], q[j]);
      }
    }
    return out;
  };
  let gen = [1];
  for (let i = 0; i < ecCwPerBlock; i++) {
    gen = polyMul(gen, [1, gfExp[i]]);
  }
  const computeRsEc = (block) => {
    const msg = block.concat(new Array(ecCwPerBlock).fill(0));
    for (let i = 0; i < block.length; i++) {
      const coef = msg[i];
      if (coef !== 0) {
        for (let j = 0; j < gen.length; j++) {
          msg[i + j] ^= gfMul(gen[j], coef);
        }
      }
    }
    return msg.slice(block.length);
  };

  const dBlocks = [];
  const eBlocks = [];
  let offset = 0;
  for (let b = 0; b < g1Blocks; b++) {
    const blk = dataCodewords.slice(offset, offset + g1Data);
    offset += g1Data;
    dBlocks.push(blk);
    eBlocks.push(computeRsEc(blk));
  }
  for (let b = 0; b < g2Blocks; b++) {
    const blk = dataCodewords.slice(offset, offset + g2Data);
    offset += g2Data;
    dBlocks.push(blk);
    eBlocks.push(computeRsEc(blk));
  }

  const finalCodewords = [];
  const maxDataLen = Math.max(g1Data, g2Data);
  for (let col = 0; col < maxDataLen; col++) {
    for (let b = 0; b < dBlocks.length; b++) {
      if (col < dBlocks[b].length) finalCodewords.push(dBlocks[b][col]);
    }
  }
  for (let col = 0; col < ecCwPerBlock; col++) {
    for (let b = 0; b < eBlocks.length; b++) {
      finalCodewords.push(eBlocks[b][col]);
    }
  }

  const streamBits = [];
  finalCodewords.forEach((cw) => {
    for (let b = 7; b >= 0; b--) streamBits.push((cw >> b) & 1);
  });
  if (chosenVer >= 2 && chosenVer <= 6) {
    for (let i = 0; i < 7; i++) streamBits.push(0);
  }

  const matrix = Array.from({ length: size }, () => new Array(size).fill(null));
  const isFunc = Array.from({ length: size }, () => new Array(size).fill(false));

  const placeFinder = (r0, c0) => {
    for (let dr = -1; dr <= 7; dr++) {
      for (let dc = -1; dc <= 7; dc++) {
        const rr = r0 + dr;
        const cc = c0 + dc;
        if (rr >= 0 && rr < size && cc >= 0 && cc < size) {
          const inOuter = dr >= 0 && dr <= 6 && dc >= 0 && dc <= 6;
          const isBorder = dr === 0 || dr === 6 || dc === 0 || dc === 6;
          const isCenter = dr >= 2 && dr <= 4 && dc >= 2 && dc <= 4;
          matrix[rr][cc] = inOuter && (isBorder || isCenter);
          isFunc[rr][cc] = true;
        }
      }
    }
  };
  placeFinder(0, 0);
  placeFinder(0, size - 7);
  placeFinder(size - 7, 0);

  for (let i = 8; i < size - 8; i++) {
    const bit = i % 2 === 0;
    matrix[6][i] = bit;
    isFunc[6][i] = true;
    matrix[i][6] = bit;
    isFunc[i][6] = true;
  }

  alignCenters.forEach((ar) => {
    alignCenters.forEach((ac) => {
      if ((ar <= 8 && ac <= 8) || (ar <= 8 && ac >= size - 8) || (ar >= size - 8 && ac <= 8)) return;
      for (let dr = -2; dr <= 2; dr++) {
        for (let dc = -2; dc <= 2; dc++) {
          const rr = ar + dr;
          const cc = ac + dc;
          matrix[rr][cc] = Math.max(Math.abs(dr), Math.abs(dc)) !== 1;
          isFunc[rr][cc] = true;
        }
      }
    });
  });

  matrix[size - 8][8] = true;
  isFunc[size - 8][8] = true;
  for (let i = 0; i < 9; i++) {
    if (i < size) {
      isFunc[8][i] = true;
      isFunc[i][8] = true;
    }
  }
  for (let i = 0; i < 8; i++) {
    isFunc[8][size - 1 - i] = true;
    isFunc[size - 1 - i][8] = true;
  }

  if (QR_VERSION_BITS_JS[chosenVer]) {
    const vbits = QR_VERSION_BITS_JS[chosenVer];
    for (let i = 0; i < 18; i++) {
      const bit = ((vbits >> i) & 1) === 1;
      const a = size - 11 + (i % 3);
      const b = Math.floor(i / 3);
      matrix[a][b] = bit;
      isFunc[a][b] = true;
      matrix[b][a] = bit;
      isFunc[b][a] = true;
    }
  }

  let bitIdx = 0;
  let upward = true;
  let col = size - 1;
  while (col > 0) {
    if (col === 6) col -= 1;
    const rows = upward
      ? Array.from({ length: size }, (_, k) => size - 1 - k)
      : Array.from({ length: size }, (_, k) => k);
    for (const r of rows) {
      for (const dc of [0, -1]) {
        const c = col + dc;
        if (!isFunc[r][c]) {
          const bVal = bitIdx < streamBits.length ? Boolean(streamBits[bitIdx]) : false;
          bitIdx++;
          const maskBit = (r + c) % 2 === 0; // Mask 0
          matrix[r][c] = bVal !== maskBit;
        }
      }
    }
    upward = !upward;
    col -= 2;
  }

  const fmt = QR_FORMAT_BITS_M_JS[0];
  const fbits = Array.from({ length: 15 }, (_, i) => Boolean((fmt >> i) & 1));
  const coordsTl = [
    [8, 0], [8, 1], [8, 2], [8, 3], [8, 4], [8, 5], [8, 7], [8, 8],
    [7, 8], [5, 8], [4, 8], [3, 8], [2, 8], [1, 8], [0, 8],
  ];
  coordsTl.forEach(([r, c], idx) => {
    matrix[r][c] = fbits[14 - idx];
  });
  for (let i = 0; i < 7; i++) matrix[size - 1 - i][8] = fbits[14 - i];
  for (let i = 7; i < 15; i++) matrix[8][size - 15 + i] = fbits[14 - i];
  return matrix;
}

function renderInlineQrCodeSvg(urlText, labelText) {
  let fullUrl = String(urlText || "https://www.scouting.org/merit-badges/").trim();
  if (fullUrl.startsWith("/")) {
    fullUrl = `${window.location.origin}${fullUrl}`;
  } else if (!/^https?:\/\//i.test(fullUrl)) {
    fullUrl = `https://www.scouting.org/merit-badges/`;
  }
  const matrix = encodeIsoQrMatrixJs(fullUrl);
  const n = matrix.length;
  const border = 2;
  const totalModules = n + border * 2;
  const rects = [];
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      if (matrix[r][c]) {
        rects.push(`<rect x="${c + border}" y="${r + border}" width="1" height="1" fill="#003F87" />`);
      }
    }
  }
  const boxSize = Number((n * 0.21).toFixed(2));
  const boxXy = Number(((totalModules - boxSize) / 2).toFixed(2));
  const imgPad = Number((boxSize * 0.08).toFixed(2));
  const imgXy = Number((boxXy + imgPad).toFixed(2));
  const imgSize = Number((boxSize - imgPad * 2).toFixed(2));
  const logoHref = `${window.location.origin}/assets/bsa_logo.png`;
  const qrEndpoint = `/api/v1/qr.svg?url=${encodeURIComponent(fullUrl)}`;
  return `
    <a href="${escapeHtml(fullUrl)}" target="_blank" rel="noopener noreferrer" data-qr-endpoint="${escapeHtml(qrEndpoint)}" title="Scan QR with phone camera or click to open: ${escapeHtml(fullUrl)}" style="text-decoration:none; display:inline-flex; flex-direction:column; align-items:center; border:1.5px solid #CBD5E1; border-radius:8px; padding:6px 8px; background:#FFFFFF;">
      <svg width="96" height="96" viewBox="0 0 ${totalModules} ${totalModules}" shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${escapeHtml(labelText)} — ${escapeHtml(fullUrl)}">
        <rect width="${totalModules}" height="${totalModules}" fill="#FFFFFF" />
        ${rects.join("")}
        <rect x="${boxXy}" y="${boxXy}" width="${boxSize}" height="${boxSize}" rx="1.1" fill="#FFFFFF" stroke="#003F87" stroke-width="0.35" />
        <image href="${escapeHtml(logoHref)}" x="${imgXy}" y="${imgXy}" width="${imgSize}" height="${imgSize}" preserveAspectRatio="xMidYMid meet" />
      </svg>
      <div style="font-size:9.5px; font-weight:800; color:#003F87; margin-top:4px; text-align:center; max-width:112px;">${escapeHtml(labelText)} ↗</div>
    </a>
  `;
}

function printPocketFieldQrHandout(result) {
  const res = result || state.currentResult;
  if (!res) return;
  const badgeName = res.badge_name || "First Aid";
  const reqs = res.research_artifact?.requirements || [];
  const counselorName = document.getElementById("input-counselor-name")?.value || "Scoutmaster Bob";
  const troopName = document.getElementById("input-troop-name")?.value || "Troop 123, My Council";
  let pamphletUrl = document.getElementById("link-top-pamphlet")?.href || res.pamphlet_url || "https://www.scouting.org/merit-badges/";
  let drgUrl = document.getElementById("link-top-drg")?.href || res.digital_resource_guide_url || "https://www.scouting.org/skills/merit-badges/";
  if (pamphletUrl.startsWith("/")) pamphletUrl = `${window.location.origin}${pamphletUrl}`;
  if (drgUrl.startsWith("/")) drgUrl = `${window.location.origin}${drgUrl}`;
  const gearGroups = deriveGearGroupsForBadge(res);

  const reqChecklistHtml = reqs
    .map(
      (r) => `
      <div style="display:flex; align-items:flex-start; gap:6px; padding:4px 0; border-bottom:1px solid #E2E8F0; font-size:11.5px;">
        <span style="font-weight:800; color:#003F87; min-width:54px;">☐ Req ${escapeHtml(String(r.req_number))}</span>
        <span style="flex:1; color:#1E293B;">${escapeHtml(String(r.req_text || "").slice(0, 165))}</span>
        <span style="font-size:10px; font-weight:700; color:#475569; background:#F1F5F9; padding:1px 6px; border-radius:4px;">${escapeHtml(String(r.execution_mode || "IN_CLASS").replace(/_/g, " "))}</span>
      </div>
    `
    )
    .join("");

  const gearFlat = gearGroups
    .flatMap((g) => g.items.slice(0, 2).map((it) => `<li><strong>Req ${escapeHtml(String(g.req_number))}:</strong> ${escapeHtml(it)}</li>`))
    .slice(0, 8)
    .join("");

  const bodyHtml = `
    <div style="display:grid; grid-template-columns:1fr auto; gap:16px; align-items:center; background:#F8FAFC; border:1.5px solid #CBD5E1; border-radius:10px; padding:12px 14px; margin-bottom:14px;">
      <div>
        <div style="font-size:14px; font-weight:800; color:#003F87;">Scout Field Pocket Checklist &amp; Official Digital Links</div>
        <div style="font-size:11.5px; color:#334155; margin-top:4px;">
          <strong>Scout Name:</strong> ___________________________ &nbsp;&nbsp; <strong>Patrol:</strong> ___________________<br/>
          <strong>Counselor:</strong> ${escapeHtml(counselorName)} (${escapeHtml(troopName)})
        </div>
        <div style="font-size:10.5px; color:#475569; margin-top:6px;">
          <strong>Official Pamphlet PDF:</strong> <a href="${escapeHtml(pamphletUrl)}" target="_blank" rel="noopener noreferrer" style="color:#003F87;">${escapeHtml(pamphletUrl)}</a><br/>
          <strong>Digital Resource Guide:</strong> <a href="${escapeHtml(drgUrl)}" target="_blank" rel="noopener noreferrer" style="color:#003F87;">${escapeHtml(drgUrl)}</a>
        </div>
      </div>
      <div style="display:flex; gap:10px;">
        ${renderInlineQrCodeSvg(pamphletUrl, "Official BSA Pamphlet PDF")}
        ${renderInlineQrCodeSvg(drgUrl, "Digital Resource Guide")}
      </div>
    </div>
    <h3 style="margin:8px 0 4px 0; font-size:13.5px; color:#003F87;">1. Official Requirement Sign-Off Checklist (${reqs.length} Requirements)</h3>
    <div>${reqChecklistHtml}</div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:12px;">
      <div style="border:1px solid #CBD5E1; border-radius:8px; padding:10px 12px;">
        <h3 style="margin:0 0 6px 0; font-size:12.5px; color:#003F87;">2. Essential Field &amp; Station Gear</h3>
        <ul style="margin:0; padding-left:16px; font-size:11px; color:#334155;">${gearFlat}</ul>
      </div>
      <div style="border:1px solid #FCA5A5; background:#FEF2F2; border-radius:8px; padding:10px 12px;">
        <h3 style="margin:0 0 6px 0; font-size:12.5px; color:#991B1B;">3. Guide to Safe Scouting &amp; Buddy Rules</h3>
        <ul style="margin:0; padding-left:16px; font-size:11px; color:#7F1D1D;">
          <li><strong>Two-Deep Leadership:</strong> Always include a parent or second registered adult in all counselor meetings and emails.</li>
          <li><strong>Buddy System:</strong> Pair up with a Scout buddy for every skill station and field observation.</li>
          <li><strong>Hurry Cases &amp; PPE:</strong> Inspect scene safety and wear protective gloves during hands-on demonstrations.</li>
        </ul>
      </div>
    </div>
  `;

  printHtmlDocument(
    `${badgeName} Merit Badge — 1-Page Pocket Field Checklist & QR Handout`,
    `Prepared for ${troopName} • Counselor: ${counselorName}`,
    bodyHtml
  );
}

// ===========================================================================
// PHASE 4: UI-1..UI-7, COUNSELOR FEATURES C1..C5 & ZERO-PII ADMIN CONSOLE
// ===========================================================================

let presenterPopupWin = null;
let presenterBroadcastChannel = null;
try {
  if (typeof BroadcastChannel !== "undefined") {
    presenterBroadcastChannel = new BroadcastChannel("bsa_workbench_presenter_sync");
  }
} catch (_e) {
  presenterBroadcastChannel = null;
}

state.sessionTimerSeconds = 2700;
state.sessionTimerRunning = false;
state.sessionTimerInterval = null;
state.quizRevealMode = false;
state.presenterConsoleOpen = false;
state.preferredExportMode = "pptx";
state.isAdminSession = false;
state.adminCatalogItems = [];
state.selectedAdminImage = null;
state.adminAssetMatrixRows = [];

function formatTimerMmSs(totalSec) {
  const clamped = Math.max(0, Math.floor(Number(totalSec) || 0));
  const mins = Math.floor(clamped / 60);
  const secs = clamped % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function updateSessionTimerDisplay() {
  const pill = document.getElementById("session-timer-pill");
  const fsTimer = document.getElementById("fullscreen-hud-timer");
  const cluster = document.getElementById("session-timer-cluster");
  const startBtn = document.getElementById("btn-timer-start-pause");
  const formatted = formatTimerMmSs(state.sessionTimerSeconds);
  if (pill) {
    pill.textContent = formatted;
  }
  if (fsTimer) {
    fsTimer.textContent = `⏱️ ${formatted}`;
  }
  if (startBtn) {
    startBtn.textContent = state.sessionTimerRunning ? "⏸" : "▶";
  }
  if (cluster) {
    cluster.classList.toggle("timer-warn", state.sessionTimerSeconds > 0 && state.sessionTimerSeconds <= 300);
    cluster.classList.toggle("timer-expired", state.sessionTimerSeconds <= 0);
  }
  syncPresenterViewWindow();
}

function toggleSessionTimer() {
  state.sessionTimerRunning = !state.sessionTimerRunning;
  if (state.sessionTimerInterval) {
    clearInterval(state.sessionTimerInterval);
    state.sessionTimerInterval = null;
  }
  if (state.sessionTimerRunning) {
    state.sessionTimerInterval = setInterval(() => {
      if (state.sessionTimerSeconds > 0) {
        state.sessionTimerSeconds -= 1;
        updateSessionTimerDisplay();
      } else {
        state.sessionTimerRunning = false;
        clearInterval(state.sessionTimerInterval);
        state.sessionTimerInterval = null;
        updateSessionTimerDisplay();
      }
    }, 1000);
  }
  updateSessionTimerDisplay();
}

function resetSessionTimer() {
  state.sessionTimerRunning = false;
  if (state.sessionTimerInterval) {
    clearInterval(state.sessionTimerInterval);
    state.sessionTimerInterval = null;
  }
  const presetEl = document.getElementById("session-timer-preset-select");
  state.sessionTimerSeconds = parseInt(presetEl?.value || "2700", 10) || 2700;
  updateSessionTimerDisplay();
}

// Feature C2: Classroom Quiz & Scenario Answer Reveal Mask
function applyQuizRevealMaskIfEnabled(slide) {
  const leftZone = document.getElementById("stage-left-cards");
  if (!leftZone || !slide) return;
  const cards = leftZone.querySelectorAll(".m3-slide-card-item");
  if (!state.quizRevealMode) {
    cards.forEach((c) => c.classList.remove("m3-quiz-masked", "revealed"));
    return;
  }
  const arch = String(slide.archetype || "").toUpperCase();
  const isQuizSlide = arch === "SOCRATIC_CHECKPOINT_QUIZ" || arch === "WORKED_EXAMPLE_TEMPLATE";
  cards.forEach((card, idx) => {
    const textContent = (card.textContent || "").toLowerCase();
    const shouldMask =
      (isQuizSlide && idx > 0) ||
      textContent.includes("answer:") ||
      textContent.includes("solution:") ||
      textContent.includes("debrief:") ||
      textContent.includes("correct response") ||
      idx >= Math.ceil(cards.length / 2);
    if (shouldMask) {
      card.classList.add("m3-quiz-masked");
      card.title = "Click or press Space to reveal answer to Scouts";
      if (!card.querySelector(".m3-quiz-reveal-hint")) {
        const hint = document.createElement("span");
        hint.className = "m3-quiz-reveal-hint";
        hint.textContent = "👆 Click or Space to Reveal";
        card.prepend(hint);
      }
      card.onclick = () => {
        card.classList.toggle("revealed");
      };
    }
  });
}

// UI-3: Visual Archetype Thumbnail Picker Sync
function syncArchetypeVisualPicker(activeArch) {
  const archVal = activeArch || document.getElementById("codesign-archetype-select")?.value || "SPLIT_VISUAL_EXPLAINER";
  document.querySelectorAll("#codesign-archetype-visual-grid .m3-arch-thumb-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-arch") === archVal);
  });
}

// UI-2 & Plan 7 #3 / Plan 11 #2: In-Stage Split-Screen Presenter Console + Dual-Window 2nd-Monitor Pop-Out
function formatPresenterCueBodyHtml(rawSegment) {
  let decorated = escapeHtml(String(rawSegment || "").trim());
  decorated = decorated
    .replace(/\*{1,2}([^*\n]{2,110}?)\*{2}/g, "<strong>$1</strong>")
    .replace(/\*{2}([^*\n]{2,110}?)\*{1,2}/g, "<strong>$1</strong>");
  decorated = decorated.replace(
    /\[Expected Answer:\s*([^\]]+)\]/gi,
    '<div class="m3-expected-answer-box"><strong>✓ Expected Answer:</strong> $1</div>'
  );
  decorated = decorated.replace(
    /\[((?!SAY\]|DEMONSTRATE\]|ASK SCOUTS\])[^\]]{3,160})\]/g,
    '<span class="m3-stage-cue-pill">🎬 [$1]</span>'
  );
  return decorated;
}

function formatPresenterConsoleCardsHtml(rawNotes) {
  const lines = String(rawNotes || "")
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length === 0) {
    return "<em>No speaker notes for this slide.</em>";
  }
  const cards = [];
  for (const line of lines) {
    if (/^\[SAY\]/i.test(line)) {
      const body = formatPresenterCueBodyHtml(line.replace(/^\[SAY\]\s*/i, ""));
      cards.push(`
        <div class="m3-pc-cue-card m3-pc-cue-card-say">
          <div class="m3-pc-cue-kicker">🗣️ [SAY — CONVERSATIONAL SCRIPT]</div>
          <div>${body}</div>
        </div>
      `);
    } else if (/^\[DEMONSTRATE\]/i.test(line)) {
      const body = formatPresenterCueBodyHtml(line.replace(/^\[DEMONSTRATE\]\s*/i, ""));
      cards.push(`
        <div class="m3-pc-cue-card m3-pc-cue-card-demo">
          <div class="m3-pc-cue-kicker">🛠️ [DEMONSTRATE]</div>
          <div>${body}</div>
        </div>
      `);
    } else if (/^\[ASK SCOUTS\]/i.test(line)) {
      const body = formatPresenterCueBodyHtml(line.replace(/^\[ASK SCOUTS\]\s*/i, ""));
      cards.push(`
        <div class="m3-pc-cue-card m3-pc-cue-card-ask">
          <div class="m3-pc-cue-kicker">❓ [ASK SCOUTS]</div>
          <div>${body}</div>
        </div>
      `);
    } else {
      const body = formatPresenterCueBodyHtml(line);
      cards.push(`
        <div class="m3-pc-cue-card m3-pc-cue-card-say">
          <div class="m3-pc-cue-kicker">🗣️ [COUNSELOR NOTE]</div>
          <div>${body}</div>
        </div>
      `);
    }
  }
  return cards.join("");
}

function buildPresenterSyncPayload() {
  const res = state.currentResult || {};
  const slides = res.storyboard?.slides || [];
  const idx = state.activeSlideIdx;
  const isCover = idx === -1;
  const totalDeckSlides = slides.length + 1;
  const currSlideNum = isCover ? 1 : idx + 2;
  const nextSlideNum = Math.min(totalDeckSlides, currSlideNum + 1);
  const currSlide = isCover
    ? {
        title: `${res.badge_name || "First Aid"} Merit Badge - Cover Slide`,
        req_number: "Cover",
        presenter_notes:
          res._polishedCoverNotes ||
          document.getElementById("stage-presenter-notes")?.innerText ||
          "[SAY] Welcome to our Merit Badge session, Scouts! [Point to the Counselor Contact card on screen] Let's make sure everyone has their printable Merit Badge Workbook and pen ready, and remember our Two-Deep Leadership rule whenever you email or call with questions.\n[DEMONSTRATE] [Hold up the Merit Badge emblem and sample Workbook] Walk through today's session schedule and show where Scouts will log their field observations.\n[ASK SCOUTS] Who has already started working on the home or campout prerequisites? [Expected Answer: Collect prerequisite logs or note which Scouts need campout scheduling.]",
      }
    : slides[idx] || {};
  const nextSlide = idx + 1 < slides.length ? slides[idx + 1] : null;
  const rawNotes = currSlide.presenter_notes || "";
  return {
    badgeName: res.badge_name || "First Aid",
    slideNumberLabel: isCover ? `Cover Slide (1 of ${totalDeckSlides})` : `Slide ${currSlideNum} of ${totalDeckSlides}`,
    upNextKickerLabel: nextSlide
      ? `UP NEXT • SLIDE ${nextSlideNum} OF ${totalDeckSlides}`
      : `CURRENT • SLIDE ${currSlideNum} OF ${totalDeckSlides}`,
    reqLabel: isCover ? "Cover" : `Requirement ${currSlide.req_number || ""}`,
    slideTitle: currSlide.title || "",
    notesHtml: formatPresenterConsoleCardsHtml(rawNotes),
    nextSlideTitle: nextSlide
      ? `${nextSlide.title}${nextSlide.req_number ? ` (Req ${nextSlide.req_number})` : ""}`
      : `${currSlide.title || "Final Slide"} (End of Slide Deck)`,
    timerFormatted: formatTimerMmSs(state.sessionTimerSeconds),
  };
}

function togglePresenterConsoleMode(forceState) {
  const stageWrapper = document.getElementById("slide-stage-wrapper");
  const dockEl = document.getElementById("stage-presenter-console-dock");
  if (!stageWrapper || !dockEl) return;
  const nextActive = typeof forceState === "boolean" ? forceState : !state.presenterConsoleOpen;
  state.presenterConsoleOpen = nextActive;

  // Always ensure the construction animation stage is hidden and the 16:9 slide stage is visible
  // so Presenter View never hides the slides in either normal or fullscreen mode.
  if (nextActive) {
    hideConstructionAnimationStage();
    document.getElementById("widescreen-slide-stage")?.classList.remove("hidden");
  }

  stageWrapper.classList.toggle("is-presenter-console-active", nextActive);
  dockEl.classList.toggle("hidden", !nextActive);

  const mainBtn = document.getElementById("btn-popout-speaker-notes");
  if (mainBtn) {
    mainBtn.textContent = nextActive ? "🪟 Exit Presenter View (P)" : "🪟 Presenter View (P)";
    mainBtn.classList.toggle("m3-btn-filled", nextActive);
    mainBtn.classList.toggle("m3-btn-tonal", !nextActive);
  }
  const fsBtn = document.getElementById("btn-fs-popout-notes");
  if (fsBtn) {
    fsBtn.textContent = nextActive ? "🪟 Exit Split View (P)" : "🪟 Presenter View (P)";
  }
  syncPresenterViewWindow();
  fitActiveSlideToStage();
  setTimeout(() => fitActiveSlideToStage(), 40);
}

function changePresenterFontScale(delta) {
  const current = typeof state.presenterFontScale === "number" ? state.presenterFontScale : 0.86;
  const nextScale = Math.min(1.45, Math.max(0.72, Math.round((current + delta) * 100) / 100));
  state.presenterFontScale = nextScale;
  const dockNotes = document.getElementById("pc-dock-notes-body");
  if (dockNotes) {
    dockNotes.style.fontSize = `${nextScale}rem`;
  }
  if (presenterPopupWin && !presenterPopupWin.closed) {
    try {
      const notesEl = presenterPopupWin.document.getElementById("pv-notes-body");
      if (notesEl) {
        notesEl.style.fontSize = `${Math.round((nextScale + 0.10) * 100) / 100}rem`;
      }
    } catch (_e) {}
  }
}

function syncPresenterViewWindow() {
  const payload = buildPresenterSyncPayload();
  const slides = state.currentResult?.storyboard?.slides || [];

  // 1. Update In-Stage Split-Screen Presenter Console Dock
  const dockTitle = document.getElementById("pc-dock-slide-title");
  const dockMeta = document.getElementById("pc-dock-slide-meta");
  const dockNotes = document.getElementById("pc-dock-notes-body");
  const dockNext = document.getElementById("pc-dock-next-slide");
  const dockTimer = document.getElementById("pc-dock-timer");
  const prevBtn = document.getElementById("btn-pc-prev-slide");
  const nextBtn = document.getElementById("btn-pc-next-slide");

  if (dockTitle) dockTitle.textContent = payload.slideTitle;
  if (dockMeta) dockMeta.textContent = payload.upNextKickerLabel;
  if (dockNotes) {
    dockNotes.innerHTML = payload.notesHtml || "<em>No speaker notes for this slide.</em>";
    const scale = typeof state.presenterFontScale === "number" ? state.presenterFontScale : 0.86;
    dockNotes.style.fontSize = `${scale}rem`;
  }
  if (dockNext) dockNext.textContent = payload.nextSlideTitle;
  if (dockTimer) {
    dockTimer.textContent = payload.timerFormatted;
    dockTimer.title = state.sessionTimerRunning
      ? "Timer running (Click to Pause)"
      : "Click to Start/Resume Session Timer";
  }
  if (prevBtn) prevBtn.disabled = state.activeSlideIdx <= -1;
  if (nextBtn) nextBtn.disabled = state.activeSlideIdx >= slides.length - 1;

  // 2. BroadcastChannel + Optional 2nd-Monitor Popup Window
  try {
    presenterBroadcastChannel?.postMessage({ type: "SLIDE_SYNC", payload });
  } catch (_e) {
    // ignore
  }
  if (presenterPopupWin && !presenterPopupWin.closed) {
    try {
      const doc = presenterPopupWin.document;
      const titleEl = doc.getElementById("pv-slide-title");
      const metaEl = doc.getElementById("pv-slide-meta");
      const notesEl = doc.getElementById("pv-notes-body");
      const nextEl = doc.getElementById("pv-next-slide");
      const timerEl = doc.getElementById("pv-timer");
      const pvPrevBtn = doc.getElementById("pv-btn-prev");
      const pvNextBtn = doc.getElementById("pv-btn-next");
      if (titleEl) titleEl.textContent = payload.slideTitle;
      if (metaEl) metaEl.textContent = `${payload.badgeName} • ${payload.slideNumberLabel} • ${payload.reqLabel}`;
      if (notesEl) notesEl.innerHTML = payload.notesHtml || "<em>No speaker notes for this slide.</em>";
      if (nextEl) nextEl.textContent = payload.nextSlideTitle;
      if (timerEl) timerEl.textContent = payload.timerFormatted;
      if (pvPrevBtn) pvPrevBtn.disabled = state.activeSlideIdx <= -1;
      if (pvNextBtn) pvNextBtn.disabled = state.activeSlideIdx >= slides.length - 1;
    } catch (_e) {
      // ignore cross-window race
    }
  }
}

function openPresenterViewWindow() {
  state._openingSecondMonitorPopupAt = Date.now();
  // Ensure native OS fullscreen is not active when opening the popup so macOS never forces the popup into a Fullscreen Space
  if (document.fullscreenElement && document.exitFullscreen) {
    try {
      document.exitFullscreen().catch(() => {});
    } catch (_e) {}
  }
  const popupLeft = Math.max(20, (window.screenX || 0) + (window.outerWidth || 1200) - 660);
  const popupTop = Math.max(20, (window.screenY || 0) + 60);
  const features = `popup=yes,width=640,height=740,left=${popupLeft},top=${popupTop},resizable=yes,scrollbars=yes`;
  presenterPopupWin = window.open("", "BSAPresenterView", features);
  if (!presenterPopupWin) return;
  try {
    presenterPopupWin.resizeTo(640, 740);
  } catch (_e) {}
  // Auto-close the in-stage right dock when the 2nd Monitor popup opens so the main screen shows only the centered 16:9 slide
  if (state.presenterConsoleOpen) {
    togglePresenterConsoleMode(false);
  }
  document.getElementById("widescreen-slide-stage")?.classList.remove("hidden");
  const payload = buildPresenterSyncPayload();
  const baseFontScale = Math.round(((state.presenterFontScale || 0.86) + 0.10) * 100) / 100;
  presenterPopupWin.document.open();
  presenterPopupWin.document.write(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>2nd Monitor Speaker Teleprompter — ${escapeHtml(payload.badgeName)}</title>
  <style>
    body {
      margin: 0;
      padding: 16px 18px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0F172A;
      color: #F8FAFC;
      line-height: 1.52;
    }
    .pv-banner {
      background: rgba(30, 58, 138, 0.45);
      border: 1px solid #3B82F6;
      border-radius: 8px;
      padding: 6px 12px;
      margin-bottom: 10px;
      font-size: 0.75rem;
      color: #BFDBFE;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .pv-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #334155;
      padding-bottom: 10px;
      margin-bottom: 10px;
      gap: 8px;
      flex-wrap: wrap;
    }
    .pv-badge {
      background: #F4C430;
      color: #0F172A;
      font-size: 0.68rem;
      font-weight: 900;
      padding: 3px 9px;
      border-radius: 999px;
      letter-spacing: 0.04em;
    }
    .pv-timer {
      font-family: monospace;
      font-size: 0.92rem;
      font-weight: 800;
      color: #38BDF8;
      background: rgba(30, 41, 59, 0.95);
      padding: 4px 10px;
      border-radius: 6px;
      border: 1px solid rgba(56, 189, 248, 0.42);
      cursor: pointer;
    }
    .pv-controls {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .pv-controls button {
      height: 30px;
      background: rgba(30, 41, 59, 0.96);
      color: #E2E8F0;
      border: 1px solid rgba(148, 163, 184, 0.45);
      border-radius: 6px;
      padding: 0 10px;
      font-weight: 800;
      font-size: 0.76rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .pv-controls button:hover:not(:disabled) {
      background: #334155;
      border-color: #60A5FA;
      color: #FFFFFF;
    }
    .pv-controls button:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
    .pv-controls button.pv-close-btn {
      background: rgba(239, 68, 68, 0.22);
      border-color: rgba(248, 113, 113, 0.45);
      color: #FCA5A5;
    }
    .pv-controls button.pv-close-btn:hover {
      background: #DC2626;
      color: #FFFFFF;
    }
    .pv-upnext-card {
      background: rgba(30, 41, 59, 0.88);
      border: 1px solid rgba(148, 163, 184, 0.28);
      border-radius: 9px;
      padding: 8px 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
    }
    .pv-nav-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-bottom: 10px;
    }
    .pv-nav-grid button {
      height: 34px;
      border-radius: 8px;
      font-weight: 800;
      font-size: 0.78rem;
      cursor: pointer;
    }
    #pv-btn-prev {
      background: rgba(30, 41, 59, 0.96);
      border: 1px solid rgba(148, 163, 184, 0.42);
      color: #E2E8F0;
    }
    #pv-btn-next {
      background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
      border: 1px solid rgba(96, 165, 250, 0.55);
      color: #FFFFFF;
    }
    .pv-title {
      font-size: 1.05rem;
      font-weight: 800;
      color: #FDE047;
      margin: 4px 0 10px 0;
    }
    .pv-notes {
      display: flex;
      flex-direction: column;
      gap: 9px;
      font-size: ${baseFontScale}rem;
    }
    .m3-pc-cue-card {
      padding: 10px 12px;
      border-radius: 9px;
      line-height: 1.5;
    }
    .m3-pc-cue-card-say {
      background: rgba(30, 58, 138, 0.36);
      border-left: 3.5px solid #60A5FA;
    }
    .m3-pc-cue-card-demo {
      background: rgba(120, 53, 15, 0.36);
      border-left: 3.5px solid #FBBF24;
    }
    .m3-pc-cue-card-ask {
      background: rgba(6, 78, 59, 0.36);
      border-left: 3.5px solid #34D399;
    }
    .m3-pc-cue-kicker {
      font-size: 0.66rem;
      font-weight: 800;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      margin-bottom: 4px;
    }
    .m3-pc-cue-card-say .m3-pc-cue-kicker { color: #93C5FD; }
    .m3-pc-cue-card-demo .m3-pc-cue-kicker { color: #FCD34D; }
    .m3-pc-cue-card-ask .m3-pc-cue-kicker { color: #6EE7B7; }
    .m3-stage-cue-pill {
      display: inline-block;
      font-size: 0.78rem;
      font-weight: 700;
      font-style: italic;
      color: #FDE68A;
      background: #451A03;
      border: 1px solid #F59E0B;
      border-radius: 999px;
      padding: 1px 8px;
      margin: 1px 3px;
    }
    .m3-expected-answer-box {
      margin-top: 6px;
      padding: 8px 12px;
      background: rgba(6, 78, 59, 0.68);
      border-left: 4px solid #10B981;
      border-radius: 6px;
      font-size: 0.88rem;
      color: #A7F3D0;
      font-weight: 600;
    }
  </style>
</head>
<body>
  <div class="pv-banner">
    <span>🪟 <strong>2nd Monitor Speaker Teleprompter</strong> — Drag to your laptop screen while projecting the main slide deck.</span>
  </div>
  <div class="pv-top">
    <div style="display:flex; align-items:center; gap:8px;">
      <span class="pv-badge">PRESENTER VIEW</span>
      <span class="pv-timer" id="pv-timer" title="Click to Start/Pause Session Timer">${escapeHtml(payload.timerFormatted)}</span>
    </div>
    <div class="pv-controls">
      <button type="button" id="pv-btn-font-dec" title="Decrease Font Size">A−</button>
      <button type="button" id="pv-btn-font-inc" title="Increase Font Size">A+</button>
      <button type="button" class="pv-close-btn" id="pv-btn-close" title="Close Floating Window">✕</button>
    </div>
  </div>
  <div class="pv-upnext-card">
    <div>
      <div id="pv-slide-meta" style="font-size:0.65rem; color:#94A3B8; font-weight:800; text-transform:uppercase;">${escapeHtml(payload.upNextKickerLabel)}</div>
      <div id="pv-next-slide" style="font-size:0.78rem; color:#E2E8F0; font-weight:700; margin-top:2px;">${escapeHtml(payload.nextSlideTitle)}</div>
    </div>
    <span style="font-size:0.70rem; color:#FBBF24; font-weight:800; background:rgba(251,191,36,0.14); border:1px solid rgba(251,191,36,0.32); padding:4px 8px; border-radius:6px; white-space:nowrap;">⏱ ~2 min</span>
  </div>
  <div class="pv-nav-grid">
    <button type="button" id="pv-btn-prev">◀ Prev Slide</button>
    <button type="button" id="pv-btn-next">Next Slide ▶</button>
  </div>
  <div class="pv-title" id="pv-slide-title">${escapeHtml(payload.slideTitle)}</div>
  <div class="pv-notes" id="pv-notes-body">${payload.notesHtml}</div>
</body>
</html>`);
  presenterPopupWin.document.close();
  presenterPopupWin.document.getElementById("pv-timer")?.addEventListener("click", () => {
    toggleSessionTimer();
  });
  presenterPopupWin.document.getElementById("pv-btn-font-dec")?.addEventListener("click", () => {
    changePresenterFontScale(-0.08);
  });
  presenterPopupWin.document.getElementById("pv-btn-font-inc")?.addEventListener("click", () => {
    changePresenterFontScale(0.08);
  });
  presenterPopupWin.document.getElementById("pv-btn-prev")?.addEventListener("click", () => {
    document.getElementById("btn-prev-slide")?.click();
  });
  presenterPopupWin.document.getElementById("pv-btn-next")?.addEventListener("click", () => {
    document.getElementById("btn-next-slide")?.click();
  });
  presenterPopupWin.document.getElementById("pv-btn-close")?.addEventListener("click", () => {
    presenterPopupWin?.close();
  });
  presenterPopupWin.document.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      document.getElementById("btn-prev-slide")?.click();
    } else if (ev.key === "ArrowRight" || ev.key === " ") {
      ev.preventDefault();
      document.getElementById("btn-next-slide")?.click();
    }
  });
  try {
    presenterPopupWin.focus();
  } catch (_e) {}
}

// Feature C4: Printable 3x5 / 4x6 Counselor Pocket Cue Cards
function printCounselorPocketCueCards() {
  if (!state.currentResult) return;
  const badgeName = state.currentResult.badge_name || "First Aid";
  const slides = state.currentResult.storyboard?.slides || [];
  const cardsHtml = slides
    .map((s, idx) => {
      const notesHtml = formatSpeakerNotesHtml(s.presenter_notes || "");
      const bullets = (s.bullet_points || []).slice(0, 3).map((b) => `<li>${escapeHtml(String(b))}</li>`).join("");
      return `
        <div style="border:2px solid #003F87; border-radius:10px; padding:12px 14px; margin-bottom:14px; page-break-inside:avoid; background:#FFFFFF;">
          <div style="display:flex; justify-content:space-between; border-bottom:1.5px solid #CBD5E1; padding-bottom:5px; margin-bottom:6px; font-size:11.5px; font-weight:800; color:#003F87;">
            <span>CARD #${idx + 1} • ${escapeHtml(badgeName.toUpperCase())} • REQ ${escapeHtml(String(s.req_number || ""))}</span>
            <span>EDGE CUE CARD (3&times;5)</span>
          </div>
          <div style="font-size:14px; font-weight:800; color:#0F172A; margin-bottom:6px;">${escapeHtml(s.title || "")}</div>
          <ul style="margin:0 0 8px 16px; padding:0; font-size:11.5px; color:#334155;">${bullets}</ul>
          <div style="font-size:11.5px; background:#F8FAFC; border-left:3px solid #003F87; padding:6px 8px; border-radius:4px;">
            ${notesHtml}
          </div>
        </div>
      `;
    })
    .join("");
  printHtmlDocument(
    `${badgeName} Merit Badge — Counselor 3x5 Field Pocket Cue Cards`,
    `${slides.length} Instructional EDGE Cards ([SAY] / [DEMONSTRATE] / [ASK SCOUTS])`,
    `<div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">${cardsHtml}</div>`
  );
}

// Feature C5: Interactive Patrol / Buddy Station Rotator Matrix
function renderBuddyStationRotator(result) {
  const wrap = document.getElementById("buddy-rotator-matrix-wrap");
  if (!wrap || !result) return;
  const reqs = result.research_artifact?.requirements || [];
  const handsOn = reqs.filter((r) => r.execution_mode === "HANDS_ON_SKILL_STATION");
  const stations = (handsOn.length > 0 ? handsOn : reqs.slice(0, 4)).slice(0, 6);
  const minsPerStation = parseInt(document.getElementById("rotator-minutes-select")?.value || "12", 10) || 12;

  if (stations.length === 0) {
    wrap.innerHTML = `<div style="padding:10px; color:#64748B;">No hands-on stations found for this badge.</div>`;
    return;
  }

  const groups = stations.map((_, idx) => `Patrol / Buddy Team ${String.fromCharCode(65 + idx)}`);
  const headerCols = stations
    .map((st, sIdx) => `<th>Station ${sIdx + 1}: Req ${escapeHtml(String(st.req_number))}</th>`)
    .join("");

  const rowsHtml = stations
    .map((_, roundIdx) => {
      const startMin = roundIdx * minsPerStation;
      const endMin = (roundIdx + 1) * minsPerStation;
      const cells = stations
        .map((__, stIdx) => {
          const teamIdx = (stIdx + roundIdx) % groups.length;
          return `<td><strong>${escapeHtml(groups[teamIdx])}</strong></td>`;
        })
        .join("");
      return `
        <tr>
          <td><strong>Rotation ${roundIdx + 1}</strong> (${startMin}–${endMin}m)</td>
          ${cells}
        </tr>
      `;
    })
    .join("");

  wrap.innerHTML = `
    <table class="m3-finops-table" style="width:100%;">
      <thead>
        <tr>
          <th>Rotation Window</th>
          ${headerCols}
        </tr>
      </thead>
      <tbody>${rowsHtml}</tbody>
    </table>
  `;
}

// Feature C3: Pre-Class Scout Prerequisite Readiness Checklist
function renderPrereqReadinessChecklist(result) {
  const listEl = document.getElementById("prereq-readiness-list");
  if (!listEl || !result) return;
  const reqs = result.research_artifact?.requirements || [];
  const prereqs = reqs.filter((r) => r.execution_mode === "PREREQUISITE_CAMPOUT_HOME");
  const targetList = prereqs.length > 0 ? prereqs : reqs.slice(0, 3);

  listEl.innerHTML = targetList
    .map((r) => {
      return `
        <label style="display:flex; align-items:flex-start; gap:8px; padding:10px 12px; border:1px solid #CBD5E1; border-radius:10px; background:#F8FAFC; cursor:pointer;">
          <input type="checkbox" style="margin-top:3px; width:16px; height:16px; accent-color:#003F87;" />
          <div style="font-size:0.79rem; line-height:1.4;">
            <strong style="color:#003F87;">Req ${escapeHtml(String(r.req_number))} Pre-Check:</strong>
            <span style="color:#1E293B;">${escapeHtml(String(r.req_text || "").slice(0, 140))}</span>
          </div>
        </label>
      `;
    })
    .join("");
}

// ===========================================================================
// SUPER-USER ADMIN CONSOLE & ENHANCED COUNSELOR / UI FUNCTIONS
// ===========================================================================

async function checkAdminSessionAndInit() {
  try {
    const resp = await fetch("/api/v1/admin/session");
    if (!resp.ok) return;
    const data = await resp.json();
    state.isAdminSession = Boolean(data.is_admin);
    const adminTabBtn = document.getElementById("tab-btn-admin");
    const footerBtn = document.getElementById("btn-footer-admin-unlock");
    const modeChip = document.getElementById("admin-auth-mode-chip");
    if (adminTabBtn) {
      adminTabBtn.classList.toggle("hidden", !state.isAdminSession);
    }
    if (footerBtn) {
      footerBtn.textContent = state.isAdminSession ? "🛡️ Admin Console" : "🔒 Admin";
    }
    if (modeChip) {
      modeChip.textContent = `🔒 Zero-PII • Auth: ${data.auth_mode || "verified"}`;
    }
    if (state.currentResult) {
      renderActiveSlide(state.activeSlideIdx);
    }
  } catch (_e) {
    // ignore offline
  }
}

function populateAdminBadgeSelector() {
  const sel = document.getElementById("admin-catalog-badge-select");
  if (!sel) return;
  const badgesList =
    Array.isArray(state.badges) && state.badges.length > 0
      ? state.badges
      : Array.isArray(state.catalog) && state.catalog.length > 0
      ? state.catalog
      : [{ badge_name: "First Aid" }];
  if (sel.options.length >= 144) return;
  const prevVal = sel.value || state.currentBadge || "First Aid";
  sel.innerHTML = badgesList
    .map((b) => {
      const bName = b.badge_name || b.name || "First Aid";
      return `<option value="${escapeHtml(bName)}">${escapeHtml(bName)}</option>`;
    })
    .join("");
  if (badgesList.some((b) => (b.badge_name || b.name) === prevVal)) {
    sel.value = prevVal;
  }
}

async function loadAdminConsoleData() {
  populateAdminBadgeSelector();
  await Promise.all([
    loadAdminCatalogImages(),
    loadAdminZeroPiiTelemetry(),
    loadAdminAssetDiagnostics(),
  ]);
}

async function loadAdminCatalogImages(preselectImageId = null) {
  populateAdminBadgeSelector();
  const badgeSel = document.getElementById("admin-catalog-badge-select");
  const reqSel = document.getElementById("admin-catalog-req-select");
  const srcSel = document.getElementById("admin-catalog-source-select");
  const roleSel = document.getElementById("admin-catalog-role-select");
  const searchInput = document.getElementById("admin-catalog-search-input");
  const badgeName = badgeSel?.value || state.currentBadge || "First Aid";
  const reqVal = reqSel?.value || "ALL";
  const srcVal = srcSel?.value || "ALL";
  const roleVal = roleSel?.value || "ALL";

  try {
    const qs = new URLSearchParams({
      badge_name: badgeName,
      req_number: reqVal,
      source_type: srcVal,
      role: roleVal,
    });
    const resp = await fetch(`/api/v1/admin/catalog/images?${qs.toString()}`);
    if (!resp.ok) return;
    const data = await resp.json();
    const prevReq = reqSel?.value || "ALL";
    if (reqSel && Array.isArray(data.available_requirements)) {
      reqSel.innerHTML =
        `<option value="ALL">All Requirements</option>` +
        data.available_requirements
          .map((r) => `<option value="${escapeHtml(r)}" ${r === prevReq ? "selected" : ""}>Req ${escapeHtml(r)}</option>`)
          .join("");
    }
    let items = Array.isArray(data.images) ? data.images : [];
    const q = (searchInput?.value || "").trim().toLowerCase();
    if (q) {
      items = items.filter((it) =>
        `${it.title || ""} ${it.caption || ""} ${it.filename || ""} ${it.req_number || ""}`.toLowerCase().includes(q)
      );
    }
    state.adminCatalogItems = items;
    const countLbl = document.getElementById("admin-catalog-count-label");
    if (countLbl) {
      countLbl.textContent = `Showing ${items.length} of ${data.total_unfiltered || items.length} cached visuals for ${badgeName}`;
    }
    renderAdminCatalogGrid(preselectImageId);
  } catch (err) {
    console.warn("Admin catalog load warning:", err);
  }
}

function renderAdminCatalogGrid(preselectImageId = null) {
  const grid = document.getElementById("admin-catalog-grid");
  if (!grid) return;
  const items = state.adminCatalogItems || [];
  if (items.length === 0) {
    grid.innerHTML = `<div style="padding:18px; color:#64748B;">No cached images match the current filter for this Merit Badge.</div>`;
    return;
  }

  const targetId = preselectImageId || state.selectedAdminImage?.image_id || items[0]?.image_id;
  grid.innerHTML = items
    .map((it, idx) => {
      const isSelected = it.image_id === targetId;
      const rolePill = it.is_alternate
        ? `<span class="m3-role-badge-alt">🔄 ALT #${it.alternate_rank || 1}</span>`
        : `<span class="m3-role-badge-primary">⭐ PRIMARY</span>`;
      const dimLabel = it.width && it.height ? `${it.width}×${it.height}px • ${it.file_size_kb || 0}KB` : `${it.file_size_kb || 0}KB`;
      return `
        <div class="m3-admin-img-card ${isSelected ? "selected" : ""}" data-admin-card-idx="${idx}">
          <div style="display:flex; justify-content:space-between; align-items:center; gap:4px;">
            <span class="m3-chip m3-chip-primary" style="font-size:0.65rem; padding:1px 6px;">Req ${escapeHtml(String(it.req_number || "1"))}</span>
            ${rolePill}
          </div>
          <div class="m3-catalog-img-zoom-wrap" style="position:relative;">
            <img src="${escapeHtml(it.image_url || "")}" alt="${escapeHtml(it.title || "")}" data-admin-zoom-idx="${idx}" title="Click to inspect • Click 🔍 Zoom to open in Lightbox (up to 500%)" style="width:100%; height:128px; object-fit:contain; background:#F8FAFC; border-radius:8px; border:1px solid #E2E8F0; cursor:pointer;" loading="lazy" />
            <button type="button" class="m3-catalog-zoom-pill" data-admin-zoom-idx="${idx}" title="Open image and caption in Click-to-Zoom Lightbox (up to 500%)">🔍 Zoom</button>
          </div>
          <div style="font-size:0.79rem; font-weight:700; color:#0F172A; line-height:1.25;">${escapeHtml(it.title || it.filename || "Visual")}</div>
          <div style="font-size:0.72rem; color:#475569; line-height:1.35; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">
            ${escapeHtml(it.caption || it.description || "")}
          </div>
          <div style="font-family:var(--font-mono); font-size:0.66rem; color:#64748B; margin-top:auto;">
            ${escapeHtml(dimLabel)}
          </div>
        </div>
      `;
    })
    .join("");

  const found = items.find((i) => i.image_id === targetId) || items[0];
  if (found) {
    selectAdminCatalogImage(found, false);
  }

  grid.querySelectorAll("button.m3-catalog-zoom-pill[data-admin-zoom-idx]").forEach((zBtn) => {
    zBtn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const idx = parseInt(zBtn.getAttribute("data-admin-zoom-idx") || "0", 10);
      const chosen = items[idx];
      if (chosen && chosen.image_url) {
        selectAdminCatalogImage(chosen, false);
        openImageZoomLightbox({
          src: chosen.image_url,
          title: chosen.title || chosen.filename || "Catalog Visual",
          caption: chosen.caption || chosen.description || chosen.title || "",
        });
      }
    });
  });

  grid.querySelectorAll("[data-admin-card-idx]").forEach((cardEl) => {
    cardEl.addEventListener("click", () => {
      const idx = parseInt(cardEl.getAttribute("data-admin-card-idx") || "0", 10);
      const chosen = items[idx];
      if (chosen) {
        grid.querySelectorAll(".m3-admin-img-card").forEach((c) => c.classList.remove("selected"));
        cardEl.classList.add("selected");
        selectAdminCatalogImage(chosen, false);
      }
    });
    cardEl.addEventListener("dblclick", () => {
      const idx = parseInt(cardEl.getAttribute("data-admin-card-idx") || "0", 10);
      const chosen = items[idx];
      if (chosen && chosen.image_url) {
        openImageZoomLightbox({
          src: chosen.image_url,
          title: chosen.title || chosen.filename || "Catalog Visual",
          caption: chosen.caption || chosen.description || chosen.title || "",
        });
      }
    });
  });
}

function selectAdminCatalogImage(item, clearStatus = true) {
  if (!item) return;
  state.selectedAdminImage = item;
  const imgEl = document.getElementById("admin-inspector-img");
  const metaEl = document.getElementById("admin-inspector-file-meta");
  const roleChip = document.getElementById("admin-inspector-role-chip");
  const idInput = document.getElementById("admin-edit-image-id");
  const titleInput = document.getElementById("admin-edit-title");
  const capInput = document.getElementById("admin-edit-caption");
  const reqInput = document.getElementById("admin-edit-req");
  const roleSel = document.getElementById("admin-edit-role-select");
  const discardCb = document.getElementById("admin-edit-discard");
  const statusEl = document.getElementById("admin-inspector-status");

  if (imgEl) imgEl.src = item.image_url || "";
  if (metaEl) {
    metaEl.textContent = `${item.filename || item.image_id} • ${item.width || 0}×${item.height || 0}px (${item.file_size_kb || 0} KB) • ${item.source_type || ""}`;
  }
  if (roleChip) {
    roleChip.textContent = item.is_alternate ? `🔄 Alternate #${item.alternate_rank || 1}` : "⭐ Primary Default";
  }
  if (idInput) idInput.value = item.image_id || "";
  if (titleInput) titleInput.value = item.title || "";
  if (capInput) capInput.value = item.caption || item.description || "";
  if (reqInput) reqInput.value = item.req_number || "1";
  if (roleSel) roleSel.value = item.is_alternate ? "alternate" : "primary";
  if (discardCb) discardCb.checked = Boolean(item.discard);
  if (clearStatus && statusEl) {
    statusEl.classList.add("hidden");
  }
}

function showAdminInspectorFeedback(msg, isError = false) {
  const statusEl = document.getElementById("admin-inspector-status");
  if (!statusEl) return;
  statusEl.classList.remove("hidden");
  statusEl.style.background = isError ? "#FEF2F2" : "#F0FDF4";
  statusEl.style.border = isError ? "1px solid #FCA5A5" : "1px solid #86EFAC";
  statusEl.style.color = isError ? "#991B1B" : "#166534";
  statusEl.textContent = msg;
}

async function openAdminStudioForSlideVisual(entry) {
  populateAdminBadgeSelector();
  const badgeSel = document.getElementById("admin-catalog-badge-select");
  if (badgeSel && state.currentResult?.badge_name) {
    badgeSel.value = state.currentResult.badge_name;
  }
  const reqSel = document.getElementById("admin-catalog-req-select");
  if (reqSel) reqSel.value = "ALL";
  document.getElementById("btn-admin-subtab-catalog")?.click();
  switchMainTab("panel-admin");
  await loadAdminCatalogImages(entry?.image_id || null);
  document.getElementById("panel-admin")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderMiniHistogram(containerId, histogramArr) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const buckets = Array.isArray(histogramArr) && histogramArr.length > 0
    ? histogramArr
    : [
        { bucket: "<200ms", count: 0, pct: 8 },
        { bucket: "200-500ms", count: 0, pct: 8 },
        { bucket: "500ms-1s", count: 0, pct: 8 },
        { bucket: "1-2s", count: 0, pct: 8 },
        { bucket: ">2s", count: 0, pct: 8 },
      ];
  el.innerHTML = buckets
    .map(
      (b) => `
      <div class="m3-hist-bar-row" title="${escapeHtml(b.bucket)}: ${b.count || 0} sample(s)">
        <span>${escapeHtml(b.bucket)}</span>
        <div class="m3-hist-bar-track">
          <div class="m3-hist-bar-fill" style="width:${Math.max(6, Math.min(100, Number(b.pct || 8)))}%;"></div>
        </div>
        <span style="text-align:right;">${b.count || 0} (${Math.round(Number(b.pct || 0))}%)</span>
      </div>
    `
    )
    .join("");
}

async function loadAdminZeroPiiTelemetry() {
  try {
    const resp = await fetch("/api/v1/admin/telemetry/summary");
    if (!resp.ok) return;
    const data = await resp.json();
    const tel = data.zero_pii_telemetry || {};
    const rt = data.runtime_metrics || {};

    const runsAll = Math.max(Number(tel.runs_all_time ?? tel.total_runs ?? 0), Number(rt.workflow_runs_total || 0));
    const runs24h = Number(tel.runs_24h ?? runsAll);
    const runs7d = Number(tel.runs_7d ?? runsAll);
    const ratioPct = Math.round(Number(tel.cache_hit_ratio ?? rt.cache_hit_ratio ?? 0) * 100);
    const warmLat = tel.latency_warm_ms || rt.latency_warm_ms || {};
    const coldLat = tel.latency_cold_ms || rt.latency_cold_ms || {};
    const regenLat = tel.latency_slide_regen_ms || {};
    const fb = tel.anonymous_feedback || {};
    const tiers = tel.tier_breakdown || {};
    const depths = tel.depth_breakdown || {};

    const setTxt = (id, txt) => {
      const el = document.getElementById(id);
      if (el) el.textContent = txt;
    };
    setTxt("admin-kpi-total-runs", `${runs24h} / ${runs7d} / ${runsAll}`);
    setTxt("admin-kpi-runs-window", `24h: ${runs24h} • 7d: ${runs7d} • All-Time: ${runsAll}`);
    setTxt("admin-kpi-cache-ratio", `Cache Hit Ratio: ${ratioPct}%`);
    const tierDepthText = `Theme: Warm Cream ${tiers.BEAUTIFIED || 0} • Dark Slate ${tiers.STUDIO || 0} • Crisp White ${tiers.STANDARD || 0} | Depth: Deep Dive ${depths["Deep Dive"] || 0} • Standard ${depths.Standard || 0}`;
    setTxt("admin-kpi-tier-split", tierDepthText);
    setTxt("admin-kpi-tier-depth-breakdown", tierDepthText);
    setTxt("admin-kpi-warm-p50", `p50: ${warmLat.p50 || 0} ms`);
    setTxt("admin-kpi-warm-p95", `p95: ${warmLat.p95 || 0} ms • p99: ${warmLat.p99 || 0} ms`);
    setTxt("admin-kpi-cold-p50", `p50: ${coldLat.p50 || 0} ms`);
    setTxt("admin-kpi-cold-p95", `p95: ${coldLat.p95 || 0} ms • p99: ${coldLat.p99 || 0} ms`);
    setTxt("admin-kpi-regen-p50", `p50: ${regenLat.p50 || 0} ms`);
    setTxt("admin-kpi-regen-p95", `p95: ${regenLat.p95 || 0} ms • p99: ${regenLat.p99 || 0} ms`);
    setTxt("admin-kpi-avg-rating", `${fb.average_rating || 5.0} ★`);
    setTxt("admin-kpi-golden-count", `${fb.golden_promotions || 0} Golden Promotions`);
    const spendUsd = Number(tel.total_estimated_cost_usd ?? rt.cumulative_spend_usd ?? 0);
    const savedUsd = Number(tel.total_estimated_saved_usd ?? Math.max(0.64, runsAll * 0.64));
    setTxt("admin-kpi-total-spend", `$${spendUsd.toFixed(2)} Spent`);
    setTxt("admin-kpi-total-saved", `💰 $${savedUsd.toFixed(2)} Saved via Pre-Cached Catalog`);

    renderMiniHistogram("admin-hist-warm", warmLat.histogram);
    renderMiniHistogram("admin-warm-histogram", warmLat.histogram);
    renderMiniHistogram("admin-hist-cold", coldLat.histogram);
    renderMiniHistogram("admin-cold-histogram", coldLat.histogram);
    renderMiniHistogram("admin-hist-regen", regenLat.histogram);
    renderMiniHistogram("admin-regen-histogram", regenLat.histogram);

    const adminFinopsEl = document.getElementById("admin-finops-ledger-preview");
    if (adminFinopsEl && state.currentResult?.finops_telemetry) {
      adminFinopsEl.innerHTML = renderFinopsTableHtml(state.currentResult.finops_telemetry);
    } else if (adminFinopsEl && tel.finops_ledger) {
      adminFinopsEl.innerHTML = renderFinopsTableHtml({
        estimated_cost_usd: spendUsd,
        max_budget_usd: 1.0,
        cached_rerun_cost_usd: 0.02,
        estimated_input_tokens: tel.finops_ledger.total_input_tokens || 18500,
        estimated_output_tokens: tel.finops_ledger.total_output_tokens || 6200,
        beautification_tier: "BEAUTIFIED",
        depth_mode: "Deep Dive / Camp School Deck",
      });
    }

    // Top Badges table
    const popWrap = document.getElementById("admin-badge-popularity-table-wrap");
    if (popWrap) {
      const rows = tel.badge_popularity || [];
      if (rows.length === 0) {
        popWrap.innerHTML = `<div style="padding:12px; color:#64748B; font-size:0.80rem;">No workflow runs recorded yet in this SQLite instance.</div>`;
      } else {
        popWrap.innerHTML = `
          <table class="m3-finops-table" style="width:100%;">
            <thead>
              <tr><th>Merit Badge</th><th>Runs</th><th>Warm</th><th>Cold</th><th>Avg Latency</th><th>Avg QA</th></tr>
            </thead>
            <tbody>
              ${rows
                .map(
                  (r) => `
                <tr>
                  <td><strong>${escapeHtml(r.badge_name)}</strong></td>
                  <td>${r.run_count}</td>
                  <td>${r.warm_runs}</td>
                  <td>${r.cold_runs}</td>
                  <td>${r.avg_duration_ms} ms</td>
                  <td>${r.avg_qa_score}%</td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        `;
      }
    }

    // Image Swap Hotspots table with 1-Click Promote Top Replacement to Default
    const swapsWrap = document.getElementById("admin-image-swaps-table-wrap");
    if (swapsWrap) {
      const swaps = tel.image_swap_hotspots || [];
      if (swaps.length === 0) {
        swapsWrap.innerHTML = `<div style="padding:12px; color:#64748B; font-size:0.80rem;">No slide visual swap events recorded yet. Use the Easy Slide Image Switcher on any slide to record anonymous swap telemetry.</div>`;
      } else {
        swapsWrap.innerHTML = `
          <table class="m3-finops-table" style="width:100%;">
            <thead>
              <tr><th>Merit Badge</th><th>Req</th><th>Replacement Target</th><th>Swaps</th><th>Action</th></tr>
            </thead>
            <tbody>
              ${swaps
                .map(
                  (s, idx) => `
                <tr>
                  <td><strong>${escapeHtml(s.badge_name)}</strong></td>
                  <td>Req ${escapeHtml(s.req_number)}</td>
                  <td><code>${escapeHtml(s.to_image_id || s.event_type || "alternate")}</code></td>
                  <td><strong>${s.event_count}</strong></td>
                  <td>
                    ${
                      s.to_image_id
                        ? `<button type="button" class="m3-btn m3-btn-tonal" data-promote-hotspot-idx="${idx}" style="padding:2px 8px; font-size:0.68rem;">⚡ Promote Top Replacement to Default</button>`
                        : `<span style="font-size:0.70rem; color:#64748B;">Logged</span>`
                    }
                  </td>
                </tr>`
                )
                .join("")}
            </tbody>
          </table>
        `;
        swapsWrap.querySelectorAll("[data-promote-hotspot-idx]").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const idx = parseInt(btn.getAttribute("data-promote-hotspot-idx") || "0", 10);
            const h = swaps[idx];
            if (!h || !h.to_image_id) return;
            btn.disabled = true;
            btn.textContent = "⏳ Promoting...";
            const pResp = await fetch("/api/v1/admin/catalog/promote-primary", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                badge_name: h.badge_name,
                image_id: h.to_image_id,
                req_number: h.req_number || "1",
              }),
            });
            btn.textContent = pResp.ok ? "✅ Promoted to Default!" : "⚠️ Check Catalog Studio";
          });
        });
      }
    }

    // Stage latency bars (p50 / p95 / p99 + mini histogram)
    const stageBarsEl = document.getElementById("admin-stage-latency-bars");
    if (stageBarsEl) {
      const stages = tel.stage_latencies_ms || {};
      const entries = Object.entries(stages);
      if (entries.length === 0) {
        stageBarsEl.innerHTML = `<div style="padding:10px; color:#64748B; font-size:0.80rem;">Run or stream a deck generation to populate per-stage latency histograms.</div>`;
      } else {
        const maxP99 = Math.max(100, ...entries.map(([, v]) => Number(v.p99_ms || v.p95_ms || v.p95 || 1)));
        stageBarsEl.innerHTML = entries
          .map(([sid, st]) => {
            const p50 = Number(st.p50_ms ?? st.p50 ?? 0);
            const p95 = Number(st.p95_ms ?? st.p95 ?? 0);
            const p99 = Number(st.p99_ms ?? st.p99 ?? p95);
            const pct = Math.min(100, Math.max(6, Math.round((p95 / maxP99) * 100)));
            return `
              <div class="m3-stage-latency-row" style="display:grid; grid-template-columns:minmax(225px, 245px) minmax(90px, 1fr) auto; gap:12px; align-items:center; font-size:0.79rem;">
                <strong class="m3-stage-latency-name" style="color:#0F172A; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${escapeHtml(sid)}">${escapeHtml(sid)}</strong>
                <div class="m3-stage-latency-track" style="background:#E2E8F0; height:10px; border-radius:999px; overflow:hidden; min-width:80px;">
                  <div class="m3-stage-latency-fill" style="width:${pct}%; height:100%; background:#003F87; border-radius:999px;"></div>
                </div>
                <span class="m3-stage-latency-stats" style="font-family:var(--font-mono); font-size:0.72rem; color:#334155; white-space:nowrap; text-align:right;">p50: ${p50}ms • p95: ${p95}ms • p99: ${p99}ms</span>
              </div>
            `;
          })
          .join("");
      }
    }

    // Circuit Breakers grid in Diagnostics Sub-tab
    const cbGrid = document.getElementById("admin-circuit-breakers-grid");
    if (cbGrid && rt.circuit_breakers) {
      cbGrid.innerHTML = Object.values(rt.circuit_breakers)
        .map((cb) => {
          const isClosed = cb.state === "CLOSED";
          const pillBg = isClosed ? "#DCFCE7" : "#FEF2F2";
          const pillFg = isClosed ? "#166534" : "#991B1B";
          return `
            <div style="border:1.5px solid #CBD5E1; border-radius:10px; padding:12px; background:#F8FAFC;">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <strong style="font-size:0.82rem; color:#0F172A;">${escapeHtml(cb.name)}</strong>
                <span style="background:${pillBg}; color:${pillFg}; font-size:0.68rem; font-weight:800; padding:2px 8px; border-radius:999px;">${escapeHtml(cb.state)}</span>
              </div>
              <div style="font-size:0.74rem; color:#475569; margin-top:6px;">
                Failures: <strong>${cb.failure_count}/${cb.failure_threshold}</strong> &bull;
                Successes: <strong>${cb.total_successes}</strong> &bull;
                Short-Circuits: <strong>${cb.total_short_circuits}</strong>
              </div>
            </div>
          `;
        })
        .join("");
    }
  } catch (err) {
    console.warn("Admin telemetry load warning:", err);
  }
}

async function loadAdminAssetDiagnostics() {
  try {
    const resp = await fetch("/api/v1/admin/diagnostics/assets");
    if (!resp.ok) return;
    const data = await resp.json();
    state.adminAssetMatrixRows = data.badges || [];
    const subEl = document.getElementById("admin-asset-summary-subtitle");
    if (subEl) {
      subEl.innerHTML = `Verified <strong>${data.total_badges || 144} Merit Badges</strong>: <strong>${data.covers_present || 0}/144</strong> Covers &bull; <strong>${data.emblems_present || 0}/144</strong> Emblems &bull; <strong>${data.total_pamphlet_figures || 0}</strong> Pamphlet Figures &bull; <strong>${data.total_nano_banana_heroes || 0}</strong> Nano Banana Heroes`;
    }
    renderAdminAssetMatrixTable();

    // Render Prompt SHA-256 Manifest table
    const pmBody = document.getElementById("admin-prompt-manifest-table-body");
    if (pmBody) {
      const prompts = data.prompt_manifest || [];
      pmBody.innerHTML =
        prompts.length === 0
          ? `<tr><td colspan="5" style="color:#64748B;">No prompt manifest entries found.</td></tr>`
          : prompts
              .map(
                (p) => `
              <tr>
                <td><strong>${escapeHtml(p.agent_id)}</strong></td>
                <td><code>v${escapeHtml(p.version)}</code></td>
                <td><code style="font-size:0.68rem;">${escapeHtml(p.file || "")}</code></td>
                <td><code style="font-size:0.68rem;">${escapeHtml(String(p.sha256 || "").slice(0, 14))}…</code></td>
                <td>${p.verified ? '<span style="color:#15803D; font-weight:800;">✅ Verified</span>' : "⚠️ Mismatch"}</td>
              </tr>`
              )
              .join("");
    }

    // Render Zero-PII Guardrail & Security Audit Log table
    const gaBody = document.getElementById("admin-guardrail-audit-table-body");
    if (gaBody) {
      const events = data.compliance_audit_events || [];
      gaBody.innerHTML =
        events.length === 0
          ? `<tr><td colspan="4" style="color:#15803D; font-weight:700;">✅ Zero Youth Protection or Model Armor blocks recorded.</td></tr>`
          : events
              .map((ev) => {
                const tsStr = ev.timestamp_iso
                  ? String(ev.timestamp_iso).slice(0, 19).replace("T", " ")
                  : ev.timestamp_epoch
                  ? new Date(Number(ev.timestamp_epoch) * 1000).toISOString().slice(0, 19).replace("T", " ")
                  : String(ev.timestamp || "Recent").slice(0, 19);
                return `
              <tr>
                <td style="font-family:var(--font-mono); font-size:0.70rem;">${escapeHtml(tsStr)}</td>
                <td><code>${escapeHtml(ev.guardrail_status || ev.rule_id || "ADMIN_AUTH_SUCCESS")}</code></td>
                <td><strong>${escapeHtml(ev.action || "VERIFIED")}</strong></td>
                <td>${escapeHtml(ev.caller_identity || ev.summary || "us-central1")}</td>
              </tr>`;
              })
              .join("");
    }
  } catch (err) {
    console.warn("Admin asset diagnostics warning:", err);
  }
}

function renderAdminAssetMatrixTable() {
  const tbody = document.getElementById("admin-asset-health-table-body");
  if (!tbody) return;
  const q = (document.getElementById("admin-asset-matrix-search")?.value || "").trim().toLowerCase();
  const rows = (state.adminAssetMatrixRows || []).filter(
    (r) => !q || `${r.badge_name} ${r.category}`.toLowerCase().includes(q)
  );
  tbody.innerHTML = rows
    .map(
      (r) => `
      <tr>
        <td><strong>${escapeHtml(r.badge_name)}</strong> ${r.eagle_required ? "⭐" : ""}</td>
        <td>${escapeHtml(r.category || "")}</td>
        <td>${r.cover_present ? "✅" : "⚠️"}</td>
        <td>${r.emblem_present ? "✅" : "⚠️"}</td>
        <td><strong>${r.pamphlet_figures}</strong> figs</td>
        <td><strong>${r.nano_banana_heroes}</strong> heroes</td>
        <td>${r.pdf_and_index_present !== false ? `✅ (${r.indexed_reqs || 8} Reqs)` : "⚠️"}</td>
        <td>
          <button type="button" class="m3-btn m3-btn-tonal" data-admin-inspect-badge="${escapeHtml(r.badge_name)}" style="padding:3px 9px; font-size:0.72rem;">
            🖼️ Inspect Visuals
          </button>
        </td>
      </tr>
    `
    )
    .join("");

  tbody.querySelectorAll("[data-admin-inspect-badge]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const bName = btn.getAttribute("data-admin-inspect-badge") || "First Aid";
      populateAdminBadgeSelector();
      const badgeSel = document.getElementById("admin-catalog-badge-select");
      if (badgeSel) {
        if (!Array.from(badgeSel.options).some((o) => o.value === bName)) {
          const opt = document.createElement("option");
          opt.value = bName;
          opt.textContent = bName;
          badgeSel.appendChild(opt);
        }
        badgeSel.value = bName;
      }
      const reqSel = document.getElementById("admin-catalog-req-select");
      if (reqSel) reqSel.value = "ALL";
      document.getElementById("btn-admin-subtab-catalog")?.click();
      await loadAdminCatalogImages();
      document.getElementById("panel-admin")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

async function customizeActiveSlideDeck(action, extraPayload = {}) {
  if (!state.currentResult) return;
  const slides = state.currentResult.storyboard?.slides || [];
  try {
    const resp = await fetch("/api/slide/deck-customize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        badge_name: state.currentResult.badge_name,
        action,
        slide_index: Math.max(0, state.activeSlideIdx),
        storyboard_slides: slides,
        counselor_info: state.currentResult.counselor_info || {},
        output_path: state.currentResult.output_path || "",
        ...extraPayload,
      }),
    });
    if (!resp.ok) return;
    const data = await resp.json();
    if (Array.isArray(data.storyboard_slides)) {
      state.currentResult.storyboard.slides = data.storyboard_slides;
    }
    if (typeof data.active_slide_index === "number") {
      state.activeSlideIdx = data.active_slide_index;
    }
    if (data.pptx_download_url) {
      state.currentResult.pptx_download_url = data.pptx_download_url;
      const dlBtn = document.getElementById("btn-download-pptx");
      if (dlBtn) dlBtn.href = data.pptx_download_url;
    }
    renderFilmstrip(state.currentResult.storyboard.slides);
    renderRequirementJumpBar(state.currentResult.storyboard.slides);
    renderActiveSlide(state.activeSlideIdx);
  } catch (err) {
    console.warn("Slide deck customize warning:", err);
  }
}

function renderPatchGalleryModal() {
  const grid = document.getElementById("patch-gallery-grid");
  if (!grid) return;

  // Populate category dropdown from all 144 badges if not yet populated
  const catSelect = document.getElementById("patch-gallery-category-select");
  const allBadges =
    state.badges?.length > 0
      ? state.badges
      : [{ badge_name: "First Aid", is_eagle_required: true, category: "Personal Development" }];
  if (catSelect && catSelect.options.length <= 1) {
    const cats =
      state.categories?.length > 0
        ? state.categories
        : Array.from(new Set(allBadges.map((b) => b.category).filter(Boolean))).sort();
    cats.forEach((cat) => {
      const opt = document.createElement("option");
      opt.value = cat;
      opt.textContent = cat;
      catSelect.appendChild(opt);
    });
  }

  const q = (document.getElementById("patch-gallery-search-input")?.value || "").trim().toLowerCase();
  const filterSelectEl =
    document.getElementById("patch-gallery-filter-select") ||
    document.getElementById("patch-gallery-eagle-filter");
  const filterMode = (filterSelectEl?.value || "all").toLowerCase();
  const selectedCat = catSelect?.value || "all";

  const favSet = new Set((state.favoriteBadges || []).map((x) => String(x).toLowerCase()));
  const filtered = allBadges.filter((b) => {
    const name = b.badge_name || "";
    const cat = b.category || "";
    if (q && !`${name} ${cat}`.toLowerCase().includes(q)) return false;
    if (filterMode === "favorites" && !favSet.has(name.toLowerCase())) return false;
    if ((filterMode === "eagle" || filterMode === "eagle_required") && !b.is_eagle_required) return false;
    if (filterMode === "elective" && b.is_eagle_required) return false;
    if (selectedCat.toLowerCase() !== "all" && cat !== selectedCat) return false;
    return true;
  });

  const countChip = document.getElementById("patch-gallery-count-chip");
  if (countChip) {
    countChip.textContent = `${filtered.length} / ${allBadges.length} Badges`;
  }

  grid.innerHTML = filtered
    .map((b) => {
      const name = b.badge_name;
      const slug = badgeNameToEmblemSlug(name);
      const isSelected = name === state.currentBadge;
      const isFav = favSet.has(name.toLowerCase());
      const eagleClass = b.is_eagle_required ? "eagle-patch" : "";
      return `
        <div class="m3-patch-gallery-card ${eagleClass} ${isSelected ? "active" : ""}" data-gallery-badge="${escapeHtml(name)}" style="position:relative;">
          <button type="button" class="m3-patch-fav-btn" data-fav-toggle-badge="${escapeHtml(name)}" title="${isFav ? "Remove from My Favorites" : "Add to My Favorites"}">${isFav ? "⭐" : "☆"}</button>
          <img src="/assets/badge_emblems/${escapeHtml(slug)}.png?v=20261016c" alt="${escapeHtml(name)} Emblem" loading="lazy" />
          <div class="m3-patch-card-title" style="font-size:0.76rem; font-weight:800; color:#0F172A; line-height:1.2;">
            ${b.is_eagle_required ? "★ " : ""}${escapeHtml(name)}
          </div>
          <div class="m3-patch-card-category" style="font-size:0.65rem; color:#64748B;">${escapeHtml(b.category || "")}</div>
        </div>
      `;
    })
    .join("");

  grid.querySelectorAll("[data-fav-toggle-badge]").forEach((favBtn) => {
    favBtn.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      const bName = favBtn.getAttribute("data-fav-toggle-badge");
      if (bName && typeof window.toggleFavoriteBadge === "function") {
        await window.toggleFavoriteBadge(bName);
        renderPatchGalleryModal();
      }
    });
  });

  grid.querySelectorAll("[data-gallery-badge]").forEach((card) => {
    card.addEventListener("click", async () => {
      const badge = card.getAttribute("data-gallery-badge");
      if (!badge) return;
      const modal = document.getElementById("patch-gallery-modal");
      modal?.classList.remove("open");
      modal?.classList.add("hidden");
      const select = document.getElementById("badge-select");
      if (select) select.value = badge;
      await executeStreamingWorkflow(badge);
    });
  });
}

async function openGoogleSlidesExportModal() {
  if (!state.currentResult) return;
  const modal = document.getElementById("gslides-export-modal");
  if (!modal) return;
  const accountEmailEl = document.getElementById("gslides-detected-account-email");
  const authModeBadgeEl = document.getElementById("gslides-detected-auth-mode-badge");
  const shareEmailInput = document.getElementById("gslides-share-email-input");
  const statusBanner = document.getElementById("gslides-export-status-banner");
  const statusText = document.getElementById("gslides-export-status-text");
  const openTabLink = document.getElementById("gslides-export-open-tab-link");

  if (statusBanner) statusBanner.classList.add("hidden");
  if (openTabLink) openTabLink.style.display = "none";

  // Pre-fill saved secondary email if any
  try {
    const savedShareEmail = window.localStorage.getItem("scouts_bsa_gslides_share_email") || "";
    if (shareEmailInput && !shareEmailInput.value && savedShareEmail) {
      shareEmailInput.value = savedShareEmail;
    }
  } catch (_e) {}

  modal.classList.remove("hidden");
  modal.classList.add("open");

  try {
    const resp = await fetch("/api/v1/slide/export-gslides/account-info");
    if (resp.ok) {
      const info = await resp.json();
      if (accountEmailEl && info.detected_account_email) {
        accountEmailEl.textContent = info.detected_account_email;
      }
      if (authModeBadgeEl) {
        authModeBadgeEl.textContent = info.gdrive_cli_available
          ? "GOOGLE DRIVE CLI + ADC"
          : info.adc_available
          ? "CLOUD ADC"
          : "BROWSER OAUTH / GUIDED";
      }
      if (info.oauth_client_id) {
        state.googleOauthClientId = info.oauth_client_id;
      }
    }
  } catch (_e) {
    // keep default account label
  }
}

async function runGoogleSlidesExportAndOpenTab({ oauthToken = "", shareEmail = "" } = {}) {
  if (!state.currentResult) return;
  const mainBtn = document.getElementById("btn-download-pptx");
  const labelEl = document.getElementById("deck-export-main-label");
  const createBtn = document.getElementById("btn-gslides-create-and-open-tab");
  const statusBanner = document.getElementById("gslides-export-status-banner");
  const statusText = document.getElementById("gslides-export-status-text");
  const openTabLink = document.getElementById("gslides-export-open-tab-link");
  const origLabel = labelEl?.textContent || "Open in Google Slides";

  // Pre-open the new browser tab synchronously inside the click gesture so browser popup blockers NEVER block it
  let slideTab = null;
  try {
    slideTab = window.open("about:blank", "_blank");
    if (slideTab && slideTab.document) {
      slideTab.document.write(`<!DOCTYPE html>
<html><head><title>Creating Google Slides Presentation...</title>
<style>body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0F172A;color:#F8FAFC;text-align:center;}
.box{max-width:460px;padding:28px 32px;background:#1E293B;border:1px solid #334155;border-radius:16px;box-shadow:0 20px 45px rgba(0,0,0,0.4);}
.spin{width:38px;height:38px;border:4px solid #334155;border-top-color:#FACC15;border-radius:50%;animation:s 0.8s linear infinite;margin:0 auto 14px auto;}
@keyframes s{to{transform:rotate(360deg)}}</style></head>
<body><div class="box"><div class="spin"></div><h2 style="margin:0 0 8px 0;font-size:1.15rem;color:#FDE047;">Creating Google Slides Presentation...</h2>
<p style="margin:0;font-size:0.86rem;color:#CBD5E1;line-height:1.45;">Uploading and converting your <strong>${escapeHtml(
        state.currentResult.badge_name || "Merit Badge"
      )}</strong> slide deck into Google Drive. This tab will redirect automatically in a moment.</p></div></body></html>`);
      slideTab.document.close();
    }
  } catch (_e) {
    slideTab = null;
  }

  if (labelEl) labelEl.textContent = "⏳ Creating Google Slides Deck...";
  if (mainBtn) mainBtn.style.pointerEvents = "none";
  if (createBtn) {
    createBtn.disabled = true;
    createBtn.textContent = "⏳ Creating Google Slides Deck in Drive...";
  }
  if (statusBanner) {
    statusBanner.classList.remove("hidden");
    statusBanner.style.background = "#FEFCE8";
    statusBanner.style.borderColor = "#FDE047";
  }
  if (statusText) {
    statusText.style.color = "#854D0E";
    statusText.textContent = "⏳ Converting .PPTX to native Google Slides presentation in Google Drive...";
  }
  if (openTabLink) openTabLink.style.display = "none";

  try {
    let tokenToUse = oauthToken;
    if (!tokenToUse) {
      try {
        tokenToUse = window.localStorage.getItem("scouts_bsa_google_oauth_token") || "";
      } catch (_e) {}
    }
    const cleanShareEmail = (shareEmail || "").trim();
    if (cleanShareEmail) {
      try {
        window.localStorage.setItem("scouts_bsa_gslides_share_email", cleanShareEmail);
      } catch (_e) {}
    }

    const resp = await fetch("/api/v1/slide/export-gslides", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        badge_name: state.currentResult.badge_name || "First Aid",
        output_path: state.currentResult.output_path || "",
        pptx_download_url: state.currentResult.pptx_download_url || "",
        storyboard_slides: state.currentResult.storyboard?.slides || [],
        counselor_info: state.currentResult.counselor_info || {},
        google_oauth_access_token: tokenToUse,
        share_with_email: cleanShareEmail,
      }),
    });

    if (resp.ok) {
      const data = await resp.json();
      if ((data.status === "SUCCESS" || data.status === "EXPORTED") && data.presentation_url) {
        const targetUrl = data.presentation_url;
        if (slideTab && !slideTab.closed) {
          slideTab.location.replace(targetUrl);
        } else {
          window.open(targetUrl, "_blank", "noopener,noreferrer");
        }
        if (statusBanner) {
          statusBanner.style.background = "#F0FDF4";
          statusBanner.style.borderColor = "#86EFAC";
        }
        if (statusText) {
          statusText.style.color = "#166534";
          const ownerNote = data.owner_account ? ` in ${data.owner_account}` : "";
          const sharedNote = data.shared_with_email ? ` (shared with ${data.shared_with_email})` : "";
          statusText.textContent = `✅ Google Slides presentation created${ownerNote}${sharedNote} and opened in a new browser tab!`;
        }
        if (openTabLink) {
          openTabLink.href = targetUrl;
          openTabLink.style.display = "inline-flex";
        }
        if (labelEl) labelEl.textContent = "✅ Opened in Google Slides!";
        setTimeout(() => {
          if (labelEl) labelEl.textContent = origLabel;
        }, 3000);
        return;
      }

      // Guided Import fallback (only if neither OAuth, Cloud ADC, nor local gdrive CLI succeeded)
      const fallbackUrl = data.google_slides_import_url || "https://docs.google.com/presentation/u/0/";
      if (slideTab && !slideTab.closed) {
        slideTab.location.replace(fallbackUrl);
      } else {
        window.open(fallbackUrl, "_blank", "noopener,noreferrer");
      }
      if (data.pptx_download_url) {
        const dlLink = document.createElement("a");
        dlLink.href = `${data.pptx_download_url}?v=${Date.now()}`;
        dlLink.download = `${(state.currentResult.badge_name || "Merit_Badge").replace(/\s+/g, "_")}_Deck.pptx`;
        document.body.appendChild(dlLink);
        dlLink.click();
        dlLink.remove();
      }
      if (statusText) {
        statusText.textContent =
          "ℹ️ Direct Drive upload unavailable — downloaded .PPTX locally and opened Google Slides in a new tab.";
      }
      if (openTabLink) {
        openTabLink.href = fallbackUrl;
        openTabLink.style.display = "inline-flex";
      }
      if (labelEl) labelEl.textContent = "✅ PPTX Downloaded + Slides Opened";
      setTimeout(() => {
        if (labelEl) labelEl.textContent = origLabel;
      }, 2800);
    } else if (slideTab && !slideTab.closed) {
      slideTab.close();
    }
  } catch (err) {
    console.warn("Google Slides export warning:", err);
    if (slideTab && !slideTab.closed) {
      slideTab.close();
    }
  } finally {
    if (mainBtn) mainBtn.style.pointerEvents = "";
    if (createBtn) {
      createBtn.disabled = false;
      createBtn.textContent = "🟨 Create & Open in New Tab ↗";
    }
  }
}

async function exportActiveDeckToGoogleSlides() {
  await openGoogleSlidesExportModal();
}

function syncDeckExportSplitButtonUi(mode) {
  const normalized = mode === "gslides" ? "gslides" : "pptx";
  state.preferredExportMode = normalized;
  try {
    window.localStorage.setItem("scouts_bsa_preferred_export_mode", normalized);
  } catch (_e) {}

  const mainBtn = document.getElementById("btn-download-pptx");
  const iconEl = document.getElementById("deck-export-main-icon");
  const labelEl = document.getElementById("deck-export-main-label");
  const chkPptx = document.getElementById("export-check-pptx");
  const chkGslides = document.getElementById("export-check-gslides");

  if (chkPptx) chkPptx.textContent = normalized === "pptx" ? "✓" : "";
  if (chkGslides) chkGslides.textContent = normalized === "gslides" ? "✓" : "";

  if (normalized === "gslides") {
    if (iconEl) iconEl.textContent = "slideshow";
    if (labelEl) labelEl.textContent = "Open in Google Slides";
    if (mainBtn) {
      mainBtn.removeAttribute("download");
      mainBtn.href = "#export-gslides";
    }
  } else {
    if (iconEl) iconEl.textContent = "download";
    if (labelEl) labelEl.textContent = "Download Slide Deck (.PPTX)";
    if (mainBtn) {
      mainBtn.setAttribute("download", "");
      if (state.currentResult?.pptx_download_url) {
        mainBtn.href = `${state.currentResult.pptx_download_url}?v=${Date.now()}`;
      }
    }
  }
}

function bindEnhancedWorkbenchAndAdminFeatures() {
  // Set default date stamp in Blue Card tracker
  const dateInput = document.getElementById("bluecard-signoff-date");
  if (dateInput && !dateInput.value) {
    dateInput.value = new Date().toISOString().slice(0, 10);
  }

  // Plan 7 #8b: Sticky Split-Button for Deck Export (.PPTX vs Direct Google Slides)
  let savedExportMode = "pptx";
  try {
    savedExportMode = window.localStorage.getItem("scouts_bsa_preferred_export_mode") || "pptx";
  } catch (_e) {}
  syncDeckExportSplitButtonUi(savedExportMode);

  const deckCaretBtn = document.getElementById("btn-deck-export-caret");
  const deckExportMenu = document.getElementById("deck-export-mode-menu");
  deckCaretBtn?.addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    deckExportMenu?.classList.toggle("hidden");
  });
  document.querySelectorAll("#deck-export-mode-menu [data-export-mode]").forEach((optBtn) => {
    optBtn.addEventListener("click", async (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const chosen = optBtn.getAttribute("data-export-mode") || "pptx";
      deckExportMenu?.classList.add("hidden");
      syncDeckExportSplitButtonUi(chosen);
      if (chosen === "gslides") {
        await exportActiveDeckToGoogleSlides();
      } else {
        const dlBtn = document.getElementById("btn-download-pptx");
        if (dlBtn && state.currentResult?.pptx_download_url) {
          dlBtn.click();
        }
      }
    });
  });
  document.getElementById("btn-download-pptx")?.addEventListener("click", async (ev) => {
    if (state.preferredExportMode === "gslides") {
      ev.preventDefault();
      await exportActiveDeckToGoogleSlides();
    }
  });

  // UI-1 & Part 2 Features 4 & 5: Top Bar Export & Print Dropdown Menu
  const exportToggleBtn = document.getElementById("btn-export-menu-toggle");
  const exportMenu = document.getElementById("top-export-dropdown-menu");
  exportToggleBtn?.addEventListener("click", (ev) => {
    ev.stopPropagation();
    exportMenu?.classList.toggle("hidden");
  });
  document.addEventListener("click", () => {
    exportMenu?.classList.add("hidden");
    deckExportMenu?.classList.add("hidden");
  });
  document.getElementById("btn-top-print-workbook")?.addEventListener("click", () => {
    document.getElementById("btn-print-workbook")?.click();
  });
  document.getElementById("btn-top-print-field-qr-handout")?.addEventListener("click", () => {
    printPocketFieldQrHandout(state.currentResult);
  });
  document.getElementById("btn-workbook-print-field-qr")?.addEventListener("click", () => {
    printPocketFieldQrHandout(state.currentResult);
  });
  document.getElementById("btn-studiokit-print-field-qr")?.addEventListener("click", () => {
    printPocketFieldQrHandout(state.currentResult);
  });
  document.getElementById("btn-top-print-3panel-bluecards")?.addEventListener("click", () => {
    printThreePanelBlueCards(state.currentResult);
  });
  document.getElementById("btn-bluecard-print-3panel")?.addEventListener("click", () => {
    printThreePanelBlueCards(state.currentResult);
  });
  document.getElementById("btn-top-print-cue-cards")?.addEventListener("click", () => {
    printCounselorPocketCueCards();
  });
  document.getElementById("btn-top-export-bluecard-csv")?.addEventListener("click", () => {
    if (state.currentResult) exportBlueCardCsv(state.currentResult);
  });

  // Scoutbook CSV Roster Import
  const csvImportBtn = document.getElementById("btn-bluecard-import-csv");
  const csvFileInput = document.getElementById("bluecard-csv-file-input");
  csvImportBtn?.addEventListener("click", () => {
    csvFileInput?.click();
  });
  csvFileInput?.addEventListener("change", () => {
    const file = csvFileInput.files?.[0];
    if (file && state.currentResult) {
      importBlueCardCsvFile(file, state.currentResult);
    }
    csvFileInput.value = "";
  });

  // Plan 9 Fix 4: Jump to Patrol Blue Card (#34124) Tracker button at top of Requirements & Blue Cards page
  document.getElementById("btn-jump-to-bluecard-tracker")?.addEventListener("click", () => {
    const trackerCard = document.getElementById("bluecard-tracker-card");
    if (trackerCard) {
      trackerCard.scrollIntoView({ behavior: "smooth", block: "start" });
      trackerCard.style.transition = "box-shadow 0.25s ease, outline 0.25s ease";
      trackerCard.style.outline = "3px solid #D97706";
      trackerCard.style.boxShadow = "0 0 0 6px rgba(217, 119, 6, 0.22)";
      setTimeout(() => {
        trackerCard.style.outline = "";
        trackerCard.style.boxShadow = "";
      }, 1600);
    }
  });

  // Plan 10 Request #3: Jump to "Rate This Merit Badge Teaching Package" on Grounded Research Citations & Local Troop References page
  document.getElementById("btn-jump-to-counselor-rating")?.addEventListener("click", () => {
    const ratingCard = document.getElementById("studiokit-feedback-card");
    if (ratingCard) {
      ratingCard.scrollIntoView({ behavior: "smooth", block: "start" });
      ratingCard.style.transition = "box-shadow 0.25s ease, outline 0.25s ease";
      ratingCard.style.outline = "3px solid #D97706";
      ratingCard.style.boxShadow = "0 0 0 6px rgba(217, 119, 6, 0.22)";
      setTimeout(() => {
        ratingCard.style.outline = "";
        ratingCard.style.boxShadow = "";
      }, 1600);
    }
  });

  // Plan 10 Request #7: Google Account & Slides Export Modal handlers
  const gslidesModal = document.getElementById("gslides-export-modal");
  const closeGslidesModal = () => {
    gslidesModal?.classList.remove("open");
    gslidesModal?.classList.add("hidden");
  };
  document.getElementById("btn-close-gslides-export-modal")?.addEventListener("click", closeGslidesModal);
  document.getElementById("btn-cancel-gslides-export-modal")?.addEventListener("click", closeGslidesModal);
  document.getElementById("btn-gslides-create-and-open-tab")?.addEventListener("click", async () => {
    const shareEmail = document.getElementById("gslides-share-email-input")?.value || "";
    await runGoogleSlidesExportAndOpenTab({ shareEmail });
  });
  document.getElementById("btn-gslides-pick-google-account")?.addEventListener("click", async () => {
    const shareEmailInput = document.getElementById("gslides-share-email-input");
    const shareEmail = (shareEmailInput?.value || "").trim();
    const statusBanner = document.getElementById("gslides-export-status-banner");
    const statusText = document.getElementById("gslides-export-status-text");
    // If Google Identity Services (GIS) is loaded and an OAuth Client ID is configured, invoke the native Google Account Picker
    if (window.google?.accounts?.oauth2 && state.googleOauthClientId) {
      const tokenClient = window.google.accounts.oauth2.initTokenClient({
        client_id: state.googleOauthClientId,
        scope: "https://www.googleapis.com/auth/drive.file",
        prompt: "select_account",
        callback: async (tokenResponse) => {
          if (tokenResponse && tokenResponse.access_token) {
            try {
              window.localStorage.setItem("scouts_bsa_google_oauth_token", tokenResponse.access_token);
            } catch (_e) {}
            await runGoogleSlidesExportAndOpenTab({
              oauthToken: tokenResponse.access_token,
              shareEmail,
            });
          }
        },
      });
      tokenClient.requestAccessToken({ prompt: "select_account" });
      return;
    }
    // When no browser OAuth Client ID is configured, if the counselor entered a target email in Card 2, export & share with that account immediately;
    // otherwise focus Card 2 and show instructions to enter their target @gmail.com / Google Workspace address
    if (!shareEmail && shareEmailInput) {
      shareEmailInput.focus();
      shareEmailInput.style.outline = "2px solid #2563EB";
      if (statusBanner && statusText) {
        statusBanner.classList.remove("hidden");
        statusBanner.style.background = "#EFF6FF";
        statusBanner.style.borderColor = "#93C5FD";
        statusText.style.color = "#1E3A8A";
        statusText.textContent =
          "🔑 Enter your target @gmail.com or Google account email in Box 2 above (or leave blank to use your active workstation account), then click 'Create & Open in New Tab ↗'.";
      }
      setTimeout(() => {
        shareEmailInput.style.outline = "";
      }, 2200);
      return;
    }
    await runGoogleSlidesExportAndOpenTab({ shareEmail });
  });

  // UI-6: Synchronized Dark Mode & Sunlight / High-Contrast Camp Mode toggles
  const darkBtn = document.getElementById("btn-toggle-dark-mode");
  const docsThemeBtn = document.getElementById("btn-docs-toggle-theme");
  const sunlightBtn = document.getElementById("btn-toggle-sunlight-mode");

  const applyWorkbenchDarkMode = (enableDark) => {
    const active = Boolean(enableDark);
    document.body.classList.toggle("m3-dark-mode", active);
    if (active && document.body.classList.contains("m3-sunlight-mode")) {
      document.body.classList.remove("m3-sunlight-mode");
      if (sunlightBtn) sunlightBtn.textContent = "☀️ Sunlight Mode";
      try {
        window.localStorage.setItem("scouts_bsa_sunlight_mode", "0");
      } catch (_e) {}
    }
    if (darkBtn) darkBtn.textContent = active ? "☀️ Light" : "🌙 Dark";
    if (docsThemeBtn) docsThemeBtn.textContent = active ? "☀️ Light" : "🌙 Dark";
    try {
      window.localStorage.setItem("scouts_bsa_dark_mode", active ? "1" : "0");
    } catch (_e) {}
  };

  try {
    if (window.localStorage.getItem("scouts_bsa_dark_mode") === "1") {
      applyWorkbenchDarkMode(true);
    } else if (window.localStorage.getItem("scouts_bsa_sunlight_mode") === "1") {
      document.body.classList.add("m3-sunlight-mode");
      if (sunlightBtn) sunlightBtn.textContent = "☀️ Sunlight: ON";
    }
  } catch (_e) {}

  darkBtn?.addEventListener("click", () => {
    const nextDark = !document.body.classList.contains("m3-dark-mode");
    applyWorkbenchDarkMode(nextDark);
  });
  docsThemeBtn?.addEventListener("click", () => {
    const nextDark = !document.body.classList.contains("m3-dark-mode");
    applyWorkbenchDarkMode(nextDark);
  });
  sunlightBtn?.addEventListener("click", () => {
    const active = document.body.classList.toggle("m3-sunlight-mode");
    if (active && document.body.classList.contains("m3-dark-mode")) {
      applyWorkbenchDarkMode(false);
    }
    sunlightBtn.textContent = active ? "☀️ Sunlight: ON" : "☀️ Sunlight Mode";
    try {
      window.localStorage.setItem("scouts_bsa_sunlight_mode", active ? "1" : "0");
    } catch (_e) {}
  });

  // UI-6 & Plan 7 #1b: 144-Badge Patch Gallery Modal + Eagle/Elective & Category Filters
  const patchModal = document.getElementById("patch-gallery-modal");
  document.getElementById("btn-open-patch-gallery")?.addEventListener("click", () => {
    renderPatchGalleryModal();
    patchModal?.classList.remove("hidden");
    patchModal?.classList.add("open");
  });
  document.getElementById("btn-close-patch-gallery")?.addEventListener("click", () => {
    patchModal?.classList.remove("open");
    patchModal?.classList.add("hidden");
  });
  document.getElementById("patch-gallery-search-input")?.addEventListener("input", () => renderPatchGalleryModal());
  document.getElementById("patch-gallery-filter-select")?.addEventListener("change", () => renderPatchGalleryModal());
  document.getElementById("patch-gallery-eagle-filter")?.addEventListener("change", () => renderPatchGalleryModal());
  document.getElementById("patch-gallery-category-select")?.addEventListener("change", () => renderPatchGalleryModal());

  // Feature C1: Live Classroom Session Countdown Timer + Fullscreen HUD Timer
  document.getElementById("session-timer-preset-select")?.addEventListener("change", () => {
    resetSessionTimer();
  });
  document.getElementById("btn-timer-start-pause")?.addEventListener("click", () => {
    toggleSessionTimer();
  });
  document.getElementById("fullscreen-hud-timer")?.addEventListener("click", () => {
    toggleSessionTimer();
  });
  document.getElementById("btn-timer-reset")?.addEventListener("click", () => {
    resetSessionTimer();
  });

  // Feature 1 & Plan 7 #3: Fullscreen Teleprompter Notes (`🎙️ Notes (N)`) & In-Stage Split-Screen Presenter Console (`🪟 Presenter View (P)`)
  const toggleFullscreenTeleprompter = () => {
    const drawer = document.getElementById("fullscreen-teleprompter-drawer");
    if (!drawer) return;
    const isHidden = drawer.classList.toggle("hidden");
    const fsNotesBtn = document.getElementById("btn-fs-toggle-notes");
    if (fsNotesBtn) {
      fsNotesBtn.textContent = isHidden ? "🎙️ Notes (N)" : "🎙️ Hide Notes (N)";
    }
  };
  document.getElementById("btn-fs-toggle-notes")?.addEventListener("click", toggleFullscreenTeleprompter);
  document.getElementById("btn-close-fs-teleprompter")?.addEventListener("click", () => {
    document.getElementById("fullscreen-teleprompter-drawer")?.classList.add("hidden");
  });
  document.getElementById("btn-fs-popout-notes")?.addEventListener("click", () => {
    togglePresenterConsoleMode();
  });
  document.getElementById("btn-pc-close-dock")?.addEventListener("click", () => {
    togglePresenterConsoleMode(false);
  });
  document.getElementById("btn-pc-close-console")?.addEventListener("click", () => {
    togglePresenterConsoleMode(false);
  });
  document.getElementById("btn-pc-prev-slide")?.addEventListener("click", () => {
    document.getElementById("btn-prev-slide")?.click();
  });
  document.getElementById("btn-pc-next-slide")?.addEventListener("click", () => {
    document.getElementById("btn-next-slide")?.click();
  });
  document.getElementById("btn-pc-font-dec")?.addEventListener("click", () => {
    changePresenterFontScale(-0.08);
  });
  document.getElementById("btn-pc-font-inc")?.addEventListener("click", () => {
    changePresenterFontScale(0.08);
  });
  document.getElementById("pc-dock-timer")?.addEventListener("click", () => {
    toggleSessionTimer();
  });
  document.getElementById("btn-pc-popout-window")?.addEventListener("click", () => {
    openPresenterViewWindow();
  });

  // Feature C2 & Feature 2: Classroom Quiz Reveal Mode, Patrol Scoreboard & Quiz Slide Filter
  const quizBtn = document.getElementById("btn-toggle-quiz-reveal");
  quizBtn?.addEventListener("click", () => {
    state.quizRevealMode = !state.quizRevealMode;
    quizBtn.textContent = state.quizRevealMode ? "🎯 Quiz Reveal: ON" : "🎯 Quiz Reveal: Off";
    quizBtn.classList.toggle("m3-btn-filled", state.quizRevealMode);
    quizBtn.classList.toggle("m3-btn-outlined", !state.quizRevealMode);
    if (state.currentResult && state.activeSlideIdx >= 0) {
      renderActiveSlide(state.activeSlideIdx);
    }
  });

  state.patrolScores = { eagle: 0, fox: 0, wolf: 0, raven: 0 };
  const syncPatrolScoreboardDom = () => {
    ["eagle", "fox", "wolf", "raven"].forEach((p) => {
      const el = document.getElementById(`patrol-score-${p}`);
      if (el) el.textContent = String(state.patrolScores[p] || 0);
    });
  };
  document.getElementById("btn-toggle-patrol-scoreboard")?.addEventListener("click", () => {
    state.patrolScoreboardVisible = !state.patrolScoreboardVisible;
    document.getElementById("stage-patrol-scoreboard")?.classList.toggle("hidden", !state.patrolScoreboardVisible);
  });
  document.querySelectorAll(".m3-patrol-score-Delta").forEach((btn) => {
    btn.addEventListener("click", () => {
      const patrol = btn.getAttribute("data-patrol") || "eagle";
      const delta = parseInt(btn.getAttribute("data-delta") || "1", 10);
      state.patrolScores[patrol] = Math.max(0, (state.patrolScores[patrol] || 0) + delta);
      syncPatrolScoreboardDom();
    });
  });
  document.getElementById("btn-patrol-score-reset")?.addEventListener("click", () => {
    state.patrolScores = { eagle: 0, fox: 0, wolf: 0, raven: 0 };
    syncPatrolScoreboardDom();
  });

  const filterQuizBtn = document.getElementById("btn-filter-quiz-slides");
  filterQuizBtn?.addEventListener("click", () => {
    state.filterQuizSlidesOnly = !state.filterQuizSlidesOnly;
    filterQuizBtn.textContent = state.filterQuizSlidesOnly ? "⚡ Showing Quiz Slides (All)" : "⚡ Quiz Slides Only";
    filterQuizBtn.classList.toggle("m3-btn-filled", state.filterQuizSlidesOnly);
    filterQuizBtn.classList.toggle("m3-btn-tonal", !state.filterQuizSlidesOnly);
    const slides = state.currentResult?.storyboard?.slides || [];
    renderFilmstrip(slides);
  });

  // Feature 3: Slide Deck Customizer (Insert Custom Slide, Hide Slide, Hide Prereqs, Move Up/Down)
  const insertSlideModal = document.getElementById("insert-custom-slide-modal");
  document.getElementById("btn-insert-custom-slide")?.addEventListener("click", () => {
    const slides = state.currentResult?.storyboard?.slides || [];
    const cur = slides[Math.max(0, state.activeSlideIdx)] || {};
    const reqIn = document.getElementById("custom-slide-req-input");
    if (reqIn && cur.req_number) reqIn.value = String(cur.req_number);
    insertSlideModal?.classList.remove("hidden");
    insertSlideModal?.classList.add("open");
  });
  document.getElementById("btn-close-insert-slide-modal")?.addEventListener("click", () => {
    insertSlideModal?.classList.remove("open");
    insertSlideModal?.classList.add("hidden");
  });
  document.getElementById("btn-confirm-insert-custom-slide")?.addEventListener("click", async () => {
    const title = document.getElementById("custom-slide-title-input")?.value || "Local Camp & Troop Procedures";
    const reqNum = document.getElementById("custom-slide-req-input")?.value || "Local";
    const arch = document.getElementById("custom-slide-archetype-select")?.value || "CONCEPT_TEXT_SLIDE";
    const bullets = (document.getElementById("custom-slide-bullets-input")?.value || "")
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);
    const notes = document.getElementById("custom-slide-notes-input")?.value || "";
    insertSlideModal?.classList.remove("open");
    insertSlideModal?.classList.add("hidden");
    await customizeActiveSlideDeck("insert", {
      custom_slide: {
        title,
        req_number: reqNum,
        archetype: arch,
        bullet_points: bullets,
        presenter_notes: notes,
      },
    });
  });

  document.getElementById("btn-toggle-hide-slide")?.addEventListener("click", async () => {
    if (state.activeSlideIdx < 0) return;
    await customizeActiveSlideDeck("toggle_hide");
  });
  let prereqsHiddenState = false;
  document.getElementById("btn-toggle-hide-prereq-slides")?.addEventListener("click", async (ev) => {
    prereqsHiddenState = !prereqsHiddenState;
    const btn = ev.currentTarget;
    if (btn) btn.textContent = prereqsHiddenState ? "🏠 Show Home-Prereqs" : "🏠 Hide Home-Prereqs";
    const prereqNums = (state.currentResult?.research_artifact?.requirements || [])
      .filter((r) => r.execution_mode === "PREREQUISITE_CAMPOUT_HOME")
      .map((r) => String(r.req_number));
    await customizeActiveSlideDeck("hide_prereqs", {
      hide_prereqs: prereqsHiddenState,
      prereq_req_numbers: prereqNums,
    });
  });
  document.getElementById("btn-move-slide-up")?.addEventListener("click", async () => {
    if (state.activeSlideIdx <= 0) return;
    await customizeActiveSlideDeck("move_up");
  });
  document.getElementById("btn-move-slide-down")?.addEventListener("click", async () => {
    const slides = state.currentResult?.storyboard?.slides || [];
    if (state.activeSlideIdx < 0 || state.activeSlideIdx >= slides.length - 1) return;
    await customizeActiveSlideDeck("move_down");
  });

  // UI-2 & Plan 7 #3: In-Stage Split-Screen Presenter Console Toggle (`🪟 Presenter View (P)`)
  document.getElementById("btn-popout-speaker-notes")?.addEventListener("click", () => {
    togglePresenterConsoleMode();
  });

  // UI-2 & UI-3: Visual Archetype Thumbnail Picker + Auto-Apply Co-Design Controls + Restore Original
  document.querySelectorAll("#codesign-archetype-visual-grid .m3-arch-thumb-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const arch = btn.getAttribute("data-arch") || "SPLIT_VISUAL_EXPLAINER";
      const archSel = document.getElementById("codesign-archetype-select");
      if (archSel) archSel.value = arch;
      syncArchetypeVisualPicker(arch);
      document.getElementById("btn-apply-codesign")?.click();
    });
  });
  ["codesign-archetype-select", "codesign-theme-select", "codesign-palette-select", "codesign-source-select"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", (ev) => {
      if (id === "codesign-archetype-select") {
        syncArchetypeVisualPicker(ev.target.value);
      }
      document.getElementById("btn-apply-codesign")?.click();
    });
  });
  document.getElementById("btn-restore-original-slide")?.addEventListener("click", () => {
    const srcSel = document.getElementById("codesign-source-select");
    if (srcSel) srcSel.value = "restore_original";
    document.getElementById("btn-apply-codesign")?.click();
  });

  // UI-4 & C4: Workbook search filter & Pocket Cue Cards
  document.getElementById("btn-print-cue-cards")?.addEventListener("click", () => {
    printCounselorPocketCueCards();
  });
  document.getElementById("workbook-search-input")?.addEventListener("input", (ev) => {
    const q = (ev.target.value || "").trim().toLowerCase();
    const previewEl = document.getElementById("workbook-markdown-preview");
    if (!previewEl || !state.currentResult) return;
    const rawMd = state.currentResult.workbook_markdown || "";
    if (!q) {
      previewEl.innerHTML = renderMarkdownToStyledHtml(rawMd);
      return;
    }
    const blocks = rawMd.split(/\n(?=##\s)/);
    const filtered = blocks.filter((b, i) => i === 0 || b.toLowerCase().includes(q));
    previewEl.innerHTML = renderMarkdownToStyledHtml(filtered.join("\n\n") || `No workbook sections matching "${q}".`);
  });

  // UI-5: StudioKit Sub-Tab Pill Switcher
  document.querySelectorAll("#studiokit-subtabs-bar .m3-studiokit-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      const filter = pill.getAttribute("data-studiokit-filter") || "ALL";
      document.querySelectorAll("#studiokit-subtabs-bar .m3-studiokit-pill").forEach((p) =>
        p.classList.toggle("active", p === pill)
      );
      const secAgenda = document.getElementById("studiokit-sec-agenda");
      const secGear = document.getElementById("studiokit-gear-checklist-card");
      const secRotator = document.getElementById("buddy-rotator-card");
      const secPrereq = document.getElementById("prereq-readiness-card");
      const secFinops = document.getElementById("studiokit-sec-finops");
      const secFeedback = document.getElementById("studiokit-feedback-card");

      if (secAgenda) secAgenda.style.display = filter === "ALL" || filter === "AGENDA" ? "grid" : "none";
      if (secGear) secGear.classList.toggle("hidden", filter !== "ALL" && filter !== "GEAR");
      if (secRotator) secRotator.classList.toggle("hidden", filter !== "ALL" && filter !== "GEAR");
      if (secPrereq) secPrereq.classList.toggle("hidden", filter !== "ALL" && filter !== "PREREQ");
      if (secFinops) secFinops.style.display = filter === "ALL" || filter === "FINOPS" ? "grid" : "none";
      if (secFeedback) secFeedback.classList.toggle("hidden", filter !== "ALL" && filter !== "FINOPS");
    });
  });

  // Feature C5: Patrol / Buddy Station Rotator controls
  document.getElementById("rotator-minutes-select")?.addEventListener("change", () => {
    if (state.currentResult) renderBuddyStationRotator(state.currentResult);
  });
  document.getElementById("btn-print-rotator")?.addEventListener("click", () => {
    const badge = state.currentResult?.badge_name || "First Aid";
    const html = document.getElementById("buddy-rotator-matrix-wrap")?.innerHTML || "";
    printHtmlDocument(`${badge} Merit Badge — Patrol & Buddy Skill Station Rotation Matrix`, "Hands-On EDGE Station Schedule", html);
  });

  // Feature C3: Copy Pre-Class Prerequisite Reminder
  document.getElementById("btn-email-prereq-reminder")?.addEventListener("click", (ev) => {
    const badge = state.currentResult?.badge_name || "First Aid";
    const reqs = (state.currentResult?.research_artifact?.requirements || []).filter(
      (r) => r.execution_mode === "PREREQUISITE_CAMPOUT_HOME"
    );
    const lines = reqs.map((r) => `- Requirement ${r.req_number}: ${r.req_text}`).join("\n");
    const snippet = `Scouts & Parents — Before our ${badge} Merit Badge session, please bring your completed prerequisite notes/logs for:\n${lines || "- Review your Merit Badge Workbook prerequisites."}`;
    copyTextWithFeedback(ev.currentTarget, snippet, "✅ Copied Reminder!");
  });

  // UI-6: Blue Card Bulk Paste Roster & Mark In-Class Complete
  document.getElementById("btn-bluecard-bulk-paste")?.addEventListener("click", () => {
    document.getElementById("bluecard-bulk-paste-box")?.classList.toggle("hidden");
  });
  document.getElementById("btn-bluecard-bulk-apply")?.addEventListener("click", () => {
    if (!state.currentResult) return;
    const raw = document.getElementById("bluecard-bulk-textarea")?.value || "";
    const names = raw
      .split(/[\n,;]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (names.length === 0) return;
    const roster = loadBadgeBlueCardRoster(state.currentResult.badge_name);
    names.forEach((n) => {
      if (!roster.scouts.some((s) => s.name.toLowerCase() === n.toLowerCase())) {
        roster.scouts.push({ name: n, completedReqs: [] });
      }
    });
    saveBadgeBlueCardRoster(state.currentResult.badge_name, roster);
    renderBlueCardTracker(state.currentResult);
    document.getElementById("bluecard-bulk-paste-box")?.classList.add("hidden");
  });
  document.getElementById("btn-bluecard-mark-inclass")?.addEventListener("click", () => {
    if (!state.currentResult) return;
    const reqs = state.currentResult.research_artifact?.requirements || [];
    const inClassNums = reqs
      .filter((r) => (r.execution_mode || "IN_CLASS_DISCUSSION") === "IN_CLASS_DISCUSSION")
      .map((r) => String(r.req_number));
    const roster = loadBadgeBlueCardRoster(state.currentResult.badge_name);
    roster.scouts.forEach((scout) => {
      const set = new Set(scout.completedReqs || []);
      inClassNums.forEach((n) => set.add(n));
      scout.completedReqs = Array.from(set);
    });
    saveBadgeBlueCardRoster(state.currentResult.badge_name, roster);
    renderBlueCardTracker(state.currentResult);
  });

  // UI-5 & UI-7 & Plan 7 #3/#5: Keyboard Shortcuts Modal (`?`) + `[` / `]` Image Cycling + `Space` Quiz Reveal + `N` Notes + `P` Presenter Console
  const shortcutsModal = document.getElementById("keyboard-shortcuts-modal");
  document.getElementById("btn-keyboard-shortcuts")?.addEventListener("click", () => {
    shortcutsModal?.classList.remove("hidden");
    shortcutsModal?.classList.add("open");
  });
  document.getElementById("btn-close-shortcuts-modal")?.addEventListener("click", () => {
    shortcutsModal?.classList.remove("open");
    shortcutsModal?.classList.add("hidden");
  });
  document.addEventListener("keydown", (ev) => {
    const tag = (ev.target?.tagName || "").toUpperCase();
    if (["INPUT", "TEXTAREA", "SELECT"].includes(tag) || ev.target?.isContentEditable) return;
    if (ev.key === "?") {
      ev.preventDefault();
      const isHidden = shortcutsModal?.classList.toggle("hidden");
      shortcutsModal?.classList.toggle("open", !isHidden);
    } else if (ev.key === "[" || (ev.altKey && ev.key === "ArrowLeft")) {
      ev.preventDefault();
      cycleSlideImageChoice(-1);
    } else if (ev.key === "]" || (ev.altKey && ev.key === "ArrowRight")) {
      ev.preventDefault();
      cycleSlideImageChoice(1);
    } else if (ev.key.toLowerCase() === "n" && !ev.ctrlKey && !ev.metaKey) {
      ev.preventDefault();
      const stageWrapper = document.getElementById("slide-stage-wrapper");
      if (stageWrapper?.classList.contains("is-presenting-fullscreen") || document.fullscreenElement) {
        toggleFullscreenTeleprompter();
      } else {
        state.activeUnderstageTab = "notes";
        syncUnderstageDrawerVisibility(state.activeSlideIdx);
      }
    } else if (ev.key === " " && !ev.ctrlKey && !ev.metaKey) {
      // 1. On SOCRATIC_CHECKPOINT_QUIZ slides, Space reveals/hides the Verified Answer card
      const revealAnswerBtn = document.getElementById("btn-reveal-quiz-answer");
      const answerCard = document.getElementById("quiz-verified-answer-card");
      if (revealAnswerBtn && !revealAnswerBtn.classList.contains("hidden")) {
        ev.preventDefault();
        revealAnswerBtn.click();
        return;
      }
      if (answerCard && !answerCard.classList.contains("hidden") && revealAnswerBtn) {
        ev.preventDefault();
        state.revealedQuizSlides.delete(state.activeSlideIdx);
        answerCard.classList.add("hidden");
        revealAnswerBtn.classList.remove("hidden");
        fitActiveSlideToStage();
        return;
      }
      // 2. When Quiz Reveal Mode (Q) is active, Space reveals the next masked card
      const maskedCards = document.querySelectorAll("#stage-left-cards .m3-slide-card-item.m3-quiz-masked:not(.revealed)");
      if (maskedCards.length > 0) {
        ev.preventDefault();
        maskedCards[0].classList.add("revealed");
      }
    } else if (ev.key.toLowerCase() === "p" && !ev.ctrlKey && !ev.metaKey) {
      ev.preventDefault();
      togglePresenterConsoleMode();
    } else if (ev.key.toLowerCase() === "q" && !ev.ctrlKey && !ev.metaKey) {
      ev.preventDefault();
      document.getElementById("btn-toggle-quiz-reveal")?.click();
    } else if (ev.key.toLowerCase() === "t" && !ev.ctrlKey && !ev.metaKey) {
      ev.preventDefault();
      toggleSessionTimer();
    } else if (ev.key.toLowerCase() === "d" && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
      ev.preventDefault();
      openDocumentationViewerModal();
    } else if (ev.ctrlKey && ev.shiftKey && ev.key.toLowerCase() === "a") {
      ev.preventDefault();
      document.getElementById("btn-footer-admin-unlock")?.click();
    }
  });

  // Super-User Admin Console Bindings
  checkAdminSessionAndInit();

  const unlockModal = document.getElementById("admin-unlock-modal");
  document.getElementById("btn-footer-admin-unlock")?.addEventListener("click", () => {
    if (state.isAdminSession) {
      document.getElementById("tab-btn-admin")?.classList.remove("hidden");
      switchMainTab("panel-admin");
    } else {
      unlockModal?.classList.remove("hidden");
      unlockModal?.classList.add("open");
    }
  });
  document.getElementById("btn-close-admin-unlock-modal")?.addEventListener("click", () => {
    unlockModal?.classList.remove("open");
    unlockModal?.classList.add("hidden");
  });
  document.getElementById("btn-submit-admin-unlock")?.addEventListener("click", async () => {
    const tokenVal = document.getElementById("admin-unlock-passphrase-input")?.value || "";
    const errEl = document.getElementById("admin-unlock-error-msg");
    try {
      const resp = await fetch("/api/v1/admin/unlock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: tokenVal }),
      });
      if (resp.ok) {
        state.isAdminSession = true;
        unlockModal?.classList.remove("open");
        unlockModal?.classList.add("hidden");
        document.getElementById("tab-btn-admin")?.classList.remove("hidden");
        const footerBtn = document.getElementById("btn-footer-admin-unlock");
        if (footerBtn) footerBtn.textContent = "🛡️ Admin Console";
        if (state.currentResult) {
          renderActiveSlide(state.activeSlideIdx);
        }
        switchMainTab("panel-admin");
      } else {
        if (errEl) {
          errEl.classList.remove("hidden");
          errEl.textContent = "Invalid Super-User Admin token.";
        }
      }
    } catch (e) {
      if (errEl) {
        errEl.classList.remove("hidden");
        errEl.textContent = `Unlock error: ${e.message}`;
      }
    }
  });

  document.getElementById("btn-admin-lock-session")?.addEventListener("click", async () => {
    await fetch("/api/v1/admin/lock", { method: "POST" }).catch(() => {});
    state.isAdminSession = false;
    document.getElementById("tab-btn-admin")?.classList.add("hidden");
    const footerBtn = document.getElementById("btn-footer-admin-unlock");
    if (footerBtn) footerBtn.textContent = "🔒 Admin";
    if (state.currentResult) {
      renderActiveSlide(state.activeSlideIdx);
    }
    switchMainTab("panel-storyboard");
  });

  document.getElementById("btn-admin-refresh-all")?.addEventListener("click", () => {
    loadAdminConsoleData();
  });

  // Admin 3 Sub-Tabs
  document.querySelectorAll("[data-admin-subtab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-admin-subtab");
      document.querySelectorAll("[data-admin-subtab]").forEach((b) => b.classList.toggle("active", b === btn));
      ["admin-subtab-catalog", "admin-subtab-telemetry", "admin-subtab-diagnostics"].forEach((id) => {
        document.getElementById(id)?.classList.toggle("hidden", id !== targetId);
      });
    });
  });

  // Admin Catalog filters
  ["admin-catalog-badge-select", "admin-catalog-req-select", "admin-catalog-source-select", "admin-catalog-role-select"].forEach(
    (id) => {
      document.getElementById(id)?.addEventListener("change", () => loadAdminCatalogImages());
    }
  );
  document.getElementById("admin-catalog-search-input")?.addEventListener("input", () => loadAdminCatalogImages());
  document.getElementById("btn-admin-sync-active-badge")?.addEventListener("click", () => {
    populateAdminBadgeSelector();
    const badgeSel = document.getElementById("admin-catalog-badge-select");
    if (badgeSel && state.currentBadge) {
      badgeSel.value = state.currentBadge;
      loadAdminCatalogImages();
    }
  });
  document.getElementById("btn-admin-open-nano-studio")?.addEventListener("click", () => {
    document.getElementById("btn-open-image-studio")?.click();
  });

  // Admin Inspector Actions: Save, Promote Primary, Gemini Vision Recaption, Replace/Upload Asset, Regenerate In-Place
  document.getElementById("btn-admin-save-metadata")?.addEventListener("click", async () => {
    const item = state.selectedAdminImage;
    if (!item) return;
    const badgeName = document.getElementById("admin-catalog-badge-select")?.value || item.badge_name || "First Aid";
    const payload = {
      badge_name: badgeName,
      image_id: item.image_id,
      title: document.getElementById("admin-edit-title")?.value || item.title,
      caption: document.getElementById("admin-edit-caption")?.value || "",
      req_number: document.getElementById("admin-edit-req")?.value || "1",
      is_alternate: document.getElementById("admin-edit-role-select")?.value === "alternate",
      discard: Boolean(document.getElementById("admin-edit-discard")?.checked),
    };
    const resp = await fetch("/api/v1/admin/catalog/image", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (resp.ok) {
      showAdminInspectorFeedback("✅ Saved caption & metadata to catalog JSON and SQLite!");
      await loadAdminCatalogImages(item.image_id);
    } else {
      showAdminInspectorFeedback("⚠️ Failed to save metadata.", true);
    }
  });

  document.getElementById("btn-admin-promote-primary")?.addEventListener("click", async () => {
    const item = state.selectedAdminImage;
    if (!item) return;
    const badgeName = document.getElementById("admin-catalog-badge-select")?.value || item.badge_name || "First Aid";
    const reqNum = document.getElementById("admin-edit-req")?.value || item.req_number || "1";
    const resp = await fetch("/api/v1/admin/catalog/promote-primary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        badge_name: badgeName,
        image_id: item.image_id,
        req_number: reqNum,
      }),
    });
    if (resp.ok) {
      showAdminInspectorFeedback(`⭐ Promoted to Primary Default for ${badgeName} Req ${reqNum}!`);
      await loadAdminCatalogImages(item.image_id);
    } else {
      showAdminInspectorFeedback("⚠️ Could not promote image.", true);
    }
  });

  document.getElementById("btn-admin-recaption-vision")?.addEventListener("click", async (ev) => {
    const item = state.selectedAdminImage;
    if (!item) return;
    const btn = ev.currentTarget;
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = "⏳ Captioning with Gemini Vision...";
    const badgeName = document.getElementById("admin-catalog-badge-select")?.value || item.badge_name || "First Aid";
    const reqNum = document.getElementById("admin-edit-req")?.value || item.req_number || "1";
    try {
      const resp = await fetch("/api/v1/admin/catalog/recaption-vision", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: badgeName,
          image_id: item.image_id,
          req_number: reqNum,
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        const capInput = document.getElementById("admin-edit-caption");
        if (capInput && data.caption) capInput.value = data.caption;
        showAdminInspectorFeedback(`✨ Auto-captioned via ${data.vision_model_used || "Gemini Vision"}!`);
        await loadAdminCatalogImages(item.image_id);
      } else {
        showAdminInspectorFeedback("⚠️ Vision recaption failed.", true);
      }
    } finally {
      btn.disabled = false;
      btn.textContent = orig;
    }
  });

  // Admin #3: Replace / Upload Built-In Asset & Regenerate In-Place with Nano Banana
  const adminReplaceBtn = document.getElementById("btn-admin-replace-upload");
  const adminReplaceFile = document.getElementById("admin-replace-file-input");
  adminReplaceBtn?.addEventListener("click", () => {
    if (!state.selectedAdminImage) return;
    adminReplaceFile?.click();
  });
  adminReplaceFile?.addEventListener("change", () => {
    const file = adminReplaceFile.files?.[0];
    const item = state.selectedAdminImage;
    if (!file || !item) return;
    const badgeName = document.getElementById("admin-catalog-badge-select")?.value || item.badge_name || "First Aid";
    const reader = new FileReader();
    reader.onload = async (ev) => {
      const dataUrl = String(ev.target?.result || "");
      showAdminInspectorFeedback("⏳ Backing up original asset & quantizing replacement to 8-bit PNG...");
      const resp = await fetch("/api/v1/admin/catalog/replace-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: badgeName,
          image_id: item.image_id,
          req_number: document.getElementById("admin-edit-req")?.value || item.req_number || "1",
          data_url: dataUrl,
          title: document.getElementById("admin-edit-title")?.value || item.title || "",
          caption: document.getElementById("admin-edit-caption")?.value || item.caption || "",
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        showAdminInspectorFeedback(`✅ Replaced asset (${data.width}×${data.height}px, ${data.file_size_kb} KB) with .bak backup!`);
        await loadAdminCatalogImages(item.image_id);
      } else {
        showAdminInspectorFeedback("⚠️ Asset replacement failed.", true);
      }
    };
    reader.readAsDataURL(file);
    adminReplaceFile.value = "";
  });

  document.getElementById("btn-admin-regenerate-inplace")?.addEventListener("click", async (ev) => {
    const item = state.selectedAdminImage;
    if (!item) return;
    const btn = ev.currentTarget;
    const orig = btn.textContent;
    btn.disabled = true;
    btn.textContent = "⏳ Regenerating In-Place with Nano Banana...";
    const badgeName = document.getElementById("admin-catalog-badge-select")?.value || item.badge_name || "First Aid";
    const reqNum = document.getElementById("admin-edit-req")?.value || item.req_number || "1";
    const customPrompt =
      document.getElementById("admin-edit-caption")?.value ||
      document.getElementById("admin-edit-title")?.value ||
      `${badgeName} Requirement ${reqNum} instructional illustration`;
    try {
      const resp = await fetch("/api/v1/admin/catalog/replace-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: badgeName,
          image_id: item.image_id,
          req_number: reqNum,
          regenerate_nano_banana: true,
          custom_prompt: customPrompt,
          title: document.getElementById("admin-edit-title")?.value || item.title || "",
          caption: document.getElementById("admin-edit-caption")?.value || item.caption || "",
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        showAdminInspectorFeedback(`🍌 Regenerated in-place (${data.width}×${data.height}px, ${data.file_size_kb} KB)!`);
        await loadAdminCatalogImages(item.image_id);
      } else {
        showAdminInspectorFeedback("⚠️ Nano Banana in-place regeneration failed.", true);
      }
    } finally {
      btn.disabled = false;
      btn.textContent = orig;
    }
  });

  // Admin #9: 1-Click Maintenance Actions
  const setMaintStatus = (msg) => {
    const el = document.getElementById("admin-maint-status-banner");
    if (!el) return;
    el.classList.remove("hidden");
    el.textContent = msg;
  };
  document.getElementById("btn-admin-maint-purge-cache")?.addEventListener("click", async () => {
    setMaintStatus("⏳ Purging temporary web/AI cache files across all 144 badges...");
    const resp = await fetch("/api/v1/admin/maintenance/purge-temp-cache", { method: "POST" });
    if (resp.ok) {
      const d = await resp.json();
      setMaintStatus(`✅ Purged ${d.removed_files || 0} temporary web/AI cache file(s) across ${d.badges_scanned || 144} badges.`);
    }
  });
  document.getElementById("btn-admin-maint-repair-covers")?.addEventListener("click", async () => {
    setMaintStatus("⏳ Verifying & repairing all 144 pamphlet covers and emblems...");
    const resp = await fetch("/api/v1/admin/maintenance/repair-covers", { method: "POST" });
    if (resp.ok) {
      const d = await resp.json();
      setMaintStatus(`✅ Verified ${d.covers_verified || 144}/144 covers & ${d.emblems_verified || 144}/144 emblems (${d.repaired_count || 0} repaired).`);
      await loadAdminAssetDiagnostics();
    }
  });
  document.getElementById("btn-admin-maint-refresh-senators")?.addEventListener("click", async () => {
    setMaintStatus("⏳ Refreshing 24h U.S. Senator & Regional Civic Grounding cache...");
    const resp = await fetch("/api/v1/admin/senators/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state_code: "MA" }),
    });
    if (resp.ok) {
      setMaintStatus("✅ Refreshed U.S. Senator & Regional Civic Grounding cache!");
    }
  });
  document.getElementById("btn-admin-maint-download-snapshot")?.addEventListener("click", () => {
    window.open("/api/v1/admin/maintenance/snapshot", "_blank");
    setMaintStatus("📥 Downloading Zero-PII Admin Telemetry & Catalog Snapshot JSON...");
  });

  document.getElementById("admin-asset-matrix-search")?.addEventListener("input", () => {
    renderAdminAssetMatrixTable();
  });

  document.getElementById("btn-admin-reset-breakers")?.addEventListener("click", async () => {
    await fetch("/api/v1/admin/circuit-breakers/reset", { method: "POST" });
    await loadAdminZeroPiiTelemetry();
  });

  bindDocumentationViewerModal();
}

// ===========================================================================
// PLAN 11 FEATURE #2: OPTION A DUAL-MODE DOCUMENTATION STUDIO VIEWER
// ===========================================================================

state.docsCatalog = null;
state.currentDocId = "user_guide";
state.currentDocMarkdown = "";
state.currentDocTitle = "User Guide";
state.docsEngListVisible = false;

const DOC_PATH_TO_ID_MAP = {
  "docs/user_guide.md": "user_guide",
  "user_guide.md": "user_guide",
  "docs/admin_guide.md": "admin_guide",
  "admin_guide.md": "admin_guide",
  "readme.md": "readme",
  "docs/tdd.md": "tdd",
  "tdd.md": "tdd",
  "architecture_decisions.md": "architecture_decisions",
  "docs/adr/readme.md": "adr_readme",
  "adr/readme.md": "adr_readme",
  "docs/api_integration_guide.md": "api_integration_guide",
  "api_integration_guide.md": "api_integration_guide",
  "docs/finops-billing-and-deployment-guide.md": "finops_guide",
  "finops-billing-and-deployment-guide.md": "finops_guide",
  "scope.md": "scope",
  "spec.md": "spec",
  "docs/runbook.md": "runbook",
  "runbook.md": "runbook",
};

function slugifyDocHeading(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/<[^>]+>/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function formatDocInlineMarkdown(text, currentDocRelPath = "") {
  let s = escapeHtml(text);
  // Inline images ![alt](src)
  s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_m, alt, rawSrc) => {
    let src = rawSrc.trim();
    if (src.startsWith("images/")) {
      src = `/docs/${src}`;
    } else if (src.startsWith("docs/images/")) {
      src = `/${src}`;
    } else if (src.startsWith("./images/")) {
      src = `/docs/${src.slice(2)}`;
    }
    return `<figure class="m3-doc-zoomable-figure" data-zoom-src="${src}" data-zoom-alt="${alt}" title="Click to zoom screenshot in full-screen lightbox"><img src="${src}" alt="${alt}" class="m3-doc-zoomable-img" loading="lazy" /><span class="m3-doc-zoom-pill">🔍 Click to zoom</span></figure>`;
  });

  // Links [label](href) — use CSS class .m3-doc-inline-link so Light Mode (#003F87) & Dark Mode (#60A5FA) adapt cleanly
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, label, rawHref) => {
    const href = rawHref.trim();
    const cleanTarget = href.split("#")[0].replace(/^\.\//, "").replace(/^\.\.\//, "").toLowerCase();
    const mappedDocId =
      DOC_PATH_TO_ID_MAP[cleanTarget] ||
      (currentDocRelPath.startsWith("docs/") && DOC_PATH_TO_ID_MAP[`docs/${cleanTarget}`]);
    if (mappedDocId) {
      return `<a href="#doc-${mappedDocId}" class="m3-doc-inline-link is-internal-doc" data-internal-doc-id="${mappedDocId}">${label}</a>`;
    }
    if (href.startsWith("#")) {
      return `<a href="${href}" class="m3-doc-inline-link is-anchor-link">${label}</a>`;
    }
    return `<a href="${href}" class="m3-doc-inline-link" target="_blank" rel="noopener noreferrer">${label}</a>`;
  });

  // Bold **text**
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Italic *text*
  s = s.replace(/(^|\s)\*([^*]+)\*/g, "$1<em>$2</em>");
  // Inline code `code`
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  return s;
}

function renderDocumentationMarkdownToHtml(md, currentDocRelPath = "") {
  const lines = String(md || "").split(/\r?\n/);
  const out = [];
  const headings = [];
  let inList = false;
  let inOrderedList = false;
  let inTable = false;
  let inCodeFence = false;
  let codeFenceLang = "";
  let codeFenceLines = [];

  const closeLists = () => {
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
    if (inOrderedList) {
      out.push("</ol>");
      inOrderedList = false;
    }
  };
  const closeTable = () => {
    if (inTable) {
      out.push("</tbody></table>");
      inTable = false;
    }
  };

  const alertMetaMap = {
    NOTE: { icon: "ℹ️", label: "NOTE", cls: "is-note" },
    TIP: { icon: "💡", label: "TIP", cls: "is-tip" },
    IMPORTANT: { icon: "📌", label: "IMPORTANT", cls: "is-important" },
    WARNING: { icon: "⚠️", label: "WARNING", cls: "is-warning" },
    CAUTION: { icon: "🛑", label: "CAUTION", cls: "is-caution" },
  };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const trimmed = raw.trim();

    if (trimmed.startsWith("```")) {
      closeLists();
      closeTable();
      if (!inCodeFence) {
        inCodeFence = true;
        codeFenceLang = trimmed.slice(3).trim().toLowerCase();
        codeFenceLines = [];
      } else {
        const blockContent = codeFenceLines.join("\n");
        if (codeFenceLang === "mermaid") {
          out.push(
            `<div class="m3-doc-mermaid-wrap" title="Click diagram to zoom in full-screen lightbox"><div class="mermaid">${escapeHtml(
              blockContent
            )}</div><span class="m3-doc-zoom-pill">🔍 Click diagram to zoom</span></div>`
          );
        } else {
          out.push(`<pre><code class="lang-${escapeHtml(codeFenceLang)}">${escapeHtml(blockContent)}</code></pre>`);
        }
        inCodeFence = false;
        codeFenceLang = "";
        codeFenceLines = [];
      }
      continue;
    }

    if (inCodeFence) {
      codeFenceLines.push(raw);
      continue;
    }

    if (!trimmed) {
      closeLists();
      closeTable();
      continue;
    }

    // Standalone image line
    if (/^!\[([^\]]*)\]\(([^)]+)\)$/.test(trimmed)) {
      closeLists();
      closeTable();
      out.push(`<div class="m3-doc-img-block">${formatDocInlineMarkdown(trimmed, currentDocRelPath)}</div>`);
      continue;
    }

    // Table row
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      closeLists();
      const cells = trimmed
        .slice(1, -1)
        .split("|")
        .map((c) => c.trim());
      if (cells.every((c) => /^[-:\s]+$/.test(c))) {
        continue;
      }
      if (!inTable) {
        out.push("<table><thead><tr>");
        cells.forEach((c) => out.push(`<th>${formatDocInlineMarkdown(c, currentDocRelPath)}</th>`));
        out.push("</tr></thead><tbody>");
        inTable = true;
      } else {
        out.push("<tr>");
        cells.forEach((c) => out.push(`<td>${formatDocInlineMarkdown(c, currentDocRelPath)}</td>`));
        out.push("</tr>");
      }
      continue;
    } else {
      closeTable();
    }

    if (/^---+$/.test(trimmed)) {
      closeLists();
      out.push("<hr/>");
      continue;
    }

    if (trimmed.startsWith("### ")) {
      closeLists();
      const rawTitle = trimmed.slice(4).trim();
      const slug = slugifyDocHeading(rawTitle);
      const id = `doc-sec-${slug}-${headings.length}`;
      headings.push({ level: 3, text: rawTitle.replace(/\*\*/g, "").replace(/`/g, ""), id, slug });
      out.push(`<h3 id="${id}" data-heading-slug="${slug}">${formatDocInlineMarkdown(rawTitle, currentDocRelPath)}</h3>`);
      continue;
    }
    if (trimmed.startsWith("## ")) {
      closeLists();
      const rawTitle = trimmed.slice(3).trim();
      const slug = slugifyDocHeading(rawTitle);
      const id = `doc-sec-${slug}-${headings.length}`;
      headings.push({ level: 2, text: rawTitle.replace(/\*\*/g, "").replace(/`/g, ""), id, slug });
      out.push(`<h2 id="${id}" data-heading-slug="${slug}">${formatDocInlineMarkdown(rawTitle, currentDocRelPath)}</h2>`);
      continue;
    }
    if (trimmed.startsWith("# ")) {
      closeLists();
      const rawTitle = trimmed.slice(2).trim();
      const slug = slugifyDocHeading(rawTitle);
      const id = `doc-sec-${slug}-${headings.length}`;
      out.push(`<h1 id="${id}" data-heading-slug="${slug}">${formatDocInlineMarkdown(rawTitle, currentDocRelPath)}</h1>`);
      continue;
    }

    if (trimmed.startsWith(">")) {
      closeLists();
      const quoteLines = [trimmed.replace(/^>\s?/, "")];
      while (i + 1 < lines.length && lines[i + 1].trim().startsWith(">")) {
        i += 1;
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ""));
      }
      const combinedQuote = quoteLines.join(" ").trim();
      const alertMatch = combinedQuote.match(/^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(.*)$/i);
      if (alertMatch) {
        const kind = alertMatch[1].toUpperCase();
        const bodyPart = alertMatch[2] || "";
        const meta = alertMetaMap[kind] || alertMetaMap.NOTE;
        out.push(
          `<blockquote class="m3-doc-alert ${meta.cls}"><span class="m3-doc-alert-badge">${meta.icon} ${meta.label}</span> <span>${formatDocInlineMarkdown(
            bodyPart,
            currentDocRelPath
          )}</span></blockquote>`
        );
      } else {
        out.push(`<blockquote>${formatDocInlineMarkdown(combinedQuote, currentDocRelPath)}</blockquote>`);
      }
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      if (inOrderedList) {
        out.push("</ol>");
        inOrderedList = false;
      }
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${formatDocInlineMarkdown(trimmed.replace(/^[-*]\s+/, ""), currentDocRelPath)}</li>`);
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      if (!inOrderedList) {
        out.push("<ol>");
        inOrderedList = true;
      }
      out.push(`<li>${formatDocInlineMarkdown(trimmed.replace(/^\d+\.\s+/, ""), currentDocRelPath)}</li>`);
      continue;
    }

    closeLists();
    out.push(`<p>${formatDocInlineMarkdown(trimmed, currentDocRelPath)}</p>`);
  }

  closeLists();
  closeTable();
  return { html: out.join("\n"), headings };
}

function renderDocumentationEngineeringList() {
  const navEl = document.getElementById("docs-eng-list-nav");
  if (!navEl || !state.docsCatalog) return;
  const engDocs = state.docsCatalog.engineering_docs || [];
  navEl.innerHTML = engDocs
    .map(
      (doc) => `
      <button type="button" class="m3-docs-eng-item-btn ${state.currentDocId === doc.doc_id ? "is-active" : ""}" data-doc-id="${escapeHtml(doc.doc_id)}">
        <span class="m3-docs-eng-item-title">${escapeHtml(doc.icon || "📄")} ${escapeHtml(doc.title)}</span>
        <span class="m3-docs-eng-item-path">${escapeHtml(doc.rel_path)}</span>
      </button>
    `
    )
    .join("");

  navEl.querySelectorAll("[data-doc-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const docId = btn.getAttribute("data-doc-id");
      if (docId) loadDocumentationItem(docId);
    });
  });
}

async function loadDocumentationItem(docId) {
  const bodyEl = document.getElementById("docs-viewer-markdown-body");
  const tocEl = document.getElementById("docs-toc-nav");
  const catBadgeEl = document.getElementById("docs-current-category-badge");
  const pathPillEl = document.getElementById("docs-current-rel-path");
  const ghLinkEl = document.getElementById("link-docs-current-github");
  const btnUserGuide = document.getElementById("btn-docs-select-user-guide");
  const btnAdminGuide = document.getElementById("btn-docs-select-admin-guide");
  const btnEngToggle = document.getElementById("btn-docs-toggle-eng-list");
  const engSection = document.getElementById("docs-sidebar-eng-section");

  state.currentDocId = docId;

  if (btnUserGuide) {
    const isUg = docId === "user_guide";
    btnUserGuide.classList.toggle("is-active", isUg);
    btnUserGuide.setAttribute("aria-selected", isUg ? "true" : "false");
  }
  if (btnAdminGuide) {
    const isAg = docId === "admin_guide";
    btnAdminGuide.classList.toggle("is-active", isAg);
    btnAdminGuide.setAttribute("aria-selected", isAg ? "true" : "false");
  }

  const isEngineeringDoc = docId !== "user_guide" && docId !== "admin_guide";
  if (isEngineeringDoc) {
    state.docsEngListVisible = true;
    engSection?.classList.remove("hidden");
  }
  if (btnEngToggle) {
    btnEngToggle.classList.toggle("is-active", isEngineeringDoc || state.docsEngListVisible);
    btnEngToggle.setAttribute("aria-expanded", state.docsEngListVisible ? "true" : "false");
  }
  renderDocumentationEngineeringList();

  if (bodyEl) {
    bodyEl.innerHTML = `<div style="padding:24px; color:#003F87; font-weight:700;">⏳ Loading documentation...</div>`;
  }

  try {
    const resp = await fetch(`/api/v1/docs/${encodeURIComponent(docId)}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    state.currentDocMarkdown = data.markdown || "";
    state.currentDocTitle = data.title || docId;

    if (catBadgeEl) {
      const isEng = data.category === "engineering";
      catBadgeEl.textContent = isEng ? "ENGINEERING DOC" : "USER & ADMIN DOC";
      catBadgeEl.classList.toggle("is-engineering", isEng);
    }
    if (pathPillEl) {
      pathPillEl.textContent = data.rel_path || data.repo_path || `${docId}.md`;
    }
    const subtitleEl = document.getElementById("docs-viewer-doc-subtitle");
    if (subtitleEl) {
      subtitleEl.textContent = data.subtitle || data.title || "";
    }
    if (ghLinkEl && data.github_url) {
      ghLinkEl.href = data.github_url;
    }

    const searchInput = document.getElementById("docs-viewer-search-input");
    if (searchInput) searchInput.value = "";

    renderActiveDocMarkdownAndToc(state.currentDocMarkdown, data.rel_path || "");
    document.getElementById("docs-viewer-scroll-container")?.scrollTo({ top: 0, behavior: "instant" });
  } catch (err) {
    if (bodyEl) {
      bodyEl.innerHTML = `<div style="padding:24px; color:#991B1B; font-weight:700;">Could not load document: ${escapeHtml(err.message)}</div>`;
    }
  }
}

function renderActiveDocMarkdownAndToc(markdownText, relPath = "") {
  const bodyEl = document.getElementById("docs-viewer-markdown-body");
  const tocEl = document.getElementById("docs-toc-nav");
  if (!bodyEl) return;

  const { html, headings } = renderDocumentationMarkdownToHtml(markdownText, relPath);
  bodyEl.innerHTML = html;

  // Bind internal .md links inside the rendered article so they switch documents inside the modal
  bodyEl.querySelectorAll("[data-internal-doc-id]").forEach((a) => {
    a.addEventListener("click", (ev) => {
      ev.preventDefault();
      const targetId = a.getAttribute("data-internal-doc-id");
      if (targetId) loadDocumentationItem(targetId);
    });
  });

  // Bind in-article Table of Contents anchor links (e.g. #1-getting-started-in-60-seconds) so they smooth-scroll inside #docs-viewer-scroll-container
  bodyEl.querySelectorAll('a[href^="#"]:not([data-internal-doc-id])').forEach((a) => {
    a.addEventListener("click", (ev) => {
      const rawHash = (a.getAttribute("href") || "").slice(1);
      if (!rawHash) return;
      const slug = slugifyDocHeading(rawHash);
      const targetEl =
        document.getElementById(rawHash) ||
        bodyEl.querySelector(`[data-heading-slug="${slug}"]`) ||
        bodyEl.querySelector(`[id^="doc-sec-${slug}"]`);
      if (targetEl) {
        ev.preventDefault();
        targetEl.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });

  // Bind Click-to-Zoom Lightbox on all embedded screenshots (img / figure) and Mermaid diagrams
  bodyEl.querySelectorAll(".m3-doc-zoomable-figure, .m3-doc-article-body img, img").forEach((el) => {
    if (el.dataset.zoomBound === "1") return;
    el.dataset.zoomBound = "1";
    el.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const imgNode = el.tagName === "IMG" ? el : el.querySelector("img");
      const src = imgNode?.getAttribute("src") || el.getAttribute("data-zoom-src") || "";
      const alt = imgNode?.getAttribute("alt") || el.getAttribute("data-zoom-alt") || "Embedded Documentation Screenshot";
      if (src) {
        openImageZoomLightbox({ src, title: alt, caption: alt });
      }
    });
  });

  bodyEl.querySelectorAll(".m3-doc-mermaid-wrap, .mermaid").forEach((wrapEl) => {
    if (wrapEl.dataset.zoomBound === "1") return;
    wrapEl.dataset.zoomBound = "1";
    wrapEl.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const mNode = wrapEl.classList.contains("mermaid") ? wrapEl : wrapEl.querySelector(".mermaid");
      if (!mNode) return;
      openImageZoomLightbox({
        svgHtml: mNode.innerHTML,
        title: "Architecture & Workflow Diagram (Mermaid)",
        caption: `${state.currentDocTitle || "Documentation"} — Interactive Mermaid Architecture Diagram (Use + / - or Ctrl+Scroll to zoom up to 500%)`,
      });
    });
  });

  // Render Table of Contents in left rail
  if (tocEl) {
    if (headings.length === 0) {
      tocEl.innerHTML = `<div style="font-size:0.74rem; color:#64748B; padding:4px 8px;">No section headings</div>`;
    } else {
      tocEl.innerHTML = headings
        .map(
          (h) => `
          <button type="button" class="m3-docs-toc-link ${h.level === 3 ? "is-h3" : ""}" data-toc-target="${escapeHtml(h.id)}">
            ${escapeHtml(h.text)}
          </button>
        `
        )
        .join("");
      tocEl.querySelectorAll("[data-toc-target]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const targetId = btn.getAttribute("data-toc-target");
          const targetEl = targetId ? document.getElementById(targetId) : null;
          if (targetEl) {
            targetEl.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        });
      });
    }
  }

  // Render Mermaid diagrams if present (lazy-load mermaid.js asynchronously so it never blocks page startup)
  const expandMermaidSvgs = (rootNode) => {
    rootNode.querySelectorAll(".mermaid svg").forEach((svgEl) => {
      svgEl.style.maxWidth = "100%";
      svgEl.style.width = "100%";
      svgEl.style.height = "auto";
    });
  };
  const mermaidBlocks = bodyEl.querySelectorAll(".mermaid");
  if (mermaidBlocks.length > 0) {
    if (window.mermaid) {
      try {
        window.mermaid.initialize({ startOnLoad: false, theme: "default", securityLevel: "loose" });
        window.mermaid
          .run({ nodes: mermaidBlocks })
          .then(() => expandMermaidSvgs(bodyEl))
          .catch(() => {});
      } catch (_e) {}
    } else if (!window.__mermaidLoading) {
      window.__mermaidLoading = true;
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
      s.async = true;
      s.onload = () => {
        try {
          window.mermaid.initialize({ startOnLoad: false, theme: "default", securityLevel: "loose" });
          const currentBlocks = document.querySelectorAll("#docs-viewer-markdown-body .mermaid");
          if (currentBlocks.length > 0) {
            window.mermaid
              .run({ nodes: currentBlocks })
              .then(() => expandMermaidSvgs(document))
              .catch(() => {});
          }
        } catch (_e) {}
      };
      document.head.appendChild(s);
    }
  }
}

state.lightboxZoomScale = 1.0;

function applyLightboxZoomScale(nextScale) {
  const clamped = Math.min(5.0, Math.max(0.5, Number(nextScale) || 1.0));
  state.lightboxZoomScale = Math.round(clamped * 100) / 100;
  const innerEl = document.getElementById("lightbox-content-inner");
  const scalePill = document.getElementById("lightbox-zoom-scale-pill");
  if (innerEl) {
    innerEl.style.transform = `scale(${state.lightboxZoomScale})`;
  }
  if (scalePill) {
    scalePill.textContent = `${Math.round(state.lightboxZoomScale * 100)}%`;
  }
}

function openImageZoomLightbox({ src = "", title = "Screenshot / Diagram Preview", caption = "", svgHtml = "" } = {}) {
  const modal = document.getElementById("image-zoom-lightbox-modal");
  const titleEl = document.getElementById("lightbox-modal-title");
  const innerEl = document.getElementById("lightbox-content-inner");
  const captionBar = document.getElementById("lightbox-caption-bar");
  const captionTextEl = document.getElementById("lightbox-caption-text");
  if (!modal || !innerEl) return;

  if (titleEl) {
    titleEl.textContent = title || "Screenshot / Diagram Preview";
  }
  if (svgHtml) {
    innerEl.innerHTML = `<div class="m3-lightbox-mermaid-card">${svgHtml}</div>`;
    const svgEl = innerEl.querySelector("svg");
    if (svgEl) {
      svgEl.style.maxWidth = "none";
      svgEl.style.width = "100%";
      svgEl.style.height = "auto";
    }
  } else if (src) {
    innerEl.innerHTML = `<img src="${escapeHtml(src)}" alt="${escapeHtml(title)}" class="m3-lightbox-zoomed-img" />`;
  }

  const resolvedCaption = String(caption || title || "").trim();
  if (captionBar && captionTextEl) {
    if (resolvedCaption) {
      captionTextEl.textContent = resolvedCaption;
      captionBar.classList.remove("hidden");
    } else {
      captionTextEl.textContent = "";
      captionBar.classList.add("hidden");
    }
  }

  applyLightboxZoomScale(1.0);
  modal.classList.remove("hidden");
  modal.classList.add("open");
}

function closeImageZoomLightbox() {
  const modal = document.getElementById("image-zoom-lightbox-modal");
  modal?.classList.remove("open");
  modal?.classList.add("hidden");
}

async function openDocumentationViewerModal(initialDocId = null) {
  const modal = document.getElementById("docs-viewer-modal");
  if (!modal) return;
  modal.classList.remove("hidden");
  modal.classList.add("open");

  if (!state.docsCatalog) {
    try {
      const resp = await fetch("/api/v1/docs");
      if (resp.ok) {
        state.docsCatalog = await resp.json();
      }
    } catch (_e) {}
  }

  const targetDocId = initialDocId || state.currentDocId || "user_guide";
  await loadDocumentationItem(targetDocId);
}

function bindDocumentationViewerModal() {
  const modal = document.getElementById("docs-viewer-modal");
  const closeModal = () => {
    modal?.classList.remove("open");
    modal?.classList.add("hidden");
  };

  document.getElementById("btn-open-docs-viewer")?.addEventListener("click", () => {
    openDocumentationViewerModal("user_guide");
  });
  document.getElementById("btn-close-docs-viewer-modal")?.addEventListener("click", closeModal);
  const maxBtn = document.getElementById("btn-docs-viewer-maximize");
  const dialogBox = document.getElementById("docs-studio-dialog-box");
  maxBtn?.addEventListener("click", () => {
    if (!dialogBox) return;
    const isMax = dialogBox.classList.toggle("is-maximized");
    modal?.classList.toggle("is-maximized-backdrop", isMax);
    maxBtn.textContent = isMax ? "⤡ Restore" : "⤢ Maximize";
  });
  modal?.addEventListener("click", (ev) => {
    if (ev.target === modal) closeModal();
  });

  // Bind Click-to-Zoom Lightbox modal controls
  const lbModal = document.getElementById("image-zoom-lightbox-modal");
  const lbStage = document.getElementById("lightbox-canvas-stage");
  document.getElementById("btn-close-lightbox-modal")?.addEventListener("click", closeImageZoomLightbox);
  document.getElementById("btn-lightbox-zoom-in")?.addEventListener("click", () => {
    applyLightboxZoomScale(state.lightboxZoomScale + 0.25);
  });
  document.getElementById("btn-lightbox-zoom-out")?.addEventListener("click", () => {
    applyLightboxZoomScale(state.lightboxZoomScale - 0.25);
  });
  document.getElementById("btn-lightbox-zoom-reset")?.addEventListener("click", () => {
    applyLightboxZoomScale(1.0);
  });
  lbModal?.addEventListener("click", (ev) => {
    if (ev.target === lbModal || ev.target === lbStage) {
      closeImageZoomLightbox();
    }
  });
  lbStage?.addEventListener(
    "wheel",
    (ev) => {
      if (ev.ctrlKey || ev.metaKey) {
        ev.preventDefault();
        applyLightboxZoomScale(state.lightboxZoomScale + (ev.deltaY < 0 ? 0.15 : -0.15));
      }
    },
    { passive: false }
  );
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && lbModal && !lbModal.classList.contains("hidden")) {
      ev.stopPropagation();
      closeImageZoomLightbox();
    }
  });

  // Allow clicking the 16:9 slide diagram (#stage-diagram-img) or its 🔍 Click to zoom pill (#btn-stage-zoom-image)
  // to open the Click-to-Zoom Lightbox with the slide's title and visual caption
  const openActiveSlideDiagramInLightbox = (ev) => {
    ev?.stopPropagation();
    const stageImg = document.getElementById("stage-diagram-img");
    const src = stageImg?.getAttribute("src") || "";
    if (!src) return;
    const slides = state.currentResult?.storyboard?.slides || [];
    const activeSlide = slides[state.activeSlideIdx] || {};
    const title = activeSlide.title || stageImg?.getAttribute("alt") || "Slide Visual Diagram";
    const caption =
      document.getElementById("stage-diagram-caption")?.textContent ||
      activeSlide.visual_caption ||
      stageImg?.getAttribute("alt") ||
      title;
    openImageZoomLightbox({ src, title, caption });
  };
  document.getElementById("stage-diagram-img")?.addEventListener("click", openActiveSlideDiagramInLightbox);
  document.getElementById("btn-stage-zoom-image")?.addEventListener("click", openActiveSlideDiagramInLightbox);

  // Allow clicking the Admin "Image & Caption Inspector" preview image (#admin-inspector-img) or its 🔍 Click to zoom pill (#btn-admin-inspector-zoom)
  const openAdminInspectorImageInLightbox = (ev) => {
    ev?.stopPropagation();
    const inspImg = document.getElementById("admin-inspector-img");
    const src = inspImg?.getAttribute("src") || "";
    if (!src) return;
    const title =
      document.getElementById("admin-edit-title")?.value ||
      state.selectedAdminImage?.title ||
      "Admin Catalog Visual";
    const caption =
      document.getElementById("admin-edit-caption")?.value ||
      state.selectedAdminImage?.caption ||
      state.selectedAdminImage?.description ||
      title;
    openImageZoomLightbox({ src, title, caption });
  };
  document.getElementById("admin-inspector-img")?.addEventListener("click", openAdminInspectorImageInLightbox);
  document.getElementById("btn-admin-inspector-zoom")?.addEventListener("click", openAdminInspectorImageInLightbox);

  // Allow clicking the Local File Upload preview image (#studio-upload-preview-img) in Tab 4 of the Image Studio Modal
  document.getElementById("studio-upload-preview-img")?.addEventListener("click", (ev) => {
    ev.stopPropagation();
    const upImg = document.getElementById("studio-upload-preview-img");
    const src = upImg?.getAttribute("src") || "";
    if (!src) return;
    const title = document.getElementById("studio-upload-title-input")?.value || "Uploaded Slide Image Preview";
    const caption =
      document.getElementById("studio-upload-desc-input")?.value ||
      document.getElementById("studio-upload-title-input")?.value ||
      document.getElementById("studio-upload-preview-meta")?.textContent ||
      title;
    openImageZoomLightbox({ src, title, caption });
  });

  document.getElementById("btn-docs-select-user-guide")?.addEventListener("click", () => {
    loadDocumentationItem("user_guide");
  });
  document.getElementById("btn-docs-select-admin-guide")?.addEventListener("click", () => {
    loadDocumentationItem("admin_guide");
  });

  const engToggleBtn = document.getElementById("btn-docs-toggle-eng-list");
  const engSection = document.getElementById("docs-sidebar-eng-section");
  engToggleBtn?.addEventListener("click", () => {
    state.docsEngListVisible = !state.docsEngListVisible;
    engSection?.classList.toggle("hidden", !state.docsEngListVisible);
    engToggleBtn.classList.toggle("is-active", state.docsEngListVisible);
    engToggleBtn.setAttribute("aria-expanded", state.docsEngListVisible ? "true" : "false");
    if (state.docsEngListVisible) {
      renderDocumentationEngineeringList();
      if (state.currentDocId === "user_guide" || state.currentDocId === "admin_guide") {
        loadDocumentationItem("readme");
      }
    }
  });

  document.getElementById("docs-viewer-search-input")?.addEventListener("input", (ev) => {
    const q = (ev.target.value || "").trim().toLowerCase();
    const rawMd = state.currentDocMarkdown || "";
    if (!q) {
      renderActiveDocMarkdownAndToc(rawMd);
      return;
    }
    const sections = rawMd.split(/\n(?=##\s)/);
    const matched = sections.filter((sec, idx) => idx === 0 || sec.toLowerCase().includes(q));
    renderActiveDocMarkdownAndToc(
      matched.length > 0 ? matched.join("\n\n") : `# No sections matching "${q}"\n\nTry a different keyword.`
    );
  });

  document.getElementById("btn-docs-print-doc")?.addEventListener("click", () => {
    const bodyHtml = document.getElementById("docs-viewer-markdown-body")?.innerHTML || "";
    const relPath = document.getElementById("docs-current-rel-path")?.textContent || "";
    printHtmlDocument(
      `${state.currentDocTitle || "Documentation"} — Scouts BSA Merit Badge Counselor Workbench`,
      `Source: ${relPath}`,
      bodyHtml
    );
  });

  initPowerPointTemplateStudio();
  initMultiBadgeWorkspacesAndFavorites();
  initMcpAgentHubAndPlayground();
}

// ============================================================================
// PLAN 16A: HYBRID POWERPOINT TEMPLATE & CUSTOM SLIDE THEME ENGINE
// ============================================================================

const TEMPLATE_STORAGE_KEY = "scouts_bsa_active_template_id_v1";

function getActiveTemplateProfile() {
  const tplId = state.activeTemplateId || "default_workbench";
  const list = state.templateCatalog || [];
  return list.find((t) => t.template_id === tplId) || list[0] || {
    template_id: "default_workbench",
    name: "Workbench Classic (Full Canvas)",
    primary_hex: "#003F87",
    accent_hex: "#D4AF37",
    card_bg_hex: "#EFF6FF",
    safe_bounds: { content_bottom_max_in: 6.95 },
  };
}

window.renderSlideTemplateOverlay = function renderSlideTemplateOverlay(isCover = false, tokens = null) {
  const overlayEl = document.getElementById("slide-template-overlay-layer");
  const xrayEl = document.getElementById("slide-safezone-xray-layer");
  const footerStrip = document.getElementById("stage-footer-strip");
  const prof = getActiveTemplateProfile();
  state.activeTemplateProfile = prof;

  if (xrayEl) {
    const showXray = Boolean(state.showSafeZoneXray);
    xrayEl.classList.toggle("hidden", !showXray);
    const bottomIn = prof?.safe_bounds?.content_bottom_max_in || 6.95;
    const contentLbl = document.getElementById("xray-content-zone-label");
    const footerLbl = document.getElementById("xray-footer-zone-label");
    if (contentLbl) {
      contentLbl.textContent = `ZONES 2–4: INSTRUCTIONAL CARDS & VISUAL SAFE CANVAS (1.12"–${bottomIn.toFixed(2)}")`;
    }
    if (footerLbl) {
      footerLbl.textContent =
        prof.template_id === "default_workbench"
          ? `ZONE 6: STANDARD SLIDE FOOTER STRIP (7.15"–7.43")`
          : `RESERVED TEMPLATE BRANDING & LOGO SAFE ZONE (${bottomIn.toFixed(2)}"–7.50") • Template: ${prof.name}`;
    }
  }

  if (!overlayEl) return;
  if (!prof || prof.template_id === "default_workbench") {
    overlayEl.classList.add("hidden");
    overlayEl.innerHTML = "";
    if (footerStrip) {
      footerStrip.style.background = "";
      footerStrip.style.color = "";
      footerStrip.style.paddingRight = "";
      footerStrip.style.borderRadius = "";
    }
    return;
  }

  overlayEl.classList.remove("hidden");
  const isDarkSlide = Boolean(tokens?.isStudio || document.getElementById("beautification-select")?.value === "STUDIO");
  const parts = [];

  if (isCover && prof.cover_bg_url) {
    parts.push(
      `<img src="${escapeHtml(prof.cover_bg_url)}" alt="" style="position:absolute; inset:0; width:100%; height:100%; object-fit:cover; opacity:${isDarkSlide ? "0.22" : "0.18"}; pointer-events:none;" />`
    );
  } else if (!isCover && prof.canvas_watermark_url && !isDarkSlide) {
    parts.push(
      `<img src="${escapeHtml(prof.canvas_watermark_url)}" alt="" style="position:absolute; inset:0; width:100%; height:100%; object-fit:cover; opacity:0.55; pointer-events:none;" />`
    );
  }

  const silUrl = isDarkSlide ? (prof.bottom_silhouette_dark_url || prof.bottom_silhouette_url) : prof.bottom_silhouette_url;
  if (silUrl) {
    parts.push(
      `<img src="${escapeHtml(silUrl)}" alt="" style="position:absolute; left:0; right:0; bottom:0; width:100%; height:10.2%; object-fit:fill; pointer-events:none; opacity:0.95;" />`
    );
  } else if (prof.bottom_bar_hex) {
    const barHex = prof.bottom_bar_hex;
    const accHex = prof.bottom_accent_hex || "#D4AF37";
    parts.push(
      `<div style="position:absolute; left:0; bottom:1.6%; width:76%; height:4.4%; background:${escapeHtml(barHex)}; border-top:3px solid ${escapeHtml(accHex)}; border-radius:0 6px 6px 0; pointer-events:none; opacity:0.94;"></div>`
    );
  }

  const logoUrl = isDarkSlide ? (prof.corner_logo_dark_url || prof.corner_logo_url) : prof.corner_logo_url;
  if (logoUrl) {
    parts.push(
      `<img src="${escapeHtml(logoUrl)}" alt="${escapeHtml(prof.name)} Logo" style="position:absolute; right:1.8%; bottom:1.6%; max-width:20.5%; max-height:7.6%; object-fit:contain; pointer-events:none; filter:drop-shadow(0 1px 3px rgba(15,23,42,0.18));" />`
    );
  }

  overlayEl.innerHTML = parts.join("");

  if (footerStrip) {
    if (prof.bottom_bar_hex && !silUrl) {
      footerStrip.style.background = "transparent";
      footerStrip.style.color = "#F8FAFC";
      footerStrip.style.paddingRight = "24%";
      footerStrip.style.position = "relative";
      footerStrip.style.zIndex = "4";
    } else if (silUrl) {
      footerStrip.style.background = "transparent";
      footerStrip.style.color = "#FFFFFF";
      footerStrip.style.paddingRight = "24%";
      footerStrip.style.position = "relative";
      footerStrip.style.zIndex = "4";
    } else {
      footerStrip.style.background = "";
      footerStrip.style.color = "";
      footerStrip.style.paddingRight = "";
    }
  }
};

function syncTemplateSelectorUi() {
  const prof = getActiveTemplateProfile();
  state.activeTemplateProfile = prof;
  const sel = document.getElementById("template-select");
  if (sel && Array.from(sel.options).some((o) => o.value === prof.template_id)) {
    sel.value = prof.template_id;
  }
  const pillLbl = document.getElementById("stage-template-pill-label");
  if (pillLbl) {
    const shortName = prof.name.replace(" (Full Canvas)", "").replace("Scouting America | ", "");
    pillLbl.textContent = `Template: ${shortName}`;
  }
}

async function applyTemplateToActiveDeck(templateId, showNotification = true) {
  state.activeTemplateId = templateId || "default_workbench";
  try {
    window.localStorage.setItem(TEMPLATE_STORAGE_KEY, state.activeTemplateId);
  } catch (_e) {}

  const prof = getActiveTemplateProfile();
  state.activeTemplateProfile = prof;
  syncTemplateSelectorUi();

  const matchPaletteChecked = document.getElementById("template-match-palette-checkbox")?.checked !== false;
  const slides = state.currentResult?.storyboard?.slides || [];
  slides.forEach((s) => {
    s.template_id = prof.template_id;
    if (matchPaletteChecked && prof.template_id !== "default_workbench") {
      s.accent_palette_key = "MATCH_TEMPLATE";
    } else if (prof.template_id === "default_workbench" && s.accent_palette_key === "MATCH_TEMPLATE") {
      s.accent_palette_key = "NAVY_GOLD";
    }
  });

  if (state.currentResult) {
    state.currentResult.template_id = prof.template_id;
    renderActiveSlide(state.activeSlideIdx);
  }
  renderTemplateCatalogGrid();

  // Synchronize downloadable .pptx in background
  if (state.currentResult && slides.length > 0) {
    try {
      const resp = await fetch("/api/v1/templates/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          badge_name: state.currentResult.badge_name || state.currentBadge || "First Aid",
          template_id: prof.template_id,
          storyboard_slides: slides,
          counselor_info: state.currentResult.counselor_info || null,
          accent_palette_key: matchPaletteChecked && prof.template_id !== "default_workbench" ? "MATCH_TEMPLATE" : null,
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.pptx_download_url && state.currentResult) {
          state.currentResult.pptx_download_url = data.pptx_download_url;
          syncDeckExportSplitButtonUi(state.preferredExportMode || "pptx");
        }
      }
    } catch (_e) {}
  }

  if (typeof window.autoSaveActiveWorkspaceDebounced === "function") {
    window.autoSaveActiveWorkspaceDebounced();
  }
  if (showNotification) {
    showToast(`Applied "${prof.name}" template (${prof.safe_bounds?.content_bottom_max_in || 6.95}" safe canvas).`, "info");
  }
}

function renderTemplateCatalogGrid() {
  const grid = document.getElementById("template-catalog-grid");
  if (!grid) return;
  const list = state.templateCatalog || [];
  const countChip = document.getElementById("template-catalog-count-chip");
  if (countChip) countChip.textContent = `${list.length} Templates`;

  const sel = document.getElementById("template-select");
  if (sel && list.length > 0) {
    sel.innerHTML = list
      .map(
        (t) =>
          `<option value="${escapeHtml(t.template_id)}" ${t.template_id === state.activeTemplateId ? "selected" : ""}>${escapeHtml(t.name)}</option>`
      )
      .join("");
  }

  grid.innerHTML = list
    .map((t) => {
      const isActive = t.template_id === (state.activeTemplateId || "default_workbench");
      const bottomSafe = (t.safe_bounds?.content_bottom_max_in || 6.95).toFixed(2);
      const previewBg = t.cover_bg_url
        ? `background-image:linear-gradient(rgba(250,248,245,0.78), rgba(250,248,245,0.84)), url('${escapeHtml(t.cover_bg_url)}'); background-size:cover;`
        : t.canvas_watermark_url
        ? `background-image:url('${escapeHtml(t.canvas_watermark_url)}'); background-size:cover;`
        : "background:#FAF8F5;";
      return `
        <div class="m3-template-card ${isActive ? "active" : ""}" data-select-template="${escapeHtml(t.template_id)}">
          <div>
            <div class="m3-template-preview-box" style="${previewBg}">
              <div style="height:16%; background:${escapeHtml(t.primary_hex || "#003F87")}; border-bottom:2px solid ${escapeHtml(t.accent_hex || "#D4AF37")}; display:flex; align-items:center; justify-content:space-between; padding:0 8px; color:#FFFFFF; font-size:0.60rem; font-weight:800;">
                <span>${escapeHtml(t.name.slice(0, 24))}</span>
                <span>16:9</span>
              </div>
              <div style="padding:6px 8px; display:grid; grid-template-columns:1.2fr 0.8fr; gap:5px; flex:1; align-items:center;">
                <div class="m3-tpl-preview-safe-card" style="background:${escapeHtml(t.card_bg_hex || "#EFF6FF")}; border-left:3px solid ${escapeHtml(t.primary_hex || "#003F87")}; border-radius:4px; height:72%; padding:3px 5px; font-size:0.52rem; font-weight:800;">
                  Safe Zone: 1.12"&ndash;${bottomSafe}"
                </div>
                <div class="m3-tpl-preview-fig-card" style="background:#FFFFFF; border:1px solid #CBD5E1; border-radius:4px; height:72%; display:flex; align-items:center; justify-content:center; font-size:0.52rem; font-weight:700;">
                  Figure
                </div>
              </div>
              <div style="height:13%; position:relative; display:flex; align-items:center; justify-content:space-between; padding:0 6px; background:${escapeHtml(t.bottom_bar_hex || "transparent")};">
                ${
                  t.bottom_silhouette_url
                    ? `<img src="${escapeHtml(t.bottom_silhouette_url)}" alt="" style="position:absolute; inset:0; width:100%; height:100%; object-fit:fill;" />`
                    : `<span style="font-size:0.50rem; color:${t.bottom_bar_hex ? "#FFFFFF" : "#64748B"}; font-weight:700;">Footer Strip</span>`
                }
                ${
                  t.corner_logo_url
                    ? `<img src="${escapeHtml(t.corner_logo_url)}" alt="" style="max-height:85%; max-width:36%; object-fit:contain; margin-left:auto; position:relative; z-index:2; background:rgba(255,255,255,0.88); padding:1px 3px; border-radius:3px;" />`
                    : ""
                }
              </div>
            </div>
            <div style="display:flex; align-items:center; justify-content:space-between; gap:4px; margin-top:7px;">
              <div style="font-size:0.79rem; font-weight:800; color:#003F87; line-height:1.2;">${escapeHtml(t.name)}</div>
              ${isActive ? `<span class="m3-chip m3-chip-primary" style="font-size:0.62rem; padding:1px 6px;">✓ Active</span>` : ""}
            </div>
            <div style="font-size:0.69rem; color:#475569; margin-top:3px; line-height:1.35;">${escapeHtml(t.description || "")}</div>
          </div>
          <div style="display:flex; align-items:center; justify-content:space-between; gap:6px; padding-top:4px; border-top:1px solid #E2E8F0; font-size:0.66rem; color:#64748B;">
            <span>📐 Max Y: <strong>${bottomSafe}"</strong></span>
            <span style="display:inline-flex; align-items:center; gap:4px;">
              <span style="width:10px; height:10px; border-radius:50%; background:${escapeHtml(t.primary_hex || "#003F87")}; display:inline-block;"></span>
              <span style="width:10px; height:10px; border-radius:50%; background:${escapeHtml(t.accent_hex || "#D4AF37")}; display:inline-block;"></span>
            </span>
          </div>
        </div>
      `;
    })
    .join("");

  grid.querySelectorAll("[data-select-template]").forEach((card) => {
    card.addEventListener("click", async () => {
      const tid = card.getAttribute("data-select-template");
      if (tid) {
        await applyTemplateToActiveDeck(tid, true);
      }
    });
  });
}

async function initPowerPointTemplateStudio() {
  state.activeTemplateId = window.localStorage.getItem(TEMPLATE_STORAGE_KEY) || "default_workbench";
  state.templateCatalog = [];
  state.showSafeZoneXray = false;

  try {
    const resp = await fetch("/api/v1/templates");
    if (resp.ok) {
      const data = await resp.json();
      state.templateCatalog = data.templates || [];
    }
  } catch (_e) {}

  syncTemplateSelectorUi();
  renderTemplateCatalogGrid();

  const openModal = () => {
    renderTemplateCatalogGrid();
    const m = document.getElementById("template-studio-modal");
    m?.classList.remove("hidden");
    m?.classList.add("open");
  };
  const closeModal = () => {
    const m = document.getElementById("template-studio-modal");
    m?.classList.remove("open");
    m?.classList.add("hidden");
  };

  document.getElementById("btn-open-template-studio-sidebar")?.addEventListener("click", openModal);
  document.getElementById("btn-stage-template-picker")?.addEventListener("click", openModal);
  document.getElementById("btn-close-template-studio")?.addEventListener("click", closeModal);

  document.getElementById("template-select")?.addEventListener("change", async (ev) => {
    await applyTemplateToActiveDeck(ev.target.value, true);
  });

  document.getElementById("template-safezone-xray-checkbox")?.addEventListener("change", (ev) => {
    state.showSafeZoneXray = Boolean(ev.target.checked);
    window.renderSlideTemplateOverlay(state.activeSlideIdx === -1, null);
  });

  document.getElementById("template-match-palette-checkbox")?.addEventListener("change", async () => {
    await applyTemplateToActiveDeck(state.activeTemplateId || "default_workbench", false);
  });

  document.getElementById("btn-upload-template-file")?.addEventListener("click", async () => {
    const fileInput = document.getElementById("template-upload-file-input");
    const statusEl = document.getElementById("template-import-status-msg");
    const file = fileInput?.files?.[0];
    if (!file) {
      showToast("Select a .pptx, .ppt, .png, or .jpg file first.", "warning");
      return;
    }
    if (statusEl) statusEl.textContent = `Uploading and analyzing ${file.name}...`;
    try {
      const arrayBuf = await file.arrayBuffer();
      const bytes = new Uint8Array(arrayBuf);
      let binary = "";
      for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
      }
      const b64 = window.btoa(binary);
      const resp = await fetch("/api/v1/templates/upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: file.name, data_base64: b64 }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "Upload failed");
      state.templateCatalog = data.templates || state.templateCatalog;
      await applyTemplateToActiveDeck(data.template.template_id, true);
      if (statusEl) statusEl.textContent = `✓ Imported and applied "${data.template.name}".`;
    } catch (err) {
      if (statusEl) statusEl.textContent = `⚠️ Upload error: ${err.message}`;
    }
  });

  document.getElementById("btn-import-template-url")?.addEventListener("click", async () => {
    const urlInput = document.getElementById("template-import-url-input");
    const statusEl = document.getElementById("template-import-status-msg");
    const url = (urlInput?.value || "").trim();
    if (!url) {
      showToast("Paste an HTTP/HTTPS template URL first.", "warning");
      return;
    }
    if (statusEl) statusEl.textContent = `Downloading and inspecting template from URL...`;
    try {
      const resp = await fetch("/api/v1/templates/import-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "URL import failed");
      state.templateCatalog = data.templates || state.templateCatalog;
      await applyTemplateToActiveDeck(data.template.template_id, true);
      if (statusEl) statusEl.textContent = `✓ Imported and applied "${data.template.name}".`;
    } catch (err) {
      if (statusEl) statusEl.textContent = `⚠️ URL import error: ${err.message}`;
    }
  });
}

// ============================================================================
// PLAN 16B: MULTI-BADGE COUNSELOR WORKSPACES, FAVORITES & SAVED DECK LIBRARY
// ============================================================================

const FAVORITES_STORAGE_KEY = "bsa_favorite_badges_v1";
const WORKSPACES_INDEX_STORAGE_KEY = "bsa_saved_workspaces_index_v1";

window.syncActiveBadgeStarButton = function syncActiveBadgeStarButton() {
  const starBtn = document.getElementById("btn-star-active-badge");
  const select = document.getElementById("badge-select");
  const current = select?.value || state.currentBadge || "First Aid";
  const favSet = new Set((state.favoriteBadges || []).map((x) => String(x).toLowerCase()));
  const isFav = favSet.has(current.toLowerCase());
  if (starBtn) {
    starBtn.textContent = isFav ? "⭐ Favorited" : "☆ Favorite";
    starBtn.style.background = isFav ? "#FEF3C7" : "";
    starBtn.style.color = isFav ? "#92400E" : "";
    starBtn.style.borderColor = isFav ? "#F59E0B" : "";
  }
  const favCountEl = document.getElementById("fav-badges-count-lbl");
  if (favCountEl) favCountEl.textContent = String((state.favoriteBadges || []).length);
};

window.toggleFavoriteBadge = async function toggleFavoriteBadge(badgeName) {
  const clean = String(badgeName || state.currentBadge || "First Aid").trim();
  if (!clean) return;
  const favs = Array.isArray(state.favoriteBadges) ? [...state.favoriteBadges] : [];
  const idx = favs.findIndex((x) => x.toLowerCase() === clean.toLowerCase());
  const nowFav = idx === -1;
  if (nowFav) {
    favs.push(clean);
  } else {
    favs.splice(idx, 1);
  }
  state.favoriteBadges = favs;
  try {
    window.localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(favs));
  } catch (_e) {}

  try {
    const resp = await fetch("/api/v1/counselor/favorites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ badge_name: clean, is_favorite: nowFav }),
    });
    if (resp.ok) {
      const data = await resp.json();
      if (Array.isArray(data.favorites)) {
        state.favoriteBadges = data.favorites;
        window.localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(data.favorites));
      }
    }
  } catch (_e) {}

  applyBadgeFilters(false);
  renderQuickSelectBadgesRow();
  window.syncActiveBadgeStarButton();
  showToast(
    nowFav ? `⭐ Added "${clean}" to My Favorite Merit Badges.` : `Removed "${clean}" from My Favorites.`,
    "info"
  );
};

function renderQuickSelectBadgesRow() {
  const row = document.getElementById("quick-badges-row");
  if (!row) return;
  const mode = state.quickSelectMode || "popular";
  const favCountEl = document.getElementById("fav-badges-count-lbl");
  if (favCountEl) favCountEl.textContent = String((state.favoriteBadges || []).length);
  const wsCountEl = document.getElementById("ws-badges-count-lbl");
  if (wsCountEl) wsCountEl.textContent = String((state.savedWorkspaces || []).length);

  if (mode === "favorites") {
    const favs = state.favoriteBadges || [];
    if (favs.length === 0) {
      row.innerHTML = `<div style="font-size:0.74rem; color:#64748B; padding:4px 2px;">No starred badges yet — click <strong>☆ Favorite</strong> above or star patches in the <strong>🎖️ Patch Gallery</strong>!</div>`;
      return;
    }
    row.innerHTML = favs
      .map(
        (bName) =>
          `<button type="button" class="m3-badge-pill ${bName === state.currentBadge ? "active" : ""}" data-badge="${escapeHtml(bName)}">⭐ ${escapeHtml(bName)}</button>`
      )
      .join("");
  } else if (mode === "workspaces") {
    const wsList = state.savedWorkspaces || [];
    if (wsList.length === 0) {
      row.innerHTML = `<div style="font-size:0.74rem; color:#64748B; padding:4px 2px;">No saved decks yet — click <strong>💾 Save Deck</strong> to pin multiple badges in progress.</div>`;
      return;
    }
    row.innerHTML = wsList
      .slice(0, 8)
      .map(
        (ws) =>
          `<button type="button" class="m3-badge-pill ${ws.workspace_id === state.activeWorkspaceId ? "active" : ""}" data-switch-ws="${escapeHtml(ws.workspace_id)}">🗂️ ${escapeHtml(ws.workspace_title || ws.badge_name)}</button>`
      )
      .join("");
    row.querySelectorAll("[data-switch-ws]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const wsId = btn.getAttribute("data-switch-ws");
        if (wsId) await switchActiveWorkspace(wsId);
      });
    });
    return;
  } else {
    const popular = [
      { name: "First Aid", label: "★ First Aid" },
      { name: "Weather", label: "Weather" },
      { name: "Camping", label: "★ Camping" },
      { name: "Citizenship in the Nation", label: "★ Cit. in Nation" },
      { name: "Cooking", label: "★ Cooking" },
      { name: "Emergency Preparedness", label: "★ Emergency Prep" },
      { name: "Environmental Science", label: "★ Env. Science" },
      { name: "Robotics", label: "Robotics" },
    ];
    row.innerHTML = popular
      .map(
        (p) =>
          `<button type="button" class="m3-badge-pill ${p.name === state.currentBadge ? "active" : ""}" data-badge="${escapeHtml(p.name)}">${escapeHtml(p.label)}</button>`
      )
      .join("");
  }

  row.querySelectorAll("[data-badge]").forEach((pill) => {
    pill.addEventListener("click", async () => {
      const bName = pill.getAttribute("data-badge");
      if (!bName) return;
      const select = document.getElementById("badge-select");
      if (select) select.value = bName;
      await executeStreamingWorkflow(bName);
    });
  });
}

function renderActiveWorkspacesBar() {
  const bar = document.getElementById("active-workspaces-bar");
  const listEl = document.getElementById("active-workspaces-pills-list");
  const topPill = document.getElementById("top-workspaces-count-pill");
  const copySelect = document.getElementById("select-bluecard-copy-workspace");
  const wsList = state.savedWorkspaces || [];

  if (topPill) topPill.textContent = String(Math.max(1, wsList.length));
  const wsCountEl = document.getElementById("ws-badges-count-lbl");
  if (wsCountEl) wsCountEl.textContent = String(Math.max(1, wsList.length));

  if (copySelect) {
    const otherWs = wsList.filter((w) => w.workspace_id !== state.activeWorkspaceId);
    copySelect.innerHTML =
      `<option value="">🔁 Copy Scouts From Deck (${otherWs.length})...</option>` +
      otherWs
        .map(
          (w) =>
            `<option value="${escapeHtml(w.workspace_id)}">📋 ${escapeHtml(w.workspace_title || w.badge_name)} (${w.scout_count || 0} Scouts)</option>`
        )
        .join("");
  }

  if (!bar || !listEl) return;
  if (!state.currentResult) {
    bar.classList.add("hidden");
    return;
  }
  bar.classList.remove("hidden");

  const itemsHtml = wsList
    .slice(0, 6)
    .map((ws) => {
      const isAct = ws.workspace_id === state.activeWorkspaceId;
      const slug = badgeNameToEmblemSlug(ws.badge_name || "First Aid");
      const label = ws.session_label ? `${ws.badge_name} (${ws.session_label})` : ws.workspace_title || ws.badge_name;
      return `
        <button type="button" class="m3-ws-pill ${isAct ? "active" : ""}" data-ws-bar-id="${escapeHtml(ws.workspace_id)}" title="Switch to ${escapeHtml(ws.workspace_title || ws.badge_name)} (${ws.slide_count || 0} slides, ${ws.scout_count || 0} Scouts)">
          <img src="/assets/badge_emblems/${escapeHtml(slug)}.png" alt="" style="width:16px; height:16px; border-radius:50%; object-fit:contain;" />
          <span>${escapeHtml(label)}</span>
          <span class="m3-ws-pill-meta">&bull; ${ws.scout_count || 0} Scouts</span>
        </button>
      `;
    })
    .join("");

  listEl.innerHTML = `<span style="font-size:0.72rem; font-weight:800; color:#003F87; margin-right:2px;">🗂️ Active Decks:</span>${itemsHtml}`;
  listEl.querySelectorAll("[data-ws-bar-id]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const wid = btn.getAttribute("data-ws-bar-id");
      if (wid && wid !== state.activeWorkspaceId) {
        await switchActiveWorkspace(wid);
      }
    });
  });
}

async function saveCurrentDeckAsWorkspace(options = {}) {
  if (!state.currentResult) return null;
  const badgeName = state.currentResult.badge_name || state.currentBadge || "First Aid";
  const existingWs = (state.savedWorkspaces || []).find((w) =>
    options.forceNew
      ? false
      : state.activeWorkspaceId
      ? w.workspace_id === state.activeWorkspaceId
      : w.badge_name.toLowerCase() === badgeName.toLowerCase()
  );
  const wsId = options.forceNew ? null : existingWs?.workspace_id || state.activeWorkspaceId || null;
  const sessionLabel =
    options.sessionLabel !== undefined
      ? options.sessionLabel
      : document.getElementById("ws-session-label-input")?.value || existingWs?.session_label || "";
  const bundleTag =
    options.bundleTag !== undefined
      ? options.bundleTag
      : document.getElementById("ws-bundle-tag-input")?.value || existingWs?.camp_bundle_tag || "";
  const titleInputVal = document.getElementById("ws-title-input")?.value?.trim();
  const wsTitle =
    options.workspaceTitle ||
    titleInputVal ||
    existingWs?.workspace_title ||
    (sessionLabel ? `${badgeName} — ${sessionLabel}` : `${badgeName} Merit Badge Deck`);

  const roster = loadBadgeBlueCardRoster(badgeName);
  const slides = state.currentResult?.storyboard?.slides || [];

  const payload = {
    workspace_id: wsId,
    workspace_title: wsTitle,
    badge_name: badgeName,
    session_label: sessionLabel,
    camp_bundle_tag: bundleTag,
    template_id: state.activeTemplateId || "default_workbench",
    counselor_info: state.currentResult.counselor_info || {},
    deck_result: state.currentResult,
    blue_card_roster: roster,
    active_slide_idx: state.activeSlideIdx,
    slide_count: slides.length + 1,
    scout_count: (roster?.scouts || []).length,
  };

  try {
    const resp = await fetch("/api/v1/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (resp.ok) {
      const data = await resp.json();
      state.activeWorkspaceId = data.workspace?.workspace_id || state.activeWorkspaceId;
      state.savedWorkspaces = data.workspaces || state.savedWorkspaces;
      try {
        window.localStorage.setItem(WORKSPACES_INDEX_STORAGE_KEY, JSON.stringify(state.savedWorkspaces));
      } catch (_e) {}
      renderActiveWorkspacesBar();
      renderSavedWorkspacesGrid();
      if (options.toastMessage) showToast(options.toastMessage, "info");
      return data.workspace;
    }
  } catch (_e) {}
  return null;
}

window.autoSaveActiveWorkspaceDebounced = function autoSaveActiveWorkspaceDebounced() {
  if (state._wsAutoSaveTimer) clearTimeout(state._wsAutoSaveTimer);
  state._wsAutoSaveTimer = setTimeout(() => {
    saveCurrentDeckAsWorkspace({ toastMessage: "" });
  }, 450);
};

window.syncActiveWorkspaceBlueCardRoster = function syncActiveWorkspaceBlueCardRoster(_rosterObj) {
  window.autoSaveActiveWorkspaceDebounced();
};

window.onWorkbenchDeckHydrated = async function onWorkbenchDeckHydrated(result) {
  if (!result || state._switchingWorkspaceInProgress) return;
  const badgeName = result.badge_name || "First Aid";
  const matchWs = (state.savedWorkspaces || []).find((w) => w.badge_name.toLowerCase() === badgeName.toLowerCase());
  state.activeWorkspaceId = matchWs ? matchWs.workspace_id : null;
  await saveCurrentDeckAsWorkspace({ toastMessage: "" });
};

async function switchActiveWorkspace(workspaceId) {
  if (!workspaceId) return;
  try {
    // Auto-save current workspace before switching
    if (state.currentResult && state.activeWorkspaceId && state.activeWorkspaceId !== workspaceId) {
      await saveCurrentDeckAsWorkspace({ toastMessage: "" });
    }
    const resp = await fetch(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}`);
    if (!resp.ok) throw new Error("Workspace not found");
    const data = await resp.json();
    const ws = data.workspace;
    if (!ws) return;

    state._switchingWorkspaceInProgress = true;
    state.activeWorkspaceId = ws.workspace_id;
    state.currentBadge = ws.badge_name;
    state.activeTemplateId = ws.template_id || "default_workbench";
    syncTemplateSelectorUi();

    const select = document.getElementById("badge-select");
    if (select) select.value = ws.badge_name;

    if (ws.blue_card_roster && Array.isArray(ws.blue_card_roster.scouts)) {
      saveBadgeBlueCardRoster(ws.badge_name, ws.blue_card_roster);
    }

    if (ws.deck_result && ws.deck_result.storyboard) {
      hydrateWorkbench(ws.deck_result);
      if (typeof ws.active_slide_idx === "number" && ws.active_slide_idx >= -1) {
        state.activeSlideIdx = ws.active_slide_idx;
        renderFilmstrip(ws.deck_result.storyboard.slides || []);
        renderActiveSlide(ws.active_slide_idx);
      }
    } else {
      await executeStreamingWorkflow(ws.badge_name);
    }
    state._switchingWorkspaceInProgress = false;

    const titleIn = document.getElementById("ws-title-input");
    const sessIn = document.getElementById("ws-session-label-input");
    const bndlIn = document.getElementById("ws-bundle-tag-input");
    if (titleIn) titleIn.value = ws.workspace_title || "";
    if (sessIn) sessIn.value = ws.session_label || "";
    if (bndlIn) bndlIn.value = ws.camp_bundle_tag || "";

    renderActiveWorkspacesBar();
    renderSavedWorkspacesGrid();
    renderQuickSelectBadgesRow();
    showToast(`Switched to "${ws.workspace_title || ws.badge_name}".`, "info");
  } catch (err) {
    state._switchingWorkspaceInProgress = false;
    showToast(`Could not load workspace: ${err.message}`, "warning");
  }
}

function renderSavedWorkspacesGrid() {
  const grid = document.getElementById("saved-workspaces-grid");
  if (!grid) return;
  const q = (document.getElementById("workspaces-search-input")?.value || "").trim().toLowerCase();
  const list = (state.savedWorkspaces || []).filter((w) => {
    if (!q) return true;
    return `${w.workspace_title} ${w.badge_name} ${w.session_label} ${w.camp_bundle_tag}`.toLowerCase().includes(q);
  });

  if (list.length === 0) {
    grid.innerHTML = `<div style="padding:18px; color:#64748B; font-size:0.84rem;">No saved Merit Badge workspaces match your filter. Click <strong>💾 Save Active Deck</strong> above to save your current deck.</div>`;
    return;
  }

  grid.innerHTML = list
    .map((w) => {
      const isAct = w.workspace_id === state.activeWorkspaceId;
      const slug = badgeNameToEmblemSlug(w.badge_name || "First Aid");
      const tplProf = (state.templateCatalog || []).find((t) => t.template_id === w.template_id);
      const tplName = tplProf ? tplProf.name : "Workbench Classic";
      return `
        <div class="m3-workspace-card ${isAct ? "active" : ""}">
          <div>
            <div style="display:flex; align-items:center; gap:10px;">
              <img src="/assets/badge_emblems/${escapeHtml(slug)}.png" alt="" style="width:42px; height:42px; object-fit:contain; flex-shrink:0;" />
              <div style="min-width:0; flex:1;">
                <div style="font-size:0.86rem; font-weight:800; color:#003F87; line-height:1.25;">${escapeHtml(w.workspace_title || w.badge_name)}</div>
                <div style="font-size:0.72rem; color:#475569; margin-top:2px;">
                  <strong>${escapeHtml(w.badge_name)}</strong>
                  ${w.session_label ? ` &bull; ${escapeHtml(w.session_label)}` : ""}
                  ${w.camp_bundle_tag ? ` &bull; <span style="color:#0284C7; font-weight:700;">🏕️ ${escapeHtml(w.camp_bundle_tag)}</span>` : ""}
                </div>
              </div>
              ${isAct ? `<span class="m3-chip m3-chip-primary" style="font-size:0.65rem;">Active</span>` : ""}
            </div>
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-top:10px; font-size:0.71rem; color:#475569;">
              <span style="white-space:nowrap;">📊 <strong>${w.slide_count || 0}</strong> Slides</span>
              <span>&bull;</span>
              <span style="white-space:nowrap;">🪪 <strong>${w.scout_count || 0}</strong> Scouts in Roster</span>
              <span>&bull;</span>
              <span style="white-space:nowrap;">🖼️ ${escapeHtml(tplName.slice(0, 24))}</span>
            </div>
          </div>
          <div style="display:flex; align-items:center; justify-content:space-between; gap:6px; padding-top:8px; border-top:1px solid #E2E8F0;">
            <button type="button" class="m3-btn ${isAct ? "m3-btn-tonal" : "m3-btn-filled"}" data-ws-open="${escapeHtml(w.workspace_id)}" style="padding:5px 12px; font-size:0.74rem; font-weight:800;">
              ${isAct ? "✓ Currently Open" : "📂 Switch to Deck"}
            </button>
            <div style="display:flex; gap:5px;">
              <button type="button" class="m3-btn m3-btn-outlined" data-ws-clone="${escapeHtml(w.workspace_id)}" title="Clone this deck for another class section (e.g. Afternoon Patrol)" style="padding:5px 9px; font-size:0.72rem;">
                📑 Clone
              </button>
              <button type="button" class="m3-btn m3-btn-outlined" data-ws-delete="${escapeHtml(w.workspace_id)}" title="Delete saved deck workspace" style="padding:5px 9px; font-size:0.72rem; color:#DC2626;">
                🗑️
              </button>
            </div>
          </div>
        </div>
      `;
    })
    .join("");

  grid.querySelectorAll("[data-ws-open]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const wid = btn.getAttribute("data-ws-open");
      if (wid) {
        await switchActiveWorkspace(wid);
        const modal = document.getElementById("saved-workspaces-modal");
        modal?.classList.remove("open");
        modal?.classList.add("hidden");
      }
    });
  });

  grid.querySelectorAll("[data-ws-clone]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const wid = btn.getAttribute("data-ws-clone");
      if (!wid) return;
      const resp = await fetch(`/api/v1/workspaces/${encodeURIComponent(wid)}/clone`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_label: "Section 2 / Afternoon Patrol", copy_roster: false }),
      });
      if (resp.ok) {
        const data = await resp.json();
        state.savedWorkspaces = data.workspaces || state.savedWorkspaces;
        renderSavedWorkspacesGrid();
        renderActiveWorkspacesBar();
        showToast(`Cloned deck as "${data.workspace?.workspace_title}" with a clean Blue Card roster!`, "info");
      }
    });
  });

  grid.querySelectorAll("[data-ws-delete]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const wid = btn.getAttribute("data-ws-delete");
      if (!wid) return;
      const resp = await fetch(`/api/v1/workspaces/${encodeURIComponent(wid)}`, { method: "DELETE" });
      if (resp.ok) {
        const data = await resp.json();
        state.savedWorkspaces = data.workspaces || [];
        if (state.activeWorkspaceId === wid) {
          state.activeWorkspaceId = state.savedWorkspaces[0]?.workspace_id || null;
        }
        renderSavedWorkspacesGrid();
        renderActiveWorkspacesBar();
        showToast("Deleted saved deck workspace.", "info");
      }
    });
  });
}

async function initMultiBadgeWorkspacesAndFavorites() {
  state.quickSelectMode = "popular";
  try {
    const localFavs = JSON.parse(window.localStorage.getItem(FAVORITES_STORAGE_KEY) || "null");
    state.favoriteBadges = Array.isArray(localFavs) ? localFavs : ["First Aid", "Camping", "Weather"];
  } catch (_e) {
    state.favoriteBadges = ["First Aid", "Camping", "Weather"];
  }

  try {
    const resp = await fetch("/api/v1/counselor/favorites");
    if (resp.ok) {
      const data = await resp.json();
      if (Array.isArray(data.favorites) && data.favorites.length > 0) {
        state.favoriteBadges = data.favorites;
      }
    }
  } catch (_e) {}

  try {
    const respWs = await fetch("/api/v1/workspaces");
    if (respWs.ok) {
      const dataWs = await respWs.json();
      state.savedWorkspaces = dataWs.workspaces || [];
    }
  } catch (_e) {
    state.savedWorkspaces = [];
  }

  window.syncActiveBadgeStarButton();
  renderQuickSelectBadgesRow();
  renderActiveWorkspacesBar();

  document.getElementById("btn-star-active-badge")?.addEventListener("click", async () => {
    const select = document.getElementById("badge-select");
    const targetBadge = select?.value || state.currentBadge || "First Aid";
    await window.toggleFavoriteBadge(targetBadge);
  });

  document.querySelectorAll("[data-quick-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.quickSelectMode = btn.getAttribute("data-quick-mode") || "popular";
      document.querySelectorAll("[data-quick-mode]").forEach((b) => {
        b.classList.toggle("active", b.getAttribute("data-quick-mode") === state.quickSelectMode);
      });
      renderQuickSelectBadgesRow();
    });
  });

  const openWsModal = () => {
    const titleIn = document.getElementById("ws-title-input");
    if (titleIn && !titleIn.value && state.currentResult) {
      titleIn.value = `${state.currentResult.badge_name} Merit Badge Deck`;
    }
    renderSavedWorkspacesGrid();
    const m = document.getElementById("saved-workspaces-modal");
    m?.classList.remove("hidden");
    m?.classList.add("open");
  };
  const closeWsModal = () => {
    const m = document.getElementById("saved-workspaces-modal");
    m?.classList.remove("open");
    m?.classList.add("hidden");
  };

  document.getElementById("btn-open-saved-workspaces")?.addEventListener("click", openWsModal);
  document.getElementById("btn-ws-open-library")?.addEventListener("click", openWsModal);
  document.getElementById("btn-close-workspaces-modal")?.addEventListener("click", closeWsModal);

  document.getElementById("btn-ws-save-current")?.addEventListener("click", async () => {
    await saveCurrentDeckAsWorkspace({ toastMessage: "💾 Saved current deck & Blue Card roster to your Deck Library!" });
  });

  document.getElementById("btn-modal-save-workspace")?.addEventListener("click", async () => {
    await saveCurrentDeckAsWorkspace({ toastMessage: "💾 Updated active deck in your Deck Library!" });
  });

  const handleCloneCurrent = async () => {
    if (!state.activeWorkspaceId) {
      await saveCurrentDeckAsWorkspace({ toastMessage: "" });
    }
    if (!state.activeWorkspaceId) return;
    const label = document.getElementById("ws-session-label-input")?.value?.trim() || "Section 2 / Afternoon Patrol";
    const resp = await fetch(`/api/v1/workspaces/${encodeURIComponent(state.activeWorkspaceId)}/clone`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_label: label, copy_roster: false }),
    });
    if (resp.ok) {
      const data = await resp.json();
      state.savedWorkspaces = data.workspaces || state.savedWorkspaces;
      if (data.workspace?.workspace_id) {
        await switchActiveWorkspace(data.workspace.workspace_id);
      }
      showToast(`📑 Cloned deck for "${label}" with a fresh Blue Card roster!`, "info");
    }
  };

  document.getElementById("btn-ws-clone-section")?.addEventListener("click", handleCloneCurrent);
  document.getElementById("btn-modal-clone-workspace")?.addEventListener("click", handleCloneCurrent);
  document.getElementById("workspaces-search-input")?.addEventListener("input", renderSavedWorkspacesGrid);

  // Cross-Badge Patrol Blue Card Roster Copy
  document.getElementById("select-bluecard-copy-workspace")?.addEventListener("change", async (ev) => {
    const srcWsId = ev.target.value;
    ev.target.value = "";
    if (!srcWsId || !state.currentResult) return;
    try {
      const resp = await fetch(`/api/v1/workspaces/${encodeURIComponent(srcWsId)}`);
      if (!resp.ok) return;
      const data = await resp.json();
      const srcScouts = data.workspace?.blue_card_roster?.scouts || [];
      const badgeName = state.currentResult.badge_name || "First Aid";
      const curRoster = loadBadgeBlueCardRoster(badgeName);
      const existingNames = new Set((curRoster.scouts || []).map((s) => String(s.name || "").toLowerCase()));
      let added = 0;
      srcScouts.forEach((sc) => {
        const nm = String(sc.name || "").trim();
        if (nm && !existingNames.has(nm.toLowerCase())) {
          curRoster.scouts.push({ name: nm, completedReqs: [] });
          existingNames.add(nm.toLowerCase());
          added += 1;
        }
      });
      saveBadgeBlueCardRoster(badgeName, curRoster);
      renderBlueCardTracker(state.currentResult);
      showToast(`🔁 Copied ${added} Scout attendee(s) from "${data.workspace?.workspace_title || data.workspace?.badge_name}"!`, "info");
    } catch (_e) {}
  });

  // Portable .bsadeck.json Export & Import
  document.getElementById("btn-export-workspaces-json")?.addEventListener("click", () => {
    const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), favorites: state.favoriteBadges, workspaces: state.savedWorkspaces }, null, 2)], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `scouts_bsa_workbench_decks_${new Date().toISOString().slice(0, 10)}.bsadeck.json`;
    a.click();
  });

  document.getElementById("btn-import-workspaces-json")?.addEventListener("click", () => {
    document.getElementById("workspaces-import-json-input")?.click();
  });

  document.getElementById("workspaces-import-json-input")?.addEventListener("change", async (ev) => {
    const file = ev.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed.favorites)) {
        state.favoriteBadges = parsed.favorites;
        window.localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(parsed.favorites));
      }
      if (Array.isArray(parsed.workspaces)) {
        for (const ws of parsed.workspaces) {
          await fetch("/api/v1/workspaces", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(ws),
          });
        }
        const respWs = await fetch("/api/v1/workspaces");
        if (respWs.ok) {
          const dataWs = await respWs.json();
          state.savedWorkspaces = dataWs.workspaces || [];
        }
      }
      renderSavedWorkspacesGrid();
      renderActiveWorkspacesBar();
      renderQuickSelectBadgesRow();
      showToast("📥 Imported saved deck workspaces backup!", "info");
    } catch (_e) {
      showToast("Invalid .bsadeck.json backup file.", "warning");
    }
  });
}

// ============================================================================
// PLAN 16C: OFFICIAL SCOUTS BSA WORKBENCH MCP SERVER HUB & PLAYGROUND
// ============================================================================

const MCP_SAMPLE_PAYLOADS = {
  search_merit_badges: { query: "water", eagle_only: false, favorites_only: false },
  query_merit_badge_pamphlet: { badge_name: "First Aid", question: "How do you treat severe arterial bleeding and shock?", top_k: 4 },
  create_merit_badge_slide_deck: {
    badge_name: "Camping",
    instruction_depth: "Deep Dive",
    template_id: "scouting_america_250",
    visual_theme: "BEAUTIFIED",
    workspace_title: "Camping — Summer Camp Week 1",
    session_label: "Morning Patrol",
  },
  get_slide_deck_workspace: { workspace_id: "REPLACE_WITH_WORKSPACE_ID", include_slides: true },
  update_slide_in_deck: {
    workspace_id: "REPLACE_WITH_WORKSPACE_ID",
    slide_index: 0,
    title: "Requirement 1a: BSA Swimmer Test & Buddy System",
  },
  polish_slide_teaching_notes: { workspace_id: "REPLACE_WITH_WORKSPACE_ID", slide_index: 0, audience_level: "All Scouts (Ages 11–17)" },
  generate_or_select_slide_image: { workspace_id: "REPLACE_WITH_WORKSPACE_ID", slide_index: 0, action: "list_choices" },
  apply_powerpoint_template: { workspace_id: "REPLACE_WITH_WORKSPACE_ID", template_id: "scouting_america_forest_sunrise" },
  export_slide_deck: { workspace_id: "REPLACE_WITH_WORKSPACE_ID", export_format: "pptx" },
  generate_class_prep_and_parent_letter: { workspace_id: "REPLACE_WITH_WORKSPACE_ID", session_mode: "TWO_TROOP_MEETINGS" },
  manage_patrol_blue_card_roster: {
    workspace_id: "REPLACE_WITH_WORKSPACE_ID",
    action: "add_or_update_scout",
    scout_name: "Leo Martinez",
    troop_number: "Troop 19",
    patrol_name: "Eagle Patrol",
    completed_reqs: ["1a", "1b", "2a"],
  },
  audit_deck_conformance: { workspace_id: "REPLACE_WITH_WORKSPACE_ID" },
  "resource:bsa://templates/catalog": { uri: "bsa://templates/catalog" },
  "resource:bsa://workspaces/list": { uri: "bsa://workspaces/list" },
};

function getMcpClientConfigSnippet(clientType) {
  const origin = window.location.origin || "http://localhost:8080";
  if (clientType === "gemini") {
    return JSON.stringify(
      {
        mcpServers: {
          "scouts-bsa-workbench": {
            httpUrl: `${origin}/mcp`,
            command: "python",
            args: ["-m", "src.mcp_server"],
          },
        },
      },
      null,
      2
    );
  }
  if (clientType === "cursor") {
    return JSON.stringify(
      {
        mcpServers: {
          "scouts-bsa-workbench": {
            url: `${origin}/mcp/sse`,
          },
        },
      },
      null,
      2
    );
  }
  if (clientType === "adk") {
    return `from google.adk.tools.mcp_tool import MCPToolset, StdioServerParameters\n\ntoolset = MCPToolset(\n    connection_params=StdioServerParameters(\n        command="python",\n        args=["-m", "src.mcp_server"],\n    )\n)`;
  }
  return JSON.stringify(
    {
      mcpServers: {
        "scouts-bsa-workbench": {
          command: "python",
          args: ["-m", "src.mcp_server"],
          env: { PYTHONPATH: "." },
        },
      },
    },
    null,
    2
  );
}

async function initMcpAgentHubAndPlayground() {
  const codeEl = document.getElementById("mcp-client-config-code");
  if (codeEl) codeEl.textContent = getMcpClientConfigSnippet("claude");

  document.querySelectorAll("[data-mcp-client]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cType = btn.getAttribute("data-mcp-client") || "claude";
      document.querySelectorAll("[data-mcp-client]").forEach((b) => {
        b.classList.toggle("active", b.getAttribute("data-mcp-client") === cType);
      });
      if (codeEl) codeEl.textContent = getMcpClientConfigSnippet(cType);
    });
  });

  document.getElementById("btn-copy-mcp-client-config")?.addEventListener("click", () => {
    const txt = codeEl?.textContent || "";
    navigator.clipboard?.writeText(txt);
    showToast("📋 Copied MCP client configuration to clipboard!", "info");
  });

  const syncPlaygroundSampleArgs = () => {
    const toolSel = document.getElementById("mcp-playground-tool-select");
    const argsBox = document.getElementById("mcp-playground-args-textarea");
    if (!toolSel || !argsBox) return;
    const key = toolSel.value;
    const sample = { ...(MCP_SAMPLE_PAYLOADS[key] || {}) };
    if (sample.workspace_id === "REPLACE_WITH_WORKSPACE_ID" && state.activeWorkspaceId) {
      sample.workspace_id = state.activeWorkspaceId;
    }
    argsBox.value = JSON.stringify(sample, null, 2);
  };

  document.getElementById("mcp-playground-tool-select")?.addEventListener("change", syncPlaygroundSampleArgs);

  const openMcpModal = async () => {
    syncPlaygroundSampleArgs();
    const listEl = document.getElementById("mcp-resources-and-prompts-list");
    if (listEl && !listEl.dataset.loaded) {
      try {
        const resp = await fetch("/mcp/info");
        if (resp.ok) {
          const info = await resp.json();
          listEl.dataset.loaded = "1";
          const resHtml = (info.resources || [])
            .map(
              (r) =>
                `<div class="m3-mcp-resource-item"><code>${escapeHtml(r.uri)}</code> — ${escapeHtml(r.name)}</div>`
            )
            .join("");
          const prmHtml = (info.prompts || [])
            .map(
              (p) =>
                `<div class="m3-mcp-prompt-item"><strong>💬 Prompt: ${escapeHtml(p.name)}</strong> — ${escapeHtml(p.description)}</div>`
            )
            .join("");
          listEl.innerHTML = resHtml + prmHtml;
        }
      } catch (_e) {}
    }
    const m = document.getElementById("mcp-hub-modal");
    m?.classList.remove("hidden");
    m?.classList.add("open");
  };

  const closeMcpModal = () => {
    const m = document.getElementById("mcp-hub-modal");
    m?.classList.remove("open");
    m?.classList.add("hidden");
  };

  document.getElementById("btn-open-mcp-hub")?.addEventListener("click", openMcpModal);
  document.getElementById("btn-close-mcp-hub")?.addEventListener("click", closeMcpModal);

  document.getElementById("btn-mcp-open-guide-doc")?.addEventListener("click", () => {
    closeMcpModal();
    if (typeof openDocumentationViewerModal === "function") {
      openDocumentationViewerModal("mcp_server_guide");
    }
  });

  document.getElementById("btn-run-mcp-playground")?.addEventListener("click", async () => {
    const toolSel = document.getElementById("mcp-playground-tool-select");
    const argsBox = document.getElementById("mcp-playground-args-textarea");
    const outPre = document.getElementById("mcp-playground-output");
    if (!toolSel || !argsBox || !outPre) return;

    let parsedArgs = {};
    try {
      parsedArgs = JSON.parse(argsBox.value || "{}");
    } catch (err) {
      outPre.textContent = `JSON Parse Error in Arguments: ${err.message}`;
      return;
    }

    const selVal = toolSel.value;
    const rpcBody = selVal.startsWith("resource:")
      ? { jsonrpc: "2.0", id: Date.now(), method: "resources/read", params: { uri: parsedArgs.uri || selVal.replace("resource:", "") } }
      : { jsonrpc: "2.0", id: Date.now(), method: "tools/call", params: { name: selVal, arguments: parsedArgs } };

    outPre.textContent = "Executing JSON-RPC 2.0 request against POST /mcp...";
    try {
      const resp = await fetch("/mcp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(rpcBody),
      });
      const data = await resp.json();
      outPre.textContent = JSON.stringify(data, null, 2);

      // If the MCP tool created or modified a workspace, refresh our live workspace bar!
      if (selVal === "create_merit_badge_slide_deck" || selVal === "update_slide_in_deck" || selVal === "apply_powerpoint_template") {
        const respWs = await fetch("/api/v1/workspaces");
        if (respWs.ok) {
          const dataWs = await respWs.json();
          state.savedWorkspaces = dataWs.workspaces || [];
          renderActiveWorkspacesBar();
          showToast(`🤖 MCP Agent executed "${selVal}" — Deck Library synced live!`, "info");
        }
      }
    } catch (err) {
      outPre.textContent = `RPC Error: ${err.message}`;
    }
  });
}




