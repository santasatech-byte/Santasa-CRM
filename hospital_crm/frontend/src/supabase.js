// ============================================================
// Supabase Client Singleton
// All API calls in app.js use this instead of apiRequest()
// ============================================================
import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL  = import.meta.env.VITE_SUPABASE_URL || "https://vdwpxcdpzhreonutitrc.supabase.co";
const SUPABASE_ANON = import.meta.env.VITE_SUPABASE_ANON_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkd3B4Y2RwemhyZW9udXRpdHJjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODY4MzkzMTEsImV4cCI6MjEwMjQxNTMxMX0.tAuwylQZ29cXXopfWiQlqFTaD1jE7kK6EV4un66jCJE";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});

// ── Helper: get current user's profile (hospital_code, role, etc.) ──────────
export async function getCurrentProfile() {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return null;

  const meta = user.user_metadata || {};

  try {
    const { data, error } = await supabase
      .from("profiles")
      .select("*")
      .eq("id", user.id)
      .maybeSingle();

    if (data && !error) {
      return {
        id: data.id,
        email: data.email,
        full_name: data.full_name || meta.full_name || user.email,
        role: data.role || meta.role || "CRM_EXECUTIVE",
        hospital_id: data.hospital_id,
        hospital_code: data.hospital_code || meta.hospital_code || "SSM",
        hospital_name: data.hospital_name || (data.hospital_code === "SHH" ? "Santasa Hassan Hospital" : (data.hospital_code === "SMH" ? "Santasa Mysore Hospital" : "SSM Hospital")),
        hospitals: {
          code: data.hospital_code || meta.hospital_code || "SSM",
          name: data.hospital_name || "Hospital"
        }
      };
    }
  } catch (err) {
    console.warn("Could not query profiles view, using metadata fallback:", err);
  }

  // Resilient fallback to user_metadata
  const code = meta.hospital_code || "SSM";
  const name = code === "SHH" ? "Santasa Hassan Hospital" : (code === "SMH" ? "Santasa Mysore Hospital" : "SSM Hospital");
  return {
    id: user.id,
    email: user.email,
    full_name: meta.full_name || user.email,
    role: meta.role || "CRM_EXECUTIVE",
    hospital_code: code,
    hospital_name: name,
    hospitals: {
      code: code,
      name: name
    }
  };
}

// ── Session Helpers ───────────────────────────────────────────
export async function getActiveSession() {
  try {
    const { data: { session }, error } = await supabase.auth.getSession();
    if (error) {
      console.warn("Session check error:", error);
      return null;
    }
    return session;
  } catch (err) {
    console.warn("Session retrieval failed:", err);
    return null;
  }
}

export function onSessionChange(callback) {
  return supabase.auth.onAuthStateChange((event, session) => {
    callback(event, session);
  });
}
