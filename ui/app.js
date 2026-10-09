/**
 * Scouts BSA Merit Badge Counselor Workbench Client (`ui/app.js`)
 *
 * Provides:
 * - Full 138-Badge Catalog search, category filter, and Eagle-Required / Elective filter
 * - Clean research & slide deck generation progress via SSE (`/api/workflow/stream`)
 * - Interactive Slide Deck Preview (including Cover Slide 1 with badge patch & pamphlet cover,
 *   plus all requirement & topic teaching slides)
 * - Direct links to the Official BSA Merit Badge Pamphlet & Digital Resource Guide
 * - One-click downloads for PowerPoint (`.pptx`) and Scout Workbook (`.md`)
 */

const COUNSELOR_STORAGE_KEY = "scouts_bsa_counselor_profile_v1";

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
};

const CONSTRUCTION_ANIM_CONCEPTS = {
  iso_heavy: {
    label: "3D Isometric Heavy Equipment Crew",
    frames: [
      {
        src: "/assets/construction_anim/iso_heavy_1_blueprint.jpg",
        title: "Step 1: Unrolling the 16:9 Slide Blueprint & Clearing the Foundation",
        desc: "Miniature Scouts inspect the 12-archetype slide blueprint on sawhorses while the yellow mini-bulldozer levels the warm cream 16:9 slide platform.",
        emblemSlot: { left: "68.5%", top: "21.0%", width: "7.6%" },
      },
      {
        src: "/assets/construction_anim/iso_heavy_2_header_crane.jpg",
        title: "Step 2: Mobile Tower Crane Hoisting the Navy & Gold Header Beam",
        desc: "A Scout crane operator hoists the glossy Scouts BSA navy-and-gold title header bar onto the upright 16:9 presentation frame.",
        emblemSlot: { left: "58.6%", top: "15.2%", width: "5.4%" },
      },
      {
        src: "/assets/construction_anim/iso_heavy_3_forklift_cards.jpg",
        title: "Step 3: Mini-Forklift & Scissor-Lift Stacking Rounded Teaching Cards",
        desc: "Scouts drive a yellow mini-forklift and scissor-lift to mount rounded-corner teaching cards with integrated left accent borders.",
        emblemSlot: { left: "64.2%", top: "13.0%", width: "5.6%" },
      },
      {
        src: "/assets/construction_anim/iso_heavy_4_helicopter_emblem.jpg",
        title: "Step 4: Twin-Rotor Cargo Helicopter Lowering the Merit Badge Emblem",
        desc: "A yellow Scout cargo helicopter hovers over the upper-right slot, lowering the transparent Merit Badge emblem ring guided by signal batons.",
        emblemSlot: { left: "75.4%", top: "50.8%", width: "7.2%" },
      },
      {
        src: "/assets/construction_anim/iso_heavy_5_scaffold_paint.jpg",
        title: "Step 5: Scaffolding Crew Airbrushing the Right-Side Hero Illustration",
        desc: "Scout artists on timber scaffolding use oversized paintbrushes and airbrushes to paint the outdoor hero graphic into the right visual card.",
        emblemSlot: { left: "64.2%", top: "13.0%", width: "5.6%" },
      },
      {
        src: "/assets/construction_anim/iso_heavy_6_inspect_reveal.jpg",
        title: "Step 6: Senior Patrol Leader Conformance Inspection & Spotlight Reveal",
        desc: "A Scout Inspector with a brass magnifying glass and green checkmark clipboard verifies zero text overlaps as camp spotlights reveal the finished slide!",
        emblemSlot: { left: "71.5%", top: "14.8%", width: "7.2%" },
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
        emblemSlot: { left: "86.8%", top: "22.2%", width: "11.6%" },
      },
      {
        src: "/assets/construction_anim/camp_pioneer_2_pulley_hoist.jpg",
        title: "Step 2: Block-and-Tackle Pulley Hoisting the Canvas Screen & Cards",
        desc: "Scouts haul hemp ropes through an A-frame pulley rig to hoist the crisp canvas projection screen and carved wooden teaching cards.",
        emblemSlot: { left: "86.8%", top: "22.2%", width: "11.6%" },
      },
      {
        src: "/assets/construction_anim/camp_pioneer_3_field_sketch.jpg",
        title: "Step 3: Ladder Scaffold Field Sketching & Laurel Medallion Mounting",
        desc: "A Scout artist on a lashed ladder paints the outdoor landscape on the canvas screen while another Scout secures the upper-right badge medallion.",
        emblemSlot: { left: "86.8%", top: "22.2%", width: "11.6%" },
      },
      {
        src: "/assets/construction_anim/camp_pioneer_4_campfire_premiere.jpg",
        title: "Step 4: Campfire Twilight Premiere with Brass Camp-Lantern Projector",
        desc: "As twilight falls, a brass camp-lantern projector illuminates the completed timber-framed slide deck while the patrol salutes around the campfire.",
        emblemSlot: { left: "86.8%", top: "22.2%", width: "11.6%" },
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
  const emblemUrl = `/assets/badge_emblems/${slug}.png`;
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
  const titleEl = document.getElementById("construction-step-title");
  const descEl = document.getElementById("construction-step-desc");
  const counterEl = document.getElementById("construction-frame-counter");
  const dotsEl = document.getElementById("construction-frame-dots");

  if (imgEl && imgEl.getAttribute("src") !== frame.src) {
    imgEl.classList.add("fade-step");
    setTimeout(() => {
      imgEl.src = frame.src;
      imgEl.classList.remove("fade-step");
    }, 110);
  }
  if (slotEl && frame.emblemSlot) {
    slotEl.style.left = frame.emblemSlot.left;
    slotEl.style.top = frame.emblemSlot.top;
    slotEl.style.width = frame.emblemSlot.width;
  }
  if (titleEl) titleEl.textContent = frame.title;
  if (descEl) descEl.textContent = frame.desc;
  if (counterEl) {
    const conceptNum = CONSTRUCTION_CONCEPT_ORDER.indexOf(currentConceptKey) + 1;
    counterEl.textContent = `Concept ${conceptNum}/${CONSTRUCTION_CONCEPT_ORDER.length} • Frame ${safeIdx + 1}/${frames.length} (Auto-Cycle)`;
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
  const slideStageEl = document.getElementById("widescreen-slide-stage");
  const codesignEl = document.getElementById("slide-codesign-bar");
  const notesCardEl = document.getElementById("slide-speaker-notes-card");

  animStage?.classList.remove("hidden");
  if (closeBtn) {
    closeBtn.classList.toggle("hidden", !isManualPreview && !state.currentResult);
  }
  if (statusPill) {
    statusPill.textContent = isManualPreview ? "🎬 INTERACTIVE ANIMATION SHOWCASE" : "🏗️ SCOUT SLIDE CREW AT WORK";
  }
  toolbarEl?.classList.add("hidden");
  slideStageEl?.classList.add("hidden");
  codesignEl?.classList.add("hidden");
  notesCardEl?.classList.add("hidden");

  renderConstructionFrame(state.constructionFrameIdx);
  startConstructionAnimationTimer();
}

function hideConstructionAnimationStage() {
  state.constructionManualPreview = false;
  const animStage = document.getElementById("slide-construction-stage");
  const toolbarEl = document.getElementById("slide-stage-toolbar");
  const slideStageEl = document.getElementById("widescreen-slide-stage");
  const notesCardEl = document.getElementById("slide-speaker-notes-card");

  animStage?.classList.add("hidden");
  toolbarEl?.classList.remove("hidden");
  slideStageEl?.classList.remove("hidden");
  notesCardEl?.classList.remove("hidden");
  if (state.constructionTimerId) {
    clearInterval(state.constructionTimerId);
    state.constructionTimerId = null;
  }
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
  bindFilterAndSlideControls();
  bindImageStudioModal();
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
}

async function saveCachedCounselorProfile() {
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
  if (state.currentResult) {
    renderActiveSlide(state.activeSlideIdx);
    renderStudioKitAndParentLetter(state.currentResult);
  }
}

function bindNavigationTabs() {
  const tabBtns = document.querySelectorAll(".m3-tab-btn[data-panel]");
  const panels = ["panel-storyboard", "panel-triage", "panel-workbook", "panel-studiokit"];

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const target = btn.getAttribute("data-panel");
      panels.forEach((pId) => {
        const el = document.getElementById(pId);
        if (el) {
          el.classList.toggle("hidden", pId !== target);
        }
      });
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
    const badge = document.getElementById("badge-select")?.value || state.currentBadge;
    if (badge) {
      await executeStreamingWorkflow(badge);
    }
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
      await executeStreamingWorkflow(badge);
    }
  });

  document.getElementById("depth-select")?.addEventListener("change", async () => {
    const badge = document.getElementById("badge-select")?.value || state.currentBadge;
    if (badge) {
      await executeStreamingWorkflow(badge);
    }
  });

  document.getElementById("beautification-select")?.addEventListener("change", async () => {
    const badge = document.getElementById("badge-select")?.value || state.currentBadge;
    if (badge) {
      await executeStreamingWorkflow(badge);
    }
  });

  document.getElementById("audience-select")?.addEventListener("change", async () => {
    const badge = document.getElementById("badge-select")?.value || state.currentBadge;
    if (badge) {
      await executeStreamingWorkflow(badge);
    }
  });

  document.getElementById("deep-research-checkbox")?.addEventListener("change", async () => {
    const badge = document.getElementById("badge-select")?.value || state.currentBadge;
    if (badge) {
      await executeStreamingWorkflow(badge);
    }
  });

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
}

function applyBadgeFilters(initialLoad = false) {
  const query = (document.getElementById("filter-search-input")?.value || "").trim().toLowerCase();
  const category = document.getElementById("filter-category-select")?.value || "ALL";
  const eagleMode = document.getElementById("filter-eagle-select")?.value || "ALL";

  state.filteredBadges = state.badges.filter((b) => {
    if (query && !b.badge_name.toLowerCase().includes(query) && !(b.category || "").toLowerCase().includes(query)) {
      return false;
    }
    if (category !== "ALL" && b.category !== category) {
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
    opt.textContent = `${b.is_eagle_required ? "★ " : ""}${b.badge_name} (${b.category})`;
    select.appendChild(opt);
  });

  if (state.filteredBadges.some((b) => b.badge_name === prevValue)) {
    select.value = prevValue;
  } else {
    select.value = state.filteredBadges[0].badge_name;
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
  const genBtn = document.getElementById("btn-generate-deck");
  const filmstripEl = document.getElementById("slide-filmstrip-list");

  // Hide the slide list while new slides are being generated so Research & Generation Progress occupies the top of the column
  if (filmstripEl) {
    filmstripEl.classList.add("hidden");
  }
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
        <div class="m3-trace-desc">Researching official ${escapeHtml(badgeName)} Merit Badge requirements and applying ${escapeHtml(beautificationTier)} mode...</div>
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

function hydrateWorkbench(result) {
  if (!result || result.status === "ERROR") return;
  state.currentResult = result;
  state.activeSlideIdx = -1;

  const slides = result.storyboard?.slides || [];
  const reqs = result.research_artifact?.requirements || [];
  const finops = result.finops_cost_estimate || {};
  const resolvedLoc = result.deep_research_enrichment?.resolved_location || {};

  // Update Location inference hint so counselor sees the resolved region & NOAA office
  const locHintEl = document.getElementById("location-infer-hint");
  if (locHintEl && resolvedLoc.region_label) {
    locHintEl.innerHTML = `Resolved Local Context: <strong>${escapeHtml(resolvedLoc.region_label)}</strong> &bull; ${escapeHtml(resolvedLoc.nws_office || "NOAA NWS")}`;
  }

  // Update FinOps Cost Pill in Sidebar
  const finopsUsdEl = document.getElementById("finops-cost-usd");
  const finopsMetaEl = document.getElementById("finops-cost-meta");
  if (finopsUsdEl && typeof finops.estimated_cost_usd === "number") {
    finopsUsdEl.innerHTML = `<strong>FinOps Est. Cost:</strong> $${finops.estimated_cost_usd.toFixed(2)} / $1.00 Cap`;
  }
  if (finopsMetaEl) {
    const totalTokK = Math.round(((finops.estimated_input_tokens || 0) + (finops.estimated_output_tokens || 0)) / 1000);
    finopsMetaEl.textContent = `${finops.beautification_tier || result.beautification_tier || "BEAUTIFIED"} • ~${totalTokK}K tokens`;
  }

  // 1. Update Hero Banner, Patch Image & Resource Links
  document.getElementById("hero-badge-title").textContent = `${result.badge_name} Merit Badge`;
  const categoryLabel = result.category ? ` • ${result.category.toUpperCase()}` : "";
  document.getElementById("hero-eagle-kicker").innerHTML = result.is_eagle_required
    ? `<span class="material-symbols-outlined" style="font-size:16px;">stars</span><span>★ EAGLE-REQUIRED MERIT BADGE${escapeHtml(categoryLabel)}</span>`
    : `<span class="material-symbols-outlined" style="font-size:16px;">verified</span><span>SCOUTS BSA ELECTIVE MERIT BADGE${escapeHtml(categoryLabel)}</span>`;

  const activeTier = result.beautification_tier || document.getElementById("beautification-select")?.value || "BEAUTIFIED";
  const activeAudience = result.audience_level || document.getElementById("audience-select")?.value || "All Scouts (Ages 11–17)";
  const depthDesc = (result.depth_mode || "").toLowerCase().includes("deep")
    ? "Detailed Deep-Dive Teaching Deck"
    : "Standard Troop Meeting Deck (1–3 Slides per Requirement)";
  document.getElementById("hero-badge-subtitle").textContent = `${depthDesc} • ${activeTier} Polish • ${activeAudience}`;

  const patchImg = document.getElementById("hero-badge-patch-img");
  if (patchImg && result.patch_url) {
    patchImg.src = result.patch_url;
    patchImg.alt = `${result.badge_name} Merit Badge Patch`;
  }

  document.getElementById("kpi-slide-count").textContent = String(result.slide_count || slides.length + 1);
  document.getElementById("kpi-subreq-count").textContent = String(reqs.length);

  // Download & Resource buttons (append cache-buster so browser always downloads freshly generated .pptx)
  const pptxBtn = document.getElementById("btn-download-pptx");
  if (pptxBtn && result.pptx_download_url) {
    pptxBtn.href = `${result.pptx_download_url}?v=${Date.now()}`;
  }
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

  // 2. Render Clean Generation Summary
  const traceList = document.getElementById("agent-trace-list");
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
        <div class="m3-trace-top"><span>2. Teaching Slides &amp; Beautification</span><span class="m3-trace-meta">${result.slide_count} Slides (${escapeHtml(activeTier)})</span></div>
        <div class="m3-trace-desc">Applied ${escapeHtml(activeTier)} theme styling, ${escapeHtml(activeAudience)} coaching, and Hero Graphics &amp; EDGE Skill Maps.</div>
      </div>
      <div class="m3-trace-item">
        <div class="m3-trace-top"><span>3. PowerPoint, Workbook &amp; StudioKit</span><span class="m3-trace-meta">$${(finops.estimated_cost_usd || 0.14).toFixed(2)}</span></div>
        <div class="m3-trace-desc">Ready to preview and download (.pptx slide deck, .md workbook, lesson plan &amp; parent letter).</div>
      </div>
    `;
  }

  // 3. Reveal Slide Stage and Render Storyboard Filmstrip & Active Slide (starting at Cover Slide = -1)
  updateConstructionBadgeEmblem(result.badge_name);
  hideConstructionAnimationStage();
  renderFilmstrip(slides);
  renderActiveSlide(-1);

  // 4. Render Official Requirements & Resource Links
  renderTriageMatrix(result.research_artifact || {}, pamphletUrl, drgUrl);

  // 5. Render Printable Workbook as styled wrapped Markdown
  const wbPreview = document.getElementById("workbook-markdown-preview");
  if (wbPreview) {
    wbPreview.innerHTML = renderMarkdownToStyledHtml(
      result.workbook_markdown || "# Counselor Workbook Generated"
    );
  }

  // 6. Render Counselor StudioKit (Lesson Plan, Parent Letter, Citations & FinOps)
  renderStudioKitAndParentLetter(result);
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
      const locHeader = resolvedLoc.region_label
        ? `<div class="m3-req-node-card" style="background:#EFF6FF; border-left:5px solid #003F87;">
             <div style="font-weight:800; color:#003F87;">📍 Resolved Local Region: ${escapeHtml(resolvedLoc.region_label)} (${escapeHtml(resolvedLoc.nws_office || "NOAA NWS")})</div>
             <div style="font-size:0.80rem; color:#1E293B; margin-top:4px;"><strong>Regional Hazards:</strong> ${escapeHtml(resolvedLoc.terrain_and_hazards || "")}<br/><strong>Field Study Sites:</strong> ${escapeHtml(resolvedLoc.field_site_examples || "")}</div>
           </div>`
        : "";
      citList.innerHTML =
        locHeader +
        citations
          .map((c) => {
            const liveFact = String(c.supplemental_fact || "")
              .split(storedTroop).join(troopName)
              .split("Troop 123, My Council").join(troopName);
            return `
              <div class="m3-req-node-card">
                <div style="font-weight:700; color:var(--md-sys-color-primary);">
                  <a href="${escapeHtml(c.source_url)}" target="_blank" rel="noopener noreferrer" style="color:var(--md-sys-color-primary); text-decoration:none;">${escapeHtml(c.source_title)}</a>
                  <span class="m3-chip m3-chip-primary" style="font-size:0.68rem; padding:2px 6px; margin-left:6px;">${escapeHtml(c.authority_domain || "")} &bull; Req ${escapeHtml(c.req_number || "")}</span>
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

function renderFilmstrip(slides) {
  const list = document.getElementById("slide-filmstrip-list");
  if (!list) return;
  list.classList.remove("hidden");
  list.innerHTML = "";

  // Slide 1: Cover Slide item
  const coverThumb = document.createElement("div");
  coverThumb.className = `m3-slide-thumb ${state.activeSlideIdx === -1 ? "active" : ""}`;
  coverThumb.innerHTML = `
    <div class="m3-thumb-top">
      <span>Slide 1 &bull; Cover</span>
      <span class="m3-thumb-archetype">Title &amp; Badge</span>
    </div>
    <div class="m3-thumb-title">${escapeHtml(state.currentResult?.badge_name || "")} Merit Badge</div>
  `;
  coverThumb.addEventListener("click", () => {
    hideConstructionAnimationStage();
    state.activeSlideIdx = -1;
    renderFilmstrip(slides);
    renderActiveSlide(-1);
  });
  list.appendChild(coverThumb);

  slides.forEach((s, idx) => {
    const thumb = document.createElement("div");
    thumb.className = `m3-slide-thumb ${idx === state.activeSlideIdx ? "active" : ""}`;
    const hasReqDef = Boolean(s.verbatim_requirement_text && s.verbatim_requirement_text.trim());
    const hasImg = Boolean(s.diagram_url);
    const hasHero = Boolean(s.ai_hero_image_path);
    const kindLabel =
      s.req_number === "Overview" || s.req_number === "Sources"
        ? s.req_number
        : hasReqDef
        ? "Req Intro"
        : hasImg
        ? "Diagram"
        : "Teaching";
    const badgeFlags = `${hasHero ? " ✨" : ""}`;
    thumb.innerHTML = `
      <div class="m3-thumb-top">
        <span>Slide ${idx + 2} &bull; ${s.req_number === "Overview" || s.req_number === "Sources" ? escapeHtml(s.req_number) : "Req " + escapeHtml(s.req_number || "")}</span>
        <span class="m3-thumb-archetype">${escapeHtml(kindLabel)}${badgeFlags}</span>
      </div>
      <div class="m3-thumb-title">${escapeHtml(s.title || "")}</div>
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
    ", and ",
    ", or ",
    ", then ",
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
  if (idx === -1) {
    const coverTokens = resolveSlidePaletteTokens(null, deckTier);
    document.getElementById("active-slide-index-chip").textContent = `Slide 1 of ${totalSlides}`;
    document.getElementById("active-slide-req-chip").textContent = "Cover Slide";
    if (themeChip) themeChip.textContent = `🎨 ${deckTier}`;
    groundedChip?.classList.add("hidden");
    codesignBar?.classList.add("hidden");
    magBadge?.classList.add("hidden");
    visSourceBadge?.classList.add("hidden");
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
      footerLeft.textContent = `Scouts BSA ${res.badge_name} Merit Badge • ${deckTier} Mode`;
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
              ? `<img src="${escapeHtml(res.patch_url)}" alt="Badge Emblem" style="width:116px; height:116px; object-fit:contain; flex-shrink:0;" />`
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
        ? `As an Eagle-Required Merit Badge, ${res.badge_name} builds essential lifelong citizenship, safety, and outdoor leadership skills.`
        : `The ${res.badge_name} Merit Badge gives Scouts an opportunity to explore a specialized field through hands-on practice and real-world observation.`;
      const coverNotes = `[SAY] Welcome Scouts to our ${res.badge_name} Merit Badge session, and introduce yourself (${counselorName}, ${troopName}) along with how Scouts and parents can reach you (${email || "via unit leadership"}) using Two-Deep Leadership / Youth Protection guidelines. ${eagleNote} Explain how we will work through each official requirement using this presentation, hands-on demonstrations, and your printable ${res.badge_name} Merit Badge Workbook.`;
      notesEl.innerHTML = formatSpeakerNotesHtml(coverNotes);
    }
    return;
  }

  // Case B: Content Slides (idx = 0 .. slides.length - 1)
  const slide = slides[idx];
  if (!slide) return;

  const archetype = slide.archetype || "SPLIT_VISUAL_EXPLAINER";
  const visTheme = slide.visual_theme || "NUMBERED_STEP_CARDS";
  const tokens = resolveSlidePaletteTokens(slide, deckTier);
  const reqLabel =
    slide.req_number === "Overview" || slide.req_number === "Sources"
      ? slide.req_number
      : `Requirement ${slide.req_number || idx + 1}`;

  document.getElementById("active-slide-index-chip").textContent = `Slide ${idx + 2} of ${totalSlides}`;
  document.getElementById("active-slide-req-chip").textContent = reqLabel;
  if (themeChip) themeChip.textContent = `🎨 ${tokens.tier} • ${visTheme}`;
  groundedChip?.classList.add("hidden");

  // Sync Per-Slide Interactive Co-Design Bar controls
  codesignBar?.classList.remove("hidden");
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
      magBadge.innerHTML = `<span style="display:inline-block; background:${tokens.badgeBg}; color:${tokens.badgeFg}; border:1px solid ${tokens.accentHex}; font-size:0.72rem; font-weight:700; padding:2px 10px; border-radius:999px;">🎨 ${escapeHtml(tokens.tier)} &bull; ${escapeHtml(badgeLabel)}</span>`;
    } else {
      magBadge.classList.add("hidden");
    }
  }

  const reqNumChip = document.getElementById("stage-req-number");
  if (reqNumChip) reqNumChip.style.display = "none";
  if (footerLeft) {
    footerLeft.textContent = `Scouts BSA ${res.badge_name} Merit Badge • ${tokens.tier} Mode`;
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
    leftZone.innerHTML = `
      <div class="m3-slide-card-item" style="background:${tokens.cardBg}; border:2px solid ${tokens.primaryHex}; color:${tokens.textFg};">
        <div class="m3-slide-card-anchor" style="color:${tokens.primaryHex};">❓ Patrol Scenario Challenge</div>
        <div class="m3-slide-card-text" style="color:${tokens.subTextFg};">${escapeHtml(qz.scenario_prompt || "")}</div>
      </div>
      ${(qz.options || []).map((opt, i) => `<div class="m3-slide-card-item" style="${baseCardSpec.style}"><strong style="color:${baseCardSpec.anchorColor};">Option ${String.fromCharCode(65 + i)}:</strong> <span style="color:${baseCardSpec.bodyColor};">${escapeHtml(opt)}</span></div>`).join("")}
      <div class="m3-slide-card-item" style="background:${tokens.isStudio ? "#064E3B" : "#DCFCE7"}; border:1.5px solid #15803D; color:${tokens.textFg};">
        <div class="m3-slide-card-anchor" style="color:${tokens.isStudio ? "#4ADE80" : "#15803D"};">✓ Verified Answer: ${escapeHtml(qz.correct_answer || "")}</div>
        <div class="m3-slide-card-text" style="color:${tokens.subTextFg};">${escapeHtml(qz.explanation || "")}</div>
      </div>
    `;
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

  if (visSourceBadge) {
    if (tokens.isBeautified && hasVisual && !hideVisualForIntro) {
      visSourceBadge.classList.remove("hidden");
      visSourceBadge.style.background = tokens.badgeBg;
      visSourceBadge.style.color = tokens.badgeFg;
      visSourceBadge.style.border = `1px solid ${tokens.accentHex}`;
      const srcLbl = String(slide.visual_source_label || "");
      const isNano = srcLbl.includes("Nano Banana") || String(slide.diagram_url || "").includes("_nano_hero");
      const isAiHero = !isNano && (Boolean(slide.ai_hero_image_path) || srcLbl.includes("EDGE Skill"));
      const isWeb = srcLbl.includes("Web Image") || srcLbl.includes("Wikimedia");
      const isUpload = srcLbl.includes("Uploaded");
      visSourceBadge.textContent = isNano
        ? "🍌 NANO BANANA AI ILLUSTRATION"
        : isUpload
        ? "📁 UPLOADED LOCAL IMAGE"
        : isWeb
        ? "🌐 WEB IMAGE CATALOG"
        : isAiHero
        ? "✨ EDGE SKILL CONCEPT MAP"
        : "📐 OFFICIAL PAMPHLET VISUAL";
    } else {
      visSourceBadge.classList.add("hidden");
    }
  }

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
      capEl.textContent = (slide.bullet_points && slide.bullet_points[0]) || slide.visual_caption || slide.title || "";
    }
  } else {
    if (leftZone) leftZone.style.display = "flex";
    if (rightZone) rightZone.style.display = "flex";
    if (splitContainer) splitContainer.style.gridTemplateColumns = "1.15fr 0.85fr";
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
  if (notesEl) {
    notesEl.innerHTML = formatSpeakerNotesHtml(slide.presenter_notes || "");
  }
}

function formatSpeakerNotesHtml(rawNotes) {
  const lines = String(rawNotes || "")
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines
    .map((line) => {
      const decorated = escapeHtml(line)
        .replace(/\[SAY\]/g, '<span class="m3-cue-tag">[SAY]</span>')
        .replace(/\[DEMONSTRATE\]/g, '<span class="m3-cue-tag" style="background:#E2EDC8;color:#151E00;">[DEMONSTRATE]</span>')
        .replace(/\[ASK SCOUTS\]/g, '<span class="m3-cue-tag" style="background:#FEF3C7;color:#B45309;">[ASK SCOUTS]</span>');
      return `<div style="margin-bottom:8px;">${decorated}</div>`;
    })
    .join("");
}

function renderTriageMatrix(research, pamphletUrl, drgUrl) {
  const reqs = research.requirements || [];
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
      .map(
        (r) => `
      <div class="m3-req-node-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span class="m3-chip m3-chip-primary" style="font-size:0.72rem; padding:2px 8px;">Requirement ${escapeHtml(r.req_number)}</span>
        </div>
        <div style="font-size:0.84rem; font-weight:600; color:var(--md-sys-color-on-surface); margin-top:4px;">${escapeHtml(r.req_text)}</div>
        ${
          r.safety_callout
            ? `<div style="font-size:0.75rem; color:#CE1126; font-weight:600; margin-top:4px;">&#9888; ${escapeHtml(r.safety_callout)}</div>`
            : ""
        }
      </div>
    `
      )
      .join("");

  document.getElementById("triage-col-in-class").innerHTML = renderReqCards(inClass);
  document.getElementById("triage-col-hands-on").innerHTML = renderReqCards(handsOn);
  document.getElementById("triage-col-prereq").innerHTML = renderReqCards(prereq);
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
  // Bold **text**
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
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
  const tierLbl = escapeHtml(String(finops.beautification_tier || "BEAUTIFIED"));
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
    ["Visual Polish Tier", `<code>${tierLbl}</code> (${plannedImgs} hero graphics)`],
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
        custom_image_caption: entry ? `${entry.title || ""}` : "",
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
      slide.visual_caption = data.visual_caption || slide.visual_caption;
      slide.diagram_url = data.diagram_url || (entry?.image_url || "");
      slide.diagram_path = data.diagram_path || (entry?.image_path || "");
      slide.ai_hero_image_path = data.visual_source_mode === "ai_hero" ? data.diagram_path : null;
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

function resolveClientSideContentAwareConfig(badgeName, slide, customPrompt = "", styleVal = "Auto (Content-Aware Mix)", humansMode = "auto") {
  const cleanTitle = cleanSlideTopicBoilerplate(slide?.title || "");
  const bullets = Array.isArray(slide?.bullet_points) ? slide.bullet_points : [];
  const bulletText = bullets.slice(0, 4).map((b) => cleanSlideTopicBoilerplate(String(b))).join(" ");
  const titlePromptLower = `${cleanTitle} ${customPrompt || ""}`.toLowerCase();
  const combinedLower = `${badgeName || ""} ${titlePromptLower} ${bulletText}`.toLowerCase();
  const reqClean = String(slide?.req_number || "1").trim().toLowerCase();

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
            <img src="${escapeHtml(entry.image_url)}" alt="${escapeHtml(entry.title)}" />
            <div style="display:flex; justify-content:space-between; align-items:center; gap:6px;">
              <span class="m3-chip m3-chip-primary" style="font-size:0.66rem; padding:2px 7px;">${escapeHtml(kindBadge)}</span>
              ${isCurrent ? '<span style="font-size:0.70rem; font-weight:800; color:#166534;">✓ Active on Slide</span>' : ""}
            </div>
            <div style="font-size:0.84rem; font-weight:700; color:#0F172A;">${escapeHtml(entry.title || `Badge Graphic ${idx + 1}`)}</div>
            <div style="font-size:0.76rem; color:#475569; line-height:1.4;">${escapeHtml(entry.description || "")}</div>
            <button type="button" class="m3-btn ${isCurrent ? "m3-btn-outlined" : "m3-btn-tonal"}" data-apply-catalog-idx="${idx}" style="margin-top:auto; width:100%; font-size:0.76rem; padding:7px 10px;">
              ${isCurrent ? "✓ Currently Active on Slide" : `✅ Use on Slide ${state.activeSlideIdx + 2}`}
            </button>
          </div>
        `;
      })
      .join("");

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
      });
      const activeSlide = slides[state.activeSlideIdx] || {};
      populateQuickImageSwitcher(activeSlide);
      renderModalCatalogGrid();
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
    const promptVal = document.getElementById("studio-ai-prompt-input")?.value || "";
    const cfg = resolveClientSideContentAwareConfig(
      state.currentResult.badge_name,
      slide,
      promptVal,
      styleVal,
      humansMode
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
      resolvedBadgeEl.innerHTML = `🧠 <strong>${escapeHtml(modeTag)}:</strong> ${directiveIcon} <strong>${escapeHtml(directiveText)}</strong> • Effective Style: <strong>${escapeHtml(cfg.effectiveStyle)}</strong>`;
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
                  <img src="${escapeHtml(entry.image_url)}" alt="${escapeHtml(entry.title)}" />
                  <div style="font-size:0.84rem; font-weight:700; color:#0F172A;">${escapeHtml(entry.title)}</div>
                  <div style="font-size:0.76rem; color:#475569; line-height:1.4;">${escapeHtml(entry.description)}</div>
                  <button type="button" class="m3-btn m3-btn-tonal" data-apply-ws-idx="${i}" style="margin-top:auto; width:100%; font-size:0.76rem; padding:7px 10px;">
                    ✅ Apply &amp; Cache to Slide ${state.activeSlideIdx + 2}
                  </button>
                </div>
              `
              )
              .join("");
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
    const customPrompt = document.getElementById("studio-ai-prompt-input")?.value || "";
    const resolvedCfg = resolveClientSideContentAwareConfig(
      state.currentResult.badge_name,
      slide,
      customPrompt,
      styleVal,
      humansMode
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
            statusBox.innerHTML = `<span style="color:#166534; font-weight:700;">✅ Generated &amp; verified "${escapeHtml(createdEntry.title)}" ($${Number(data.cost_estimate?.estimated_cost_usd || 0.08).toFixed(2)} USD). ${escapeHtml(alignSummary)}</span>`;
          }
          setTimeout(() => closeModal(), 750);
        } else {
          if (statusBox) {
            if (data.error_code === "NANO_BANANA_PROMPT_BLOCKED" || data.status === "ERROR") {
              const codeLbl = escapeHtml(data.error_code || "NANO_BANANA_PROMPT_BLOCKED");
              const msgLbl = escapeHtml(data.message || "Custom image prompt blocked by Youth Protection / Model Armor guardrail.");
              const remLbl = escapeHtml(data.remediation || "Use safe, educational Scouting descriptions.");
              statusBox.innerHTML = `
                <div style="background:#FEF2F2; border:1.5px solid #DC2626; border-radius:8px; padding:8px 12px; margin-top:4px; color:#991B1B;">
                  <div style="font-weight:800; font-size:0.84rem;">🛑 [${codeLbl}] ${msgLbl}</div>
                  <div style="font-size:0.78rem; margin-top:3px; color:#7F1D1D;"><strong>Remediation:</strong> ${remLbl} (Zero image tokens billed: $0.00 USD)</div>
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


