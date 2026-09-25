const assert = require('assert');

// Mock the state
let existingLastSuccessAt = '2026-09-01T00:00:00';
let collectedAt = '2026-09-25T12:00:00';

// Test case 1: has_login true, sales_page_ok true -> should update last_success_at
let rev = { has_login: true };
let salesText = 'Total earnings $100';
let sales_page_ok = salesText !== null && salesText.includes('Total');
let last_success_at = (rev.has_login === true && sales_page_ok === true) ? collectedAt : existingLastSuccessAt;
assert.strictEqual(last_success_at, collectedAt, 'Test 1 failed');

// Test case 2: has_login true, sales_page_ok false -> should NOT update
rev = { has_login: true };
salesText = 'No total here';
sales_page_ok = salesText !== null && salesText.includes('Total');
last_success_at = (rev.has_login === true && sales_page_ok === true) ? collectedAt : existingLastSuccessAt;
assert.strictEqual(last_success_at, existingLastSuccessAt, 'Test 2 failed');

// Test case 3: has_login false, sales_page_ok true -> should NOT update
rev = { has_login: false };
salesText = 'Total earnings $100';
sales_page_ok = salesText !== null && salesText.includes('Total');
last_success_at = (rev.has_login === true && sales_page_ok === true) ? collectedAt : existingLastSuccessAt;
assert.strictEqual(last_success_at, existingLastSuccessAt, 'Test 3 failed');

// Test case 4: has_login false, sales_page_ok false -> should NOT update
rev = { has_login: false };
salesText = 'No total here';
sales_page_ok = salesText !== null && salesText.includes('Total');
last_success_at = (rev.has_login === true && sales_page_ok === true) ? collectedAt : existingLastSuccessAt;
assert.strictEqual(last_success_at, existingLastSuccessAt, 'Test 4 failed');

console.log('All tests passed!');