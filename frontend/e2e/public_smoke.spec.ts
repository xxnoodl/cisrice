import {test,expect} from "@playwright/test";

test("public dashboard requires sign-in and exposes only service health",async({page})=>{
  await page.goto("/");
  await expect(page.getByRole("heading",{name:"Sign in to Cisrice"})).toBeVisible();
  expect((await page.request.get("/api/workspaces")).status()).toBe(401);
  await page.getByRole("link",{name:"Operations",exact:true}).click();
  await expect(page.getByText("System ok",{exact:true})).toBeVisible();
  await expect(page.getByRole("heading",{name:"Service health"})).toBeVisible();
});
