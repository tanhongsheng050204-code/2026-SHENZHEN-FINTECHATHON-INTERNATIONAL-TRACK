// Server text with dates and names inside reads fully in Chinese and Malay.
import assert from "node:assert/strict";
import { test } from "node:test";
import { zhFor } from "../src/lib/i18nZh.ts";
import { msFor } from "../src/lib/i18nMs.ts";

test("a month label is localised", () => {
  assert.equal(zhFor("September 2026"), "2026年9月");
  assert.equal(msFor("August 2026"), "Ogos 2026");
});

test("a reminder title translates the invoice inside it", () => {
  assert.equal(zhFor("Payment reminder for Invoice due 08 Nov"), "给 11月8日到期的发票 的付款提醒");
  assert.equal(msFor("Payment reminder for Invoice due 08 Nov"), "Peringatan bayaran untuk Invois tamat tempoh 08 Nov");
});

test("a month inside a server label is localised too", () => {
  assert.equal(zhFor("Bank lines reconciled, September 2026"), "已对账的银行流水（2026年9月）");
  assert.equal(msFor("Bank lines reconciled, August 2026"), "Baris bank disesuaikan, Ogos 2026");
});

test("the receivables answer reads in Chinese and Malay", () => {
  assert.equal(zhFor("Customers owe RM353,500.00 on 10 open invoices."), "客户在 10 张未结发票上共欠 RM353,500.00。");
  assert.equal(msFor("3 are overdue."), "3 telah tertunggak.");
  assert.equal(zhFor("Who owes us the most?"), "谁欠我们最多？");
});

test("a masked customer's number reads in Chinese and Malay", () => {
  assert.equal(zhFor("Customer #7"), "客户 #7");
  assert.equal(msFor("Customer #7"), "Pelanggan #7");
  assert.equal(zhFor("Payment reminder for customer #8"), "给 客户 #8 的付款提醒");
});
