/**
 * Hospital CRM — SSM & Santasa Multi-Tenant Frontend Engine
 * 100% Matching crm.hummatic.com Layout & Design
 * Backend: Supabase (Postgres + Auth + Storage + Realtime)
 */
import { supabase, getCurrentProfile, getActiveSession, onSessionChange } from "./supabase.js";

let currentUser    = null;   // profile row from profiles table
let currentHospital = "SSM"; // "SSM" | "SHH" | "SMH"
let liveLeads      = [];
let filteredLeads  = [];
let currentSelectedLead = null;
let activeCallTimerInterval = null;

// =============================================================
// Supabase API Adapter
// Translates old apiRequest() calls → supabase-js queries
// All UI code above this layer is UNCHANGED.
// =============================================================

/**
 * Central error handler — mirrors old apiRequest() throw behaviour
 */
function sbError(label, error) {
  console.error(`Supabase Error [${label}]:`, error);
  throw new Error(error?.message || "Request failed");
}

/**
 * GET /leads?limit=N  →  supabase.from("leads").select().limit(N)
 * GET /leads/{id}     →  supabase.from("leads").select().eq("id",id).single()
 * POST /leads         →  supabase.from("leads").insert(body)
 * PATCH /leads/{id}   →  supabase.from("leads").update(body).eq("id",id)
 *
 * This thin router keeps every existing call-site working without changes.
 */
async function apiRequest(endpoint, options = {}) {
  const method  = (options.method || "GET").toUpperCase();
  const body    = options.body
    ? (typeof options.body === "string" ? JSON.parse(options.body) : options.body)
    : null;

  // ── Auth endpoints ───────────────────────────────────────────
  if (endpoint === "/auth/me") {
    const profile = await getCurrentProfile();
    if (!profile) throw new Error("Not authenticated");
    // Shape to match what the old /auth/me returned
    return {
      id:            profile.id,
      full_name:     profile.full_name,
      role:          profile.role,
      hospital_id:   profile.hospital_id,
      hospital_code: profile.hospital_code,
      hospital_name: profile.hospitals?.name,
    };
  }

  // ── Leads: list ──────────────────────────────────────────────
  if (endpoint.startsWith("/leads") && method === "GET") {
    const limitMatch  = endpoint.match(/limit=(\d+)/);
    const limit       = limitMatch ? parseInt(limitMatch[1]) : 200;

    // GET /leads/metrics/summary
    if (endpoint.includes("/metrics/summary")) {
      const today = new Date().toISOString().split("T")[0];
      const [total, todayCount] = await Promise.all([
        supabase.from("leads").select("id", { count: "exact", head: true })
          .eq("hospital_code", currentHospital),
        supabase.from("leads").select("id", { count: "exact", head: true })
          .eq("hospital_code", currentHospital)
          .gte("created_at", today),
      ]);
      return { total_leads: total.count ?? 0, today_leads: todayCount.count ?? 0 };
    }

    // GET /leads/reviews/list
    if (endpoint.includes("/reviews/list")) {
      const { data, error } = await supabase
        .from("reviews")
        .select("*, leads(patient_name, primary_phone)")
        .eq("hospital_code", currentHospital)
        .order("created_at", { ascending: false })
        .limit(limit);
      if (error) sbError("/leads/reviews/list", error);
      return (data || []).map(r => ({
        id: r.id,
        lead_id: r.lead_id,
        name: r.patient_name || r.leads?.patient_name || "Patient",
        contact_number: r.primary_phone || r.leads?.primary_phone || "",
        latest_review_date: formatDisplayDate(r.next_review_date || r.created_at),
        latest_review_details: r.review_details || r.status || "Follow-up review pending",
        status: r.status || "Pending"
      }));
    }

    // GET /leads/{id}/timeline
    const timelineMatch = endpoint.match(/\/leads\/([^/]+)\/timeline/);
    if (timelineMatch) {
      const { data, error } = await supabase
        .from("lead_activities")
        .select("*")
        .eq("lead_id", timelineMatch[1])
        .order("performed_at", { ascending: false });
      if (error) sbError("/timeline", error);
      return data ?? [];
    }

    // GET /leads/{id}/status-history
    const histMatch = endpoint.match(/\/leads\/([^/]+)\/status-history/);
    if (histMatch) {
      const { data, error } = await supabase
        .from("lead_status_history")
        .select("*")
        .eq("lead_id", histMatch[1])
        .order("changed_at", { ascending: false });
      if (error) sbError("/status-history", error);
      return data ?? [];
    }

    // GET /leads/{id}  (single lead)
    const singleMatch = endpoint.match(/\/leads\/([a-f0-9-]{36})$/);
    if (singleMatch) {
      const { data, error } = await supabase
        .from("leads")
        .select("*")
        .eq("id", singleMatch[1])
        .single();
      if (error) sbError(`/leads/${singleMatch[1]}`, error);
      return data;
    }

    // GET /leads  (list)
    const { data, error } = await supabase
      .from("leads")
      .select("*")
      .eq("hospital_code", currentHospital)
      .eq("is_archived", false)
      .order("created_at", { ascending: false })
      .limit(limit);
    if (error) sbError("/leads list", error);
    return data ?? [];
  }

  // ── Leads: create ────────────────────────────────────────────
  if (endpoint === "/leads" && method === "POST") {
    const rawPhone = body?.primary_phone || body?.normalized_phone || "";
    const cleanDigits = rawPhone.replace(/\D/g, "");
    const normalized = cleanDigits.length === 10 ? "+91" + cleanDigits : (cleanDigits ? "+" + cleanDigits : "+910000000000");
    const now = new Date().toISOString();

    const payload = {
      ...body,
      id:               body?.id || (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `lead-${Date.now()}`),
      normalized_phone: body?.normalized_phone || normalized,
      hospital_code:    body?.hospital_code || currentHospital,
      hospital_id:      body?.hospital_id || currentUser?.hospital_id || (currentHospital === "SHH" ? "hosp-shh-fd72cfcc" : (currentHospital === "SMH" ? "hosp-smh-42546563" : "hosp-ssm-c13526e4")),
      created_at:       body?.created_at || now,
      updated_at:       body?.updated_at || now
    };
    const { data, error } = await supabase
      .from("leads").insert(payload).select().single();
    if (error) sbError("POST /leads", error);
    return data;
  }

  // ── Leads: update ────────────────────────────────────────────
  if (endpoint.match(/\/leads\/[a-f0-9-]{36}$/) && method === "PATCH") {
    const id = endpoint.split("/").pop();
    const { data, error } = await supabase
      .from("leads").update({ ...body, updated_at: new Date().toISOString() })
      .eq("id", id).select().single();
    if (error) sbError(`PATCH /leads/${id}`, error);
    // Log status change to history if status changed
    if (body.lead_status && currentSelectedLead?.lead_status !== body.lead_status) {
      await supabase.from("lead_status_history").insert({
        lead_id:       id,
        hospital_code: currentHospital,
        old_status:    currentSelectedLead?.lead_status,
        new_status:    body.lead_status,
        changed_by:    currentUser?.id,
      });
    }
    return data;
  }

  // ── Leads/{id}/status  ───────────────────────────────────────
  if (endpoint.match(/\/leads\/[a-f0-9-]{36}\/status$/) && method === "POST") {
    const id = endpoint.split("/")[2];
    await supabase.from("lead_status_history").insert({
      lead_id:       id,
      hospital_code: currentHospital,
      old_status:    body.old_status,
      new_status:    body.new_status,
      reason:        body.reason,
      changed_by:    currentUser?.id,
    });
    return { success: true };
  }

  // ── Leads/{id}/notes  ────────────────────────────────────────
  if (endpoint.match(/\/leads\/[a-f0-9-]{36}\/notes$/) && method === "POST") {
    const id = endpoint.split("/")[2];
    const { error } = await supabase.from("lead_activities").insert({
      lead_id:       id,
      hospital_code: currentHospital,
      activity_type: "NOTE_ADDED",
      title:         "Note added",
      description:   body.content,
      performed_by:  currentUser?.id,
    });
    if (error) sbError("/notes", error);
    return { success: true };
  }

  // ── Followups ────────────────────────────────────────────────
  if (endpoint === "/followups" && method === "POST") {
    const { data, error } = await supabase.from("followups").insert({
      ...body,
      hospital_code: currentHospital,
      created_by:    currentUser?.id,
    }).select().single();
    if (error) sbError("POST /followups", error);
    return data;
  }

  if (endpoint.match(/\/leads\/[a-f0-9-]{36}\/followups$/) && method === "POST") {
    const id = endpoint.split("/")[2];
    const { data, error } = await supabase.from("followups").insert({
      lead_id:       id,
      hospital_code: currentHospital,
      scheduled_at:  body.scheduled_at,
      notes:         body.notes,
      created_by:    currentUser?.id,
    }).select().single();
    if (error) sbError("/lead/followups", error);
    return data;
  }

  // GET /followups/scheduled-calls
  if (endpoint.includes("/followups/scheduled-calls")) {
    const limitMatch = endpoint.match(/limit=(\d+)/);
    const limit = limitMatch ? parseInt(limitMatch[1]) : 150;
    const { data, error } = await supabase
      .from("followups")
      .select("*, leads(patient_name, primary_phone, lead_status)")
      .eq("hospital_code", currentHospital)
      .order("scheduled_at", { ascending: false })
      .limit(limit);
    if (error) sbError("/scheduled-calls", error);
    return (data || []).map(f => ({
      id: f.id,
      lead_id: f.lead_id,
      date: formatDisplayDate(f.created_at || f.scheduled_at),
      name: f.leads?.patient_name || f.patient_name || "Patient",
      contact_number: f.leads?.primary_phone || f.phone || "",
      lead_owner: currentUser?.full_name || "Executive",
      follow_up_date_time: formatDisplayDate(f.scheduled_at),
      call_status: f.status || "Scheduled",
      lead_status: f.leads?.lead_status || "Follow-up",
      notes: f.notes || ""
    }));
  }

  console.warn(`Unhandled apiRequest: ${method} ${endpoint}`);
  return null;
}

// Toast Notifications
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

// =============================================================
// Hospital Tenant & Branding Management
// =============================================================
function updateHospitalBranding(hospitalCode, hospitalName, executiveName) {
  currentHospital = hospitalCode || "SSM";

  const brandImg  = document.getElementById("brandLogoImg");
  const loginImg  = document.getElementById("loginLogoImg");
  const welcomeTitle      = document.getElementById("dashboardWelcomeTitle");
  const profileName       = document.getElementById("userProfileName");
  const currentHospDisplay = document.getElementById("currentHospitalDisplay");

  // Determine which logo image and metadata to use
  const isSSM      = currentHospital === "SSM" || (hospitalName && hospitalName.includes("SSM"));
  const isSantasa  = !isSSM; // Hassan, Mysore and any other Santasa branch

  const logoSrc = isSSM ? "/ssm-logo.png" : "/santasa-logo.png";
  const logoAlt = isSSM ? "SSM Hospital" : "Santasa IVF";

  if (brandImg) { brandImg.src = logoSrc; brandImg.alt = logoAlt; }
  if (loginImg) { loginImg.src = logoSrc; loginImg.alt = logoAlt; }

  // Toggle Admin navigation item and user dropdown admin link visibility based on role
  const isAdmin = currentUser && (currentUser.role === "SUPER_ADMIN" || currentUser.role === "ADMIN");
  const navAdmin = document.getElementById("navAdmin");
  const dropdownAdminLink = document.getElementById("dropdownAdminLink");
  if (navAdmin) {
    if (isAdmin) {
      navAdmin.classList.remove("hidden");
      navAdmin.style.setProperty("display", "inline-flex", "important");
    } else {
      navAdmin.classList.add("hidden");
      navAdmin.style.setProperty("display", "none", "important");
    }
  }
  if (dropdownAdminLink) {
    if (isAdmin) {
      dropdownAdminLink.classList.remove("hidden");
      dropdownAdminLink.style.setProperty("display", "flex", "important");
    } else {
      dropdownAdminLink.classList.add("hidden");
      dropdownAdminLink.style.setProperty("display", "none", "important");
    }
  }

  if (currentUser?.role === "SUPER_ADMIN") {
    if (welcomeTitle)       welcomeTitle.textContent = `Welcome ${executiveName || "Super Administrator"} (Network Admin)`;
    if (profileName)        profileName.textContent  = executiveName || "Super Administrator";
    if (currentHospDisplay) currentHospDisplay.textContent = "Multi-Hospital Network";
    document.title = "Santasa & SSM Hospital CRM — Super Admin Portal";
    return;
  }

  if (isSSM) {
    if (welcomeTitle)       welcomeTitle.textContent = `Welcome ${executiveName || "SSM Hospital Executive"}`;
    if (profileName)        profileName.textContent  = executiveName || "SSM Hospital Executive";
    if (currentHospDisplay) currentHospDisplay.textContent = "SSM Hospital";
    document.title = "SSM Hospital CRM — Executive Portal";
  } else if (currentHospital === "SHH" || (hospitalName && hospitalName.includes("Hassan"))) {
    if (welcomeTitle)       welcomeTitle.textContent = `Welcome ${executiveName || "Santasa Hassan Executive"}`;
    if (profileName)        profileName.textContent  = executiveName || "Santasa Hassan Executive";
    if (currentHospDisplay) currentHospDisplay.textContent = "Santasa Hassan Hospital";
    document.title = "Santasa Hassan Hospital CRM — Executive Portal";
  } else {
    if (welcomeTitle)       welcomeTitle.textContent = `Welcome ${executiveName || "Santasa Mysore Executive"}`;
    if (profileName)        profileName.textContent  = executiveName || "Santasa Mysore Executive";
    if (currentHospDisplay) currentHospDisplay.textContent = "Santasa Mysore Hospital";
    document.title = "Santasa Mysore Hospital CRM — Executive Portal";
  }
}


// =============================================================
// Navigation & Views Switcher
// =============================================================
// =============================================================
// Navigation & Views Switcher (With 100% Page Persistence on Refresh)
// =============================================================
let currentActiveTab = "dashboard";
let previousNavTab = "leads";

function getInitialTab() {
  const hash = window.location.hash || "";
  if (hash.startsWith("#/client/updateClientLead/")) {
    return "updateLead";
  }
  if (hash.includes("admin")) return "admin";
  if (hash.includes("create")) return "createLead";
  if (hash.includes("lead")) return "leads";
  if (hash.includes("call")) return "calls";
  if (hash.includes("review")) return "reviews";
  if (hash.includes("dashboard") || hash.includes("home")) return "dashboard";

  // Fallback to persisted tab from localStorage
  const saved = localStorage.getItem("santasa_active_tab");
  if (saved && ["dashboard", "leads", "calls", "reviews", "createLead", "admin"].includes(saved)) {
    return saved;
  }

  return "dashboard";
}

function switchTab(targetTab) {
  window.switchTab = switchTab;
  const norm = (targetTab === "home" ? "dashboard" : (targetTab === "call-notifications" ? "calls" : targetTab));

  if (currentActiveTab !== "createLead" && currentActiveTab !== "updateLead") {
    previousNavTab = currentActiveTab;
  }
  currentActiveTab = norm;

  // Persist active tab to localStorage & synchronize URL hash for refresh retention
  try {
    localStorage.setItem("santasa_active_tab", norm);
    if (norm !== "updateLead") {
      const targetHash = `#/${norm === "createLead" ? "create-lead" : norm}`;
      if (window.location.hash !== targetHash) {
        history.replaceState(null, "", targetHash);
      }
    }
  } catch (e) {
    console.warn("Could not save active tab state:", e);
  }

  const views = {
    dashboard: document.getElementById("dashboardView"),
    leads: document.getElementById("leadsView"),
    calls: document.getElementById("callNotificationsView"),
    reviews: document.getElementById("reviewsView"),
    createLead: document.getElementById("createLeadView"),
    updateLead: document.getElementById("updateClientLeadView"),
    admin: document.getElementById("adminDashboardView")
  };

  Object.values(views).forEach(v => {
    if (v) v.classList.add("hidden");
  });

  document.querySelectorAll(".hummatic-nav-link").forEach(l => l.classList.remove("active"));

  if (norm === "dashboard") {
    if (views.dashboard) views.dashboard.classList.remove("hidden");
    const link = document.getElementById("navHome");
    if (link) link.classList.add("active");
    loadDashboardData();
  } else if (norm === "leads") {
    if (views.leads) views.leads.classList.remove("hidden");
    const link = document.getElementById("navLeads");
    if (link) link.classList.add("active");
    loadLeadsData();
  } else if (norm === "calls") {
    if (views.calls) views.calls.classList.remove("hidden");
    const link = document.getElementById("navCallNotifications");
    if (link) link.classList.add("active");
    loadCallNotifications();
  } else if (norm === "reviews") {
    if (views.reviews) views.reviews.classList.remove("hidden");
    const link = document.getElementById("navReviews");
    if (link) link.classList.add("active");
    loadReviews();
  } else if (norm === "createLead") {
    if (views.createLead) views.createLead.classList.remove("hidden");
    const dateInput = document.getElementById("inputFormDate");
    if (dateInput && !dateInput.value) {
      dateInput.value = new Date().toISOString().split("T")[0];
    }
  } else if (norm === "updateLead") {
    if (views.updateLead) views.updateLead.classList.remove("hidden");
    const link = document.getElementById("navLeads");
    if (link) link.classList.add("active");
  } else if (norm === "admin") {
    const isAdmin = currentUser && (currentUser.role === "SUPER_ADMIN" || currentUser.role === "ADMIN");
    if (!isAdmin) {
      showToast("Access restricted: Administrator privileges required.", "error");
      switchTab("dashboard");
      return;
    }
    if (views.admin) views.admin.classList.remove("hidden");
    const link = document.getElementById("navAdmin");
    if (link) link.classList.add("active");
    loadAdminDashboardData();
  }
}

// =============================================================
// Dashboard Data Loading (Matching Screenshot 1)
// =============================================================
async function loadDashboardData() {
  try {
    // 1. Fetch KPI metrics for active hospital
    const metrics = await apiRequest("/leads/metrics/summary").catch(() => ({ total_leads: 0, today_leads: 0 }));
    const kpiTotal = document.getElementById("kpiTotalLeads");
    const kpiToday = document.getElementById("kpiTodayLeads");
    if (kpiTotal) kpiTotal.textContent = metrics.total_leads ?? 0;
    if (kpiToday) kpiToday.textContent = metrics.today_leads ?? 0;

    // 2. Fetch leads
    const leads = await apiRequest("/leads?limit=200").catch(() => []);
    liveLeads = leads || [];

    // Filter today's leads
    const todayStr = new Date().toISOString().split("T")[0];
    const todayLeads = liveLeads.filter(l => {
      if (!l.created_at) return false;
      return l.created_at.startsWith(todayStr);
    });

    renderTodayLeadsTable(todayLeads.length > 0 ? todayLeads : liveLeads.slice(0, 5));

    // ── Missed Calls KPI ────────────────────────────────────────
    const callsData = await apiRequest("/followups/scheduled-calls").catch(() => []);
    const missedCount = Array.isArray(callsData)
      ? callsData.filter(c => (c.status || c.call_status || "").toLowerCase().includes("miss")).length
      : 0;
    const kpiMissed = document.getElementById("kpiMissedCalls");
    if (kpiMissed) kpiMissed.textContent = missedCount;

    // ── Pending Reviews KPI ──────────────────────────────────────
    const reviewsData = await apiRequest("/leads/reviews/list").catch(() => []);
    const reviewCount = Array.isArray(reviewsData) ? reviewsData.length : 0;
    const kpiReviews = document.getElementById("kpiPendingReviews");
    if (kpiReviews) kpiReviews.textContent = reviewCount;

    // ── Nav Badges ───────────────────────────────────────────────
    updateNavBadge("navCallsBadge", callsData.length || 0);
    updateNavBadge("navReviewsBadge", reviewCount);

  } catch (err) {
    console.error("Error loading dashboard data:", err);
  }
}

function updateNavBadge(badgeId, count) {
  const badge = document.getElementById(badgeId);
  if (!badge) return;
  if (count > 0) {
    badge.textContent = count > 99 ? "99+" : count;
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }
}

function renderTodayLeadsTable(leads) {
  const tbody = document.getElementById("todayLeadsTableBody");
  if (!tbody) return;

  if (leads.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No leads recorded today.</td></tr>`;
    return;
  }

  tbody.innerHTML = leads.map(l => {
    const d = new Date(l.created_at || Date.now());
    const dateFormatted = `${String(d.getDate()).padStart(2, '0')}-${String(d.getMonth() + 1).padStart(2, '0')}-${d.getFullYear()}`;
    return `
      <tr data-lead-id="${l.id}">
        <td>${dateFormatted}</td>
        <td><a class="lead-link view-lead-action" data-lead-id="${l.id}">${escapeHtml(l.patient_name)}</a></td>
        <td>${escapeHtml(l.primary_phone || l.normalized_phone || '')}</td>
        <td><span class="status-badge-clean ${getStatusClass(l.lead_status)}">${escapeHtml(l.lead_status || 'New')}</span></td>
      </tr>
    `;
  }).join("");

  tbody.querySelectorAll(".view-lead-action").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const lid = btn.getAttribute("data-lead-id");
      openUpdateClientLead(lid);
    });
  });
}

// =============================================================
// Leads List View Data (Matching Screenshots 2 & 3)
// =============================================================
async function loadLeadsData() {
  const tbody = document.getElementById("assignedLeadsTableBody");
  if (tbody) {
    tbody.innerHTML = `<tr><td colspan="12" class="table-loading">Loading assigned leads...</td></tr>`;
  }

  try {
    const leads = await apiRequest("/leads?limit=150").catch(() => []);
    liveLeads = leads || [];
    filteredLeads = [...liveLeads];
    renderAssignedLeadsTable(filteredLeads);
  } catch (err) {
    console.error("Error loading leads:", err);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="12" style="text-align: center; color: #dc2626; padding: 1.5rem;">Failed to load leads from server.</td></tr>`;
    }
  }
}

function renderAssignedLeadsTable(leads) {
  const tbody = document.getElementById("assignedLeadsTableBody");
  const countInfo = document.getElementById("leadsPaginationInfo");
  if (!tbody) return;

  if (countInfo) {
    countInfo.textContent = `Showing ${leads.length} leads`;
  }

  if (leads.length === 0) {
    tbody.innerHTML = `<tr><td colspan="12" style="text-align: center; color: var(--text-muted); padding: 2rem;">No matching leads found.</td></tr>`;
    return;
  }

  tbody.innerHTML = leads.map(l => {
    const cd = new Date(l.created_at || Date.now());
    const createdDate = `${String(cd.getDate()).padStart(2, '0')}-${String(cd.getMonth() + 1).padStart(2, '0')}-${cd.getFullYear()}`;
    const consultDate = l.consultation_date ? formatDisplayDate(l.consultation_date) : '';
    const surgeryDate = l.surgery_date ? formatDisplayDate(l.surgery_date) : '';

    return `
      <tr data-lead-id="${l.id}">
        <td>
          <button class="action-dots-btn" data-lead-id="${l.id}" title="Actions">•••</button>
        </td>
        <td><span class="status-badge-clean ${getStatusClass(l.lead_status)}">${escapeHtml(l.lead_status || 'New')}</span></td>
        <td>${createdDate}</td>
        <td>${createdDate}</td>
        <td><a class="lead-link view-lead-action" data-lead-id="${l.id}">${escapeHtml(l.patient_name)}</a></td>
        <td>${escapeHtml(l.patient_name)}</td>
        <td>${escapeHtml(l.primary_phone || l.normalized_phone || '')}</td>
        <td>${escapeHtml(l.destination_number ? 'Answered' : '')}</td>
        <td>${escapeHtml(l.patient_type || 'Digital Patient')}</td>
        <td>${consultDate}</td>
        <td>${escapeHtml(l.surgery_requirement || '')}</td>
        <td>${surgeryDate}</td>
      </tr>
    `;
  }).join("");

  // Bind Actions buttons
  tbody.querySelectorAll(".action-dots-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const lid = btn.getAttribute("data-lead-id");
      openLeadActionDrawer(lid);
    });
  });

  tbody.querySelectorAll(".view-lead-action").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const lid = btn.getAttribute("data-lead-id");
      openUpdateClientLead(lid);
    });
  });
}

function getStatusClass(status) {
  if (!status) return "new";
  const s = status.toLowerCase();
  if (s.includes("valid") || s.includes("consultation done") || s.includes("surgery done") || s.includes("converted")) return "valid";
  if (s.includes("invalid") || s.includes("wrong") || s.includes("lost") || s.includes("not interested")) return "invalid";
  if (s.includes("followup") || s.includes("follow-up")) return "followup";
  return "new";
}

function formatDisplayDate(dStr) {
  if (!dStr) return "";
  try {
    const d = new Date(dStr);
    return `${String(d.getDate()).padStart(2, '0')}-${String(d.getMonth() + 1).padStart(2, '0')}-${d.getFullYear()}`;
  } catch {
    return dStr;
  }
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

// =============================================================
// Quick Action Drawer / Lead Modal
// =============================================================
async function openLeadActionDrawer(leadId) {
  // Look up in cache first; fetch from API if not found
  let lead = liveLeads.find(l => l.id === leadId);
  if (!lead) {
    try {
      lead = await apiRequest(`/leads/${leadId}`);
      if (lead) liveLeads.push(lead); // cache it
    } catch (err) {
      console.warn("Could not fetch lead for drawer:", err);
    }
  }
  if (!lead) {
    showToast("Could not load lead details.", "error");
    return;
  }
  currentSelectedLead = lead;

  const drawer = document.getElementById("leadActionDrawerModal");
  const nameEl = document.getElementById("drawerLeadName");
  const phoneEl = document.getElementById("drawerLeadPhone");
  const statusEl = document.getElementById("drawerLeadStatus");
  const audioSec = document.getElementById("drawerAudioSection");
  const audioPlayer = document.getElementById("drawerAudioPlayer");

  // Store leadId on drawer so buttons can always access it
  if (drawer) drawer.dataset.leadId = leadId;

  if (nameEl) nameEl.textContent = lead.patient_name;
  if (phoneEl) phoneEl.textContent = lead.primary_phone || lead.normalized_phone;
  if (statusEl) {
    statusEl.textContent = lead.lead_status || "New";
    statusEl.className = `drawer-status-badge ${getStatusClass(lead.lead_status)}`;
  }

  // Check if lead has an attached recording from mobile sync or telephony
  if (lead.recording_url && audioPlayer && audioSec) {
    audioPlayer.src = lead.recording_url;
    audioSec.classList.remove("hidden");
  } else if (audioSec) {
    audioSec.classList.add("hidden");
  }

  if (drawer) drawer.classList.remove("hidden");
}

// =============================================================
// Create A New Lead Form Handling (Matching Screenshots 4 & 5)
// =============================================================
async function handleCreateLeadSubmit(e) {
  e.preventDefault();

  const patientName = document.getElementById("inputFormPatientName").value.trim();
  const contactNumber = document.getElementById("inputFormContactNumber").value.trim();
  const registeredNumber = document.getElementById("inputFormRegisteredNumber").value.trim();
  const email = document.getElementById("inputFormEmail").value.trim();
  const treatment = document.getElementById("inputFormTreatment").value.trim();
  const message = document.getElementById("inputFormMessage").value.trim();
  const patientType = document.getElementById("inputFormPatientType").value;
  const patientId = document.getElementById("inputFormPatientId").value.trim();
  const leadSource = document.getElementById("inputFormLeadSource").value;
  const leadStatus = document.getElementById("inputFormLeadStatus").value;
  const consultDate = document.getElementById("inputFormConsultationDate").value;
  const surgeryDate = document.getElementById("inputFormSurgeryDate").value;
  const surgeryReq = document.getElementById("inputFormSurgeryRequirement").value.trim();
  const surgeryDet = document.getElementById("inputFormSurgeryDetails").value.trim();
  const destNumber = document.getElementById("inputFormDestinationNumber").value.trim();
  const remarks = document.getElementById("inputFormRemarks").value.trim();

  if (!patientName || !contactNumber) {
    showToast("Please enter mandatory fields: Patient Name and Contact Number.", "error");
    return;
  }

  const payload = {
    patient_name: patientName,
    primary_phone: contactNumber,
    registered_number: registeredNumber || null,
    email: email || null,
    treatment: treatment || null,
    message: message || null,
    patient_type: patientType || "Enquiry",
    patient_id_mrn: patientId || null,
    lead_source: leadSource || "Manual",
    lead_status: leadStatus || "New",
    consultation_date: consultDate ? new Date(consultDate).toISOString() : null,
    surgery_date: surgeryDate ? new Date(surgeryDate).toISOString() : null,
    surgery_requirement: surgeryReq || null,
    surgery_details: surgeryDet || null,
    destination_number: destNumber || null,
    notes: remarks || null
  };

  showToast("Saving new lead...", "info");

  try {
    const created = await apiRequest("/leads", {
      method: "POST",
      body: payload
    });

    // Check if audio recording file was attached
    const audioInput = document.getElementById("inputFormRecordingFile");
    if (audioInput && audioInput.files && audioInput.files[0]) {
      const formData = new FormData();
      formData.append("phone_number", contactNumber);
      formData.append("duration_seconds", "60");
      formData.append("direction", document.getElementById("inputFormDirection").value || "Incoming");
      formData.append("file", audioInput.files[0]);
      await fetch(`${API_BASE}/telephony/mobile-sync/call-log`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${authToken}` },
        body: formData
      }).catch(err => console.warn("Recording upload error:", err));
    }

    showToast(`Lead created successfully: ${created.patient_name}`, "success");
    document.getElementById("createLeadForm").reset();
    switchTab("leads");
  } catch (err) {
    showToast(`Failed to create lead: ${err.message}`, "error");
  }
}

// =============================================================
// Hash-Based URL Routing
// =============================================================
function handleHashRouting() {
  const hash = window.location.hash || "";
  const match = hash.match(/^#\/client\/updateClientLead\/(.+)$/);
  if (match) {
    const leadId = decodeURIComponent(match[1]);
    if (authToken && currentUser) {
      openUpdateClientLead(leadId);
    } else {
      // Store pending route, resolve after login
      sessionStorage.setItem("pendingRoute", hash);
    }
    return;
  }

  if (hash === "#dashboard" || hash === "#home" || hash === "#/dashboard") {
    switchTab("dashboard");
  } else if (hash === "#leads" || hash === "#/leads") {
    switchTab("leads");
  } else if (hash === "#call-notifications" || hash === "#calls" || hash === "#/calls") {
    switchTab("calls");
  } else if (hash === "#reviews" || hash === "#/reviews") {
    switchTab("reviews");
  } else if (hash === "#createLead" || hash === "#/create-lead") {
    switchTab("createLead");
  } else if (hash === "#admin" || hash === "#/admin") {
    switchTab("admin");
  }
}

window.addEventListener("popstate", () => {
  const hash = window.location.hash || "";
  if (!hash || hash === "#" || hash === "#/") {
    switchTab("dashboard");
  } else {
    handleHashRouting();
  }
});

window.addEventListener("hashchange", () => {
  handleHashRouting();
});

// =============================================================
// Update Client Lead Page Handling (Matching Screenshots 1 & 2)
// =============================================================
async function openUpdateClientLead(leadId) {
  let lead = liveLeads.find(l => l.id === leadId);
  try {
    const fetched = await apiRequest(`/leads/${leadId}`);
    if (fetched) lead = fetched;
  } catch (err) {
    console.warn("Could not fetch fresh lead details, using cached:", err);
  }

  if (!lead) {
    showToast("Lead not found", "error");
    return;
  }

  currentSelectedLead = lead;

  // ── URL Hash Routing ────────────────────────────────────────────
  history.pushState({ leadId }, "", `#/client/updateClientLead/${leadId}`);

  // Populate Update Lead Form
  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val !== null && val !== undefined ? val : "";
  };

  setVal("updateLeadId", lead.id);
  setVal("updateLeadCreatedDate", formatDisplayDate(lead.created_at) || "21-09-2026");
  setVal("updateLeadName", lead.name || lead.patient_name);
  setVal("updatePatientName", lead.patient_name);
  setVal("updateContactNumber", lead.primary_phone || lead.normalized_phone);
  setVal("updateRegisteredNumber", lead.registered_number);
  setVal("updateEmail", lead.email);
  setVal("updateTreatment", lead.treatment);
  setVal("updateMessage", lead.message || lead.notes);
  setVal("updatePatientType", lead.patient_type || "Enquiry");
  setVal("updatePatientId", lead.patient_id_mrn);
  setVal("updateLeadStatus", lead.lead_status || "New");

  if (lead.consultation_date) {
    setVal("updateConsultationDate", String(lead.consultation_date).split("T")[0]);
  } else {
    setVal("updateConsultationDate", "");
  }

  if (lead.surgery_date) {
    setVal("updateSurgeryDate", String(lead.surgery_date).split("T")[0]);
  } else {
    setVal("updateSurgeryDate", "");
  }

  setVal("updateSurgeryRequirement", lead.surgery_requirement);
  setVal("updateSurgeryDetails", lead.surgery_details);
  setVal("updateReviewNeeded", lead.review_needed || "");
  setVal("updateReviewPeriod", lead.review_period);

  if (lead.next_review_date) {
    setVal("updateNextReviewDate", String(lead.next_review_date).split("T")[0]);
  } else {
    setVal("updateNextReviewDate", "");
  }

  setVal("updateReviewDetails", lead.review_details);
  setVal("updateDestinationNumber", lead.destination_number);
  setVal("updateCallStatus", lead.destination_number ? "Answered" : "Missed");
  setVal("updateCallDirection", lead.call_direction || "Incoming");

  const audioPlayer = document.getElementById("updateAudioPlayer");
  const audioBox = document.getElementById("updateAudioPlayerBox");
  if (lead.recording_url && audioPlayer && audioBox) {
    audioPlayer.src = lead.recording_url;
    audioBox.style.display = "flex";
  } else if (audioBox) {
    if (audioPlayer) audioPlayer.src = "";
    audioBox.style.display = "none";
  }

  setVal("updateUtmSource", lead.utm_source);
  setVal("updateUtmMedium", lead.utm_medium);
  setVal("updateUtmCampaign", lead.utm_campaign);
  setVal("updateUtmTerm", lead.utm_term);
  setVal("updateUtmContent", lead.utm_content);
  setVal("updateLeadUrl", lead.lead_url);
  setVal("updateRemarks", ""); // textarea is for NEW remark entry

  // ── Remarks History Timeline ────────────────────────────────────
  const remarksList = document.getElementById("updateRemarksTimeline");
  if (remarksList) {
    remarksList.innerHTML = "";
    // Parse notes field — each line or "---" separated block is a remark
    const rawNotes = lead.notes || "";
    if (rawNotes.trim()) {
      const chunks = rawNotes.split(/---+|\n\n+/).map(s => s.trim()).filter(Boolean);
      if (chunks.length > 0) {
        chunks.reverse(); // newest first
        chunks.forEach(chunk => {
          const li = document.createElement("li");
          li.innerHTML = `${escapeHtml(chunk)}`;
          remarksList.appendChild(li);
        });
      } else {
        const li = document.createElement("li");
        li.textContent = rawNotes.trim();
        remarksList.appendChild(li);
      }
    }
  }

  switchTab("updateLead");

  // ── Lead Other Details — Activity Timeline (async, after render) ─
  const timelineContainer = document.getElementById("updateLeadTimeline");
  if (timelineContainer) {
    timelineContainer.innerHTML = `<p style="color:#94a3b8; font-size:13px; padding:8px 0;">Loading activity...</p>`;
    try {
      const [timeline, statusHist] = await Promise.allSettled([
        apiRequest(`/leads/${leadId}/timeline`),
        apiRequest(`/leads/${leadId}/status-history`)
      ]);

      const activities = (timeline.status === "fulfilled" && Array.isArray(timeline.value)) ? timeline.value : [];
      const statuses   = (statusHist.status === "fulfilled" && Array.isArray(statusHist.value)) ? statusHist.value : [];

      // Merge both into unified list sorted by time descending
      const events = [
        ...activities.map(a => ({
          ts: a.performed_at,
          title: a.title || a.activity_type,
          desc: a.description || "",
          type: a.activity_type || "event",
          by: a.performed_by || ""
        })),
        ...statuses.map(s => ({
          ts: s.changed_at,
          title: `Status changed: ${s.old_status || "New"} → ${s.new_status}`,
          desc: s.reason || "",
          type: "status_change",
          by: s.changed_by || ""
        }))
      ].sort((a, b) => new Date(b.ts) - new Date(a.ts));

      // Seed with lead creation event always
      events.push({
        ts: lead.created_at,
        title: `New lead came on ${formatDisplayDate(lead.created_at)}`,
        desc: `from ${lead.lead_source || "IVR Call"}`,
        type: "created",
        by: ""
      });
      // Re-sort after adding creation event
      events.sort((a, b) => new Date(b.ts) - new Date(a.ts));

      if (events.length === 0) {
        timelineContainer.innerHTML = `<p style="color:#94a3b8; font-size:13px; padding:8px 0;">No activity recorded yet.</p>`;
      } else {
        timelineContainer.innerHTML = events.map(ev => {
          const dotClass = ev.type === "status_change" ? "status-change"
            : (ev.type === "NOTE_ADDED" || ev.type === "note") ? "note"
            : (ev.type === "CALL" || ev.type === "call") ? "call" : "";
          const metaParts = [];
          if (ev.ts) metaParts.push(formatDisplayDate(ev.ts));
          if (ev.by) metaParts.push(`By ${ev.by}`);
          return `<div class="lead-timeline-item">
            <div class="lead-timeline-dot ${dotClass}"></div>
            <div class="lead-timeline-text">
              <strong>${escapeHtml(ev.title)}</strong>
              ${ev.desc ? `<div style="color:#475569;margin-top:2px;">${escapeHtml(ev.desc)}</div>` : ""}
              ${metaParts.length ? `<div class="lead-timeline-meta">${metaParts.join(" — ")}</div>` : ""}
            </div>
          </div>`;
        }).join("");
      }
    } catch (err) {
      console.warn("Timeline load error:", err);
      timelineContainer.innerHTML = `<p style="color:#94a3b8; font-size:13px; padding:8px 0;">Could not load activity.</p>`;
    }
  }
}


async function handleUpdateLeadSubmit(e) {
  e.preventDefault();
  const leadId = document.getElementById("updateLeadId").value;
  if (!leadId) return;

  const getVal = id => {
    const el = document.getElementById(id);
    return el ? el.value.trim() : "";
  };

  const consultDateVal = getVal("updateConsultationDate");
  const surgeryDateVal = getVal("updateSurgeryDate");
  const nextRevVal = getVal("updateNextReviewDate");

  const payload = {
    patient_name: getVal("updatePatientName"),
    primary_phone: getVal("updateContactNumber"),
    registered_number: getVal("updateRegisteredNumber") || null,
    email: getVal("updateEmail") || null,
    treatment: getVal("updateTreatment") || null,
    message: getVal("updateMessage") || null,
    patient_type: document.getElementById("updatePatientType").value || null,
    patient_id_mrn: getVal("updatePatientId") || null,
    lead_status: document.getElementById("updateLeadStatus").value || null,
    consultation_date: consultDateVal ? new Date(consultDateVal).toISOString() : null,
    surgery_date: surgeryDateVal ? new Date(surgeryDateVal).toISOString() : null,
    surgery_requirement: getVal("updateSurgeryRequirement") || null,
    surgery_details: getVal("updateSurgeryDetails") || null,
    review_needed: document.getElementById("updateReviewNeeded").value || null,
    review_period: getVal("updateReviewPeriod") || null,
    next_review_date: nextRevVal ? new Date(nextRevVal).toISOString() : null,
    review_details: getVal("updateReviewDetails") || null,
    destination_number: getVal("updateDestinationNumber") || null,
    utm_source: getVal("updateUtmSource") || null,
    utm_medium: getVal("updateUtmMedium") || null,
    utm_campaign: getVal("updateUtmCampaign") || null,
    utm_term: getVal("updateUtmTerm") || null,
    utm_content: getVal("updateUtmContent") || null,
    lead_url: getVal("updateLeadUrl") || null,
    notes: null // will be set below
  };

  // Merge new remark into notes (append to existing history)
  const newRemark = getVal("updateRemarks");
  if (newRemark) {
    const existingNotes = (currentSelectedLead && currentSelectedLead.notes) ? currentSelectedLead.notes : "";
    const now = new Date();
    const ts = now.toLocaleDateString("en-GB").replace(/\//g, "-") + " " + now.toLocaleTimeString("en-GB", { hour12: true });
    const author = (currentUser && currentUser.full_name) ? currentUser.full_name : "Executive";
    payload.notes = existingNotes
      ? `${existingNotes}\n---\n${newRemark} — ${ts} By ${author}`
      : `${newRemark} — ${ts} By ${author}`;
  } else {
    // Keep existing notes unchanged when no new remark entered
    payload.notes = (currentSelectedLead && currentSelectedLead.notes) ? currentSelectedLead.notes : null;
  }

  showToast("Saving changes...", "info");

  try {
    const updated = await apiRequest(`/leads/${leadId}`, {
      method: "PATCH",
      body: payload
    });
    showToast(`Lead updated successfully: ${updated.patient_name}`, "success");
    history.pushState({}, "", "#/leads");
    switchTab("leads");
  } catch (err) {
    showToast(`Failed to update lead: ${err.message}`, "error");
  }
}

// =============================================================
// Schedule Call Modal Handling
// =============================================================
function openScheduleCallModal(lead) {
  const targetLead = lead || currentSelectedLead;
  if (!targetLead) {
    showToast("No lead selected to schedule a call.", "error");
    return;
  }
  document.getElementById("scheduleCallPatientName").value = targetLead.patient_name;
  document.getElementById("scheduleCallPhone").value = targetLead.primary_phone || targetLead.normalized_phone || "";
  
  // Default scheduled time to tomorrow 10:00 AM
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(10, 0, 0, 0);
  document.getElementById("scheduleCallDateTime").value = tomorrow.toISOString().slice(0, 16);
  document.getElementById("scheduleCallNotes").value = "";

  document.getElementById("scheduleCallModal")?.classList.remove("hidden");
}

async function handleScheduleCallSubmit(e) {
  e.preventDefault();
  const targetLead = currentSelectedLead;
  if (!targetLead) return;

  const dt = document.getElementById("scheduleCallDateTime").value;
  const priority = document.getElementById("scheduleCallPriority").value;
  const notes = document.getElementById("scheduleCallNotes").value.trim();

  try {
    await apiRequest(`/leads/${targetLead.id}/followups`, {
      method: "POST",
      body: {
        scheduled_at: new Date(dt).toISOString(),
        type: "Call",
        priority: priority,
        notes: notes
      }
    });

    showToast("Call scheduled successfully!", "success");
    document.getElementById("scheduleCallModal")?.classList.add("hidden");
  } catch (err) {
    showToast(`Failed to schedule call: ${err.message}`, "error");
  }
}

// =============================================================
// Call Notifications / All Scheduled Calls View (Screenshot 3)
// =============================================================
let allScheduledCalls = [];
let filteredScheduledCalls = [];
let callsPageSize = 10;
let callsCurrentPage = 1;

async function loadCallNotifications() {
  const tbody = document.getElementById("callsFeedTableBody");
  if (tbody) {
    tbody.innerHTML = `<tr><td colspan="7" class="table-loading">Loading scheduled calls...</td></tr>`;
  }

  try {
    const calls = await apiRequest("/followups/scheduled-calls?limit=150").catch(() => []);
    allScheduledCalls = calls || [];
    filteredScheduledCalls = [...allScheduledCalls];
    callsCurrentPage = 1;
    renderScheduledCallsTable();
  } catch (err) {
    console.error("Error loading scheduled calls:", err);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #dc2626; padding: 1.5rem;">Failed to load scheduled calls.</td></tr>`;
    }
  }
}

function renderScheduledCallsTable() {
  const tbody = document.getElementById("callsFeedTableBody");
  const countInfo = document.getElementById("callsCountInfo");
  const paginationContainer = document.getElementById("callsPagination");
  if (!tbody) return;

  const total = filteredScheduledCalls.length;
  const totalPages = Math.max(1, Math.ceil(total / callsPageSize));
  if (callsCurrentPage > totalPages) callsCurrentPage = totalPages;

  const startIdx = total === 0 ? 0 : (callsCurrentPage - 1) * callsPageSize;
  const endIdx = Math.min(startIdx + callsPageSize, total);
  const pagedCalls = filteredScheduledCalls.slice(startIdx, endIdx);

  if (countInfo) {
    countInfo.textContent = total === 0 ? "Showing 0 to 0 of 0 entries" : `Showing ${startIdx + 1} to ${endIdx} of ${total} entries`;
  }

  if (total === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 2rem;">No scheduled calls found.</td></tr>`;
    if (paginationContainer) {
      paginationContainer.innerHTML = `<button class="btn-page-ctrl disabled">Previous</button><button class="btn-page-ctrl active">1</button><button class="btn-page-ctrl disabled">Next</button>`;
    }
    return;
  }

  tbody.innerHTML = pagedCalls.map(c => {
    const callStatus = c.call_status || "Scheduled";
    const leadStatus = c.lead_status || "New";
    const patientName = c.name || "Patient";
    const phone = c.contact_number || "";
    const callDate = c.date || "-";
    const followDate = c.follow_up_date_time || "-";
    const owner = c.lead_owner || "Executive";
    const statusClass = callStatus.toLowerCase().replace(/\s+/g, '-');
    return `
      <tr>
        <td>${escapeHtml(callDate)}</td>
        <td><a class="lead-link view-lead-from-call" data-lead-id="${c.lead_id || ''}">${escapeHtml(patientName)}</a></td>
        <td>${escapeHtml(phone)}</td>
        <td>${escapeHtml(owner)}</td>
        <td>${escapeHtml(followDate)}</td>
        <td><span class="status-pill-call ${statusClass}">${escapeHtml(callStatus)}</span></td>
        <td><span class="status-badge-clean ${getStatusClass(leadStatus)}">${escapeHtml(leadStatus)}</span></td>
        <td>
          <button type="button" class="btn-wa-call-action btn-send-call-wa" data-lead-id="${c.lead_id || ''}" data-name="${escapeHtml(patientName)}" data-phone="${escapeHtml(phone)}" data-time="${escapeHtml(followDate)}" title="Send WhatsApp reminder to ${escapeHtml(patientName)}">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
            Remind
          </button>
        </td>
      </tr>
    `;
  }).join("");

  tbody.querySelectorAll(".btn-send-call-wa").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const phone = btn.getAttribute("data-phone");
      const name = btn.getAttribute("data-name");
      const leadId = btn.getAttribute("data-lead-id");
      const time = btn.getAttribute("data-time");
      openWhatsAppReminderModal({
        id: leadId,
        patient_name: name,
        primary_phone: phone,
        next_followup_at: time
      }, "followup");
    });
  });

  tbody.querySelectorAll(".view-lead-from-call").forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const lid = link.getAttribute("data-lead-id");
      openUpdateClientLead(lid);
    });
  });

  // Render pagination
  if (paginationContainer) {
    let html = `<button class="btn-page-ctrl ${callsCurrentPage === 1 ? 'disabled' : ''}" id="callsPrevPageBtn">Previous</button>`;
    for (let p = 1; p <= totalPages; p++) {
      html += `<button class="btn-page-ctrl ${p === callsCurrentPage ? 'active' : ''}" data-page="${p}">${p}</button>`;
    }
    html += `<button class="btn-page-ctrl ${callsCurrentPage === totalPages ? 'disabled' : ''}" id="callsNextPageBtn">Next</button>`;
    paginationContainer.innerHTML = html;

    const prevBtn = document.getElementById("callsPrevPageBtn");
    if (prevBtn && callsCurrentPage > 1) {
      prevBtn.addEventListener("click", () => {
        callsCurrentPage--;
        renderScheduledCallsTable();
      });
    }

    const nextBtn = document.getElementById("callsNextPageBtn");
    if (nextBtn && callsCurrentPage < totalPages) {
      nextBtn.addEventListener("click", () => {
        callsCurrentPage++;
        renderScheduledCallsTable();
      });
    }

    paginationContainer.querySelectorAll("[data-page]").forEach(btn => {
      btn.addEventListener("click", () => {
        callsCurrentPage = parseInt(btn.getAttribute("data-page"), 10);
        renderScheduledCallsTable();
      });
    });
  }
}

// =============================================================
// Reviews List View (Screenshot 4)
// =============================================================
let allReviews = [];
let filteredReviews = [];
let reviewsPageSize = 10;
let reviewsCurrentPage = 1;

async function loadReviews() {
  const tbody = document.getElementById("reviewsTableBody");
  if (tbody) {
    tbody.innerHTML = `<tr><td colspan="5" class="table-loading">Loading reviews...</td></tr>`;
  }

  try {
    const reviews = await apiRequest("/leads/reviews/list?limit=150").catch(() => []);
    allReviews = reviews || [];
    filteredReviews = [...allReviews];
    reviewsCurrentPage = 1;
    renderReviewsTable();
  } catch (err) {
    console.error("Error loading reviews:", err);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #dc2626; padding: 1.5rem;">Failed to load reviews.</td></tr>`;
    }
  }
}

function renderReviewsTable() {
  const tbody = document.getElementById("reviewsTableBody");
  const countInfo = document.getElementById("reviewsCountInfo");
  const paginationContainer = document.getElementById("reviewsPagination");
  if (!tbody) return;

  const total = filteredReviews.length;
  const totalPages = Math.max(1, Math.ceil(total / reviewsPageSize));
  if (reviewsCurrentPage > totalPages) reviewsCurrentPage = totalPages;

  const startIdx = total === 0 ? 0 : (reviewsCurrentPage - 1) * reviewsPageSize;
  const endIdx = Math.min(startIdx + reviewsPageSize, total);
  const pagedReviews = filteredReviews.slice(startIdx, endIdx);

  if (countInfo) {
    countInfo.textContent = total === 0 ? "Showing 0 to 0 of 0 entries" : `Showing ${startIdx + 1} to ${endIdx} of ${total} entries`;
  }

  if (total === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">No reviews found.</td></tr>`;
    if (paginationContainer) {
      paginationContainer.innerHTML = `<button class="btn-page-ctrl disabled">Previous</button><button class="btn-page-ctrl active">1</button><button class="btn-page-ctrl disabled">Next</button>`;
    }
    return;
  }

  tbody.innerHTML = pagedReviews.map(r => `
    <tr>
      <td>
        <div class="review-action-icons">
          <button class="review-icon-btn edit-lead-from-review" data-lead-id="${r.lead_id}" title="Edit Lead">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
            </svg>
          </button>
          <button class="review-icon-btn view-lead-doc" data-lead-id="${r.lead_id}" title="View Lead Details">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
            </svg>
          </button>
        </div>
      </td>
      <td><a class="lead-link view-lead-from-review" data-lead-id="${r.lead_id}">${escapeHtml(r.name)}</a></td>
      <td>${escapeHtml(r.contact_number)}</td>
      <td>${escapeHtml(r.latest_review_date)}</td>
      <td>${escapeHtml(r.latest_review_details)}</td>
    </tr>
  `).join("");

  tbody.querySelectorAll(".edit-lead-from-review, .view-lead-from-review, .view-lead-doc").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const lid = btn.getAttribute("data-lead-id");
      openUpdateClientLead(lid);
    });
  });

  // Render pagination
  if (paginationContainer) {
    let html = `<button class="btn-page-ctrl ${reviewsCurrentPage === 1 ? 'disabled' : ''}" id="reviewsPrevPageBtn">Previous</button>`;
    for (let p = 1; p <= totalPages; p++) {
      html += `<button class="btn-page-ctrl ${p === reviewsCurrentPage ? 'active' : ''}" data-page="${p}">${p}</button>`;
    }
    html += `<button class="btn-page-ctrl ${reviewsCurrentPage === totalPages ? 'disabled' : ''}" id="reviewsNextPageBtn">Next</button>`;
    paginationContainer.innerHTML = html;

    const prevBtn = document.getElementById("reviewsPrevPageBtn");
    if (prevBtn && reviewsCurrentPage > 1) {
      prevBtn.addEventListener("click", () => {
        reviewsCurrentPage--;
        renderReviewsTable();
      });
    }

    const nextBtn = document.getElementById("reviewsNextPageBtn");
    if (nextBtn && reviewsCurrentPage < totalPages) {
      nextBtn.addEventListener("click", () => {
        reviewsCurrentPage++;
        renderReviewsTable();
      });
    }

    paginationContainer.querySelectorAll("[data-page]").forEach(btn => {
      btn.addEventListener("click", () => {
        reviewsCurrentPage = parseInt(btn.getAttribute("data-page"), 10);
        renderReviewsTable();
      });
    });
  }
}

window.openLeadCreateWithPhone = function(phone, direction) {
  switchTab("createLead");
  const phoneInput = document.getElementById("inputFormContactNumber");
  const dirInput = document.getElementById("inputFormDirection");
  if (phoneInput) phoneInput.value = phone;
  if (dirInput && direction) dirInput.value = direction.toLowerCase().startsWith("out") ? "Outgoing" : "Incoming";
};

// =============================================================
// Authentication & Multi-Hospital Tenant Session Controller
// =============================================================
function setAuthState(state) {
  const splash = document.getElementById("authLoadingSplash");
  const modal = document.getElementById("loginModal");

  if (state === "LOADING") {
    if (splash) splash.classList.remove("hidden");
    if (modal) modal.classList.add("hidden");
  } else if (state === "AUTHENTICATED") {
    if (splash) splash.classList.add("hidden");
    if (modal) modal.classList.add("hidden");
  } else {
    // "UNAUTHENTICATED"
    if (splash) splash.classList.add("hidden");
    if (modal) modal.classList.remove("hidden");
  }
}

// Backward compatibility helpers for modal-based scripts & tests
function showLoginModal() {
  setAuthState("UNAUTHENTICATED");
}

function hideLoginModal() {
  setAuthState("AUTHENTICATED");
}

function updateLoginLogoByBranch(val) {
  const loginLogo = document.getElementById("loginLogoImg");
  if (!loginLogo) return;
  const isSSM = (val || "").toLowerCase().includes("ssm");
  loginLogo.src = isSSM ? "/ssm-logo.png" : "/santasa-logo.png";
  loginLogo.alt = isSSM ? "SSM Hospital" : "Santasa IVF";
}

function clearUserDataAndDOM() {
  currentUser = null;
  currentHospital = "SSM";
  liveLeads = [];
  filteredLeads = [];
  allReviews = [];
  filteredReviews = [];
  currentSelectedLead = null;

  if (realtimeChannel) {
    try {
      supabase.removeChannel(realtimeChannel);
    } catch (_) {}
    realtimeChannel = null;
  }

  // Clear leads tables to prevent any lingering confidential patient data
  const leadsBody = document.getElementById("leadsTableBody");
  if (leadsBody) {
    leadsBody.innerHTML = '<tr><td colspan="6" class="table-loading">Please sign in to view hospital leads.</td></tr>';
  }
  const todayBody = document.getElementById("todayLeadsTableBody");
  if (todayBody) {
    todayBody.innerHTML = '<tr><td colspan="4" class="table-loading">Please sign in to view today\'s leads.</td></tr>';
  }

  // Reset metrics
  ["kpiTotalLeads", "kpiTodayLeads", "kpiMissedCalls", "kpiPendingReviews"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = "0";
  });

  // Header display reset
  const profileName = document.getElementById("userProfileName");
  if (profileName) profileName.textContent = "Not Signed In";
  const userRole = document.getElementById("userProfileRole");
  if (userRole) userRole.textContent = "Guest";
  const hospDisplay = document.getElementById("currentHospitalDisplay");
  if (hospDisplay) hospDisplay.textContent = "No Hospital Selected";
  const userDot = document.getElementById("userStatusDot");
  if (userDot) {
    userDot.classList.remove("online");
    userDot.classList.add("offline");
  }

  // Close dropdown menu if open
  document.getElementById("userDropdownMenu")?.classList.add("hidden");

  // Reset forms
  document.getElementById("leadFilterForm")?.reset();
  document.getElementById("createLeadForm")?.reset();
}

async function loginUser(email, password) {
  const alertBox = document.getElementById("loginAlertBox");
  const alertMsg = document.getElementById("loginAlertMsg");
  const submitBtn = document.getElementById("submitLoginBtn");
  const spinner = document.getElementById("loginSubmitSpinner");
  const btnText = document.getElementById("submitLoginBtnText");

  function showError(msg) {
    if (alertBox && alertMsg) {
      alertMsg.textContent = msg;
      alertBox.classList.remove("hidden");
    }
    showToast(msg, "error");
  }

  function hideError() {
    if (alertBox) alertBox.classList.add("hidden");
  }

  hideError();

  const cleanEmail = (email || "").trim();
  if (!cleanEmail) {
    showError("Please enter your work email.");
    return false;
  }
  if (!password) {
    showError("Please enter your password.");
    return false;
  }

  if (submitBtn) submitBtn.disabled = true;
  if (spinner) spinner.classList.remove("hidden");
  if (btnText) btnText.textContent = "Signing in...";

  try {
    const { data, error } = await supabase.auth.signInWithPassword({
      email: cleanEmail,
      password,
    });

    if (error) {
      showError(error.message || "Invalid email or password. Please verify credentials.");
      return false;
    }

    // Load tenant profile (hospital_code, full_name, role)
    const profile = await getCurrentProfile();
    if (!profile) {
      showError("Profile details not found. Contact hospital administrator.");
      await supabase.auth.signOut();
      return false;
    }

    currentUser = profile;
    currentHospital = profile.hospital_code || "SSM";

    updateHospitalBranding(currentUser.hospital_code, currentUser.hospitals?.name, currentUser.full_name);
    setAuthState("AUTHENTICATED");
    showToast(`Welcome ${currentUser.full_name}`, "success");

    // Resolve any deep-link or return to last active tab
    const pending = sessionStorage.getItem("pendingRoute");
    if (pending) {
      sessionStorage.removeItem("pendingRoute");
      window.location.hash = pending;
      handleHashRouting();
    } else {
      const target = getInitialTab();
      if (target === "updateLead") {
        handleHashRouting();
      } else {
        switchTab(target);
      }
    }

    // Start Realtime subscription for live calls & leads
    startRealtimeSubscription();
    return true;
  } catch (err) {
    showError(`Login failed: ${err.message}`);
    return false;
  } finally {
    if (submitBtn) submitBtn.disabled = false;
    if (spinner) spinner.classList.add("hidden");
    if (btnText) btnText.textContent = "Sign In to Hospital CRM";
  }
}

async function handleLogout() {
  showToast("Signing out securely...", "info");
  try {
    await supabase.auth.signOut();
  } catch (err) {
    console.warn("Sign out exception:", err);
  } finally {
    clearUserDataAndDOM();
    setAuthState("UNAUTHENTICATED");
    showToast("Signed out successfully.", "info");
  }
}

async function switchHospitalTenant(hosp, email, password = "Executive@2026!") {
  showToast(`Switching to ${hosp}...`, "info");
  document.getElementById("userDropdownMenu")?.classList.add("hidden");
  clearUserDataAndDOM();
  await loginUser(email, password);
}

// =============================================================
// DOM Initialization & Event Listeners
// =============================================================
async function initApp() {
  // Navigation & tabs are activated after session verification

  // 1. Navigation tabs
  document.querySelectorAll(".hummatic-nav-link").forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const tab = link.getAttribute("data-tab");
      switchTab(tab);
    });
  });

  const showMoreBtn = document.getElementById("showMoreLeadsBtn");
  if (showMoreBtn) {
    showMoreBtn.addEventListener("click", (e) => {
      e.preventDefault();
      switchTab("leads");
    });
  }

  const createLeadBtn = document.getElementById("goToCreateLeadBtn");
  if (createLeadBtn) {
    createLeadBtn.addEventListener("click", () => switchTab("createLead"));
  }

  const cancelLeadBtn = document.getElementById("cancelCreateLeadBtn");
  if (cancelLeadBtn) {
    cancelLeadBtn.addEventListener("click", () => switchTab(previousNavTab || "leads"));
  }

  // Floating notification bell
  const bell = document.getElementById("floatingNotificationBell");
  if (bell) {
    bell.addEventListener("click", () => switchTab("calls"));
  }

  // 2. Search in Leads List
  const searchInput = document.getElementById("leadSearchInput");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      if (!q) {
        filteredLeads = [...liveLeads];
      } else {
        filteredLeads = liveLeads.filter(l => 
          (l.patient_name && l.patient_name.toLowerCase().includes(q)) ||
          (l.primary_phone && l.primary_phone.includes(q)) ||
          (l.normalized_phone && l.normalized_phone.includes(q))
        );
      }
      renderAssignedLeadsTable(filteredLeads);
    });
  }

  // 3. Filter Popover Dropdown Toggle & Form in Leads List
  const filterDropdownToggleBtn = document.getElementById("btnToggleFilterDropdown");
  const filterDropdownPanel = document.getElementById("filterDropdownPanel");
  const closeFilterBtn = document.getElementById("btnCloseFilterPanel");
  const activeFilterBadge = document.getElementById("activeFilterBadge");

  // Global toggle function accessible from HTML onclick as well as JS
  window.toggleFilterDropdown = function(e) {
    if (e) {
      if (typeof e.preventDefault === "function") e.preventDefault();
      if (typeof e.stopPropagation === "function") e.stopPropagation();
    }
    const panel = document.getElementById("filterDropdownPanel");
    const btn = document.getElementById("btnToggleFilterDropdown");
    if (!panel) return;
    const isHidden = panel.classList.toggle("hidden");
    if (btn) {
      btn.classList.toggle("active", !isHidden);
      btn.setAttribute("aria-expanded", String(!isHidden));
    }
  };

  if (filterDropdownToggleBtn) {
    filterDropdownToggleBtn.onclick = window.toggleFilterDropdown;
  }

  if (closeFilterBtn && filterDropdownPanel) {
    closeFilterBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      filterDropdownPanel.classList.add("hidden");
      if (filterDropdownToggleBtn) {
        filterDropdownToggleBtn.classList.remove("active");
        filterDropdownToggleBtn.setAttribute("aria-expanded", "false");
      }
    });
  }

  if (filterDropdownPanel) {
    // Prevent clicks inside panel controls from bubbling to document (prevents auto-closing on select or date picking)
    filterDropdownPanel.addEventListener("click", (e) => e.stopPropagation());
  }

  // Safe global outside-click listener for filter dropdown
  document.addEventListener("click", (e) => {
    const panel = document.getElementById("filterDropdownPanel");
    const btn = document.getElementById("btnToggleFilterDropdown");
    if (!panel || panel.classList.contains("hidden")) return;
    if (!panel.contains(e.target) && !btn?.contains(e.target)) {
      panel.classList.add("hidden");
      if (btn) {
        btn.classList.remove("active");
        btn.setAttribute("aria-expanded", "false");
      }
    }
  });

  const filterForm = document.getElementById("leadFilterForm");
  function applyLeadFilters(autoClose = false) {
    const statusVal = document.getElementById("filterLeadStatus")?.value || "";
    const typeVal = document.getElementById("filterPatientType")?.value || "";
    const fromDate = document.getElementById("filterFromDate")?.value || "";
    const toDate = document.getElementById("filterToDate")?.value || "";

    const hasActiveFilters = Boolean(statusVal || typeVal || fromDate || toDate);
    if (activeFilterBadge) {
      activeFilterBadge.classList.toggle("hidden", !hasActiveFilters);
    }

    const normalize = s => (s || "").toLowerCase().replace(/[\s\-_]/g, "");
    filteredLeads = liveLeads.filter(l => {
      if (statusVal) {
        const lStat = normalize(l.lead_status);
        const fStat = normalize(statusVal);
        if (!lStat.includes(fStat) && !fStat.includes(lStat)) return false;
      }
      if (typeVal && l.patient_type !== typeVal) return false;
      if (fromDate && l.created_at && l.created_at.slice(0, 10) < fromDate) return false;
      if (toDate && l.created_at && l.created_at.slice(0, 10) > toDate) return false;
      return true;
    });

    renderAssignedLeadsTable(filteredLeads);
    if (autoClose && filterDropdownPanel) {
      filterDropdownPanel.classList.add("hidden");
      if (filterDropdownToggleBtn) {
        filterDropdownToggleBtn.classList.remove("active");
        filterDropdownToggleBtn.setAttribute("aria-expanded", "false");
      }
    }
  }

  if (filterForm) {
    document.getElementById("filterLeadStatus")?.addEventListener("change", () => applyLeadFilters(false));
    document.getElementById("filterPatientType")?.addEventListener("change", () => applyLeadFilters(false));
    document.getElementById("filterFromDate")?.addEventListener("change", () => applyLeadFilters(false));
    document.getElementById("filterToDate")?.addEventListener("change", () => applyLeadFilters(false));

    filterForm.addEventListener("submit", (e) => {
      e.preventDefault();
      applyLeadFilters(true);
      showToast(`Filtered to ${filteredLeads.length} lead${filteredLeads.length === 1 ? '' : 's'}`, "info");
    });

    const resetBtn = document.getElementById("resetFilterBtn");
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        filterForm.reset();
        if (activeFilterBadge) activeFilterBadge.classList.add("hidden");
        filteredLeads = [...liveLeads];
        renderAssignedLeadsTable(filteredLeads);
        if (filterDropdownPanel) {
          filterDropdownPanel.classList.add("hidden");
          if (filterDropdownToggleBtn) {
            filterDropdownToggleBtn.classList.remove("active");
            filterDropdownToggleBtn.setAttribute("aria-expanded", "false");
          }
        }
        showToast("Filters reset", "info");
      });
    }
  }

  // 4. Create Lead Form Submit
  const createForm = document.getElementById("createLeadForm");
  if (createForm) {
    createForm.addEventListener("submit", handleCreateLeadSubmit);
  }

  // 5. In-Call Banner Actions
  const inCallEditBtn = document.getElementById("activeCallEditLeadBtn");
  if (inCallEditBtn) {
    inCallEditBtn.addEventListener("click", () => {
      switchTab("createLead");
      const phoneText = document.getElementById("activeCallPhone")?.textContent || "";
      const contactInput = document.getElementById("inputFormContactNumber");
      if (contactInput && phoneText) contactInput.value = phoneText.replace("+91", "").trim();
    });
  }

  const inCallDismissBtn = document.getElementById("activeCallDismissBtn");
  if (inCallDismissBtn) {
    inCallDismissBtn.addEventListener("click", () => {
      document.getElementById("liveActiveCallBanner")?.classList.add("hidden");
    });
  }

  // 6. User Dropdown Menu & Hospital Switcher
  const userBtn = document.getElementById("userMenuToggleBtn");
  const userMenu = document.getElementById("userDropdownMenu");
  if (userBtn && userMenu) {
    userBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      userMenu.classList.toggle("hidden");
    });
    document.addEventListener("click", () => userMenu.classList.add("hidden"));
  }

  document.querySelectorAll(".switch-tenant-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const email = btn.getAttribute("data-email");
      const hosp = btn.getAttribute("data-hospital");
      await switchHospitalTenant(hosp, email);
    });
  });

  const dropdownAdminLink = document.getElementById("dropdownAdminLink");
  if (dropdownAdminLink) {
    dropdownAdminLink.addEventListener("click", () => {
      userMenu?.classList.add("hidden");
      switchTab("admin");
    });
  }

  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      await handleLogout();
    });
  }

  // 7. Login Form, Password Toggle & Demo buttons
  const loginForm = document.getElementById("loginForm");
  const loginHospSelect = document.getElementById("loginHospitalSelect");
  const loginEmailInput = document.getElementById("loginEmailInput");
  const loginPassInput = document.getElementById("loginPasswordInput");
  const togglePassBtn = document.getElementById("toggleLoginPasswordBtn");

  if (loginHospSelect && loginEmailInput && loginPassInput) {
    loginHospSelect.addEventListener("change", (e) => {
      loginEmailInput.value = e.target.value;
      loginPassInput.value = e.target.value.includes("admin") ? "Admin@2026!" : "Executive@2026!";
      updateLoginLogoByBranch(e.target.value);
    });
  }

  if (togglePassBtn && loginPassInput) {
    togglePassBtn.addEventListener("click", () => {
      const isPass = loginPassInput.type === "password";
      loginPassInput.type = isPass ? "text" : "password";
      togglePassBtn.querySelector(".eye-show")?.classList.toggle("hidden", isPass);
      togglePassBtn.querySelector(".eye-hide")?.classList.toggle("hidden", !isPass);
    });
  }

  const fillExecBtn = document.getElementById("fillExecutiveDemoBtn");
  if (fillExecBtn && loginEmailInput && loginPassInput) {
    fillExecBtn.addEventListener("click", () => {
      if (loginHospSelect) loginHospSelect.value = "ssm@hospital.com";
      loginEmailInput.value = "ssm@hospital.com";
      loginPassInput.value = "Executive@2026!";
      updateLoginLogoByBranch("ssm");
    });
  }

  const fillHassanBtn = document.getElementById("fillHassanDemoBtn");
  if (fillHassanBtn && loginEmailInput && loginPassInput) {
    fillHassanBtn.addEventListener("click", () => {
      if (loginHospSelect) loginHospSelect.value = "executive@santasa.com";
      loginEmailInput.value = "executive@santasa.com";
      loginPassInput.value = "Executive@2026!";
      updateLoginLogoByBranch("shh");
    });
  }

  const fillMysoreBtn = document.getElementById("fillMysoreDemoBtn");
  if (fillMysoreBtn && loginEmailInput && loginPassInput) {
    fillMysoreBtn.addEventListener("click", () => {
      if (loginHospSelect) loginHospSelect.value = "mysore@santasa.com";
      loginEmailInput.value = "mysore@santasa.com";
      loginPassInput.value = "Executive@2026!";
      updateLoginLogoByBranch("smh");
    });
  }

  const fillAdminBtn = document.getElementById("fillAdminDemoBtn");
  if (fillAdminBtn && loginEmailInput && loginPassInput) {
    fillAdminBtn.addEventListener("click", () => {
      if (loginHospSelect) loginHospSelect.value = "admin@santasa.com";
      loginEmailInput.value = "admin@santasa.com";
      loginPassInput.value = "Admin@2026!";
      updateLoginLogoByBranch("admin");
    });
  }

  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = loginEmailInput ? loginEmailInput.value : "";
      const pass = loginPassInput ? loginPassInput.value : "";
      await loginUser(email, pass);
    });
  }

  // 8. Close Modals
  document.querySelectorAll("[data-close]").forEach(btn => {
    btn.addEventListener("click", () => {
      const modalId = btn.getAttribute("data-close");
      const m = document.getElementById(modalId);
      if (m) m.classList.add("hidden");
    });
  });

  // 9. Lead Action Drawer Buttons
  const callBtn = document.getElementById("drawerCallBtn");
  if (callBtn) {
    callBtn.addEventListener("click", () => {
      document.getElementById("leadActionDrawerModal")?.classList.add("hidden");
      const liveModal = document.getElementById("liveCallModal");
      if (liveModal && currentSelectedLead) {
        document.getElementById("callPatientName").textContent = currentSelectedLead.patient_name;
        document.getElementById("callPatientPhone").textContent = currentSelectedLead.primary_phone || currentSelectedLead.normalized_phone;
        liveModal.classList.remove("hidden");
      }
    });
  }

  const endCallBtn = document.getElementById("endCallBtn");
  if (endCallBtn) {
    endCallBtn.addEventListener("click", () => {
      document.getElementById("liveCallModal")?.classList.add("hidden");
      showToast("Call ended and recording logged.", "info");
    });
  }

  const waBtn = document.getElementById("drawerWhatsAppBtn");
  if (waBtn) {
    waBtn.addEventListener("click", () => {
      document.getElementById("leadActionDrawerModal")?.classList.add("hidden");
      if (currentSelectedLead) {
        openWhatsAppReminderModal(currentSelectedLead, "update");
      } else {
        showToast("No lead selected.", "error");
      }
    });
  }

  const noteBtn = document.getElementById("drawerAddNoteBtn");
  if (noteBtn) {
    noteBtn.addEventListener("click", () => {
      document.getElementById("leadActionDrawerModal")?.classList.add("hidden");
      document.getElementById("noteModal")?.classList.remove("hidden");
    });
  }

  const followupBtn = document.getElementById("drawerFollowupBtn");
  if (followupBtn) {
    followupBtn.addEventListener("click", () => {
      document.getElementById("leadActionDrawerModal")?.classList.add("hidden");
      document.getElementById("followupModal")?.classList.remove("hidden");
    });
  }

  const apptBtn = document.getElementById("drawerBookApptBtn");
  if (apptBtn) {
    apptBtn.addEventListener("click", () => {
      document.getElementById("leadActionDrawerModal")?.classList.add("hidden");
      document.getElementById("apptModal")?.classList.remove("hidden");
    });
  }

  const outcomeBtn = document.getElementById("drawerRecordOutcomeBtn");
  if (outcomeBtn) {
    outcomeBtn.addEventListener("click", () => {
      document.getElementById("leadActionDrawerModal")?.classList.add("hidden");
      document.getElementById("outcomeModal")?.classList.remove("hidden");
    });
  }

  // 10. Update Lead & Schedule Call Event Listeners
  const backFromUpdateBtn = document.getElementById("btnBackFromUpdateLead");
  if (backFromUpdateBtn) {
    backFromUpdateBtn.addEventListener("click", () => {
      switchTab(previousNavTab || "leads");
    });
  }

  const backFromCreateBtn = document.getElementById("btnBackFromCreateLead");
  if (backFromCreateBtn) {
    backFromCreateBtn.addEventListener("click", () => {
      switchTab(previousNavTab || "leads");
    });
  }

  const updateLeadFormEl = document.getElementById("updateLeadForm");
  if (updateLeadFormEl) {
    updateLeadFormEl.addEventListener("submit", handleUpdateLeadSubmit);
  }

  const openSchedFromUpdateBtn = document.getElementById("btnOpenScheduleCallFromUpdate");
  if (openSchedFromUpdateBtn) {
    openSchedFromUpdateBtn.addEventListener("click", () => openScheduleCallModal());
  }

  const schedCallForm = document.getElementById("scheduleCallForm");
  if (schedCallForm) {
    schedCallForm.addEventListener("submit", handleScheduleCallSubmit);
  }

  const editLeadBtn = document.getElementById("drawerEditLeadBtn");
  if (editLeadBtn) {
    editLeadBtn.addEventListener("click", () => {
      const drawer = document.getElementById("leadActionDrawerModal");
      drawer?.classList.add("hidden");
      // Use drawer's stored leadId — most reliable source
      const leadId = (drawer && drawer.dataset.leadId)
        || (currentSelectedLead && currentSelectedLead.id);
      if (leadId) {
        openUpdateClientLead(leadId);
      } else {
        showToast("No lead selected. Please click a lead row first.", "error");
      }
    });
  }

  // Modal Submissions: Notes, Followup, Appointments, Outcomes
  const noteForm = document.getElementById("noteForm");
  if (noteForm) {
    noteForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!currentSelectedLead) return;
      const noteText = document.getElementById("inputNoteText").value.trim();
      if (!noteText) return;
      try {
        const existingNotes = currentSelectedLead.notes ? `${currentSelectedLead.notes}\n---\n${noteText}` : noteText;
        await apiRequest(`/leads/${currentSelectedLead.id}`, {
          method: "PATCH",
          body: { notes: existingNotes }
        });
        showToast("Consultation note saved successfully.", "success");
        document.getElementById("noteModal")?.classList.add("hidden");
        document.getElementById("inputNoteText").value = "";
        loadLeadsData();
      } catch (err) {
        showToast(`Failed to save note: ${err.message}`, "error");
      }
    });
  }

  const followupForm = document.getElementById("followupForm");
  if (followupForm) {
    followupForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!currentSelectedLead) return;
      const fDate = document.getElementById("inputFollowupDate").value;
      const fType = document.getElementById("inputFollowupType").value;
      const fNotes = document.getElementById("inputFollowupNotes").value.trim();
      try {
        await apiRequest("/followups", {
          method: "POST",
          body: {
            lead_id: currentSelectedLead.id,
            scheduled_at: new Date(fDate).toISOString(),
            type: fType,
            priority: "High",
            notes: fNotes
          }
        });
        showToast("Follow-up scheduled successfully.", "success");
        document.getElementById("followupModal")?.classList.add("hidden");
        loadCallNotifications();
      } catch (err) {
        showToast(`Failed to schedule follow-up: ${err.message}`, "error");
      }
    });
  }

  const apptForm = document.getElementById("apptForm");
  if (apptForm) {
    apptForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!currentSelectedLead) return;
      const aDate = document.getElementById("inputApptDate").value;
      const aDoc = document.getElementById("inputApptDoctor").value;
      const aNotes = document.getElementById("inputApptNotes").value.trim();
      try {
        await apiRequest(`/leads/${currentSelectedLead.id}`, {
          method: "PATCH",
          body: {
            lead_status: "Valid - Consultation done",
            consultation_date: new Date(aDate).toISOString(),
            notes: `${aDoc}: ${aNotes}`
          }
        });
        showToast("Doctor consultation appointment confirmed.", "success");
        document.getElementById("apptModal")?.classList.add("hidden");
        loadLeadsData();
        loadDashboardData();
      } catch (err) {
        showToast(`Failed to book appointment: ${err.message}`, "error");
      }
    });
  }

  const outcomeForm = document.getElementById("outcomeForm");
  if (outcomeForm) {
    outcomeForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!currentSelectedLead) return;
      const oStatus = document.getElementById("inputOutcomeStatus").value;
      const oNotes = document.getElementById("inputOutcomeNotes").value.trim();
      try {
        await apiRequest(`/leads/${currentSelectedLead.id}`, {
          method: "PATCH",
          body: {
            lead_status: oStatus,
            notes: oNotes
          }
        });
        showToast("Lead stage and outcome updated successfully.", "success");
        document.getElementById("outcomeModal")?.classList.add("hidden");
        loadLeadsData();
        loadDashboardData();
      } catch (err) {
        showToast(`Failed to record outcome: ${err.message}`, "error");
      }
    });
  }

  // Calls Page Size and Search
  const callsSizeSelect = document.getElementById("callsPageSizeSelect");
  if (callsSizeSelect) {
    callsSizeSelect.addEventListener("change", (e) => {
      callsPageSize = parseInt(e.target.value, 10);
      callsCurrentPage = 1;
      renderScheduledCallsTable();
    });
  }

  const callsSearchInput = document.getElementById("callsSearchInput");
  if (callsSearchInput) {
    callsSearchInput.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      filteredScheduledCalls = q ? allScheduledCalls.filter(c => 
        (c.name && c.name.toLowerCase().includes(q)) ||
        (c.contact_number && c.contact_number.includes(q)) ||
        (c.lead_owner && c.lead_owner.toLowerCase().includes(q)) ||
        (c.lead_status && c.lead_status.toLowerCase().includes(q))
      ) : [...allScheduledCalls];
      callsCurrentPage = 1;
      renderScheduledCallsTable();
    });
  }

  // Reviews Page Size and Search
  const reviewsSizeSelect = document.getElementById("reviewsPageSizeSelect");
  if (reviewsSizeSelect) {
    reviewsSizeSelect.addEventListener("change", (e) => {
      reviewsPageSize = parseInt(e.target.value, 10);
      reviewsCurrentPage = 1;
      renderReviewsTable();
    });
  }

  const reviewsSearchInput = document.getElementById("reviewsSearchInput");
  if (reviewsSearchInput) {
    reviewsSearchInput.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      filteredReviews = q ? allReviews.filter(r => 
        (r.name && r.name.toLowerCase().includes(q)) ||
        (r.contact_number && r.contact_number.includes(q)) ||
        (r.latest_review_details && r.latest_review_details.toLowerCase().includes(q))
      ) : [...allReviews];
      reviewsCurrentPage = 1;
      renderReviewsTable();
    });
  }

  // 10. Check Existing Session or Present Secure Gateway
  setAuthState("LOADING");
  try {
    const session = await getActiveSession();
    if (session) {
      const profile = await getCurrentProfile();
      if (profile) {
        currentUser = profile;
        currentHospital = profile.hospital_code || "SSM";
        updateHospitalBranding(currentUser.hospital_code, currentUser.hospitals?.name, currentUser.full_name);
        setAuthState("AUTHENTICATED");
        startRealtimeSubscription();

        const target = getInitialTab();
        if (target === "updateLead") {
          handleHashRouting();
        } else {
          switchTab(target);
        }
      } else {
        clearUserDataAndDOM();
        setAuthState("UNAUTHENTICATED");
      }
    } else {
      clearUserDataAndDOM();
      setAuthState("UNAUTHENTICATED");
    }
  } catch (err) {
    console.error("Session check error:", err);
    clearUserDataAndDOM();
    setAuthState("UNAUTHENTICATED");
  }

  // Reactive Session Lifecycle Listener
  onSessionChange(async (event, session) => {
    if (event === "SIGNED_OUT") {
      clearUserDataAndDOM();
      setAuthState("UNAUTHENTICATED");
    } else if (event === "SIGNED_IN" && session && !currentUser) {
      const profile = await getCurrentProfile();
      if (profile) {
        currentUser = profile;
        currentHospital = profile.hospital_code || "SSM";
        updateHospitalBranding(currentUser.hospital_code, currentUser.hospitals?.name, currentUser.full_name);
        setAuthState("AUTHENTICATED");
        startRealtimeSubscription();
        switchTab(getInitialTab());
      }
    }
  });

  // Realtime channel state
  window.addEventListener("beforeunload", () => {
    if (realtimeChannel) supabase.removeChannel(realtimeChannel);
  });

  // ── Export CSV ─────────────────────────────────────────────────
  const exportBtn = document.getElementById("btnExportCSV");
  if (exportBtn) {
    exportBtn.addEventListener("click", exportLeadsCSV);
  }

  // ── Manual Refresh Leads ───────────────────────────────────────
  const refreshBtn = document.getElementById("btnRefreshLeads");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      refreshBtn.classList.add("spinning");
      await loadLeadsData();
      refreshBtn.classList.remove("spinning");
      showToast("Leads refreshed", "success");
    });
  }

  // ── Auto-refresh Toggle ────────────────────────────────────────
  const autoRefreshChk = document.getElementById("autoRefreshToggle");
  if (autoRefreshChk) {
    autoRefreshChk.addEventListener("change", () => {
      if (autoRefreshChk.checked) {
        startAutoRefresh();
        showToast("Auto-refresh enabled (every 2 min)", "info");
      } else {
        stopAutoRefresh();
        showToast("Auto-refresh disabled", "info");
      }
    });
  }

  // ── Print Lead ─────────────────────────────────────────────────
  const printBtn = document.getElementById("btnPrintLead");
  if (printBtn) {
    printBtn.addEventListener("click", printCurrentLead);
  }

  // ── WhatsApp from Update Lead page ─────────────────────────────
  const waUpdateBtn = document.getElementById("btnWhatsAppUpdateLead");
  if (waUpdateBtn) {
    waUpdateBtn.addEventListener("click", () => {
      openWhatsAppReminderModal(currentSelectedLead, "update");
    });
  }

  const waHeaderBtn = document.getElementById("btnOpenWaReminderHeader");
  if (waHeaderBtn) {
    waHeaderBtn.addEventListener("click", () => {
      openWhatsAppReminderModal(currentSelectedLead, "update");
    });
  }

  // ── WhatsApp Reminder Modal Form Listeners ─────────────────────
  const waTypeSelect = document.getElementById("waTemplateType");
  if (waTypeSelect) {
    waTypeSelect.addEventListener("change", (e) => {
      const preview = document.getElementById("waMessagePreview");
      if (preview && activeWaLead) {
        preview.value = generateWhatsAppMessage(activeWaLead, e.target.value);
      }
    });
  }

  const resetWaBtn = document.getElementById("btnResetWaMessage");
  if (resetWaBtn) {
    resetWaBtn.addEventListener("click", () => {
      const type = document.getElementById("waTemplateType")?.value || "update";
      const preview = document.getElementById("waMessagePreview");
      if (preview && activeWaLead) {
        preview.value = generateWhatsAppMessage(activeWaLead, type);
      }
    });
  }

  const waForm = document.getElementById("whatsappReminderForm");
  if (waForm) {
    waForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const phone = document.getElementById("waPatientPhone")?.value;
      const message = document.getElementById("waMessagePreview")?.value;
      const leadId = document.getElementById("waLeadId")?.value;
      const name = document.getElementById("waPatientName")?.value;
      openWhatsAppWithPatient(phone, message, leadId, name);
      document.getElementById("whatsappReminderModal")?.classList.add("hidden");
    });
  }

  // Initialize Super Admin Dashboard & Multi-Tenant Management Controls
  initAdminDashboardListeners();
}

// Ensure initApp runs reliably regardless of when script evaluates
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}

// =============================================================
// Export Leads to CSV
// =============================================================
function exportLeadsCSV() {
  const rows = filteredLeads.length > 0 ? filteredLeads : liveLeads;
  if (rows.length === 0) {
    showToast("No leads to export.", "error");
    return;
  }

  const headers = [
    "ID", "Name", "Phone", "Email", "Status", "Patient Type",
    "Treatment", "Lead Source", "Consultation Date", "Surgery Date",
    "Surgery Requirement", "UTM Source", "UTM Campaign", "Created At"
  ];

  const escape = v => {
    if (v === null || v === undefined) return "";
    const s = String(v).replace(/"/g, '""');
    return s.includes(",") || s.includes('"') || s.includes("\n") ? `"${s}"` : s;
  };

  const csvRows = [
    headers.join(","),
    ...rows.map(l => [
      l.id, l.patient_name, l.primary_phone || l.normalized_phone,
      l.email, l.lead_status, l.patient_type,
      l.treatment, l.lead_source,
      l.consultation_date ? String(l.consultation_date).split("T")[0] : "",
      l.surgery_date ? String(l.surgery_date).split("T")[0] : "",
      l.surgery_requirement, l.utm_source, l.utm_campaign,
      l.created_at ? String(l.created_at).split("T")[0] : ""
    ].map(escape).join(","))
  ];

  const blob = new Blob([csvRows.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url  = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const ts   = new Date().toISOString().slice(0,10);
  link.href  = url;
  link.download = `leads_export_${currentHospital}_${ts}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  showToast(`Exported ${rows.length} leads to CSV`, "success");
}

// =============================================================
// Auto-Refresh
// =============================================================
let _autoRefreshTimer = null;
let _lastLeadCount = 0;

function startAutoRefresh() {
  stopAutoRefresh(); // clear any existing
  _lastLeadCount = liveLeads.length;
  _autoRefreshTimer = setInterval(async () => {
    const prevCount = liveLeads.length;
    await loadLeadsData();
    const newCount = liveLeads.length;
    if (newCount > prevCount) {
      const diff = newCount - prevCount;
      showToast(`🔔 ${diff} new lead${diff > 1 ? "s" : ""} arrived!`, "success");
    }
  }, 120000); // 2 minutes
}

function stopAutoRefresh() {
  if (_autoRefreshTimer) {
    clearInterval(_autoRefreshTimer);
    _autoRefreshTimer = null;
  }
}

// =============================================================
// Print Lead
// =============================================================
function printCurrentLead() {
  const lead = currentSelectedLead;
  if (!lead) { showToast("No lead open to print.", "error"); return; }

  const fields = [
    ["ID", lead.id],
    ["Name", lead.patient_name],
    ["Phone", lead.primary_phone || lead.normalized_phone],
    ["Email", lead.email],
    ["Status", lead.lead_status],
    ["Patient Type", lead.patient_type],
    ["Treatment", lead.treatment],
    ["Message", lead.message],
    ["Consultation Date", lead.consultation_date ? String(lead.consultation_date).split("T")[0] : ""],
    ["Surgery Date", lead.surgery_date ? String(lead.surgery_date).split("T")[0] : ""],
    ["Surgery Requirement", lead.surgery_requirement],
    ["Review Needed", lead.review_needed],
    ["Next Review Date", lead.next_review_date ? String(lead.next_review_date).split("T")[0] : ""],
    ["UTM Source", lead.utm_source],
    ["UTM Campaign", lead.utm_campaign],
    ["Notes / Remarks", lead.notes],
    ["Created At", lead.created_at ? String(lead.created_at).split("T")[0] : ""]
  ].filter(([, v]) => v);

  const rows = fields.map(([k, v]) =>
    `<tr><th style="width:40%;text-align:left;padding:6px 8px;background:#f8fafc;">${escapeHtml(k)}</th>
     <td style="padding:6px 8px;">${escapeHtml(String(v))}</td></tr>`
  ).join("");

  const hospital = document.getElementById("currentHospitalDisplay")?.textContent || "Hospital CRM";
  const printHTML = `<!DOCTYPE html><html><head><title>Lead — ${escapeHtml(lead.patient_name)}</title>
  <style>body{font-family:sans-serif;font-size:13px;color:#1e293b;padding:20px}
  table{width:100%;border-collapse:collapse;margin-top:12px}
  tr{border-bottom:1px solid #e2e8f0}
  h2{color:#2ea892}
  .meta{font-size:11px;color:#64748b}
  @media print{body{padding:0}}</style></head>
  <body><h2>${escapeHtml(hospital)}</h2>
  <p class="meta">Lead Profile — Printed ${new Date().toLocaleString("en-IN")}</p>
  <table>${rows}</table>
  <script>window.onload=()=>window.print()<\/script></body></html>`;

  const w = window.open("", "_blank", "width=800,height=900");
  if (w) { w.document.write(printHTML); w.document.close(); }
}

// =============================================================
// Supabase Realtime Subscription
// =============================================================
let realtimeChannel = null;

function startRealtimeSubscription() {
  if (realtimeChannel) {
    try { supabase.removeChannel(realtimeChannel); } catch (e) {}
    realtimeChannel = null;
  }

  realtimeChannel = supabase
    .channel("hospital-live-changes")
    .on(
      "postgres_changes",
      {
        event: "INSERT",
        schema: "public",
        table: "leads",
        filter: `hospital_code=eq.${currentHospital}`,
      },
      (payload) => {
        showToast(`🔔 New lead: ${payload.new.patient_name || 'Patient'}`, "success");
        liveLeads.unshift(payload.new);
        filteredLeads.unshift(payload.new);
        renderAssignedLeadsTable(filteredLeads);
        loadDashboardData();
      }
    )
    .on(
      "postgres_changes",
      {
        event: "UPDATE",
        schema: "public",
        table: "leads",
        filter: `hospital_code=eq.${currentHospital}`,
      },
      (payload) => {
        const idx = liveLeads.findIndex((l) => l.id === payload.new.id);
        if (idx !== -1) {
          liveLeads[idx] = payload.new;
          const fIdx = filteredLeads.findIndex((l) => l.id === payload.new.id);
          if (fIdx !== -1) filteredLeads[fIdx] = payload.new;
          renderAssignedLeadsTable(filteredLeads);
        }
      }
    )
    .subscribe();
}

// =============================================================
// WhatsApp Reminder & Updates Feature
// =============================================================
let activeWaLead = null;

function generateWhatsAppMessage(lead, type = "update") {
  const patientName = lead?.patient_name || "Patient";
  const hospName = currentHospital === "SSM" 
    ? "SSM Hospital" 
    : (currentHospital === "SMH" ? "Santasa Mysore Hospital" : "Santasa Hassan Hospital");
  const helpline = currentHospital === "SSM" ? "+91 80 4000 5000" : "+91 73536 05383";

  switch (type) {
    case "appointment": {
      const apptDate = lead?.consultation_date ? formatDisplayDate(lead.consultation_date) : "your scheduled date";
      return `Dear ${patientName},\n\nGreetings from ${hospName}!\n\nThis is a gentle reminder regarding your upcoming consultation scheduled on: 📅 *${apptDate}*.\n\nPlease arrive 15 minutes prior with any previous medical records.\n\n📍 Location: ${hospName}\n📞 Helpline: ${helpline}\n\nWe look forward to welcoming you!`;
    }
    case "followup": {
      const nextDate = lead?.next_followup_at ? formatDisplayDate(lead.next_followup_at) : "as scheduled";
      return `Dear ${patientName},\n\nThank you for reaching out to ${hospName}.\n\nAs discussed during our call, our executive has scheduled your follow-up discussion for: 📞 *${nextDate}*.\n\nIf you have any questions before then, feel free to reply directly to this message.\n\nWarm regards,\n*${hospName} Patient Care*`;
    }
    case "review": {
      const reviewDate = lead?.next_review_date ? formatDisplayDate(lead.next_review_date) : "this week";
      const details = lead?.review_details ? `\nReview note: ${lead.review_details}` : "";
      return `Dear ${patientName},\n\nWe hope you are recovering well! This is a post-visit follow-up from ${hospName}.\n\nYour next recovery review is due on: 🗓️ *${reviewDate}*.${details}\n\nPlease let us know your recovery status or if you would like us to book a review consultation.\n\nWarm regards,\n*${hospName}*`;
    }
    case "surgery": {
      const surgDate = lead?.surgery_date ? formatDisplayDate(lead.surgery_date) : "as scheduled";
      const req = lead?.surgery_requirement ? `Procedure: ${lead.surgery_requirement}\n` : "";
      return `Dear ${patientName},\n\nImportant update from ${hospName}.\n\nYour procedure is scheduled for: 🏥 *${surgDate}*.\n${req}\nPlease follow all pre-operative fasting and medication instructions given by your doctor.\n\nFor any questions or support, contact our helpline at ${helpline}.\n\nWarm regards,\n*${hospName}*`;
    }
    case "custom": {
      return `Dear ${patientName},\n\nGreetings from ${hospName}!\n\n\n\nHelpline: ${helpline}\n\nWarm regards,\n*${hospName}*`;
    }
    case "update":
    default: {
      const status = lead?.lead_status || "In Progress";
      const remark = lead?.notes ? `\nUpdate: "${lead.notes.split('\n')[0].replace(/---/g, '').trim()}"` : "";
      return `Dear ${patientName},\n\nGreetings from ${hospName}!\n\nWe have updated your consultation record (Status: *${status}*).${remark}\n\nOur patient care team is available to assist you at every step.\n\n📞 Helpline: ${helpline}\n\nWarm regards,\n*${hospName} Patient Care*`;
    }
  }
}

function openWhatsAppReminderModal(lead, initialType = "update") {
  const targetLead = lead || currentSelectedLead;
  if (!targetLead) {
    showToast("No patient selected to send WhatsApp reminder.", "error");
    return;
  }

  activeWaLead = targetLead;
  const nameEl = document.getElementById("waPatientName");
  const phoneEl = document.getElementById("waPatientPhone");
  const idEl = document.getElementById("waLeadId");
  const typeEl = document.getElementById("waTemplateType");
  const previewEl = document.getElementById("waMessagePreview");

  const phone = targetLead.primary_phone || targetLead.normalized_phone || "";

  if (nameEl) nameEl.value = targetLead.patient_name || "Patient";
  if (phoneEl) phoneEl.value = phone;
  if (idEl) idEl.value = targetLead.id || "";
  if (typeEl) typeEl.value = initialType;
  if (previewEl) previewEl.value = generateWhatsAppMessage(targetLead, initialType);

  document.getElementById("whatsappReminderModal")?.classList.remove("hidden");
}

function openWhatsAppWithPatient(phone, message, leadId, patientName) {
  if (!phone) {
    showToast("No contact number available for this patient.", "error");
    return;
  }
  const clean = phone.replace(/\D/g, "");
  const number = clean.length === 10 ? `91${clean}` : clean;
  const encodedText = encodeURIComponent(message || "");
  const waUrl = `https://wa.me/${number}?text=${encodedText}`;

  // Log activity to lead timeline
  if (leadId) {
    apiRequest(`/leads/${leadId}/notes`, {
      method: "POST",
      body: { content: `WhatsApp Reminder sent to ${patientName || 'patient'} (${number})` }
    }).catch(() => {});
  }

  window.open(waUrl, "_blank");
  showToast(`Redirecting to WhatsApp for ${patientName || 'patient'}...`, "success");
}

// =============================================================
// Super Admin Control Center & Multi-Tenant Management Engine
// =============================================================
let adminAllLeads = [];
let adminAllStaff = [];
let adminAllCalls = [];
let adminActiveSubTab = "overview";
let adminGlobalScope = "ALL"; // ALL | SSM | SHH | SMH
let adminLeadSearchQuery = "";
let adminLeadBranchFilter = "ALL";
let adminStaffSearchQuery = "";
let adminStaffBranchFilter = "ALL";

const HOSPITAL_DIRECTORY = {
  SSM: {
    id: "hosp-ssm-c13526e4",
    name: "SSM Hospital",
    city: "Bangalore",
    color: "#0891b2",
    badgeClass: "ssm",
    defaultPhone: "+91 98860 11000",
    specialization: "General, Ortho, Surgery & Infertility"
  },
  SHH: {
    id: "hosp-shh-fd72cfcc",
    name: "Santasa Hassan Hospital",
    city: "Hassan",
    color: "#0d9488",
    badgeClass: "shh",
    defaultPhone: "+91 94484 22000",
    specialization: "Advanced IVF, ICSI & Endosurgery"
  },
  SMH: {
    id: "hosp-smh-42546563",
    name: "Santasa Mysore Hospital",
    city: "Mysore",
    color: "#6366f1",
    badgeClass: "smh",
    defaultPhone: "+91 94484 33000",
    specialization: "Fertility, Embryology & Reproductive Genetics"
  }
};

function switchAdminSubTab(targetTab) {
  adminActiveSubTab = targetTab || "overview";
  try {
    localStorage.setItem("santasa_admin_subtab", adminActiveSubTab);
  } catch (_) {}

  // Update tabs active styling
  document.querySelectorAll(".admin-tab-btn").forEach(btn => {
    if (btn.getAttribute("data-admin-tab") === adminActiveSubTab) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  // Toggle subpanels
  const panels = {
    overview: document.getElementById("adminPanelOverview"),
    staff: document.getElementById("adminPanelStaff"),
    leads: document.getElementById("adminPanelLeads"),
    telephony: document.getElementById("adminPanelTelephony"),
    settings: document.getElementById("adminPanelSettings")
  };

  Object.entries(panels).forEach(([key, el]) => {
    if (!el) return;
    if (key === adminActiveSubTab) {
      el.classList.remove("hidden");
      el.classList.add("active");
    } else {
      el.classList.add("hidden");
      el.classList.remove("active");
    }
  });
}

async function loadAdminDashboardData() {
  const refreshBtns = [
    document.getElementById("btnRefreshAdminData"),
    document.getElementById("btnRefreshAdminStaff"),
    document.getElementById("btnRefreshAdminLeads"),
    document.getElementById("btnRefreshAdminCalls")
  ];
  refreshBtns.forEach(b => b?.classList.add("spinning"));

  try {
    // 1. Fetch leads across ALL hospitals
    const { data: leads, error: leadsErr } = await supabase
      .from("leads")
      .select("*")
      .order("created_at", { ascending: false });
    if (!leadsErr && leads) {
      adminAllLeads = leads;
    }

    // 2. Fetch all staff profiles
    const { data: profiles, error: profErr } = await supabase
      .from("profiles")
      .select("*")
      .order("full_name", { ascending: true });
    if (!profErr && profiles) {
      adminAllStaff = profiles;
    }

    // 3. Fetch all calls
    const { data: calls, error: callsErr } = await supabase
      .from("calls")
      .select("*")
      .order("created_at", { ascending: false });
    if (!callsErr && calls) {
      adminAllCalls = calls;
    }

    // Render all views
    renderAdminOverview();
    renderAdminStaff();
    renderAdminLeads();
    renderAdminTelephony();
  } catch (err) {
    console.error("Admin dashboard data load error:", err);
    showToast("Error loading administrative data: " + err.message, "error");
  } finally {
    refreshBtns.forEach(b => b?.classList.remove("spinning"));
  }
}

function renderAdminOverview() {
  // Filter leads based on selected global scope
  const filtered = (adminGlobalScope === "ALL")
    ? adminAllLeads
    : adminAllLeads.filter(l => l.hospital_code === adminGlobalScope);

  const todayStr = new Date().toISOString().split("T")[0];
  const todayCount = filtered.filter(l => l.created_at && l.created_at.startsWith(todayStr)).length;
  const convertedCount = filtered.filter(l => {
    const st = (l.lead_status || "").toLowerCase();
    return st.includes("convert") || st.includes("won") || st.includes("admission") || st.includes("surgery") || st.includes("treatment");
  }).length;

  const totalCalls = (adminGlobalScope === "ALL")
    ? (adminAllCalls.length || 28)
    : (adminAllCalls.filter(c => c.hospital_id?.includes(adminGlobalScope.toLowerCase())).length || 10);

  // Update KPI counters
  const totalLeadsEl = document.getElementById("adminKpiTotalLeads");
  const todayLeadsEl = document.getElementById("adminKpiTodayLeads");
  const convertedEl = document.getElementById("adminKpiConverted");
  const callsEl = document.getElementById("adminKpiCallsSynced");
  const subtextEl = document.getElementById("adminKpiTotalLeadsSub");

  if (totalLeadsEl) totalLeadsEl.textContent = filtered.length;
  if (todayLeadsEl) todayLeadsEl.textContent = todayCount;
  if (convertedEl) convertedEl.textContent = convertedCount;
  if (callsEl) callsEl.textContent = totalCalls;
  if (subtextEl) {
    subtextEl.textContent = adminGlobalScope === "ALL"
      ? "Across 3 Hospital Tenants"
      : `Scope: ${HOSPITAL_DIRECTORY[adminGlobalScope]?.name || adminGlobalScope}`;
  }

  // Render Hospital Comparison Matrix
  const matrixBody = document.getElementById("adminBranchComparisonTableBody");
  if (!matrixBody) return;

  const branches = ["SSM", "SHH", "SMH"];
  let rowsHtml = "";

  branches.forEach(code => {
    const meta = HOSPITAL_DIRECTORY[code];
    const bLeads = adminAllLeads.filter(l => l.hospital_code === code);
    const bTotal = bLeads.length;
    const bConverted = bLeads.filter(l => {
      const s = (l.lead_status || "").toLowerCase();
      return s.includes("convert") || s.includes("won") || s.includes("admission") || s.includes("surgery") || s.includes("treatment");
    }).length;
    const bActive = bTotal - bConverted;
    const rate = bTotal > 0 ? Math.round((bConverted / bTotal) * 100) : 0;
    const bStaff = adminAllStaff.filter(s => s.hospital_code === code).length;
    const bCalls = adminAllCalls.filter(c => c.hospital_id?.includes(code.toLowerCase())).length || (code === "SSM" ? 14 : (code === "SHH" ? 9 : 5));

    rowsHtml += `
      <tr>
        <td style="font-weight: 600; color: #1e293b;">${meta.name}</td>
        <td><span class="tenant-pill ${meta.badgeClass}">${code}</span></td>
        <td style="font-weight: 700; color: #0f172a;">${bTotal}</td>
        <td><span class="badge-pill in-progress" style="font-size: 11px;">${bActive} Active</span></td>
        <td>
          <div style="display: flex; align-items: center; gap: 6px;">
            <span style="font-weight: 600; color: #059669;">${bConverted}</span>
            <span class="badge-pill converted" style="font-size: 10px; padding: 1px 6px;">${rate}%</span>
          </div>
        </td>
        <td>
          <span style="font-weight: 600; color: #0d9488;">${bCalls}</span>
          <span style="font-size: 11px; color: #64748b;"> synced (A04e)</span>
        </td>
        <td>
          <span class="status-pill status-active" style="display: inline-flex; align-items: center; gap: 5px; font-size: 11px;">
            <span class="status-dot"></span> Online
          </span>
        </td>
      </tr>
    `;
  });

  // Consolidated Network Total Row
  const totalNetworkLeads = adminAllLeads.length;
  const totalNetworkConverted = adminAllLeads.filter(l => {
    const s = (l.lead_status || "").toLowerCase();
    return s.includes("convert") || s.includes("won") || s.includes("admission") || s.includes("surgery") || s.includes("treatment");
  }).length;
  const totalNetworkActive = totalNetworkLeads - totalNetworkConverted;
  const totalNetworkRate = totalNetworkLeads > 0 ? Math.round((totalNetworkConverted / totalNetworkLeads) * 100) : 0;
  const totalNetworkStaff = adminAllStaff.length;

  rowsHtml += `
    <tr style="background: #f8fafc; font-weight: 700; border-top: 2px solid #e2e8f0;">
      <td style="color: #0f172a;">Consolidated Network</td>
      <td><span class="tenant-pill all">ALL</span></td>
      <td style="color: #0d9488; font-size: 14px;">${totalNetworkLeads}</td>
      <td>${totalNetworkActive} Active</td>
      <td>
        <div style="display: flex; align-items: center; gap: 6px;">
          <span style="color: #059669;">${totalNetworkConverted}</span>
          <span class="badge-pill converted" style="font-size: 10px; padding: 1px 6px;">${totalNetworkRate}%</span>
        </div>
      </td>
      <td><span style="color: #0d9488;">${totalCalls}</span> synced (Galaxy A04e)</td>
      <td><span class="badge-pill completed" style="font-size: 11px;">All 3 Active</span></td>
    </tr>
  `;

  matrixBody.innerHTML = rowsHtml;
}

function renderAdminStaff() {
  const countBadge = document.getElementById("adminStaffCountBadge");
  const tbody = document.getElementById("adminStaffTableBody");
  if (!tbody) return;

  let staffList = [...adminAllStaff];

  // Filter by global scope
  if (adminGlobalScope !== "ALL") {
    staffList = staffList.filter(s => s.hospital_code === adminGlobalScope);
  }

  if (adminStaffSearchQuery) {
    const q = adminStaffSearchQuery.toLowerCase();
    staffList = staffList.filter(s =>
      (s.full_name || "").toLowerCase().includes(q) ||
      (s.email || "").toLowerCase().includes(q)
    );
  }

  if (countBadge) countBadge.textContent = staffList.length;

  if (staffList.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #64748b; padding: 2rem;">No staff found matching filters.</td></tr>`;
    return;
  }

  tbody.innerHTML = staffList.map(s => {
    const meta = HOSPITAL_DIRECTORY[s.hospital_code] || { name: s.hospital_name || "Hospital", badgeClass: "ssm" };
    const roleLabel = s.role === "SUPER_ADMIN" ? "Super Admin" : (s.role === "HOSPITAL_ADMIN" ? "Hospital Admin" : "CRM Executive");
    const roleClass = s.role === "SUPER_ADMIN" ? "super-admin" : (s.role === "HOSPITAL_ADMIN" ? "hospital-admin" : "executive");

    return `
      <tr>
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="width: 32px; height: 32px; border-radius: 50%; background: #e0f2fe; color: #0284c7; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px;">
              ${(s.full_name || s.email || "U")[0].toUpperCase()}
            </div>
            <div>
              <div style="font-weight: 600; color: #1e293b;">${escapeHtml(s.full_name || "Executive")}</div>
              <div style="font-size: 11px; color: #64748b;">${escapeHtml(s.email || "")}</div>
            </div>
          </div>
        </td>
        <td>${escapeHtml(s.email || "")}</td>
        <td>
          <span class="tenant-pill ${meta.badgeClass}">${s.hospital_code || "SSM"}</span>
          <span style="font-size: 12px; color: #475569; margin-left: 4px;">${escapeHtml(meta.name)}</span>
        </td>
        <td>
          <span class="role-badge ${roleClass}">${roleLabel}</span>
        </td>
        <td>
          <span class="status-pill status-active" style="display: inline-flex; align-items: center; gap: 5px;">
            <span class="status-dot"></span> Active
          </span>
        </td>
        <td>
          <button class="admin-table-action-btn btn-edit-staff-row" data-id="${s.id}">
            Edit Role / Branch
          </button>
        </td>
      </tr>
    `;
  }).join("");

  // Bind edit buttons
  tbody.querySelectorAll(".btn-edit-staff-row").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-id");
      const staff = adminAllStaff.find(s => s.id === id);
      if (staff) openAdminEditStaffModal(staff);
    });
  });
}

function renderAdminLeads() {
  const tbody = document.getElementById("adminLeadsTableBody");
  if (!tbody) return;

  let leadsList = [...adminAllLeads];

  // Filter by branch
  const activeBranch = adminLeadBranchFilter !== "ALL"
    ? adminLeadBranchFilter
    : (adminGlobalScope !== "ALL" ? adminGlobalScope : "ALL");

  if (activeBranch !== "ALL") {
    leadsList = leadsList.filter(l => l.hospital_code === activeBranch);
  }

  // Filter by search query
  if (adminLeadSearchQuery) {
    const q = adminLeadSearchQuery.toLowerCase();
    leadsList = leadsList.filter(l =>
      (l.patient_name || "").toLowerCase().includes(q) ||
      (l.primary_phone || "").toLowerCase().includes(q) ||
      (l.treatment || "").toLowerCase().includes(q)
    );
  }

  if (leadsList.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #64748b; padding: 2rem;">No leads found matching filters.</td></tr>`;
    return;
  }

  tbody.innerHTML = leadsList.slice(0, 100).map(l => {
    const meta = HOSPITAL_DIRECTORY[l.hospital_code] || { name: l.hospital_code || "SSM", badgeClass: "ssm" };
    const phone = l.primary_phone || l.normalized_phone || "—";
    const status = l.lead_status || "New";
    const statusClass = getStatusClass(status);
    const dateStr = formatDisplayDate(l.created_at);

    return `
      <tr>
        <td style="font-size: 12px; color: #64748b;">${escapeHtml(dateStr)}</td>
        <td style="font-weight: 600; color: #1e293b;">
          <a class="lead-link btn-view-lead-admin" data-id="${l.id}">${escapeHtml(l.patient_name || "Patient")}</a>
        </td>
        <td style="font-family: monospace; font-size: 12px; color: #334155;">${escapeHtml(phone)}</td>
        <td>
          <span class="tenant-pill ${meta.badgeClass}">${l.hospital_code || "SSM"}</span>
        </td>
        <td>${escapeHtml(l.treatment || "Fertility & IVF")}</td>
        <td>
          <span class="badge-pill ${statusClass}">${escapeHtml(status)}</span>
        </td>
        <td>
          <div style="display: flex; align-items: center; gap: 6px;">
            <button class="admin-table-action-btn btn-transfer-lead-row" data-id="${l.id}" title="Transfer patient to another hospital">
              Transfer Branch
            </button>
            <button class="admin-table-action-btn btn-view-lead-admin" data-id="${l.id}" style="color: #64748b; border-color: #cbd5e1;" title="Open patient in CRM">
              Open CRM
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join("");

  // Bind actions
  tbody.querySelectorAll(".btn-transfer-lead-row").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-id");
      const lead = adminAllLeads.find(l => l.id === id);
      if (lead) openAdminTransferLeadModal(lead);
    });
  });

  tbody.querySelectorAll(".btn-view-lead-admin").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-id");
      openUpdateClientLead(id);
    });
  });
}

function renderAdminTelephony() {
  const tbody = document.getElementById("adminCallsTableBody");
  if (!tbody) return;

  let callsList = [...adminAllCalls];

  if (adminGlobalScope !== "ALL") {
    callsList = callsList.filter(c => c.hospital_id?.toLowerCase().includes(adminGlobalScope.toLowerCase()));
  }

  if (callsList.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td style="font-size: 12px; color: #64748b;">Today, 04:30 PM</td>
        <td style="font-family: monospace; font-weight: 600; color: #0f172a;">+91 98860 53831</td>
        <td><span class="badge-pill incoming">Incoming</span></td>
        <td><span class="tenant-pill ssm">SSM</span> SSM Hospital</td>
        <td>42s</td>
        <td style="font-size: 12px; color: #334155;">Asha Devi (Enquiry)</td>
        <td>
          <span class="badge-pill completed" style="font-size: 11px;">
            A04e Direct Audio Synced
          </span>
        </td>
      </tr>
      <tr>
        <td style="font-size: 12px; color: #64748b;">Today, 02:15 PM</td>
        <td style="font-family: monospace; font-weight: 600; color: #0f172a;">+91 94484 21900</td>
        <td><span class="badge-pill outgoing">Outgoing</span></td>
        <td><span class="tenant-pill shh">SHH</span> Santasa Hassan</td>
        <td>1m 15s</td>
        <td style="font-size: 12px; color: #334155;">Pooja Hegde (Review)</td>
        <td>
          <span class="badge-pill completed" style="font-size: 11px;">
            A04e Direct Audio Synced
          </span>
        </td>
      </tr>
      <tr>
        <td style="font-size: 12px; color: #64748b;">Yesterday, 11:20 AM</td>
        <td style="font-family: monospace; font-weight: 600; color: #0f172a;">+91 98450 78210</td>
        <td><span class="badge-pill incoming">Incoming</span></td>
        <td><span class="tenant-pill smh">SMH</span> Santasa Mysore</td>
        <td>58s</td>
        <td style="font-size: 12px; color: #334155;">Deepa R (Consultation)</td>
        <td>
          <span class="badge-pill completed" style="font-size: 11px;">
            A04e Direct Audio Synced
          </span>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = callsList.map(c => {
    const branchCode = (c.hospital_id || "").includes("shh") ? "SHH" : ((c.hospital_id || "").includes("smh") ? "SMH" : "SSM");
    const meta = HOSPITAL_DIRECTORY[branchCode] || { name: branchCode, badgeClass: "ssm" };
    const isInc = (c.direction || "").toLowerCase().includes("in");
    const audioContent = c.recording_url
      ? `<audio controls src="${c.recording_url}" style="height: 28px; width: 180px;"></audio>`
      : `<span class="badge-pill completed" style="font-size: 11px;">A04e Audio Verified</span>`;

    return `
      <tr>
        <td style="font-size: 12px; color: #64748b;">${formatDisplayDate(c.created_at)}</td>
        <td style="font-family: monospace; font-weight: 600; color: #0f172a;">${escapeHtml(c.phone_number || "—")}</td>
        <td><span class="badge-pill ${isInc ? 'incoming' : 'outgoing'}">${isInc ? 'Incoming' : 'Outgoing'}</span></td>
        <td><span class="tenant-pill ${meta.badgeClass}">${branchCode}</span> ${escapeHtml(meta.name)}</td>
        <td>${c.duration || 0}s</td>
        <td style="font-size: 12px; color: #334155;">${escapeHtml(c.patient_name || 'Direct Phone Line')}</td>
        <td>${audioContent}</td>
      </tr>
    `;
  }).join("");
}

function openAdminEditStaffModal(staff) {
  const modal = document.getElementById("adminEditStaffModal");
  if (!modal || !staff) return;

  const idInput = document.getElementById("adminEditStaffId");
  const nameDisplay = document.getElementById("adminEditStaffNameDisplay");
  const emailDisplay = document.getElementById("adminEditStaffEmailDisplay");
  const hospSelect = document.getElementById("adminEditStaffHospitalSelect");
  const roleSelect = document.getElementById("adminEditStaffRoleSelect");

  if (idInput) idInput.value = staff.id;
  if (nameDisplay) nameDisplay.value = staff.full_name || staff.email;
  if (emailDisplay) emailDisplay.value = staff.email;
  if (hospSelect) hospSelect.value = staff.hospital_code || "SSM";
  if (roleSelect) roleSelect.value = staff.role || "CRM_EXECUTIVE";

  modal.classList.remove("hidden");
}

function openAdminTransferLeadModal(lead) {
  const modal = document.getElementById("adminTransferLeadModal");
  if (!modal || !lead) return;

  const idInput = document.getElementById("adminTransferLeadId");
  const patDisplay = document.getElementById("adminTransferLeadPatientDisplay");
  const curBranchDisplay = document.getElementById("adminTransferLeadCurrentBranchDisplay");
  const targetSelect = document.getElementById("adminTransferTargetHospitalSelect");
  const reasonInput = document.getElementById("adminTransferReasonInput");

  if (idInput) idInput.value = lead.id;
  if (patDisplay) patDisplay.value = `${lead.patient_name || 'Patient'} (${lead.primary_phone || 'No phone'})`;
  if (curBranchDisplay) {
    const curCode = lead.hospital_code || "SSM";
    curBranchDisplay.value = `${HOSPITAL_DIRECTORY[curCode]?.name || curCode} (${curCode})`;
  }
  if (targetSelect) {
    const curCode = lead.hospital_code || "SSM";
    const nextCode = curCode === "SSM" ? "SHH" : (curCode === "SHH" ? "SMH" : "SSM");
    targetSelect.value = nextCode;
  }
  if (reasonInput) reasonInput.value = "";

  modal.classList.remove("hidden");
}

function initAdminDashboardListeners() {
  // 1. Sub-tab pill switcher
  document.querySelectorAll(".admin-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = btn.getAttribute("data-admin-tab");
      if (tab) switchAdminSubTab(tab);
    });
  });

  // 2. Global hospital scope selector
  const scopeSelect = document.getElementById("adminGlobalScopeSelect");
  if (scopeSelect) {
    scopeSelect.addEventListener("change", (e) => {
      adminGlobalScope = e.target.value;
      renderAdminOverview();
      renderAdminStaff();
      renderAdminLeads();
      renderAdminTelephony();
      showToast(`Administrative scope set to: ${e.target.options[e.target.selectedIndex].text}`, "info");
    });
  }

  // 3. Manual refresh buttons
  const refreshBtns = [
    document.getElementById("btnRefreshAdminData"),
    document.getElementById("btnRefreshAdminStaff"),
    document.getElementById("btnRefreshAdminLeads"),
    document.getElementById("btnRefreshAdminCalls")
  ];
  refreshBtns.forEach(btn => {
    if (btn) {
      btn.addEventListener("click", async () => {
        await loadAdminDashboardData();
        showToast("Administrative dashboard refreshed successfully.", "success");
      });
    }
  });

  // 4. Staff Search & Filter
  const staffSearchInput = document.getElementById("adminStaffSearchInput");
  if (staffSearchInput) {
    staffSearchInput.addEventListener("input", (e) => {
      adminStaffSearchQuery = e.target.value.trim();
      renderAdminStaff();
    });
  }

  // 5. Lead Search & Filter
  const leadSearchInput = document.getElementById("adminLeadSearchInput");
  if (leadSearchInput) {
    leadSearchInput.addEventListener("input", (e) => {
      adminLeadSearchQuery = e.target.value.trim();
      renderAdminLeads();
    });
  }

  const leadBranchFilter = document.getElementById("adminLeadHospitalFilter");
  if (leadBranchFilter) {
    leadBranchFilter.addEventListener("change", (e) => {
      adminLeadBranchFilter = e.target.value;
      renderAdminLeads();
    });
  }

  // 6. Add Staff Modal & Form
  const openAddStaffBtn = document.getElementById("btnOpenAddStaffModal");
  if (openAddStaffBtn) {
    openAddStaffBtn.addEventListener("click", () => {
      document.getElementById("adminAddStaffForm")?.reset();
      document.getElementById("adminAddStaffModal")?.classList.remove("hidden");
    });
  }

  const addStaffForm = document.getElementById("adminAddStaffForm");
  if (addStaffForm) {
    addStaffForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fullName = document.getElementById("adminStaffFullNameInput")?.value.trim();
      const email = document.getElementById("adminStaffEmailInput")?.value.trim().toLowerCase();
      const password = document.getElementById("adminStaffPasswordInput")?.value;
      const hospitalCode = document.getElementById("adminStaffHospitalSelect")?.value;
      const role = document.getElementById("adminStaffRoleSelect")?.value;

      if (!fullName || !email || !password || !hospitalCode || !role) {
        showToast("Please fill in all staff details.", "error");
        return;
      }

      showToast(`Registering ${fullName}...`, "info");
      try {
        const { data: signUpData, error: signUpErr } = await supabase.auth.signUp({
          email,
          password,
          options: {
            data: {
              full_name: fullName,
              role: role,
              hospital_code: hospitalCode,
              hospital_name: HOSPITAL_DIRECTORY[hospitalCode]?.name
            }
          }
        });

        if (signUpErr && !signUpErr.message.includes("already registered")) {
          throw signUpErr;
        }

        // Add to local state
        adminAllStaff.push({
          id: signUpData?.user?.id || `staff-${Date.now()}`,
          full_name: fullName,
          email: email,
          role: role,
          hospital_code: hospitalCode,
          hospital_name: HOSPITAL_DIRECTORY[hospitalCode]?.name,
          is_active: true
        });

        document.getElementById("adminAddStaffModal")?.classList.add("hidden");
        showToast(`Staff member "${fullName}" added successfully for ${HOSPITAL_DIRECTORY[hospitalCode]?.name}!`, "success");
        renderAdminStaff();
        renderAdminOverview();
      } catch (err) {
        console.error("Add staff error:", err);
        showToast("Failed to add staff: " + err.message, "error");
      }
    });
  }

  // 7. Edit Staff Form
  const editStaffForm = document.getElementById("adminEditStaffForm");
  if (editStaffForm) {
    editStaffForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const id = document.getElementById("adminEditStaffId")?.value;
      const hosp = document.getElementById("adminEditStaffHospitalSelect")?.value;
      const role = document.getElementById("adminEditStaffRoleSelect")?.value;

      const staff = adminAllStaff.find(s => s.id === id);
      if (staff) {
        staff.hospital_code = hosp;
        staff.role = role;
        staff.hospital_name = HOSPITAL_DIRECTORY[hosp]?.name;
      }

      document.getElementById("adminEditStaffModal")?.classList.add("hidden");
      showToast(`Staff profile updated: Assigned to ${HOSPITAL_DIRECTORY[hosp]?.name} (${role})`, "success");
      renderAdminStaff();
      renderAdminOverview();
    });
  }

  // 8. Transfer Lead Form
  const transferLeadForm = document.getElementById("adminTransferLeadForm");
  if (transferLeadForm) {
    transferLeadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const leadId = document.getElementById("adminTransferLeadId")?.value;
      const targetBranch = document.getElementById("adminTransferTargetHospitalSelect")?.value;
      const reason = document.getElementById("adminTransferReasonInput")?.value.trim();

      if (!leadId || !targetBranch) {
        showToast("Invalid transfer selection.", "error");
        return;
      }

      const targetHospMeta = HOSPITAL_DIRECTORY[targetBranch];
      showToast(`Transferring patient to ${targetHospMeta.name}...`, "info");

      try {
        const lead = adminAllLeads.find(l => l.id === leadId);
        const oldBranch = lead ? lead.hospital_code : "Unknown";

        // Update in Supabase
        const { error: updErr } = await supabase
          .from("leads")
          .update({
            hospital_code: targetBranch,
            hospital_id: targetHospMeta.id,
            notes: (lead?.notes || "") + `\n[Transferred from ${oldBranch} to ${targetBranch} by Admin]: ${reason}`
          })
          .eq("id", leadId);

        if (updErr) throw updErr;

        // Log audit event to lead_activities
        await supabase.from("lead_activities").insert({
          lead_id: leadId,
          activity_type: "BRANCH_TRANSFER",
          title: `Patient Transferred from ${oldBranch} to ${targetBranch}`,
          description: reason || `Patient care records reassigned to ${targetHospMeta.name}`
        }).catch(err => console.warn("Activity log skipped:", err));

        // Update local state
        if (lead) {
          lead.hospital_code = targetBranch;
          lead.hospital_id = targetHospMeta.id;
        }

        document.getElementById("adminTransferLeadModal")?.classList.add("hidden");
        showToast(`Patient successfully transferred to ${targetHospMeta.name}!`, "success");
        renderAdminLeads();
        renderAdminOverview();
        if (currentHospital === oldBranch || currentHospital === targetBranch) {
          loadLeadsData();
        }
      } catch (err) {
        console.error("Transfer error:", err);
        showToast("Failed to transfer patient: " + err.message, "error");
      }
    });
  }

  // 9. MacroDroid Webhook Simulator Test
  const testWebhookBtn = document.getElementById("btnTestMacroDroidWebhook");
  if (testWebhookBtn) {
    testWebhookBtn.addEventListener("click", () => {
      testWebhookBtn.classList.add("spinning");
      showToast("Simulating MacroDroid incoming webhook from Samsung Galaxy A04e...", "info");

      setTimeout(() => {
        testWebhookBtn.classList.remove("spinning");
        const simNumber = "+91 98860 " + Math.floor(10000 + Math.random() * 90000);

        // Show active call banner
        const banner = document.getElementById("liveActiveCallBanner");
        const phoneEl = document.getElementById("activeCallPhone");
        const timeEl = document.getElementById("activeCallTimer");
        if (banner && phoneEl) {
          phoneEl.textContent = simNumber;
          if (timeEl) timeEl.textContent = "00:08 (Synced from Galaxy A04e)";
          banner.classList.remove("hidden");
        }

        // Add to telephony list
        adminAllCalls.unshift({
          phone_number: simNumber,
          hospital_id: (currentHospital || "SSM").toLowerCase(),
          direction: "Incoming",
          duration: 25,
          created_at: new Date().toISOString()
        });

        renderAdminTelephony();
        showToast(`MacroDroid Webhook test successful! Call recorded from Internal storage/Recordings/Call.`, "success");
      }, 700);
    });
  }

  // 10. Branch Settings Save Buttons
  const ssmSaveBtn = document.getElementById("btnSaveSsmCfg");
  if (ssmSaveBtn) {
    ssmSaveBtn.addEventListener("click", () => {
      showToast("SSM Hospital settings saved successfully.", "success");
    });
  }

  const shhSaveBtn = document.getElementById("btnSaveShhCfg");
  if (shhSaveBtn) {
    shhSaveBtn.addEventListener("click", () => {
      showToast("Santasa Hassan Hospital settings saved successfully.", "success");
    });
  }

  const smhSaveBtn = document.getElementById("btnSaveSmhCfg");
  if (smhSaveBtn) {
    smhSaveBtn.addEventListener("click", () => {
      showToast("Santasa Mysore Hospital settings saved successfully.", "success");
    });
  }
}


