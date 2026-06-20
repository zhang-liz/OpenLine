/**
 * Google Apps Script: fire a callback when a new lead row is added.
 *
 * Setup
 * -----
 * 1. Open the Sheet -> Extensions -> Apps Script.
 * 2. Paste this file in.
 * 3. Set SERVICE_URL and SHARED_SECRET below (Secret must match LEAD_SHARED_SECRET
 *    in the server's .env).
 * 4. Triggers -> Add Trigger -> onChange, from spreadsheet, on change.
 *
 * Why onChange (not onEdit): onChange fires on programmatic/structural changes
 * too. We only act when a row's status is still blank, which both detects "new
 * lead" and prevents the server's own status write-back from re-triggering a call.
 */

const SERVICE_URL = "https://YOUR_PUBLIC_URL/lead";
const SHARED_SECRET = "CHANGE_ME_TO_MATCH_LEAD_SHARED_SECRET";
const SHEET_TAB = "Sheet1";

function onChange(e) {
  const sheet = SpreadsheetApp.getActive().getSheetByName(SHEET_TAB);
  if (!sheet) return;

  const header = sheet
    .getRange(1, 1, 1, sheet.getLastColumn())
    .getValues()[0]
    .map((h) => String(h).trim().toLowerCase());

  const statusCol = header.indexOf("status");
  const phoneCol = header.indexOf("phone");
  if (statusCol === -1 || phoneCol === -1) return;

  const lastRow = sheet.getLastRow();

  // Scan from the bottom for rows with a phone but a blank status -> uncalled leads.
  for (let row = lastRow; row >= 2; row--) {
    const values = sheet.getRange(row, 1, 1, sheet.getLastColumn()).getValues()[0];
    const status = String(values[statusCol] || "").trim();
    const phone = String(values[phoneCol] || "").trim();

    if (phone && status === "") {
      // Mark "calling" immediately so a second onChange won't double-dial.
      sheet.getRange(row, statusCol + 1).setValue("calling");
      triggerCall(row);
    }
  }
}

function triggerCall(row) {
  const options = {
    method: "post",
    contentType: "application/json",
    headers: { "X-Lead-Secret": SHARED_SECRET },
    payload: JSON.stringify({ row: row }),
    muteHttpExceptions: true,
  };
  UrlFetchApp.fetch(SERVICE_URL, options);
}
