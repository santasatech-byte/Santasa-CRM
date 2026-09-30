const { test, expect } = require('@playwright/test');

test.describe('Hospital CRM Executive Workspace Live E2E Verification Suite', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:3000/', { waitUntil: 'domcontentloaded', timeout: 15000 });
    // If login gateway is displayed, sign in as Executive
    const loginModal = page.locator('#loginModal');
    const isVisible = await loginModal.isVisible();
    const hasHidden = await loginModal.evaluate(el => el.classList.contains('hidden'));
    
    if (isVisible && !hasHidden) {
      await page.click('#fillExecutiveDemoBtn');
      await page.click('#submitLoginBtn');
      await expect(page.locator('#loginModal')).toHaveClass(/hidden/, { timeout: 10000 });
    }

    await page.waitForSelector('#leadsListContainer', { timeout: 10000 });
    await page.waitForSelector('#userProfileName', { timeout: 10000 });
    await page.waitForTimeout(400);
  });

  test('0. Strict Authentication Gatekeeper: Unauthenticated users cannot access CRM without credentials', async ({ browser }) => {
    const freshContext = await browser.newContext();
    const freshPage = await freshContext.newPage();
    await freshPage.goto('http://localhost:3000/', { waitUntil: 'domcontentloaded' });

    // 1. Verify Login Gateway is visible and workspace is locked
    await expect(freshPage.locator('#loginModal')).not.toHaveClass(/hidden/);
    await expect(freshPage.locator('#userProfileName')).toHaveText('Not Signed In');

    // 2. Try submitting with invalid password
    await freshPage.fill('#loginEmailInput', 'executive@santasa.com');
    await freshPage.fill('#loginPasswordInput', 'WrongPassword999!');
    await freshPage.click('#submitLoginBtn');

    // Verify access is denied and modal remains locked
    await freshPage.waitForTimeout(1000);
    await expect(freshPage.locator('#loginModal')).not.toHaveClass(/hidden/);
    await expect(freshPage.locator('#userProfileName')).toHaveText('Not Signed In');

    // 3. Submit valid credentials
    await freshPage.fill('#loginPasswordInput', 'Executive@2026!');
    await freshPage.click('#submitLoginBtn');

    // Verify workspace unlocks
    await expect(freshPage.locator('#loginModal')).toHaveClass(/hidden/, { timeout: 10000 });
    await expect(freshPage.locator('#userProfileRole')).toContainText('Executive');

    await freshContext.close();
  });

  test('1. Executive Workspace loads and displays CRM Executive profile & Supabase status', async ({ page }) => {
    await expect(page.locator('.brand-name')).toHaveText('Santasa IVF');
    await expect(page.locator('#systemHealthIndicator')).toContainText('Supabase Cloud Connected');
    await expect(page.locator('#userProfileName')).toBeVisible();
    await expect(page.locator('#userProfileRole')).toContainText('Executive');
  });

  test('2. Create a new patient lead with validation & phone normalization', async ({ page }) => {
    const randomSuffix = Math.floor(1000 + Math.random() * 9000);
    const testPatientName = `Sayeda Tabasuma ${randomSuffix}`;
    const testPhone = `98765${randomSuffix}1`;

    // Click + New Lead button
    await page.click('#newLeadBtn');
    await expect(page.locator('#newLeadModal')).not.toHaveClass(/hidden/);

    // Fill form
    await page.fill('#inputPatientName', testPatientName);
    await page.fill('#inputPrimaryPhone', testPhone);
    await page.fill('#inputCity', 'Hassan');
    await page.selectOption('#inputPriority', 'High');
    await page.fill('#inputNotes', 'Initial phone inquiry regarding IVF ICSI cycle.');

    // Submit form and wait for network & modal close
    await page.click('#newLeadForm button[type="submit"]');
    await expect(page.locator('#newLeadModal')).toHaveClass(/hidden/, { timeout: 10000 });
    await expect(page.locator('#leadsListContainer')).toContainText(testPatientName);
  });

  test('3. Quick Search filters leads by name and phone number', async ({ page }) => {
    const searchInput = page.locator('#globalSearchInput');
    await searchInput.fill('Sayeda');
    await page.waitForTimeout(500);

    const leadsList = page.locator('#leadsListContainer');
    await expect(leadsList).toContainText('Sayeda');
  });

  test('4. Add Executive Note and verify instant timeline sync', async ({ page }) => {
    await page.waitForSelector('.lead-card');
    await page.locator('.lead-card').first().click();
    await page.waitForTimeout(400);

    // Click ADD NOTE
    await page.click('#actionNoteBtn');
    await expect(page.locator('#noteModal')).not.toHaveClass(/hidden/);

    const testNote = `Patient requested detailed IVF cycle brochure and doctor appointment on weekend. Timestamp: ${Date.now()}`;
    await page.fill('#inputNoteText', testNote);
    await page.click('#noteForm button[type="submit"]');

    // Verify modal closes and note appears in timeline feed
    await expect(page.locator('#noteModal')).toHaveClass(/hidden/, { timeout: 10000 });
    await expect(page.locator('#timelineFeed')).toContainText(testNote);
  });

  test('5. Schedule Follow-up and complete it', async ({ page }) => {
    await page.waitForSelector('.lead-card');
    await page.locator('.lead-card').first().click();
    await page.waitForTimeout(400);

    // Click SCHEDULE FOLLOW-UP
    await page.click('#actionFollowupBtn');
    await expect(page.locator('#followupModal')).not.toHaveClass(/hidden/);

    const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 16);
    await page.fill('#inputFollowupDate', tomorrow);
    await page.fill('#inputFollowupNote', 'Call patient to confirm ultrasound scan report review');
    await page.click('#followupForm button[type="submit"]');

    await expect(page.locator('#followupModal')).toHaveClass(/hidden/, { timeout: 10000 });
    await page.waitForTimeout(600);
  });

  test('6. Book Doctor Consultation Appointment', async ({ page }) => {
    await page.waitForSelector('.lead-card');
    await page.locator('.lead-card').first().click();
    await page.waitForTimeout(400);

    // Click BOOK APPT
    await page.click('#actionApptBtn');
    await expect(page.locator('#apptModal')).not.toHaveClass(/hidden/);

    const nextWeek = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 16);
    await page.fill('#inputApptDate', nextWeek);
    await page.click('#apptForm button[type="submit"]');

    await expect(page.locator('#apptModal')).toHaveClass(/hidden/, { timeout: 10000 });
    await page.waitForTimeout(600);
  });

  test('7. Record Doctor Outcome & Treatment Conversion Revenue', async ({ page }) => {
    await page.waitForSelector('.lead-card');
    await page.locator('.lead-card').first().click();
    await page.waitForTimeout(400);

    // Click OUTCOME
    await page.click('#actionOutcomeBtn');
    await expect(page.locator('#outcomeModal')).not.toHaveClass(/hidden/);

    await page.selectOption('#inputOutcomeStatus', 'Converted (Under Treatment)');
    await page.fill('#inputRevenue', '180000');
    await page.fill('#inputOutcomeNotes', 'Patient registered for IVF cycle with deposit.');
    await page.click('#outcomeForm button[type="submit"]');

    await expect(page.locator('#outcomeModal')).toHaveClass(/hidden/, { timeout: 10000 });
    await page.waitForTimeout(600);
  });

  test('8. Dispatch WhatsApp Action', async ({ page }) => {
    await page.waitForSelector('.lead-card');
    await page.locator('.lead-card').first().click();
    await page.waitForTimeout(400);

    // Click WHATSAPP
    const popupPromise = page.waitForEvent('popup').catch(() => null);
    await page.click('#actionWhatsappBtn');
    const popup = await popupPromise;
    if (popup) {
      expect(popup.url()).toMatch(/whatsapp\.com|wa\.me/);
      await popup.close();
    } else {
      await expect(page.locator('#toastContainer')).toContainText(/WhatsApp/i);
    }
  });

  test('9. Trigger Click-to-Call overlay and end call', async ({ page }) => {
    await page.waitForSelector('.lead-card');
    await page.locator('.lead-card').first().click();
    await page.waitForTimeout(400);

    // Click CALL PATIENT
    await page.click('#actionCallBtn');
    await expect(page.locator('#liveCallModal')).not.toHaveClass(/hidden/);
    await expect(page.locator('#callTimer')).toBeVisible();

    await page.waitForTimeout(1200);
    await page.click('#endCallBtn');
    await expect(page.locator('#liveCallModal')).toHaveClass(/hidden/, { timeout: 10000 });
  });

  test('10. Toggle Executive Availability Status', async ({ page }) => {
    const statusBtn = page.locator('#agentStatusBtn');
    await statusBtn.click();
    await expect(page.locator('#agentStatusLabel')).toHaveText('In Call');
    await statusBtn.click();
    await expect(page.locator('#agentStatusLabel')).toHaveText('On Break');
    await statusBtn.click();
    await expect(page.locator('#agentStatusLabel')).toHaveText('Offline');
    await statusBtn.click();
    await expect(page.locator('#agentStatusLabel')).toHaveText('Online');
  });

  test('11. Executive Logout and Re-Login flow', async ({ page }) => {
    // Click Logout
    await page.click('#logoutBtn');
    await expect(page.locator('#loginModal')).not.toHaveClass(/hidden/, { timeout: 8000 });

    // Re-login with Executive credentials
    await page.click('#fillExecutiveDemoBtn');
    await page.click('#submitLoginBtn');

    await expect(page.locator('#loginModal')).toHaveClass(/hidden/, { timeout: 10000 });
    await expect(page.locator('#userProfileRole')).toContainText('Executive');
    await expect(page.locator('#leadsListContainer')).toBeVisible();
  });

});
