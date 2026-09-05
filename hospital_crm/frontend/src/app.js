/**
 * Santasa IVF & Hospital CRM — Live Executive Workspace Controller (v3.0.0)
 * Fully dynamic: Directly integrated with FastAPI & Supabase PostgreSQL & Audio Storage
 * Brand Theme: Royal Purple (#683381), Rose Pink (#EC5A8D), Turquoise (#40BDB3)
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
let snoozedReminders = new Set();
let lastAlertedLeadId = null;

// Audio Chime Synthesizer using Web Audio API (Zero external files needed)
function playReminderChime() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    
    osc.type = "sine";
    osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5 tone
    osc.frequency.setValueAtTime(880, ctx.currentTime + 0.15); // A5 tone
    
    gain.gain.setValueAtTime(0.12, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);
    
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.6);
  } catch (e) {
    console.debug("Audio chime note:", e);
  }
}

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
      const refreshed = await refreshSupabaseSession();
      if (refreshed) {
        options.headers["Authorization"] = `Bearer ${authToken}`;
        res = await fetch(`${API_BASE}${endpoint}`, options);
      } else {
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
  const password = customPassword || (email.includes("admin") ? "Admin@2026!" : "Executive@2026!");

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
        showToast(`Welcome to Santasa CRM, ${user.full_name || 'Executive'}!`, "success");
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

  const loginModal = document.getElementById("loginModal");
  if (loginModal) loginModal.classList.remove("hidden");

  // Real-Time 5-second Live Sync & Auto-Reminder Checker
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
          checkExecutiveDueReminders(liveLeads);
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

  const displayName = user.full_name || (user.role === "Super Admin" ? "Admin" : "CRM Executive");
  if (nameEl) nameEl.textContent = displayName;
  if (roleEl) roleEl.textContent = `${user.role || 'Executive'} • Online`;
  if (avatarEl) {
    const initials = displayName.split(" ").map(n => n[0]).join("").substring(0, 2).toUpperCase() || "EX";
    avatarEl.textContent = initials;
  }
}

// -------------------------------------------------------------
// Automatic Executive Callback Reminder System
// -------------------------------------------------------------
function checkExecutiveDueReminders(leads) {
  const now = new Date();
  const alertThreshold = new Date(now.getTime() + 15 * 60 * 1000); // due now or within next 15 mins

  const dueLead = leads.find(l => {
    if (snoozedReminders.has(l.id)) return false;
    if (l.lead_status === "Converted (Under Treatment)" || l.lead_status === "Not Interested / Lost") return false;
    if (!l.next_followup_at) return false;
    const fuDate = new Date(l.next_followup_at);
    return fuDate <= alertThreshold;
  });

  const banner = document.getElementById("executiveReminderBanner");
  if (!banner) return;

  if (dueLead) {
    const pName = document.getElementById("reminderPatientText");
    const pNote = document.getElementById("reminderNoteText");
    const pTime = document.getElementById("reminderDueTime");

    const fuDate = new Date(dueLead.next_followup_at);
    const diffMins = Math.round((fuDate - now) / (60 * 1000));
    const timeLabel = diffMins <= 0 ? "Due Now (Overdue)" : `Due in ${diffMins} min`;

    if (pName) pName.textContent = `Patient: ${dueLead.patient_name} (${dueLead.primary_phone || ''})`;
    if (pNote) pNote.textContent = dueLead.notes || "Follow-up callback required with patient.";
    if (pTime) pTime.textContent = timeLabel;

    banner.classList.remove("hidden");

    // Play synthesized audio chime only on fresh alert
    if (lastAlertedLeadId !== dueLead.id) {
      lastAlertedLeadId = dueLead.id;
      playReminderChime();
    }

    // Connect Quick Action Buttons on Reminder
    const callBtn = document.getElementById("reminderCallNowBtn");
    const waBtn = document.getElementById("reminderWhatsappBtn");
    const snoozeBtn = document.getElementById("reminderSnoozeBtn");
    const dismissBtn = document.getElementById("reminderDismissBtn");

    if (callBtn) {
      callBtn.onclick = () => {
        selectLead(dueLead.id);
        const actionCallBtn = document.getElementById("actionCallBtn");
        if (actionCallBtn) actionCallBtn.click();
        banner.classList.add("hidden");
      };
    }

    if (waBtn) {
      waBtn.onclick = () => {
        selectLead(dueLead.id);
        const actionWhatsappBtn = document.getElementById("actionWhatsappBtn");
        if (actionWhatsappBtn) actionWhatsappBtn.click();
        banner.classList.add("hidden");
      };
    }

    if (snoozeBtn) {
      snoozeBtn.onclick = () => {
        snoozedReminders.add(dueLead.id);
        banner.classList.add("hidden");
        showToast(`Reminder for ${dueLead.patient_name} snoozed for 15m.`, "info");
        setTimeout(() => {
          snoozedReminders.delete(dueLead.id);
        }, 15 * 60 * 1000);
      };
    }

    if (dismissBtn) {
      dismissBtn.onclick = () => {
        snoozedReminders.add(dueLead.id);
        banner.classList.add("hidden");
      };
    }
  } else {
    banner.classList.add("hidden");
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
    checkExecutiveDueReminders(liveLeads);

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
  const newCount = leads.filter(l => l.lead_status === "New" || !l.lead_status).length;
  const fuCount = leads.filter(l => l.lead_status === "Follow-up" || l.lead_status === "Follow-up Needed").length;
  const apptCount = leads.filter(l => l.lead_status === "Appointment Booked" || l.lead_status === "Appointment Scheduled").length;

  const now = new Date();
  const dueRemindersCount = leads.filter(l => {
    if (!l.next_followup_at) return false;
    return new Date(l.next_followup_at) <= new Date(now.getTime() + 60 * 60 * 1000);
  }).length;

  const countToday = document.getElementById("countTodayBadge");
  const countReminders = document.getElementById("countRemindersBadge");
  const countDue = document.getElementById("countDueBadge");
  const countAppts = document.getElementById("countApptsBadge");
  const countAll = document.getElementById("countAllLeads");

  if (countToday) countToday.textContent = allCount;
  if (countReminders) countReminders.textContent = dueRemindersCount;
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

  const now = new Date();
  let filtered = leads;
  if (currentFilter === "new") {
    filtered = leads.filter(l => l.lead_status === "New" || !l.lead_status);
  } else if (currentFilter === "followup" || currentFilter === "due") {
    filtered = leads.filter(l => l.lead_status === "Follow-up" || l.lead_status === "Follow-up Needed");
  } else if (currentFilter === "appointment" || currentFilter === "appointments") {
    filtered = leads.filter(l => l.lead_status === "Appointment Booked" || l.lead_status === "Appointment Scheduled");
  } else if (currentFilter === "converted") {
    filtered = leads.filter(l => (l.lead_status || '').toLowerCase().includes("convert") || (l.lead_status || '').toLowerCase().includes("treatment"));
  } else if (currentFilter === "reminders") {
    filtered = leads.filter(l => {
      if (!l.next_followup_at) return false;
      return new Date(l.next_followup_at) <= new Date(now.getTime() + 60 * 60 * 1000);
    });
  }

  if (filtered.length === 0) {
    container.innerHTML = `<div class="empty-state">No patient leads in this queue. Click <strong>+ New Lead</strong> to create one.</div>`;
    return;
  }

  container.innerHTML = filtered.map(lead => {
    const isSelected = activeLead && activeLead.id === lead.id ? "active selected" : "";
    const statusClass = getStatusClass(lead.lead_status);
    const priorityClass = getPriorityClass(lead.priority);
    const timeFormatted = lead.created_at ? new Date(lead.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "";

    const isCallbackDue = lead.next_followup_at && new Date(lead.next_followup_at) <= new Date(now.getTime() + 15 * 60 * 1000);
    const callbackDueHtml = isCallbackDue ? `<span class="reminder-due-tag">⏰ Callback Due</span>` : "";
    const cardClass = isCallbackDue ? "callback-due-card" : "";
    const initials = (lead.patient_name || 'PT').split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() || 'PT';

    return `
      <div class="lead-card ${isSelected} ${cardClass}" data-lead-id="${lead.id}">
        <div class="card-avatar-row">
          <div class="card-avatar">${initials}</div>
          <div class="card-info-col">
            <div class="card-top-row">
              <span class="card-patient-name">${escapeHtml(lead.patient_name)}</span>
              <span class="status-pill ${statusClass}">${escapeHtml(lead.lead_status || 'New')}</span>
            </div>
            <div class="card-meta-row">
              <span class="card-phone">${escapeHtml(lead.primary_phone || lead.normalized_phone || '')}</span>
              <span class="card-source-dot">•</span>
              <span>${escapeHtml(lead.city || 'Hassan')}</span>
            </div>
          </div>
        </div>
        <div class="card-badges-row">
          <span class="priority-pill ${priorityClass}">${escapeHtml(lead.priority || 'High')}</span>
          ${callbackDueHtml}
          <span class="timeline-time" style="margin-left: auto;">${timeFormatted}</span>
        </div>
      </div>
    `;
  }).join("");

  // Attach card click listeners & mobile switch
  container.querySelectorAll(".lead-card").forEach(card => {
    card.addEventListener("click", () => {
      const id = card.getAttribute("data-lead-id");
      selectLead(id);

      // On mobile devices, open detail panel
      if (window.innerWidth <= 768) {
        const detailPanel = document.getElementById("leadDetailPanel");
        if (detailPanel) detailPanel.classList.add("mobile-active");
      }
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
    await loadTimeline(leadId);
  } catch (err) {
    console.warn("Error refreshing lead details:", err);
  }
}

function renderActiveLead(lead) {
  if (!lead) return;

  const nameEl = document.getElementById("detailPatientName");
  const phoneEl = document.getElementById("detailPhone");
  const priorityEl = document.getElementById("detailPriority");
  const locationEl = document.getElementById("detailLocation");
  const sourceEl = document.getElementById("detailSource");
  const deptEl = document.getElementById("detailDept");
  const stageSelect = document.getElementById("detailStageSelect");

  if (nameEl) nameEl.textContent = lead.patient_name || "Unknown Patient";
  if (phoneEl) phoneEl.textContent = lead.primary_phone || lead.normalized_phone || "--";
  if (priorityEl) {
    priorityEl.textContent = `${lead.priority || 'High'} Priority`;
    priorityEl.className = `priority-pill ${getPriorityClass(lead.priority)}`;
  }
  if (locationEl) locationEl.textContent = `${lead.city || 'Hassan'}, Karnataka`;
  if (sourceEl) sourceEl.textContent = lead.lead_source || "Mobile Sync";
  if (deptEl) deptEl.textContent = lead.department || "Fertility & IVF";

  if (stageSelect) {
    const st = lead.lead_status || "Valid - Need Appointment";
    stageSelect.value = st;
    // Fallback if not exact match
    if (!stageSelect.value) {
      const match = Array.from(stageSelect.options).find(o => o.value.toLowerCase().includes(st.toLowerCase()));
      if (match) stageSelect.value = match.value;
    }
  }

  // General Information fields
  const pName = document.getElementById("profileName");
  const pPhone = document.getElementById("profilePhone");
  const pRegPhone = document.getElementById("profileRegPhone");
  const pPatientType = document.getElementById("profilePatientType");
  const pPatientId = document.getElementById("profilePatientId");
  const pEmail = document.getElementById("profileEmail");
  const pAgeGen = document.getElementById("profileAgeGender");
  const pCity = document.getElementById("profileCity");

  if (pName) pName.textContent = lead.patient_name || "--";
  if (pPhone) pPhone.textContent = lead.primary_phone || lead.normalized_phone || "--";
  if (pRegPhone) pRegPhone.textContent = lead.registered_number || "--";
  if (pPatientType) pPatientType.textContent = lead.patient_type || "Enquiry";
  if (pPatientId) pPatientId.textContent = lead.patient_id_mrn || "--";
  if (pEmail) pEmail.textContent = lead.email || "--";
  if (pAgeGen) pAgeGen.textContent = `${lead.age ? lead.age + ' yrs' : 'Age: --'}, ${lead.gender || 'Female'}`;
  if (pCity) pCity.textContent = lead.city || "Hassan";

  // Clinical & Surgery details
  const pTreatment = document.getElementById("profileTreatment");
  const pDept = document.getElementById("profileDept");
  const pConsultDate = document.getElementById("profileConsultDate");
  const pSurgeryDate = document.getElementById("profileSurgeryDate");
  const pSurgeryDetails = document.getElementById("profileSurgeryDetails");
  const pMessage = document.getElementById("profileMessage");

  if (pTreatment) pTreatment.textContent = lead.treatment || lead.service_interested || "Fertility & IVF";
  if (pDept) pDept.textContent = lead.department || "Fertility & IVF";
  if (pConsultDate) pConsultDate.textContent = lead.consultation_date ? new Date(lead.consultation_date).toLocaleDateString([], { dateStyle: 'medium' }) : "--";
  if (pSurgeryDate) pSurgeryDate.textContent = lead.surgery_date ? new Date(lead.surgery_date).toLocaleDateString([], { dateStyle: 'medium' }) : "--";
  if (pSurgeryDetails) {
    const req = lead.surgery_requirement ? `[Req: ${lead.surgery_requirement}] ` : '';
    pSurgeryDetails.textContent = req + (lead.surgery_details || "None required");
  }
  if (pMessage) pMessage.textContent = lead.message || "--";

  // Call & Assignment details
  const pSource = document.getElementById("profileSource");
  const pDestNumber = document.getElementById("profileDestNumber");
  const pFollowup = document.getElementById("profileFollowup");
  const pExec = document.getElementById("profileExecutive");
  const pNotes = document.getElementById("profileNotes");

  if (pSource) pSource.textContent = lead.lead_source || "Mobile Call Direct";
  if (pDestNumber) pDestNumber.textContent = lead.destination_number || "--";
  if (pFollowup) {
    pFollowup.textContent = lead.next_followup_at ? new Date(lead.next_followup_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : "None scheduled";
  }
  if (pExec) pExec.textContent = (currentExecutive && currentExecutive.full_name) || "Assigned Executive";
  if (pNotes) pNotes.textContent = lead.notes || "No clinical remarks recorded.";
}

function renderEmptyWorkspace() {
  const nameEl = document.getElementById("detailPatientName");
  if (nameEl) nameEl.textContent = "Select a Patient";
  const feed = document.getElementById("timelineFeed");
  if (feed) feed.innerHTML = `<div class="empty-state">Select a patient from the queue to start clinical counseling.</div>`;
}

// -------------------------------------------------------------
// Timeline & Activity Feed Loading with Direct Audio Streaming
// -------------------------------------------------------------
async function loadTimeline(leadId) {
  const feed = document.getElementById("timelineFeed");
  if (!feed) return;

  feed.innerHTML = `<div class="empty-state">Loading timeline...</div>`;

  try {
    const activities = await apiRequest(`/leads/${leadId}/timeline?limit=50`);
    if (!activities || activities.length === 0) {
      feed.innerHTML = `<div class="empty-state">No activities recorded yet for this patient. Click an action button above or add a note.</div>`;
      return;
    }

    feed.innerHTML = activities.map(act => {
      const type = (act.activity_type || "note").toLowerCase();
      const iconSvg = getActivityIconSvg(type);
      const timeFormatted = act.created_at ? new Date(act.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : "";
      const meta = act.activity_metadata || act.metadata || {};

      let audioPlayerHtml = "";
      if (meta.recording_url) {
        let streamUrl = meta.recording_url;
        if (!streamUrl.startsWith("http")) {
          const baseHost = API_BASE.includes("http") ? new URL(API_BASE).origin : "https://santasa-crm.onrender.com";
          streamUrl = `${baseHost}${streamUrl}`;
        }
        audioPlayerHtml = `
          <div class="audio-player-container">
            <div class="audio-controls-row">
              <audio controls src="${streamUrl}" preload="metadata" class="native-audio-element">
                Audio playback not supported.
              </audio>
              <a href="${streamUrl}" target="_blank" download class="btn-download-audio" title="Download Audio File">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              </a>
            </div>
            <div class="audio-meta-row">
              <span class="audio-badge">Recorded Call (${meta.duration || 0}s)</span>
              <span class="audio-hint">Click ▶️ Play to listen</span>
            </div>
          </div>
        `;
      }

      let iconBoxClass = "note";
      if (type.includes("call")) iconBoxClass = "call";
      else if (type.includes("whatsapp")) iconBoxClass = "whatsapp";
      else if (type.includes("appoint")) iconBoxClass = "appointment";
      else if (type.includes("follow")) iconBoxClass = "followup";
      else if (type.includes("conversion")) iconBoxClass = "conversion";

      return `
        <div class="timeline-item">
          <div class="timeline-icon-box ${iconBoxClass}">
            ${iconSvg}
          </div>
          <div class="timeline-card">
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

// -------------------------------------------------------------
// Interactive Action Handlers & Event Setup
// -------------------------------------------------------------
function setupEventHandlers() {
  // Direct Patient Stage Selector
  const stageSelect = document.getElementById("detailStageSelect");
  if (stageSelect) {
    stageSelect.addEventListener("change", async (e) => {
      if (!activeLead) return;
      const newStage = e.target.value;
      showToast(`Updating stage to: ${newStage}...`, "info");
      try {
        await apiRequest(`/leads/${activeLead.id}`, {
          method: "PATCH",
          body: { lead_status: newStage }
        });
        activeLead.lead_status = newStage;
        const inList = liveLeads.find(l => l.id === activeLead.id);
        if (inList) inList.lead_status = newStage;
        renderLeadsList(liveLeads);
        updateBadges(liveLeads);
        showToast(`Lead stage updated to: ${newStage}`, "success");
        await loadTimeline(activeLead.id);
      } catch (err) {
        showToast(`Failed to update stage: ${err.message}`, "error");
      }
    });
  }

  // Quick Clinical Note Composer
  const quickNoteInput = document.getElementById("quickTimelineNoteInput");
  const quickNoteBtn = document.getElementById("quickTimelineNoteBtn");
  const handlePostQuickNote = async () => {
    if (!activeLead || !quickNoteInput) return;
    const noteText = quickNoteInput.value.trim();
    if (!noteText) {
      showToast("Please enter a clinical note first.", "error");
      return;
    }
    showToast("Saving clinical note...", "info");
    try {
      await apiRequest(`/leads/${activeLead.id}/notes`, {
        method: "POST",
        body: { notes: noteText }
      });
      quickNoteInput.value = "";
      showToast("Clinical note recorded!", "success");
      await loadTimeline(activeLead.id);
    } catch (err) {
      showToast(`Failed to save note: ${err.message}`, "error");
    }
  };

  if (quickNoteBtn) quickNoteBtn.addEventListener("click", handlePostQuickNote);
  if (quickNoteInput) {
    quickNoteInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handlePostQuickNote();
    });
  }

  // Mobile Hamburger Toggle
  const mobileToggle = document.getElementById("mobileMenuToggle");
  const sidebar = document.getElementById("mainSidebar");
  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener("click", () => {
      sidebar.classList.toggle("open");
    });
  }

  // Mobile Back Button to Leads Queue
  const backToLeadsBtn = document.getElementById("mobileBackToLeadsBtn");
  const detailPanel = document.getElementById("leadDetailPanel");
  if (backToLeadsBtn && detailPanel) {
    backToLeadsBtn.addEventListener("click", () => {
      detailPanel.classList.remove("mobile-active");
    });
  }

  // Refresh Queue Button
  const refreshBtn = document.getElementById("refreshQueueBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      showToast("Syncing with Supabase...", "info");
      await refreshLeadsQueue();
      showToast("Leads refreshed!", "success");
    });
  }

  // Filter Chips Click
  document.querySelectorAll(".filter-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      currentFilter = chip.getAttribute("data-filter");
      renderLeadsList(liveLeads);
    });
  });

  // Modal Closers
  document.querySelectorAll("[data-close]").forEach(btn => {
    btn.addEventListener("click", () => {
      const modalId = btn.getAttribute("data-close");
      const el = document.getElementById(modalId);
      if (el) el.classList.add("hidden");
    });
  });

  // New Lead Modal Open
  const newLeadBtn = document.getElementById("newLeadBtn");
  if (newLeadBtn) {
    newLeadBtn.addEventListener("click", () => {
      const inqDateInput = document.getElementById("inputInquiryDate");
      if (inqDateInput) {
        const now = new Date();
        now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
        inqDateInput.value = now.toISOString().slice(0, 16);
      }
      document.getElementById("newLeadModal").classList.remove("hidden");
    });
  }

  // New Lead Form Submit (Comprehensive Hospital Fields)
  const newLeadForm = document.getElementById("newLeadForm");
  if (newLeadForm) {
    newLeadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("inputPatientName")?.value.trim();
      const phone = document.getElementById("inputPrimaryPhone")?.value.trim();
      const regPhone = document.getElementById("inputRegisteredPhone")?.value.trim() || null;
      const email = document.getElementById("inputEmail")?.value.trim() || null;
      const patientType = document.getElementById("inputPatientType")?.value || "Enquiry";
      const patientId = document.getElementById("inputPatientId")?.value.trim() || null;
      const treatment = document.getElementById("inputTreatment")?.value.trim() || null;
      const message = document.getElementById("inputMessage")?.value.trim() || null;

      const source = document.getElementById("inputLeadSource")?.value || "Mobile Call Direct";
      const leadStatus = document.getElementById("inputLeadStatus")?.value || "Valid - Need Appointment";
      const city = document.getElementById("inputCity")?.value.trim() || "Hassan";
      const prio = document.getElementById("inputPriority")?.value || "High";

      const consultDateVal = document.getElementById("inputConsultationDate")?.value;
      const surgeryDateVal = document.getElementById("inputSurgeryDate")?.value;
      const surgeryReq = document.getElementById("inputSurgeryRequirement")?.value.trim() || null;
      const surgeryDetails = document.getElementById("inputSurgeryDetails")?.value.trim() || null;
      const destNumber = document.getElementById("inputDestNumber")?.value.trim() || null;
      const notes = document.getElementById("inputNotes")?.value.trim() || null;

      try {
        const lead = await apiRequest("/leads", {
          method: "POST",
          body: {
            patient_name: name,
            primary_phone: phone,
            registered_number: regPhone,
            email: email,
            patient_type: patientType,
            patient_id_mrn: patientId,
            treatment: treatment,
            message: message,
            lead_source: source,
            lead_status: leadStatus,
            city: city,
            department: "Fertility & IVF",
            priority: prio,
            consultation_date: consultDateVal ? new Date(consultDateVal).toISOString() : null,
            surgery_date: surgeryDateVal ? new Date(surgeryDateVal).toISOString() : null,
            surgery_requirement: surgeryReq,
            surgery_details: surgeryDetails,
            destination_number: destNumber,
            notes: notes || "Direct SSM / Hospital Reference Entry"
          }
        });
        showToast("Patient lead created successfully!", "success");
        document.getElementById("newLeadModal").classList.add("hidden");
        newLeadForm.reset();
        await refreshLeadsQueue();
        if (lead && lead.id) selectLead(lead.id);
      } catch (err) {
        showToast(`Failed to create lead: ${err.message}`, "error");
      }
    });
  }

  // Call Patient Action Button
  const callBtn = document.getElementById("actionCallBtn");
  if (callBtn) {
    callBtn.addEventListener("click", () => {
      if (!activeLead) {
        showToast("Please select a patient first.", "error");
        return;
      }
      const callModal = document.getElementById("liveCallModal");
      document.getElementById("callPatientName").textContent = `Calling ${activeLead.patient_name}...`;
      document.getElementById("callPatientPhone").textContent = activeLead.primary_phone || activeLead.normalized_phone || "--";
      callModal.classList.remove("hidden");

      callDurationSec = 0;
      const timerEl = document.getElementById("callTimer");
      timerEl.textContent = "00:00";
      clearInterval(callInterval);
      callInterval = setInterval(() => {
        callDurationSec++;
        const mins = String(Math.floor(callDurationSec / 60)).padStart(2, '0');
        const secs = String(callDurationSec % 60).padStart(2, '0');
        timerEl.textContent = `${mins}:${secs}`;
      }, 1000);
    });
  }

  // End Call Button
  const endCallBtn = document.getElementById("endCallBtn");
  if (endCallBtn) {
    endCallBtn.addEventListener("click", async () => {
      clearInterval(callInterval);
      document.getElementById("liveCallModal").classList.add("hidden");
      if (!activeLead) return;

      showToast(`Call ended (${callDurationSec}s). Logging to timeline...`, "info");
      try {
        await apiRequest("/telephony/mobile-sync/call-log", {
          method: "POST",
          body: {
            phone_number: activeLead.primary_phone || activeLead.normalized_phone,
            direction: "Outgoing",
            duration_seconds: callDurationSec,
            notes: "Outgoing Clinical Call from Web Workspace"
          }
        });
        showToast("Call logged to patient timeline!", "success");
        await loadTimeline(activeLead.id);
      } catch (err) {
        showToast(`Call sync note: ${err.message}`, "info");
      }
    });
  }

  // WhatsApp Action Button
  const waBtn = document.getElementById("actionWhatsappBtn");
  if (waBtn) {
    waBtn.addEventListener("click", () => {
      if (!activeLead) {
        showToast("Please select a patient first.", "error");
        return;
      }
      const phone = (activeLead.primary_phone || activeLead.normalized_phone || "").replace(/[^0-9]/g, "");
      const msg = encodeURIComponent(`Hello ${activeLead.patient_name}, greetings from Santasa IVF & Hospital. We are reaching out regarding your fertility inquiry.`);
      window.open(`https://wa.me/${phone}?text=${msg}`, "_blank");
      showToast("Opened WhatsApp Web!", "success");
    });
  }

  // Schedule Follow-up Modal
  const followupBtn = document.getElementById("actionFollowupBtn");
  if (followupBtn) {
    followupBtn.addEventListener("click", () => {
      if (!activeLead) {
        showToast("Please select a patient first.", "error");
        return;
      }
      document.getElementById("followupModal").classList.remove("hidden");
    });
  }

  const followupForm = document.getElementById("followupForm");
  if (followupForm) {
    followupForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!activeLead) return;
      const dateVal = document.getElementById("inputFollowupDate").value;
      const noteVal = document.getElementById("inputFollowupNote").value.trim();

      try {
        await apiRequest(`/leads/${activeLead.id}/followups`, {
          method: "POST",
          body: {
            scheduled_at: new Date(dateVal).toISOString(),
            notes: noteVal
          }
        });
        showToast("Callback reminder scheduled!", "success");
        document.getElementById("followupModal").classList.add("hidden");
        followupForm.reset();
        await refreshLeadsQueue();
        await loadTimeline(activeLead.id);
      } catch (err) {
        showToast(`Failed to schedule reminder: ${err.message}`, "error");
      }
    });
  }

  // Book Appointment Modal
  const apptBtn = document.getElementById("actionApptBtn");
  if (apptBtn) {
    apptBtn.addEventListener("click", () => {
      if (!activeLead) {
        showToast("Please select a patient first.", "error");
        return;
      }
      document.getElementById("apptModal").classList.remove("hidden");
    });
  }

  const apptForm = document.getElementById("apptForm");
  if (apptForm) {
    apptForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!activeLead) return;
      const doctor = document.getElementById("inputDoctor").value;
      const branch = document.getElementById("inputApptBranch").value;
      const dateVal = document.getElementById("inputApptDate").value;
      const type = document.getElementById("inputApptType").value;

      try {
        await apiRequest("/appointments", {
          method: "POST",
          body: {
            lead_id: activeLead.id,
            doctor_name: doctor,
            branch_name: branch,
            appointment_date: new Date(dateVal).toISOString(),
            appointment_type: type
          }
        });
        showToast("Appointment confirmed with Dr. Soumya!", "success");
        document.getElementById("apptModal").classList.add("hidden");
        apptForm.reset();
        await refreshLeadsQueue();
        await loadTimeline(activeLead.id);
      } catch (err) {
        showToast(`Failed to book appointment: ${err.message}`, "error");
      }
    });
  }

  // Add Note Modal
  const noteBtn = document.getElementById("actionNoteBtn");
  if (noteBtn) {
    noteBtn.addEventListener("click", () => {
      if (!activeLead) {
        showToast("Please select a patient first.", "error");
        return;
      }
      document.getElementById("noteModal").classList.remove("hidden");
    });
  }

  const noteForm = document.getElementById("noteForm");
  if (noteForm) {
    noteForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!activeLead) return;
      const text = document.getElementById("inputNoteText").value.trim();

      try {
        await apiRequest(`/leads/${activeLead.id}/notes`, {
          method: "POST",
          body: { notes: text }
        });
        showToast("Clinical note recorded!", "success");
        document.getElementById("noteModal").classList.add("hidden");
        noteForm.reset();
        await loadTimeline(activeLead.id);
      } catch (err) {
        showToast(`Failed to save note: ${err.message}`, "error");
      }
    });
  }

  // Outcome / Funnel Stage Modal
  const outcomeBtn = document.getElementById("actionOutcomeBtn");
  if (outcomeBtn) {
    outcomeBtn.addEventListener("click", () => {
      if (!activeLead) {
        showToast("Please select a patient first.", "error");
        return;
      }
      document.getElementById("outcomeModal").classList.remove("hidden");
    });
  }

  const outcomeForm = document.getElementById("outcomeForm");
  if (outcomeForm) {
    outcomeForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!activeLead) return;
      const statusVal = document.getElementById("inputOutcomeStatus").value;
      const revenueVal = parseFloat(document.getElementById("inputRevenue").value || "0");
      const notesVal = document.getElementById("inputOutcomeNotes").value.trim();

      try {
        await apiRequest(`/leads/${activeLead.id}/outcome`, {
          method: "POST",
          body: {
            lead_status: statusVal,
            revenue: revenueVal,
            remarks: notesVal
          }
        });
        showToast("Lead outcome recorded!", "success");
        document.getElementById("outcomeModal").classList.add("hidden");
        outcomeForm.reset();
        await refreshLeadsQueue();
        await loadTimeline(activeLead.id);
      } catch (err) {
        showToast(`Failed to record outcome: ${err.message}`, "error");
      }
    });
  }

  // Reports / Analytics Modal
  const reportsNav = document.getElementById("navReports");
  if (reportsNav) {
    reportsNav.addEventListener("click", async (e) => {
      e.preventDefault();
      document.getElementById("reportsModal").classList.remove("hidden");

      try {
        const stats = await apiRequest("/reports/conversions");
        if (stats) {
          document.getElementById("statTotalRevenue").textContent = `₹${(stats.total_revenue || 0).toLocaleString('en-IN')}`;
          document.getElementById("statTotalConversions").textContent = stats.converted_count || 0;
          document.getElementById("statConversionRate").textContent = `${stats.conversion_rate || 0}%`;

          const funnelList = document.getElementById("funnelStagesList");
          funnelList.innerHTML = `
            <div style="background:#f8f6fa; padding:10px; border-radius:8px; border-left:4px solid var(--brand-purple);">
              <strong>Inquiries Logged:</strong> ${liveLeads.length} leads
            </div>
            <div style="background:#f8f6fa; padding:10px; border-radius:8px; border-left:4px solid var(--brand-teal);">
              <strong>Appointments Scheduled:</strong> ${liveLeads.filter(l => (l.lead_status || '').includes('App')).length} patients
            </div>
            <div style="background:#f8f6fa; padding:10px; border-radius:8px; border-left:4px solid var(--brand-pink);">
              <strong>Completed IVF Cycles:</strong> ${stats.converted_count || 0} treatments
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

      // Close mobile sidebar on navigation
      if (window.innerWidth <= 768) {
        const sidebar = document.getElementById("mainSidebar");
        if (sidebar) sidebar.classList.remove("open");
      }

      if (view === "today" || view === "all-leads") {
        currentFilter = "all";
      } else if (view === "reminders") {
        currentFilter = "reminders";
      } else if (view === "followups" || view === "overdue") {
        currentFilter = "followup";
      } else if (view === "appointments") {
        currentFilter = "appointment";
      }
      renderLeadsList(liveLeads);
      if (liveLeads.length > 0) {
        selectLead(liveLeads[0].id);
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

  // Demo Fill buttons
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
        API_BASE = "https://santasa-crm.onrender.com/api/v1";
        showToast("Reset to default API endpoint.", "info");
      }
    });
  }
  if (toggleApiBtn && apiContainer) {
    toggleApiBtn.addEventListener("click", () => {
      apiContainer.style.display = apiContainer.style.display === "none" ? "block" : "none";
    });
  }

  // Agent Status Switcher
  const statusBtn = document.getElementById("agentStatusBtn");
  const statusLabel = document.getElementById("agentStatusLabel");
  const statuses = [
    { label: "Online", dotColor: "#40bdb3" },
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
      const loginModal = document.getElementById("loginModal");
      if (loginModal) loginModal.classList.remove("hidden");

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

      showToast("Logged out of workspace.", "info");
    });
  }

  // Global Search
  const searchInput = document.getElementById("globalSearchInput");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const query = e.target.value.toLowerCase().trim();
      if (!query) {
        renderLeadsList(liveLeads);
        return;
      }
      const matched = liveLeads.filter(l => 
        (l.patient_name && l.patient_name.toLowerCase().includes(query)) ||
        (l.primary_phone && l.primary_phone.includes(query)) ||
        (l.normalized_phone && l.normalized_phone.includes(query)) ||
        (l.city && l.city.toLowerCase().includes(query))
      );
      renderLeadsList(matched);
    });
  }
}

// -------------------------------------------------------------
// Helper UI Utilities
// -------------------------------------------------------------
function getStatusClass(status) {
  if (!status) return "status-new";
  const s = status.toLowerCase();
  if (s.includes("new")) return "status-new";
  if (s.includes("follow")) return "status-followup";
  if (s.includes("app")) return "status-appointment";
  if (s.includes("convert")) return "status-converted";
  if (s.includes("lost") || s.includes("not")) return "status-lost";
  return "status-new";
}

function getPriorityClass(prio) {
  if (!prio) return "priority-medium";
  const p = prio.toLowerCase();
  if (p.includes("high")) return "priority-high";
  if (p.includes("low")) return "priority-low";
  return "priority-medium";
}

function getActivityIconSvg(type) {
  if (type.includes("call")) {
    return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>`;
  } else if (type.includes("whatsapp")) {
    return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>`;
  } else if (type.includes("appoint")) {
    return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
  } else if (type.includes("follow")) {
    return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`;
  }
  return `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(-10px)";
    toast.style.transition = "all 200ms ease";
    setTimeout(() => toast.remove(), 200);
  }, 3500);
}
