from playwright.async_api import async_playwright, TimeoutError
import time
import os
import pandas as pd
from pandas import Timestamp
from dotenv import load_dotenv
import traceback
import asyncio
import sys
import json

TRACKING_PAGE = "https://www.mymsc.com/myMSC/tracking"
API_URL = "https://services.mymsc.com/tracking/graphql"

def pause_before_exit():
    try:
        input("\nPress ENTER to close this window...")
    except EOFError:
        pass
    
def on_request(req):
        print("REQ", req.method, req.url)
        print("Headers:", req.headers)
        print('\n')
        
async def on_response(resp):
    # global pdf_url
    # ct = resp.headers.get("content-type", "")
    # if "application/pdf" in ct.lower() and resp.ok:
    #     pdf_url = resp.url
    print("RESP", resp.status)
    print("Headers:", resp.headers)
    print("Data:", await resp.json())
    print('\n')

async def checkingMSC(booking_num) -> Timestamp | None:
    with open("MSCauthToken.json","r") as f:
        data =json.load(f)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        context =  await browser.new_context(
            storage_state="auth_for_MSC.json"
        )

        page = await context.new_page()
        await page.goto(TRACKING_PAGE, wait_until="domcontentloaded")
        print("At the Invoices Page now")
        gettingTracking = await context.request.post(API_URL,
            headers = {
                "referer": "https://www.mymsc.com/",
                "mymsc-user-email": "chris@vship2000.com",
                "mymsc-user-roles": "Customer",
                'sec-ch-ua': '"Chromium";v="143", "Not A(Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
                'content-type': "application/json",
                "Authorization": f"Bearer {data["AccessToken"]}"
            },
            data=
            {
                "query": "\n    query trackingByBookingNumber($input: TrackingByBookingNumberGraphQlRequestInput!) {\n  trackingByBookingNumber(request: $input) {\n    allBillNumber\n    finalDischargePortCountry\n    finalDischargePortName\n    finalDischargePortUnCode\n    originName\n    originCode\n    destinationName\n    destinationCode\n    portLoadName\n    portLoadUnCode\n    priceCalculationDate\n    priceCalculationDateAsString\n    shippedToCountry\n    shippedToName\n    transshipmentName\n    transshipmentCode\n    resultsDateTimeInformations {\n      date\n      time\n    }\n    containers {\n      containerIsoDesc\n      containerIsOffService\n      containerNumber\n      finalEta\n      isDestinationReached\n      events {\n        emptyIndicatorCode\n        eventDate\n        eventDateDateTime\n        eventName\n        eventTime\n        lloydsNumber\n        locationCountry\n        locationName\n        locationUnCode\n        vesselName\n        voyageDesc\n        smdgTerminalCode\n        bicFacilityCode\n        activityEquipmentHandlingFacilityName\n        activityEquipmentHandlingFacilityCode\n        isEventPassed\n        portCalls {\n          portCallDate\n          isEventPassed\n          locationName\n          locationUnCode\n          locationCountry\n          etd\n          eta\n          eventDateTime\n        }\n      }\n    }\n    customsRelease {\n      error\n      response\n      details {\n        container\n        customsReference\n        customsStatus\n      }\n    }\n    lastFreeDates {\n      retrievalLevel\n      lastFreeDates {\n        containerNumber\n        lastFreeDate\n        errorMessage\n      }\n    }\n    freightRelease {\n      error\n      response\n    }\n  }\n}\n    ",
                "variables": {
                    "input": {
                        "retrieveFreightRelease": False,
                        "retrieveTracking": True,
                        "agency": {
                            "id": -1,
                            "isCustomsReleaseActive": False,
                            "isFreightReleaseActive": False,
                            "isLastFreeDateActive": False,
                            "isTrackingActive": False,
                            "name": ""
                        },
                        "retrieveCustomsRelease": False,
                        "retrieveLastFreeDate": False,
                        "bookingNumber": booking_num
                    }
                },
                "operationName": "trackingByBookingNumber"
            },
        )
        event_date = None
        if gettingTracking.ok:
            events = (await gettingTracking.json())["data"]["trackingByBookingNumber"][0]["containers"][0]["events"]
            for event in events:
                if event["eventName"] == "Estimated Time of Arrival":
                    event_date = event["eventDate"]
                    event_date = pd.to_datetime(event_date, format="%d %b %Y")
                    break
                if event["eventName"] == "Import Discharged from Vessel":
                    event_date = event["eventDate"]
                    event_date = pd.to_datetime(event_date, format="%d %b %Y")
                    break
            else:
                print(f"No ETA event found for booking {booking_num}")
                for event in events:
                    if event["eventName"] == "Full Transshipment Loaded":
                        event_date = event["eventDate"]
                        event_date = pd.to_datetime(event_date, format="%d %b %Y")
                        if event_date <= (pd.Timestamp.now() - pd.Timedelta(days=6)):
                            event_date = pd.Timestamp.now() + pd.Timedelta(days=7)
                        elif((pd.Timestamp.now() - pd.Timedelta(days=6)) < event_date < pd.Timestamp.now()):
                            event_date = event_date + pd.Timedelta(days=7)
                        elif(event_date >= pd.Timestamp.now()):
                            event_date = event_date + pd.Timedelta(days=7)
                        break
                else:
                    raise ValueError(f"No Full Transshipment Loaded event found for booking {booking_num} either. Can't determine ETA.")
            # print((await gettingTracking.json())["data"]["trackingByBookingNumber"][0]["containers"][0]["events"])
        else:
            raise RuntimeError(f"Failed to get tracking info: {gettingTracking.status} {await gettingTracking.text()}")
        await browser.close()
    return event_date

if __name__ == "__main__":
    try:
        print(asyncio.run(checkingMSC("EBKG11248028")))
    except Exception:
        print("\n❌ An error occurred:\n")
        traceback.print_exc()
        pause_before_exit()
        sys.exit(1)