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
    func testGardenTouch() {
        openGame("https://cyber-cemetery-proto.pages.dev/")
        press("开始游戏")
        press("紫围裙")
        press("地图")
        press("带我去最近空位")
        press("登记到这个碑位", timeout: 85)
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
        XCTAssertTrue(button("跳过，保留原貌").waitForExistence(timeout: 45))
        capture("mountain-native-entry")
    }
}
