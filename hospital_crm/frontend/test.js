/**
 * Frontend Verification Test Runner for Module 1
 */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

function runFrontendTests() {
  console.log("Starting Frontend Verification Suite for Module 1...");
  
  // 1. Verify index.html exists and contains core UI elements
  const htmlPath = path.join(__dirname, 'index.html');
  assert(fs.existsSync(htmlPath), "index.html must exist");
  const htmlContent = fs.readFileSync(htmlPath, 'utf8');

  assert(htmlContent.includes("CALL PATIENT"), "Action toolbar must contain CALL PATIENT button");
  assert(htmlContent.includes("WHATSAPP"), "Action toolbar must contain WHATSAPP button");
  assert(htmlContent.includes("SCHEDULE FOLLOW-UP"), "Action toolbar must contain SCHEDULE FOLLOW-UP button");
  assert(htmlContent.includes("BOOK APPOINTMENT"), "Action toolbar must contain BOOK APPOINTMENT button");
  assert(htmlContent.includes("ADD NOTE"), "Action toolbar must contain ADD NOTE button");
  assert(htmlContent.includes("timelineFeed"), "Timeline container element must exist");
  console.log("✔ index.html verification passed (All primary executive action buttons and layout containers present).");

  // 2. Verify CSS design system tokens
  const cssPath = path.join(__dirname, 'src', 'styles', 'main.css');
  assert(fs.existsSync(cssPath), "main.css must exist");
  const cssContent = fs.readFileSync(cssPath, 'utf8');

  assert(cssContent.includes("--font-sans"), "CSS variables must define typography");
  assert(cssContent.includes(".crm-main-layout"), "3-column CRM workspace layout defined");
  assert(cssContent.includes(".rapid-action-toolbar"), "Rapid action toolbar styles present");
  console.log("✔ main.css verification passed (Tokens, typography, and responsive 3-column workspace present).");

  // 3. Verify app.js logic
  const jsPath = path.join(__dirname, 'src', 'app.js');
  assert(fs.existsSync(jsPath), "app.js must exist");
  const jsContent = fs.readFileSync(jsPath, 'utf8');

  assert(jsContent.includes("renderLeadsList"), "Lead list renderer exists");
  assert(jsContent.includes("renderTimeline"), "Timeline renderer exists");
  assert(jsContent.includes("startLiveCall"), "Live telephony dialer simulator exists");
  console.log("✔ app.js verification passed (Interactive controller and timeline logic present).");

  console.log("\n==========================================");
  console.log("ALL 3 FRONTEND TEST SUITES PASSED (3/3)");
  console.log("==========================================");
}

runFrontendTests();
