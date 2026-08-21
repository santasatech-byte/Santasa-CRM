/**
 * Santasa IVF & Hospital CRM — Live Executive Workspace Controller
 * Fully dynamic: Directly integrated with FastAPI & Supabase PostgreSQL & Audio Storage
 */

let API_BASE = localStorage.getItem("crm_api_url") || "https://santasa-crm.onrender.com/api/v1";

let authToken = localStorage.getItem("supabase_access_token") || localStorage.getItem("crm_auth_token") || null;
let refreshToken = localStorage.getItem("supabase_refresh_token") || null;
let currentExecutive = null;
let liveLeads = [];
let activeLead = null;
let currentFilter = "all";
let callInterval = null;
let callDurationSec = 0;

// Default Template Definitions
const WA_TEMPLATES = {
  appointment_confirmation: "Dear {patient_name}, your consultation at Santasa IVF ({branch_name}) is confirmed for {time}. Call 08047190001 for assistance.",
  followup_reminder: "Hello {patient_name}, this is a gentle reminder regarding your upcoming follow-up with Santasa IVF. Please let us know if you need any assistance.",
  google_review_request: "Dear {patient_name}, thank you for visiting Santasa IVF. Please take a moment to share your feedback here: {review_url}",
  ivf_brochure: "Hello {patient_name}, thank you for your enquiry with Santasa IVF. Find our comprehensive treatment packages & doctor profiles here: https://santasaivf.com/brochure",
  custom: ""
};

// -------------------------------------------------------------
// Authentication & Supabase Session Management
// -------------------------------------------------------------
async function refreshSupabaseSession() {
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken })
    });
    if (res.ok) {
      const data = await res.json();
      authToken = data.access_token;
      if (data.refresh_token) refreshToken = data.refresh_token;
      localStorage.setItem("supabase_access_token", authToken);
      localStorage.setItem("supabase_refresh_token", refreshToken);
      localStorage.setItem("crm_auth_token", authToken);
      return true;
    }
  } catch (e) {
    console.warn("Supabase session refresh failed:", e);
  }
  return false;
}

async function apiRequest(endpoint, options = {}) {
  options.headers = options.headers || {};
  options.headers["Bypass-Tunnel-Reminder"] = "true";
  options.headers["ngrok-skip-browser-warning"] = "true";
  if (authToken) {
    options.headers["Authorization"] = `Bearer ${authToken}`;
  }
  if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }

  try {
    let res = await fetch(`${API_BASE}${endpoint}`, options);
    if (res.status === 401) {
      // 1. Try refreshing active Supabase session
      const refreshed = await refreshSupabaseSession();
      if (refreshed) {
        options.headers["Authorization"] = `Bearer ${authToken}`;
        res = await fetch(`${API_BASE}${endpoint}`, options);
      } else {
        // 2. Re-authenticate
        const authRes = await authenticateDefaultExecutive();
        if (authRes && authRes.success && authToken) {
          options.headers["Authorization"] = `Bearer ${authToken}`;
          res = await fetch(`${API_BASE}${endpoint}`, options);
        }
      }
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || (err.error && err.error.message) || "API Request Failed");
    }
    return await res.json();
  } catch (err) {
    console.error(`API Error [${endpoint}]:`, err);
    throw err;
  }
}

async function authenticateDefaultExecutive(customEmail = null, customPassword = null) {
  const email = (customEmail || "executive@santasa.com").trim();
  const password = customPassword || (email.includes("admin") ? "Santasa@Admin2026!" : "Executive@2026!");

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Bypass-Tunnel-Reminder": "true",
        "ngrok-skip-browser-warning": "true"
      },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json().catch(() => null);

    if (res.ok && data && data.access_token) {
      authToken = data.access_token;
      if (data.refresh_token) {
        refreshToken = data.refresh_token;
        localStorage.setItem("supabase_refresh_token", refreshToken);
      }
      localStorage.setItem("supabase_access_token", authToken);
      localStorage.setItem("crm_auth_token", authToken);
      currentExecutive = data.user;
      updateUserProfileUI(currentExecutive);
      return { success: true, user: data.user };
    } else {
      const msg = (data && (data.detail || (data.error && data.error.message))) || "Invalid email or password.";
      return { success: false, error: msg };
    }
  } catch (e) {
    console.warn("Supabase authentication failed:", e);
    return { success: false, error: e.message || "Network error connecting to auth server." };
  }
}

// -------------------------------------------------------------
// Core Initialization & Lifecycle
// -------------------------------------------------------------
async function initApp() {
  setupEventHandlers();

  // If token is already present, verify current user
  if (authToken) {
    try {
      const user = await apiRequest("/auth/me");
      if (user) {
        currentExecutive = user;
        updateUserProfileUI(currentExecutive);
        showToast(`Welcome back, ${user.full_name || 'Executive'}!`, "success");
        await refreshLeadsQueue();
        const loginModal = document.getElementById("loginModal");
        if (loginModal) loginModal.classList.add("hidden");
        return;
      }
    } catch (e) {
      console.warn("Stored token invalid or expired:", e);
      localStorage.removeItem("supabase_access_token");
      localStorage.removeItem("supabase_refresh_token");
      localStorage.removeItem("crm_auth_token");
      authToken = null;
      refreshToken = null;
    }
  }

  // Not authenticated: enforce login screen & lock workspace
  renderEmptyWorkspace();
  const listContainer = document.getElementById("leadsListContainer");
  if (listContainer) listContainer.innerHTML = `<div class="empty-state">Authentication required. Please sign in to view the patient lead queue.</div>`;
  const nameEl = document.getElementById("userProfileName");
  const roleEl = document.getElementById("userProfileRole");
  const avatarEl = document.getElementById("userAvatar");
  if (nameEl) nameEl.textContent = "Not Signed In";
  if (roleEl) roleEl.textContent = "Authentication Required";
  if (avatarEl) avatarEl.textContent = "🔒";

  // Start periodic live background polling (every 5s) to sync new calls instantly & prevent server sleep
  setInterval(async () => {
    if (authToken && !document.hidden) {
      try {
        const leads = await apiRequest("/leads?limit=100");
        if (leads && Array.isArray(leads)) {
          const countChanged = leads.length !== liveLeads.length;
          liveLeads = leads;
          updateBadges(liveLeads);
          if (countChanged) {
            renderLeadsList(liveLeads);
            showToast("New patient call synced live!", "info");
          }
        }
      } catch (e) {
        // Silent sync catch
      }
    }
  }, 5000);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}

function updateUserProfileUI(user) {
  if (!user) return;
  const nameEl = document.getElementById("userProfileName");
  const roleEl = document.getElementById("userProfileRole");
  const avatarEl = document.getElementById("userAvatar");

  const displayName = user.full_name || (user.role === "Super Admin" ? "Admin" : "Pooja Sharma");
  if (nameEl) nameEl.textContent = displayName;
  if (roleEl) roleEl.textContent = `${user.role || 'Executive'} • Online`;
  if (avatarEl) {
    const initials = displayName.split(" ").map(n => n[0]).join("").substring(0, 2).toUpperCase() || "EX";
    avatarEl.textContent = initials;
  }
}

// -------------------------------------------------------------
// Leads Queue & Work Queue Fetching
// -------------------------------------------------------------
async function refreshLeadsQueue() {
  const container = document.getElementById("leadsListContainer");
  if (container) {
    container.innerHTML = `<div class="empty-state">Loading leads from Supabase...</div>`;
  }

  try {
    const leads = await apiRequest("/leads?limit=100");
    liveLeads = leads || [];
    renderLeadsList(liveLeads);
    updateBadges(liveLeads);

    if (liveLeads.length > 0) {
      if (!activeLead || !liveLeads.find(l => l.id === activeLead.id)) {
        await selectLead(liveLeads[0].id);
      } else {
        await selectLead(activeLead.id);
      }
    } else {
      renderEmptyWorkspace();
    }
  } catch (err) {
    if (container) {
      container.innerHTML = `<div class="empty-state error">Failed to load leads: ${err.message}</div>`;
    }
  }
}

function updateBadges(leads) {
  const allCount = leads.length;
  const newCount = leads.filter(l => l.lead_status === "New").length;
  const fuCount = leads.filter(l => l.lead_status === "Follow-up").length;
  const apptCount = leads.filter(l => l.lead_status === "Appointment Booked").length;

  const countToday = document.getElementById("countTodayBadge");
  const countDue = document.getElementById("countDueBadge");
  const countAppts = document.getElementById("countApptsBadge");
  const countAll = document.getElementById("countAllLeads");

  if (countToday) countToday.textContent = allCount;
  if (countDue) countDue.textContent = fuCount;
  if (countAppts) countAppts.textContent = apptCount;
  if (countAll) countAll.textContent = allCount;

  // Update filter buttons
  const fAll = document.getElementById("filterAll");
  const fNew = document.getElementById("filterNew");
  const fFu = document.getElementById("filterFollowup");
  const fAppt = document.getElementById("filterAppt");

  if (fAll) fAll.textContent = `All (${allCount})`;
  if (fNew) fNew.textContent = `New (${newCount})`;
  if (fFu) fFu.textContent = `Follow-up (${fuCount})`;
  if (fAppt) fAppt.textContent = `Appt (${apptCount})`;
}

function renderLeadsList(leads) {
  const container = document.getElementById("leadsListContainer");
  if (!container) return;

  let filtered = leads;
  if (currentFilter === "new") filtered = leads.filter(l => l.lead_status === "New");
  else if (currentFilter === "followup") filtered = leads.filter(l => l.lead_status === "Follow-up");
  else if (currentFilter === "appointment") filtered = leads.filter(l => l.lead_status === "Appointment Booked");

  if (filtered.length === 0) {
    container.innerHTML = `<div class="empty-state">No patient leads in this queue. Click <strong>+ New Lead</strong> to create one.</div>`;
    return;
  }

  container.innerHTML = filtered.map(lead => {
    const isSelected = activeLead && activeLead.id === lead.id ? "active selected" : "";
    const statusClass = getStatusClass(lead.lead_status);
    const priorityClass = getPriorityClass(lead.priority);
    const timeFormatted = lead.created_at ? new Date(lead.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "";

    return `
      <div class="lead-card ${isSelected}" data-lead-id="${lead.id}">
        <div class="card-top-row">
          <span class="card-patient-name">${escapeHtml(lead.patient_name)}</span>
          <span class="status-pill ${statusClass}">${escapeHtml(lead.lead_status)}</span>
        </div>
        <div class="card-meta-row">
          <span class="card-phone">${escapeHtml(lead.primary_phone || lead.normalized_phone)}</span>
          <span class="card-source-dot">•</span>
          <span>${escapeHtml(lead.lead_source || 'Enquiry')}</span>
          <span class="card-source-dot">•</span>
          <span>${escapeHtml(lead.city || 'Hassan')}</span>
        </div>
        <div class="card-bottom-row">
          <span class="priority-pill ${priorityClass}">${escapeHtml(lead.priority || 'Medium')} Priority</span>
          <span class="timeline-time">${timeFormatted}</span>
        </div>
      </div>
    `;
  }).join("");

  // Attach card click listeners
  container.querySelectorAll(".lead-card").forEach(card => {
    card.addEventListener("click", () => {
      const id = card.getAttribute("data-lead-id");
      selectLead(id);
    });
  });
}

// -------------------------------------------------------------
// Lead Selection & Timeline Rendering
// -------------------------------------------------------------
async function selectLead(leadId) {
  const found = liveLeads.find(l => l.id === leadId);
  if (found) {
    activeLead = found;
    renderActiveLead(found);
  }

  // Update selected class in sidebar
  document.querySelectorAll(".lead-card").forEach(c => {
    c.classList.toggle("selected", c.getAttribute("data-lead-id") === leadId);
  });

  try {
    const lead = await apiRequest(`/leads/${leadId}`);
    activeLead = lead;
    renderActiveLead(lead);

    // Load Live Activity Timeline
    await loadTimeline(leadId);
  } catch (err) {
    console.warn("Error refreshing lead details:", err);
  }
}

function renderActiveLead(lead) {
  if (!lead) return;

  const nameEl = document.getElementById("detailPatientName");
  const phoneEl = document.getElementById("detailPhone");
  const locEl = document.getElementById("detailLocation");
  const sourceEl = document.getElementById("detailSource");
  const deptEl = document.getElementById("detailDept");
  const statusEl = document.getElementById("detailLeadStatus");
  const priorityEl = document.getElementById("detailPriority");

  if (nameEl) nameEl.textContent = lead.patient_name;
  if (phoneEl) phoneEl.textContent = lead.primary_phone || lead.normalized_phone;
  if (locEl) locEl.textContent = lead.city ? `${lead.city}, Karnataka` : "Hassan";
  if (sourceEl) sourceEl.textContent = lead.lead_source || "Incoming Inquiry";
  if (deptEl) deptEl.textContent = lead.department || "Fertility & IVF";

  if (statusEl) {
    statusEl.textContent = lead.lead_status;
    statusEl.className = `status-pill ${getStatusClass(lead.lead_status)}`;
  }
  if (priorityEl) {
    priorityEl.textContent = `${lead.priority || 'Medium'} Priority`;
    priorityEl.className = `priority-pill ${getPriorityClass(lead.priority)}`;
  }

  // Next Follow-up card
  const fuCard = document.getElementById("nextFollowupAlert");
  const fuTime = document.getElementById("followupTimeDisplay");
  const fuNote = document.getElementById("followupNoteDisplay");

  if (lead.next_followup_at && fuCard) {
    fuCard.style.display = "flex";
    if (fuTime) fuTime.textContent = new Date(lead.next_followup_at).toLocaleString();
    if (fuNote) fuNote.textContent = lead.notes || "Follow-up scheduled";
  } else if (fuCard) {
    fuCard.style.display = "none";
  }
}

async function loadTimeline(leadId) {
  const feed = document.getElementById("timelineFeed");
  if (!feed) return;

  feed.innerHTML = `<div class="empty-state">Loading timeline...</div>`;

  try {
    const activities = await apiRequest(`/leads/${leadId}/timeline?limit=50`);
    if (!activities || activities.length === 0) {
      feed.innerHTML = `<div class="empty-state">No activities recorded yet for this patient. Click an action button above to log a call, note, or follow-up.</div>`;
      return;
    }

    feed.innerHTML = activities.map(act => {
      const type = (act.activity_type || "note").toLowerCase();
      const iconSvg = getActivityIconSvg(type);
      const timeFormatted = act.created_at ? new Date(act.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : "";
      const meta = act.metadata || {};

      let audioPlayerHtml = "";
      if (meta.recording_url) {
        let streamUrl = meta.recording_url;
        if (!streamUrl.startsWith("http")) {
          const host = window.location.hostname || "localhost";
          streamUrl = `http://${host}:8000${streamUrl}`;
        }
        audioPlayerHtml = `
          <div class="recording-player-box">
            <audio controls style="width: 100%; height: 32px;" preload="none">
              <source src="${streamUrl}" type="audio/mpeg">
              Audio playback not supported.
            </audio>
            <span class="duration-text">${meta.duration || 0}s</span>
          </div>
        `;
      }

      const isConversion = type === "conversion" || (act.title && act.title.toLowerCase().includes("conversion"));
      let iconBoxClass = "note";
      if (type.includes("call")) iconBoxClass = "call";
      else if (type.includes("whatsapp")) iconBoxClass = "whatsapp";
      else if (type.includes("appoint")) iconBoxClass = "appointment";
      else if (type.includes("follow")) iconBoxClass = "followup";
      else if (isConversion) iconBoxClass = "conversion";

      return `
        <div class="timeline-item">
          <div class="timeline-icon-box ${iconBoxClass}">
            ${iconSvg}
          </div>
          <div class="timeline-card ${isConversion ? 'highlight-conversion' : ''}">
            <div class="timeline-card-header">
              <span class="timeline-card-title">${escapeHtml(act.title)}</span>
              <span class="timeline-time">${timeFormatted}</span>
            </div>
            <div class="timeline-desc">${escapeHtml(act.description || '')}</div>
            ${audioPlayerHtml}
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    feed.innerHTML = `<div class="empty-state error">Failed to load timeline: ${err.message}</div>`;
  }
}

function renderEmptyWorkspace() {
  const nameEl = document.getElementById("detailPatientName");
  if (nameEl) nameEl.textContent = "No Patient Leads Found";
  const feed = document.getElementById("timelineFeed");
  if (feed) feed.innerHTML = `<div class="empty-state">Your workspace is clean. Create your first lead with <strong>+ New Lead</strong>.</div>`;
}

// -------------------------------------------------------------
// Interactive Action Handlers & Modals
// -------------------------------------------------------------
function setupEventHandlers() {
  // Modal Open/Close handlers
  document.querySelectorAll("[data-close]").forEach(btn => {
    btn.addEventListener("click", () => {
      const modalId = btn.getAttribute("data-close");
      const modal = document.getElementById(modalId);
      if (modal) modal.classList.add("hidden");
    });
  });

  // Global Quick Search
  const searchInput = document.getElementById("globalSearchInput");
  if (searchInput) {
    let searchTimeout = null;
    searchInput.addEventListener("input", (e) => {
      clearTimeout(searchTimeout);
      const q = e.target.value.trim();
      searchTimeout = setTimeout(async () => {
        if (!q) {
          refreshLeadsQueue();
          return;
        }
        try {
          const results = await apiRequest(`/leads/search?q=${encodeURIComponent(q)}`);
          liveLeads = results || [];
          renderLeadsList(liveLeads);
          if (liveLeads.length > 0) {
            selectLead(liveLeads[0].id);
          }
        } catch (err) {
          console.error("Search failed:", err);
        }
      }, 300);
    });
  }

  // Refresh Queue Button
  const refreshBtn = document.getElementById("refreshQueueBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => refreshLeadsQueue());
  }

  // Filters
  document.querySelectorAll(".filter-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      currentFilter = chip.getAttribute("data-filter");
      renderLeadsList(liveLeads);
    });
  });

  // New Lead Modal Open
  const newLeadBtn = document.getElementById("newLeadBtn");
  if (newLeadBtn) {
    newLeadBtn.addEventListener("click", () => {
      document.getElementById("newLeadModal").classList.remove("hidden");
    });
  }

  // New Lead Form Submit
  const newLeadForm = document.getElementById("newLeadForm");
  if (newLeadForm) {
    newLeadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        patient_name: document.getElementById("nlPatientName").value,
        primary_phone: document.getElementById("nlPhone").value,
        city: document.getElementById("nlCity").value || "Hassan",
        department: document.getElementById("nlDepartment").value,
        lead_source: document.getElementById("nlSource").value,
        priority: document.getElementById("nlPriority").value,
        notes: document.getElementById("nlNotes").value
      };

      try {
        const lead = await apiRequest("/leads", {
          method: "POST",
          body: payload
        });
        showToast(`Patient lead '${lead.patient_name}' created successfully!`, "success");
        document.getElementById("newLeadModal").classList.add("hidden");
        newLeadForm.reset();
        await refreshLeadsQueue();
        await selectLead(lead.id);
      } catch (err) {
        showToast(`Failed to create lead: ${err.message}`, "error");
      }
    });
  }

function getActiveLeadOrFirst() {
  if (activeLead) return activeLead;
  if (liveLeads && liveLeads.length > 0) {
    activeLead = liveLeads[0];
    renderActiveLead(activeLead);
    return activeLead;
  }
  return null;
}

  // Add Note Modal Open
  const noteBtn = document.getElementById("actionNoteBtn");
  if (noteBtn) {
    noteBtn.addEventListener("click", () => {
      const current = getActiveLeadOrFirst();
      if (!current) return showToast("Create or select a patient lead first.", "warning");
      document.getElementById("addNoteModal").classList.remove("hidden");
    });
  }

  // Add Note Form Submit
  const addNoteForm = document.getElementById("addNoteForm");
  if (addNoteForm) {
    addNoteForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const current = getActiveLeadOrFirst();
      if (!current) return;
      const note = document.getElementById("noteContentInput").value;
      try {
        await apiRequest(`/leads/${current.id}/notes`, {
          method: "POST",
          body: { note }
        });
        showToast("Note added to timeline", "success");
        document.getElementById("addNoteModal").classList.add("hidden");
        addNoteForm.reset();
        await loadTimeline(current.id);
      } catch (err) {
        showToast(`Failed to add note: ${err.message}`, "error");
      }
    });
  }

  // Follow-up Modal Open
  const fuBtn = document.getElementById("actionFollowupBtn");
  if (fuBtn) {
    fuBtn.addEventListener("click", () => {
      const current = getActiveLeadOrFirst();
      if (!current) return showToast("Create or select a patient lead first.", "warning");
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      const dInput = document.getElementById("fuDateInput");
      if (dInput) dInput.value = tomorrow.toISOString().slice(0, 10);
      document.getElementById("scheduleFollowupModal").classList.remove("hidden");
    });
  }

  // Follow-up Form Submit
  const fuForm = document.getElementById("scheduleFollowupForm");
  if (fuForm) {
    fuForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const current = getActiveLeadOrFirst();
      if (!current) return;
      const dVal = document.getElementById("fuDateInput")?.value || new Date().toISOString().slice(0, 10);
      const tVal = document.getElementById("fuTimeInput")?.value || "10:30";
      const scheduledAt = new Date(`${dVal}T${tVal}:00`).toISOString();
      const fuType = document.getElementById("fuTypeSelect")?.value || "Call";
      const fuNotes = document.getElementById("fuNotesInput")?.value || "";

      const payload = {
        lead_id: current.id,
        scheduled_at: scheduledAt,
        type: fuType,
        priority: "High",
        notes: fuNotes
      };

      try {
        await apiRequest("/followups", {
          method: "POST",
          body: payload
        });
        showToast("Follow-up scheduled successfully", "success");
        document.getElementById("scheduleFollowupModal").classList.add("hidden");
        fuForm.reset();
        await refreshLeadsQueue();
        await selectLead(current.id);
      } catch (err) {
        showToast(`Failed to schedule follow-up: ${err.message}`, "error");
      }
    });
  }

  // Complete Follow-up
  const markDoneBtn = document.getElementById("markFollowupDoneBtn");
  if (markDoneBtn) {
    markDoneBtn.addEventListener("click", async () => {
      const current = getActiveLeadOrFirst();
      if (!current) return;
      try {
        const workQueue = await apiRequest("/followups/work-queue");
        const allItems = [...(workQueue.due_today || []), ...(workQueue.overdue || []), ...(workQueue.upcoming || [])];
        const match = allItems.find(item => item.lead_id === current.id);

        if (match) {
          await apiRequest(`/followups/${match.id}/complete`, {
            method: "POST",
            body: { completion_notes: "Follow-up marked as completed by executive." }
          });
          showToast("Follow-up marked as completed", "success");
        } else {
          await apiRequest(`/leads/${current.id}/notes`, {
            method: "POST",
            body: { note: "Follow-up completed." }
          });
          showToast("Follow-up completed", "success");
        }
        await refreshLeadsQueue();
        await selectLead(current.id);
      } catch (err) {
        showToast(`Error completing follow-up: ${err.message}`, "error");
      }
    });
  }

  // Book Appointment Modal Open
  const apptBtn = document.getElementById("actionAppointmentBtn");
  if (apptBtn) {
    apptBtn.addEventListener("click", () => {
      const current = getActiveLeadOrFirst();
      if (!current) return showToast("Create or select a patient lead first.", "warning");
      const nextDay = new Date();
      nextDay.setDate(nextDay.getDate() + 2);
      const dInput = document.getElementById("apptDateInput");
      if (dInput) dInput.value = nextDay.toISOString().slice(0, 10);
      document.getElementById("bookAppointmentModal").classList.remove("hidden");
    });
  }

  // Book Appointment Form Submit
  const apptForm = document.getElementById("bookAppointmentForm");
  if (apptForm) {
    apptForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const current = getActiveLeadOrFirst();
      if (!current) return;
      const dVal = document.getElementById("apptDateInput")?.value || new Date().toISOString().slice(0, 10);
      const tVal = document.getElementById("apptTimeInput")?.value || "11:00";
      const appointmentAt = new Date(`${dVal}T${tVal}:00`).toISOString();
      const doctor = document.getElementById("apptDoctorSelect")?.value || "Dr. Soumya Dinesh (Senior IVF Specialist)";
      const notes = document.getElementById("apptNotesInput")?.value || "";

      const payload = {
        lead_id: current.id,
        appointment_at: appointmentAt,
        service_type: "Fertility Consultation",
        notes: `Consulting: ${doctor}. ${notes}`
      };

      try {
        await apiRequest("/appointments", {
          method: "POST",
          body: payload
        });
        showToast("Consultation appointment booked successfully!", "success");
        document.getElementById("bookAppointmentModal").classList.add("hidden");
        apptForm.reset();
        await refreshLeadsQueue();
        await selectLead(current.id);
      } catch (err) {
        showToast(`Failed to book appointment: ${err.message}`, "error");
      }
    });
  }

  // Consultation Outcome Modal Open
  const outcomeBtn = document.getElementById("actionOutcomeBtn");
  if (outcomeBtn) {
    outcomeBtn.addEventListener("click", () => {
      const current = getActiveLeadOrFirst();
      if (!current) return showToast("Create or select a patient lead first.", "warning");
      document.getElementById("consultationOutcomeModal").classList.remove("hidden");
    });
  }

  // Consultation Outcome Form Submit
  const outcomeForm = document.getElementById("consultationOutcomeForm");
  if (outcomeForm) {
    outcomeForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const current = getActiveLeadOrFirst();
      if (!current) return;
      const decision = document.getElementById("outcomeStatusSelect").value;
      const service = document.getElementById("outcomeServiceInput").value;
      const estVal = parseFloat(document.getElementById("outcomeEstimatedValInput").value) || 0;
      const convVal = parseFloat(document.getElementById("outcomeConversionValInput").value) || 0;
      const summary = document.getElementById("outcomeSummaryInput").value;

      try {
        if (decision.includes("Converted") || decision.includes("Booked")) {
          // Record Conversion & Revenue
          await apiRequest("/conversions", {
            method: "POST",
            body: {
              lead_id: current.id,
              converted_service: service,
              conversion_value: convVal,
              notes: summary
            }
          });
          showToast(`Treatment conversion recorded (₹${convVal.toLocaleString()})!`, "success");
        } else {
          // Log outcome via note / status
          await apiRequest(`/leads/${current.id}/notes`, {
            method: "POST",
            body: { note: `Outcome: ${decision}. Summary: ${summary}` }
          });
          showToast("Outcome recorded successfully", "success");
        }
        document.getElementById("consultationOutcomeModal").classList.add("hidden");
        outcomeForm.reset();
        await refreshLeadsQueue();
        await selectLead(current.id);
      } catch (err) {
        showToast(`Failed to record outcome: ${err.message}`, "error");
      }
    });
  }

  // WhatsApp Modal Open
  const waBtn = document.getElementById("actionWhatsappBtn");
  if (waBtn) {
    waBtn.addEventListener("click", () => {
      const current = getActiveLeadOrFirst();
      if (!current) return showToast("Create or select a patient lead first.", "warning");
      const phoneEl = document.getElementById("waRecipientPhone");
      if (phoneEl) phoneEl.value = current.primary_phone || current.normalized_phone;
      updateWhatsAppPreview();
      document.getElementById("whatsappModal").classList.remove("hidden");
    });
  }

  const waSelect = document.getElementById("waTemplateSelect");
  if (waSelect) {
    waSelect.addEventListener("change", () => updateWhatsAppPreview());
  }

  function updateWhatsAppPreview() {
    const current = getActiveLeadOrFirst();
    if (!current) return;
    const tName = document.getElementById("waTemplateSelect").value;
    const bodyEl = document.getElementById("waMessageBody");
    if (!bodyEl) return;

    let text = WA_TEMPLATES[tName] || "";
    text = text.replace("{patient_name}", current.patient_name || "Patient")
               .replace("{branch_name}", current.city || "Hassan")
               .replace("{time}", "Saturday, 11:30 AM")
               .replace("{review_url}", "https://g.page/r/santasa-ivf-review");
    bodyEl.value = text;
  }

  // WhatsApp Form Submit
  const waForm = document.getElementById("whatsappForm");
  if (waForm) {
    waForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const current = getActiveLeadOrFirst();
      if (!current) return;
      const tName = document.getElementById("waTemplateSelect").value;
      const body = document.getElementById("waMessageBody").value;
      const rawPhone = current.primary_phone || current.normalized_phone || "";
      const cleanDigits = rawPhone.replace(/\D/g, "");
      const intlPhone = cleanDigits.length === 10 ? `91${cleanDigits}` : cleanDigits;

      try {
        if (tName === "google_review_request") {
          await apiRequest("/communication/whatsapp/review-request", {
            method: "POST",
            body: { lead_id: current.id }
          });
          showToast("Google Review link logged & opening WhatsApp...", "success");
        } else {
          await apiRequest("/communication/whatsapp/send", {
            method: "POST",
            body: {
              lead_id: current.id,
              template_name: tName !== "custom" ? tName : null,
              custom_body: tName === "custom" ? body : null,
              template_params: { time: "Saturday, 11:30 AM", branch_name: current.city || "Hassan" }
            }
          });
          showToast("WhatsApp message logged & opening chat...", "success");
        }
        document.getElementById("whatsappModal").classList.add("hidden");
        await loadTimeline(current.id);

        // Open Real WhatsApp (App on mobile, Web on desktop)
        if (intlPhone) {
          const waUrl = `https://wa.me/${intlPhone}?text=${encodeURIComponent(body)}`;
          window.open(waUrl, "_blank");
        }
      } catch (err) {
        showToast(`Failed to send WhatsApp: ${err.message}`, "error");
      }
    });
  }

  // Click-to-Call Patient
  const callBtn = document.getElementById("actionCallBtn");
  if (callBtn) {
    callBtn.addEventListener("click", async () => {
      const current = getActiveLeadOrFirst();
      if (!current) return showToast("Create or select a patient lead first.", "warning");
      const phone = current.primary_phone || current.normalized_phone || "";
      const cleanDigits = phone.replace(/\D/g, "");
      const intlPhone = cleanDigits.length === 10 ? `+91${cleanDigits}` : `+${cleanDigits}`;

      // 1. Open live call modal in CRM
      const modal = document.getElementById("liveCallModal");
      const nameEl = document.getElementById("callPatientName");
      const phoneEl = document.getElementById("callPatientPhone");
      if (nameEl) nameEl.textContent = current.patient_name;
      if (phoneEl) phoneEl.textContent = phone;
      modal.classList.remove("hidden");

      // 2. Trigger native device phone dialer (Direct SIM dialing on phone)
      try {
        const dialerLink = document.createElement("a");
        dialerLink.href = `tel:${intlPhone}`;
        dialerLink.style.display = "none";
        document.body.appendChild(dialerLink);
        dialerLink.click();
        setTimeout(() => dialerLink.remove(), 400);
      } catch (e) {
        console.warn("Native dialer trigger:", e);
      }

      // Start timer
      callDurationSec = 0;
      const timerEl = document.getElementById("callTimer");
      clearInterval(callInterval);
      callInterval = setInterval(() => {
        callDurationSec++;
        const mins = String(Math.floor(callDurationSec / 60)).padStart(2, '0');
        const secs = String(callDurationSec % 60).padStart(2, '0');
        if (timerEl) timerEl.textContent = `${mins}:${secs}`;
      }, 1000);

      // Trigger Click-to-call API in backend
      try {
        await apiRequest("/telephony/click-to-call", {
          method: "POST",
          body: {
            lead_id: current.id,
            patient_phone: phone
          }
        });
        document.getElementById("modalCallStatus").textContent = "Call Connected. Conversation in progress...";
      } catch (err) {
        console.warn("Click-to-call direct trigger:", err.message);
      }
    });
  }

  // End Call Button
  const endCallBtn = document.getElementById("endCallBtn");
  if (endCallBtn) {
    endCallBtn.addEventListener("click", async () => {
      clearInterval(callInterval);
      document.getElementById("liveCallModal").classList.add("hidden");
      showToast(`Call ended (${callDurationSec}s). Logged to timeline.`, "info");
      if (activeLead) {
        await loadTimeline(activeLead.id);
      }
    });
  }

  // Reports & Analytics Modal
  const reportsNav = document.getElementById("navReports");
  if (reportsNav) {
    reportsNav.addEventListener("click", async (e) => {
      e.preventDefault();
      const modal = document.getElementById("reportsModal");
      if (modal) modal.classList.remove("hidden");

      try {
        const [funnel, rev] = await Promise.all([
          apiRequest("/reports/funnel"),
          apiRequest("/reports/revenue-summary")
        ]);

        const revEl = document.getElementById("statTotalRevenue");
        const convEl = document.getElementById("statTotalConversions");
        const rateEl = document.getElementById("statConversionRate");

        if (revEl) revEl.textContent = `₹${(rev.total_revenue_inr || 0).toLocaleString()}`;
        if (convEl) convEl.textContent = rev.total_conversions || 0;
        if (rateEl) rateEl.textContent = `${funnel.conversion_rate_percent || 0}%`;

        const stagesEl = document.getElementById("funnelStagesList");
        if (stagesEl) {
          stagesEl.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:6px;">
              <div style="display:flex; justify-content:space-between; padding:6px 10px; background:#f8fafc; border-radius:4px;">
                <span>1. Total Inquiries (Leads)</span>
                <strong>${funnel.total_leads || 0}</strong>
              </div>
              <div style="display:flex; justify-content:space-between; padding:6px 10px; background:#f8fafc; border-radius:4px;">
                <span>2. Follow-ups Contacted</span>
                <strong>${funnel.contacted_leads || 0}</strong>
              </div>
              <div style="display:flex; justify-content:space-between; padding:6px 10px; background:#f8fafc; border-radius:4px;">
                <span>3. Appointments Scheduled</span>
                <strong>${funnel.appointments_scheduled || 0}</strong>
              </div>
              <div style="display:flex; justify-content:space-between; padding:6px 10px; background:#f8fafc; border-radius:4px;">
                <span>4. Consultations Completed</span>
                <strong>${funnel.consultations_completed || 0}</strong>
              </div>
              <div style="display:flex; justify-content:space-between; padding:6px 10px; background:#dcfce7; border-radius:4px; font-weight:700; color:#166534;">
                <span>5. Patient Conversions (Revenue)</span>
                <strong>${funnel.converted || 0} (₹${(rev.total_revenue_inr || 0).toLocaleString()})</strong>
              </div>
            </div>
          `;
        }
      } catch (err) {
        showToast(`Failed to load reports: ${err.message}`, "error");
      }
    });
  }

  // Sidebar Navigation Routing
  document.querySelectorAll(".nav-item:not(#navReports)").forEach(item => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
      item.classList.add("active");
      const view = item.getAttribute("data-view");
      if (view === "today" || view === "leads") {
        currentFilter = "all";
      } else if (view === "due" || view === "overdue") {
        currentFilter = "followup";
      } else if (view === "appointments") {
        currentFilter = "appointment";
      }
      renderLeadsList(liveLeads);
      if (liveLeads.length > 0) {
        const filtered = filterLeads(liveLeads, currentFilter);
        if (filtered.length > 0) {
          selectLead(filtered[0].id);
        }
      }
    });
  });

  // Executive Login Form Submit
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("loginEmailInput").value.trim();
      const password = document.getElementById("loginPasswordInput").value;

      showToast("Signing in to Executive Workspace...", "info");
      const result = await authenticateDefaultExecutive(email, password);
      if (result && result.success) {
        document.getElementById("loginModal").classList.add("hidden");
        showToast(`Signed in as ${currentExecutive?.full_name || 'Executive'}`, "success");
        await refreshLeadsQueue();
      } else {
        showToast((result && result.error) || "Invalid credentials. Please verify your email and password.", "error");
      }
    });
  }

  // Quick Demo Fill buttons
  const fillExecBtn = document.getElementById("fillExecutiveDemoBtn");
  if (fillExecBtn) {
    fillExecBtn.addEventListener("click", () => {
      const emailInput = document.getElementById("loginEmailInput");
      const passInput = document.getElementById("loginPasswordInput");
      if (emailInput) emailInput.value = "executive@santasa.com";
      if (passInput) passInput.value = "Executive@2026!";
    });
  }

  const fillAdminBtn = document.getElementById("fillAdminDemoBtn");
  if (fillAdminBtn) {
    fillAdminBtn.addEventListener("click", () => {
      const emailInput = document.getElementById("loginEmailInput");
      const passInput = document.getElementById("loginPasswordInput");
      if (emailInput) emailInput.value = "admin@santasa.com";
      if (passInput) passInput.value = "Admin@2026!";
    });
  }

  // API Server Configuration Toggle
  const toggleApiBtn = document.getElementById("toggleApiSettingsBtn");
  const apiContainer = document.getElementById("apiSettingsContainer");
  const customApiInput = document.getElementById("customApiUrlInput");
  if (customApiInput) {
    customApiInput.value = localStorage.getItem("crm_api_url") || "";
    customApiInput.addEventListener("change", (e) => {
      const val = e.target.value.trim().replace(/\/+$/, "");
      if (val) {
        localStorage.setItem("crm_api_url", val);
        API_BASE = val;
        showToast(`API Server set to: ${val}`, "info");
      } else {
        localStorage.removeItem("crm_api_url");
        API_BASE = window.VITE_API_URL || "/api/v1";
        showToast("Reset to default API endpoint.", "info");
      }
    });
  }
  if (toggleApiBtn && apiContainer) {
    toggleApiBtn.addEventListener("click", () => {
      apiContainer.style.display = apiContainer.style.display === "none" ? "block" : "none";
    });
  }

  // Executive Status Switcher
  const statusBtn = document.getElementById("agentStatusBtn");
  const statusLabel = document.getElementById("agentStatusLabel");
  const statuses = [
    { label: "Online", dotColor: "#10b981" },
    { label: "In Call", dotColor: "#f59e0b" },
    { label: "On Break", dotColor: "#64748b" },
    { label: "Offline", dotColor: "#dc2626" }
  ];
  let statusIdx = 0;
  if (statusBtn) {
    statusBtn.addEventListener("click", () => {
      statusIdx = (statusIdx + 1) % statuses.length;
      const s = statuses[statusIdx];
      if (statusLabel) statusLabel.textContent = s.label;
      const dot = statusBtn.querySelector(".dot");
      if (dot) dot.style.background = s.dotColor;
      showToast(`Status updated: ${s.label}`, "info");
    });
  }

  // Logout Button
  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      // 1. Show login modal immediately
      const loginModal = document.getElementById("loginModal");
      if (loginModal) loginModal.classList.remove("hidden");

      // 2. Clear state and storage
      localStorage.removeItem("supabase_access_token");
      localStorage.removeItem("supabase_refresh_token");
      localStorage.removeItem("crm_auth_token");
      authToken = null;
      refreshToken = null;
      currentExecutive = null;
      liveLeads = [];
      activeLead = null;
      renderEmptyWorkspace();

      const listContainer = document.getElementById("leadsListContainer");
      if (listContainer) listContainer.innerHTML = `<div class="empty-state">Please sign in to view your patient queue.</div>`;
      const nameEl = document.getElementById("userProfileName");
      const roleEl = document.getElementById("userProfileRole");
      const avatarEl = document.getElementById("userAvatar");
      if (nameEl) nameEl.textContent = "Not Signed In";
      if (roleEl) roleEl.textContent = "Offline";
      if (avatarEl) avatarEl.textContent = "--";

      showToast("Logged out of executive workspace.", "info");

      // 3. Inform backend
      try {
        await apiRequest("/auth/logout", { method: "POST" });
      } catch (e) {
        console.warn("Logout notice:", e);
      }
    });
  }
}

function filterLeads(leads, filter) {
  if (filter === "new") return leads.filter(l => l.lead_status === "New");
  if (filter === "followup") return leads.filter(l => l.lead_status === "Follow-up");
  if (filter === "appointment") return leads.filter(l => l.lead_status === "Appointment Booked");
  return leads;
}

// -------------------------------------------------------------
// Helpers & Toasts
// -------------------------------------------------------------
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function getStatusClass(status) {
  if (!status) return "status-new";
  const s = status.toLowerCase();
  if (s.includes("new")) return "status-new";
  if (s.includes("follow")) return "status-followup";
  if (s.includes("appoint")) return "status-appointment";
  if (s.includes("convert") || s.includes("treat")) return "status-converted";
  if (s.includes("lost") || s.includes("drop")) return "status-lost";
  return "status-followup";
}

function getPriorityClass(priority) {
  if (!priority) return "priority-medium";
  const p = priority.toLowerCase();
  if (p.includes("high") || p.includes("urgent")) return "priority-high";
  if (p.includes("low")) return "priority-low";
  return "priority-medium";
}

function getActivityIconSvg(type) {
  const t = (type || "").toLowerCase();
  if (t.includes("call")) {
    return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>`;
  }
  if (t.includes("whatsapp")) {
    return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>`;
  }
  if (t.includes("note")) {
    return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`;
  }
  if (t.includes("appoint")) {
    return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/><line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/></svg>`;
  }
  if (t.includes("follow")) {
    return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`;
  }
  if (t.includes("convert") || t.includes("treat")) {
    return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`;
  }
  return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// Global Keyboard Shortcut: Alt + / or Ctrl + K for quick search
window.addEventListener("keydown", (e) => {
  if ((e.altKey && e.key === "/") || ((e.ctrlKey || e.metaKey) && e.key === "k")) {
    e.preventDefault();
    const searchInput = document.getElementById("globalSearchInput");
    if (searchInput) {
      searchInput.focus();
      searchInput.select();
    }
  }
});
