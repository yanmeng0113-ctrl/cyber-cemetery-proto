"""Exercise save replacement against a locally served garden in Chromium or WebKit."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


def seed(page, url, candles):
    page.clock.set_fixed_time("2027-04-03T12:00:00+08:00")
    page.goto(url, wait_until="domcontentloaded")
    page.evaluate("""candles => {
        const plot = PLOTS[0];
        const pet = mkPet("小满", "cat", "memorial", "#e8a04c", plot.x, plot.y, "", "");
        pet.mine = true; pet.plot = plot.no; pet.counts.candle = candles;
        S.pets.push(pet); S.myPetId = pet.id; S.avatarChosen = true; S.playerTotal = candles;
        S.lastGiftDate = "2027-4-3"; S.loginDays = 1;
        localStorage.setItem(SAVE_KEY, JSON.stringify(S));
    }""", candles)
    page.reload(wait_until="domcontentloaded")
    assert page.evaluate("myHomePet().counts.candle") == candles


def enter_settings(page):
    if page.locator("#titleOverlay").is_visible():
        page.click("#btnTitleLoad")
    if not page.locator("#hudDrawer").is_visible():
        page.click("#btnDrawer")
    if not page.locator("#btnImport").is_visible():
        page.click("#saveManagement summary")


def choose_file(page, button, raw):
    with page.expect_file_chooser() as chooser:
        page.click(button)
    chooser.value.set_files({"name": "园子.json", "mimeType": "application/json", "buffer": raw})


def snapshot(page):
    return page.evaluate("""() => {
        const raw = localStorage.getItem(SAVE_KEY);
        const refs = JSON.parse(raw).__gardenRecovery || [];
        return {raw, refs, backups: refs.map(key => localStorage.getItem(key)),
                legacy: localStorage.getItem(SAVE_KEY+'__bak2')};
    }""")


def play(browser, url, evidence):
    context = browser.new_context(viewport={"width": 375, "height": 667}, has_touch=True,
                                  is_mobile=True, timezone_id="Asia/Shanghai")
    page = context.new_page()
    errors = []
    context.on("page", lambda tab: tab.on("pageerror", lambda error: errors.append(str(error))))
    page.on("pageerror", lambda error: errors.append(str(error)))
    other = context.new_page()
    parsed = urlparse(url)
    host = "localhost" if parsed.hostname == "127.0.0.1" else "127.0.0.1"
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    alternate = parsed._replace(netloc=netloc).geturl()
    seed(page, url, 2)
    seed(other, alternate, 1)
    enter_settings(other)
    with other.expect_download() as download:
        other.click("#btnExport")
    incoming = download.value.path().read_bytes()
    assert "__gardenRecovery" not in json.loads(incoming)
    other.close()
    enter_settings(page)
    preview = page.get_by_role("dialog", name="导入文件，替换当前园子？")
    confirm = preview.get_by_role("button", name="确认导入")
    saved = snapshot(page)

    choose_file(page, "#btnImport", b'{"pets":[{}]}')
    page.wait_for_function("""document.getElementById('toast').textContent.includes('没有导入')
                           || toastQ.some(text=>text.includes('没有导入'))""")
    expect(preview).to_be_hidden()
    assert snapshot(page) == saved
    choose_file(page, "#btnImport", incoming)
    expect(preview.locator("#savePreviewCurrent")).to_contain_text("小满（纪念）")
    expect(preview.locator("#savePreviewCurrent")).to_contain_text("点烛 2 次")
    expect(preview.locator("#savePreviewNext")).to_contain_text("点烛 1 次")
    expect(preview.get_by_role("button", name="取消")).to_be_focused()
    if evidence:
        page.screenshot(path=evidence / "preview.png", animations="disabled")
    page.keyboard.press("Escape")
    expect(page.locator("#btnImport")).to_be_focused()
    assert snapshot(page) == saved
    print("PASS intact legacy current save after invalid JSON and keyboard cancellation", flush=True)

    choose_file(page, "#btnImport", incoming)
    with page.expect_navigation(wait_until="domcontentloaded"):
        confirm.click()
    assert page.evaluate("myHomePet().counts.candle === 1 && S.lastGiftDate === '2027-04-03'")
    restore = page.locator("#btnTitleRestore")
    expect(restore).to_be_visible()
    enter_settings(page)
    with page.expect_download() as download:
        page.click("#btnExport")
    identical = download.value.path().read_bytes()
    unchanged = snapshot(page)
    choose_file(page, "#btnImport", identical)
    page.wait_for_function("document.getElementById('toast').textContent.includes('已是当前园子') || toastQ.some(t=>t.includes('已是当前园子'))")
    expect(preview).to_be_hidden()
    assert snapshot(page) == unchanged
    page.reload(wait_until="domcontentloaded")
    restore.click()
    expect(page.locator("#savePreviewNext")).to_contain_text("点烛 2 次")
    if evidence:
        page.screenshot(path=evidence / "restore.png", animations="disabled")
    with page.expect_navigation(wait_until="domcontentloaded"):
        page.get_by_role("button", name="确认恢复").click()
    assert page.evaluate("myHomePet().counts.candle") == 2
    assert json.loads(snapshot(page)["backups"][0])["pets"][-1]["counts"]["candle"] == 1
    print("PASS UI export between origins, legacy date import, reload undo and reverse backup", flush=True)

    # Establish two committed snapshots before the following storage faults.
    third_state = json.loads(incoming)
    third_state["pets"][-1]["counts"]["candle"] = 3
    enter_settings(page)
    choose_file(page, "#btnImport", json.dumps(third_state).encode())
    with page.expect_navigation(wait_until="domcontentloaded"):
        confirm.click()
    enter_settings(page)
    saved = snapshot(page)
    assert len(saved["refs"]) == 2
    peer = context.new_page()
    peer.goto(url, wait_until="domcontentloaded")

    choose_file(page, "#btnImport", incoming)
    page.evaluate("""() => {
        const write = Storage.prototype.setItem, remove = Storage.prototype.removeItem;
        Storage.prototype.setItem = function(key, value) {
            if(key === SAVE_KEY) throw new DOMException('simulated primary failure', 'QuotaExceededError');
            return write.call(this, key, value);
        };
        Storage.prototype.removeItem = function(key) {
            if(isRecoveryKey(key)) throw new DOMException('simulated rollback failure', 'QuotaExceededError');
            return remove.call(this, key);
        };
        window.undoStorageFault = () => { Storage.prototype.setItem = write; Storage.prototype.removeItem = remove; };
    }""")
    confirm.click()
    expect(preview.get_by_role("alert")).to_contain_text("当前园子已保留")
    expect(confirm).to_be_enabled()
    assert snapshot(page) == saved
    expect(peer.locator("#staleBar")).to_be_hidden()
    page.evaluate("undoStorageFault()")
    print("PASS primary write and staging cleanup faults preserve both committed backups", flush=True)

    quota = page.evaluate("""() => {
        const filler = 'garden-test-quota-filler';
        let lo = 0, hi = 2**24, seen;
        while(lo + 1 < hi){
            const n = Math.floor((lo + hi)/2);
            try{ localStorage.setItem(filler,'x'.repeat(n)); lo = n; }
            catch(e){ seen = e.name; hi = n; }
        }
        localStorage.setItem(filler,'x'.repeat(lo-512));
        return {max:lo, failed:seen};
    }""")
    assert quota["failed"] == "QuotaExceededError" and quota["max"] > 512
    confirm.click()
    expect(preview.get_by_role("alert")).to_contain_text("当前园子已保留")
    expect(confirm).to_be_enabled()
    assert snapshot(page) == saved
    expect(peer.locator("#staleBar")).to_be_hidden()
    if evidence:
        page.screenshot(path=evidence / "quota.png", animations="disabled")
    page.evaluate("localStorage.removeItem('garden-test-quota-filler')")
    print("PASS browser quota failure keeps current save and both previous snapshots", flush=True)

    peer.click("#btnTitleLoad")
    peer.click("#btnMusic")
    latest = snapshot(peer)
    assert latest["raw"] != saved["raw"]
    confirm.click()
    expect(preview.get_by_role("alert")).to_contain_text("本机存档已更新")
    assert snapshot(page) == latest
    with page.expect_navigation(wait_until="domcontentloaded"):
        page.click("#btnStaleReload")
    title_peer = context.new_page()
    title_peer.goto(url, wait_until="domcontentloaded")
    enter_settings(page)
    choose_file(page, "#btnImport", incoming)
    with page.expect_navigation(wait_until="domcontentloaded"):
        confirm.click()
    expect(title_peer.locator("#staleBar")).to_be_visible()
    button = title_peer.get_by_role("button", name="刷新页面", exact=True)
    expect(button).to_be_enabled()
    assert button.evaluate("button => !button.closest('[inert]') && !!button.closest('#titleOverlay')")
    with title_peer.expect_navigation(wait_until="domcontentloaded"):
        button.click()
    expect(title_peer.locator("#staleBar")).to_be_hidden()
    assert title_peer.evaluate("myHomePet().counts.candle") == 1
    print("PASS rejected stale preview, inert title refresh and successor readback", flush=True)

    page.evaluate("""() => {
        const raw = JSON.parse(localStorage.getItem(SAVE_KEY));
        localStorage.setItem(raw.__gardenRecovery[0], 'bad json');
    }""")
    page.reload(wait_until="domcontentloaded")
    restore.click()
    expect(page.locator("#savePreviewNext")).to_contain_text("点烛 2 次")
    page.keyboard.press("Escape")

    canceled = browser.new_context()
    canceled_page = canceled.new_page()
    canceled_page.goto(url, wait_until="domcontentloaded")
    pristine = canceled_page.evaluate("localStorage.getItem(SAVE_KEY)")
    canceled_page.evaluate("""() => {
        const read = File.prototype.text;
        File.prototype.text = function() {
            return read.call(this).then(text => new Promise(resolve => {
                window.releaseCanceledImport = () => resolve(text);
            }));
        };
    }""")
    canceled_page.click("#btnTitleLoad")
    choose_file(canceled_page, "#btnLoadImport", incoming)
    canceled_page.wait_for_function("typeof releaseCanceledImport === 'function'")
    canceled_page.keyboard.press("Escape")
    canceled_page.evaluate("releaseCanceledImport()")
    canceled_page.wait_for_timeout(650)
    assert canceled_page.evaluate("localStorage.getItem(SAVE_KEY)") == pristine
    assert canceled_page.evaluate("myHomePet() === null")
    expect(canceled_page.locator("#btnTitleLoad")).to_be_visible()
    canceled.close()
    print("PASS identical upload preserves recoverability and cancel invalidates a file already being read", flush=True)

    fresh = browser.new_context()
    new_page = fresh.new_page()
    new_page.goto(url, wait_until="domcontentloaded")
    new_page.click("#btnTitleLoad")
    with new_page.expect_navigation(wait_until="domcontentloaded"):
        choose_file(new_page, "#btnLoadImport", incoming)
    assert new_page.evaluate("myHomePet().counts.candle") == 1
    fresh.close()
    assert not errors, errors
    print("PASS corrupt-newest fallback and pristine title file import", flush=True)
    context.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--browser", choices=["chromium", "webkit"], default="chromium")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    if urlparse(args.url).hostname not in ("127.0.0.1", "localhost"):
        parser.error("Use a local server")
    if args.evidence:
        args.evidence.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as driver:
        browser = getattr(driver, args.browser).launch()
        try:
            play(browser, args.url, args.evidence)
        finally:
            browser.close()
