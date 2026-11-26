(async () => {
  const garden = location.hostname === "cyber-cemetery-proto.pages.dev"
  if (!garden && location.hostname !== "yunqi-shanzhong-v2-play.pages.dev") return
  const report = message => window.webkit.messageHandlers.report.postMessage(message)
  const find = selector => document.querySelector(selector)
  async function wait(check) {
    const until = Date.now() + 85000
    while (!check()) {
      if (Date.now() > until) throw new Error(String(check))
      await new Promise(resolve => setTimeout(resolve, 200))
    }
  }
  const visible = selector => find(selector)?.getClientRects().length
  async function click(selector) {
    await wait(() => visible(selector) && !find(selector).disabled)
    find(selector).click()
  }
  try {
    if (garden) {
      await click("#btnTitleMain")
      await click("[data-av=a4]")
      await click("#btnMapTop")
      await click("#btnNearestPlot")
      await wait(() => visible("#btnRegHere"))
      await click("#btnDrawer")
      await click("#btnCheckin")
      await wait(() => find("#checkinLabel").textContent.includes("今日已签到"))
    } else {
      await wait(() => visible("#nick"))
      find("#nick").value = "WebViewTest"
      find("#nick").dispatchEvent(new Event("input", {bubbles:true}))
      await click("#enter")
      await wait(() => visible("#lookPicker") || visible("#tripSkip") || visible("#btnMap"))
      if (visible("#lookPicker")) {
        await click("#lookChoices button")
        await click("#lookConfirm")
      }
      await wait(() => visible("#tripSkip") || visible("#btnMap"))
      if (visible("#tripSkip")) await click("#tripSkip")
      await click("#btnMap")
      await click("#mapDirectoryToggle")
      await click('.mpAct[data-hot="hall"]')
      await wait(() => visible(".prayer-panel"))
      find(".prayer-form input").value = "River"
      find(".prayer-form input").dispatchEvent(new Event("input", {bubbles:true}))
      await click(".prayer-form button[type=submit]")
      await wait(() => find(".prayer-current").textContent.includes("River"))
    }
    window.checkAfterResume = async () => {
      try {
        await wait(() => !document.hidden && (garden ? visible("#btnCheckin") : visible(".prayer-current")))
        if (garden) {
          if (!find("#btnCheckin").disabled || !find("#checkinLabel").textContent.includes("今日已签到")) throw new Error("Check-in lost")
        } else if (!find(".prayer-current").textContent.includes("River")) throw new Error("Recipient lost")
        report("PASS")
      } catch (error) { report("FAIL " + error.message) }
    }
    report("ready")
  } catch (error) { report("FAIL " + error.message) }
})()
