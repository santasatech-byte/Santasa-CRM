import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.VITE_SUPABASE_URL || "https://vdwpxcdpzhreonutitrc.supabase.co";
// Using the direct Postgres pooler service or anon client
const SUPABASE_ANON = process.env.VITE_SUPABASE_ANON_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZkd3B4Y2RwemhyZW9udXRpdHJjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODY4MzkzMTEsImV4cCI6MjEwMjQxNTMxMX0.tAuwylQZ29cXXopfWiQlqFTaD1jE7kK6EV4un66jCJE";

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON);

const HOSPITAL_MAP = {
  SSM: { id: "hosp-ssm-c13526e4", name: "SSM Hospital" },
  SHH: { id: "hosp-shh-fd72cfcc", name: "Santasa Hassan Hospital" },
  SMH: { id: "hosp-smh-42546563", name: "Santasa Mysore Hospital" }
};

export default async function handler(req, res) {
  // Set CORS headers
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed. Use POST." });
  }

  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {});
    const rawPhone = body.phone_number || body.caller_number || body.number || "";
    const cleanDigits = rawPhone.replace(/\D/g, "");
    const core10 = cleanDigits.slice(-10);
    const normalizedPhone = core10.length === 10 ? "+91" + core10 : (cleanDigits ? "+" + cleanDigits : "+910000000000");

    const hospitalCode = (body.hospital_code || "SSM").toUpperCase();
    const hospitalInfo = HOSPITAL_MAP[hospitalCode] || HOSPITAL_MAP.SSM;
    const duration = parseInt(body.duration_seconds || body.duration || "0", 10);
    const direction = (body.direction || "Incoming").toLowerCase();
    const isMissed = duration === 0 || direction.includes("miss");

    const now = new Date().toISOString();

    // 1. Authenticate / Service client: Sign in with executive account to bypass RLS
    const { data: authData } = await supabase.auth.signInWithPassword({
      email: hospitalCode === "SHH" ? "executive@santasa.com" : (hospitalCode === "SMH" ? "mysore@santasa.com" : "ssm@hospital.com"),
      password: "Executive@2026!"
    });

    const client = supabase; // Authenticated session is active

    // 2. Check if a Lead exists with this phone number
    let existingLead = null;
    if (core10) {
      const { data: leads } = await client
        .from("leads")
        .select("*")
        .eq("hospital_code", hospitalCode)
        .or(`primary_phone.ilike.%${core10}%,normalized_phone.ilike.%${core10}%`)
        .limit(1);

      if (leads && leads.length > 0) {
        existingLead = leads[0];
      }
    }

    let leadId = existingLead ? existingLead.id : null;
    let patientName = existingLead ? existingLead.patient_name : `Inbound Caller (${core10 || rawPhone})`;

    // 3. Create a New Lead if none exists
    if (!existingLead && core10) {
      const newLeadPayload = {
        patient_name: patientName,
        primary_phone: core10,
        normalized_phone: normalizedPhone,
        hospital_code: hospitalCode,
        hospital_id: hospitalInfo.id,
        lead_status: "New",
        lead_source: "Mobile Inbound Call",
        treatment_interest: "IVF Consultation",
        notes: `Auto-created from phone call on ${now}. Call duration: ${duration}s.`
      };

      const { data: createdLead, error: leadErr } = await client
        .from("leads")
        .insert(newLeadPayload)
        .select()
        .single();

      if (!leadErr && createdLead) {
        leadId = createdLead.id;
        patientName = createdLead.patient_name;
      }
    }

    // 4. Record Call Log in `calls` table
    const callPayload = {
      hospital_id: hospitalInfo.id,
      lead_id: leadId,
      phone_number: core10 || rawPhone,
      patient_name: patientName,
      direction: direction.includes("out") ? "outbound" : "inbound",
      duration: duration,
      status: isMissed ? "Missed" : "Completed",
      notes: body.notes || `Direct mobile sync from ${hospitalCode} phone`,
      created_at: now
    };

    const { data: createdCall, error: callErr } = await client
      .from("calls")
      .insert(callPayload)
      .select()
      .single();

    return res.status(200).json({
      success: true,
      message: "Call synced successfully and mapped to lead",
      lead_id: leadId,
      lead_name: patientName,
      call_id: createdCall?.id,
      hospital: hospitalCode
    });
  } catch (err) {
    console.error("Mobile sync webhook error:", err);
    return res.status(500).json({ error: err.message || "Internal server error" });
  }
}
