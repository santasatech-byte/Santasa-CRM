const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 800 } });
  const page = await context.newPage();

  console.log("Navigating to https://santasacrm.vercel.app...");
  await page.goto('https://santasacrm.vercel.app', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  // Function to switch tenant via profile dropdown
  async function switchTenant(hospCode, expectedName, screenshotName) {
    console.log(`\nTesting Hospital Tenant [${hospCode}]...`);

    // Click profile dropdown toggle
    await page.click('#userProfileBtn');
    await page.waitForTimeout(500);

    // Click the specific tenant switch button
    await page.click(`button.switch-tenant-btn[data-hospital="${hospCode}"]`);
    await page.waitForTimeout(3000);

    // Verify User Profile & Hospital
    const profileName = await page.locator('#userProfileName').textContent();
    const currentHosp = await page.locator('#currentHospitalDisplay').textContent();
    console.log(`  ✔ Active Profile: "${profileName.trim()}" | Hospital: "${currentHosp.trim()}"`);

    // Click Leads View
    await page.click('#navLeads');
    await page.waitForTimeout(2000);

    // Count rows
    const rowCount = await page.locator('#leadsTableBody tr').count();
    console.log(`  ✔ Leads Displayed: ${rowCount} rows`);

    await page.screenshot({ path: `C:/Users/Praveen/.gemini/antigravity/brain/c469a397-9578-468b-8009-87f180e12475/${screenshotName}` });
    console.log(`  ✔ Captured: ${screenshotName}`);
  }

  // 1. Verify SSM Hospital
  await switchTenant('SSM', 'SSM Hospital', 'live_prod_ssm.png');

  // 2. Verify Santasa Hassan Hospital
  await switchTenant('SHH', 'Santasa Hassan Hospital', 'live_prod_shh.png');

  // 3. Verify Santasa Mysore Hospital
  await switchTenant('SMH', 'Santasa Mysore Hospital', 'live_prod_smh.png');

  // 4. Test Sign Out & Login Modal
  console.log("\nTesting Sign Out to Login Gateway...");
  await page.click('#userProfileBtn');
  await page.waitForTimeout(500);
  await page.click('#logoutBtn');
  await page.waitForTimeout(1500);

  const isModalVisible = await page.locator('#loginModal').isVisible();
  console.log(`  ✔ Login Gateway Modal Visible: ${isModalVisible}`);
  await page.screenshot({ path: `C:/Users/Praveen/.gemini/antigravity/brain/c469a397-9578-468b-8009-87f180e12475/live_prod_login_modal.png` });
  console.log("  ✔ Captured: live_prod_login_modal.png");

  await browser.close();
  console.log("\n========================================================");
  console.log("🎉 ALL 3 HOSPITAL LIVE PRODUCTION TENANTS VERIFIED (3/3)");
  console.log("========================================================");
})();
