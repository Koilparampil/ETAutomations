from playwright.async_api import async_playwright

l=[]
l_not_found = []
def normalize(s) -> str:
    return (
        s.split(",")[0]
        .split("_")[0]
        .split(" ")[0]
        .strip()
    )
async def write_notif_in_VShip(passed, eta, notifNum, booking_no):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
                storage_state="auth_for_VshipCRM.json"
            )
        page = await context.new_page()
        await page.goto("https://vshipcrm.com/Home/GlobalSearch")
        print("At the Booking Page now")
        await page.fill('input[name="Booking_No"]', booking_no)
        await page.evaluate("reInitGrid()")
        await page.wait_for_load_state("networkidle")
        await page.locator('a[title="Edit"][href^="/Booking/CreateBooking/"]').first.click()
        await page.wait_for_load_state("networkidle")
        booking_num = normalize(await page.locator('input#Booking_No').get_attribute('value'))
        if booking_num.find(booking_no)!=-1:
            print(f"Booking No: {booking_no}")
            if passed:
                await page.locator('#InternalComment').fill(f"ARRIVED ON {eta.dt.strftime('%m/%d')}. NOTIF #{notifNum}")
                await page.get_by_role("button", name="Save").click()
            else:
                await page.locator('#InternalComment').fill(f"ARRIVING ON {eta.dt.strftime('%m/%d')}.")
                await page.get_by_role("button", name="Save").click()  
        else:
            l_not_found.append(booking_no)
            print(f"Booking No not found: {booking_no}")
        await browser.close()
        
        # myMSC/dashboard/invoices
    print(f"List of booking numbers with no Note : {l_not_found}")