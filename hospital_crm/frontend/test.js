/**
 * Frontend Verification Test Runner for Module 1
 */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

function runFrontendTests() {
  console.log("Starting Frontend Verification Suite for Module 1...");
  
  // 1. Verify index.html exists and contains core UI & Auth elements
  const htmlPath = path.join(__dirname, 'index.html');
  assert(fs.existsSync(htmlPath), "index.html must exist");
  const htmlContent = fs.readFileSync(htmlPath, 'utf8');

  assert(htmlContent.includes('id="loginModal"'), "Login gateway modal element must exist");
  assert(htmlContent.includes('id="loginForm"'), "Login form element must exist");
  assert(htmlContent.includes('id="submitLoginBtn"'), "Sign in button must exist");
  assert(htmlContent.includes('id="userProfileBadge"'), "Executive user profile badge must exist");
  assert(htmlContent.includes('id="logoutBtn"'), "Secure logout button must exist");
  assert(htmlContent.includes('id="authLoadingSplash"'), "Session verification splash must exist");
  console.log("✔ index.html verification passed (All primary authentication portals and layout containers present).");

  // 2. Verify CSS design system tokens and Auth styles
  const cssPath = path.join(__dirname, 'src', 'styles', 'main.css');
  assert(fs.existsSync(cssPath), "main.css must exist");
  const cssContent = fs.readFileSync(cssPath, 'utf8');

  assert(cssContent.includes("--font-sans"), "CSS variables must define typography");
  assert(cssContent.includes(".login-modal-card"), "Login modal card styles present");
  assert(cssContent.includes(".auth-splash-screen"), "Auth splash screen styles present");
  assert(cssContent.includes(".btn-toggle-password"), "Password visibility toggle styles present");
  console.log("✔ main.css verification passed (Tokens, typography, and auth gateway styles present).");

  // 3. Verify app.js logic and Session Management
  const jsPath = path.join(__dirname, 'src', 'app.js');
  assert(fs.existsSync(jsPath), "app.js must exist");
  const jsContent = fs.readFileSync(jsPath, 'utf8');

  assert(jsContent.includes("loginUser"), "Login controller exists");
  assert(jsContent.includes("handleLogout"), "Secure logout handler exists");
  assert(jsContent.includes("setAuthState"), "Session state machine exists");
  assert(jsContent.includes("switchHospitalTenant"), "Hospital tenant switcher exists");
  assert(jsContent.includes("clearUserDataAndDOM"), "Secure session memory and DOM cleaner exists");
  console.log("✔ app.js verification passed (Session management, authentication controller, and tenant isolation present).");

  console.log("\n==========================================");
  console.log("ALL 3 FRONTEND TEST SUITES PASSED (3/3)");
  console.log("==========================================");
}

runFrontendTests();
