import XCTest

final class NativeInputs: XCTestCase {
    let safari = XCUIApplication(bundleIdentifier: "com.apple.mobilesafari")
    func openGame(_ url: String) {
        continueAfterFailure = false
        safari.open(URL(string: url)!)
        for title in ["Continue", "Not Now", "Got It"] {
            let button = safari.buttons[title]
            if button.exists && button.isHittable { button.tap() }
        }
    }
    func button(_ label: String) -> XCUIElement {
        safari.webViews.buttons.matching(NSPredicate(format: "label CONTAINS %@", label)).firstMatch
    }
    func press(_ label: String, timeout: TimeInterval = 50) {
        let target = button(label)
        XCTAssertTrue(target.waitForExistence(timeout: timeout), label + ": " + safari.webViews.debugDescription.prefix(1300))
        target.tap()
    }
    func capture(_ title: String) {
        let item = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        item.name = title
        item.lifetime = .keepAlways
        add(item)
    }
    func tapGardenTitle() {
        let start = button("开始游戏")
        let load = button("读取存档")
        let window = safari.frame
        var lastFrame = CGRect.null
        let settled = NSPredicate { _, _ in
            guard start.exists, load.exists, start.isHittable else { return false }
            let frame = start.frame
            let ready = frame == lastFrame && frame.width > window.width / 2
                && window.contains(frame) && frame.midY > window.midY && load.frame.minY >= frame.maxY
            lastFrame = frame
            return ready
        }
        let rendered = XCTNSPredicateExpectation(predicate: settled, object: nil)
        XCTAssertEqual(XCTWaiter.wait(for: [rendered], timeout: 60), .completed)
        let frame = start.frame
        capture("garden-native-title")
        // Safari can return a stale default hit point during its initial page navigation.
        let origin = safari.coordinate(withNormalizedOffset: .zero)
        origin.withOffset(CGVector(dx: frame.midX - window.minX, dy: frame.midY - window.minY)).tap()
    }
    func testGardenTouch() {
        openGame("https://cyber-cemetery-proto.pages.dev/")
        tapGardenTitle()
        press("紫围裙")
        press("地图")
        press("带我去最近空位")
        let register = button("登记到这个碑位")
        XCTAssertTrue(register.waitForExistence(timeout: 85))
        XCTAssertTrue(register.isHittable, "登记按钮应在 Safari 工具栏上方直接可点")
        capture("garden-native-register")
        register.tap()
        let field = safari.webViews.textFields.firstMatch
        XCTAssertTrue(field.waitForExistence(timeout: 15))
        field.tap()
        field.typeText("Momo")
        XCTAssertEqual(field.value as? String, "Momo")
        capture("garden-native-name")
    }
    func testMountainKeyboard() {
        openGame("https://yunqi-shanzhong-v2-play.pages.dev/")
        let nickname = safari.webViews.textFields.firstMatch
        XCTAssertTrue(nickname.waitForExistence(timeout: 60))
        nickname.tap()
        nickname.typeText("River")
        XCTAssertEqual(nickname.value as? String, "River")
        capture("mountain-native-keyboard")
        press("从岔路口开始")
        XCTAssertTrue(button("选好了").waitForExistence(timeout: 45))
        capture("mountain-native-entry")
    }
}
