// Supabase Auth (minimal working setup)
// Safe to keep the anon key in frontend. NEVER put the service_role key in the browser.

const SUPABASE_URL = "https://cekzzpatfrnzoymkwfun.supabase.co";
const SUPABASE_ANON_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNla3p6cGF0ZnJuem95bWt3ZnVuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAyOTI2MDksImV4cCI6MjA4NTg2ODYwOX0.4h0F5v54kE4atLvRNNxxdnIzmddiMaiu1uNz9pbu31E";

// Load Supabase JS client from CDN (no build tools needed)
const supabaseScript = document.createElement("script");
supabaseScript.src = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2";
supabaseScript.onload = () => initAuth();
document.head.appendChild(supabaseScript);

function $(id) {
  return document.getElementById(id);
}

function setStatus(msg) {
  const el = $("authStatus");
  if (el) el.textContent = msg;
}

async function initAuth() {
  // Create client
  const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

  // Elements
  const emailEl = $("email");
  const passwordEl = $("password");

  $("btnSignUp").addEventListener("click", async () => {
    try {
      const email = emailEl.value.trim();
      const password = passwordEl.value;
      if (!email || !password) return setStatus("Enter email + password.");

      const { data, error } = await supabase.auth.signUp({ email, password });
      if (error) return setStatus(`Sign up error: ${error.message}`);

      setStatus(
        `Sign up OK.\nUser: ${data.user?.email ?? "unknown"}\n(If email confirmation is enabled, check inbox.)`
      );
    } catch (e) {
      setStatus(`Sign up exception: ${e?.message ?? e}`);
    }
  });

  $("btnSignIn").addEventListener("click", async () => {
    try {
      const email = emailEl.value.trim();
      const password = passwordEl.value;
      if (!email || !password) return setStatus("Enter email + password.");

      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) return setStatus(`Sign in error: ${error.message}`);

      setStatus(`Signed in.\nUser: ${data.user?.email ?? "unknown"}`);
    } catch (e) {
      setStatus(`Sign in exception: ${e?.message ?? e}`);
    }
  });

  $("btnMagicLink").addEventListener("click", async () => {
    try {
      const email = emailEl.value.trim();
      if (!email) return setStatus("Enter your email first.");

      // IMPORTANT: Add this URL to Supabase Auth -> URL Configuration -> Redirect URLs
      const redirectTo = window.location.origin;

      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: { emailRedirectTo: redirectTo },
      });

      if (error) return setStatus(`Magic link error: ${error.message}`);
      setStatus(`Magic link sent to ${email}.\nCheck your inbox.`);
    } catch (e) {
      setStatus(`Magic link exception: ${e?.message ?? e}`);
    }
  });

  $("btnSignOut").addEventListener("click", async () => {
    try {
      const { error } = await supabase.auth.signOut();
      if (error) return setStatus(`Sign out error: ${error.message}`);
      setStatus("Signed out.");
    } catch (e) {
      setStatus(`Sign out exception: ${e?.message ?? e}`);
    }
  });

  $("btnCallApi").addEventListener("click", async () => {
  try {
    const { data: sessionData, error: sessionErr } = await supabase.auth.getSession();
    if (sessionErr) return setStatus(`Session error: ${sessionErr.message}`);

    const token = sessionData.session?.access_token;
    if (!token) return setStatus("Not signed in. Sign in first, then call the API.");

    const res = await fetch("api/hello", {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    const text = await res.text();
    setStatus(`API status: ${res.status}\n\n${text}`);
  } catch (e) {
    setStatus(`API call exception: ${e?.message ?? e}`);
  }
});


  // Show initial session state
  const { data: sessionData } = await supabase.auth.getSession();
  setStatus(sessionData.session ? `Session active.\nUser: ${sessionData.session.user.email}` : "Not signed in.");

  // React to auth changes
  supabase.auth.onAuthStateChange((_event, session) => {
    if (session?.user?.email) {
      setStatus(`Auth changed.\nSigned in as: ${session.user.email}`);
    } else {
      setStatus("Auth changed.\nNot signed in.");
    }
  });
}
