const { test, expect } = require('@playwright/test');

async function expectNoHorizontalOverflow(page) {
  const metrics = await page.evaluate(() => ({
    viewportWidth: document.documentElement.clientWidth,
    documentWidth: document.documentElement.scrollWidth,
  }));
  expect(
    metrics.documentWidth,
    `Document overflows horizontally: ${metrics.documentWidth}px > viewport ${metrics.viewportWidth}px`,
  ).toBeLessThanOrEqual(metrics.viewportWidth + 1);
}

test('desktop auth landing page fits the viewport and keeps login fields aligned', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Штаб писателя' })).toBeVisible();
  await expect(page.locator('#signInForm')).toBeVisible();
  await expectNoHorizontalOverflow(page);

  const email = await page.locator('#loginEmail').boundingBox();
  const password = await page.locator('#loginPassword').boundingBox();
  expect(email).not.toBeNull();
  expect(password).not.toBeNull();
  expect(Math.abs(email.y - password.y), 'Desktop login fields should share a row').toBeLessThan(3);
  expect(password.x).toBeGreaterThan(email.x);
});

test('mobile auth and registration forms stack fields without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Штаб писателя' })).toBeVisible();
  await expect(page.locator('#signInForm')).toBeVisible();
  await expectNoHorizontalOverflow(page);

  const email = await page.locator('#loginEmail').boundingBox();
  const password = await page.locator('#loginPassword').boundingBox();
  expect(email).not.toBeNull();
  expect(password).not.toBeNull();
  expect(password.y).toBeGreaterThan(email.y + email.height - 2);

  await page.locator('#signupDetails summary').click();
  await expect(page.locator('#displayName')).toBeVisible();
  await expect(page.locator('#signupEmail')).toBeVisible();
  const name = await page.locator('#displayName').boundingBox();
  const signupEmail = await page.locator('#signupEmail').boundingBox();
  expect(name).not.toBeNull();
  expect(signupEmail).not.toBeNull();
  expect(signupEmail.y).toBeGreaterThan(name.y + name.height - 2);

  const consent = page.locator('label[for="shareStatsOnFollow"], label.privacy-setting').filter({ has: page.locator('#shareStatsOnFollow') });
  await expect(consent).toContainText('Разрешаю показывать статистику и достижения авторам, которые подписаны на меня');
  await expect(consent).toContainText('Эту настройку можно будет изменить в профиле');
  await expectNoHorizontalOverflow(page);
});

test('forgot-password empty-email path gives a visible explanation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Забыли пароль?' }).click();
  await expect(page.locator('.auth-message').filter({ hasText: 'Сначала укажи email' })).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
