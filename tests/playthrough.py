"""Run against a locally served checkout with Python Playwright and Chrome.
Example: python tests/playthrough.py http://127.0.0.1:8000 --screenshots screenshots
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


def play(browser, url, mobile, screenshots):
    size = {"width": 390, "height": 844} if mobile else {"width": 1280, "height": 900}
    context = browser.new_context(viewport=size, has_touch=mobile, timezone_id="Asia/Shanghai")
    page = context.new_page()
    page.set_default_timeout(20000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type in ("warning", "error") and
            (msg.type == "error" or "跳过一帧" in msg.text) else None)
    page.route("**/favicon.ico", lambda route: route.fulfill(status=204))
    click = page.click
    el = page.locator
    wait = page.wait_for_function

    def snap(name):
        if screenshots:
            screenshots.mkdir(parents=True, exist_ok=True)
            mode = "touch" if mobile else "desktop"
            page.screenshot(path=screenshots / f"{mode}-{name}.png")

    def mapped(selector):
        click("#btnMapTop")
        click(selector)

    def choose_plot(label):
        click("#btnMapTop")
        zones = el("#mapZones button")
        for index in range(zones.count()):
            zones.nth(index).click()
            target = el("#plotChoices").get_by_role("button", name=label, exact=label[0].isdigit())
            if target.count():
                target.click()
                expect(target).to_have_attribute("aria-pressed","true")
                click("#btnWalkPlot")
                return
            click("#btnMapOverview")
        raise AssertionError("Missing plot " + label)

    def walking_done():
        wait("!player.destQ.length && Math.hypot(player.tx-player.x,player.ty-player.y)<=4",
             timeout=35000)

    def tap_world(x, y):
        pos = page.evaluate("([x,y])=>({x:(x-camera().x)*ZOOM,y:(y-camera().y)*ZOOM})", [x,y])
        el("#map").click(position=pos)

    page.clock.set_fixed_time("2027-04-01T12:00:00+08:00")
    delayed = []
    if not mobile:
        page.route("**/avatar-previews.webp", lambda route: delayed.append(route))
    page.goto(url, wait_until="commit")
    wait("typeof openAvatarPicker === 'function' && document.getElementById('titleOverlay').style.display === 'flex'")
    expect(el("#btnTitleMain")).to_be_focused()
    for key, selector in [("Tab","#btnTitleLoad"),("Tab","#btnTitleMain"),("Shift+Tab","#btnTitleLoad")]:
        page.keyboard.press(key)
        expect(el(selector)).to_be_focused()
    click("#btnTitleLoad")
    expect(el("#loadChoiceOverlay")).to_be_visible()
    expect(el("#btnLoadNew")).to_be_focused()
    page.keyboard.press("Escape")
    expect(el("#btnTitleLoad")).to_be_focused()
    click("#btnTitleLoad")
    click("#btnLoadNew")
    if not mobile:
        assert delayed
        pending = delayed.pop()
        pending.fulfill(response=pending.fetch())
        page.unroute("**/avatar-previews.webp")
    wait("Array.from(document.querySelectorAll('.avCard canvas')).every(c => "
         "c.getContext('2d').getImageData(0,0,c.width,c.height).data.some(v=>v))")
    snap("avatars")
    click("[data-av=a4]")
    expect(el("#regOverlay")).to_be_hidden()
    if mobile:
        knob = el("#joy")
        expect(knob).to_be_visible()
        box = knob.bounding_box()
        x,y = box['x']+box['width']/2, box['y']+box['height']/2
        client = context.new_cdp_session(page)
        before = page.evaluate("player.x")
        client.send("Input.dispatchTouchEvent", {"type":"touchStart", "touchPoints":[{"x":x,"y":y}]})
        client.send("Input.dispatchTouchEvent", {"type":"touchMove", "touchPoints":[{"x":x+35,"y":y}]})
        wait("old => player.x > old+12", arg=before)
        client.send("Input.dispatchTouchEvent", {"type":"touchEnd","touchPoints":[]})
    else:
        before = page.evaluate("player.x")
        page.keyboard.down("d")
        wait("old => player.x > old+12", arg=before)
        page.keyboard.up("d")

    click("#btnDrawer")
    expect(el("#tierProgress")).to_contain_text("青铜碑还差 3 天")
    click("#btnLoginGift")
    expect(el("#btnLoginGift")).to_be_disabled()
    expect(el("#giftLabel")).to_have_text("今日物资已领")
    click("#btnCheckin")
    expect(el("#tierProgress")).to_contain_text("青铜碑还差 2 天")
    expect(el("#btnCheckin")).to_be_disabled()
    click("#btnAvatar")
    click("[data-av=a2]")
    page.reload()
    expect(el("#btnTitleMain")).to_have_text("继续游戏")
    click("#btnTitleLoad")
    expect(el("#titleOverlay")).to_be_hidden()
    expect(el("#loadChoiceOverlay")).to_be_hidden()
    assert page.evaluate("S.avatar === 'a2' && S.checkin.total === 1")
    print("PASS entry, movement, avatar images and guest resume", flush=True)

    # Walk from the bridge to an empty plot using only map controls.
    mapped("#btnNearestPlot")
    walking_done()
    expect(el("#btnRegHere")).to_be_visible()
    expect(el("#regOverlay")).to_be_hidden()
    # Once the visitor is standing still, the same plot should not repaint its text every frame.
    assert page.evaluate("""async () => {
        const panel = document.getElementById('infoPanel');
        let changes = 0;
        const observer = new MutationObserver(records => { changes += records.length; });
        observer.observe(panel, {childList: true, subtree: true});
        for (let i = 0; i < 5; i++) await new Promise(requestAnimationFrame);
        observer.disconnect();
        return changes === 0;
    }""")
    click("#btnMapTop")
    seen = []
    for i in range(4):
        el("#mapZones button").nth(i).click()
        assert page.evaluate("getComputedStyle(mapScene).transform.startsWith('matrix(2,')")
        bounds = el("#plotChoices button").evaluate_all("""buttons => buttons.map(button => {
            const {left,top,right,bottom,width,height} = button.getBoundingClientRect();
            return {n:Number(button.dataset.plot),left,top,right,bottom,width,height};
        })""")
        assert bounds and all(b["width"] >= 44 and b["height"] >= 44 for b in bounds)
        for n,a in enumerate(bounds):
            for b in bounds[n+1:]:
                assert a["right"]<=b["left"] or b["right"]<=a["left"] or a["bottom"]<=b["top"] or b["bottom"]<=a["top"]
        seen.extend(b["n"] for b in bounds)
        if i == 0:
            point = page.evaluate("""() => {
                const crop = mapBox.getBoundingClientRect(), scene = mapScene.getBoundingClientRect();
                const plot = PLOTS.find(p => p.no === 1);
                return {x:scene.left-crop.left+scene.width*plot.x/WORLD.w,
                        y:scene.top-crop.top+scene.height*plot.y/WORLD.h};
            }""")
            el("#mapBox").click(position=point)
            expect(el("#btnWalkPlot")).to_contain_text("1 号空位")
            expect(el("#plotChoices [data-plot='1']")).to_have_attribute("aria-pressed","true")
            expect(el("#mapMarks .mapNumber")).to_have_text("1 号")
        click("#btnMapOverview")
    assert sorted(seen) == list(range(1,51))
    click("#btnMapClose")
    choose_plot("1 号 · 空位")
    walking_done()
    expect(el("#infoName")).to_contain_text("1 号碑位")
    click("#btnRegHere")
    expect(el("#regStatus")).to_have_value("")
    expect(el("#regMemorialOnly")).to_be_hidden()
    el("#regName").fill("未选择")
    click("#btnRegister")
    expect(el("#regStatus")).to_be_focused()
    assert page.evaluate("myPets().length === 0")
    el("#regStatus").select_option("prereg")
    click("#btnRegCancel")
    click("#btnRegHere")
    expect(el("#regStatus")).to_have_value("")
    el("#regStatus").select_option("memorial")
    expect(el("#regMemorialOnly")).to_be_visible()
    expect(el("#regBreed")).to_be_hidden()
    click("#regAppearance summary")
    expect(el("#regBreed")).to_be_visible()
    click("#regAppearance summary")
    expect(el("#btnRegister")).to_have_text("建档，送它入园")
    pet_name = "星<月>&"
    el("#regName").fill(pet_name)
    el("#regLine").fill("记得我们一起走过的路。")
    click("#btnRegister")
    click("#btnSkipCer")
    click("#btnFirstCandle")
    expect(el("#infoName")).to_contain_text(pet_name)
    expect(el("#infoText")).to_have_text("碑前的烛光亮着。 「记得我们一起走过的路。」")
    expect(el("#careStats")).to_be_hidden()
    click("#careRecord summary")
    expect(el("#careStats")).to_contain_text("被点烛 1 次")
    click("#careRecord summary")
    assert page.evaluate("myHomePet().plot === 1 && myHomePet().counts.candle === 1")
    click("#btnMapTop")
    expect(el(".mapTag").filter(has_text=pet_name)).to_have_text(pet_name+"的小屋")
    snap("map")
    click(".mapBadge.home")
    expect(el("#house")).to_be_visible()
    expect(el("#infoPanel")).to_be_hidden()
    click("[data-act=feed]")
    click("[data-act=flower]")
    click("[data-act=pray]")
    click("[data-act=play]")
    click("[data-act=offer]")
    expect(el("#houseStats")).to_contain_text("食盆 1/3")
    expect(el("#houseStats")).to_contain_text("被投喂 1")
    expect(el("#houseStats")).to_contain_text("房间里的玩具 ×1")
    snap("house")
    click("#btnLeave")
    print("PASS registration, ceremony, map labels, home and pet interactions", flush=True)

    click("#btnDrawer")
    # The virtual calendar moves forward; navigation and animation still run in real time.
    for day in range(2,31):
        page.clock.set_fixed_time(f"2027-04-{day:02}T12:00:00+08:00")
        expect(el("#btnCheckin")).to_be_enabled()
        click("#btnCheckin")
        expect(el("#checkinLabel")).to_have_text("今日已签到")
        assert page.evaluate("S.checkin.total") == day
        if day == 2:
            expect(el("#btnLoginGift")).to_be_enabled()
        if day == 30:
            expect(el("#tierProgress")).to_contain_text("碑材质已集齐")
        if day in (2,3,6,7,13,14,29,30):
            unlocked = sum(day >= n for n in (3,7,14,30))
            expect(el("#tierBtns button:enabled")).to_have_count(unlocked+1)
            if day in (3,7,14,30):
                click("#btnDrawer")
                el("#tierBtns button").nth(unlocked).click()
                assert page.evaluate("myHomePet().stoneTier") == unlocked
                click("#btnDrawer")
    expect(el("#btnReset")).to_be_hidden()
    click("#saveManagement summary")
    click("#btnReset")
    expect(el("#resetOverlay")).to_be_visible()
    click("#btnResetCancel")
    with page.expect_download() as download:
        click("#btnExport")
    backup = download.value.path().read_bytes()
    assert json.loads(backup)["checkin"]["total"] == 30
    click("#btnDrawer")
    page.reload()
    click("#btnTitleLoad")
    wait("nearestPet && nearestPet === myHomePet()")
    assert page.evaluate("myHomePet().stoneTier === 4")
    wait("stoneTierImg().naturalWidth > 0")
    snap("diamond")
    print("PASS daily rollover, four tier boundaries, switching and reload", flush=True)

    # Change the destination after starting a trip home, then visit the same grave normally.
    choose_plot("团团")
    walking_done()
    click("#btnHome")
    choose_plot("团团")
    walking_done()
    assert page.evaluate("pendingHomePet === null")
    click("#btnDrawer")
    click("#btnDir")
    el("#dirSearch").fill(pet_name)
    expect(el("#dirList button")).to_have_count(1)
    el("#dirList button").click()
    walking_done()
    expect(el("#house")).to_be_hidden()
    click("#btnHome")
    expect(el("#house")).to_be_visible()
    expect(el("#infoPanel")).to_be_hidden()
    click("#btnLeave")
    mapped(".mapBadge:not(.home)")
    walking_done()
    hx,hy = page.evaluate("[BLESS_HOUSE.x, BLESS_HOUSE.y]")
    tap_world(hx,hy-25)
    expect(el("#blessRoom")).to_be_visible()
    before = page.evaluate("[player.x,player.y]")
    page.keyboard.down("a")
    page.wait_for_timeout(250)
    page.keyboard.up("a")
    assert page.evaluate("[player.x,player.y]") == before
    click("#btnIncense")
    click("#btnIncense")
    assert page.evaluate("myHomePet().counts.incense === 1")
    snap("shrine")
    # The first empty plaque opens the independent preregistration route.
    plaque = page.evaluate("plaqueRects.find(r=>!r.pet)")
    rect = el("#blessCanvas").bounding_box()
    el("#blessCanvas").click(position={"x":(plaque["x"]+plaque["w"]/2)*rect["width"]/880,
                                      "y":(plaque["y"]+plaque["h"]/2)*rect["height"]/500})
    el("#plaqueInfo button").click()
    expect(el("#regStatus")).to_have_value("prereg")
    el("#regName").fill("小羽")
    el("#regSpecies").select_option("bird")
    el("#regStatus").select_option("prereg")
    click("#btnRegister")
    assert page.evaluate("myPets().length === 2 && myHomePet().name !== '小羽'")
    tap_world(hx,hy-25)
    plaque = page.evaluate("plaqueRects.find(r=>r.pet && r.pet.name === '小羽')")
    rect = el("#blessCanvas").bounding_box()
    el("#blessCanvas").click(position={"x":(plaque["x"]+plaque["w"]/2)*rect["width"]/880,
                                      "y":(plaque["y"]+plaque["h"]/2)*rect["height"]/500})
    wish = el("#plaqueInfo").get_by_role("button", name="平平安安")
    wish.click()
    wish.click()
    assert page.evaluate("selPlaque.counts.bless === 1")
    el("#plaqueInfo").get_by_role("button", name="送它过桥（转纪念）").click()
    expect(el("#btnConvertGo")).to_be_disabled()
    el("#convertName").fill("小羽")
    click("#btnConvertGo")
    click("#btnSkipCer")
    if el("#firstCandle").is_visible():
        click("#btnFirstCandleSkip")
    assert page.evaluate("myHomePet().name === '小羽' && myHomePet().status === 'memorial'")
    print("PASS redirect, directory, shrine, once-daily blessing and memorial conversion", flush=True)

    # Import through the title in another clean browser context. Exercise an older date format.
    migrated = json.loads(backup)
    migrated["lastGiftDate"] = "2027-4-30"
    migrated["loginDays"] = 4
    other = browser.new_context(timezone_id="Asia/Shanghai")
    imported = other.new_page()
    imported.on("pageerror", lambda err: errors.append(str(err)))
    imported.clock.set_fixed_time("2027-04-30T12:00:00+08:00")
    imported.goto(url)
    imported.click("#btnTitleLoad")
    with imported.expect_file_chooser() as chooser:
        imported.click("#btnLoadImport")
    with imported.expect_navigation():
        chooser.value.set_files({"name":"园子.json","mimeType":"application/json",
                                 "buffer":json.dumps(migrated).encode()})
    imported.click("#btnTitleLoad")
    imported.click("#btnDrawer")
    expect(imported.locator("#btnLoginGift")).to_be_disabled()
    assert imported.evaluate("S.loginDays === 4 && S.checkin.total === 30 && myHomePet().stoneTier === 4")
    stored = imported.evaluate("localStorage.getItem(SAVE_KEY)")
    imported.click("#saveManagement summary")
    with imported.expect_file_chooser() as chooser:
        imported.click("#btnImport")
    chooser.value.set_files({"name":"incomplete.json","mimeType":"application/json",
                             "buffer":b'{"pets":[{}]}'})
    imported.wait_for_function("document.getElementById('toast').textContent.includes('没有导入') || "
                               "toastQ.some(text=>text.includes('没有导入'))")
    assert imported.evaluate("localStorage.getItem(SAVE_KEY)") == stored
    other.close()
    assert not errors, errors
    context.close()
    print("PASS export/import, legacy daily gift and browser error checks", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument("--mode", choices=["desktop","touch"], default="desktop")
    args = parser.parse_args()
    if urlparse(args.url).hostname not in ("localhost","127.0.0.1","::1"):
        parser.error("Use a local test server")
    with sync_playwright() as driver:
        browser = driver.chromium.launch(channel="chrome")
        play(browser, args.url, args.mode == "touch", args.screenshots)
        browser.close()
